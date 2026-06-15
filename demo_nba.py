#!/usr/bin/env python3
"""Temporary on-device A/B: alternate scorebug <-> statline for a simulated live
NBA game (Game 5 slice) so the two NBA live views can be compared on the Pixoo.
Run while the main service is stopped. Ctrl-C / kill to end."""
import copy
import time

import espn
import render
from pixoo import Pixoo

espn.set_display_tz("Asia/Tokyo")
g = espn.fetch_league("nba", ["lakers"])[0]        # real NY@SA teams/logos/leaders
live = copy.deepcopy(g)
live["state"] = "in"
live["status"] = "Q3 5:42"
live["away"]["score"] = "71"
live["home"]["score"] = "74"

dev = Pixoo("YOUR_PIXOO_IP")
layouts = ["scorebug", "statline"]
HOLD = 8  # seconds per layout

i = 0
while True:
    lay = layouts[i % 2]
    try:
        dev.push(render.render_game(live, lay))
        print(f"showing: {lay}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"push fail: {e}", flush=True)
    i += 1
    time.sleep(HOLD)
