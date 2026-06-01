#!/usr/bin/env python3
"""FE8 portrait <-> decomp tile-sheet converter.

A vanilla FE8 talking portrait is drawn as 6 hardware sprite (OAM) objects that
carve rectangular tile regions out of a 32-tile-wide VRAM sheet (the tracked
`graphics/portrait/portrait_<Name>_tileset.png`, 256x32, indexed 16-color) and
composite them into the on-screen 96x80 bust. The arrangement is the engine's
`gSprite_Face96x96[]` (see fireemblem8u/src/face.c).

This tool converts between the two representations so we can AUTHOR a portrait as
a plain 96x80 indexed bust and mechanically produce the decomp's sheet PNG that
gbagfx + the build expect.

  decode  sheet.png  -> bust 96x80   (for inspecting vanilla art)
  encode  bust.png   -> sheet 256x32 (for inserting custom art)

Constraints (hard FE8 ceilings, enforced here):
  * indexed PNG, exactly <=16 colors; index 0 = transparent (the bust background)
  * bust is 96x80; sheet is 256x32 (32x4 tiles of 8x8)

The 6 objects of gSprite_Face96x96 (w,h, screen x,y relative to a centered
origin, CHR tile-index into the 32-wide grid). Screen x is normalized by +48 so
the bust origin is (0,0).
"""

import sys
from PIL import Image

# (w_px, h_px, screen_x, screen_y, chr_tile_index) -- from src/face.c gSprite_Face96x96
OBJECTS = [
    (64, 32, -32,  0, 0x00),
    (64, 32, -32, 32, 0x08),
    (32, 16, -32, 64, 0x10),
    (32, 16,   0, 64, 0x50),
    (16, 32, -48, 48, 0x14),
    (16, 32,  32, 48, 0x16),
]
X_ORIGIN = 48          # normalize screen x so leftmost object lands at bust x=0
SHEET_W, SHEET_H = 256, 32
BUST_W, BUST_H = 96, 80
GRID_W = SHEET_W // 8  # 32 tiles wide


def _iter_tiles(w, h, chr_idx):
    """Yield (tile_col_in_obj, tile_row_in_obj, sheet_px_x, sheet_px_y)."""
    tw, th = w // 8, h // 8
    col0, row0 = chr_idx % GRID_W, chr_idx // GRID_W
    for j in range(th):
        for i in range(tw):
            yield i, j, (col0 + i) * 8, (row0 + j) * 8


def decode(sheet):
    """32-wide tile sheet -> 96x80 bust (palette preserved)."""
    bust = Image.new('P', (BUST_W, BUST_H), 0)
    if sheet.palette:
        bust.putpalette(sheet.getpalette())
    for w, h, x, y, chr_idx in OBJECTS:
        for i, j, sx, sy in _iter_tiles(w, h, chr_idx):
            tile = sheet.crop((sx, sy, sx + 8, sy + 8))
            bust.paste(tile, (x + X_ORIGIN + i * 8, y + j * 8))
    return bust


def encode(bust):
    """96x80 bust -> 32-wide tile sheet (inverse of decode)."""
    sheet = Image.new('P', (SHEET_W, SHEET_H), 0)
    if bust.palette:
        sheet.putpalette(bust.getpalette())
    for w, h, x, y, chr_idx in OBJECTS:
        for i, j, sx, sy in _iter_tiles(w, h, chr_idx):
            bx, by = x + X_ORIGIN + i * 8, y + j * 8
            tile = bust.crop((bx, by, bx + 8, by + 8))
            sheet.paste(tile, (sx, sy))
    return sheet


def _check_indexed(im, path):
    if im.mode != 'P':
        sys.exit('ERROR: %s is mode %s; must be indexed (P) 16-color' % (path, im.mode))
    used = {p for p in im.getdata()}
    if max(used) > 15:
        sys.exit('ERROR: %s uses palette index >15 (found %d); FE8 ceiling is 16'
                 % (path, max(used)))


def main():
    if len(sys.argv) != 4 or sys.argv[1] not in ('decode', 'encode'):
        sys.exit('usage: portrait_tool.py {decode|encode} <in.png> <out.png>')
    op, inp, outp = sys.argv[1:]
    im = Image.open(inp)
    _check_indexed(im, inp)
    if op == 'decode':
        if im.size != (SHEET_W, SHEET_H):
            sys.exit('ERROR: decode expects a %dx%d sheet, got %s' % (SHEET_W, SHEET_H, im.size))
        out = decode(im)
    else:
        if im.size != (BUST_W, BUST_H):
            sys.exit('ERROR: encode expects a %dx%d bust, got %s' % (BUST_W, BUST_H, im.size))
        out = encode(im)
    out.save(outp)
    print('%s -> %s (%s)' % (inp, outp, op))


if __name__ == '__main__':
    main()
