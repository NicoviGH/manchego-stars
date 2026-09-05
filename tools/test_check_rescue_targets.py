#!/usr/bin/env python3
"""Tests for check.py's rescue-target guard (#26).

A chapter with `rescue_boats:` declares which units are the clock. Everything ELSE that can
reach a hull is a mob the chapter did not plan for, and ch06 shipped four of them: the fuse was
tuned as a one-pursuer clock and the hull sank on turn 4 instead of 7.

The pure half is tested against synthetic input, both directions, because a guard that cannot
fail is not a guard.

Run: python3 tools/test_check_rescue_targets.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check                                            # noqa: E402

SAFE = (0x08, 0x03, 0, 0)      # ActionInRange_ExceptCivilian -- cannot target a hull
MOB = (0x00, 0x03, 0, 0)       # plain ActionInRange -- steps out and swings
PURSUER = (0x00, 0x00, 0, 0)


def run(reachers, pursuers=('ice-crab',)):
    return check._rescue_target_violations('ch06', reachers, set(pursuers))


class RescueTargetsHaveOnlyTheirDeclaredClock(unittest.TestCase):
    def test_a_declared_pursuer_may_reach_a_hull(self):
        self.assertEqual([], run([('ice-crab', PURSUER)]))

    def test_a_unit_carrying_the_safe_ACTION_may_reach_a_hull(self):
        self.assertEqual([], run([('merfolk-bow', SAFE)]))

    def test_an_UNDECLARED_striker_that_reaches_a_hull_is_reported(self):
        found = run([('merfolk-bow', MOB)])
        self.assertEqual(len(found), 1, found)
        self.assertIn('merfolk-bow', found[0])

    def test_every_offender_is_reported_not_just_the_first(self):
        self.assertEqual(2, len(run([('merfolk-bow', MOB), ('shark-rider-steel', MOB)])))

    def test_a_pursuer_that_is_not_declared_is_still_reported(self):
        """A pursuer walks to the hull over several turns, which is a clock -- but an
        UNdeclared one is a second clock nobody costed."""
        found = run([('crab-rider-hard-lance', PURSUER)])
        self.assertEqual(len(found), 1, found)

    def test_nothing_reaching_a_hull_is_clean(self):
        self.assertEqual([], run([]))

    def test_the_finding_names_the_two_ways_out(self):
        """The message has to say what to DO, because the fix is a design choice between
        declaring the unit as a pursuer and giving it the safe action byte."""
        text = run([('merfolk-bow', MOB)])[0]
        self.assertIn('ai_override', text)
        self.assertIn('pursuer', text)


if __name__ == '__main__':
    unittest.main()
