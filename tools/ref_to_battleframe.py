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
from PIL import Image

TILE = 8  # GBA OBJ tiles are 8x8


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
