#!/usr/bin/env python3
"""Switch the scoreboard layout and restart the service.

Usage:
    ./venv/bin/python layout.py            # show current + options
    ./venv/bin/python layout.py neon       # lock a layout
    ./venv/bin/python layout.py all        # cycle through every layout live
"""
import json
import os
import subprocess
import sys

import render

HERE = os.path.dirname(os.path.abspath(__file__))
CFG = os.path.join(HERE, "config.json")
CHOICES = render.LAYOUT_ORDER + render.PLAYOFF_ORDER + ["all"]


def main():
    with open(CFG) as f:
        cfg = json.load(f)
    cur = cfg.get("layout", "broadcast")
    if len(sys.argv) < 2:
        print(f"current layout: {cur}")
        print("options:", ", ".join(CHOICES))
        return
    want = sys.argv[1].lower()
    if want not in CHOICES:
        print(f"unknown layout '{want}'. options: {', '.join(CHOICES)}")
        sys.exit(1)
    cfg["layout"] = want
    with open(CFG, "w") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")
    print(f"layout: {cur} -> {want}")
    r = subprocess.run(["sudo", "systemctl", "restart", "pixoo-scores"])
    print("service restarted" if r.returncode == 0 else "restart failed (run: sudo systemctl restart pixoo-scores)")


if __name__ == "__main__":
    main()
