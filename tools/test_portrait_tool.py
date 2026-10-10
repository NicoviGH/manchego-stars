#!/usr/bin/env python3
"""Tests for portrait_tool's model of how FE8 draws a bust (#471).

Run:  python3 tools/test_portrait_tool.py
"""
import os
import sys
import unittest

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portrait_tool as pt  # noqa: E402


def _full_bust():
    """A bust that paints every pixel, each 8x8 tile its own non-zero colour pattern."""
    bust = Image.new('P', (pt.BUST_W, pt.BUST_H), 0)
    bust.putpalette([i * 16 for i in range(16) for _ in range(3)])
    bust.putdata([1 + (x // 8 + y // 8 + x % 3) % 15
                  for y in range(pt.BUST_H) for x in range(pt.BUST_W)])
    return bust


def _sheet_tiles(objects):
    tiles = set()
    for w, h, _x, _y, chr_idx in objects:
        for i in range(w // 8):
            for j in range(h // 8):
                tiles.add(chr_idx + i + j * pt.GRID_W)
    return tiles


class TheCorners(unittest.TestCase):
    def test_with_corners_the_whole_bust_round_trips(self):
        bust = _full_bust()
        self.assertEqual(list(bust.getdata()),
                         list(pt.decode(pt.encode(bust, corners=True), corners=True).getdata()))

    def test_without_them_exactly_the_two_16x48_strips_drop(self):
        bust = _full_bust()
        ships = pt.decode(pt.encode(bust))
        dropped = [b != s for b, s in zip(bust.getdata(), ships.getdata())]
        expect = [(x < 16 or x >= 80) and y < 48
                  for y in range(pt.BUST_H) for x in range(pt.BUST_W)]
        self.assertEqual(expect, dropped)

    def test_corner_tiles_are_free_of_the_face_and_the_mouth_target(self):
        # sub_8005FE0 writes the talking mouth into 0x1C-0x1F / 0x3C-0x3F every frame, and
        # PutFace80x72_Standard reads it from there.
        corners = _sheet_tiles(pt.CORNER_OBJECTS)
        self.assertEqual(24, len(corners))
        self.assertFalse(corners & _sheet_tiles(pt.OBJECTS))
        self.assertFalse(corners & {0x1C, 0x1D, 0x1E, 0x1F, 0x3C, 0x3D, 0x3E, 0x3F})

    def test_a_static_sheet_carries_them_and_keeps_its_baked_mouth(self):
        bust = _full_bust()
        tileset, _mouth, _chibi, _pal = pt.generate(bust, static_portrait=True)
        self.assertEqual(list(bust.getdata()),
                         list(pt.decode(tileset, corners=True).getdata()))
        neutral_mouth = bust.crop((16, 48, 48, 64))
        self.assertEqual(list(neutral_mouth.getdata()),
                         list(tileset.crop((224, 0, 256, 16)).getdata()))

    def test_an_animated_sheet_leaves_the_eye_frame_tiles_alone(self):
        tileset, _mouth, _chibi, _pal = pt.generate(_full_bust())
        self.assertEqual({0}, set(tileset.crop((192, 0, 224, 32)).getdata()))


if __name__ == '__main__':
    unittest.main()
