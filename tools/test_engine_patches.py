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
from inject.warm import PATCHED_DECOMP_FILES  # noqa: E402


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


if __name__ == '__main__':
    unittest.main()
