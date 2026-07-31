"""map_sprite_swapper geometry + apply tests.

The swapper drives by-eye palette work on the real cast sheets, so the one thing that
must not drift is how it SLICES them: frames stack vertically, and the frame width is
the sheet width. A hardcoded 16 silently interleaved half-rows on the 32x32 monster
size class (Lupin's Lycanroc idle), which reads as garbage in the preview.
"""
import os
import shutil
import tempfile
import unittest

from PIL import Image

import map_sprite_swapper as sw

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MS = os.path.join(REPO, 'campaigns', 'rime-of-the-frostmaiden', 'map_sprites')


def _indexed(path, w, h, fill):
    im = Image.new('P', (w, h))
    im.putpalette([0, 0, 0] * 16)
    im.putdata(fill)
    im.save(path)


class SheetGeometry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='swapper_')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_32_wide_idle_slices_by_sheet_width(self):
        """A 32x96 idle is 3 frames of 32x32 -- each frame a contiguous 1024-px block."""
        p = os.path.join(self.tmp, 'idle32.png')
        _indexed(p, 32, 96, [i // 1024 for i in range(32 * 96)])
        s = sw._sheet(p, 32)
        self.assertEqual((s['w'], s['h'], s['n']), (32, 32, 3))
        for f, frame in enumerate(s['frames']):
            self.assertEqual(len(frame), 32 * 32)
            self.assertEqual(set(frame), {f}, 'frame %d interleaved rows from another frame' % f)

    def test_16_wide_idle_still_slices_at_16(self):
        """The 16-wide classes (Trex 16x16, Basil 16x32) are unaffected by the fix."""
        p = os.path.join(self.tmp, 'idle16.png')
        _indexed(p, 16, 96, [i // 256 for i in range(16 * 96)])
        s = sw._sheet(p, 16)
        self.assertEqual((s['w'], s['h'], s['n']), (16, 16, 6))
        self.assertEqual(set(s['frames'][3]), {3})

    def test_real_lupin_idle_is_three_32x32_frames(self):
        """Guards the live asset, not just a synthetic one."""
        s = sw._sheet(os.path.join(MS, 'lupin.png'), 32)
        self.assertEqual((s['w'], s['h'], s['n']), (32, 32, 3))


class Apply(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='swapper_')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_apply_remaps_indices_and_keeps_palette(self):
        idle = os.path.join(self.tmp, 'i.png')
        walk = os.path.join(self.tmp, 'w.png')
        _indexed(idle, 32, 32, [1] * 512 + [3] * 512)
        _indexed(walk, 32, 32, [1] * 1024)
        pal = os.path.join(self.tmp, 'pal.png')
        _indexed(pal, 16, 1, list(range(16)))
        before = Image.open(idle).getpalette()
        sw.Doc(idle, walk, pal, idle_fh=32).apply({'1': 11}, {})
        self.assertEqual(set(Image.open(idle).getdata()), {11, 3})
        self.assertEqual(set(Image.open(walk).getdata()), {1}, 'walk must be independent')
        self.assertEqual(Image.open(idle).getpalette(), before, 'palette must be untouched')


if __name__ == '__main__':
    unittest.main()
