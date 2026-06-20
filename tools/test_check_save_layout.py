#!/usr/bin/env python3
"""Tests for the save-layout-stability guard in check.py (#59).

The guard pins the FE8 decomp constants that decide whether a tester's battery .sav
survives a new build: the save-block validity magics (SAVEMAGIC16/32) and the two
array dimensions that size struct GameSaveBlock (BWL_ARRAY_NUM = roster, WIN_ARRAY_NUM =
chapter count). We reskin within FE8's fixed slots and never bump the submodule, so these
are constant -- if one ever drifts, old saves fail the checksum (auto-wiped) and that drop
needs the #59 starter-save fallback. The guard makes that the loud, one-line CI signal.

Decomp grounding: bmsave-lib.c:125-128 (magic+checksum validity), bmsave.h (the #defines).
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check  # noqa: E402

REPO = check.REPO

SAMPLE_HEADER = """
enum bmsave_magics_fe8 {
    SAVEMAGIC16       = 0x200A,
    SAVEMAGIC32       = 0x40624,
    SAVEMAGIC32_ARENA = 0x20112,
    SAVEMAGIC32_XMAP  = 0x20223,
};
#define BWL_ARRAY_NUM 0x46
#define WIN_ARRAY_NUM 0x30
"""


class TestParseSaveLayout(unittest.TestCase):
    def test_extracts_all_four_constants(self):
        got = check._parse_save_layout_constants(SAMPLE_HEADER)
        self.assertEqual(got['BWL_ARRAY_NUM'], 0x46)
        self.assertEqual(got['WIN_ARRAY_NUM'], 0x30)
        self.assertEqual(got['SAVEMAGIC16'], 0x200A)
        self.assertEqual(got['SAVEMAGIC32'], 0x40624)

    def test_word_boundary_does_not_match_arena_variant(self):
        # SAVEMAGIC32 must not capture SAVEMAGIC32_ARENA's value (0x20112).
        got = check._parse_save_layout_constants(SAMPLE_HEADER)
        self.assertEqual(got['SAVEMAGIC32'], 0x40624)

    def test_missing_constant_is_absent_from_result(self):
        got = check._parse_save_layout_constants("#define BWL_ARRAY_NUM 0x46\n")
        self.assertNotIn('WIN_ARRAY_NUM', got)


class TestSaveLayoutDrift(unittest.TestCase):
    def test_no_drift_when_values_match(self):
        self.assertEqual(check._save_layout_drift(dict(check.PINNED_SAVE_LAYOUT)), [])

    def test_changed_value_is_drift(self):
        found = dict(check.PINNED_SAVE_LAYOUT)
        found['WIN_ARRAY_NUM'] += 1  # a chapter added -> struct grows -> saves break
        msgs = check._save_layout_drift(found)
        self.assertEqual(len(msgs), 1)
        self.assertIn('WIN_ARRAY_NUM', msgs[0])

    def test_missing_value_is_drift(self):
        found = dict(check.PINNED_SAVE_LAYOUT)
        del found['SAVEMAGIC32']
        msgs = check._save_layout_drift(found)
        self.assertTrue(any('SAVEMAGIC32' in m for m in msgs))


class TestGuardOnRealDecomp(unittest.TestCase):
    def test_real_decomp_passes(self):
        if not os.path.isdir(os.path.join(REPO, 'fireemblem8u', 'src')):
            self.skipTest('fireemblem8u submodule not checked out')
        fail = []
        check.check_save_layout_stable(fail)
        self.assertEqual(fail, [], 'save-layout constants drifted from pinned values')


if __name__ == '__main__':
    unittest.main()
