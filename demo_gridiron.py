#!/usr/bin/env python3
"""On-device demo: cycle gridiron through its states (live / red-zone / pre /
final) on simulated NFL data, since it's the offseason. Run with the main
service stopped."""
import copy
import time

import espn
import render
from pixoo import Pixoo

espn.set_display_tz("Asia/Tokyo")
games = espn.fetch_league("nfl", ["49ers"])
g = next((x for x in games if "LAC" in (x["away"]["abbr"], x["home"]["abbr"])), games[0])


def mk(state, status, asc, hsc, sit=None, **e):
    x = copy.deepcopy(g)
    x["state"], x["status"] = state, status
    x["away"]["score"], x["home"]["score"] = asc, hsc
    if sit is not None:
        x["situation"] = sit
    x.update(e)
    return x


FRAMES = [
    mk("in", "Q3 8:42", "17", "20",
       {"possession": "away", "ball_pct": 68, "fd_pct": 75, "dd_text": "3RD & 7",
        "spot_text": "KC 32", "play_clock": 14, "red_zone": False}),
    mk("in", "Q4 2:05", "24", "20",
       {"possession": "away", "ball_pct": 94, "fd_pct": 100, "dd_text": "1ST & GL",
        "spot_text": "KC 4", "red_zone": True}),
    mk("post", "FINAL", "27", "20"),
]
LABELS = ["live 3rd&7", "RED ZONE", "final"]
FRAMES[0]["away"]["record"] = "9-3"  # not used live, harmless

dev = Pixoo("YOUR_PIXOO_IP")
HOLD = 9
i = 0
while True:
    try:
        dev.push(render.render_game(FRAMES[i % len(FRAMES)], "gridiron"))
        print(f"gridiron: {LABELS[i % len(LABELS)]}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"push fail: {e}", flush=True)
    i += 1
    time.sleep(HOLD)
