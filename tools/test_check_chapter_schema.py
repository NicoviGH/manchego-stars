#!/usr/bin/env python3
"""Tests for the chapter deployment-schema gate in check.py (#107).

The 2026-07-02 audit (2.2) found four incompatible roster shapes across the 9 chapter
YAMLs -- invisible only because each built chapter had a hand-written injector. The gate
pins the ONE normalized shape (`deployment:` block owns deploy_limit/deploy_slots/note/
green_allies; `player_units:` only for the fixed-roster prologue) so the shared injector
machinery and difficulty.py can read a single access path.
"""
import glob
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check  # noqa: E402

import yaml  # noqa: E402

REPO = check.REPO


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
            violations({'status': 'active', 'player_units': [{'id': 'hlin'}]}), [])

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


class TestRealChapters(unittest.TestCase):
    def test_all_repo_chapters_pass(self):
        for f in sorted(glob.glob(os.path.join(
                REPO, 'campaigns/*/chapters/ch*.yaml'))):
            with open(f, encoding='utf-8') as fh:
                d = yaml.safe_load(fh) or {}
            self.assertEqual(
                check._chapter_deployment_violations(os.path.relpath(f, REPO), d), [])


if __name__ == '__main__':
    unittest.main()
