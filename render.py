"""Render a game (or status screen) to a 64x64 Pillow image.

Five switchable layouts, designed in consultation with Gemini to fight the
"flat" look of solid color bands. Pick via config `layout` (or "all" to rotate
through every layout so you can compare them live):

    bands       - clean color bands (the original)
    jumbotron   - beveled 3D stadium light-boxes with depth shading
    diagonal    - bold diagonal team split, versus energy, stroked text
    neon        - black bg, glowing HSV-boosted neon outlines
    broadcast   - modern TV lower-third panels with gradient depth

Labels in Tiny5, scores in Press Start 2P, pixel-crisp (no antialiasing).
"""
import colorsys
import math
import os

from PIL import Image, ImageDraw, ImageFont

import logos

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "assets", "fonts")

SIZE = 64
GOLD = (255, 210, 74)
HEADER_BG = (14, 16, 20)
WHITE = (236, 238, 240)
BLACK = (8, 8, 10)

_font_cache = {}


def font(name, size):
    key = (name, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(os.path.join(FONT_DIR, name), size)
    return _font_cache[key]


def big(size):      # Press Start 2P — blocky scores / numbers
    return font("PressStart2P.ttf", size)


def small(size):    # Tiny5 — narrow labels
    return font("Tiny5.ttf", size)


# 3x5 bitmap micro-font (ported from design-Claude's mockup) — denser than any
# TTF at this size, ideal for stat lines. '#' = lit pixel.
MICRO = {
    '0': ['###', '#.#', '#.#', '#.#', '###'], '1': ['.#.', '##.', '.#.', '.#.', '###'],
    '2': ['###', '..#', '###', '#..', '###'], '3': ['###', '..#', '.##', '..#', '###'],
    '4': ['#.#', '#.#', '###', '..#', '..#'], '5': ['###', '#..', '###', '..#', '###'],
    '6': ['###', '#..', '###', '#.#', '###'], '7': ['###', '..#', '..#', '..#', '..#'],
    '8': ['###', '#.#', '###', '#.#', '###'], '9': ['###', '#.#', '###', '..#', '###'],
    'A': ['###', '#.#', '###', '#.#', '#.#'], 'B': ['##.', '#.#', '##.', '#.#', '##.'],
    'C': ['###', '#..', '#..', '#..', '###'], 'D': ['##.', '#.#', '#.#', '#.#', '##.'],
    'E': ['###', '#..', '##.', '#..', '###'], 'F': ['###', '#..', '##.', '#..', '#..'],
    'G': ['###', '#..', '#.#', '#.#', '###'], 'H': ['#.#', '#.#', '###', '#.#', '#.#'],
    'I': ['###', '.#.', '.#.', '.#.', '###'], 'J': ['..#', '..#', '..#', '#.#', '###'],
    'K': ['#.#', '#.#', '##.', '#.#', '#.#'], 'L': ['#..', '#..', '#..', '#..', '###'],
    'M': ['#.#', '###', '###', '#.#', '#.#'], 'N': ['##.', '#.#', '#.#', '#.#', '#.#'],
    'O': ['###', '#.#', '#.#', '#.#', '###'], 'P': ['###', '#.#', '###', '#..', '#..'],
    'Q': ['###', '#.#', '#.#', '###', '.##'], 'R': ['###', '#.#', '###', '##.', '#.#'],
    'S': ['###', '#..', '###', '..#', '###'], 'T': ['###', '.#.', '.#.', '.#.', '.#.'],
    'U': ['#.#', '#.#', '#.#', '#.#', '###'], 'V': ['#.#', '#.#', '#.#', '#.#', '.#.'],
    'W': ['#.#', '#.#', '###', '###', '#.#'], 'X': ['#.#', '#.#', '.#.', '#.#', '#.#'],
    'Y': ['#.#', '#.#', '.#.', '.#.', '.#.'], 'Z': ['###', '..#', '.#.', '#..', '###'],
    ' ': ['...', '...', '...', '...', '...'], '-': ['...', '...', '###', '...', '...'],
    '.': ['...', '...', '...', '...', '.#.'], ':': ['...', '.#.', '...', '.#.', '...'],
    '/': ['..#', '..#', '.#.', '#..', '#..'], '+': ['...', '.#.', '###', '.#.', '...'],
    "'": ['.#.', '.#.', '...', '...', '...'], '&': ['.#.', '#.#', '.#.', '#.#', '.##'],
    '@': ['###', '#.#', '###', '#..', '###'], '?': ['###', '..#', '.#.', '...', '.#.'],
    '%': ['#.#', '..#', '.#.', '#..', '#.#'],
    '·': ['...', '...', '.#.', '...', '...'], ',': ['...', '...', '...', '.#.', '#..'],
    '*': ['#.#', '.#.', '#.#', '...', '...'], '(': ['.##', '.#.', '#..', '.#.', '.##'],
    ')': ['##.', '.#.', '..#', '.#.', '##.'],
}


def micro(d, x, y, text, color, scale=1, gap=1):
    """Draw 3x5 bitmap text. Returns rendered width."""
    cx = x
    for ch in str(text).upper():
        g = MICRO.get(ch, MICRO['?'])
        for ry in range(5):
            row = g[ry]
            for rx in range(3):
                if row[rx] != '.':
                    if scale == 1:
                        d.point((cx + rx, y + ry), fill=color)
                    else:
                        d.rectangle([cx + rx * scale, y + ry * scale,
                                     cx + rx * scale + scale - 1, y + ry * scale + scale - 1], fill=color)
        cx += (3 + gap) * scale
    return cx - x - gap * scale


def micro_w(text, scale=1, gap=1):
    return len(str(text)) * (3 + gap) * scale - gap * scale


def micro_r(d, xr, y, text, color, scale=1, gap=1):
    w = micro_w(text, scale, gap)
    micro(d, xr - w, y, text, color, scale, gap)
    return w


def micro_c(d, cx, y, text, color, scale=1, gap=1):
    w = micro_w(text, scale, gap)
    micro(d, round(cx - w / 2), y, text, color, scale, gap)
    return w


# ---------------------------------------------------------------- color utils
def hex_rgb(h, default=(32, 32, 32)):
    h = (h or "").lstrip("#")
    if len(h) != 6:
        return default
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return default


def luminance(rgb):
    r, g, b = rgb
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def contrast_on(rgb):
    return BLACK if luminance(rgb) > 0.55 else WHITE


def shade(rgb, f):
    """Scale brightness (f>1 lighter, f<1 darker), clamped."""
    return tuple(max(0, min(255, int(c * f))) for c in rgb)


def mix(a, b, t):
    return tuple(int(a[i] * (1 - t) + b[i] * t) for i in range(3))


def vivid(rgb, min_v=0.82, min_s=0.55):
    """Boost a color into neon territory; rescues near-black team colors."""
    r, g, b = (c / 255 for c in rgb)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    if v < 0.12:          # pure-black teams have no hue -> give them a cool tint
        h, s = 0.58, min_s
    v, s = max(v, min_v), max(s, min_s)
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


def _fit_band_color(rgb):
    return (30, 33, 40) if luminance(rgb) < 0.06 else rgb


# ---------------------------------------------------------------- draw helpers
def _draw(img):
    d = ImageDraw.Draw(img)
    d.fontmode = "1"  # disable antialiasing -> crisp pixel text
    return d


def vgrad(d, box, top, bottom):
    x0, y0, x1, y1 = box
    h = max(1, y1 - y0)
    for i in range(y1 - y0 + 1):
        d.line([(x0, y0 + i), (x1, y0 + i)], fill=mix(top, bottom, i / h))


def fit_big(d, text, max_w, start=16, end=8):
    size = start
    while size > end and d.textlength(text, big(size)) > max_w:
        size -= 1
    return big(size), size


def shadow_text(d, xy, s, fnt, fill, sh=BLACK, off=(1, 1), anchor=None):
    d.text((xy[0] + off[0], xy[1] + off[1]), s, font=fnt, fill=sh, anchor=anchor)
    d.text(xy, s, font=fnt, fill=fill, anchor=anchor)


def score_info(team, state):
    """What to show in the score slot: live/final -> score; pre -> record/dash."""
    if state == "pre":
        return team.get("record", "") or "--", False
    return str(team.get("score", "0")), True


# ---------------------------------------------------------------- header strip
def _header(d, game, bg=HEADER_BG, y1=9):
    d.rectangle([0, 0, SIZE - 1, y1], fill=bg)
    d.text((2, 1), game["label"], font=small(9), fill=GOLD)
    status = game["status"]
    sw = d.textlength(status, small(9))
    sx = SIZE - 2 - sw
    if game["state"] == "in":
        d.ellipse([sx - 7, 2, sx - 3, 6], fill=(235, 60, 60))
    col = (235, 235, 235) if game["state"] != "post" else (150, 150, 150)
    d.text((sx, 1), status, font=small(9), fill=col)


# ================================================================ LAYOUT: bands
def layout_bands(game):
    img = Image.new("RGB", (SIZE, SIZE), HEADER_BG)
    d = _draw(img)
    _header(d, game)
    d.line([0, 10, SIZE - 1, 10], fill=(0, 0, 0))
    band_h = 26
    for idx, side in enumerate(("away", "home")):
        t = game[side]
        y0 = 11 + idx * (band_h + 1)
        color = _fit_band_color(hex_rgb(t["color"]))
        fg = contrast_on(color)
        d.rectangle([0, y0, SIZE - 1, y0 + band_h - 1], fill=color)
        ax = 4
        if t.get("fav"):
            d.rectangle([0, y0, 2, y0 + band_h - 1], fill=GOLD)
            ax = 6
        d.text((ax, y0 + 4), t["abbr"][:3], font=small(15), fill=fg)
        abbr_r = ax + d.textlength(t["abbr"][:3], small(15))
        txt, is_score = score_info(t, game["state"])
        f, sz = fit_big(d, txt, SIZE - 6 - (abbr_r + 3)) if is_score else (small(11), 11)
        d.text((SIZE - 3 - d.textlength(txt, f), y0 + (band_h - sz) // 2 - 1),
               txt, font=f, fill=fg)
        if game["state"] == "post" and t.get("winner"):
            d.polygon([(SIZE - 3, y0 + band_h - 5), (SIZE - 8, y0 + band_h - 5),
                       (SIZE - 3, y0 + band_h - 1)], fill=GOLD)
    return img


# ============================================================ LAYOUT: jumbotron
def _bevel_box(d, box, color, fav):
    x0, y0, x1, y1 = box
    vgrad(d, box, shade(color, 1.15), shade(color, 0.82))   # top-lit sheen
    d.line([(x0, y0), (x1, y0)], fill=shade(color, 1.7))     # top highlight
    d.line([(x0, y0), (x0, y1)], fill=shade(color, 1.5))     # left highlight
    d.line([(x0, y1), (x1, y1)], fill=shade(color, 0.45))    # bottom shadow
    d.line([(x1, y0), (x1, y1)], fill=shade(color, 0.5))     # right shadow
    if fav:
        d.rectangle([x0, y0, x1, y1], outline=GOLD)


def layout_jumbotron(game):
    img = Image.new("RGB", (SIZE, SIZE), BLACK)
    d = _draw(img)
    _header(d, game, bg=(0, 0, 0))
    for idx, side in enumerate(("away", "home")):
        t = game[side]
        y0 = 12 + idx * 25
        box = (1, y0, SIZE - 2, y0 + 23)
        color = _fit_band_color(hex_rgb(t["color"]))
        fg = contrast_on(shade(color, 0.95))
        _bevel_box(d, box, color, t.get("fav"))
        ax = 5
        if t.get("fav"):
            d.ellipse([3, y0 + 9, 7, y0 + 13], fill=GOLD)
            ax = 10
        shadow_text(d, (ax, y0 + 8), t["abbr"][:3], small(14), fg,
                    sh=shade(color, 0.4), anchor="lm")
        abbr_r = ax + d.textlength(t["abbr"][:3], small(14))
        txt, is_score = score_info(t, game["state"])
        f, sz = fit_big(d, txt, SIZE - 6 - (abbr_r + 3)) if is_score else (small(11), 11)
        shadow_text(d, (SIZE - 4, y0 + 12), txt, f, fg,
                    sh=shade(color, 0.4), anchor="rm")
        if game["state"] == "post" and t.get("winner"):
            d.polygon([(SIZE - 3, y0 + 1), (SIZE - 9, y0 + 1), (SIZE - 3, y0 + 6)], fill=GOLD)
    return img


# ============================================================== LAYOUT: diagonal
def layout_diagonal(game):
    img = Image.new("RGB", (SIZE, SIZE), BLACK)
    d = _draw(img)
    a, h = game["away"], game["home"]
    ca, ch = vivid(hex_rgb(a["color"])), vivid(hex_rgb(h["color"]))
    # diagonal split
    d.polygon([(0, 0), (SIZE, 0), (SIZE, 22), (0, 42)], fill=ca)
    d.polygon([(0, 42), (SIZE, 22), (SIZE, SIZE), (0, SIZE)], fill=ch)
    d.line([(0, 42), (SIZE - 1, 22)], fill=BLACK, width=1)
    d.line([(0, 44), (SIZE - 1, 24)], fill=shade(ch, 0.5), width=1)  # drop shadow

    def stroked(xy, s, fnt, fill, anchor):
        d.text(xy, s, font=fnt, fill=fill, anchor=anchor, stroke_width=1, stroke_fill=BLACK)

    # away occupies the upper-left wedge, home the lower-right wedge.
    # abbr stacked ABOVE score (top-anchored) so they never overlap.
    ta, _ = score_info(a, game["state"])
    th, _ = score_info(h, game["state"])
    fa, _ = fit_big(d, ta, 46)
    fh, _ = fit_big(d, th, 46)
    stroked((3, 1), a["abbr"][:3], small(12), WHITE, "lt")
    stroked((3, 10), ta, fa, WHITE, "lt")
    stroked((SIZE - 3, 39), h["abbr"][:3], small(12), WHITE, "rt")
    stroked((SIZE - 3, 48), th, fh, WHITE, "rt")
    # favorite gold corner ticks
    if a.get("fav"):
        d.line([(0, 0), (6, 0)], fill=GOLD); d.line([(0, 0), (0, 6)], fill=GOLD)
    if h.get("fav"):
        d.line([(SIZE - 7, SIZE - 1), (SIZE - 1, SIZE - 1)], fill=GOLD)
        d.line([(SIZE - 1, SIZE - 7), (SIZE - 1, SIZE - 1)], fill=GOLD)
    # center status pill
    s = game["status"]
    sw = d.textlength(s, small(9))
    px0 = (SIZE - sw) // 2 - 3
    d.rectangle([px0, 27, px0 + sw + 5, 37], fill=BLACK)
    if game["state"] == "in":
        d.ellipse([px0 + 1, 30, px0 + 4, 33], fill=(235, 60, 60))
    d.text((SIZE // 2, 32), s, font=small(9), fill=WHITE, anchor="mm")
    # league tag tiny, top-right corner over away color
    d.text((SIZE - 2, 1), game["label"], font=small(8), fill=BLACK, anchor="ra")
    return img


# ================================================================= LAYOUT: neon
def _neon_box(d, box, color):
    x0, y0, x1, y1 = box
    d.rectangle([x0 - 1, y0 - 1, x1 + 1, y1 + 1], outline=shade(color, 0.3))
    d.rectangle([x0, y0, x1, y1], outline=shade(color, 0.7))
    d.rectangle([x0 + 1, y0 + 1, x1 - 1, y1 - 1], outline=mix(color, WHITE, 0.45))


def layout_neon(game):
    img = Image.new("RGB", (SIZE, SIZE), (2, 2, 4))
    d = _draw(img)
    d.text((SIZE // 2, 4), f"{game['label']}  {game['status']}", font=small(9),
           fill=(120, 200, 255), anchor="mm")
    for idx, side in enumerate(("away", "home")):
        t = game[side]
        y0 = 13 + idx * 25
        box = (5, y0, SIZE - 6, y0 + 19)
        color = vivid(hex_rgb(t["color"]))
        _neon_box(d, box, color)
        d.text((11, y0 + 10), t["abbr"][:3], font=small(13), fill=color, anchor="lm")
        txt, is_score = score_info(t, game["state"])
        f, _ = fit_big(d, txt, 30) if is_score else (small(11), 11)
        d.text((SIZE - 10, y0 + 10), txt, font=f, fill=mix(color, WHITE, 0.25), anchor="rm")
        if t.get("fav"):
            d.polygon([(1, y0 + 6), (4, y0 + 9), (1, y0 + 12)], fill=GOLD)
        if game["state"] == "post" and t.get("winner"):
            d.text((SIZE - 2, y0 + 10), "", font=small(9), fill=GOLD)
    return img


# ============================================================ LAYOUT: broadcast
def layout_broadcast(game):
    img = Image.new("RGB", (SIZE, SIZE), (12, 14, 18))
    d = _draw(img)
    vgrad(d, (0, 0, SIZE - 1, SIZE - 1), (22, 26, 34), (8, 9, 13))
    # header: league pill + status
    lab = game["label"]
    lw = d.textlength(lab, small(9))
    d.rectangle([2, 1, 6 + lw, 9], fill=GOLD)
    d.text((4, 1), lab, font=small(9), fill=BLACK)
    s = game["status"]
    sx = SIZE - 2 - d.textlength(s, small(9))
    if game["state"] == "in":
        d.ellipse([sx - 7, 2, sx - 3, 6], fill=(235, 60, 60))
    d.text((sx, 1), s, font=small(9),
           fill=WHITE if game["state"] != "post" else (150, 150, 150))
    # two panels with team-color accent edge + gradient depth
    for idx, side in enumerate(("away", "home")):
        t = game[side]
        y0 = 12 + idx * 26
        color = _fit_band_color(hex_rgb(t["color"]))
        vgrad(d, (0, y0, SIZE - 1, y0 + 24), shade(color, 0.55), shade(color, 0.22))
        d.rectangle([0, y0, 4, y0 + 24], fill=color)                 # accent bar
        d.line([(5, y0), (5, y0 + 24)], fill=shade(color, 1.6))      # highlight edge
        if t.get("fav"):
            d.rectangle([0, y0, 4, y0 + 24], fill=GOLD)
            d.ellipse([8, y0 + 2, 12, y0 + 6], fill=GOLD)
        d.text((9, y0 + 13), t["abbr"][:3], font=small(15), fill=WHITE, anchor="lm")
        txt, is_score = score_info(t, game["state"])
        f, _ = fit_big(d, txt, 30) if is_score else (small(12), 12)
        shadow_text(d, (SIZE - 4, y0 + 13), txt, f, WHITE, sh=(0, 0, 0), anchor="rm")
        if game["state"] == "post" and t.get("winner"):
            d.polygon([(SIZE - 3, y0 + 1), (SIZE - 8, y0 + 1), (SIZE - 3, y0 + 5)], fill=GOLD)
    d.line([0, 37, SIZE - 1, 37], fill=(0, 0, 0))
    return img


# ============================================================ PLAYOFF LAYOUTS
OBSIDIAN = (10, 10, 13)
GOLD_DK = (150, 110, 20)
CRIT = (220, 50, 50)


def _gold_banner(d, y0, y1, text):
    vgrad(d, (0, y0, SIZE - 1, y1), (255, 222, 120), GOLD_DK)
    d.line([(0, y0), (SIZE - 1, y0)], fill=(255, 240, 180))
    d.text((SIZE // 2, (y0 + y1) // 2), text, font=small(9), fill=(40, 28, 0), anchor="mm")


def win_pips(d, x0, y, wins, needed, align="l", gap=5):
    """best-of-N pips: filled gold = won, hollow = remaining. Returns end x.
    A subtle glow is drawn only at wide spacing (gap>=5); tight rows skip it so
    adjacent pips don't merge into a bar."""
    sz = 3
    total_w = needed * gap - (gap - sz)
    x = x0 - total_w if align == "r" else x0
    for i in range(needed):
        px = x + i * gap
        box = [px, y, px + sz - 1, y + sz - 1]
        if i < wins:
            if gap >= 5:
                d.rectangle([px - 1, y - 1, px + sz, y + sz], fill=GOLD_DK)
            d.rectangle(box, fill=GOLD)
        else:
            d.rectangle(box, outline=(80, 80, 92))
    return x + total_w


def series_callout(away, home, needed):
    """Returns (text, critical) for the drama line, or ('', False)."""
    aw, hw = away["series_wins"], home["series_wins"]
    lead = max(aw, hw)
    if lead >= needed:
        return ("SERIES OVER", False)
    if aw == needed - 1 and hw == needed - 1:
        return ("GAME 7", True)
    if lead == needed - 1:
        return ("ELIMINATION", True)
    return ("", False)


def _po_header_text(g):
    r = g.get("po_round") or "PLAYOFFS"
    gm = g.get("po_game")
    return f"{r} G{gm}" if gm else r


def _short_status(g):
    s = g["status"]
    for tag in ("jst", "et", "ct", "mt", "pt"):
        if s.endswith(tag):
            return s[: -len(tag)]
    return s


def _drama_box(d, y0, y1, call, crit, fallback):
    """Centered pill: red callout when critical, else the series summary."""
    if call:
        bw = d.textlength(call, small(9)) + 6
        bx = (SIZE - bw) // 2
        d.rectangle([bx, y0, bx + bw, y1], fill=CRIT if crit else (44, 38, 22))
        d.text((SIZE // 2, (y0 + y1) // 2), call, font=small(9), fill=WHITE, anchor="mm")
    elif fallback:
        d.text((SIZE // 2, (y0 + y1) // 2), fallback[:18], font=small(9),
               fill=(185, 185, 195), anchor="mm")


# -------- 1. CRUCIBLE: obsidian vs-split, center divider, pips under each side
def layout_playoff_crucible(game):
    img = Image.new("RGB", (SIZE, SIZE), OBSIDIAN)
    d = _draw(img)
    a, h = game["away"], game["home"]
    pre = game["state"] == "pre"
    _gold_banner(d, 0, 8, _po_header_text(game))
    for yy in range(20, 33, 2):                       # center dashed divider
        d.point((31, yy), fill=(70, 60, 30))
    ca, ch = vivid(hex_rgb(a["color"])), vivid(hex_rgb(h["color"]))
    d.text((2, 12), a["abbr"][:3], font=small(11), fill=ca, anchor="lm")        # away top-left
    d.text((SIZE - 2, 12), h["abbr"][:3], font=small(11), fill=ch, anchor="rm")  # home top-right
    if pre:
        t = _short_status(game)                       # tip time is the hero
        f, _ = fit_big(d, t, 54, start=14)
        shadow_text(d, (SIZE // 2, 27), t, f, GOLD, sh=BLACK, anchor="mm")
    else:
        ta, _ = score_info(a, game["state"])
        th, _ = score_info(h, game["state"])
        fa, _ = fit_big(d, ta, 28)
        fh, _ = fit_big(d, th, 28)
        shadow_text(d, (29, 27), ta, fa, WHITE, sh=BLACK, anchor="rm")
        shadow_text(d, (34, 27), th, fh, WHITE, sh=BLACK, anchor="lm")
    win_pips(d, 27, 38, a["series_wins"], game["series_needed"], align="r")
    win_pips(d, 36, 38, h["series_wins"], game["series_needed"], align="l")
    call, crit = series_callout(a, h, game["series_needed"])
    _drama_box(d, 43, 52, call, crit, game.get("series_summary", ""))
    # bottom: live clock (or TIP-OFF label for pre, since time is shown big)
    if pre:
        d.text((SIZE // 2, 57), "TIP-OFF", font=small(9), fill=(150, 150, 160), anchor="mm")
    else:
        st = game["status"]
        sw = d.textlength(st, small(11))
        if game["state"] == "in":
            d.ellipse([SIZE // 2 - sw // 2 - 7, 54, SIZE // 2 - sw // 2 - 3, 58], fill=CRIT)
        d.text((SIZE // 2, 57), st, font=small(11),
               fill=GOLD if game["state"] == "post" else WHITE, anchor="mm")
    return img


# -------- 2. SERIES: prestige rows, inline win pips per team, callout ribbon
def layout_playoff_series(game):
    img = Image.new("RGB", (SIZE, SIZE), OBSIDIAN)
    d = _draw(img)
    vgrad(d, (0, 9, SIZE - 1, 50), (20, 20, 26), (10, 10, 13))
    _gold_banner(d, 0, 8, _po_header_text(game))
    pre = game["state"] == "pre"
    # rows per Gemini's fix: abbr stacked OVER pips on the left, score right.
    for idx, side in enumerate(("away", "home")):
        t = game[side]
        y0 = 10 + idx * 20
        color = _fit_band_color(hex_rgb(t["color"]))
        d.rectangle([0, y0, 3, y0 + 18], fill=color)
        d.line([(4, y0), (4, y0 + 18)], fill=shade(color, 1.6))
        d.text((7, y0 + 1), t["abbr"][:3], font=small(12), fill=WHITE, anchor="lt")
        win_pips(d, 7, y0 + 12, t["series_wins"], game["series_needed"], align="l", gap=4)
        if not pre:                                   # score only once it exists
            txt = str(t.get("score", "0"))
            f, _ = fit_big(d, txt, 25)                # right of the pips (x38+)
            shadow_text(d, (SIZE - 3, y0 + 9), txt, f, WHITE, sh=BLACK, anchor="rm")
    # bottom ribbon: callout (left) + clock (right), split so they never overlap
    call, crit = series_callout(game["away"], game["home"], game["series_needed"])
    d.rectangle([0, 53, SIZE - 1, 63], fill=CRIT if crit else (34, 30, 18))
    left = call if call else game.get("series_summary", "")
    if left == "ELIMINATION":          # full word won't fit beside the clock
        left = "ELIM"
    while left and d.textlength(left, small(8)) > 36:
        left = left[:-1]
    d.text((2, 58), left, font=small(8), fill=WHITE, anchor="lm")
    d.text((SIZE - 2, 58), _short_status(game), font=small(8),
           fill=WHITE if crit else GOLD, anchor="rm")
    return img


# -------- 3. SPOTLIGHT: huge centered score (or tip time), corner pip clusters
def layout_playoff_spotlight(game):
    img = Image.new("RGB", (SIZE, SIZE), OBSIDIAN)
    d = _draw(img)
    a, h = game["away"], game["home"]
    pre = game["state"] == "pre"
    vgrad(d, (0, 20, SIZE - 1, 44), (40, 31, 9), OBSIDIAN)   # gold glow behind center
    d.text((SIZE // 2, 4), _po_header_text(game), font=small(9), fill=GOLD, anchor="mm")
    d.text((2, 12), a["abbr"][:3], font=small(11), fill=vivid(hex_rgb(a["color"])), anchor="lm")
    win_pips(d, 2, 18, a["series_wins"], game["series_needed"], align="l")
    d.text((SIZE - 2, 12), h["abbr"][:3], font=small(11), fill=vivid(hex_rgb(h["color"])), anchor="rm")
    win_pips(d, SIZE - 2, 18, h["series_wins"], game["series_needed"], align="r")
    if pre:
        hero = _short_status(game)
        f, _ = fit_big(d, hero, 60, start=18)
        shadow_text(d, (SIZE // 2, 33), hero, f, GOLD, sh=(60, 45, 10), anchor="mm")
    else:
        hero = f"{a.get('score', '0')}-{h.get('score', '0')}"
        f, _ = fit_big(d, hero, 60, start=18)
        shadow_text(d, (SIZE // 2, 33), hero, f, WHITE, sh=(60, 45, 10), anchor="mm")
    call, crit = series_callout(a, h, game["series_needed"])
    _drama_box(d, 47, 56, call, crit, "")
    if not pre or not call:
        d.text((SIZE // 2, 60), game["status"] if not pre else "TIP-OFF",
               font=small(9), fill=(190, 190, 200), anchor="mm")
    return img


# ----------------------------------------------------- logo tile (real or crest)
def logo_tile(img, d, x, y, size, team):
    """Composite the real team logo on a dark tile with a team-color border.
    Falls back to a colored 2-letter crest when the logo can't be loaded."""
    color = _fit_band_color(hex_rgb(team["color"]))
    spr = logos.sprite(team.get("logo", ""), size - 2)
    if spr is not None:
        d.rectangle([x, y, x + size - 1, y + size - 1], fill=(12, 13, 16))
        d.rectangle([x, y, x + size - 1, y + size - 1], outline=color)
        img.paste(spr, (x + 1, y + 1), spr)          # alpha-composite, no text overlay
        return True
    # crest fallback
    d.rectangle([x, y, x + size - 1, y + size - 1], fill=color)
    cap = max(3, round(size * 0.32))
    d.rectangle([x, y, x + size - 1, y + cap - 1], fill=shade(color, 1.4))
    d.line([(x, y), (x + size - 1, y)], fill=shade(color, 1.7))
    d.line([(x, y + size - 1), (x + size - 1, y + size - 1)], fill=shade(color, 0.4))
    d.rectangle([x, y, x + size - 1, y + size - 1], outline=shade(color, 1.5))
    ink = contrast_on(color)
    ab = team["abbr"][:2]
    w = micro_w(ab, 2)
    micro(d, x + (size - w) // 2, y + cap + (size - cap - 10) // 2, ab, ink, 2)
    return False


# ================================================================ LAYOUT: scorebug
def layout_scorebug(game):
    img = Image.new("RGB", (SIZE, SIZE), (0, 0, 0))
    d = _draw(img)
    state = game["state"]
    vgrad(d, (0, 0, SIZE - 1, 7), (24, 27, 33), (12, 14, 17))
    d.line([0, 8, SIZE - 1, 8], fill=(39, 44, 51))
    lx = 2
    if state == "in":
        d.rectangle([2, 2, 4, 4], fill=(255, 59, 48))
        lx = 8
    micro(d, lx, 2, game["label"], (160, 165, 173), 1)
    micro_r(d, SIZE - 2, 2, game["status"],
            GOLD if state != "post" else (150, 150, 150), 1)

    for idx, side in enumerate(("away", "home")):
        t = game[side]
        y0 = 11 + idx * 22
        color = _fit_band_color(hex_rgb(t["color"]))
        win = state == "post" and t.get("winner")
        if win:                                   # winner: tinted row + accent rail
            d.rectangle([0, y0 - 1, SIZE - 1, y0 + 20], fill=shade(color, 0.45))
            d.rectangle([0, y0 - 1, 2, y0 + 20], fill=GOLD)
        logo_tile(img, d, 3, y0, 19, t)
        if state == "pre":
            rec = t.get("record", "") or "--"
            micro_r(d, SIZE - 3, y0 + 7, rec, (231, 235, 239), 2, 1)
        else:
            sc = str(t.get("score", "0"))
            col = GOLD if win else WHITE
            w = micro_w(sc, 3, 1)
            if win:
                glow_rect(d, SIZE - 4 - w, y0 + 2, w + 2, 16, vivid(color))
            micro(d, SIZE - 3 - w, y0 + 3, sc, col, 3, 1)
            if win:                               # crown badge
                cx = 24
                micro(d, cx, y0 + 6, "*", GOLD, 2)
    # bottom context line: playoff series, or favorite/standout
    d.rectangle([0, 55, SIZE - 1, 63], fill=(12, 14, 17))
    d.line([0, 55, SIZE - 1, 55], fill=(39, 44, 51))
    if game.get("playoff") and game.get("series_summary"):
        ctx = game["series_summary"].replace(" series ", " ")   # "NY leads 3-1"
        col = GOLD
    else:
        ctx = game.get("label", "") + (" · FAV" if game.get("fav") else "")
        col = (139, 144, 153)
    while micro_w(ctx, 1) > 62:                                  # keep it on-screen
        ctx = ctx[:-1]
    micro_c(d, SIZE // 2, 57, ctx, col, 1)
    return img


def glow_rect(d, x, y, w, h, color):
    for l in (2, 1):
        a = 70 if l == 1 else 35
        d.rectangle([x - l, y - l, x + w + l, y + h + l], outline=shade(color, a / 100))


# ================================================================ LAYOUT: statline
_UNIT_PRE = {"PTS": "PPG", "REB": "RPG", "AST": "APG"}
_BAR_MAX = {"PTS": 35, "REB": 18, "AST": 12}


def layout_statline(game):
    img = Image.new("RGB", (SIZE, SIZE), (10, 12, 16))
    d = _draw(img)
    state = game["state"]
    a, h = game["away"], game["home"]
    ca, ch = _fit_band_color(hex_rgb(a["color"])), _fit_band_color(hex_rgb(h["color"]))
    # compact score header
    vgrad(d, (0, 0, SIZE - 1, 9), (23, 27, 34), (12, 15, 19))
    d.line([0, 10, SIZE - 1, 10], fill=(39, 44, 51))
    d.rectangle([2, 3, 4, 7], fill=ca)
    micro(d, 7, 3, a["abbr"], (205, 211, 219), 1)
    d.rectangle([59, 3, 61, 7], fill=ch)
    micro_r(d, 57, 3, h["abbr"], (205, 211, 219), 1)
    if state != "pre":                                   # scores flank the center
        micro(d, 18, 3, str(a.get("score", 0)), WHITE, 1)
        micro_r(d, 46, 3, str(h.get("score", 0)), WHITE, 1)
    # short center token: period (live) / F (final) / none (pre)
    center = game["status"].split(" ")[0] if state == "in" else ("F" if state == "post" else "")
    if center:
        micro_c(d, 32, 3, center, GOLD, 1)
    label = {"in": "LIVE LEADERS", "post": "GAME LEADERS"}.get(state, "SEASON LEADERS")
    micro_c(d, 32, 12, label, (110, 116, 128), 1)

    # build up to 3 leader rows: each team's top scorer + the better rebounder
    rows = []
    if a["leaders"].get("PTS"):
        rows.append((a, ca, a["leaders"]["PTS"], "PTS"))
    if h["leaders"].get("PTS"):
        rows.append((h, ch, h["leaders"]["PTS"], "PTS"))
    rebs = [(a, ca, a["leaders"].get("REB")), (h, ch, h["leaders"].get("REB"))]
    rebs = [(t, c, r) for t, c, r in rebs if r]
    if rebs:
        t, c, r = max(rebs, key=lambda x: x[2][1])
        rows.append((t, c, r, "REB"))
    rows = rows[:3]

    if not rows:                       # no leaders (non-NBA) -> stay within the new layouts
        return layout_scorebug(game)

    top, rh = 19, 15
    for i, (t, color, (name, val), unit) in enumerate(rows):
        y = top + i * rh
        glow = vivid(color)
        d.rectangle([2, y, 6, y + 4], fill=color)
        d.rectangle([2, y, 6, y + 4], outline=shade(color, 1.5))
        last = name.split()[-1] if name else "?"          # last name, capped
        micro(d, 10, y, last[:7], (231, 235, 239), 1)
        disp = f"{val:.0f}"
        micro_r(d, SIZE - 1, y, disp, WHITE, 2, 1)         # big value
        unit_lbl = _UNIT_PRE[unit] if state == "pre" else unit
        micro(d, 10, y + 9, unit_lbl, glow, 1)
        bw = round(28 * min(1.0, val / _BAR_MAX.get(unit, 35)))
        d.rectangle([26, y + 10, 53, y + 11], fill=(29, 36, 43))
        if bw > 0:
            gradient_h(d, 26, y + 10, bw, 2, color, glow)
    return img


def gradient_h(d, x, y, w, h, c1, c2):
    for i in range(w):
        t = 0 if w <= 1 else i / (w - 1)
        d.line([(x + i, y), (x + i, y + h - 1)], fill=mix(c1, c2, t))


# ----------------------------------------------------- diamond drawing helpers
def _hline(d, x, y, n, c):
    if n > 0:
        d.line([(x, y), (x + n - 1, y)], fill=c)


def _vline(d, x, y, n, c):
    if n > 0:
        d.line([(x, y), (x, y + n - 1)], fill=c)


def pix_diamond(d, cx, cy, r, c, fill=True):
    for yy in range(-r, r + 1):
        span = r - abs(yy)
        if fill:
            _hline(d, cx - span, cy + yy, 2 * span + 1, c)
        else:
            d.point((cx - span, cy + yy), fill=c)
            d.point((cx + span, cy + yy), fill=c)


def count_dots(d, x, y, n, filled, c, off=(57, 66, 75)):
    for i in range(n):
        fx = x + i * 4
        if i < filled:
            d.rectangle([fx, y, fx + 1, y + 1], fill=c)
        else:
            d.rectangle([fx, y, fx + 1, y + 1], outline=off)


def tri_up(d, cx, cy_top, hh, c):
    for i in range(hh):
        _hline(d, cx - i, cy_top + i, 2 * i + 1, c)


def tri_dn(d, cx, cy_top, hh, c):
    for i in range(hh):
        _hline(d, cx - (hh - 1 - i), cy_top + i, 2 * (hh - 1 - i) + 1, c)


def tri_r(d, x_left, cy, hh, c):
    for i in range(hh):
        _vline(d, x_left + i, cy - (hh - 1 - i), 2 * (hh - 1 - i) + 1, c)


def tri_l(d, x_right, cy, hh, c):
    for i in range(hh):
        _vline(d, x_right - i, cy - (hh - 1 - i), 2 * (hh - 1 - i) + 1, c)


def ring(d, cx, cy, r, c):
    for yy in range(-r, r + 1):
        for xx in range(-r, r + 1):
            dd = xx * xx + yy * yy
            if (r - 1) * (r - 1) < dd <= r * r + r * 0.6:
                d.point((cx + xx, cy + yy), fill=c)


# ================================================================ LAYOUT: court
def layout_court(game):
    """NBA half-court shot chart (design concept 8): made = featured-color dot +
    white core, miss = dim hollow square; footer shows FG + hottest zone."""
    img = Image.new("RGB", (SIZE, SIZE), (10, 12, 16))
    d = _draw(img)
    a, h = game["away"], game["home"]
    state = game["state"]
    feat = game.get("feat", "home")
    ft = a if feat == "away" else h
    fc, fglow = _fit_band_color(hex_rgb(ft["color"])), vivid(hex_rgb(ft["color"]))
    ac, hc = _fit_band_color(hex_rgb(a["color"])), _fit_band_color(hex_rgb(h["color"]))
    # header score strip
    vgrad(d, (0, 0, SIZE - 1, 8), (23, 27, 34), (12, 15, 19))
    d.line([0, 9, SIZE - 1, 9], fill=(39, 44, 51))
    d.rectangle([2, 2, 4, 6], fill=ac)
    micro(d, 7, 2, str(a.get("score", 0)), (255, 255, 255) if feat == "away" else (154, 163, 173), 1)
    d.rectangle([59, 2, 61, 6], fill=hc)
    micro_r(d, 57, 2, str(h.get("score", 0)), (255, 255, 255) if feat == "home" else (154, 163, 173), 1)
    micro_c(d, 32, 2, "FINAL" if state == "post" else game["status"].split(" ")[0], GOLD, 1)
    # court
    lineC = (57, 66, 75)
    vgrad(d, (2, 11, 61, 57), (18, 22, 28), (12, 16, 21))
    hx, hy = 32, 15
    d.line([(28, 12), (36, 12)], fill=lineC)            # backboard
    ring(d, hx, hy, 1, fglow)                            # rim
    d.rectangle([26, 12, 38, 37], outline=lineC)        # paint
    ring(d, hx, 38, 5, lineC)                           # free-throw circle
    d.line([(5, 12), (5, 28)], fill=lineC)              # corner-3 verticals
    d.line([(58, 12), (58, 28)], fill=lineC)
    for ang in range(22, 159, 3):                       # 3pt arc
        x = round(hx + 30 * math.cos(math.radians(ang)))
        y = round(hy + 30 * math.sin(math.radians(ang)))
        d.point((x, y), fill=lineC)
    # shots
    for s in game.get("shots", []):
        x, y = s["x"], s["y"]
        if s["m"]:
            d.rectangle([x - 1, y - 1, x, y], fill=fglow)   # vivid so dark teams still pop
            d.point((x, y), fill=(255, 255, 255))
        else:
            d.rectangle([x - 1, y - 1, x, y], outline=(74, 82, 91))
    # footer
    d.rectangle([0, 58, SIZE - 1, 63], fill=(11, 15, 19))
    d.line([0, 58, SIZE - 1, 58], fill=(28, 39, 48))
    d.rectangle([2, 59, 4, 62], fill=fc)
    micro(d, 7, 59, ft["abbr"][:3], (205, 211, 218), 1)
    micro(d, 18, 59, game.get("fg", ""), (255, 255, 255), 1)
    micro_r(d, SIZE - 2, 59, game.get("hot", ""), fglow, 1)
    return img


# ================================================================= LAYOUT: diamond
GREEN = (124, 220, 58)
REDO = (255, 90, 77)


def layout_diamond(game):
    img = Image.new("RGB", (SIZE, SIZE), (5, 8, 11))
    d = _draw(img)
    a, h = game["away"], game["home"]
    state = game["state"]
    if state == "in":
        sit = game.get("situation", {})
        vgrad(d, (0, 0, SIZE - 1, 7), (15, 24, 32), (7, 11, 14))
        d.line([0, 8, SIZE - 1, 8], fill=(28, 39, 48))
        half = game.get("half", "top")
        (tri_up if half.startswith(("top", "mid")) else tri_dn)(d, 5, 2, 3, GREEN)
        micro(d, 11, 2, game.get("inning", ""), (205, 211, 218), 1)
        micro_r(d, SIZE - 2, 2, "LIVE", (255, 59, 48), 1)
        # team logos + scores flanking the diamond
        logo_tile(img, d, 2, 11, 13, a)
        micro_c(d, 8, 27, str(a.get("score", 0)), (231, 235, 239), 2, 1)
        logo_tile(img, d, 49, 11, 13, h)
        micro_c(d, 56, 27, str(h.get("score", 0)), (231, 235, 239), 2, 1)
        # base diamond (hero)
        cx, cy = 32, 22
        second, first, third, home = (cx, cy - 9), (cx + 10, cy), (cx - 10, cy), (cx, cy + 9)
        for p1, p2 in [(home, first), (first, second), (second, third), (third, home)]:
            d.line([p1, p2], fill=(42, 68, 25))
        bases = sit.get("bases", [False, False, False])
        for pos, on in ((second, bases[1]), (first, bases[0]), (third, bases[2])):
            if on:
                pix_diamond(d, pos[0], pos[1], 3, GOLD)
            else:
                pix_diamond(d, pos[0], pos[1], 3, (57, 66, 75), fill=False)
        pix_diamond(d, home[0], home[1], 2, (231, 235, 239))
        # balls / strikes / outs
        d.line([0, 38, SIZE - 1, 38], fill=(20, 27, 34))
        micro(d, 3, 41, "B", GREEN, 1); count_dots(d, 8, 42, 3, sit.get("balls", 0), GREEN)
        micro(d, 25, 41, "S", GOLD, 1); count_dots(d, 30, 42, 2, sit.get("strikes", 0), GOLD)
        micro(d, 44, 41, "O", REDO, 1); count_dots(d, 49, 42, 2, sit.get("outs", 0), REDO)
        # pitcher + at-bat
        d.line([0, 48, SIZE - 1, 48], fill=(20, 27, 34))
        pit = sit.get("pitcher", "")
        micro(d, 3, 50, ("P " + pit)[:13] if pit else "P --", (139, 144, 153), 1)
        d.rectangle([0, 55, SIZE - 1, 63], fill=(11, 15, 19))
        d.line([0, 55, SIZE - 1, 55], fill=(28, 39, 48))
        tri_r(d, 3, 59, 2, GOLD)
        bat = sit.get("batter", "")
        micro(d, 8, 57, ("AB " + bat)[:14] if bat else "AB --", (205, 211, 218), 1)
    elif state == "pre":
        vgrad(d, (0, 0, SIZE - 1, 7), (15, 24, 32), (7, 11, 14))
        d.line([0, 8, SIZE - 1, 8], fill=(28, 39, 48))
        micro(d, 3, 2, game["label"], (154, 163, 173), 1)
        logo_tile(img, d, 3, 13, 18, a)
        logo_tile(img, d, 43, 13, 18, h)
        micro_c(d, 32, 20, "AT", (120, 128, 138), 2)
        micro(d, 3, 36, a.get("record", "") or "--", (139, 144, 153), 1)
        micro_r(d, SIZE - 3, 36, h.get("record", "") or "--", (139, 144, 153), 1)
        d.line([0, 44, SIZE - 1, 44], fill=(20, 27, 34))
        micro_c(d, 32, 47, "FIRST PITCH", (125, 150, 168), 1)
        when = game.get("status", "")
        date = game.get("date_short", "")
        line2 = f"{date}  {when}".strip() if date else when
        micro_c(d, 32, 55, line2, (180, 198, 212), 1)
    else:  # final
        vgrad(d, (0, 0, SIZE - 1, 7), (15, 24, 32), (7, 11, 14))
        d.line([0, 8, SIZE - 1, 8], fill=(28, 39, 48))
        micro_c(d, 32, 2, "FINAL", (205, 211, 218), 1)
        logo_tile(img, d, 2, 13, 16, a)
        micro_c(d, 10, 34, str(a.get("score", 0)), (255, 255, 255), 3, 1)
        logo_tile(img, d, 46, 13, 16, h)
        col_h = GOLD if h.get("winner") else (255, 255, 255)
        micro_c(d, 54, 34, str(h.get("score", 0)), col_h, 3, 1)
    return img


def _fit_hr(hrs, budget=13):
    """Join HR log entries to fit `budget` chars, '+N' for the remainder."""
    out, used = [], 0
    for i, e in enumerate(hrs):
        seg = (", " if out else "") + e
        if used + len(seg) > budget:
            left = len(hrs) - i
            tail = f" +{left}"
            while out and used + len(tail) > budget:
                used -= len(", " + out[-1]) if len(out) > 1 else len(out[-1])
                out.pop()
            return "".join(out) + (tail if left else "")
        out.append(seg); used += len(seg)
    return "".join(out)


def layout_mlb_box(game):
    """MLB final as a full line score grid (runs by inning + R/H/E) over a
    pitching-decisions / HR block. (Design concept 12.)"""
    img = Image.new("RGB", (SIZE, SIZE), (6, 9, 13))
    d = _draw(img)
    a, h = game["away"], game["home"]
    bx = game.get("box", {})
    away_line = bx.get("away_line", [])
    home_line = bx.get("home_line", [])
    innings = bx.get("innings", 9)

    vgrad(d, (0, 0, SIZE - 1, 7), (19, 24, 31), (10, 13, 18))
    d.line([0, 8, SIZE - 1, 8], fill=(34, 42, 51))
    head = "FINAL/" + str(innings) if innings > 9 else "FINAL"
    micro_c(d, 32, 2, head, (205, 211, 218), 1)

    # column geometry: rail | abbr | innings 1-9 | R H E. R/H/E centered on even
    # 5px pitch (H may be 2-digit; it grows symmetrically under its label).
    def ix(i):
        return 14 + i * 4
    Rc, Hc, Ec = 52, 57, 62
    shown = min(innings, 9)
    for i in range(shown):
        micro(d, ix(i), 10, str(i + 1), (69, 77, 86), 1)
    micro_c(d, Rc, 10, "R", (126, 136, 147), 1)
    micro_c(d, Hc, 10, "H", (126, 136, 147), 1)
    micro_c(d, Ec, 10, "E", (126, 136, 147), 1)
    d.line([0, 16, SIZE - 1, 16], fill=(26, 33, 42))
    d.line([49, 9, 49, 32], fill=(26, 33, 42))

    def row(team, line, R, H, E, y, won):
        kit = vivid(hex_rgb(team.get("color", "808080")))
        if won:
            d.rectangle([0, y - 1, 1, y + 5], fill=kit)
        micro(d, 3, y, team.get("abbr", "?")[:3], kit, 1)  # x3 clears the 2px rail
        for i in range(shown):
            v = line[i] if i < len(line) else ""
            col = (69, 77, 86) if v in ("x", "0", "") else (255, 255, 255)
            micro(d, ix(i), y, v, col, 1)
        micro_c(d, Rc, y, str(R), GOLD if won else (255, 255, 255))
        micro_c(d, Hc, y, str(H), (174, 182, 191))
        micro_c(d, Ec, y, str(E), (154, 163, 173))

    aR, hR = bx.get("away_R", "0"), bx.get("home_R", "0")
    try:
        a_won = int(aR) > int(hR)
    except ValueError:
        a_won = False
    row(a, away_line, aR, bx.get("away_H", "0"), bx.get("away_E", "0"), 18, a_won)
    row(h, home_line, hR, bx.get("home_H", "0"), bx.get("home_E", "0"), 26, not a_won)

    # decisions + HR block. Name truncates to whatever room the IP/K line leaves.
    d.line([0, 34, SIZE - 1, 34], fill=(34, 42, 51))
    micro(d, 2, 37, "DECISIONS", (69, 77, 86), 1)

    def decision(tag, tag_col, name, line, y):
        micro(d, 2, y, tag, tag_col, 1)
        micro_r(d, 63, y, line, (139, 144, 153), 1)
        max_x = 63 - (micro_w(line) if line else 0) - 3
        while name and 8 + micro_w(name) - 1 > max_x:
            name = name[:-1]
        micro(d, 8, y, name, (231, 235, 239), 1)

    if bx.get("wp"):
        decision("W", (47, 191, 74), bx["wp"], bx.get("wpL", ""), 44)
    if bx.get("lp"):
        decision("L", (226, 59, 59), bx["lp"], bx.get("lpL", ""), 51)
    hrs = bx.get("hr", [])
    if hrs:
        micro(d, 2, 58, "HR", GOLD, 1)
        micro(d, 12, 58, _fit_hr(hrs), (205, 211, 218), 1)
    return img


def _logo_half(img, d, team, x0, w, h=64, zoom=88, dark=95):
    """Fill a half with a zoomed, cropped slice of the team logo over a dark
    team-color field (logo detail bleeds off the edges, not squished in)."""
    base = _fit_band_color(hex_rgb(team["color"]))
    d.rectangle([x0, 0, x0 + w - 1, h - 1], fill=shade(base, 0.42))
    raw = logos._raw_logo(team.get("logo", ""))
    if raw is not None:
        big = raw.resize((zoom, zoom), Image.LANCZOS)
        fx, fy = (zoom - w) // 2, (zoom - h) // 2
        crop = big.crop((fx, fy, fx + w, fy + h))
        img.paste(crop, (x0, 0), crop)
    img.paste((0, 0, 0), (x0, 0), Image.new("L", (w, h), dark))  # legibility veil


def layout_jumbotron_tape(game):
    """Tale-of-the-tape: zoomed-logo halves, black-gradient seam, head-to-head
    scores + stat rows. (Design concept 9, with logo-crop + dark-seam mods.)"""
    img = Image.new("RGB", (SIZE, SIZE), (10, 12, 16))
    d = _draw(img)
    a, h = game["away"], game["home"]
    z = game.get("jumbo_zoom", 120)
    _logo_half(img, d, a, 0, 32, zoom=z)
    _logo_half(img, d, h, 32, 32, zoom=z)
    # darken the lower stat band so the comparison text reads over the logos
    img.paste((0, 0, 0), (0, 25, SIZE, SIZE), Image.new("L", (SIZE, SIZE - 25), 95))
    # black gradient seam down the middle (replaces the gold line)
    seam_w = 14
    mask = Image.new("L", (seam_w, SIZE), 0)
    for dx in range(seam_w):
        val = int(235 * max(0.0, 1 - abs(dx - seam_w / 2 + 0.5) / (seam_w / 2)))
        for yy in range(SIZE):
            mask.putpixel((dx, yy), val)
    img.paste((0, 0, 0), (32 - seam_w // 2, 0), mask)

    state = game["state"]
    # corner team labels
    micro(d, 3, 3, a["abbr"], (230, 234, 238), 1)
    micro_r(d, SIZE - 3, 3, h["abbr"], (230, 234, 238), 1)
    # center status pill
    d.rectangle([24, 2, 39, 9], fill=(8, 10, 13))
    d.rectangle([24, 2, 39, 9], outline=(42, 48, 56))
    cen = "FIN" if state == "post" else (game["status"].split(" ")[0] if state == "in" else "VS")
    micro_c(d, 32, 3, cen, GOLD, 1)
    # big beveled scores per half
    for cx, t in ((16, a), (47, h)):
        s = str(t.get("score", 0))
        w = micro_w(s, 2, 1)
        micro(d, round(cx - w / 2) + 1, 14, s, (0, 0, 0), 2, 1)
        micro(d, round(cx - w / 2), 13, s, (255, 255, 255), 2, 1)
    # stat comparison rows
    for i, r in enumerate(game.get("jumbo_stats", [])[:4]):
        y = 28 + i * 9
        av, hv = _num(r["a"]), _num(r["h"])
        # tie -> highlight both (>=); chevron only on a strict win (>)
        micro_r(d, 24, y, r["a"], (255, 255, 255) if av >= hv else (126, 136, 147), 1)
        if av > hv:
            tri_r(d, 5, y + 2, 2, vivid(hex_rgb(a["color"])))
        micro_c(d, 32, y, r["k"], (107, 116, 128), 1)
        micro(d, 40, y, r["h"], (255, 255, 255) if hv >= av else (126, 136, 147), 1)
        if hv > av:
            tri_r(d, 57, y + 2, 2, vivid(hex_rgb(h["color"])))
    return img


def _num(s):
    try:
        return float(str(s).replace("%", ""))
    except ValueError:
        return 0.0


def _mini_logo(img, d, team, x, y, sz):
    """Small logo sprite, or a color chip fallback."""
    spr = logos.sprite(team.get("logo", ""), sz)
    if spr is not None:
        img.paste(spr, (x, y), spr)
    else:
        d.rectangle([x, y + 1, x + 2, y + sz - 1], fill=_fit_band_color(hex_rgb(team["color"])))


# ================================================================ LAYOUT: momentum
def layout_momentum(game):
    """Live lead-margin tracker (design concept 7). Away color fills above the
    baseline when away leads, home below; gold ticks mark lead changes; the
    readout shows who's up, by how much, and any active run."""
    img = Image.new("RGB", (SIZE, SIZE), (10, 12, 16))
    d = _draw(img)
    a, h = game["away"], game["home"]
    state = game["state"]
    bg = (10, 12, 16)
    cx0, cw, base, half = 2, 60, 32, 12
    ac, hc = _fit_band_color(hex_rgb(a["color"])), _fit_band_color(hex_rgb(h["color"]))

    if state == "pre":
        vgrad(d, (0, 0, SIZE - 1, 7), (23, 27, 34), (12, 15, 19))
        d.line([0, 8, SIZE - 1, 8], fill=(39, 44, 51))
        micro(d, 3, 2, game.get("day_label") or "TODAY", (154, 163, 173), 1)
        logo_tile(img, d, 8, 11, 14, a)
        logo_tile(img, d, 42, 11, 14, h)
        micro_c(d, 32, 16, "AT", (90, 98, 107), 1)
        micro_c(d, 15, 28, a.get("record", "") or "--", (139, 144, 153), 1)
        micro_c(d, 49, 28, h.get("record", "") or "--", (139, 144, 153), 1)
        for x in range(cx0, cx0 + cw, 3):
            d.point((x, 38), fill=(34, 42, 50))
        micro_c(d, 32, 41, "AWAITING TIP", (63, 71, 79), 1)
        d.rectangle([0, 46, SIZE - 1, 63], fill=(11, 15, 19))
        d.line([0, 46, SIZE - 1, 46], fill=(28, 39, 48))
        micro(d, 4, 49, "TIP-OFF", (90, 98, 107), 1)
        micro_c(d, 32, 54, _short_status(game), (255, 255, 255), 2, 1)
        return img

    # header
    vgrad(d, (0, 0, SIZE - 1, 7), (23, 27, 34), (12, 15, 19))
    d.line([0, 8, SIZE - 1, 8], fill=(39, 44, 51))
    if state == "post":
        micro_c(d, 32, 2, "FINAL", (205, 211, 218), 1)
    else:
        d.rectangle([2, 2, 4, 4], fill=(255, 59, 48))
        parts = game["status"].split(" ")
        micro(d, 9, 2, parts[0], (205, 211, 218), 1)
        if len(parts) > 1:
            micro_r(d, SIZE - 2, 2, parts[-1], GOLD, 1)
    # reference: small logo + score per side (logo carries identity; no room for
    # logo + abbr + 3-digit score together)
    _mini_logo(img, d, a, 1, 9, 9)
    micro(d, 12, 10, str(a.get("score", 0)), (255, 255, 255), 1)
    _mini_logo(img, d, h, 54, 9, 9)
    micro_r(d, 52, 10, str(h.get("score", 0)), (255, 255, 255), 1)

    m = game.get("margins") or [0, 0]
    n = len(m)
    mx = max(1, max(abs(v) for v in m))
    scl = half / mx
    # quarter dividers
    for q in (1, 2, 3):
        x = cx0 + round(cw * q / 4)
        d.line([(x, base - half), (x, base + half - 1)], fill=(22, 29, 37))
    # interpolated two-color fill + crisp lead edge
    # brighten fills via vivid() so near-black team colors still read as an area
    afill = mix(bg, vivid(ac, 0.7, 0.4), 0.62)
    hfill = mix(bg, vivid(hc, 0.7, 0.4), 0.62)
    hedge = vivid(hc)
    for px in range(cw):
        t = px / (cw - 1) * (n - 1) if n > 1 else 0
        i0 = int(t)
        i1 = min(n - 1, i0 + 1)
        v = m[i0] + (m[i1] - m[i0]) * (t - i0)
        hgt = round(v * scl)
        x = cx0 + px
        if hgt > 0:
            d.line([(x, base - hgt), (x, base - 1)], fill=afill)
            d.point((x, base - hgt), fill=(255, 255, 255))
        elif hgt < 0:
            d.line([(x, base + 1), (x, base - hgt)], fill=hfill)
            d.point((x, base - hgt), fill=hedge)
    d.line([(cx0, base), (cx0 + cw - 1, base)], fill=(58, 64, 72))
    # lead-change ticks (gold notch below baseline at each crossing)
    for i in range(1, n):
        if (m[i - 1] < 0) != (m[i] < 0) and m[i - 1] != 0 and m[i] != 0:
            fr = abs(m[i - 1]) / (abs(m[i - 1]) + abs(m[i]))
            gx = cx0 + round(cw * ((i - 1 + fr) / (n - 1)))
            d.line([(gx, base + 1), (gx, base + 3)], fill=GOLD)
    # leading-edge marker
    last = m[-1]
    ey = base - round(last * scl)
    ex = cx0 + cw - 1
    glow_rect(d, ex - 1, ey - 1, 2, 2, (255, 255, 255) if last >= 0 else hedge)
    d.rectangle([ex - 1, ey - 1, ex, ey], fill=(255, 255, 255))
    # readout
    d.rectangle([0, 46, SIZE - 1, 63], fill=(11, 15, 19))
    d.line([0, 46, SIZE - 1, 46], fill=(28, 39, 48))
    if last == 0:
        micro_c(d, 32, 54, "ALL TIED", (205, 211, 218), 2, 1)
    else:
        lead_away = last > 0
        tri_up(d, 6, 49, 2, (231, 235, 239) if lead_away else hedge)
        micro(d, 11, 48, (a if lead_away else h)["abbr"][:3], (205, 211, 218), 1)
        run = game.get("run")
        if run:
            rt = game.get("run_team")
            rc = vivid(hex_rgb((a if rt == "away" else h)["color"])) if rt else GOLD
            micro_r(d, SIZE - 2, 48, run + " RUN", rc, 1)
        elif game.get("lead_changes"):
            micro_r(d, SIZE - 2, 48, str(game["lead_changes"]) + " LEAD CHG", (202, 160, 106), 1)
        micro_c(d, 32, 54, "+" + str(abs(last)), (255, 255, 255), 2, 1)
    return img


# ================================================================ LAYOUT: gridiron
def layout_gridiron(game):
    """NFL field-position view (design concept 3): yard-line field, ball + first-
    down markers, possession, down & distance, red-zone alert."""
    img = Image.new("RGB", (SIZE, SIZE), (4, 6, 10))
    d = _draw(img)
    a, h = game["away"], game["home"]
    state = game["state"]
    sit = game.get("situation", {})
    ac, hc = _fit_band_color(hex_rgb(a["color"])), _fit_band_color(hex_rgb(h["color"]))

    def header(label_left=None):
        vgrad(d, (0, 0, SIZE - 1, 7), (18, 24, 33), (8, 12, 16))
        d.line([0, 8, SIZE - 1, 8], fill=(28, 39, 48))
        if label_left:
            micro(d, 3, 2, label_left, (154, 163, 173), 1)

    if state == "in":
        rz = sit.get("red_zone", False)
        header()
        parts = game["status"].split(" ")
        micro(d, 3, 2, parts[0], (205, 211, 218), 1)
        if len(parts) > 1:
            micro_r(d, SIZE - 2, 2, parts[-1], GOLD, 1)
        d.rectangle([29, 2, 31, 4], fill=(255, 59, 48))
        # crests + scores at the edges, center divider so they never merge
        logo_tile(img, d, 2, 11, 12, a)
        micro(d, 16, 14, str(a.get("score", 0)), (255, 255, 255), 2, 1)
        logo_tile(img, d, 50, 11, 12, h)
        micro_r(d, 48, 14, str(h.get("score", 0)), (255, 255, 255), 2, 1)
        d.line([(32, 14), (32, 24)], fill=(58, 64, 72))
        poss = sit.get("possession")
        if poss == "away":
            d.rectangle([5, 26, 7, 27], fill=(201, 138, 74)); d.point((6, 26), fill=(255, 224, 168))
        elif poss == "home":
            d.rectangle([54, 26, 56, 27], fill=(201, 138, 74)); d.point((55, 26), fill=(255, 224, 168))
        # field
        fx, fw, fy, fh = 2, 60, 31, 12
        top = (58, 20, 20) if rz else (22, 51, 26)
        bot = (36, 12, 12) if rz else (12, 34, 15)
        vgrad(d, (fx, fy, fx + fw - 1, fy + fh - 1), top, bot)
        for yd in range(11):
            lx = fx + round(fw * yd / 10)
            d.line([(lx, fy), (lx, fy + fh - 1)], fill=(74, 106, 74) if yd == 5 else (34, 64, 42))
        d.rectangle([fx, fy, fx + 3, fy + fh - 1], fill=mix(bot, ac, 0.6))            # end zones
        d.rectangle([fx + fw - 4, fy, fx + fw - 1, fy + fh - 1], fill=mix(bot, hc, 0.6))
        fdx = fx + round(fw * sit.get("fd_pct", 0) / 100)                              # first-down line
        d.line([(fdx, fy - 1), (fdx, fy + fh)], fill=GOLD)
        bx = fx + round(fw * sit.get("ball_pct", 50) / 100)                            # ball + chevron
        by = fy + fh // 2
        d.rectangle([bx - 1, by - 1, bx + 1, by + 1], fill=(107, 59, 26))
        d.rectangle([bx - 1, by - 1, bx + 1, by + 1], outline=(201, 138, 74))
        if poss == "away":
            tri_r(d, bx + 3, by, 2, (255, 255, 255))
        elif poss == "home":
            tri_l(d, bx - 3, by, 2, (255, 255, 255))
        micro_c(d, 32, 44, sit.get("dd_text", ""), (255, 90, 77) if rz else (255, 255, 255), 2, 1)
        d.rectangle([0, 55, SIZE - 1, 63], fill=(11, 15, 19))
        d.line([0, 55, SIZE - 1, 55], fill=(28, 39, 48))
        if rz:
            micro_c(d, 32, 57, "RED ZONE", (255, 90, 77), 1)
        else:
            micro(d, 2, 57, ("BALL " + sit.get("spot_text", "")).strip(), (139, 144, 153), 1)
            if sit.get("play_clock"):
                micro_r(d, SIZE - 2, 57, ":" + str(sit["play_clock"]), (139, 144, 153), 1)
    elif state == "pre":
        header("NFL")
        logo_tile(img, d, 3, 13, 16, a)
        logo_tile(img, d, 45, 13, 16, h)
        micro_c(d, 32, 18, "AT", (90, 98, 107), 1)
        micro(d, 3, 34, a.get("record", "") or "--", vivid(ac), 1)
        micro_r(d, SIZE - 3, 34, h.get("record", "") or "--", vivid(hc), 1)
        d.line([0, 42, SIZE - 1, 42], fill=(20, 27, 34))
        micro(d, 2, 46, "KICKOFF", (90, 98, 107), 1)
        micro_c(d, 32, 53, game["status"], (255, 255, 255), 2, 1)
    else:  # final
        header()
        micro_c(d, 32, 2, "FINAL", (205, 211, 218), 1)
        win_h = int(_num(h.get("score", 0))) > int(_num(a.get("score", 0)))
        logo_tile(img, d, 2, 22, 13, a)
        micro(d, 17, 25, str(a.get("score", 0)), (255, 255, 255) if win_h else GOLD, 2, 1)
        d.line([(32, 26), (32, 33)], fill=(120, 128, 138))   # 1px score separator
        logo_tile(img, d, 49, 22, 13, h)
        micro_r(d, 48, 25, str(h.get("score", 0)), GOLD if win_h else (255, 255, 255), 2, 1)
        d.rectangle([0, 42, SIZE - 1, 43], fill=vivid(hc if win_h else ac))
    return img


LAYOUTS = {
    "bands": layout_bands,
    "jumbotron": layout_jumbotron,
    "jumbotape": layout_jumbotron_tape,
    "momentum": layout_momentum,
    "gridiron": layout_gridiron,
    "court": layout_court,
    "diagonal": layout_diagonal,
    "neon": layout_neon,
    "broadcast": layout_broadcast,
    "scorebug": layout_scorebug,
    "statline": layout_statline,
    "diamond": layout_diamond,
    "mlbbox": layout_mlb_box,
}
LAYOUT_ORDER = ["bands", "jumbotron", "diagonal", "neon", "broadcast", "scorebug", "statline", "diamond"]

PLAYOFF_LAYOUTS = {
    "po_crucible": layout_playoff_crucible,
    "po_series": layout_playoff_series,
    "po_spotlight": layout_playoff_spotlight,
}
PLAYOFF_ORDER = ["po_crucible", "po_series", "po_spotlight"]

ALL_LAYOUTS = {**LAYOUTS, **PLAYOFF_LAYOUTS}


def render_game(game, layout="broadcast"):
    return ALL_LAYOUTS.get(layout, layout_broadcast)(game)


# ---------------------------------------------------------------- ticker board
LEAGUE_PIP = {
    "nba": (200, 90, 30), "nfl": (40, 110, 200), "mlb": (60, 140, 70),
    "nhl": (150, 150, 160), "epl": (130, 60, 160),
}


def render_list(games, title="SCORES", max_rows=5):
    img = Image.new("RGB", (SIZE, SIZE), HEADER_BG)
    d = _draw(img)
    d.rectangle([0, 0, SIZE - 1, 8], fill=(24, 28, 36))
    d.text((2, 1), title[:12], font=small(9), fill=GOLD)
    cnt = f"{len(games)}"
    d.text((SIZE - 2 - d.textlength(cnt, small(9)), 1), cnt, font=small(9), fill=(120, 125, 135))
    row_h = 11
    for i in range(min(len(games), max_rows)):
        g = games[i]
        y = 10 + i * row_h
        away, home = g["away"], g["home"]
        d.rectangle([0, y + 1, 1, y + 7], fill=LEAGUE_PIP.get(g["league"], (120, 120, 120)))
        fav = away.get("fav") or home.get("fav")
        col = GOLD if fav else WHITE
        if g["state"] == "pre":
            d.text((4, y), f"{away['abbr']}-{home['abbr']}", font=small(9), fill=col)
            t = g["status"]
            for tag in ("jst", "et", "ct", "mt", "pt"):
                if t.endswith(tag):
                    t = t[: -len(tag)]
            d.text((SIZE - 1 - d.textlength(t, small(9)), y), t, font=small(9), fill=(140, 145, 155))
        else:
            line = f"{away['abbr']} {away['score']}-{home['score']} {home['abbr']}"
            d.text((4, y), line, font=small(9), fill=col)
            if g["state"] == "in":
                d.ellipse([SIZE - 4, y + 2, SIZE - 1, y + 5], fill=(235, 60, 60))
            elif g["state"] == "post":
                d.text((SIZE - 1 - d.textlength("F", small(9)), y), "F", font=small(9), fill=(120, 125, 135))
    return img


def blank():
    """Clean dark frame for when there's genuinely nothing to show (no message)."""
    return Image.new("RGB", (SIZE, SIZE), (0, 0, 0))


def render_message(title, subtitle="", leagues=None):
    img = Image.new("RGB", (SIZE, SIZE), HEADER_BG)
    d = _draw(img)
    d.rectangle([0, 0, SIZE - 1, 9], fill=(24, 28, 36))
    lbl = "/".join(l.upper() for l in (leagues or [])) or "SCORES"
    d.text((2, 2), lbl[:14], font=small(9), fill=GOLD)
    tw = d.textlength(title, small(13))
    d.text(((SIZE - tw) // 2, 24), title, font=small(13), fill=WHITE)
    if subtitle:
        sw = d.textlength(subtitle, small(9))
        d.text(((SIZE - sw) // 2, 40), subtitle, font=small(9), fill=(150, 155, 165))
    return img
