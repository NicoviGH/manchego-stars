#!/usr/bin/env python3
"""Tests for the battle-frame conversion (#65 M-A): static sprite -> FE8 banim assets.

The pure core here is the TILER: cut a transparent sprite into the 8x8 tiles a GBA OBJ
sheet is built from, and emit one OAM entry per non-empty cell (tile index + pixel
offset). Fully-transparent cells carry no hardware sprite, so they're skipped. Everything
in this file runs with no emulator (in `make test`). Format grounding: data/banim/*.s
(banim_frame_oam tile,x,y) + the decomp's banim build (graphics/banim/*_sheet_*.4bpp).
"""
import os
import sys
import unittest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ref_to_battleframe as rb  # noqa: E402


def blank(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


class TestTiler(unittest.TestCase):
    def test_skips_fully_transparent_cells_and_places_the_filled_one(self):
        # 16x16 = a 2x2 grid of 8x8 cells; fill only the bottom-right cell.
        im = blank(16, 16)
        for y in range(8, 16):
            for x in range(8, 16):
                im.putpixel((x, y), (0, 200, 0, 255))
        tiles, oam = rb.tile_sprite(im)
        self.assertEqual(len(tiles), 1)          # only the one non-empty 8x8 tile
        self.assertEqual(len(oam), 1)
        self.assertEqual(oam[0]["tile"], 0)      # first emitted tile
        self.assertEqual((oam[0]["dx"], oam[0]["dy"]), (8, 8))  # its cell's top-left

    def test_emits_one_tile_and_oam_entry_per_filled_cell(self):
        # fill the top-left and bottom-right cells with DISTINCT content -> 2 tiles
        im = blank(16, 16)
        for (ox, oy, col) in [(0, 0, (200, 0, 0, 255)), (8, 8, (0, 0, 200, 255))]:
            for y in range(oy, oy + 8):
                for x in range(ox, ox + 8):
                    im.putpixel((x, y), col)
        tiles, oam = rb.tile_sprite(im)
        self.assertEqual(len(tiles), 2)
        self.assertEqual({(o["dx"], o["dy"]) for o in oam}, {(0, 0), (8, 8)})
        self.assertEqual(sorted(o["tile"] for o in oam), [0, 1])

    def test_identical_cells_share_one_tile(self):
        # two cells with byte-identical content -> ONE sheet tile, two OAM entries on it
        im = blank(16, 8)
        for (ox, _) in [(0, 0), (8, 0)]:
            for y in range(0, 8):
                for x in range(ox, ox + 8):
                    im.putpixel((x, y), (10, 20, 30, 255))
        tiles, oam = rb.tile_sprite(im)
        self.assertEqual(len(tiles), 1)              # deduped
        self.assertEqual(len(oam), 2)                # both cells still drawn
        self.assertEqual([o["tile"] for o in oam], [0, 0])


if __name__ == "__main__":
    unittest.main()
