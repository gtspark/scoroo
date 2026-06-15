#!/usr/bin/env python3
"""Pixoo 64 sports scoreboard.

Polls ESPN across the configured leagues, prioritizes followed teams, and
rotates stylish 64x64 score cards on a Divoom Pixoo 64. A static "ticker board"
screen summarizes several games at once (the device's HTTP firmware can't do
smooth scrolling, so this is the glanceable multi-game view).

Run:  ./venv/bin/python app.py [path/to/config.json]
"""
import json
import logging
import os
import sys
import time
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

import espn
import render
from pixoo import Pixoo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("scoreboard")

HERE = os.path.dirname(os.path.abspath(__file__))


def load_config(path):
    with open(path) as f:
        return json.load(f)


def local_hour(tzname):
    tz = ZoneInfo(tzname) if (tzname and ZoneInfo) else None
    return datetime.now(tz).hour


def target_brightness(cfg):
    b = cfg.get("brightness", {})
    if not b:
        return None
    h = local_hour(cfg.get("timezone"))
    start, end = b.get("night_start_hour", 23), b.get("night_end_hour", 8)
    night = (h >= start or h < end) if start > end else (start <= h < end)
    return b.get("night", 25) if night else b.get("day", 90)


# --- lazy play-by-play cache: only pulled for games actually on screen ---
_SUMMARY_CACHE = {}                      # (kind, event_id) -> (ts, data)
_TIER3_CACHE = {"ts": 0.0, "games": []}  # favorites' recent/upcoming (slow-changing)


def _summary(kind, event_id, fetch_fn, ttl):
    key = (kind, event_id)
    now = time.time()
    hit = _SUMMARY_CACHE.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    try:
        data = fetch_fn()
        _SUMMARY_CACHE[key] = (now, data)
        return data
    except Exception as e:  # noqa: BLE001
        log.warning("%s fetch failed (%s): %s", kind, event_id, e)
        return hit[1] if hit else {}


def game_views(g):
    """Frames for one game in its sport-appropriate view(s). Basketball (NBA +
    WNBA) live -> momentum, final -> jumbotron (lazily pulling margins + stats)."""
    lg, eid, state = g["league"], g.get("event_id"), g["state"]
    if lg in ("nba", "wnba"):
        # live -> MOMENTUM (the in-progress flow); final -> JUMBOTRON tale-of-tape
        if state == "in":
            if eid:
                g.update(_summary("margins", eid, lambda: espn.fetch_margins(lg, eid), 20))
            return [render.render_game(g, "momentum")]
        if state == "post":
            if eid:
                g.update(_summary("stats", eid, lambda: espn.fetch_team_stats(lg, eid), 1800))
            return [render.render_game(g, "jumbotape")]
        return [render.render_game(g, "momentum")]  # pre: upcoming card
    if lg == "mlb":
        # final -> BOX SCORE (line score + decisions); pre/live -> DIAMOND.
        # If the box fetch comes back empty, fall back to the diamond final.
        if state == "post" and eid:
            g.update(_summary("box", eid, lambda: espn.fetch_mlb_box(eid), 1800))
            if g.get("box", {}).get("away_line"):
                return [render.render_game(g, "mlbbox")]
        return [render.render_game(g, "diamond")]
    if lg == "nfl":
        return [render.render_game(g, "gridiron")]
    return [render.render_game(g, "scorebug")]


def build_screens(cfg, games):
    """Tiered selector: 1) favorites live  2) Finals live (any team)
    3) favorites' recent + upcoming."""
    favs_live = [g for g in games if g["fav"] and g["state"] == "in"]
    if favs_live:
        tier, why = favs_live, "fav-live"
    elif [g for g in games if g["state"] == "in" and g.get("is_finals")]:
        tier = [g for g in games if g["state"] == "in" and g.get("is_finals")]
        why = "finals-live"
    else:
        now = time.time()
        if now - _TIER3_CACHE["ts"] > 600 or not _TIER3_CACHE["games"]:
            _TIER3_CACHE["games"] = espn.fetch_favorite_games(cfg["leagues"], cfg["favorites"])
            _TIER3_CACHE["ts"] = now
        tier, why = _TIER3_CACHE["games"], "fav recent/upcoming"
    tier = tier[: cfg.get("max_cards", 8)]
    log.info("tier=%s (%d games)", why, len(tier))
    screens = []
    for g in tier:
        screens += game_views(g)
    return screens or [render.blank()]


def main():
    cfg_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "config.json")
    cfg = load_config(cfg_path)
    espn.set_display_tz(cfg.get("timezone"))
    log.info("config: leagues=%s favorites=%s tz=%s",
             cfg["leagues"], cfg["favorites"], cfg.get("timezone"))

    dev = Pixoo(cfg["device_ip"])
    rotate = cfg.get("rotate_seconds", 7)
    # adaptive polling: fast while a game is live, slower when games exist but
    # none are in play, very slow when there's nothing on (data isn't changing).
    r_live = cfg.get("refresh_live", 8)
    r_idle = cfg.get("refresh_idle", 120)
    r_empty = cfg.get("refresh_empty", 1800)
    cur_refresh = r_live

    screens = []
    idx = 0
    last_fetch = 0.0
    last_brightness = None

    while True:
        now = time.time()
        # refresh data when the (adaptive) interval has elapsed
        if now - last_fetch >= cur_refresh or not screens:
            try:
                games = espn.fetch_all(cfg["leagues"], cfg["favorites"])
                screens = build_screens(cfg, games)
                last_fetch = now
                live = sum(1 for g in games if g["state"] == "in")
                cur_refresh = r_live if live else (r_idle if games else r_empty)
                log.info("refreshed: %d games (%d live) -> %d screens; next poll in %ds",
                         len(games), live, len(screens), cur_refresh)
            except Exception as e:  # noqa: BLE001
                log.warning("fetch failed: %s", e)
                cur_refresh = min(cur_refresh, 30)  # retry sooner after a failure
                if not screens:
                    screens = [render.blank()]

        # brightness schedule (only when it changes)
        want = target_brightness(cfg)
        if want is not None and want != last_brightness:
            try:
                dev.set_brightness(want)
                last_brightness = want
                log.info("brightness -> %d", want)
            except Exception as e:  # noqa: BLE001
                log.warning("set_brightness failed: %s", e)

        # push current screen
        if screens:
            idx %= len(screens)
            try:
                dev.push(screens[idx])
            except Exception as e:  # noqa: BLE001
                log.warning("push failed: %s", e)
            idx += 1

        time.sleep(rotate)


if __name__ == "__main__":
    main()
