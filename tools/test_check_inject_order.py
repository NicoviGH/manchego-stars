#!/usr/bin/env python3
"""Tests for the injection-ordering guard in check.py (audit 2.6 / #110).

build_campaign.main() runs its injection steps in a dependency order that was
documented only in comments ("inject_ch01 MUST precede inject_prologue", "lord
floor after lord-select", ...). One reorder breaks the build at its most
expensive point; the guard pins the documented MUST-precede pairs and screams
if a constrained step is renamed away.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check  # noqa: E402

GOOD = """
def helper():
    inject_prologue(x)   # not main(); ignored

def main():
    inject_portraits(c)
    engine_hooks._inject_lord_select_engine()
    engine_hooks._inject_lord_floor_engine()
    inject_map_sprites(c)
    inject_enemy_class_reskins(c)
    inject_enemy_class_battle_anims(c)
    inject_winter_tileset(c)
    inject_ch01(c)
    if test:
        inject_test_chapter(c)
    else:
        inject_prologue(c, montage=m)
"""


class TestCallSequence(unittest.TestCase):
    def test_extracts_main_calls_in_order(self):
        order = check._injection_call_sequence(GOOD)
        self.assertLess(order.index('inject_ch01'), order.index('inject_prologue'))
        self.assertIn('_inject_lord_select_engine', order)   # engine_hooks. prefix stripped

    def test_ignores_calls_outside_main(self):
        # helper()'s inject_prologue must not count as the first call.
        order = check._injection_call_sequence(GOOD)
        self.assertGreater(order.index('inject_prologue'), order.index('inject_portraits'))

    def test_no_main_yields_empty(self):
        self.assertEqual(check._injection_call_sequence('x = 1\n'), [])


class TestOrderViolations(unittest.TestCase):
    def good_order(self):
        return check._injection_call_sequence(GOOD)

    def test_documented_order_passes(self):
        self.assertEqual(check._injection_order_violations(self.good_order()), [])

    def test_swapped_pair_is_flagged(self):
        order = self.good_order()
        a, b = order.index('inject_ch01'), order.index('inject_prologue')
        order[a], order[b] = order[b], order[a]
        msgs = check._injection_order_violations(order)
        self.assertTrue(any('inject_ch01 must run before inject_prologue' in m
                            for m in msgs))

    def test_renamed_step_screams_instead_of_silently_passing(self):
        order = [n for n in self.good_order() if n != 'inject_winter_tileset']
        msgs = check._injection_order_violations(order)
        self.assertTrue(any('unknown step' in m and 'inject_winter_tileset' in m
                            for m in msgs))


class TestRealBuildCampaign(unittest.TestCase):
    def test_repo_main_satisfies_all_constraints(self):
        fail = []
        check.check_injection_order(fail)
        self.assertEqual(fail, [])


if __name__ == '__main__':
    unittest.main()
