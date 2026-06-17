"""Big-moment splash animations for live games.

Faithful Pillow port of the design's pixel-canvas animations (docs/Pixoo
Scoreboards.dc(3).html — "LIVE SPLASHES"). Each splash is a continuous function
spl_*(p, t, data) sampled into frames and played on-device as one looping
multi-frame GIF (pixoo.push_animation), which the Pixoo plays from its own
memory — smooth, not bound by the ~1fps HTTP push limit.
"""
import math

from PIL import Image

SIZE = 64

# 3x5 pixel font (Tiny5-class), ported verbatim from the design source.
FONT = {
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
    '!': ['.#.', '.#.', '.#.', '...', '.#.'], "'": ['.#.', '.#.', '...', '...', '...'],
    '&': ['.#.', '#.#', '.#.', '#.#', '.##'], '%': ['#.#', '..#', '.#.', '#..', '#.#'],
    '@': ['###', '#.#', '###', '#..', '###'], '?': ['###', '..#', '.#.', '...', '.#.'],
    '·': ['...', '...', '.#.', '...', '...'], ',': ['...', '...', '...', '.#.', '#..'],
    '*': ['#.#', '.#.', '#.#', '...', '...'], '(': ['.##', '.#.', '#..', '.#.', '.##'],
    ')': ['##.', '.#.', '..#', '.#.', '##.'], '°': ['.#.', '#.#', '.#.', '...', '...'],
    '#': ['#.#', '###', '#.#', '###', '#.#'],
}


def _hex(c):
    if isinstance(c, (tuple, list)):
        return tuple(c)
    c = str(c).lstrip('#')
    if len(c) == 3:
        c = ''.join(x * 2 for x in c)
    n = int(c, 16)
    return ((n >> 16) & 255, (n >> 8) & 255, n & 255)


class Pix:
    """Port of the design's makePix: a 64x64 RGB buffer with alpha-blending
    primitives, mirroring the JS API so splash code ports ~1:1."""

    def __init__(self, w=SIZE, h=SIZE):
        self.w, self.h = w, h
        self.buf = bytearray(w * h * 3)

    def set(self, x, y, c, a=255):
        x = int(x); y = int(y)
        if x < 0 or y < 0 or x >= self.w or y >= self.h:
            return
        r, g, b = _hex(c)
        i = (y * self.w + x) * 3
        if a >= 255:
            self.buf[i] = r; self.buf[i + 1] = g; self.buf[i + 2] = b
        else:
            af = a / 255.0; ia = 1 - af
            self.buf[i] = int(r * af + self.buf[i] * ia)
            self.buf[i + 1] = int(g * af + self.buf[i + 1] * ia)
            self.buf[i + 2] = int(b * af + self.buf[i + 2] * ia)

    def fillBlock(self, x, y, bw, bh, c, a=255):
        x = int(x); y = int(y); bw = int(bw); bh = int(bh)
        if a >= 255 and x <= 0 and y <= 0 and x + bw >= self.w and y + bh >= self.h:
            r, g, bl = _hex(c)                       # fast path: full-screen fill
            self.buf[:] = bytes((r, g, bl)) * (self.w * self.h)
            return
        for yy in range(bh):
            for xx in range(bw):
                self.set(x + xx, y + yy, c, a)

    def rectOutline(self, x, y, bw, bh, c, a=255):
        bw = int(bw); bh = int(bh)
        for xx in range(bw):
            self.set(x + xx, y, c, a); self.set(x + xx, y + bh - 1, c, a)
        for yy in range(bh):
            self.set(x, y + yy, c, a); self.set(x + bw - 1, y + yy, c, a)

    def hline(self, x, y, length, c, a=255):
        for i in range(int(length)):
            self.set(x + i, y, c, a)

    def vline(self, x, y, length, c, a=255):
        for i in range(int(length)):
            self.set(x, y + i, c, a)

    def line(self, x0, y0, x1, y1, c, a=255):
        x0 = int(x0); y0 = int(y0); x1 = int(x1); y1 = int(y1)
        dx = abs(x1 - x0); dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1; sy = 1 if y0 < y1 else -1; err = dx + dy
        while True:
            self.set(x0, y0, c, a)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy; x0 += sx
            if e2 <= dx:
                err += dx; y0 += sy

    def disc(self, cx, cy, r, c, a=255):
        r = int(r)
        for yy in range(-r, r + 1):
            for xx in range(-r, r + 1):
                if xx * xx + yy * yy <= r * r + r * 0.6:
                    self.set(cx + xx, cy + yy, c, a)

    def ring(self, cx, cy, r, c, a=255):
        r = int(r)
        for yy in range(-r, r + 1):
            for xx in range(-r, r + 1):
                d = xx * xx + yy * yy
                if d <= r * r + r * 0.6 and d > (r - 1) * (r - 1):
                    self.set(cx + xx, cy + yy, c, a)

    def diamond(self, cx, cy, r, c, fill=True, a=255):
        r = int(r)
        for yy in range(-r, r + 1):
            span = r - abs(yy)
            if fill:
                for xx in range(-span, span + 1):
                    self.set(cx + xx, cy + yy, c, a)
            else:
                self.set(cx - span, cy + yy, c, a); self.set(cx + span, cy + yy, c, a)

    def text(self, x, y, s, c, scale=1, gap=1):
        cx = x
        for ch in str(s).upper():
            g = FONT.get(ch, FONT['?'])
            for ry in range(5):
                row = g[ry]
                for rx in range(3):
                    if row[rx] != '.':
                        self.fillBlock(cx + rx * scale, y + ry * scale, scale, scale, c)
            cx += (3 + gap) * scale
        return cx - x - gap * scale

    def textW(self, s, scale=1, gap=1):
        return len(str(s)) * (3 + gap) * scale - gap * scale

    def to_image(self):
        return Image.frombytes('RGB', (self.w, self.h), bytes(self.buf))


# ---- celebration helpers (ported from the design's class methods) ----

def _rnd(i):
    x = math.sin(i * 127.1 + 311.7) * 43758.5453
    return x - math.floor(x)


def _out_text(p, cx, y, s, col, scale):
    wd = p.textW(s, scale, 1)
    x = round(cx - wd / 2)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        p.text(x + dx, y + dy, s, '#070708', scale, 1)
    p.text(x, y, s, col, scale, 1)


def _flash(p, ts, dur):
    if ts < 0 or ts > dur:
        return
    p.fillBlock(0, 0, 64, 64, '#ffffff', round(210 * (1 - ts / dur)))


def _burst(p, ox, oy, ts, pal, n, speed):
    if ts < 0 or ts > 1.1:
        return
    for i in range(n):
        a = (i / n) * 6.2832 + ox * 0.6
        sp = speed * (0.55 + _rnd(i + ox) * 0.7)
        x = ox + math.cos(a) * sp * ts
        y = oy + math.sin(a) * sp * ts + 14 * ts * ts
        al = max(0, 255 * (1 - (ts - 0.6) / 0.5)) if ts > 0.6 else 255
        col = pal[(i + int(ts * 8)) % len(pal)]
        p.set(int(x), int(y), col, al)
        if ts < 0.5:
            p.set(int(x - math.cos(a)), int(y - math.sin(a)), col, al * 0.45)


def _seg_line(p, cx, y, segs):
    """Draw a centered line of (text, color) segments with a space between them
    (outlined). Lets us color the jersey number differently from the name."""
    widths = [p.textW(s, 1, 1) for s, _ in segs]
    total = sum(widths) + 4 * (len(segs) - 1)        # one char-cell gap between segs
    x = round(cx - total / 2)
    for (s, col), w in zip(segs, widths):
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            p.text(x + dx, y + dy, s, '#070708', 1, 1)
        p.text(x, y, s, col, 1, 1)
        x += w + 4


def _confetti(p, ts, pal):
    if ts < 0:
        return
    for i in range(26):
        x = _rnd(i) * 64 + ts * 9 * (_rnd(i + 9) - 0.5)
        x = ((x % 64) + 64) % 64
        y = (_rnd(i + 3) * 16 + ts * 42) % 70
        if y < 5 or y > 63:
            continue
        p.fillBlock(int(x), int(y), 1, 2, pal[i % len(pal)])


def _info_strip(p, lines, accent='#ffd23f'):
    """Bottom data strip: 1-2 short centered lines of (text,color) segments
    (player / number / distance), drawn under the big celebration text."""
    lines = [ln for ln in lines if ln]
    if not lines:
        return
    top = 64 - (6 * len(lines) + 2)
    p.fillBlock(0, top - 1, 64, 64 - top + 1, '#06080e', 225)
    p.hline(0, top - 1, 64, accent, 110)
    for i, segs in enumerate(lines):
        _seg_line(p, 32, top + 1 + i * 6, segs)


def _hr_lines(data):
    """Home-run info: 'OHTANI' (white) + jersey number (gold) / distance (gold).
    No '#' glyph — the gold number reads as the jersey on its own."""
    if not data:
        return []
    name = (data.get('player') or '').upper()[:10]
    num = str(data.get('number') or '')
    dist = str(data.get('detail') or '')         # e.g. "417'"
    line1 = []
    if name:
        line1.append((name, '#ffffff'))
    if num:
        line1.append((num, '#ffd23f'))
    return [line1, [(dist, '#ffd23f')] if dist else []]


# ---- splashes ----

def spl_hr(p, t, data=None):
    """HOME RUN: ball launches over the wall, three firework bursts, big text.
    Design splHR (D=3.0s) + a bottom data strip with player/number/distance."""
    D = 3.0
    lt = t % D
    p.fillBlock(0, 0, 64, 64, '#06080e')
    for i in range(12):                                   # faint stars
        if _rnd(i) < 0.75:
            p.set(int(_rnd(i) * 64), int(_rnd(i + 5) * 42), '#1b2536')
    p.fillBlock(0, 47, 64, 5, '#13351c')                 # grass
    p.hline(0, 47, 64, '#ffd23f', 120)                   # wall line
    for x in range(0, 64, 3):
        p.set(x, 46, '#0c2113')
    if lt < 1.0:                                          # ball arcs out, trailing
        u = min(1, lt / 0.9)
        for k in range(5, -1, -1):
            uk = max(0, u - k * 0.045)
            tx = 6 + 52 * uk
            ty = 49 - 30 * uk - 13 * math.sin(uk * math.pi)
            p.set(int(tx), int(ty), '#ffffff' if k == 0 else '#5d6675',
                  255 if k == 0 else 180 - k * 28)
    _flash(p, lt, 0.16)
    _burst(p, 46, 12, lt - 0.8, ['#ffd23f', '#ff9e3d', '#ffffff'], 16, 30)
    _burst(p, 17, 16, lt - 1.3, ['#ff5a4d', '#ffd23f', '#ffffff'], 16, 26)
    _burst(p, 40, 20, lt - 1.8, ['#4f7be0', '#ffffff', '#ffd23f'], 16, 28)
    if lt > 1.0:
        if lt < 1.12:
            _flash(p, lt - 1.0, 0.12)
        _out_text(p, 32, 22, 'HOME', '#ffd23f', 2)
        _out_text(p, 32, 36, 'RUN', '#ffffff', 2)
        _info_strip(p, _hr_lines(data))


def spl_slam(p, t, data=None):
    """GRAND SLAM: bases light 1-2-3-4 as the runner circles, '+4', finale burst.
    Design splSlam (D=3.2s) + the batter's name up top."""
    D = 3.2
    lt = t % D
    p.fillBlock(0, 0, 64, 64, '#0a0810')
    cx, cy, r = 32, 24, 11      # diamond dropped 2px to clear the batter name
    home = [cx, cy + r]; first = [cx + r, cy]; second = [cx, cy - r]; third = [cx - r, cy]
    pts = [home, first, second, third]
    for i in range(4):
        a, b = pts[i], pts[(i + 1) % 4]
        p.line(a[0], a[1], b[0], b[1], '#33281a')
    legs = min(1, lt / 1.4) * 4
    for i in range(4):
        b = pts[(i + 1) % 4]
        if legs > i:
            p.diamond(b[0], b[1], 2, '#ffd23f')
        else:
            p.diamond(b[0], b[1], 2, '#4a4030', False)
    p.diamond(home[0], home[1], 2, '#ffffff')
    if lt < 1.4:
        li = int(legs) % 4
        f = legs - int(legs)
        a, b = pts[li], pts[(li + 1) % 4]
        p.disc(int(a[0] + (b[0] - a[0]) * f), int(a[1] + (b[1] - a[1]) * f), 1, '#ffffff')
    p.text(54, 3, '+4', '#ffd23f', 1)
    _burst(p, 16, 14, lt - 1.4, ['#ffd23f', '#ffffff'], 16, 26)
    _burst(p, 48, 14, lt - 1.7, ['#ff5a4d', '#ffd23f'], 16, 26)
    _burst(p, 32, 10, lt - 2.0, ['#4f7be0', '#ffffff', '#ffd23f'], 18, 30)
    if data:
        nm = (data.get('player') or '').upper()[:9]
        if nm:
            _out_text(p, 22, 3, nm, '#cdd3da', 1)
    if lt > 1.4:
        if lt < 1.55:
            _flash(p, lt - 1.4, 0.14)
        _out_text(p, 32, 40, 'GRAND', '#ffffff', 1)
        _out_text(p, 32, 48, 'SLAM', '#ffd23f', 2)


def spl_walk(p, t, data=None):
    """WALK-OFF WIN: runner touches home, crowd line erupts, confetti. Design
    splWalk (D=3.0s) + the walk-off hero's name."""
    D = 3.0
    lt = t % D
    p.fillBlock(0, 0, 64, 64, '#0a0810')
    hx, hy = 32, 46
    p.diamond(hx, hy, 3, '#e7ebef')
    if lt < 1.0:
        u = min(1, lt / 0.9)
        x = 58 - (58 - hx) * u; y = hy - 1
        p.fillBlock(int(x - 1), int(y - 3), 3, 4, '#1565a6')
        p.rectOutline(int(x - 1), int(y - 3), 3, 4, '#5aa2dd')
    if lt > 0.9:
        st = lt - 0.9
        if st < 0.18:
            _flash(p, st, 0.18)
        for x in range(2, 62, 3):
            j = abs(math.sin(t * 5 + x)) * 3
            p.set(x, int(57 - j), '#243a6b')
            p.set(x, int(61 - j), '#1565a6')
        _confetti(p, st, ['#1565a6', '#5aa2dd', '#ffffff', '#ffd23f'])
        _out_text(p, 32, 15, 'WALK-OFF', '#ffffff', 1)
        _out_text(p, 32, 25, 'WIN', '#ffd23f', 3)
        if data:
            nm = (data.get('player') or '').upper()[:11]
            if nm:
                p.fillBlock(0, 43, 64, 7, '#0a0810', 210)   # clear confetti behind the name
                _out_text(p, 32, 44, nm, '#cdd3da', 1)


SPLASHES = {'hr': spl_hr, 'slam': spl_slam, 'walkoff': spl_walk}
DURATIONS = {'hr': 3.0, 'slam': 3.2, 'walkoff': 3.0}


def animate(kind, data=None, fps=16, duration=None):
    """Render a splash to a list of PIL frames + the per-frame ms for playback.
    Sampling D seconds into N frames makes a seamless loop on the device."""
    fn = SPLASHES[kind]
    dur = duration or DURATIONS.get(kind, 3.0)
    n = max(1, int(round(dur * fps)))
    frames = [None] * n
    for i in range(n):
        p = Pix()
        fn(p, dur * i / n, data)
        frames[i] = p.to_image()
    return frames, int(round(1000.0 / fps))
