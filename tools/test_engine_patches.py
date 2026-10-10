#!/usr/bin/env python3
"""Tests for the engine patch series, engine/patches/ (#410).

Run:  python3 tools/test_engine_patches.py
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject import engine_patches  # noqa: E402
from inject.decomp import FOUNDING_EXP_FLAG, LORDSEL_FLAG_BASE  # noqa: E402
from inject.portraits import PORTRAIT_BLINK  # noqa: E402
from inject.warm import PATCHED_DECOMP_FILES  # noqa: E402
import portrait_tool  # noqa: E402


class TheSeries(unittest.TestCase):
    # Applied for real, in a scratch copy of the vanilla files: `git apply --check` checks each
    # patch against the untouched tree, so 0006 (on top of 0005's eventinfo.c) would fail it.
    def test_it_applies_to_vanilla(self):
        self.assertIn('LordSelect_GetPid', engine_patches.patched_text('src/eventinfo.c'))

    def test_the_optional_patch_applies_on_top(self):
        self.assertIn('MsD20CritShow', engine_patches.patched_text(
            'src/banim-efxhit.c', optional=('crit-d20-flourish',)))

    def test_the_sound_room_audition_lists_every_song(self):
        text = engine_patches.patched_text('src/soundroom.c', optional=('sound-room-audition',))
        self.assertNotIn('if (LoadAndVerifySoundRoomData', text)
        self.assertNotIn('displayCondFunc(proc)', text)

    def test_it_is_numbered_densely_and_each_patch_says_what_it_is_for(self):
        series = engine_patches.patches()
        self.assertEqual([int(os.path.basename(p)[:4]) for p in series],
                         list(range(1, len(series) + 1)))
        for path in series:
            self.assertNotEqual(engine_patches.subject(path), os.path.basename(path), path)

    def test_every_file_it_changes_is_restored_before_each_build(self):
        # `git apply` needs the vanilla text under it, and restore_vanilla_sources is what
        # puts it back after the last build's injection.
        optional = [os.path.join(engine_patches.OPTIONAL_DIR, name)
                    for name in sorted(os.listdir(engine_patches.OPTIONAL_DIR))]
        files = engine_patches.patched_files(engine_patches.patches() + optional)
        self.assertEqual([f for f in files if f not in PATCHED_DECOMP_FILES], [])


class ItsLiterals(unittest.TestCase):
    """Values the Python side owns, which the patches carry as C literals."""

    def test_the_custom_banim_threshold_is_the_vanilla_banim_count(self):
        first_custom = '0x%X' % engine_patches.vanilla_banim_count()
        self.assertIn('banim_id >= %s' % first_custom,
                      engine_patches.patched_text('src/banim-ekrmain.c'))
        self.assertIn('gBanimIdx[POS_L] < %s' % first_custom,
                      engine_patches.patched_text('src/banim-ekrbattleintro.c'))

    def test_lord_select_reads_the_flags_the_campaign_sets(self):
        eventinfo = engine_patches.patched_text('src/eventinfo.c')
        self.assertTrue(re.search(r'\b0x%X\b' % LORDSEL_FLAG_BASE, eventinfo, re.I)
                        or re.search(r'\b%d\b' % LORDSEL_FLAG_BASE, eventinfo),
                        'LORDSEL_FLAG_BASE 0x%X is not in the patched eventinfo.c'
                        % LORDSEL_FLAG_BASE)


    def test_founding_exp_reads_the_flag_the_campaign_owns(self):
        eventinfo = engine_patches.patched_text('src/eventinfo.c')
        self.assertIn('CheckFlag(0x%X)' % FOUNDING_EXP_FLAG, eventinfo)
        self.assertIn('SetFlag(0x%X)' % FOUNDING_EXP_FLAG, eventinfo)
        self.assertNotIn(FOUNDING_EXP_FLAG, range(LORDSEL_FLAG_BASE, LORDSEL_FLAG_BASE + 11))


def _oam_table(text, name):
    """(w, h, x, y, chr) per piece of a `u16 CONST_DATA <name>[]` sprite table."""
    body = re.search(r'%s\[\] =\s*\{(.*?)\};' % re.escape(name), text, re.S).group(1)
    pieces = []
    for row in re.findall(r'OAM0_SHAPE_.*?OAM2_CHR\(0x[0-9A-Fa-f]+\)', body):
        w, h = map(int, re.search(r'SHAPE_(\d+)x(\d+)', row).groups())
        y = re.search(r'OAM0_Y\((-?\d+)\)', row)
        x = re.search(r'OAM1_X\(\+?(-?\d+)\)', row)
        chr_idx = int(re.search(r'OAM2_CHR\((0x[0-9A-Fa-f]+)\)', row).group(1), 16)
        pieces.append((w, h, int(x.group(1)) if x else 0, int(y.group(1)) if y else 0, chr_idx))
    return pieces


class TheStillFaceCorners(unittest.TestCase):
    """Patch 0018 draws the tiles portrait_tool packs; the two sides carry the layout twice."""

    FACE = engine_patches.patched_text('src/face.c')

    def test_the_corner_layout_is_the_one_portrait_tool_packs(self):
        self.assertEqual(portrait_tool.OBJECTS + portrait_tool.CORNER_OBJECTS,
                         _oam_table(self.FACE, 'gSprite_Face96x96_Corners'))

    def test_the_flipped_layout_mirrors_it(self):
        def mirrored(pieces):
            return sorted((w, h, -x - w, y, c) for w, h, x, y, c in pieces)
        self.assertEqual(mirrored(_oam_table(self.FACE, 'gSprite_Face96x96_Corners')),
                         sorted(_oam_table(self.FACE, 'gSprite_Face96x96_Corners_Flipped')))

    def test_the_status_face_edge_columns_read_the_corner_tiles(self):
        # PutFace80x72 shows bust x 8..87: its edge columns are bust x 8..15 and 80..87.
        def column(bust_x):
            tiles = []
            for bust_y in range(0, 48, 8):
                for w, h, x, y, c in portrait_tool.CORNER_OBJECTS:
                    ox, oy = bust_x - (x + portrait_tool.X_ORIGIN), bust_y - y
                    if 0 <= ox < w and 0 <= oy < h:
                        tiles.append('0x%02X' % (c + ox // 8 + oy // 8 * portrait_tool.GRID_W))
            return '{ %s }' % ', '.join(tiles)
        self.assertIn('cornerL[6] = %s;' % column(8), self.FACE)
        self.assertIn('cornerR[6] = %s;' % column(80), self.FACE)

    def test_the_blink_kind_the_injector_writes_is_the_engine_s(self):
        self.assertIn('%s = 7,' % PORTRAIT_BLINK, engine_patches.patched_text('include/types.h'))
        self.assertIn('blinkKind == %s' % PORTRAIT_BLINK, self.FACE)


if __name__ == '__main__':
    unittest.main()
