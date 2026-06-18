#!/usr/bin/env python3
"""Tests for tools/build_campaign.py stat-resolution helpers.

These pin the donor-inheritance primitives the difficulty engine and the character
patcher share, against real vanilla values read from fireemblem8u/src/data_characters.c.
Run:  python3 tools/test_build_campaign.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_campaign as bc

with open(bc.CHARACTERS_C, encoding='utf-8') as _f:
    VANILLA = _f.read()


class DonorBaseStats(unittest.TestCase):
    def test_reads_garcias_personal_bases(self):
        # Garcia (braulo's donor): a real personal line on top of the Fighter class.
        self.assertEqual(bc.donor_base_stats(VANILLA, 'CHARACTER_GARCIA'), {
            'baseHP': 8, 'basePow': 3, 'baseSkl': 5, 'baseSpd': 3,
            'baseDef': 3, 'baseRes': 1, 'baseLck': 3, 'baseCon': 3,
        })

    def test_reads_ewans_personal_bases(self):
        # Ewan (the shamans' Ch1-appropriate base donor): fast + lucky mage kid.
        self.assertEqual(bc.donor_base_stats(VANILLA, 'CHARACTER_EWAN'), {
            'baseHP': 2, 'basePow': 2, 'baseSkl': 2, 'baseSpd': 4,
            'baseDef': 0, 'baseRes': 0, 'baseLck': 5, 'baseCon': 0,
        })

    def test_zero_personal_donor_reads_all_zero(self):
        # Gilliam (wolfram's donor) has no personal line -- donor-base inheritance
        # adds nothing beyond the Armor Knight class base, by design.
        self.assertEqual(bc.donor_base_stats(VANILLA, 'CHARACTER_GILLIAM'), {
            'baseHP': 0, 'basePow': 0, 'baseSkl': 0, 'baseSpd': 0,
            'baseDef': 0, 'baseRes': 0, 'baseLck': 0, 'baseCon': 0,
        })


if __name__ == '__main__':
    unittest.main()
