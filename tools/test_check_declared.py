#!/usr/bin/env python3
"""Tests for check.py's chapter-declared playtest case guards (#314).

The pure half (`_declared_case_violations`) is tested here against synthetic inputs, the
same split test_check_chapter_schema.py uses. A guard is asserted in BOTH directions --
clean input produces nothing, bad input produces the finding -- because a guard that cannot
fail is not a guard, and this repo has shipped one of those before.

Run: python3 tools/test_check_declared.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check                                            # noqa: E402

CLEAN_LUA = 'local M = {}\nM.WHEN.visit = function(api, arg) return api.visitVillage(arg.x) end\n'
VILLAGES = {'ch05': [[5, 1], [5, 6], [12, 10], [12, 19]]}


def case(**over):
    c = {'name': 'ch05village', 'proves': 'x',
         'when': [{'visit': {'x': 12, 'y': 19}}], 'then': [{'gained_item': 0x60}]}
    c.update(over)
    return [('ch05', c)]


class TestVisitTilesMatchTheChapter(unittest.TestCase):
    def test_a_declared_village_tile_is_clean(self):
        self.assertEqual(check._declared_case_violations(case(), VILLAGES, CLEAN_LUA), [])

    def test_a_tile_the_chapter_declares_no_village_at_is_reported(self):
        bad = case(when=[{'visit': {'x': 12, 'y': 18}}])      # off by one row
        found = check._declared_case_violations(bad, VILLAGES, CLEAN_LUA)
        self.assertEqual(len(found), 1, found)
        self.assertIn('(12,18)', found[0])

    def test_every_bad_step_is_reported_not_just_the_first(self):
        bad = case(when=[{'visit': {'x': 0, 'y': 0}}, {'visit': {'x': 1, 'y': 1}}])
        self.assertEqual(len(check._declared_case_violations(bad, VILLAGES, CLEAN_LUA)), 2)

    def test_a_non_visit_step_is_not_checked_against_villages(self):
        self.assertEqual(
            check._declared_case_violations(case(when=[{'end_turn': True}]), VILLAGES, CLEAN_LUA),
            [])

    def test_a_malformed_step_is_reported_rather_than_crashing(self):
        bad = case(when=[{'visit': {'x': 1}, 'spoke': True}])   # two keys
        found = check._declared_case_violations(bad, VILLAGES, CLEAN_LUA)
        self.assertEqual(len(found), 1, found)
        self.assertIn('single-key', found[0])


class TestTheDriverStaysGuarded(unittest.TestCase):
    def test_a_clean_driver_is_clean(self):
        self.assertEqual(check._declared_case_violations(case(), VILLAGES, CLEAN_LUA), [])

    def test_a_raw_press_in_the_driver_is_reported(self):
        # One blind press here un-guards EVERY declared case at once, not one of them.
        dirty = CLEAN_LUA + 'M.WHEN.mash = function(api) press(api.K.A, 4) end\n'
        found = check._declared_case_violations(case(), VILLAGES, dirty)
        self.assertEqual(len(found), 1, found)
        self.assertIn('raw press()', found[0])


class TestTheShippedCasesAreClean(unittest.TestCase):
    def test_the_real_chapter_yaml_passes_both_guards(self):
        fail = []
        check.check_declared_cases(fail)
        self.assertEqual(fail, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
