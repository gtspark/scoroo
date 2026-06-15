#!/usr/bin/env python3
"""On-device demo: cycle the momentum lead-tracker through three game-shapes
(nailbiter / comeback / blowout) on simulated NBA data, since no NBA game is
live to pull real margins from. Run while the main service is stopped."""
import copy
import time

import espn
import render
from pixoo import Pixoo, device_ip

espn.set_display_tz("Asia/Tokyo")
g = espn.fetch_league("nba", ["lakers"])[0]


def mk(state, status, asc, hsc, margins, **extra):
    x = copy.deepcopy(g)
    x["state"], x["status"] = state, status
    x["away"]["score"], x["home"]["score"], x["margins"] = asc, hsc, margins
    x.update(extra)
    return x


FRAMES = [
    mk("in", "Q4 2:18", "96", "99",
       [0, 2, 4, 2, 5, 3, 6, 4, 2, -1, -3, -1, 2, 4, 1, -2, -4, -2, 0, 3, 1, -2, -1, 1, -1, -2, -1, -2, -3, -3],
       run="6-0", run_team="home"),
    mk("in", "Q4 5:40", "88", "94",
       [0, 3, 6, 9, 12, 11, 14, 13, 15, 12, 10, 8, 9, 6, 7, 4, 5, 2, 3, 0, -2, -1, -3, -2, -4, -3, -5, -4, -5, -6],
       run="8-0", run_team="home"),
    mk("post", "FINAL", "124", "102",
       [0, 1, 3, 2, 4, 6, 5, 8, 10, 9, 11, 13, 12, 14, 15, 14, 16, 18, 17, 19, 20, 19, 21, 22, 21, 22, 23, 22, 22, 22]),
]
LABELS = ["nailbiter", "comeback", "blowout"]

# prepend the REAL Game 5 momentum pulled from play-by-play
try:
    real = copy.deepcopy(g)
    real.update(espn.fetch_margins("nba", g["event_id"]))
    FRAMES.insert(0, real)
    LABELS.insert(0, "REAL game5")
except Exception as e:  # noqa: BLE001
    print(f"real margins fetch failed: {e}", flush=True)

dev = Pixoo(device_ip())
HOLD = 9
i = 0
while True:
    try:
        dev.push(render.render_game(FRAMES[i % len(FRAMES)], "momentum"))
        print(f"momentum: {LABELS[i % len(LABELS)]}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"push fail: {e}", flush=True)
    i += 1
    time.sleep(HOLD)
