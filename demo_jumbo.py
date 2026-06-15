#!/usr/bin/env python3
"""On-device demo: cycle the new tale-of-the-tape jumbotron through three zoom
levels (tight -> loose) on a simulated live NBA game, so the logo-crop look can
be judged on the actual LEDs. Run while the main service is stopped."""
import copy
import time

import espn
import render
from pixoo import Pixoo

espn.set_display_tz("Asia/Tokyo")
g = espn.fetch_league("nba", ["lakers"])[0]   # real Game 5 (final, 94-90)
live = copy.deepcopy(g)
try:
    live.update(espn.fetch_team_stats("nba", g["event_id"]))   # REAL box-score stats
except Exception as e:  # noqa: BLE001
    print(f"stats fetch failed: {e}", flush=True)

dev = Pixoo("YOUR_PIXOO_IP")
ZOOMS = [120]   # locked: the tight crop reads as the team at a glance
HOLD = 9

i = 0
while True:
    z = ZOOMS[i % len(ZOOMS)]
    live["jumbo_zoom"] = z
    try:
        dev.push(render.render_game(live, "jumbotape"))
        print(f"jumbotron zoom={z}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"push fail: {e}", flush=True)
    i += 1
    time.sleep(HOLD)
