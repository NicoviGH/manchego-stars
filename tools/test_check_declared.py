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

CLEAN = {'tools/playtest/cases.lua':
         'local M = {}\nM.WHEN.visit = function(api, arg) return api.visitVillage(arg.x) end\n',
         "harness.lua's declared-case api adapter": 'local api = {shot = shot}\n'}
VILLAGES = {'ch05': [[5, 1], [5, 6], [12, 10], [12, 19]]}


def case(**over):
    c = {'name': 'ch05village', 'proves': 'x',
         'when': [{'visit': {'x': 12, 'y': 19}}], 'then': [{'gained_item': 0x60}]}
    c.update(over)
    return [('ch05', c)]


class TestVisitTilesMatchTheChapter(unittest.TestCase):
    def test_a_declared_village_tile_is_clean(self):
        self.assertEqual(check._declared_case_violations(case(), VILLAGES, CLEAN), [])

    def test_a_tile_the_chapter_declares_no_village_at_is_reported(self):
        bad = case(when=[{'visit': {'x': 12, 'y': 18}}])      # off by one row
        found = check._declared_case_violations(bad, VILLAGES, CLEAN)
        self.assertEqual(len(found), 1, found)
        self.assertIn('(12,18)', found[0])

    def test_every_bad_step_is_reported_not_just_the_first(self):
        bad = case(when=[{'visit': {'x': 0, 'y': 0}}, {'visit': {'x': 1, 'y': 1}}])
        self.assertEqual(len(check._declared_case_violations(bad, VILLAGES, CLEAN)), 2)

    def test_a_non_visit_step_is_not_checked_against_villages(self):
        self.assertEqual(
            check._declared_case_violations(case(when=[{'end_turn': True}]), VILLAGES, CLEAN),
            [])

    def test_a_malformed_step_is_reported_rather_than_crashing(self):
        bad = case(when=[{'visit': {'x': 1}, 'spoke': True}])   # two keys
        found = check._declared_case_violations(bad, VILLAGES, CLEAN)
        self.assertEqual(len(found), 1, found)
        self.assertIn('single-key', found[0])

    def test_a_non_mapping_visit_argument_does_not_abort_the_whole_lint(self):
        # `- visit: south` reached arg.get() and raised AttributeError. main() calls the
        # checks unguarded, so one typo aborted the drift gate and every check after this
        # one never ran -- a lint that fails OPEN.
        found = check._declared_case_violations(case(when=[{'visit': 'south'}]), VILLAGES, CLEAN)
        self.assertEqual(len(found), 1, found)
        self.assertIn('mapping with x and y', found[0])

    def test_a_malformed_then_entry_is_reported(self):
        # `- spoke` instead of `- spoke: true` linted clean and then died inside mGBA.
        found = check._declared_case_violations(case(then=['spoke']), VILLAGES, CLEAN)
        self.assertEqual(len(found), 1, found)
        self.assertIn('single-key mapping', found[0])


class TestTheDriverStaysGuarded(unittest.TestCase):
    def test_a_clean_driver_is_clean(self):
        self.assertEqual(check._declared_case_violations(case(), VILLAGES, CLEAN), [])

    def test_a_raw_press_in_the_driver_is_reported(self):
        # One blind press here un-guards EVERY declared case at once, not one of them.
        dirty = dict(CLEAN)
        dirty['tools/playtest/cases.lua'] += 'M.WHEN.mash = function(api) press(1, 4) end\n'
        found = check._declared_case_violations(case(), VILLAGES, dirty)
        self.assertEqual(len(found), 1, found)
        self.assertIn('raw press()', found[0])

    def test_a_raw_press_in_the_API_ADAPTER_is_reported(self):
        """The adapter lives inside harness.lua's runner coroutine, so `harness_functions`
        attributes it to the preceding `record` scenario and the blind-press gate skips it.
        It is every declared case's only route to the game, so it gets checked by name."""
        dirty = dict(CLEAN)
        dirty["harness.lua's declared-case api adapter"] += 'press(1, 4)\n'
        found = check._declared_case_violations(case(), VILLAGES, dirty)
        self.assertEqual(len(found), 1, found)
        self.assertIn('api adapter', found[0])

    def test_the_adapter_is_actually_found_in_the_live_harness(self):
        """If the carve-out stops matching, the check silently reviews nothing."""
        import os
        with open(os.path.join(check.REPO, 'tools/playtest/harness.lua'), encoding='utf-8') as fh:
            adapter = check._declared_api_adapter(fh.read())
        self.assertIsNotNone(adapter)
        self.assertIn('visitVillage', adapter, 'the carve-out must cover the real api table')
        self.assertLess(len(adapter), 4000, 'the carve-out has run past the adapter')


class TestTheShippedCasesAreClean(unittest.TestCase):
    def test_the_real_chapter_yaml_passes_both_guards(self):
        fail = []
        check.check_declared_cases(fail)
        self.assertEqual(fail, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
