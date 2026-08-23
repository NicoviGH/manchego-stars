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
    _anims.run(inject_enemy_class_battle_anims, c)
    inject_winter_tileset(c)
    inject_ch01(c)
    inject_ch03(c)
    inject_ch04(c)
    inject_ch05(c)
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

    def test_a_cached_step_still_counts_as_itself(self):
        """A step run through the injection cache (`_anims.run(inject_x, ...)`, #309) is the
        same step in the same place -- exactly like `_scopes.run`. If the parser missed it,
        the step would silently drop out of this gate and its ordering constraints with it."""
        order = check._injection_call_sequence(GOOD)
        self.assertIn('inject_enemy_class_battle_anims', order)
        self.assertLess(order.index('inject_enemy_class_reskins'),
                        order.index('inject_enemy_class_battle_anims'))

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

    def test_ch04_runs_after_the_previous_chapter_host(self):
        self.assertTrue(any(a == 'inject_ch03' and b == 'inject_ch04'
                            for a, b, _why in check.INJECTION_ORDER))
        order = self.good_order()
        a, b = order.index('inject_ch03'), order.index('inject_ch04')
        order[a], order[b] = order[b], order[a]
        msgs = check._injection_order_violations(order)
        self.assertTrue(any('inject_ch03 must run before inject_ch04' in m
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



CACHED_GOOD = """
def main():
    _requested_flags = {'TESTCH': args.test_chapter, 'CH05BOOT': args.ch05_boot}
    if args.ch05_moose and not args.ch05_boot:
        sys.exit('--ch05-moose needs --ch05-boot')
    _anims.run(inject_enemy_class_battle_anims, args.campaign)
    _anims.run(inject_battle_anims, args.campaign)
    _scopes.run(inject_ch05, args.campaign, boot=args.ch05_boot)
    if args.ch05_boot:
        _configure_boot(CH05_HOST_INDEX)
"""

CACHED_BAD = """
def main():
    _requested_flags = {'TESTCH': args.test_chapter, 'CH05BOOT': args.ch05_boot}
    _scopes.run(inject_ch05, args.campaign, boot=args.ch05_boot)
    _anims.run(inject_battle_anims, args.campaign)
"""


class TestCachedStepsAreConfigInvariant(unittest.TestCase):
    """A cached step's output is restored across ROM configurations, so nothing that reads a
    boot flag may run before it (#309). Ordering is what makes the cache sound; a comment
    saying so is not."""

    def test_a_cached_step_ahead_of_every_flagged_injector_passes(self):
        self.assertEqual(check._cached_step_violations(CACHED_GOOD), [])

    def test_a_flagged_injector_ahead_of_a_cached_step_is_a_violation(self):
        msgs = check._cached_step_violations(CACHED_BAD)
        self.assertEqual(len(msgs), 1, msgs)
        self.assertIn('inject_battle_anims', msgs[0])
        self.assertIn('inject_ch05', msgs[0])

    def test_the_real_build_campaign_satisfies_it(self):
        fail = []
        check.check_cached_steps_are_config_invariant(fail)
        self.assertEqual(fail, [])

if __name__ == '__main__':
    unittest.main()
