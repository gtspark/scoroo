#!/usr/bin/env python3
"""Render a gallery of example screens into docs/ for the README.

Uses real ESPN data where it's available (the recent NBA Finals game, real MLB
finals + upcoming games) and realistic synthesized situations for layouts whose
live data isn't on right now (live diamond / gridiron, since MLB had nothing
live and the NFL is in the offseason)."""
import copy
import os

from PIL import Image

import espn
import render

espn.set_display_tz("Asia/Tokyo")
OUT = os.path.join(os.path.dirname(__file__), "docs")
SCALE = 8


def save(img, name):
    img.resize((64 * SCALE, 64 * SCALE), Image.NEAREST).save(os.path.join(OUT, name))
    print("wrote docs/" + name)


def find(games, pred, default=None):
    return next((g for g in games if pred(g)), default)


# --- NBA: recent Finals game (real margins + box stats) -----------------------
nba = espn.fetch_league("nba", ["lakers"], dates="20260605-20260615")
g = find(nba, lambda x: x.get("event_id"), nba[0] if nba else None)
if g:
    eid = g["event_id"]
    gm = copy.deepcopy(g)
    gm["state"] = "in"
    gm["status"] = "Q4 2:14"
    gm.update(espn.fetch_margins("nba", eid))
    save(render.render_game(gm, "momentum"), "example-momentum.png")

    gj = copy.deepcopy(g)
    gj["state"] = "post"
    gj.update(espn.fetch_team_stats("nba", eid))
    save(render.render_game(gj, "jumbotape"), "example-jumbotron.png")

# --- MLB: real box-score final (2-digit hits), real first-pitch pre -----------
mlb_fin = espn.fetch_league("mlb", [], dates="20260613-20260614")
gb = find(mlb_fin, lambda x: x["state"] == "post" and x.get("event_id"))
if gb:
    gb = copy.deepcopy(gb)
    gb.update(espn.fetch_mlb_box(gb["event_id"]))
    save(render.render_game(gb, "mlbbox"), "example-mlbbox.png")

mlb_up = espn.fetch_league("mlb", [], dates="20260616-20260617")
gp = find(mlb_up, lambda x: x["state"] == "pre")
if gp:
    save(render.render_game(gp, "diamond"), "example-diamond-pre.png")

# --- MLB: live diamond (synthesized at-bat on a real matchup) -----------------
if gp:
    gl = copy.deepcopy(gp)
    gl["state"] = "in"
    gl["status"] = "Bot 7th"
    gl["half"], gl["inning"] = "bot", "7TH"
    gl["away"]["score"], gl["home"]["score"] = "3", "4"
    gl["situation"] = {
        "balls": 3, "strikes": 2, "outs": 2,
        "bases": [True, False, True],   # runners on first + third
        "batter": "M. Betts", "pitcher": "J. Hader",
    }
    save(render.render_game(gl, "diamond"), "example-diamond-live.png")

# --- NFL: gridiron red-zone (synthesized drive, offseason) --------------------
nfl = espn.fetch_league("nfl", ["49ers"])
gg = find(nfl, lambda x: x.get("event_id"), nfl[0] if nfl else None)
if gg:
    gg = copy.deepcopy(gg)
    gg["state"], gg["status"] = "in", "Q4 2:05"
    gg["away"]["score"], gg["home"]["score"] = "24", "20"
    gg["situation"] = {
        "possession": "away", "ball_pct": 94, "fd_pct": 100,
        "dd_text": "1ST & GL", "spot_text": "KC 4", "red_zone": True,
    }
    save(render.render_game(gg, "gridiron"), "example-gridiron.png")

print("done")
