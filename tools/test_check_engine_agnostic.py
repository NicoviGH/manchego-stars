#!/usr/bin/env python3
"""Tests for the mechanized Engine/Content Boundary Rule in tools/check.py.

Pins the pure name-scan: hand-written engine code must not hardcode a campaign character
id ("braulo" belongs in YAML, not a .c). Run: python3 tools/test_check_engine_agnostic.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check


class EngineNameHits(unittest.TestCase):
    IDS = {'braulo', 'prof-rbg', 'brie', 'marty'}

    def test_bare_name_is_caught(self):
        self.assertEqual(check._engine_name_hits(self.IDS, 'if (pid == braulo) {'),
                         [('braulo', 1)])

    def test_caught_in_a_comment_case_insensitively(self):
        self.assertEqual(check._engine_name_hits(self.IDS, '/* MARTY rides the lord slot */'),
                         [('marty', 1)])

    def test_hyphenated_id_is_caught(self):
        self.assertEqual(check._engine_name_hits(self.IDS, '    /* prof-rbg hook */'),
                         [('prof-rbg', 1)])

    def test_substring_is_not_a_false_positive(self):
        # 'brie' must not fire on 'brief'; word boundaries protect common-word ids.
        self.assertEqual(check._engine_name_hits(self.IDS, 'int brief_count = 0;'), [])

    def test_clean_engine_text_passes(self):
        self.assertEqual(
            check._engine_name_hits(self.IDS, 'StartFace(0, GetUnitPortraitId(gActiveUnit));'),
            [])

    def test_reports_the_line_number(self):
        text = 'line one\nline two\n    if (pid == sclorbo) act();'
        self.assertEqual(check._engine_name_hits({'sclorbo'}, text), [('sclorbo', 3)])

    def test_empty_id_set_is_a_noop(self):
        self.assertEqual(check._engine_name_hits(set(), 'braulo everywhere'), [])


class CampaignIds(unittest.TestCase):
    def test_real_roster_loads_from_yaml(self):
        ids = check._campaign_character_ids()
        # The real campaign should yield its leads (sanity that the YAML scan works).
        self.assertIn('braulo', ids)
        self.assertIn('prof-rbg', ids)

    def test_the_live_tree_is_already_agnostic(self):
        # The committed engine sources must be clean right now -- the guard ships green.
        fail = []
        check.check_engine_campaign_agnostic(fail)
        self.assertEqual(fail, [], 'engine sources name a campaign character:\n' + '\n'.join(fail))


if __name__ == '__main__':
    unittest.main()
