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

  decode   sheet.png  -> bust 96x80              (for inspecting vanilla art)
  encode   bust.png   -> sheet 256x32            (for inserting custom art)
  generate bust.png <base>                       (produce all 4 decomp assets)
           --xmouth N  tile-column mouth offset  (default 2, range 0-6)
           --ymouth N  tile-row mouth offset     (default 6, range 0-9)

generate produces:
  <base>_tileset.png    256x32 tile sheet (mouth region blanked)
  <base>_mouth.png      32x96 mouth animation (6 identical static frames)
  <base>_chibi.png      32x32 map/UI thumbnail (face region scaled down)
  <base>_palette.agbpal 32-byte GBA RGB555 palette (direct .incbin target)

Constraints (hard FE8 ceilings, enforced here):
  * indexed PNG, exactly <=16 colors; index 0 = transparent (the bust background)
  * bust is 96x80; sheet is 256x32 (32x4 tiles of 8x8)
  * mouth.png is 32x96 (6 frames of 32x16, stacked)
  * chibi.png is 32x32

The 6 objects of gSprite_Face96x96 (w,h, screen x,y relative to a centered
origin, CHR tile-index into the 32-wide grid). Screen x is normalized by +48 so
the bust origin is (0,0).

Mouth positioning (derived from face.c OAM math):
  bust_x = (xmouth - 4) * 8 + 32   e.g. xmouth=2 -> bust_x=16
  bust_y = ymouth * 8               e.g. ymouth=6 -> bust_y=48
  The 32x16 mouth region is extracted from the bust at (bust_x, bust_y),
  blanked in the tileset, and used as all 6 mouth frames.
"""

import struct
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
MOUTH_W, MOUTH_H = 32, 16
MOUTH_FRAMES = 6
CHIBI_W, CHIBI_H = 32, 32
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


def _palette_to_agbpal(pal_rgb):
    """Convert PIL flat palette [R,G,B,...] (16 colors) -> 32-byte GBA RGB555 binary."""
    colors = []
    for i in range(16):
        r, g, b = pal_rgb[i * 3], pal_rgb[i * 3 + 1], pal_rgb[i * 3 + 2]
        colors.append((r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10))
    return struct.pack('<16H', *colors)


def _nearest_pal_idx(r, g, b, a, pal_rgb, n=16):
    """Return the palette index (0..n-1) nearest to the given RGBA pixel."""
    if a < 128:
        return 0
    best_i, best_d = 0, float('inf')
    for i in range(n):
        pr, pg, pb = pal_rgb[i * 3], pal_rgb[i * 3 + 1], pal_rgb[i * 3 + 2]
        d = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
        if d < best_d:
            best_d, best_i = d, i
    return best_i


def _make_chibi(bust):
    """96x80 bust -> 32x32 chibi using bust palette (face-region crop + nearest-neighbor)."""
    rgba = bust.convert('RGBA')
    # Center on face: take the horizontal center, upper 2/3 of the bust
    cx = BUST_W // 2
    crop = 64
    x0, y0 = cx - crop // 2, 4
    face = rgba.crop((x0, y0, x0 + crop, y0 + crop))
    face = face.resize((CHIBI_W, CHIBI_H), Image.NEAREST)

    pal = bust.getpalette()
    chibi = Image.new('P', (CHIBI_W, CHIBI_H), 0)
    chibi.putpalette(pal)
    chibi.putdata([_nearest_pal_idx(r, g, b, a, pal) for r, g, b, a in face.getdata()])
    return chibi


def generate(bust, xmouth=2, ymouth=6):
    """Derive all four decomp portrait assets from a 96x80 indexed bust.

    Returns (tileset_png, mouth_png, chibi_png, palette_bytes) where:
      tileset_png  — 256x32 tile sheet with mouth region blanked (index 0)
      mouth_png    — 32x96 indexed PNG (6 identical 32x16 frames)
      chibi_png    — 32x32 indexed PNG
      palette_bytes — 32-byte GBA RGB555 blob (.agbpal)
    """
    mouth_bx = (xmouth - 4) * 8 + 32   # bust x of the 32x16 mouth window
    mouth_by = ymouth * 8               # bust y of the 32x16 mouth window

    # --- palette ---
    pal_rgb = bust.getpalette()[:48]    # first 16 colors, 3 bytes each
    palette_bytes = _palette_to_agbpal(pal_rgb)

    # --- mouth: extract 32x16 region from bust, then blank it ---
    mouth_frame = bust.crop((mouth_bx, mouth_by,
                             mouth_bx + MOUTH_W, mouth_by + MOUTH_H))

    mod_bust = bust.copy()
    px = list(mod_bust.getdata())
    for row in range(mouth_by, mouth_by + MOUTH_H):
        for col in range(mouth_bx, mouth_bx + MOUTH_W):
            px[row * BUST_W + col] = 0
    mod_bust.putdata(px)

    mouth_png = Image.new('P', (MOUTH_W, MOUTH_H * MOUTH_FRAMES), 0)
    mouth_png.putpalette(bust.getpalette())
    for i in range(MOUTH_FRAMES):
        mouth_png.paste(mouth_frame, (0, i * MOUTH_H))

    # --- tileset: encode the modified bust ---
    tileset_png = encode(mod_bust)

    # --- chibi ---
    chibi_png = _make_chibi(bust)

    return tileset_png, mouth_png, chibi_png, palette_bytes


def _check_indexed(im, path):
    if im.mode != 'P':
        sys.exit('ERROR: %s is mode %s; must be indexed (P) 16-color' % (path, im.mode))
    used = {p for p in im.getdata()}
    if max(used) > 15:
        sys.exit('ERROR: %s uses palette index >15 (found %d); FE8 ceiling is 16'
                 % (path, max(used)))


def main():
    import argparse
    if len(sys.argv) < 2 or sys.argv[1] not in ('decode', 'encode', 'generate'):
        sys.exit('usage:\n'
                 '  portrait_tool.py decode  <sheet.png>  <bust.png>\n'
                 '  portrait_tool.py encode  <bust.png>   <sheet.png>\n'
                 '  portrait_tool.py generate <bust.png>  <out_base> [--xmouth N] [--ymouth N]')

    op = sys.argv[1]

    if op in ('decode', 'encode'):
        if len(sys.argv) != 4:
            sys.exit('usage: portrait_tool.py %s <in.png> <out.png>' % op)
        inp, outp = sys.argv[2], sys.argv[3]
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

    else:  # generate
        parser = argparse.ArgumentParser(prog='portrait_tool.py generate')
        parser.add_argument('bust')
        parser.add_argument('out_base')
        parser.add_argument('--xmouth', type=int, default=2,
                            help='mouth tile-column offset (default 2)')
        parser.add_argument('--ymouth', type=int, default=6,
                            help='mouth tile-row offset (default 6)')
        args = parser.parse_args(sys.argv[2:])

        im = Image.open(args.bust)
        _check_indexed(im, args.bust)
        if im.size != (BUST_W, BUST_H):
            sys.exit('ERROR: generate expects a %dx%d bust, got %s' % (BUST_W, BUST_H, im.size))

        tileset, mouth, chibi, pal_bytes = generate(im, args.xmouth, args.ymouth)

        tileset_path = args.out_base + '_tileset.png'
        mouth_path   = args.out_base + '_mouth.png'
        chibi_path   = args.out_base + '_chibi.png'
        pal_path     = args.out_base + '_palette.agbpal'

        tileset.save(tileset_path)
        mouth.save(mouth_path)
        chibi.save(chibi_path)
        with open(pal_path, 'wb') as f:
            f.write(pal_bytes)

        print('generated from %s (xmouth=%d, ymouth=%d):' % (args.bust, args.xmouth, args.ymouth))
        print('  %s  (%dx%d tileset)' % (tileset_path, SHEET_W, SHEET_H))
        print('  %s  (%dx%d mouth, %d frames)' % (mouth_path, MOUTH_W, MOUTH_H * MOUTH_FRAMES, MOUTH_FRAMES))
        print('  %s  (%dx%d chibi)' % (chibi_path, CHIBI_W, CHIBI_H))
        print('  %s  (%d bytes palette)' % (pal_path, len(pal_bytes)))


if __name__ == '__main__':
    main()
