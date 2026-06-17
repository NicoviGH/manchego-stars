#!/usr/bin/env python3
"""Render the title-screen subtitle ("RIME OF THE FROSTMAIDEN") in the bold
slab-serif caps of the vanilla "THE SACRED STONES" scroll banner.

The scroll font is a one-off (only its own letters exist + several touch/kern), so
the subtitle is hand-built here as ~10px shape masks matching that style: bold 2px
stems, square slab terminals, flat black ink (mode 'L', the scroll graphic's
grayscale). Two lines are composed and stacked by the caller. Style reference:
graphics/titlescreen/title_logos.png rows 14-23.
"""
import sys

import numpy as np
from PIL import Image

INK = 17        # dark grayscale value of the scroll text (mode 'L')
BG = 255        # parchment / transparent marker
CAP_H = 10
LETTER_GAP = 2
SPACE_W = 6

# 10-row bold slab caps, `#` = ink.
GLYPHS = {
    'R': ["#####  ",
          "##..## ",
          "##..## ",
          "##..## ",
          "#####  ",
          "####   ",
          "##.##  ",
          "##.##  ",
          "##..## ",
          "##..## "],
    'I': ["######",
          "..##..",
          "..##..",
          "..##..",
          "..##..",
          "..##..",
          "..##..",
          "..##..",
          "..##..",
          "######"],
    'M': ["##....##",
          "###..###",
          "########",
          "##.##.##",
          "##.##.##",
          "##....##",
          "##....##",
          "##....##",
          "##....##",
          "##....##"],
    'E': ["######",
          "######",
          "##....",
          "##....",
          "#####.",
          "#####.",
          "##....",
          "##....",
          "######",
          "######"],
    'O': [".####.",
          "######",
          "##..##",
          "##..##",
          "##..##",
          "##..##",
          "##..##",
          "##..##",
          "######",
          ".####."],
    'F': ["######",
          "######",
          "##....",
          "##....",
          "#####.",
          "#####.",
          "##....",
          "##....",
          "##....",
          "##...."],
    'T': ["######",
          "######",
          "..##..",
          "..##..",
          "..##..",
          "..##..",
          "..##..",
          "..##..",
          "..##..",
          "..##.."],
    'H': ["##..##",
          "##..##",
          "##..##",
          "##..##",
          "######",
          "######",
          "##..##",
          "##..##",
          "##..##",
          "##..##"],
    'S': [".#####",
          "######",
          "##....",
          "###...",
          ".####.",
          "..####",
          "....##",
          "....##",
          "######",
          "#####."],
    'A': [".####.",
          "######",
          "##..##",
          "##..##",
          "##..##",
          "######",
          "######",
          "##..##",
          "##..##",
          "##..##"],
    'D': ["#####.",
          "######",
          "##..##",
          "##..##",
          "##..##",
          "##..##",
          "##..##",
          "##..##",
          "######",
          "#####."],
    'N': ["##..##",
          "###.##",
          "######",
          "######",
          "##.###",
          "##..##",
          "##..##",
          "##..##",
          "##..##",
          "##..##"],
}


def _mask(ch):
    rows = GLYPHS[ch]
    w = max(len(r) for r in rows)
    m = np.zeros((CAP_H, w), dtype=bool)
    for y, r in enumerate(rows):
        for x, c in enumerate(r):
            if c == '#':
                m[y, x] = True
    return m


def compose(text):
    """One line of subtitle text as an (H, W) uint8 'L' array (INK on BG)."""
    text = text.upper()
    parts, widths = [], []
    for ch in text:
        if ch == ' ':
            parts.append(None)
            widths.append(SPACE_W)
        else:
            if ch not in GLYPHS:
                sys.exit('ERROR: no subtitle glyph for %r' % ch)
            m = _mask(ch)
            parts.append(m)
            widths.append(m.shape[1])
    total = sum(widths) + LETTER_GAP * (len(parts) - 1)
    out = np.full((CAP_H, total), BG, dtype=np.uint8)
    x = 0
    for m, w in zip(parts, widths):
        if m is not None:
            out[:, x:x + w][m] = INK
        x += w + LETTER_GAP
    return out


def compose_lines(lines):
    """Stack lines (list of strings) centered, 2px leading, as an 'L' Image."""
    arrs = [compose(t) for t in lines]
    W = max(a.shape[1] for a in arrs)
    lead = 2
    H = sum(a.shape[0] for a in arrs) + lead * (len(arrs) - 1)
    out = np.full((H, W), BG, dtype=np.uint8)
    y = 0
    for a in arrs:
        x = (W - a.shape[1]) // 2
        sub = out[y:y + a.shape[0], x:x + a.shape[1]]
        sub[a == INK] = INK
        y += a.shape[0] + lead
    return Image.fromarray(out, 'L')


def replace_scroll(orig_path, lines=('RIME OF THE', 'FROSTMAIDEN'),
                   clear=(11, 39, 0, 228), origin=(104, 12)):
    """New title_logos.png: drop the "THE SACRED STONES" scroll (cleared to the
    transparent index 0) and draw the two-line subtitle floating in its place, so the
    existing banner sprite (PutSpriteExt at screen 16,85) renders our subtitle. Keeps
    "Press START" + the copyright line untouched. Light fill (white) + dark outline so
    it reads on the title art. `origin`=(centre x, top y) in title_logos pixels; the
    banner draws at screen x=16, so centre x=104 -> screen centre 120."""
    im = Image.open(orig_path).convert('L')
    a = np.array(im)
    y0, y1, x0, x1 = clear
    a[y0:y1, x0:x1] = 0                          # 0 -> transparent OBJ index
    sub = np.array(compose_lines(list(lines)))   # 17 ink, 255 bg
    ink = sub == 17
    ys, xs = np.where(ink)
    sw = ink.shape[1]
    cx, ty = origin
    ox, oy = cx - sw // 2, ty
    for dy in (-1, 0, 1):                         # dark outline on transparent cells
        for dx in (-1, 0, 1):
            ny, nx = ys + dy + oy, xs + dx + ox
            ok = (ny >= 0) & (ny < a.shape[0]) & (nx >= 0) & (nx < a.shape[1])
            a[ny[ok], nx[ok]] = np.where(a[ny[ok], nx[ok]] == 0, 17, a[ny[ok], nx[ok]])
    a[ys + oy, xs + ox] = 255                     # white fill (index 15)
    return Image.fromarray(a, 'L')


def main():
    if len(sys.argv) < 3:
        sys.exit('usage: gen_subtitle.py out.png LINE1 [LINE2 ...]')
    im = compose_lines(sys.argv[2:])
    im.save(sys.argv[1])
    w, h = im.size
    im.convert('RGB').resize((w * 6, h * 6), Image.NEAREST).save(
        sys.argv[1][:-4] + '_6x.png')
    print('wrote %s (%dx%d)' % (sys.argv[1], w, h))


if __name__ == '__main__':
    main()
