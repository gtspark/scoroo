# Pixoo 64 Sports Scoreboard — Design Brief

A brief for mocking up new ways to represent live sports on a Divoom Pixoo 64.
Hand this to a design assistant. It covers the canvas, how we draw, the **hard
constraints**, and the **full data palette** (including everything we're not
using yet). Goal: stop underselling a 4096-pixel canvas.

---

## 1. The canvas
- **64 × 64 RGB LED matrix = 4096 pixels.** Each pixel fully addressable, 24-bit color.
- Viewed from across a room (desk shelf). Glanceability > density, but there's
  real room for pixel art, icons, and layered composition.
- Brightness controllable 0–100 (we auto-dim at night). No touch input, no sensors.
- It's a *physical pixel-art display* — think NES/arcade sprite art, scoreboard
  jumbotrons, transit signage. Not a tiny webpage.

## 2. How we render (capabilities)
- **Python + Pillow.** We compose a 64×64 RGB image per frame and push it.
- Full per-pixel control. Primitives: rectangles, lines, polygons, ellipses/arcs,
  individual points, paste/blit of sprites & PNGs.
- **Manual gradients, bevels, drop shadows, glows, dithering** — all already in use.
- **Pixel fonts**, anti-aliasing OFF (crisp). Currently bundled:
  - *Press Start 2P* — chunky 8px-grid, great for big scores/numbers.
  - *Tiny5* — narrow 5px, good for labels in tight spots.
  - We can add more pixel/BDF fonts trivially (e.g. a 3×5 micro font for dense text).
- **Sprites/logos:** we can download PNGs (ESPN serves team logos at 500px),
  downscale to 16–28px, and blit them. **Not used yet** — big opportunity.
- Frames can be precomputed/cached; we control a rotation of "screens."

## 3. THE HARD CONSTRAINT (read this before designing motion)
The device's HTTP firmware is **single-threaded and slow**. Pushing single
frames sustains only **~1 frame/sec**, and it drops connections if you burst.
**So: design for static "posters," not video.** A new composition every few
seconds (we rotate screens ~7s each) is the native rhythm.

- ❌ No smooth 30fps animation via frame pushes.
- ⚠️ A short looping animation uploaded as **one batched multi-frame GIF**
  (the device plays it internally) *might* be smooth — untested by us, worth a
  probe. Treat smooth motion as "maybe," static as "guaranteed."
- ✅ Subtle per-rotation state changes are free (blink a "LIVE" dot between
  refreshes, alternate two poster variants).

Design primarily for **one beautiful still frame** that reads instantly.

## 4. The data palette (what we can show)
Source: ESPN's public scoreboard API (no key), polled ~every 60s, per league
(NBA / NFL / MLB; NHL & EPL available). Per game we have:

### Currently used
- Team abbreviations (SA, NY), primary + alternate **team colors** (hex)
- Live **score**, game **state** (pre / in / post)
- **Status/clock**: "Q3 4:21", "Top 5th", "FINAL", tip-off time (shown in JST)
- **Favorite** flag (teams the user follows)
- **Win/loss record** ("62-20")
- **Playoff series**: round + game ("NBA Finals · G5"), series summary
  ("NY leads 3-1"), per-team series wins (for best-of-7 win pips),
  match-point / elimination / Game-7 detection

### Available but NOT used yet (the upside)
- **Official team logos** (PNG, any size) — `…/teamlogos/nba/500/scoreboard/sa.png`
- **Scoring leaders per team**: athlete + stat, e.g. "V. Wembanyama — 25.0 PPG",
  "11.5 RPG", "7.4 APG". A "players to watch" / live-leader strip.
- **Record splits**: total, **home**, **road** ("32-8 home", "29-12 road")
- **Betting odds**: spread ("SA -5.5"), over/under (216.5), moneyline (+160 / -192)
- **Broadcast channel** ("ABC", "ESPN") — "where to watch"
- **Venue** ("Frost Bank Center"), attendance, neutral-site flag
- **Baseball live situation** (MLB, during play): balls / strikes / **outs**,
  runners **on 1st/2nd/3rd** (a base-diamond!), current pitcher & batter, last play
- **Football live situation** (NFL, during play): down & distance, possession,
  red-zone flag (typically available live)
- Series format, highlights links, game leaders rating string

## 5. Per-sport texture worth leaning into
- **NBA**: quarter + clock, 3-digit scores, scoring leaders, playoff series pips.
- **MLB**: a **base/out/count diamond** is the iconic baseball glance — bases as
  3 diamonds that fill, outs as dots, the count. Very pixel-friendly.
- **NFL**: down & distance ("3rd & 7"), possession arrow, red-zone alert color.
- **Playoffs (now)**: series win pips, "ELIMINATION" / "GAME 7" drama, gold/trophy
  prestige treatment.

## 6. What exists today (so you can push past it)
8 layouts, switchable, that rotate as full-screen cards:
- **Regular:** `bands` (flat baseline), `jumbotron` (3D bevels), `diagonal`
  (color split), `neon` (glow outlines), `broadcast` (gradient TV panels).
- **Playoff (auto):** `po_crucible`, `po_series`, `po_spotlight` (win pips +
  elimination callouts).
- Plus a static "ticker board" listing several games at once.

Honest critique: these are mostly **two team-color bands + abbreviation + big
number**. They're clean but they treat 4096 pixels like a 2-row LCD. We're not
using logos, leaders, base/out diamonds, spatial composition, or icon language.

## 7. What I want from you (design assistant)
Mock up **fresh 64×64 concepts** that make this feel like a premium pixel-art
scoreboard. Ideas to explore:
- Use **team logos** as the hero element (downscaled sprite art).
- A real **MLB base/out/count diamond** layout.
- An **NFL down-&-distance / field-position** layout.
- A **"stat line"** layout surfacing scoring leaders, not just the score.
- Information-dense but legible compositions that earn the full canvas.
- A distinctive **typographic / icon system** (custom glyphs for live/final, outs,
  possession, series pips, etc.).
- Per-state variants (pre = matchup + odds + tip time; live = score + situation;
  final = result + standout performer).

**Deliverable:** annotated 64×64 mockups (render at large scale / nearest-neighbor
so pixels are visible). For each, note exact pixel regions for every element so
it's implementable in Pillow, and call out one legibility risk. Remember the
~1fps constraint — design still frames, not motion. Favor bold, layered,
glanceable compositions over flat bands.
```
Implementable primitives recap: rect, line, polygon, ellipse, point, gradient
(manual), bevel (light/dark edges), glow (concentric rects), PNG sprite blit,
pixel fonts (Press Start 2P, Tiny5, + we can add). No anti-aliasing.
```
