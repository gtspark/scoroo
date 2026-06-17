#!/usr/bin/env python3
"""On-device splash rotation: cycles the given splash kinds so you can eyeball the
animations on the Pixoo. Run with the main service stopped.

    ./venv/bin/python demo_splashes.py hr,slam,walkoff
"""
import sys
import time

import splash
from pixoo import Pixoo, device_ip

KINDS = (sys.argv[1] if len(sys.argv) > 1 else ",".join(splash.SPLASHES)).split(",")
HOLD = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0   # seconds looping per splash

# representative sample data so the name/number/distance bindings show
SAMPLE = {
    'hr':      {'player': 'Ohtani',  'number': '17', 'detail': "417'", 'away_abbr': 'TB',  'home_abbr': 'LAD', 'score': ('0', '1')},
    'slam':    {'player': 'Freeman', 'number': '5',  'detail': "412'", 'away_abbr': 'SF',  'home_abbr': 'LAD', 'score': ('2', '6')},
    'walkoff': {'player': 'Betts',   'number': '50', 'away_abbr': 'SF',  'home_abbr': 'LAD', 'score': ('3', '4')},
    'buzzer':  {'player': 'Clark',   'number': '22', 'detail': "26'",  'away_abbr': 'NY',  'home_abbr': 'IND', 'score': ('78', '80')},
    'three':   {'player': 'Clark',   'number': '22', 'detail': "29'",  'away_abbr': 'NY',  'home_abbr': 'IND', 'score': ('77', '78')},
    'td':      {'player': 'Herbert', 'number': '10', 'detail': '42 YD', 'away_abbr': 'KC', 'home_abbr': 'LAC', 'score': ('14', '21')},
    'picksix': {'player': 'James',   'number': '3',  'detail': '55 YD', 'away_abbr': 'KC', 'home_abbr': 'LAC', 'score': ('14', '28')},
    'fg':      {'player': 'Dicker',  'number': '15', 'detail': '59 YD', 'away_abbr': 'KC', 'home_abbr': 'LAC', 'score': ('20', '23')},
}

dev = Pixoo(device_ip())
print(f"rotating splashes: {KINDS} ({HOLD}s each)")
i = 0
while True:
    k = KINDS[i % len(KINDS)].strip()
    frames, spd = splash.animate(k, SAMPLE.get(k, {}), fps=16)
    print(f"  playing {k}", flush=True)
    dev.push_animation(frames, speed_ms=spd)
    time.sleep(HOLD)
    i += 1
