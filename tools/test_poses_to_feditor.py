#!/usr/bin/env python3
"""Tests for the hi-res-poses -> FEditor-frames bridge (#90 import path).

Two behaviours are pinned here, both added for Lupin's wolf pounce (#206) and both OPT-IN
so the shipped Pinky frames stay byte-identical:

  * `outline: true` re-strokes the silhouette in the palette's ink after the shrink. The
    faked 3-pose path (descale_battleframe) has always done this -- an area-average
    downscale eats a drawn outline, and an FE8 battle sprite without one reads as a blob.
  * `sharpen:` pre-unsharps before the area shrink, the way `descale --sharpen` always has.
    It rescues edges only -- detail finer than one shrink cell is PAINTED at final size
    instead (tools/banim_paint.py), which is how Lupin gets his glasses.
"""
import os
import shutil
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import poses_to_feditor as pf  # noqa: E402


def pose_png(path, w, h, body=(150, 150, 150), mark=(20, 20, 20)):
    """A solid `body` block with a small dark `mark` (so the palette has a distinct ink)."""
    im = Image.new("RGBA", (w, h), body + (255,))
    for y in range(2, 6):
        for x in range(2, 6):
            im.putpixel((x, y), mark + (255,))
    im.save(path)


class PosesToFeditorCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        pose_png(os.path.join(self.dir, "idle.png"), 40, 40)
        self.spec = {
            "canvas": [60, 60], "home": [30, 30], "target_h": 20, "abbr": "test",
            "flip": False,
            "poses": [{"name": "idle", "src": "idle.png", "dx": 0, "dy": 0}],
        }

    def tearDown(self):
        shutil.rmtree(self.dir)

    def rgb(self, canvas, xy):
        pal = canvas.getpalette()
        i = canvas.getpixel(xy)
        return tuple(pal[i * 3:i * 3 + 3])


class TestOutline(PosesToFeditorCase):
    def test_no_outline_by_default(self):
        """Pinky shipped without one; the default must not repaint his frames."""
        (_, canvas), = pf.build_frames(self.spec, self.dir)
        self.assertEqual(canvas.getpixel((19, 30)), 0)   # 1px outside the 20x20 body

    def test_outline_strokes_the_silhouette_in_the_darkest_tone(self):
        self.spec["outline"] = True
        (_, canvas), = pf.build_frames(self.spec, self.dir)
        self.assertNotEqual(canvas.getpixel((19, 30)), 0)
        self.assertEqual(self.rgb(canvas, (19, 30)), self.rgb(canvas, (21, 21)))

    def test_the_outline_does_not_repaint_the_body(self):
        self.spec["outline"] = True
        (_, canvas), = pf.build_frames(self.spec, self.dir)
        self.assertNotEqual(self.rgb(canvas, (30, 30)), self.rgb(canvas, (19, 30)))


class TestSharpen(PosesToFeditorCase):
    """The faked 3-pose path pre-sharpens before the area shrink (`descale --sharpen`, 1.6-2.0
    on the big units); the import path never did, so fine dark detail -- a face, a pair of
    glasses -- averaged into the body colour on the way down."""

    def darkest(self, canvas):
        pal, used = canvas.getpalette(), {i for i in canvas.getdata() if i}
        return min(0.299 * pal[i * 3] + 0.587 * pal[i * 3 + 1] + 0.114 * pal[i * 3 + 2]
                   for i in used)

    def setUp(self):
        super().setUp()
        # A dark mark exactly one shrink-cell wide (40 -> 10 is 4:1) on a light body. Measured
        # caveat worth knowing before reaching for --sharpen: detail SMALLER than the cell is
        # made slightly WORSE, because the unsharp halo brightens the neighbours the box filter
        # then averages in. Sharpening rescues edges, it does not rescue sub-pixel features.
        im = Image.new("RGBA", (40, 40), (150, 150, 150, 255))
        for y in range(20, 24):
            for x in range(20, 24):
                im.putpixel((x, y), (20, 20, 20, 255))
        im.save(os.path.join(self.dir, "idle.png"))
        self.spec["target_h"] = 10

    def test_sharpen_keeps_cell_sized_dark_detail_darker_through_the_shrink(self):
        plain, = pf.build_frames(self.spec, self.dir)
        self.spec["sharpen"] = 2.0
        sharp, = pf.build_frames(self.spec, self.dir)
        self.assertLess(self.darkest(sharp[1]), self.darkest(plain[1]))

    def test_no_sharpen_by_default(self):
        """Pinky shipped unsharpened; the default must not repaint his frames."""
        plain, = pf.build_frames(self.spec, self.dir)
        self.spec["sharpen"] = 0
        self.assertEqual(list(pf.build_frames(self.spec, self.dir)[0][1].getdata()),
                         list(plain[1].getdata()))


class TestReserve(PosesToFeditorCase):
    """`reserve:` forces a colour into the <=15-colour palette even though no source pixel
    is that colour -- the same seam `descale --reserve` opened for Rootis's carrot nose.
    Here it is what gives the hand-painter a true white to draw a lens with (the wolf's
    own lightest tone is an off-white ~185)."""

    def test_a_reserved_colour_is_in_the_frames_palette(self):
        self.spec["reserve"] = [[255, 255, 255]]
        (_, canvas), = pf.build_frames(self.spec, self.dir)
        entries = [tuple(canvas.getpalette()[i * 3:i * 3 + 3]) for i in range(16)]
        self.assertIn((255, 255, 255), entries)

    def test_nothing_is_reserved_by_default(self):
        (_, canvas), = pf.build_frames(self.spec, self.dir)
        entries = [tuple(canvas.getpalette()[i * 3:i * 3 + 3]) for i in range(16)]
        self.assertNotIn((255, 255, 255), entries)


if __name__ == "__main__":
    unittest.main()
