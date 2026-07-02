#!/usr/bin/env python3
"""Tests for the chapter deployment-schema gate in check.py (#107).

The 2026-07-02 audit (2.2) found four incompatible roster shapes across the 9 chapter
YAMLs -- invisible only because each built chapter had a hand-written injector. The gate
pins the ONE normalized shape (`deployment:` block owns deploy_limit/deploy_slots/note/
green_allies; `player_units:` only for the fixed-roster prologue) so the shared injector
machinery and difficulty.py can read a single access path.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check  # noqa: E402


def violations(d):
    return check._chapter_deployment_violations('chNN.yaml', d)


def valid_active():
    """A minimal active chapter in the normalized shape."""
    return {
        'status': 'active',
        'deployment': {
            'deploy_limit': 2,
            'deploy_slots': [[3, 8], [3, 9]],
        },
    }


class TestNormalizedShapePasses(unittest.TestCase):
    def test_active_with_limit_and_slots(self):
        self.assertEqual(violations(valid_active()), [])

    def test_planned_prose_only_deployment(self):
        # ch04-ch08 seeds: a deployment block with only a prose note is fine
        # while status is planned.
        self.assertEqual(
            violations({'status': 'planned', 'deployment': {'note': 'cap TBD'}}), [])

    def test_prologue_player_units(self):
        self.assertEqual(
            violations({'status': 'active', 'is_prologue': True,
                        'player_units': [{'id': 'hlin', 'class': 'fighter',
                                          'level': 3, 'position': [8, 5]}]}), [])

    def test_green_allies_complete_entries(self):
        d = valid_active()
        d['deployment']['green_allies'] = [{
            'id': 'chwinga-mote', 'class': 'pegasus_knight',
            'level': 1, 'position': [3, 4],
        }]
        self.assertEqual(violations(d), [])


class TestDriftShapesFail(unittest.TestCase):
    def test_top_level_deploy_limit_rejected(self):
        d = valid_active()
        d['deploy_limit'] = 4                       # the old ch01 shape
        self.assertTrue(any('top-level `deploy_limit`' in m for m in violations(d)))

    def test_top_level_deploy_slots_rejected(self):
        d = valid_active()
        d['deploy_slots'] = [[1, 1]]                # the old ch01/ch02 shape
        self.assertTrue(any('top-level `deploy_slots`' in m for m in violations(d)))

    def test_both_roster_shapes_rejected(self):
        d = valid_active()
        d['player_units'] = [{'id': 'x'}]
        self.assertTrue(any('EITHER' in m for m in violations(d)))

    def test_neither_roster_shape_rejected(self):
        self.assertTrue(any('EITHER' in m
                            for m in violations({'status': 'planned'})))

    def test_slots_must_match_limit(self):
        d = valid_active()
        d['deployment']['deploy_slots'].append([2, 8])   # 3 slots, limit 2
        self.assertTrue(any('must match' in m for m in violations(d)))

    def test_slots_without_limit_fail_the_match(self):
        d = {'status': 'planned',
             'deployment': {'deploy_slots': [[1, 1]]}}
        self.assertTrue(any('must match' in m for m in violations(d)))

    def test_malformed_slot_rejected(self):
        d = valid_active()
        d['deployment']['deploy_slots'] = [[3, 8], [3]]  # not a [col, row] pair
        self.assertTrue(any('[col, row]' in m for m in violations(d)))

    def test_active_needs_machine_readable_limit(self):
        # An active chapter can't hide its cap in prose (the ch04-08 seed shape
        # is only legal while planned).
        d = {'status': 'active', 'deployment': {'note': 'fields 5'}}
        self.assertTrue(any('machine-readable' in m for m in violations(d)))

    def test_non_int_limit_rejected(self):
        d = valid_active()
        d['deployment']['deploy_limit'] = 'five'
        self.assertTrue(any('positive int' in m for m in violations(d)))

    def test_incomplete_green_ally_rejected(self):
        d = valid_active()
        d['deployment']['green_allies'] = [{'id': 'chwinga-mote', 'level': 1}]
        msgs = violations(d)
        self.assertTrue(any('green_allies' in m and 'class' in m for m in msgs))


class TestMalformedYamlIsAViolationNotACrash(unittest.TestCase):
    # A typo'd chapter must produce a per-file message, never a traceback that
    # aborts check.py and skips every later gate.

    def test_scalar_deploy_slots(self):
        d = valid_active()
        d['deployment']['deploy_slots'] = 5     # confused slots with the limit
        self.assertTrue(any('must be a list' in m for m in violations(d)))

    def test_string_green_ally_entry(self):
        d = valid_active()
        d['deployment']['green_allies'] = ['chwinga-mote']   # bare id, no mapping
        self.assertTrue(any('must be a mapping' in m for m in violations(d)))

    def test_boolean_deploy_limit_rejected(self):
        # YAML `deploy_limit: yes` parses to True; isinstance(True, int) is True,
        # so an explicit bool exclusion keeps a typo from becoming a cap of 1.
        d = valid_active()
        d['deployment']['deploy_limit'] = True
        d['deployment']['deploy_slots'] = [[3, 8]]
        self.assertTrue(any('positive int' in m for m in violations(d)))

    def test_green_ally_position_shape_checked(self):
        # inject_ch02 indexes position[0]/position[1]; the gate must reject what
        # the consumer would crash on.
        d = valid_active()
        d['deployment']['green_allies'] = [{'id': 'chwinga-mote',
                                            'class': 'pegasus_knight',
                                            'level': 1, 'position': 7}]
        self.assertTrue(any('position' in m and '[col, row]' in m
                            for m in violations(d)))

    def test_one_bad_limit_does_not_cascade(self):
        # A single typo'd limit reports ONCE; the slots-match and
        # machine-readable rules stay quiet (same root cause).
        d = valid_active()
        d['deployment']['deploy_limit'] = 'five'
        msgs = violations(d)
        self.assertEqual(len(msgs), 1, msgs)
        self.assertIn('positive int', msgs[0])

    def test_player_units_requires_is_prologue(self):
        # The fixed-roster escape hatch is tied to is_prologue structurally --
        # a prep-screen chapter can't dodge deployment validation by switching
        # roster shapes.
        d = {'status': 'active',
             'player_units': [{'id': 'x', 'class': 'fighter', 'level': 1,
                               'position': [1, 1]}]}
        self.assertTrue(any('is_prologue' in m for m in violations(d)))


class TestRealChapters(unittest.TestCase):
    def test_all_repo_chapters_pass(self):
        # Exercise the PUBLIC gate exactly as CI runs it (glob + parse policy
        # included), not a hand-rolled copy of its loop.
        fail = []
        check.check_chapter_deployment_schema(fail)
        self.assertEqual(fail, [])


if __name__ == '__main__':
    unittest.main()
