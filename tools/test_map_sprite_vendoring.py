#!/usr/bin/env python3
"""Vendoring a COMMUNITY map sprite onto the cast palette (#25).

The repo's own sheets (and every vanilla donor `recolour` was written against) mark
transparency with palette index 0. FE-Repo community sheets do not: they ship on a green
key, `#80a080`, and their index 0 is an ordinary colour. Converting one as though index 0
were transparent turns the BACKDROP into a real cast colour, and the result passes every
existing check -- geometry fine, colour count fine, preview fine -- then renders in game as
a solid 16x16 block with the sprite inside it.

That is what happened vendoring Ravisin's `Druid Hoodless (F)`: its index 0 is a cream
used by 12 pixels and its background is index 5, 253 pixels of green. So the key is
detected rather than assumed, and a finished sheet with NO transparent pixel is rejected.
"""
import os
import shutil
import tempfile
import unittest

from PIL import Image

import map_sprite_tool as mst

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MS = os.path.join(REPO, 'campaigns', 'rime-of-the-frostmaiden', 'map_sprites')


def _sheet(path, pal, data, size):
    im = Image.new('P', size)
    im.putpalette(pal)
    im.putdata(data)
    im.save(path)


class TransparencyKey(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='vendor_')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _green_key_donor(self):
        """A community-style sheet: index 0 a real colour, background the green key."""
        p = os.path.join(self.tmp, 'donor.png')
        pal = [0, 0, 0] * 16
        pal[0:3] = [0xf8, 0xf8, 0xd0]        # index 0: an ORDINARY colour, not transparency
        pal[3:6] = [0x40, 0x38, 0x38]        # index 1: the sprite's dark
        pal[6:9] = [0x80, 0xa0, 0x80]        # index 2: THE GREEN KEY (the backdrop)
        # 16x48 = the 3 frames the engine reads: a 2x2 blob in a field of key, plus one
        # index-0 pixel per frame (the "ordinary colour at index 0" this test is about).
        frame = [2] * 256
        frame[0] = 0                         # the cream pixel, in the corner
        for i in (100, 101, 116, 117):
            frame[i] = 1
        _sheet(p, pal, frame * 3, (16, 48))
        return p

    def test_the_green_key_becomes_transparent_not_a_cast_colour(self):
        d = self._green_key_donor()
        out = os.path.join(self.tmp, 'out.png')
        mst.recolour(d, os.path.join(MS, 'cast_palette.png'), out)
        got = list(Image.open(out).getdata())
        self.assertEqual(got[100], got[101])
        self.assertNotEqual(got[100], 0, 'the sprite body must NOT be transparent')
        self.assertEqual(got[1], 0, 'the green key must map to index 0')
        self.assertGreater(sum(1 for v in got if v == 0), 200)

    def test_index_zero_is_not_assumed_transparent_when_a_key_is_present(self):
        """The donor's index 0 is a real cream colour here; it must survive as a colour."""
        d = self._green_key_donor()
        out = os.path.join(self.tmp, 'out.png')
        mst.recolour(d, os.path.join(MS, 'cast_palette.png'), out)
        self.assertNotEqual(list(Image.open(out).getdata())[0], 0)

    def test_a_decomp_style_sheet_still_treats_index_0_as_transparent(self):
        """No regression for the vanilla donors recolour was written for: no green key,
        so index 0 keeps its old meaning."""
        p = os.path.join(self.tmp, 'vanilla.png')
        pal = [0, 0, 0] * 16
        pal[3:6] = [0x40, 0x38, 0x38]
        frame = [0] * 256
        for i in (100, 101):
            frame[i] = 1
        _sheet(p, pal, frame * 3, (16, 48))
        out = os.path.join(self.tmp, 'out.png')
        mst.recolour(p, os.path.join(MS, 'cast_palette.png'), out)
        got = list(Image.open(out).getdata())
        self.assertEqual(got[0], 0)
        self.assertNotEqual(got[100], 0)


class OpaqueSheetIsRejected(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='vendor_')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_sheet_with_no_transparent_pixel_fails(self):
        """Always wrong, and invisible to every other check -- it renders as a block."""
        p = os.path.join(self.tmp, 'opaque.png')
        _sheet(p, [0, 0, 0] * 16, [3] * (16 * 48), (16, 48))
        with self.assertRaises(SystemExit):
            mst.sheet_info(p, (16, 16))

    def test_a_normal_sheet_passes(self):
        p = os.path.join(self.tmp, 'ok.png')
        data = [0] * (16 * 48)
        for i in range(100, 140):
            data[i] = 3
        _sheet(p, [0, 0, 0] * 16, data, (16, 48))
        macro, fw, fh, n = mst.sheet_info(p, (16, 16))
        self.assertEqual((fw, fh, n), (16, 16, 3))


class TransparencyMatchesTheDonorExactly(unittest.TestCase):
    """The invariant that actually catches holes. "Has any index-0 pixel?" is far too weak:
    the shipped sheets passed it with 265 legitimate background pixels while carrying holes
    punched through Ravisin's FACE (12 cream pixels mapped to 0)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='vendor_')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_colour_forced_to_transparent_is_rejected(self):
        p = os.path.join(self.tmp, 'donor.png')
        pal = [0, 0, 0] * 16
        pal[0:3] = [0xf8, 0xf8, 0xd0]        # art (the face highlight, in Ravisin's case)
        pal[3:6] = [0x40, 0x38, 0x38]
        pal[6:9] = [0x80, 0xa0, 0x80]        # the key
        frame = [2] * 256
        frame[0] = 0
        for i in (100, 101):
            frame[i] = 1
        _sheet(p, pal, frame * 3, (16, 48))
        out = os.path.join(self.tmp, 'out.png')
        # forcing the ART colour to transparent = a hole; must fail, not ship
        with self.assertRaises(SystemExit):
            mst.recolour(p, os.path.join(MS, 'cast_palette.png'), out, {0: 0})

    def test_ravisins_shipped_sheets_hole_free_against_their_donor(self):
        """Guards the live assets: transparency lands exactly on the donor's key."""
        donor_dir = os.path.join(REPO, 'map-review', 'ch05', 'fe-repo', 'sms')
        stem = 'Druid_Hoodless_(F)_Ultra-Fenix_Velvet_Kitsune'
        for src, out in ((stem + '-stand.png', 'ravisin.png'),
                         (stem + '-walk.png', 'ravisin_mu.png')):
            src = os.path.join(donor_dir, src)
            if not os.path.isfile(src):
                self.skipTest('vendored donor not present')
            dim = Image.open(src)
            key = mst._transparent_index(dim, dim.getpalette())
            want = {i for i, v in enumerate(dim.getdata()) if v == key}
            got = {i for i, v in enumerate(Image.open(os.path.join(MS, out)).getdata())
                   if v == 0}
            self.assertEqual(got, want,
                             '%s: transparency does not match the donor key' % out)


class FrameCount(unittest.TestCase):
    """`pattern` is not a frame count. Eirika Lord carries 0, the Druid 2, the Bonewalker 3
    -- and all three sheets are 16x48. The count comes from the HEIGHT, and the engine
    reads exactly 3 (ApplyUnitSpriteImage16x16 loops i < 3)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='vendor_')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_a_two_frame_16x16_sheet_is_rejected(self):
        p = os.path.join(self.tmp, 'short.png')
        data = [0] * (16 * 32)
        for i in range(100, 120):
            data[i] = 3
        _sheet(p, [0, 0, 0] * 16, data, (16, 32))
        with self.assertRaises(SystemExit):
            mst.sheet_info(p, (16, 16))

    def test_the_vanilla_druid_sheet_is_three_frames_despite_its_row_saying_2(self):
        d = os.path.join(REPO, 'fireemblem8u', 'graphics', 'unit_icon', 'wait',
                         'unit_icon_wait_Druid_sheet.png')
        if not os.path.isfile(d):
            self.skipTest('decomp graphics not built out')
        self.assertEqual(Image.open(d).size, (16, 48))


class RavisinsShippedSheets(unittest.TestCase):
    """The live assets: whatever the palette pass ends up as, these must hold."""

    def test_both_sheets_have_transparency_and_the_right_geometry(self):
        idle = os.path.join(MS, 'ravisin.png')
        walk = os.path.join(MS, 'ravisin_mu.png')
        if not os.path.isfile(idle):
            self.skipTest('ravisin map sprite not vendored')
        macro, fw, fh, n = mst.sheet_info(idle, (16, 16))
        self.assertEqual((fw, fh, n), (16, 16, 3))
        self.assertIn(0, set(Image.open(idle).getdata()))
        self.assertIn(0, set(Image.open(walk).getdata()))
        mst.validate_mu_sheet(walk)

    def test_she_wears_the_cast_palette(self):
        idle = os.path.join(MS, 'ravisin.png')
        if not os.path.isfile(idle):
            self.skipTest('ravisin map sprite not vendored')
        cast = mst.read_palette(os.path.join(MS, 'cast_palette.png'))
        self.assertEqual((Image.open(idle).getpalette() or [])[:48], cast[:48])


if __name__ == '__main__':
    unittest.main()
