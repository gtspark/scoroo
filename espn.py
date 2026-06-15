"""ESPN scoreboard fetch + normalization.

Public ESPN site API, no key required:
  https://site.api.espn.com/apis/site/v2/sports/<path>/scoreboard
"""
import logging
import unicodedata
from datetime import datetime, timedelta

import requests

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

log = logging.getLogger("espn")


def _ascii(s):
    """Fold accents to ASCII so the bitmap micro-font can render player names
    (Hernández -> Hernandez); the font has no accented glyphs and would show '?'."""
    if not s:
        return s
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


# Display timezone for start times. US leagues are conventionally listed in ET;
# app.py can override via set_display_tz(). None => host local time.
_DISPLAY_TZ = None
_TZ_TAG = ""


def set_display_tz(name):
    """Set the tz used to render start times, e.g. 'America/New_York'."""
    global _DISPLAY_TZ, _TZ_TAG
    if not name or ZoneInfo is None:
        _DISPLAY_TZ, _TZ_TAG = None, ""
        return
    try:
        _DISPLAY_TZ = ZoneInfo(name)
        _TZ_TAG = {"America/New_York": "et", "America/Chicago": "ct",
                   "America/Denver": "mt", "America/Los_Angeles": "pt",
                   "Asia/Tokyo": "jst"}.get(name, "")
    except Exception as e:  # noqa: BLE001
        log.warning("bad tz %s: %s", name, e)
        _DISPLAY_TZ, _TZ_TAG = None, ""

BASE = "https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard"

# league key -> (espn path, pretty label)
LEAGUES = {
    "nba": ("basketball/nba", "NBA"),
    "wnba": ("basketball/wnba", "WNBA"),
    "nfl": ("football/nfl", "NFL"),
    "mlb": ("baseball/mlb", "MLB"),
    "nhl": ("hockey/nhl", "NHL"),
    "epl": ("soccer/eng.1", "EPL"),
}


def _matches_fav(team, favorites):
    """True if any favorite string matches this ESPN team object."""
    fields = [
        team.get("abbreviation", ""),
        team.get("name", ""),
        team.get("shortDisplayName", ""),
        team.get("displayName", ""),
        team.get("location", ""),
        team.get("nickname", ""),
    ]
    hay = " ".join(f.lower() for f in fields if f)
    for fav in favorites:
        f = fav.strip().lower()
        if f and f in hay:
            return True
    return False


def _fmt_status(league, status, comp):
    """Return a short status string and the state (pre/in/post)."""
    st = status.get("type", {})
    state = st.get("state", "pre")  # pre / in / post
    if state == "post":
        detail = (st.get("shortDetail") or st.get("detail") or "FINAL").upper()
        # compact overtime/shootout suffixes so they fit the header
        detail = detail.replace("FINAL/", "F/").replace("/SO", "/SO")
        return detail, state
    if state == "in":
        if league == "mlb":
            # e.g. "Top 5th" / "Bot 9th" / "Mid 3rd"
            return (st.get("shortDetail") or "LIVE").upper(), state
        period = status.get("period", 0)
        clock = status.get("displayClock", "")
        if league in ("nba", "wnba", "nfl"):
            qlabel = f"Q{period}" if period <= 4 else ("OT" if period == 5 else f"{period - 4}OT")
        elif league == "nhl":
            qlabel = f"P{period}" if period <= 3 else "OT"
        else:
            qlabel = st.get("shortDetail", "")
        return f"{qlabel} {clock}".strip(), state
    # pre: show start time in the configured display tz (default host local)
    iso = comp.get("date") or status.get("type", {}).get("detail", "")
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        dt = dt.astimezone(_DISPLAY_TZ) if _DISPLAY_TZ else dt.astimezone()
        return dt.strftime("%H:%M"), state  # 24hr, no am/pm, no tz tag
    except Exception:  # noqa: BLE001
        return (st.get("shortDetail") or "SOON").upper(), state


def _start_epoch(comp):
    try:
        return datetime.fromisoformat(comp["date"].replace("Z", "+00:00")).timestamp()
    except Exception:  # noqa: BLE001
        return 0.0


def _fmt_date(comp):
    """Short calendar date in the display tz, e.g. 'JUN 16'."""
    try:
        dt = datetime.fromisoformat(comp["date"].replace("Z", "+00:00"))
        dt = dt.astimezone(_DISPLAY_TZ) if _DISPLAY_TZ else dt.astimezone()
        return dt.strftime("%b %d").upper().replace(" 0", " ")  # 'JUN 6' not 'JUN 06'
    except Exception:  # noqa: BLE001
        return ""


def fetch_league(league_key, favorites, timeout=12, dates=None):
    path, label = LEAGUES[league_key]
    url = BASE.format(path=path)
    if dates:
        url += f"?dates={dates}"
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    games = []
    # Parse each event in isolation: a single malformed event (e.g. a TBD /
    # placeholder with no 'competitions') is skipped, not allowed to drop the
    # whole league's slate for the cycle.
    for event in data.get("events", []):
        try:
            g = _parse_event(league_key, label, event, favorites)
        except Exception as e:  # noqa: BLE001
            log.warning("%s: skipping malformed event %s: %s",
                        league_key, event.get("id"), e)
            continue
        if g:
            games.append(g)
    return games


def _parse_event(league_key, label, event, favorites):
    """Turn one ESPN scoreboard event into a game dict (or None to skip)."""
    comps = event.get("competitions") or []
    if not comps:
        return None
    comp = comps[0]
    status = event.get("status", {})
    status_txt, state = _fmt_status(league_key, status, comp)

    # --- playoff / series metadata ---
    playoff = event.get("season", {}).get("type") == 3
    series = comp.get("series") or {}
    series_wins = {str(sc.get("id")): sc.get("wins", 0) for sc in series.get("competitors", [])}
    total = series.get("totalCompetitions") or 7
    series_needed = total // 2 + 1
    headline = ""
    for note in comp.get("notes", []) or []:
        if note.get("headline"):
            headline = note["headline"]
            break
    po_round, po_game = _parse_headline(headline)
    # championship finals only (not conference/division finals)
    low_hl = headline.lower()
    is_finals = playoff and (
        ("finals" in low_hl and "conference" not in low_hl and "division" not in low_hl)
        or "world series" in low_hl or "super bowl" in low_hl or "stanley cup" in low_hl
    )

    teams = {}
    any_fav = False
    for c in comp.get("competitors", []):
        t = c.get("team", {})
        fav = _matches_fav(t, favorites)
        any_fav = any_fav or fav
        record = ""
        for rec in c.get("records", []) or []:
            if rec.get("type") in ("total", None) or rec.get("name") == "overall":
                record = rec.get("summary", "")
                break
        teams[c.get("homeAway", "home")] = {
            "id": str(t.get("id", "")),
            "series_wins": series_wins.get(str(t.get("id", "")), 0),
            "abbr": t.get("abbreviation", "???"),
            "name": t.get("shortDisplayName") or t.get("name", ""),
            "score": c.get("score", "0"),
            "color": (t.get("color") or "202020"),
            "alt": (t.get("alternateColor") or "404040"),
            "logo": t.get("logo", ""),
            "fav": fav,
            "winner": c.get("winner", False),
            "record": record,
            "leaders": _extract_leaders(c),
        }
    if "home" not in teams or "away" not in teams:
        return None
    sit = comp.get("situation") or {}
    situation = {
        # MLB
        "balls": sit.get("balls") or 0,
        "strikes": sit.get("strikes") or 0,
        "outs": sit.get("outs") or 0,
        "bases": [bool(sit.get("onFirst")), bool(sit.get("onSecond")), bool(sit.get("onThird"))],
        "batter": _ascii(((sit.get("batter") or {}).get("athlete", {}) or {}).get("shortName", "")),
        "pitcher": _ascii(((sit.get("pitcher") or {}).get("athlete", {}) or {}).get("shortName", "")),
    }
    # NFL drive situation (only populated during live football). The yardLine
    # -> field-percent mapping is best-effort and needs a live game to verify.
    poss_id = str(sit.get("possession") or "")
    poss_side = None
    if poss_id == teams.get("away", {}).get("id"):
        poss_side = "away"
    elif poss_id == teams.get("home", {}).get("id"):
        poss_side = "home"
    yard, dist = sit.get("yardLine"), sit.get("distance")
    situation.update({
        "down": sit.get("down"),
        "distance": dist,
        "dd_text": (sit.get("shortDownDistanceText") or sit.get("downDistanceText") or "").upper(),
        "spot_text": (sit.get("possessionText") or "").upper(),
        "red_zone": bool(sit.get("isRedZone")),
        "possession": poss_side,
        "ball_pct": yard if isinstance(yard, (int, float)) else None,
        "fd_pct": min(100, yard + dist) if isinstance(yard, (int, float)) and isinstance(dist, (int, float)) else None,
    })
    # half/inning from the status detail ("Top 9th" -> half=top, inning=9TH)
    parts = status_txt.split()
    half = parts[0].lower() if parts else ""
    inning = parts[1] if len(parts) > 1 else (parts[0] if parts else "")

    return {
        "league": league_key,
        "event_id": event.get("id"),
        "label": label,
        "state": state,
        "status": status_txt,
        "date_short": _fmt_date(comp),
        "situation": situation,
        "half": half,
        "inning": inning,
        "home": teams["home"],
        "away": teams["away"],
        "fav": any_fav,
        "start": _start_epoch(comp),
        "playoff": playoff,
        "is_finals": is_finals,
        "po_round": po_round,
        "po_game": po_game,
        "series_summary": series.get("summary", ""),
        "series_needed": series_needed,
    }


def fetch_margins(league_key, event_id, timeout=12):
    """Build the lead-margin series (away_score - home_score over scoring plays)
    for the momentum layout, plus the current run and lead-change count. Pulls
    the play-by-play summary endpoint — one richer call per momentum game."""
    path = LEAGUES[league_key][0]
    url = f"https://site.api.espn.com/apis/site/v2/sports/{path}/summary?event={event_id}"
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    d = r.json()
    comps = (d.get("header", {}).get("competitions") or [{}])[0].get("competitors", [])
    away_id = next((str(c["team"]["id"]) for c in comps if c.get("homeAway") == "away"), None)
    scoring = [p for p in (d.get("plays") or []) if p.get("scoringPlay")]
    margins = [0]
    for p in scoring:
        a, h = p.get("awayScore"), p.get("homeScore")
        if a is not None and h is not None:
            margins.append(a - h)
    # current run: trailing consecutive scoring by one team
    run, run_team = "", ""
    if scoring:
        last_team = str((scoring[-1].get("team") or {}).get("id"))
        pts = 0
        for p in reversed(scoring):
            if str((p.get("team") or {}).get("id")) == last_team:
                pts += p.get("scoreValue", 0) or 0
            else:
                break
        if pts >= 5:
            run = f"{pts}-0"
            run_team = "away" if last_team == away_id else "home"
    # lead changes (sign flips, ignoring ties)
    lc, prev = 0, 0
    for v in margins:
        if v != 0:
            if prev != 0 and (v < 0) != (prev < 0):
                lc += 1
            prev = v
    return {"margins": margins, "run": run, "run_team": run_team, "lead_changes": lc}


def fetch_team_stats(league_key, event_id, timeout=12):
    """Head-to-head team box-score stats for the jumbotron (FG% / 3PT / REB / AST)."""
    path = LEAGUES[league_key][0]
    url = f"https://site.api.espn.com/apis/site/v2/sports/{path}/summary?event={event_id}"
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    teams = (r.json().get("boxscore", {}) or {}).get("teams", []) or []
    by = {t.get("homeAway"): {s.get("name"): s.get("displayValue") for s in t.get("statistics", []) or []}
          for t in teams}
    a, h = by.get("away", {}), by.get("home", {})

    def made(v):                       # "12-37" -> "12"
        return (v or "-").split("-")[0]

    rows = [
        ("FG%", a.get("fieldGoalPct"), h.get("fieldGoalPct")),
        ("3PT", made(a.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted")),
                made(h.get("threePointFieldGoalsMade-threePointFieldGoalsAttempted"))),
        ("REB", a.get("totalRebounds"), h.get("totalRebounds")),
        ("AST", a.get("assists"), h.get("assists")),
    ]
    stats = [{"k": k, "a": av or "-", "h": hv or "-"} for k, av, hv in rows]
    return {"jumbo_stats": stats}


def _last_name(short):
    """ESPN shortName 'M. Liberatore' -> 'LIBERATORE'."""
    if not short:
        return ""
    return _ascii(short).replace(".", "").split()[-1].upper()


def fetch_mlb_box(event_id, timeout=12):
    """Full line score (runs by inning + R/H/E) plus pitching decisions and the
    home-run log for the MLB box-score final layout. One richer summary pull."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/summary?event={event_id}"
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    d = r.json()

    comp = (d.get("header", {}).get("competitions") or [{}])[0]
    sides = {}
    for c in comp.get("competitors", []):
        sides[c.get("homeAway")] = {
            "line": [str(x.get("displayValue", "")) for x in c.get("linescores", []) or []],
            "R": str(c.get("score", "0")),
            "H": str(c.get("hits", 0)),
            "E": str(c.get("errors", 0)),
        }
    a, h = sides.get("away", {}), sides.get("home", {})
    n = max(len(a.get("line", [])), len(h.get("line", [])), 9)

    def padline(side):
        ln = list(side.get("line", []))
        # a shorter line = team didn't bat that inning (e.g. home leading after 9)
        return [ln[i] if i < len(ln) else "x" for i in range(n)]

    wp = lp = ("", "")
    hrs = []
    for tm in (d.get("boxscore", {}) or {}).get("players", []) or []:
        for cat in tm.get("statistics", []) or []:
            labels = cat.get("labels", []) or []
            hr_i = labels.index("HR") if "HR" in labels else -1
            for ath in cat.get("athletes", []) or []:
                nm = _last_name((ath.get("athlete") or {}).get("shortName"))
                st = ath.get("stats", []) or []
                for note in ath.get("notes", []) or []:
                    if note.get("type") == "pitchingDecision":
                        ip = st[0] if st else "?"
                        k = st[5] if len(st) > 5 else "?"
                        line = (nm, f"{ip}IP {k}K")
                        if note.get("text", "").startswith("W"):
                            wp = line
                        elif note.get("text", "").startswith("L"):
                            lp = line
                if cat.get("type") == "batting" and hr_i >= 0 and len(st) > hr_i:
                    v = st[hr_i]
                    if v not in ("0", "", None):
                        try:
                            cnt = int(v)
                        except ValueError:
                            cnt = 1
                        hrs.append(nm if cnt == 1 else f"{nm} {cnt}")

    return {"box": {
        "away_line": padline(a), "home_line": padline(h),
        "away_R": a.get("R", "0"), "away_H": a.get("H", "0"), "away_E": a.get("E", "0"),
        "home_R": h.get("R", "0"), "home_H": h.get("H", "0"), "home_E": h.get("E", "0"),
        "wp": wp[0], "wpL": wp[1], "lp": lp[0], "lpL": lp[1],
        "hr": hrs, "innings": n,
    }}


def fetch_shots(league_key, event_id, feat_id, limit=18, timeout=12):
    """Shot chart for the featured team: map ESPN shot coordinates (~0-50) into
    the 64px court, compute FG made/attempted and the hottest zone. FG/hot are
    full-game; only the most recent `limit` shots are plotted (80+ on one 64px
    court is an unreadable blob — keep it to a recent, glanceable subset)."""
    path = LEAGUES[league_key][0]
    url = f"https://site.api.espn.com/apis/site/v2/sports/{path}/summary?event={event_id}"
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    plays = (r.json().get("plays") or [])
    shots, made, att = [], 0, 0
    zones = {"PAINT": 0, "WING": 0, "TOP": 0}
    for p in plays:
        if not p.get("shootingPlay"):
            continue
        if str((p.get("team") or {}).get("id")) != str(feat_id):
            continue
        c = p.get("coordinate") or {}
        x, y = c.get("x"), c.get("y")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            continue
        if not (0 <= x <= 50 and 0 <= y <= 50):   # skip free throws / sentinels
            continue
        att += 1
        m = bool(p.get("scoringPlay"))
        cx = round(5 + (x / 50) * 53)              # ESPN -> court space
        cy = round(15 + (y / 47) * 40)
        shots.append({"x": cx, "y": cy, "m": m})
        if m:
            made += 1
            if cy < 28 and 24 < cx < 40:
                zones["PAINT"] += 1
            elif 24 < cx < 40:
                zones["TOP"] += 1
            else:
                zones["WING"] += 1
    hot = max(zones, key=zones.get) if made else ""
    plotted = shots[-limit:] if limit else shots
    return {"shots": plotted, "fg": f"{made}/{att}", "hot": hot}


def _extract_leaders(c):
    """Per-competitor scoring leaders -> {'PTS': (name, value), 'REB': ..., 'AST': ...}.
    ESPN uses 'points'/'rebounds'/'assists' live and '...PerGame' pre-game."""
    out = {}
    for cat in c.get("leaders", []) or []:
        name = (cat.get("name") or "").lower()
        ldr = (cat.get("leaders") or [{}])[0]
        ath = ldr.get("athlete", {}) or {}
        disp = ldr.get("displayValue", "") or ""
        num = ""
        for ch in disp:                      # parse the leading number
            if ch.isdigit() or ch == ".":
                num += ch
            elif num:
                break
        try:
            val = float(num) if num else 0.0
        except ValueError:
            val = 0.0
        short = _ascii(ath.get("shortName") or ath.get("displayName", ""))
        if "point" in name:
            out.setdefault("PTS", (short, val))
        elif "rebound" in name:
            out.setdefault("REB", (short, val))
        elif "assist" in name:
            out.setdefault("AST", (short, val))
    return out


def _parse_headline(headline):
    """'NBA Finals - Game 5' -> ('FINALS', 5). Round name kept short for 64px."""
    if not headline:
        return "", None
    parts = headline.split(" - ")
    low = parts[0].strip().lower()
    if "finals" in low and "conference" not in low:
        rnd = "FINALS"
    elif "western conference finals" in low:
        rnd = "WCF"
    elif "eastern conference finals" in low:
        rnd = "ECF"
    elif "conference finals" in low:
        rnd = "CONF FINALS"
    elif "semifinal" in low or "conference semi" in low:
        rnd = "SEMIS"
    elif "first round" in low:
        rnd = "RD 1"
    elif "play-in" in low or "play in" in low:
        rnd = "PLAY-IN"
    else:
        rnd = parts[0].strip().upper()[:11]
    game_no = None
    for p in parts[1:]:
        digits = "".join(ch for ch in p if ch.isdigit())
        if digits:
            game_no = int(digits)
    return rnd, game_no


def fetch_favorite_games(leagues, favorites, days_back=3, days_fwd=10):
    """Tier 3: ONE card per favorite team — its single most relevant game (live,
    else the next upcoming, else the most recent), not its whole slate. Scans a
    date window so just-finished and about-to-start games are both candidates."""
    now = datetime.now(_DISPLAY_TZ) if _DISPLAY_TZ else datetime.now()
    dates = f"{(now - timedelta(days=days_back)):%Y%m%d}-{(now + timedelta(days=days_fwd)):%Y%m%d}"
    out = []
    for lk in leagues:
        if lk not in LEAGUES:
            continue
        try:
            out += [g for g in fetch_league(lk, favorites, dates=dates) if g["fav"]]
        except Exception as e:  # noqa: BLE001
            log.warning("range fetch %s failed: %s", lk, e)
    ref = now.timestamp()

    def rank(g):
        # lower is better: live first, then soonest upcoming, then most recent past
        s = g["start"] or 0
        if g["state"] == "in":
            return (0, 0.0)
        if s >= ref:
            return (1, s - ref)        # upcoming: soonest first
        return (2, ref - s)            # past: most recent first

    # pick the best-ranked game for each favorite team
    best = {}
    for g in out:
        r = rank(g)
        for side in (g["away"], g["home"]):
            ab = side.get("abbr")
            if side.get("fav") and (ab not in best or r < best[ab][0]):
                best[ab] = (r, g)
    # one game can be the pick for two favorites (they're playing each other) —
    # dedup by event id, ordered live -> upcoming -> recent for display
    chosen, seen = [], set()
    for r, g in sorted(best.values(), key=lambda rg: rg[0]):
        gid = g.get("event_id") or id(g)
        if gid not in seen:
            seen.add(gid)
            chosen.append(g)
    return chosen


def fetch_all(leagues, favorites):
    """Fetch every configured league, sorted by display priority."""
    all_games = []
    for lk in leagues:
        if lk not in LEAGUES:
            log.warning("unknown league %s, skipping", lk)
            continue
        try:
            all_games.extend(fetch_league(lk, favorites))
        except Exception as e:  # noqa: BLE001
            log.warning("fetch %s failed: %s", lk, e)
    all_games.sort(key=_sort_key)
    return all_games


# State rank: live first, then upcoming, then final.
_STATE_RANK = {"in": 0, "pre": 1, "post": 2}
# Basketball leads; NBA and WNBA tie so they interleave purely by game time
# (the `start` tiebreaker in _sort_key), with no preference between them.
_LEAGUE_RANK = {"nba": 0, "wnba": 0, "nfl": 1, "mlb": 2, "nhl": 3, "epl": 4}


def _sort_key(g):
    return (
        0 if g["fav"] else 1,                 # favorite teams first
        _STATE_RANK.get(g["state"], 3),       # live > upcoming > final
        _LEAGUE_RANK.get(g["league"], 9),     # NBA first among leagues
        g["start"],                           # earliest start first
    )
