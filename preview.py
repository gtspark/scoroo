"""Render frames to a scaled-up PNG sheet for visual inspection (no device)."""
import sys

from PIL import Image

import espn
import render

SCALE = 8
FAVS = ["lakers", "49ers", "yankees"]
LEAGUES = ["nba", "nfl", "mlb"]


def scale(img):
    return img.resize((64 * SCALE, 64 * SCALE), Image.NEAREST)


def sheet(images, cols=4):
    rows = (len(images) + cols - 1) // cols
    pad = 8
    cell = 64 * SCALE
    sheet = Image.new("RGB", (cols * cell + (cols + 1) * pad,
                             rows * cell + (rows + 1) * pad), (40, 40, 40))
    for i, im in enumerate(images):
        r, c = divmod(i, cols)
        x = pad + c * (cell + pad)
        y = pad + r * (cell + pad)
        sheet.paste(scale(im), (x, y))
    return sheet


def synthetic():
    """Hand-built games to exercise live/pre/final + fav highlighting."""
    return [
        {"league": "nba", "label": "NBA", "state": "in", "status": "Q3 4:21",
         "away": {"abbr": "NY", "score": "78", "color": "1d428a", "fav": False, "record": "", "winner": False},
         "home": {"abbr": "SA", "score": "82", "color": "000000", "fav": True, "record": "", "winner": False}},
        {"league": "nfl", "label": "NFL", "state": "pre", "status": "1:05P",
         "away": {"abbr": "LAC", "score": "0", "color": "0080c6", "fav": True, "record": "11-3", "winner": False},
         "home": {"abbr": "KC", "score": "0", "color": "e31837", "fav": False, "record": "12-2", "winner": False}},
        {"league": "mlb", "label": "MLB", "state": "post", "status": "FINAL",
         "away": {"abbr": "LAD", "score": "5", "color": "005a9c", "fav": True, "record": "", "winner": True},
         "home": {"abbr": "SF", "score": "3", "color": "fd5a1e", "fav": False, "record": "", "winner": False}},
        {"league": "nba", "label": "NBA", "state": "post", "status": "FINAL/OT",
         "away": {"abbr": "BOS", "score": "121", "color": "007a33", "fav": False, "record": "", "winner": True},
         "home": {"abbr": "MIA", "score": "118", "color": "98002e", "fav": False, "record": "", "winner": False}},
    ]


if __name__ == "__main__":
    imgs = []
    if "--synthetic" in sys.argv or "--both" in sys.argv:
        imgs += [render.render_game(g) for g in synthetic()]
    if "--synthetic" not in sys.argv:
        games = espn.fetch_all(LEAGUES, FAVS)
        print(f"fetched {len(games)} real games")
        for g in games[:6]:
            print(" ", g["league"], g["state"], g["status"], g["away"]["abbr"], g["away"]["score"],
                  "@", g["home"]["abbr"], g["home"]["score"], "fav" if g["fav"] else "")
        if games:
            imgs += [render.render_game(g) for g in games[:4]]
        else:
            imgs.append(render.render_message("No games", "today", LEAGUES))
    out = "/home/admin/pixoo-scores/debug/preview.png"
    sheet(imgs).save(out)
    print("saved", out)
