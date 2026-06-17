#!/usr/bin/env python3
"""Compose a gold FE8 title-logo word (the "FIRE EMBLEM" style) from hand-drawn
letter SHAPE masks + the logo's own gradient/outline/shadow rules.

The vanilla gold logo (graphics/titlescreen/title_fire_emblem_logo.png) is a
one-off ~10-letter font, so a new title like "MANCHEGO STARS" can't be cut from
it -- the missing letters have to be drawn. They're drawn here as upright block
masks (`#` = ink); the styler then reproduces the logo look automatically:

  * FILL  -- a per-row vertical sheen gradient read off a clean vanilla stem
             (dark top, bright middle highlight, dark bottom).
  * OUTLINE-- a red-brown edge (the logo's idx 13/14) around the fill.
  * SHADOW -- a dark drop-shadow offset down-right.
  * ITALIC -- the whole glyph sheared right with rising rows (the logo's slant).

Palette is the vanilla logo's own (indices below index into it), so the output
drops onto the title sprite with no palette change.

Usage: gen_gold_title.py "MANCHEGO STARS" out.png [preview4x.png]
"""
import os
import sys

import numpy as np
from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO = os.path.join(REPO, 'fireemblem8u', 'graphics', 'titlescreen',
                    'title_fire_emblem_logo.png')

# Palette indices into the vanilla logo palette.
FILL_GRADIENT = [3, 3, 5, 5, 7, 7, 7, 7, 7, 5, 5, 3, 3, 3]  # top->bottom sheen
OUTLINE = 13        # red-brown edge (148,49,24)
OUTLINE_DARK = 14   # darker red-brown (82,16,8) for the bottom-right edge
SHADOW = 1          # near-black drop shadow (8,16,8)
BG = 0              # transparent/background (131,164,131 -- keyed out on the sprite)

CAP_H = len(FILL_GRADIENT)   # ink height in rows
SLANT = 0.26                 # px of rightward shear per row above the baseline
LETTER_GAP = 1               # blank columns between letters (pre-slant)
SPACE_W = 6                  # width of a ' '

# The logo sprite is drawn at screen x=4 (titlescreen.c), so canvas col 0 -> screen 4
# and only canvas cols 0..VIS_W-1 are on the 240px screen. Center the word in that
# visible window (shifted left of the canvas centre) so it doesn't clip off the right.
VIS_W = 240 - 4

# Upright block masks, top->bottom, exactly CAP_H rows. `#` = ink, ` ` = empty.
# Bold 3px stems so the gold fill dominates the 1px red outline (as vanilla does).
GLYPHS = {
    'M': ["###       ###",
          "####     ####",
          "#####   #####",
          "### ### ### ##",
          "###  ###  ###",
          "###   #   ###",
          "###       ###",
          "###       ###",
          "###       ###",
          "###       ###",
          "###       ###",
          "###       ###",
          "###       ###",
          "###       ###"],
    'A': ["    ####    ",
          "   ######   ",
          "  ###  ###  ",
          " ###    ### ",
          "###      ###",
          "###      ###",
          "############",
          "############",
          "###      ###",
          "###      ###",
          "###      ###",
          "###      ###",
          "###      ###",
          "###      ###"],
    'N': ["###      ###",
          "####     ###",
          "#####    ###",
          "### ###  ###",
          "###  ### ###",
          "###   ######",
          "###    #####",
          "###     ####",
          "###      ###",
          "###      ###",
          "###      ###",
          "###      ###",
          "###      ###",
          "###      ###"],
    'C': ["  ########  ",
          " ########## ",
          "###      ###",
          "###       # ",
          "###         ",
          "###         ",
          "###         ",
          "###         ",
          "###         ",
          "###       # ",
          "###      ###",
          " ########## ",
          "  ########  ",
          "            "],
    'H': ["###      ###",
          "###      ###",
          "###      ###",
          "###      ###",
          "###      ###",
          "############",
          "############",
          "###      ###",
          "###      ###",
          "###      ###",
          "###      ###",
          "###      ###",
          "###      ###",
          "###      ###"],
    'E': ["###########",
          "###########",
          "###        ",
          "###        ",
          "###        ",
          "########   ",
          "########   ",
          "###        ",
          "###        ",
          "###        ",
          "###        ",
          "###########",
          "###########",
          "           "],
    'G': ["  ########  ",
          " ########## ",
          "###      ###",
          "###       # ",
          "###         ",
          "###         ",
          "###    #####",
          "###    #####",
          "###      ###",
          "###      ###",
          "###      ###",
          " ########## ",
          "  ########  ",
          "            "],
    'O': ["  ########  ",
          " ########## ",
          "###      ###",
          "###      ###",
          "###      ###",
          "###      ###",
          "###      ###",
          "###      ###",
          "###      ###",
          "###      ###",
          "###      ###",
          " ########## ",
          "  ########  ",
          "            "],
    'S': ["  ########  ",
          " ########## ",
          "###      ###",
          "###         ",
          "####        ",
          " #######    ",
          "   ####### ",
          "       #### ",
          "         ###",
          "###      ###",
          "###      ###",
          " ########## ",
          "  ########  ",
          "            "],
    'T': ["############",
          "############",
          "     ##     ",
          "     ##     ",
          "     ##     ",
          "     ##     ",
          "     ##     ",
          "     ##     ",
          "     ##     ",
          "     ##     ",
          "     ##     ",
          "     ##     ",
          "     ##     ",
          "            "],
    'R': ["#########   ",
          "########### ",
          "###      ###",
          "###      ###",
          "###      ###",
          "########### ",
          "#########   ",
          "###  ###    ",
          "###   ###   ",
          "###   ###   ",
          "###    ###  ",
          "###     ### ",
          "###      ###",
          "            "],
    'I': ["######",
          "######",
          "  ##  ",
          "  ##  ",
          "  ##  ",
          "  ##  ",
          "  ##  ",
          "  ##  ",
          "  ##  ",
          "  ##  ",
          "  ##  ",
          "######",
          "######",
          "      "],
    'F': ["##########",
          "##########",
          "###       ",
          "###       ",
          "###       ",
          "########  ",
          "########  ",
          "###       ",
          "###       ",
          "###       ",
          "###       ",
          "###       ",
          "###       ",
          "          "],
    'D': ["#########   ",
          "########### ",
          "###     ### ",
          "###      ###",
          "###      ###",
          "###      ###",
          "###      ###",
          "###      ###",
          "###      ###",
          "###     ### ",
          "########### ",
          "#########   ",
          "            ",
          "            "],
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


def _style_letter(mask):
    """A styled (unsheared) glyph as an indexed array, fill+outline only on an
    margin canvas (shadow/slant applied later at composite time)."""
    h, w = mask.shape
    pad = 2
    canvas = np.zeros((h + 2 * pad, w + 2 * pad), dtype=np.uint8)
    ys, xs = np.where(mask)
    # outline: any empty cell 8-adjacent to ink
    for y in range(h):
        for x in range(w):
            if mask[y, x]:
                continue
            near = mask[max(0, y - 1):y + 2, max(0, x - 1):x + 2].any()
            if near:
                # darker on the bottom/right edges for a beveled read
                below_right = (y + 1 < h and mask[y + 1, x]) or \
                              (x - 1 >= 0 and mask[y, x - 1] and y > h // 2)
                canvas[y + pad, x + pad] = OUTLINE_DARK if below_right else OUTLINE
    # fill: row gradient
    for y, x in zip(ys, xs):
        canvas[y + pad, x + pad] = FILL_GRADIENT[y]
    return canvas


def compose(text):
    text = text.upper()
    letters = []
    for ch in text:
        if ch == ' ':
            letters.append(('space', None))
        else:
            if ch not in GLYPHS:
                sys.exit('ERROR: no gold glyph for %r -- add it to GLYPHS' % ch)
            letters.append((ch, _style_letter(_mask(ch))))
    # lay out unsheared, then shear the whole canvas
    total_w = 0
    for ch, g in letters:
        total_w += SPACE_W if ch == 'space' else g.shape[1] + LETTER_GAP
    H = CAP_H + 4
    shear = int(np.ceil(CAP_H * SLANT)) + 2
    flat = np.zeros((H, total_w + shear + 4), dtype=np.uint8)
    x = 0
    for ch, g in letters:
        if ch == 'space':
            x += SPACE_W
            continue
        gh, gw = g.shape
        region = flat[0:gh, x:x + gw]
        region[g != 0] = g[g != 0]
        x += gw + LETTER_GAP
    # italic shear: shift row y right by (CAP_H - y) * SLANT
    sheared = np.zeros_like(flat)
    for y in range(H):
        dx = int(round((CAP_H - y) * SLANT))
        if dx >= 0:
            sheared[y, dx:] = flat[y, :flat.shape[1] - dx] if dx else flat[y]
    # drop shadow: copy ink (fill+outline) down-right by (2,2) into empty cells
    shaded = sheared.copy()
    ink = sheared != 0
    sh, sw = sheared.shape
    for y in range(sh - 2):
        for x in range(sw - 2):
            if ink[y, x] and sheared[y + 2, x + 2] == 0:
                shaded[y + 2, x + 2] = SHADOW
    # crop to content width
    cols = np.where((shaded != 0).any(axis=0))[0]
    if len(cols):
        shaded = shaded[:, max(0, cols[0] - 1):cols[-1] + 2]
    im = Image.fromarray(shaded, mode='P')
    im.putpalette(Image.open(LOGO).getpalette())
    return im


SUB_FILL = 7        # logo-palette cream (255,255,213) -- light subtitle ink
SUB_OUTLINE = 14    # logo-palette dark red-brown (82,16,8) -- subtitle outline


def compose_logo(text='MANCHEGO STARS', subtitle=('RIME OF THE', 'FROSTMAIDEN'),
                 top=5, sub_top=34):
    """Full 256x64 drop-in replacement for title_fire_emblem_logo.png: `text` in
    gold at the top, the two-line `subtitle` (slab-serif, gen_subtitle) below it in
    cream with a dark outline. Both ride the vanilla logo palette so the sprite +
    .gbapal are unchanged (the old scroll banner is disabled separately). The faint
    vanilla lower-half subtitle is dropped."""
    import gen_subtitle
    base = Image.open(LOGO)
    word = np.array(compose(text))
    h, w = word.shape
    if w > VIS_W:
        sys.exit('ERROR: gold title is %dpx wide (>%d visible) -- tighten spacing or '
                 'narrow glyphs' % (w, VIS_W))
    canvas = np.zeros((64, 256), dtype=np.uint8)
    x = max(0, (VIS_W - w) // 2)   # centre within the on-screen window, not the canvas
    canvas[top:top + h, x:x + w] = word

    if subtitle:
        sub = np.array(gen_subtitle.compose_lines(list(subtitle)))  # 17=ink,255=bg
        ink = sub == 17
        sh, sw = ink.shape
        sx = max(0, (VIS_W - sw) // 2)
        # outline first (8-neighbour halo), then cream fill
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                ys, xs = np.where(ink)
                ny, nx = ys + dy + sub_top, xs + dx + sx
                ok = (ny >= 0) & (ny < 64) & (nx >= 0) & (nx < 256)
                canvas[ny[ok], nx[ok]] = np.where(canvas[ny[ok], nx[ok]] == 0,
                                                  SUB_OUTLINE, canvas[ny[ok], nx[ok]])
        ys, xs = np.where(ink)
        canvas[ys + sub_top, xs + sx] = SUB_FILL

    im = Image.fromarray(canvas)
    im.putpalette(base.getpalette())
    return im


def main():
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    text, out = sys.argv[1], sys.argv[2]
    im = compose(text)
    im.save(out)
    if len(sys.argv) == 4:
        w, h = im.size
        im.convert('RGB').resize((w * 6, h * 6), Image.NEAREST).save(sys.argv[3])
    print('wrote %s (%r, %dx%d)' % (out, text, *im.size))


if __name__ == '__main__':
    main()
