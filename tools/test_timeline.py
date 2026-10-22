#!/usr/bin/env python3
"""Tests for tools/timeline.py -- instrument v2's layer 2 (#430 step 2b). Run:

    python3 tools/test_timeline.py
"""
import contextlib
import copy
import io
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import danger_map as dm
import difficulty as dif
import fe_combat as fc
import map_placement_preview as pp
import timeline as tl

PLAINS = pp.TERRAIN['TERRAIN_PLAINS']
FOOT = 'TerrainTable_MovCost_CommonT1Normal'


def plains(w=12, h=3):
    return [[PLAINS] * w for _ in range(h)]


def soldier(name='e', weapon='iron-lance'):
    return fc.Combatant(name, hp=20, pow=6, skl=4, spd=4, df=3, res=0, lck=0, con=10,
                        weapon=fc.W[weapon])


def body(source, shape='pursuer', arrives=1, mov=5, weapon='iron-lance', index=0):
    return dm.Body('e', index, source, shape, 0x00, arrives, FOOT, mov, (soldier(weapon=weapon),))


class TheTwinsBoard(unittest.TestCase):
    def test_the_layout_comes_from_the_chapter_settings(self):
        self.assertEqual(dif.vanilla_layout('FE8 Ch4'), 'Ch4Map')
        self.assertEqual(dif.vanilla_layout('FE8 Prologue'), 'PrologueMap')

    def test_the_front_is_the_table_the_event_group_names(self):
        # ch05's deploy_slots are lifted 1:1 from vanilla Ch5's playerUnitsInNormal table.
        chapter = pp.load_chapter('ch05')
        self.assertEqual(dif.vanilla_front('FE8 Ch5'), tl.our_front(chapter))

    def test_a_fixed_roster_front_is_its_player_units(self):
        chapter = pp.load_chapter('ch00')
        self.assertEqual(tl.our_front(chapter),
                         sorted(tuple(pu['position']) for pu in chapter['player_units']))

    def test_the_twins_reinforcements_arrive_on_their_eventscript_turns(self):
        waves = {b.arrives for b in dm.vanilla_bodies('FE8 Ch5')}
        self.assertEqual(waves, {1, 2, 6, 8})


class FirstContact(unittest.TestCase):
    def _board(self, bodies):
        return dm.Board(None, terrain=plains(), fielded=bodies)

    def test_a_pursuer_closes_its_movement_each_phase(self):
        # 10 tiles from the front at Mov 5: in lance range (1) after 9 tiles, phase 2.
        pursuer = body((10, 1))
        self.assertEqual(tl.first_contact(self._board([pursuer]), pursuer, [(0, 1)]), 2)

    def test_a_statue_out_of_range_never_makes_contact(self):
        statue = body((10, 1), shape='statue')
        self.assertIsNone(tl.first_contact(self._board([statue]), statue, [(0, 1)]))

    def test_a_reinforcement_cannot_make_contact_before_it_arrives(self):
        late = body((2, 1), arrives=4)
        self.assertEqual(tl.first_contact(self._board([late]), late, [(0, 1)]), 4)


class OurBodiesMove(unittest.TestCase):
    def test_a_bag_member_moves_as_itself(self):
        bag = {'composition': ['fighter', 'cavalier'], 'positions': [[0, 0], [1, 0]]}
        self.assertEqual(dm._movement(bag, 1), pp.class_movement('cavalier'))

    def test_a_reskin_slot_moves_as_the_class_it_clones(self):
        # ch03's brigand-brute is a campaign slot cloned from CLASS_BRIGAND.
        brute = {'class': 'brigand', 'deploy_class': 'brigand-brute'}
        self.assertEqual(dm._movement(brute, 0), pp.class_movement('brigand'))

    def test_each_class_walks_its_own_table(self):
        # `.pMovCostTable` is a { Normal, Rain, Snow } list; reading it as a bare name matched
        # nothing, so every class walked the foot table and the two tests above held vacuously.
        self.assertEqual(pp.class_movement('brigand')[0], 'TerrainTable_MovCost_BrigandNormal')
        self.assertEqual(pp.class_movement('pegasus-knight'), ('TerrainTable_MovCost_FlyNormal', 7))
        self.assertNotEqual(pp.class_movement('cavalier')[0], pp.class_movement('fighter')[0])

    def test_a_lone_position_is_a_body(self):
        # Bosses are written `position:`; the boards read `positions:` alone and lost every one.
        import chapter_schema
        self.assertEqual(chapter_schema.entry_tiles({'position': [3, 4]}), [[3, 4]])
        self.assertEqual(chapter_schema.entry_tiles({'positions': [[1, 1], [2, 2]]}),
                         [[1, 1], [2, 2]])
        ids = {b.id for b in dm.Board(pp.load_chapter('ch02'), None, every_mode=True).bodies}
        self.assertTrue({'raider-captain', 'raider-bruiser'} <= ids)

    def test_vanilla_ch2s_brigands_cross_its_peaks(self):
        # The turn-3 pair spawns on the peaks at (0,9)/(1,9); on the foot table it never moved.
        board = dm.Board(None, terrain=dif.vanilla_terrain('FE8 Ch2'),
                         fielded=dm.vanilla_bodies('FE8 Ch2'))
        front = dif.vanilla_front('FE8 Ch2')
        self.assertTrue(all(tl.first_contact(board, b, front) is not None for b in board.bodies))


class OneReaderPerForce(unittest.TestCase):
    """#510 step 7: the board and the combat read index ONE list of bodies per side, so an
    engagement's members are positions in `party_matchup`'s force. Each check is against a
    reader the parity read does not go through."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _fields(self, chapter, mode):
        return dif.arriving_fields(pp.load_chapter(chapter), self.CAMPAIGN, mode)

    @staticmethod
    def _line(u):
        return (u.name, u.hp, u.pow, u.skl, u.spd, u.df, u.res, u.weapon.name)

    def test_the_force_is_the_mode_shifted_force(self):
        # ch07's Difficult shift moves its lines: a force read without it would still align.
        chapter = pp.load_chapter('ch07')
        shifts = dif.inject.chapter_settings.chapter_difficulty_shifts(chapter)
        fields = self._fields('ch07', 'difficult')
        self.assertEqual([self._line(u) for u, _t in fields['our_force']],
                         [self._line(u) for _e, u in dif.chapter_units(chapter, 'difficult',
                                                                         shifts)])

    def test_our_board_is_the_force_less_its_unarmed_bodies(self):
        # ch06's two menders carry no modeled weapon: on the map, in neither list.
        fields = self._fields('ch06', 'normal')
        armed = [b for b in dm.bodies(pp.load_chapter('ch06'), 'normal', every_mode=True)
                 if b.arms]
        self.assertEqual([(b.id, b.index) for b in fields['our_bodies']],
                         [(b.id, b.index) for b in armed])
        self.assertEqual([self._line(b.unit) for b in fields['our_bodies']],
                         [self._line(u) for u, _t in fields['our_force']])
        self.assertEqual([t for _u, t in fields['our_force']],
                         [dif.ai_target.combat_weight_table(b.ai) for b in armed])

    def test_the_twins_board_is_its_force(self):
        fields = self._fields('ch06', 'normal')
        self.assertEqual([self._line(b.unit) for b in fields['van_bodies']],
                         [self._line(u) for u, _ai in dif.vanilla_enemy_bodies('FE8 Ch6',
                                                                                 'normal')])

    def test_an_unwritten_chapter_is_read_as_its_twin_only(self):
        # ADR 0363: a planned chapter does not exist for the difficulty math. The report
        # prints its twin's numbers and never walks its draft roster.
        out = io.StringIO()
        with mock.patch.object(dif, 'chapter_force', side_effect=AssertionError('read draft')), \
                contextlib.redirect_stdout(out):
            dif.report('rime-of-the-frostmaiden', 'ch08')
        self.assertIn("vanilla twin FE8 Ch8's", out.getvalue())

    def test_a_written_chapter_places_every_body(self):
        chapter = copy.deepcopy(pp.load_chapter('ch04'))
        entry = next(e for e in chapter['enemy_units'] if e.get('count'))
        del entry['positions']
        with self.assertRaisesRegex(ValueError, 'no position'):
            dm.bodies(chapter, 'normal', every_mode=True)


if __name__ == '__main__':
    unittest.main()
