#!/usr/bin/env python3
"""banim_palette tests -- the hand-edited battle-anim palette (#25).

The load-bearing property is ORDER. A hand edit is stored as native-hex -> new-hex, and
the injector applies it as a `recolor` over the palette feditor_to_banim derives at build
time; if this tool showed swatches in a different order than that derivation, Nicolas
would be editing index 3 and the ROM would recolour index 7. So the editor reads its
palette from `feditor_to_banim._palette` itself rather than deriving its own.

The other property is that an edit is a PALETTE change only: the sheets keep their native
indices (that is what makes a hand edit a look call and not a re-import).
"""
import json
import os
import shutil
import tempfile
import unittest

from PIL import Image

import banim_palette as bp
import feditor_to_banim as fb

VENDORED = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'engine',
                        'battle_anims', '_vendored', 'wildling', 'unarmed')
RAVISIN = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'campaigns',
                       'rime-of-the-frostmaiden', 'battle_anims', 'ravisin')


class Palette(unittest.TestCase):
    def test_palette_matches_the_injectors_own_derivation(self):
        """The swatch order IS feditor_to_banim's, not a re-derivation of it."""
        doc = bp.Doc(VENDORED, 'Unarmed.txt')
        anim = fb.parse_feditor(open(os.path.join(VENDORED, 'Unarmed.txt')).read())
        imgs = [fb._load_frame(os.path.join(VENDORED, f)) for f in fb.unique_frames(anim)]
        self.assertEqual(doc.palette, fb._palette(imgs))

    def test_index_zero_is_transparent_and_not_editable(self):
        doc = bp.Doc(VENDORED, 'Unarmed.txt')
        self.assertEqual(doc.palette[0], (0, 0, 0))
        self.assertEqual(doc.data()['swatches'][0]['n'], 0)   # nothing draws with it

    def test_swatch_counts_are_per_index_pixel_totals(self):
        doc = bp.Doc(VENDORED, 'Unarmed.txt')
        sw = doc.data()['swatches']
        self.assertEqual(len(sw), len(doc.palette))
        # every opaque pixel of every previewed frame is accounted for by some swatch
        total = sum(s['n'] for s in sw)
        drawn = sum(sum(1 for p in f if p) for f in doc.data()['frames'])
        self.assertEqual(total, drawn)

    def test_preview_frames_share_one_window_so_motion_survives(self):
        """Every frame is cropped to the SAME box -- a pose drawn forward stays forward.
        Per-frame cropping would re-centre each pose and flatten the animation."""
        doc = bp.Doc(VENDORED, 'Unarmed.txt')
        d = doc.data()
        self.assertEqual(len({len(f) for f in d['frames']}), 1)
        self.assertEqual(len(d['frames'][0]), d['w'] * d['h'])


class EditRoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='banimpal_')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_save_then_load_recolors_only_the_edited_entries(self):
        p = os.path.join(self.tmp, 'palette.json')
        native = [(0, 0, 0), (24, 88, 216), (136, 96, 80)]
        bp.save_edit(p, native, {1: (216, 24, 24)})
        rc = bp.load_recolor(p)
        self.assertEqual(rc((24, 88, 216)), (216, 24, 24))    # edited
        self.assertEqual(rc((136, 96, 80)), (136, 96, 80))    # untouched -> identity
        self.assertEqual(rc((1, 2, 3)), (1, 2, 3))            # unknown -> identity

    def test_saved_file_records_the_full_ordered_palette(self):
        """The file has to say which palette the edit was made against, or a later
        re-vendor silently repoints every entry."""
        p = os.path.join(self.tmp, 'palette.json')
        native = [(0, 0, 0), (24, 88, 216), (136, 96, 80)]
        bp.save_edit(p, native, {2: (255, 0, 0)})
        blob = json.load(open(p))
        self.assertEqual(blob['native'], ['#000000', '#1858d8', '#886050'])
        # stored QUANTIZED -- #ff0000 is not a colour the GBA has (5 bits a channel)
        self.assertEqual(blob['edited']['2'], '#f80000')

    def test_an_empty_edit_loads_as_identity(self):
        p = os.path.join(self.tmp, 'palette.json')
        bp.save_edit(p, [(0, 0, 0), (1, 2, 3)], {})
        self.assertEqual(bp.load_recolor(p)((1, 2, 3)), (1, 2, 3))

    def test_a_missing_file_is_an_error_not_a_silent_identity(self):
        """A typo'd `palette_edit:` path must fail the BUILD, not ship native colours."""
        with self.assertRaises(IOError):
            bp.load_recolor(os.path.join(self.tmp, 'nope.json'))


class QuantizedToWhatTheGbaCanShow(unittest.TestCase):
    """A picked colour is snapped at PICK time. The hardware keeps 5 bits a channel, so
    two swatches chosen as distinct ramp steps can land on one halfword -- this tool's own
    "a ramp must stay a ramp" failure, reached through the tool that documents it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='banimpal_')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_quantize_keeps_the_top_five_bits(self):
        self.assertEqual(bp.gba_quantize((0x40, 0x40, 0x52)), (0x40, 0x40, 0x50))
        self.assertEqual(bp.gba_quantize((0xff, 0xff, 0xff)), (0xf8, 0xf8, 0xf8))
        self.assertEqual(bp.gba_quantize((0, 0, 0)), (0, 0, 0))

    def test_a_saved_edit_holds_only_reachable_colours(self):
        p = os.path.join(self.tmp, 'palette.json')
        bp.save_edit(p, [(0, 0, 0), (1, 2, 3)], {1: (0x40, 0x40, 0x52)})
        self.assertEqual(json.load(open(p))['edited']['1'], '#404050')

    def test_two_picks_that_collapse_to_one_colour_are_stored_as_one(self):
        """The failure this guards: #404052 and #404050 are the SAME halfword."""
        self.assertEqual(bp.gba_quantize((0x40, 0x40, 0x52)),
                         bp.gba_quantize((0x40, 0x40, 0x50)))


class EditMustStillMatchThePalette(unittest.TestCase):
    """The edit is stored per-INDEX and applied per-COLOUR, and nothing else compares them."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='banimpal_')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_an_edit_naming_a_vanished_colour_fails_the_build(self):
        p = os.path.join(self.tmp, 'palette.json')
        bp.save_edit(p, [(0, 0, 0), (24, 88, 216)], {1: (216, 24, 24)})
        rc = bp.load_recolor(p)
        for c in [(0, 0, 0), (99, 99, 99)]:      # a palette that no longer holds #1858d8
            rc(c)
        with self.assertRaises(SystemExit):
            bp.assert_all_applied(rc, 'test unit')

    def test_an_edit_whose_colours_are_all_present_passes(self):
        p = os.path.join(self.tmp, 'palette.json')
        bp.save_edit(p, [(0, 0, 0), (24, 88, 216)], {1: (216, 24, 24)})
        rc = bp.load_recolor(p)
        for c in [(0, 0, 0), (24, 88, 216)]:
            rc(c)
        bp.assert_all_applied(rc, 'test unit')     # must not raise

    def test_ravisins_live_edit_still_matches_her_frames(self):
        """Guards the shipped asset against a future re-vendor of her frames."""
        rc = bp.load_recolor(bp.edit_path(RAVISIN))
        for c in bp.Doc(RAVISIN, 'Magic.txt').palette:
            rc(c)
        bp.assert_all_applied(rc, 'ravisin')


class BrowserCacheKey(unittest.TestCase):
    def test_the_key_is_the_path_not_the_basename(self):
        """`wildling/unarmed` and `lizardzerker/unarmed` share a basename, as does every
        anim's axe/handaxe pair -- one draft would be handed to another creature."""
        a = bp.Doc(VENDORED, 'Unarmed.txt').data()['key']
        self.assertIn('wildling', a)
        self.assertNotEqual(a, 'unarmed')


class AppliedToTheRealImport(unittest.TestCase):
    """The end of the chain: a saved edit -> build_import -> recoloured agbpal, same sheets."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='banimpal_')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_edit_changes_the_agbpal_and_leaves_every_sheet_index_alone(self):
        doc = bp.Doc(VENDORED, 'Unarmed.txt')
        p = os.path.join(self.tmp, 'palette.json')
        bp.save_edit(p, doc.palette, {1: (248, 8, 8)})
        plain = fb.build_import('wu', os.path.join(VENDORED, 'Unarmed.txt'), VENDORED)
        edit = fb.build_import('wu', os.path.join(VENDORED, 'Unarmed.txt'), VENDORED,
                               recolor=bp.load_recolor(p))
        self.assertNotEqual(plain['pal'], edit['pal'])
        self.assertEqual([s.tobytes() for s in plain['sheets']],
                         [s.tobytes() for s in edit['sheets']])


class RavisinIsEditable(unittest.TestCase):
    """Guards the live asset this was built for: her frames must load and yield the
    15-colour palette the ROM bakes, or the editor is showing fiction."""

    def test_ravisin_loads_with_a_full_fe8_obj_palette(self):
        doc = bp.Doc(RAVISIN, 'Magic.txt')
        self.assertLessEqual(len(doc.palette), 16)
        self.assertEqual(doc.palette[0], (0, 0, 0))
        self.assertGreater(len(doc.data()['frames']), 20)   # 45 distinct frames


if __name__ == '__main__':
    unittest.main()
