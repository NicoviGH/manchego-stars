#!/usr/bin/env python3
"""Tests for the pose-sheet splitter (#206): one generated sheet -> per-pose PNGs.

The generated battle-anim references arrive as ONE wide image holding every pose side by
side, each standing on a baked ground shadow the FE8 battle screen must not inherit (it
draws its own platform, and an airborne pose would tow a floating ellipse). The two pure
pieces here are the segmentation (where does one pose end and the next begin) and the
shadow key (drop the ellipse, keep fur that happens to be near its colour).
"""
import os
import sys
import unittest

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import split_pose_sheet as sp  # noqa: E402


def sheet(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def box(im, x0, y0, x1, y1, colour):
    """Fill [x0, x1) x [y0, y1) with an opaque colour."""
    px = im.load()
    for y in range(y0, y1):
        for x in range(x0, x1):
            px[x, y] = colour + (255,)


class TestPoseBoxes(unittest.TestCase):
    """Segment a sheet into one alpha bbox per pose, left to right."""

    def test_two_blobs_split_on_the_transparent_gutter(self):
        im = sheet(200, 60)
        box(im, 10, 10, 40, 50, (200, 200, 200))
        box(im, 120, 5, 170, 55, (200, 200, 200))
        self.assertEqual(sp.pose_boxes(im), [(10, 10, 40, 50), (120, 5, 170, 55)])

    def test_a_stray_speck_is_not_a_pose(self):
        """The sheet carries a 2x1 artifact between poses; it must not become a frame."""
        im = sheet(200, 60)
        box(im, 10, 10, 40, 50, (200, 200, 200))
        box(im, 70, 30, 72, 31, (200, 200, 200))     # the speck
        box(im, 120, 5, 170, 55, (200, 200, 200))
        self.assertEqual(sp.pose_boxes(im), [(10, 10, 40, 50), (120, 5, 170, 55)])

    def test_a_grid_sheet_reads_row_major(self):
        """The poses may be laid out as a grid, not a strip -- read them the way they are
        named: left to right, top row first."""
        im = sheet(200, 200)
        box(im, 10, 10, 40, 50, (200, 200, 200))      # top-left
        box(im, 120, 10, 170, 50, (200, 200, 200))    # top-right
        box(im, 10, 140, 40, 190, (200, 200, 200))    # bottom-left
        box(im, 120, 140, 170, 190, (200, 200, 200))  # bottom-right
        self.assertEqual(sp.pose_boxes(im),
                         [(10, 10, 40, 50), (120, 10, 170, 50),
                          (10, 140, 40, 190), (120, 140, 170, 190)])

    def test_poses_on_one_row_at_different_heights_stay_one_row(self):
        """A leaping pose sits higher on the sheet than a standing one; overlapping row
        spans are the SAME row, not two."""
        im = sheet(200, 100)
        box(im, 10, 30, 40, 90, (200, 200, 200))
        box(im, 120, 5, 170, 60, (200, 200, 200))
        self.assertEqual(sp.pose_boxes(im), [(10, 30, 40, 90), (120, 5, 170, 60)])

    def test_a_narrow_internal_break_keeps_one_pose_whole(self):
        """A raised paw leaves a few empty columns INSIDE a pose -- not a pose boundary."""
        im = sheet(200, 60)
        box(im, 10, 10, 40, 50, (200, 200, 200))
        box(im, 46, 10, 76, 50, (200, 200, 200))     # 6px internal gap, under `gap`
        self.assertEqual(sp.pose_boxes(im, gap=30), [(10, 10, 76, 50)])


class TestKeyShadow(unittest.TestCase):
    """Drop the baked ground shadow without eating the sprite."""

    TEAL = (48, 108, 108)

    def test_the_shadow_blob_becomes_transparent(self):
        im = sheet(60, 40)
        box(im, 5, 30, 55, 38, self.TEAL)
        out = sp.key_shadow(im, self.TEAL, feather=0)
        self.assertEqual(out.getpixel((30, 34))[3], 0)

    def test_sprite_pixels_near_the_shadow_colour_survive(self):
        """Fur shading lands within the SPREAD tolerance of the teal; it is not connected
        to a tight seed, so a reconstruction-based key leaves it alone (a flat colour key
        would eat it)."""
        im = sheet(60, 40)
        box(im, 5, 30, 55, 38, self.TEAL)            # the shadow
        box(im, 20, 4, 30, 14, (88, 96, 99))         # fur shading, ~40 away in RGB
        out = sp.key_shadow(im, self.TEAL, feather=0)
        self.assertEqual(out.getpixel((25, 9))[3], 255)

    def test_the_shadows_antialiased_fringe_goes_with_it(self):
        """One feather ring past the keyed blob. The fringe where the ellipse meets the
        transparent backdrop is washed FAR off-colour (outside the spread tolerance), so
        only the feather reaches it -- and a surviving teal halo would steal a slot from
        the 15-colour banim palette."""
        im = sheet(60, 40)
        box(im, 5, 30, 55, 38, self.TEAL)
        box(im, 5, 29, 55, 30, (150, 190, 190))      # the washed-out AA fringe
        self.assertEqual(sp.key_shadow(im, self.TEAL, feather=0).getpixel((30, 29))[3], 255)
        self.assertEqual(sp.key_shadow(im, self.TEAL, feather=1).getpixel((30, 29))[3], 0)

    def test_a_sheet_with_no_shadow_is_returned_unchanged(self):
        im = sheet(60, 40)
        box(im, 20, 4, 30, 14, (88, 96, 99))
        out = sp.key_shadow(im, self.TEAL, feather=2)
        self.assertEqual(out.getpixel((25, 9))[3], 255)


class TestSplitSheet(unittest.TestCase):
    """The whole job: sheet + names -> named, shadow-free, alpha-cropped poses."""

    TEAL = (48, 108, 108)

    def test_each_named_pose_is_cropped_tight_to_its_own_art(self):
        im = sheet(200, 60)
        box(im, 10, 10, 40, 50, (200, 200, 200))
        box(im, 120, 5, 170, 55, (200, 200, 200))
        out = sp.split_sheet(im, ["idle", "lunge"])
        self.assertEqual([n for n, _ in out], ["idle", "lunge"])
        self.assertEqual([p.size for _, p in out], [(30, 40), (50, 50)])

    def test_the_crop_is_taken_after_the_shadow_is_keyed(self):
        """The shadow sits BELOW the paws; keying first is what makes the crop the body."""
        im = sheet(120, 60)
        box(im, 10, 10, 40, 44, (200, 200, 200))     # the body: 34 tall
        box(im, 5, 46, 45, 54, self.TEAL)            # its shadow, lower still
        (_, pose), = sp.split_sheet(im, ["idle"], shadow=self.TEAL, feather=0)
        self.assertEqual(pose.size, (30, 34))

    def test_a_name_count_mismatch_is_rejected(self):
        im = sheet(200, 60)
        box(im, 10, 10, 40, 50, (200, 200, 200))
        box(im, 120, 5, 170, 55, (200, 200, 200))
        with self.assertRaises(ValueError):
            sp.split_sheet(im, ["idle"])


if __name__ == "__main__":
    unittest.main()
