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


class TestMergeObjects(unittest.TestCase):
    """Greedy merge of filled 8x8 cells into the largest legal GBA square OBJ.

    The naive tiler emits one 8x8 OBJ per filled cell (RBG@64x64 -> 47). The GBA can
    draw a 2x2 or 4x4 block of tiles as a SINGLE OBJ (16x16 / 32x32), so vanilla covers
    a battle sprite in ~16. merge_objects packs the filled cells into the fewest square
    OBJs, never covering an empty cell (that would draw a garbage tile).
    """

    def test_solid_4x4_block_becomes_one_32x32_object(self):
        filled = {(c, r) for c in range(4) for r in range(4)}  # full 4x4-cell grid
        objs = rb.merge_objects(filled, 4, 4)
        self.assertEqual(len(objs), 1)
        self.assertEqual(objs[0], {"cx": 0, "cy": 0, "w": 4, "h": 4})

    def test_solid_2x2_block_becomes_one_16x16_object(self):
        filled = {(c, r) for c in range(2) for r in range(2)}
        objs = rb.merge_objects(filled, 2, 2)
        self.assertEqual(len(objs), 1)
        self.assertEqual(objs[0], {"cx": 0, "cy": 0, "w": 2, "h": 2})

    def test_never_covers_an_empty_cell(self):
        # L-shape: 3 of a 2x2 block filled. No 16x16 fits (would cover the empty cell);
        # must fall back to three 8x8 objs covering exactly the filled cells.
        filled = {(0, 0), (1, 0), (0, 1)}
        objs = rb.merge_objects(filled, 2, 2)
        covered = {(o["cx"] + dx, o["cy"] + dy)
                   for o in objs for dx in range(o["w"]) for dy in range(o["h"])}
        self.assertEqual(covered, filled)            # exactly the filled cells, no more
        self.assertTrue(all(o["w"] == 1 and o["h"] == 1 for o in objs))

    def test_partitions_cover_all_filled_with_legal_square_sizes(self):
        # 4x4 solid plus one stray cell -> one 32x32 + one 8x8, covering all, no empties.
        filled = {(c, r) for c in range(4) for r in range(4)} | {(5, 0)}
        objs = rb.merge_objects(filled, 6, 4)
        covered = {(o["cx"] + dx, o["cy"] + dy)
                   for o in objs for dx in range(o["w"]) for dy in range(o["h"])}
        self.assertEqual(covered, filled)
        for o in objs:
            self.assertIn(o["w"], (1, 2, 4))         # legal GBA square cell-sizes
            self.assertEqual(o["w"], o["h"])
        self.assertLess(len(objs), len(filled))      # actually merged


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
