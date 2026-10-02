#!/usr/bin/env python3
"""Tests for tools/inject/chapters/prologue.py.

Run:  python3 tools/test_inject_prologue.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.chapters.prologue


class PrologueRosterFromYaml(unittest.TestCase):
    """The prologue roster is DATA, not a hardcode.

    #255's invalidation probe caught the opposite: bumping `level:` under the ch00 YAML's
    `enemy_units` moved no injected byte, and two full ROM builds -- edited and not --
    came out byte-identical, because inject_prologue emitted literals while its comment
    claimed it read the YAML. The values agreed by hand, so nothing looked wrong; a
    rebalance authored in YAML would simply not have shipped. These pin the wiring.
    """

    SLOTS = ('Eirika', 'Seth', 'ONeill')
    CLASSES = ('CLASS_FIGHTER', 'CLASS_HERO')
    GUEST_ITEMS = ('ITEM_AXE_HANDAXE, ITEM_VULNERARY', 'ITEM_SWORD_STEEL, ITEM_AXE_HANDAXE')

    def by_id(self, **over):
        units = {
            'hlin-trollbane': {'level': 3, 'position': [8, 5]},
            'scramsax': {'level': 1, 'position': [13, 9]},
            'sephek-kaltro': {'level': 5, 'position': [14, 8],
                              # #335: the boss holds his tile by declared override, because
                              # O'Neill's own DoNothing depends on a tutorial event-script
                              # we do not run.
                              'ai_override': {'ai': '{GuardTileAI, 0x9, 0x20}',
                                              'why': 'see the ch00 YAML'},
                              'inventory': [{'id': 'ice-longsword',
                                             'fe_base': 'steel-sword'}]},
            'caravan-guard': {'class': 'soldier', 'level': 2, 'count': 2,
                              'positions': [[14, 7], [13, 7]],
                              'donor': {'at': [14, 7], 'level': 2},
                              'inventory': [{'id': 'iron-lance'}]},
        }
        for uid, fields in over.items():                 # kwarg ids use _ for -
            units[uid.replace('_', '-')].update(fields)
        return units

    def blocks(self, **over):
        units = self.by_id(**over)
        chap = {'parity_reference': 'FE8 Prologue',
                'enemy_units': [units['sephek-kaltro'], units['caravan-guard']]}
        return inject.chapters.prologue._prologue_roster_blocks(chap, units, self.SLOTS, self.CLASSES,
                                          self.GUEST_ITEMS)

    def test_guard_class_and_weapon_track_the_yaml(self):
        enemy = self.blocks()[1]
        self.assertIn('.classIndex = CLASS_SOLDIER,', enemy)
        self.assertIn('ITEM_LANCE_IRON', enemy)
        enemy = self.blocks(caravan_guard={'class': 'fighter',
                                           'inventory': [{'id': 'iron-axe'}]})[1]
        self.assertIn('.classIndex = CLASS_FIGHTER,', enemy)

    def test_guest_items_come_from_the_yaml_in_order(self):
        self.assertEqual(inject.chapters.prologue.guest_items_for(
            {'inventory': [{'id': 'killer-axe'}, {'id': 'hand-axe'}, {'id': 'vulnerary'}]}),
            'ITEM_AXE_KILLER, ITEM_AXE_HANDAXE, ITEM_VULNERARY')

    def test_boss_level_tracks_the_yaml(self):
        self.assertIn('.level = 5,', self.blocks()[1])
        self.assertIn('.level = 6,', self.blocks(sephek_kaltro={'level': 6})[1])

    def test_boss_position_tracks_the_yaml(self):
        enemy = self.blocks(sephek_kaltro={'position': [3, 4]})[1]
        self.assertIn('.xPosition = 3,', enemy)
        self.assertIn('.yPosition = 4,', enemy)

    def test_boss_weapon_still_tracks_the_yaml(self):
        # #52's wiring, kept: the flavor "ice-longsword" resolves through fe_base.
        self.assertIn('ITEM_SWORD_STEEL', self.blocks()[1])

    def test_guest_level_and_position_track_the_yaml(self):
        ally = self.blocks(hlin_trollbane={'level': 4, 'position': [1, 2]})[0]
        self.assertIn('.level = 4,', ally)
        self.assertIn('.xPosition = 1,', ally)
        self.assertIn('.yPosition = 2,', ally)

    def test_guard_count_drives_how_many_are_emitted(self):
        self.assertEqual(self.blocks()[1].count('CLASS_SOLDIER'), 2)
        one = self.blocks(caravan_guard={'count': 1, 'positions': [[14, 7]]})[1]
        self.assertEqual(one.count('CLASS_SOLDIER'), 1)

    def test_guard_count_disagreeing_with_positions_is_fatal(self):
        # Silently emitting `count` guards at the first `count` positions would ship a
        # roster nobody authored. Fail the build instead.
        with self.assertRaises(SystemExit):
            self.blocks(caravan_guard={'count': 3})

    def test_more_guards_than_spare_slots_is_fatal(self):
        with self.assertRaises(SystemExit):
            self.blocks(caravan_guard={'count': 3, 'positions': [[1, 1], [2, 2], [3, 3]]})


if __name__ == '__main__':
    unittest.main()
