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


class TheGateSurvivesAnUngroundedRosterEntry(unittest.TestCase):
    """`check_rescue_targets` now reaches `units_reaching`, which -- since #369 widened it to
    every roster key -- calls `difficulty.enemy_ai_bytes` on `reinforcements:` and
    `enemy_reinforcements:` entries too, and that call RAISES on an entry with neither
    `donor:` nor `ai_override:` (a normal mid-draft state while a chapter is being
    authored). No live chapter combines `rescue_boats` with such an entry today, but
    `check.py`'s `main()` calls every check with zero per-check exception isolation, so this
    is not a print-and-skip away from crashing the WHOLE gate for an unrelated future
    chapter -- it is one YAML edit away."""

    def _ch06_with_ungrounded_wave(self):
        import copy
        import check as chk
        chap = copy.deepcopy(next(d for rel, d in chk._chapters()
                                  if d.get('id', '').startswith('ch06')))
        chap['reinforcements'] = [{'id': 'draft-stub', 'class': 'fighter', 'level': 1,
                                   'positions': [[0, 0]], 'inventory': [{'id': 'iron-sword'}]}]
        return chap

    def test_an_unreadable_map_is_reported_as_drift_not_swallowed_or_crashed(self):
        """Three outcomes are possible for a map this gate cannot read, and two are wrong.
        Swallowing it skips a HARD gate in silence; letting it propagate takes down every
        other check with it (`main` runs them with no isolation). It is reported instead --
        the gate fails, attributed, without a traceback. A missing map (a chapter with no
        compiled `.mar` yet) stays a legitimate skip, which is what the narrowing preserves."""
        import map_placement_preview as pp
        chap = {'id': 'ch99-broken', 'rescue_boats': [{'id': 'b', 'tile': [1, 1]}],
                'map': {'file': 'maps/ch99.mar'}}
        original = check._chapters
        real_terrain_grid = pp.terrain_grid
        check._chapters = lambda: iter([('ch99.yaml', chap)])
        pp.terrain_grid = lambda _d: (_ for _ in ()).throw(ValueError('unreadable tileset'))
        try:
            fail = []
            check.check_rescue_targets(fail)          # must not raise
            self.assertEqual(len(fail), 1, fail)
            self.assertIn('unreadable tileset', fail[0])
        finally:
            check._chapters = original
            pp.terrain_grid = real_terrain_grid

    def test_a_chapter_with_no_compiled_map_is_still_just_skipped(self):
        chap = {'id': 'ch99-planned', 'rescue_boats': [{'id': 'b', 'tile': [1, 1]}],
                'map': {'file': 'maps/ch99-does-not-exist.mar'}}
        original = check._chapters
        check._chapters = lambda: iter([('ch99.yaml', chap)])
        try:
            fail = []
            check.check_rescue_targets(fail)
            self.assertEqual([], fail)
        finally:
            check._chapters = original

    def test_an_ungrounded_reinforcement_does_not_crash_the_whole_gate(self):
        chap = self._ch06_with_ungrounded_wave()
        original = check._chapters
        check._chapters = lambda: iter([('ch06-stub.yaml', chap)])
        try:
            fail = []
            check.check_rescue_targets(fail)          # must not raise
        finally:
            check._chapters = original


if __name__ == '__main__':
    unittest.main()
