#!/usr/bin/env python3
"""On-device demo: real Game 5 shot charts, alternating SA and NY featured.
Run with the main service stopped."""
import copy
import time

import espn
import render
from pixoo import Pixoo

espn.set_display_tz("Asia/Tokyo")
g = espn.fetch_league("nba", ["lakers"])[0]

FRAMES, LABELS = [], []
for side, label in (("home", "SA"), ("away", "NY")):
    try:
        x = copy.deepcopy(g)
        x.update(espn.fetch_shots("nba", g["event_id"], x[side]["id"]))
        x["feat"] = side
        FRAMES.append(x)
        LABELS.append(label)
    except Exception as e:  # noqa: BLE001
        print(f"shots fetch failed ({label}): {e}", flush=True)

dev = Pixoo("YOUR_PIXOO_IP")
HOLD = 10
i = 0
while FRAMES:
    try:
        dev.push(render.render_game(FRAMES[i % len(FRAMES)], "court"))
        print(f"court: {LABELS[i % len(LABELS)]}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"push fail: {e}", flush=True)
    i += 1
    time.sleep(HOLD)
