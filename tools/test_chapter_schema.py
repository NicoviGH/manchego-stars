#!/usr/bin/env python3
"""Tests for tools/chapter_schema.py (#411).

Run:  python3 tools/test_chapter_schema.py
"""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import campaign_chapters
import chapter_schema as schema


class ShippedChaptersPass(unittest.TestCase):
    def test_every_shipped_chapter_yaml_matches(self):
        for chapter in campaign_chapters.load_all():
            self.assertEqual([], schema.violations(campaign_chapters.short_id(chapter), chapter))


class BadKeysFail(unittest.TestCase):
    def setUp(self):
        self.ch05 = copy.deepcopy(campaign_chapters.load('ch05'))

    def test_a_typo_at_the_top_is_named_with_its_likely_fix(self):
        self.ch05['enemy_unit'] = self.ch05.pop('enemy_units')
        bad = schema.violations('ch05', self.ch05)
        self.assertEqual(1, len(bad))
        self.assertIn('enemy_unit is not a chapter key', bad[0])
        self.assertIn('did you mean `enemy_units`', bad[0])

    def test_a_typo_inside_a_list_item_names_its_path(self):
        self.ch05['enemy_units'][2]['is_bos'] = True
        self.assertEqual(['ch05: enemy_units[2].is_bos is not a chapter key -- did you mean '
                          '`is_boss`? (tools/chapter_schema.py lists them; add it there if it '
                          'is new)'], schema.violations('ch05', self.ch05))

    def test_a_typo_inside_a_nested_mapping_fails(self):
        self.ch05['objective']['turn'] = 20
        self.assertTrue(any('objective.turn ' in v for v in schema.violations('ch05', self.ch05)))

    def test_a_list_where_a_mapping_belongs_fails(self):
        self.ch05['objective'] = [self.ch05['objective']]
        self.assertEqual(['ch05: objective must be a mapping, not a list'],
                         schema.violations('ch05', self.ch05))

    def test_every_roster_key_takes_the_one_unit_shape(self):
        # The readers treat these keys interchangeably (raw_pids.PLACED_ROSTER_KEYS), so a boss
        # with a personal line is as legal in a wave as on the opening board (#426 review).
        boss = {'id': 'b', 'class': 'druid', 'level': 7, 'is_boss': True,
                'personal': {'baseHP': 3}, 'weapon': 'flux', 'art': {'portrait': 'b.png'}}
        for key in ('enemy_units', 'reinforcements', 'enemy_reinforcements', 'neutral_units',
                    'green_units', 'player_units'):
            self.assertEqual([], schema.violations('chNN', {key: [dict(boss)]}), key)
        self.assertEqual([], schema.violations('chNN', {'deployment': {'green_allies': [boss]}}))

    def test_free_keyed_mappings_accept_any_key(self):
        doc = {'rescue_boats': [{'id': 'b', 'reached_on': {'anything-goes': 3}}]}
        self.assertEqual([], schema.violations('chNN', doc))

    def test_a_scene_script_is_left_to_the_scene_preview(self):
        doc = {'events': [{'trigger': 'opening', 'script': [{'whoever': 'line'}, ['nested']]}]}
        self.assertEqual([], schema.violations('chNN', doc))

    def test_validate_exits_listing_every_violation(self):
        self.ch05['win_conditon'] = 'x'
        self.ch05['objective']['turn'] = 20
        with self.assertRaises(SystemExit) as caught:
            schema.validate('ch05', self.ch05)
        self.assertIn('win_conditon', str(caught.exception))
        self.assertIn('objective.turn', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
