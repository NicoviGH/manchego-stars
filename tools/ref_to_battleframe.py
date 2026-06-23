#!/usr/bin/env python3
"""Battle-frame conversion (#65 Milestone A): a static sprite -> FE8 banim assets.

Sibling of ref_to_bust.py: where that turns a reference into an FE8 portrait, this turns
1-3 transparent static frames into a faked battle animation -- 4bpp tile sheet(s) + OAM
frame layouts + palette + a motion script (timing/effects cloned from a donor class). No
hand-drawn motion frames; the engine's projectile/hit effects sell the action (epic #65).

This module is built bottom-up, TDD'd in test_ref_to_battleframe.py (in `make test`):
  * tile_sprite -- cut a sprite into the 8x8 OBJ tiles a GBA sheet is built from, emitting
    one OAM entry per non-empty cell. (further stages added as TDD proceeds)
"""
import struct

from PIL import Image

TILE = 8  # GBA OBJ tiles are 8x8
SQUARE_SIZES = (4, 2, 1)  # legal GBA square OBJ side, in 8x8 cells (32x32 / 16x16 / 8x8)
PAL_BANK = 16     # colours per GBA 4bpp sub-palette
PAL_BANKS = 4     # a banim .agbpal holds 4 sub-palettes (64 BGR555 hwords, 128 bytes)


def _bgr555(rgb):
    """Pack an 8-bit (r, g, b) into a GBA BGR555 hword."""
    r, g, b = rgb
    return ((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3)


def agbpal_bytes(palette):
    """A <=16-colour palette -> the 128-byte .agbpal the banim build links.

    Encodes the colours as BGR555, pads the bank to 16 entries with 0, and mirrors that
    one 16-colour bank across all 4 sub-palettes (our OAM only references palbank 0; the
    other banks are kept sane in case the engine touches them).
    """
    bank = [_bgr555(c) for c in palette[:PAL_BANK]]
    bank += [0] * (PAL_BANK - len(bank))
    return struct.pack("<%dH" % (PAL_BANK * PAL_BANKS), *(bank * PAL_BANKS))


def merge_objects(filled, cols, rows):
    """Pack the filled 8x8 cells into the fewest legal square GBA OBJs.

    `filled` is a set of (cx, cy) cell coords; `cols`/`rows` bound the grid. Returns a
    list of {cx, cy, w, h} placements (w==h, in cells) covering EXACTLY the filled cells.
    A larger OBJ is placed only when every cell it spans is filled -- so a merged OBJ
    never draws a transparent/garbage tile, the way one 16x16 over an L-shape would.

    Greedy, row-major, largest-first: 47 stray 8x8 cells collapse to ~16 when the sprite
    body has solid 2x2/4x4 blocks; irregular edges stay 8x8.
    """
    remaining = set(filled)
    objs = []
    for cy in range(rows):
        for cx in range(cols):
            if (cx, cy) not in remaining:
                continue
            for s in SQUARE_SIZES:
                if cx + s > cols or cy + s > rows:
                    continue
                block = {(cx + dx, cy + dy) for dx in range(s) for dy in range(s)}
                if block <= remaining:
                    objs.append({"cx": cx, "cy": cy, "w": s, "h": s})
                    remaining -= block
                    break
    return objs


def build_sheet_png(tiles, palette, tiles_per_row=32):
    """Lay deduped 8x8 `tiles` row-major into an indexed (mode "P") sheet PNG.

    Every pixel becomes an index into `palette` (<=16 (r,g,b) colours); a transparent
    pixel (alpha 0) maps to index 0, the FE backdrop convention. gbagfx turns the PNG
    into the linked .4bpp at build time (`%.4bpp: %.png`).
    """
    rows = (len(tiles) + tiles_per_row - 1) // tiles_per_row
    w, h = tiles_per_row * TILE, max(rows, 1) * TILE
    lut = {c: i for i, c in enumerate(palette[:PAL_BANK])}
    sheet = Image.new("P", (w, h), 0)
    flat = []
    for c in palette[:PAL_BANK]:
        flat += list(c)
    flat += [0] * (3 * PAL_BANK - len(flat))
    sheet.putpalette(flat)
    for ti, tile in enumerate(tiles):
        ox, oy = (ti % tiles_per_row) * TILE, (ti // tiles_per_row) * TILE
        px = tile.load()
        for y in range(TILE):
            for x in range(TILE):
                r, g, b, a = px[x, y]
                sheet.putpixel((ox + x, oy + y), 0 if a == 0 else lut.get((r, g, b), 0))
    return sheet


def _cell_is_empty(im, ox, oy):
    """True if the 8x8 cell at (ox, oy) is fully transparent."""
    for y in range(oy, oy + TILE):
        for x in range(ox, ox + TILE):
            if im.getpixel((x, y))[3] != 0:
                return False
    return True


def tile_sprite(im):
    """Cut `im` (RGBA) into 8x8 tiles, returning (tiles, oam).

    `tiles` is the list of non-empty 8x8 tile images in emission (row-major) order.
    `oam` is a parallel list of {tile, dx, dy}: the tile's index and the top-left pixel
    offset of its cell in `im`. Fully-transparent cells carry no hardware sprite and are
    skipped (no tile, no OAM entry) -- that's what keeps a sparse sprite cheap.
    """
    w, h = im.size
    tiles, oam = [], []
    index = {}  # tile bytes -> sheet index, so identical cells share one tile
    for oy in range(0, h, TILE):
        for ox in range(0, w, TILE):
            if _cell_is_empty(im, ox, oy):
                continue
            cell = im.crop((ox, oy, ox + TILE, oy + TILE))
            key = cell.tobytes()
            idx = index.get(key)
            if idx is None:
                idx = len(tiles)
                index[key] = idx
                tiles.append(cell)
            oam.append({"tile": idx, "dx": ox, "dy": oy})
    return tiles, oam
