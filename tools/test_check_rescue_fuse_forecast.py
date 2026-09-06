#!/usr/bin/env python3
"""Tests for check.py's rescue-fuse-forecast guard (#367, #26).

`check_rescue_targets` (test_check_rescue_targets.py) proves nothing UNDECLARED can attack a
rescue target. This guard asks the other question: can the DECLARED clock actually reach it,
and does a declared fuse sit inside the forecast band. It is ADVISORY, not a gate -- ch06's
own east pursuer fails the first question today (a real, already-confirmed bug, #26), and
flipping this to a hard gate is a follow-up left for Nicolas once that pursuer is settled.
Turning it into a gate before then would redden CI on `main` for a finding nobody asked this
PR to fix.

Run: python3 tools/test_check_rescue_fuse_forecast.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check                                             # noqa: E402
import rescue_forecast as rf                             # noqa: E402


def row(enemy_id, boat_id, arrival=None, low=None, expected=None, high=None):
    return rf.PursuerForecast(enemy_id, boat_id, 1, arrival, None, low, expected, high)


class ADeclaredPursuerMustReachSomeTarget(unittest.TestCase):
    def test_a_pursuer_that_reaches_a_boat_is_clean(self):
        chap = {'rescue_pursuers': [{'id': 'crab'}], 'rescue_boats': [{'id': 'b'}]}
        rows = [row('crab', 'b', arrival=2, low=6, expected=9, high=12)]
        self.assertEqual(check._fuse_forecast_findings(chap, rows), [])

    def test_a_pursuer_that_reaches_no_boat_is_reported(self):
        chap = {'rescue_pursuers': [{'id': 'thrower'}], 'rescue_boats': [{'id': 'east'}]}
        rows = [row('thrower', 'east', arrival=None)]
        found = check._fuse_forecast_findings(chap, rows)
        self.assertEqual(len(found), 1, found)
        self.assertIn('thrower', found[0])

    def test_a_pursuer_that_reaches_at_least_one_of_several_boats_is_clean(self):
        chap = {'rescue_pursuers': [{'id': 'p'}], 'rescue_boats': [{'id': 'a'}, {'id': 'b'}]}
        rows = [row('p', 'a', arrival=None), row('p', 'b', arrival=3, low=5, expected=7, high=9)]
        self.assertEqual(check._fuse_forecast_findings(chap, rows), [])

    def test_every_offending_pursuer_is_reported_not_just_the_first(self):
        chap = {'rescue_pursuers': [{'id': 'p1'}, {'id': 'p2'}], 'rescue_boats': [{'id': 'a'}]}
        rows = [row('p1', 'a', arrival=None), row('p2', 'a', arrival=None)]
        self.assertEqual(2, len(check._fuse_forecast_findings(chap, rows)))

    def test_a_chapter_with_no_rows_for_a_pursuer_says_nothing(self):
        """A schema mismatch (the pursuer id names no roster entry) is a DIFFERENT guard's
        job -- this one only speaks to pursuers it was actually able to forecast."""
        chap = {'rescue_pursuers': [{'id': 'ghost'}], 'rescue_boats': [{'id': 'a'}]}
        self.assertEqual(check._fuse_forecast_findings(chap, []), [])


class ADeclaredFuseMustFallInsideTheBand(unittest.TestCase):
    """Optional and forward-looking: no shipped chapter declares `declared_fuse` yet (ch06's
    is prose, in `difficulty_note:`, not a schema field), so this never fires today -- it is
    built in for the day a chapter adopts the field, per the model's own step 4."""

    def test_a_fuse_inside_the_band_is_clean(self):
        chap = {'rescue_pursuers': [{'id': 'p'}],
                'rescue_boats': [{'id': 'b', 'declared_fuse': 8}]}
        rows = [row('p', 'b', arrival=2, low=6, expected=9, high=12)]
        self.assertEqual(check._fuse_forecast_findings(chap, rows), [])

    def test_a_fuse_outside_every_reaching_pursuers_band_is_reported(self):
        chap = {'rescue_pursuers': [{'id': 'p'}],
                'rescue_boats': [{'id': 'b', 'declared_fuse': 30}]}
        rows = [row('p', 'b', arrival=2, low=6, expected=9, high=12)]
        found = check._fuse_forecast_findings(chap, rows)
        self.assertEqual(len(found), 1, found)
        self.assertIn('b', found[0])
        self.assertIn('30', found[0])

    def test_no_declared_fuse_means_nothing_to_check(self):
        chap = {'rescue_pursuers': [{'id': 'p'}], 'rescue_boats': [{'id': 'b'}]}
        rows = [row('p', 'b', arrival=2, low=6, expected=9, high=12)]
        self.assertEqual(check._fuse_forecast_findings(chap, rows), [])

    def test_a_fuse_is_not_double_reported_when_nothing_reaches(self):
        """The unreachable-pursuer finding already says this boat's clock is broken; a
        second finding about its fuse would just be noise on the same fact."""
        chap = {'rescue_pursuers': [{'id': 'p'}],
                'rescue_boats': [{'id': 'b', 'declared_fuse': 8}]}
        rows = [row('p', 'b', arrival=None)]
        found = check._fuse_forecast_findings(chap, rows)
        self.assertEqual(len(found), 1, found)
        self.assertIn('never', found[0])

    def test_a_reaching_pursuer_with_no_sink_band_does_not_crash_the_gate(self):
        """`pursuer_forecast` returns `arrival_turn` set with `sink_low/high=None` when it
        reaches a firing cell but deals no true damage (`sink_band`'s own `None` case, e.g.
        0 hit chance or an effectiveness mismatch) -- a real return shape, not a synthetic
        edge. This guard's whole docstring promise is that it NEVER fails the build; the
        comparison must not blow up on the exact row that promise exists to cover."""
        chap = {'rescue_pursuers': [{'id': 'p'}],
                'rescue_boats': [{'id': 'b', 'declared_fuse': 8}]}
        rows = [row('p', 'b', arrival=2)]           # reaches; low/expected/high all None
        found = check._fuse_forecast_findings(chap, rows)   # must not raise
        self.assertEqual(found, [])


class TheGuardIsAdvisoryAndReproducesCh06(unittest.TestCase):
    """`check_rescue_fuse_forecast` must NEVER append to `fail`, regardless of whether any
    chapter's rescue clock is currently clean -- ch06's east pursuer was the confirmed #26
    bug this guard was built to surface (`merfolk-thrower` corked by its own line), fixed on
    ch06-east-pursuer by moving the two corking bodies off the corridor. The advisory
    contract has to hold either way, so this class no longer needs a live finding to test it."""

    def test_the_check_never_fails_the_build(self):
        fail = []
        check.check_rescue_fuse_forecast(fail)
        self.assertEqual(fail, [])

    def test_ch06s_pursuers_are_now_clean_so_it_prints_nothing_about_them(self):
        """Not a synthetic stand-in: the real chapter YAML, the real compiled map. Confirms
        the fix, not just the tool -- a regression here means the corridor corked again."""
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            check.check_rescue_fuse_forecast([])
        self.assertNotIn('merfolk-thrower', buf.getvalue())

    def test_ch06s_west_pursuer_is_clean_so_it_prints_nothing_about_it(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            check.check_rescue_fuse_forecast([])
        self.assertNotIn('ice-crab', buf.getvalue())


if __name__ == '__main__':
    unittest.main()
