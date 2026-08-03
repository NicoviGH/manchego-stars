#!/usr/bin/env python3
"""Tests for handing generated battle-anim frames to the pixel editor and back (#206).

Detail finer than one shrink cell (Lupin's glasses) cannot be generated -- it is painted by
hand at final size. The frames ARE the deliverable once painted, so this module only moves
them: the numbered FEditor frames become one vertical sheet the editor can open, and the
saved sheet becomes the numbered frames again, indices untouched (it is the INDICES, not the
embedded colours, that gbagfx packs to 4bpp).

The hazard it guards is drift in the other direction: `poses_to_feditor` would happily
re-render over the paint. Once a manifest is marked hand-painted, regenerating has to be
deliberate.
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import banim_paint as bp  # noqa: E402
import poses_to_feditor as pf  # noqa: E402

PALETTE = [0, 255, 0] + [v for i in range(15) for v in (i * 16, i * 8, i * 4)]


def frame(w, h, blocks=()):
    im = Image.new("P", (w, h), 0)
    im.putpalette(PALETTE + [0] * (768 - len(PALETTE)))
    for x, y, i in blocks:
        im.putpixel((x, y), i)
    return im


class TestCropWindow(unittest.TestCase):
    """ONE window over every frame. The FEditor canvas is 248x160 and mostly empty -- the
    art is ~60x45 of it -- and the editor's per-row motion fit is O(canvas), so handing it
    the raw canvas costs half a minute of stall for a lot of empty green to paint on."""

    def test_the_window_covers_every_frames_art(self):
        a, b = frame(60, 40, [(10, 10, 3)]), frame(60, 40, [(50, 30, 3)])
        self.assertEqual(bp.crop_window([a, b], pad=0), (10, 10, 51, 31))

    def test_the_window_is_padded_so_paint_can_go_outside_the_silhouette(self):
        self.assertEqual(bp.crop_window([frame(60, 40, [(10, 10, 3)])], pad=2),
                         (8, 8, 13, 13))

    def test_the_window_is_clamped_to_the_canvas(self):
        self.assertEqual(bp.crop_window([frame(60, 40, [(0, 0, 3)])], pad=5), (0, 0, 6, 6))


class TestSheetRoundTrip(unittest.TestCase):
    """Frames -> one vertical strip the editor opens -> the same frames again."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.frames = [frame(24, 16, [(3, 4, 5)]), frame(24, 16, [(7, 9, 11)])]
        for i, f in enumerate(self.frames):
            f.save(os.path.join(self.dir, "Test_%03d.png" % i))
        self.win = bp.crop_window(self.frames, pad=2)

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_the_sheet_stacks_every_frame_at_window_size(self):
        w, h = self.win[2] - self.win[0], self.win[3] - self.win[1]
        self.assertEqual(bp.build_sheet(self.frames, self.win).size, (w, h * 2))

    def test_indices_survive_the_round_trip_unchanged(self):
        sheet = bp.build_sheet(self.frames, self.win)
        bp.write_frames(sheet, self.dir, "Test", 2, self.win)
        for i, original in enumerate(self.frames):
            back = Image.open(os.path.join(self.dir, "Test_%03d.png" % i))
            self.assertEqual(list(original.getdata()), list(back.getdata()))

    def test_the_sheet_keeps_the_frames_palette(self):
        """The editor writes back INDICES; the palette has to be the frames' own or the
        saved sheet would recolour the sprite on the way home."""
        self.assertEqual(bp.build_sheet(self.frames, self.win).getpalette()[:48],
                         self.frames[0].getpalette()[:48])

    def test_a_painted_pixel_lands_at_the_right_place_on_the_full_canvas(self):
        sheet = bp.build_sheet(self.frames, self.win)
        wh = self.win[3] - self.win[1]
        sheet.putpixel((1, wh + 1), 9)                # frame 1, window-local (1, 1)
        bp.write_frames(sheet, self.dir, "Test", 2, self.win)
        self.assertEqual(Image.open(os.path.join(self.dir, "Test_001.png"))
                         .getpixel((self.win[0] + 1, self.win[1] + 1)), 9)

    def test_pixels_outside_the_window_are_left_alone(self):
        outside = frame(24, 16, [(3, 4, 5), (23, 15, 6)])
        outside.save(os.path.join(self.dir, "Test_000.png"))
        sheet = bp.build_sheet(self.frames, self.win)
        bp.write_frames(sheet, self.dir, "Test", 2, self.win)
        self.assertEqual(Image.open(os.path.join(self.dir, "Test_000.png"))
                         .getpixel((23, 15)), 6)


class TestEditKeepsPaint(unittest.TestCase):
    """Re-opening the editor must not throw away what is already painted.

    The sheet is scratch built FROM the frames, so the naive `edit` rebuilds it every run --
    which silently discards a painting session that had not been `apply`d yet. Nearly cost a
    real one (2026-08-02): the frames were re-rendered mid-session for a palette change and
    only the saved sheet still held the glasses."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        for i in range(2):
            frame(24, 16, [(3, 4, 5)]).save(os.path.join(self.dir, "Test_%03d.png" % i))
        with open(os.path.join(self.dir, "poses.yaml"), "w", encoding="utf-8") as f:
            f.write("abbr: test\n")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_an_existing_sheet_of_the_right_shape_is_kept(self):
        sheet_path = bp.prepare_sheet(self.dir)
        painted = Image.open(sheet_path)
        painted.putpixel((0, 0), 9)
        painted.save(sheet_path)
        bp.prepare_sheet(self.dir)
        self.assertEqual(Image.open(sheet_path).getpixel((0, 0)), 9)

    def test_reset_rebuilds_the_sheet_from_the_frames(self):
        sheet_path = bp.prepare_sheet(self.dir)
        painted = Image.open(sheet_path)
        painted.putpixel((0, 0), 9)
        painted.save(sheet_path)
        bp.prepare_sheet(self.dir, reset=True)
        self.assertEqual(Image.open(sheet_path).getpixel((0, 0)), 0)

    def test_a_sheet_of_the_wrong_shape_is_rebuilt(self):
        """The window moved (the arc was retuned), so the old sheet no longer lines up."""
        sheet_path = bp.prepare_sheet(self.dir)
        Image.new("P", (8, 8), 3).save(sheet_path)
        bp.prepare_sheet(self.dir)
        self.assertNotEqual(Image.open(sheet_path).size, (8, 8))


class TestRegenerationGuard(unittest.TestCase):
    """A hand-painted manifest must not be silently re-rendered over."""

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        Image.new("RGBA", (40, 40), (150, 150, 150, 255)).save(
            os.path.join(self.dir, "idle.png"))
        self.spec = {
            "canvas": [60, 60], "home": [30, 30], "target_h": 20, "abbr": "test",
            "flip": False, "hand_painted": True,
            "poses": [{"name": "idle", "src": "idle.png", "dx": 0, "dy": 0}],
        }

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_writing_frames_over_a_hand_painted_manifest_is_refused(self):
        with self.assertRaises(SystemExit):
            pf.write_frames(self.spec, self.dir)

    def test_force_overrides_the_guard(self):
        with contextlib.redirect_stdout(io.StringIO()):     # keep the suite's output pristine
            pf.write_frames(self.spec, self.dir, force=True)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "Test_000.png")))

    def test_an_unpainted_manifest_writes_normally(self):
        del self.spec["hand_painted"]
        with contextlib.redirect_stdout(io.StringIO()):
            pf.write_frames(self.spec, self.dir)
        self.assertTrue(os.path.isfile(os.path.join(self.dir, "Test_000.png")))


if __name__ == "__main__":
    unittest.main()
