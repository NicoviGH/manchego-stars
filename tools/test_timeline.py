#!/usr/bin/env python3
"""Tests for tools/timeline.py -- instrument v2's layer 2 (#430 step 2b). Run:

    python3 tools/test_timeline.py
"""
import collections
import contextlib
import copy
import dataclasses
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

    def test_a_charge_after_one_turn_waits_its_first_turn(self):
        # AI_B_12 (cp_data.c): AI_NOP_0E for a turn, then pursue. 12 tiles out at Mov 5: a
        # pursuer strikes on phase 3, the waiter on phase 4.
        plain = body((12, 1))
        waiter = dataclasses.replace(plain, ai=(0x00, 0x12, 0x0C, 0x00))
        self.assertEqual(tl.first_contact(self._board([plain]), plain, [(0, 1)]), 3)
        self.assertEqual(tl.first_contact(self._board([waiter]), waiter, [(0, 1)]), 4)

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


class Engagements(unittest.TestCase):
    """#510 step 7: the sets of enemies the party faces together (ADR 0364)."""
    FRONT = [(0, 1)]
    REACH = (1,)

    def _read(self, bodies, w=24, h=3):
        board = dm.Board(None, terrain=plains(w, h), fielded=bodies)
        return tl.engagements(board, self.FRONT, soldier('party'), self.REACH)

    def _members(self, read, kind):
        return sorted(sorted(e.members) for e in read if e.kind == kind)

    def test_pursuers_that_reach_the_front_on_one_phase_are_one_wave(self):
        # A front of three: 10 tiles out at Mov 5 strikes on phase 2, two of them side by
        # side; 16 tiles out, phase 3.
        bodies = [body((10, 0), index=0), body((10, 2), index=1), body((16, 1), index=2)]
        board = dm.Board(None, terrain=plains(24, 3), fielded=bodies)
        read = tl.engagements(board, [(0, 0), (0, 1), (0, 2)], soldier('party'), self.REACH)
        self.assertEqual([(e.phase, sorted(e.members)) for e in read if e.kind == 'wave'],
                         [(2, [0, 1]), (3, [2])])
        self.assertEqual(self._members(read, 'pocket'), [])

    def test_a_striker_without_a_free_firing_tile_waits_a_phase(self):
        # One party tile, one tile beside it the walkers can reach on phase 2: the first in AI
        # order takes it, and the second strikes from the next tile in on phase 3 (ch04waves).
        bodies = [body((10, 1), index=0), body((11, 1), index=1)]
        board = dm.Board(None, terrain=plains(24, 3), fielded=bodies, blocked=self.FRONT)
        self.assertEqual(tl.front_contacts(board, self.FRONT), {0: 2, 1: 3})

    def test_a_tie_in_ai_order_goes_to_the_unit_that_loaded_first(self):
        # A unit's table slot is where it LOADED: a turn-3 reinforcement listed first still
        # moves after a turn-1 unit of equal priority (vanilla Ch2's raiders and Bazba).
        # Both can reach the one free tile beside the party, (1, 1), on phase 2.
        late = body((5, 1), arrives=2, index=0)
        early = body((10, 1), index=1)
        board = dm.Board(None, terrain=plains(24, 3), fielded=[late, early], blocked=self.FRONT)
        self.assertEqual(tl.front_contacts(board, self.FRONT, 8), {0: 3, 1: 2})

    def test_ai_order_is_mov_then_reach_then_table(self):
        # SortAiUnitList: ascending Mov + 20 melee / 40 ranged, stable on the table order.
        slow, fast = body((0, 0), mov=4, index=0), body((0, 0), mov=6, index=1)
        bow = body((0, 0), mov=4, weapon='iron-bow', index=2)
        self.assertEqual(sorted([fast, bow, slow], key=tl.ai_priority), [slow, fast, bow])

    def test_a_lone_waiting_enemy_is_a_fight_of_one(self):
        read = self._read([body((12, 1), shape='striker', index=0)])
        self.assertEqual(self._members(read, 'pocket'), [[0]])

    def test_neighbours_that_cover_every_approach_are_pulled_together(self):
        # Two strikers side by side: every tile next to either is in the other's step.
        read = self._read([body((12, 1), shape='striker', index=0),
                           body((13, 1), shape='striker', index=1)])
        self.assertEqual(self._members(read, 'pocket'), [[0, 1], [0, 1]])

    def test_the_party_pulls_from_the_tile_the_others_cannot_reach(self):
        # A Mov-1 striker four tiles east of a statue: the statue's west side is out of its step.
        read = self._read([body((10, 1), shape='statue', index=0),
                           body((14, 1), shape='striker', mov=1, index=1)])
        statue = next(e for e in read if 0 in e.members)
        self.assertEqual(sorted(statue.members), [0])
        self.assertEqual(statue.tile, (9, 1))

    def test_an_unarmed_or_errand_body_is_in_nothing(self):
        unarmed = dm.Body('e', 0, (12, 1), 'striker', 0x00, 1, FOOT, 5, ())
        errand = body((14, 1), shape='own-errand', index=1)
        self.assertEqual(self._read([unarmed, errand]), [])

    def test_each_pocket_is_read_when_its_own_body_arrives(self):
        # A turn-1 striker is pulled before a turn-4 one standing beside it has arrived.
        read = self._read([body((12, 1), shape='striker', index=0),
                           body((13, 1), shape='striker', arrives=4, index=1)])
        first = next(e for e in read if 0 in e.members and e.phase == 1)
        self.assertEqual(sorted(first.members), [0])
        self.assertTrue(any(e.phase == 4 and e.members == {0, 1} for e in read))

    def test_a_pull_tile_the_party_cannot_walk_to_is_no_pull_tile(self):
        # The statue's one tile out of the striker's step, (12,2), is ringed by water, so the
        # party can only pull from (11,1) or (12,0), both in the striker's step: a pocket of two.
        terrain = plains(24, 3)
        water = pp.TERRAIN['TERRAIN_WATER']
        for x, y in ((13, 0), (13, 1), (13, 2), (11, 2)):
            terrain[y][x] = water
        bodies = [body((12, 1), shape='statue', index=0),
                  body((10, 0), shape='striker', mov=1, index=1)]
        board = dm.Board(None, terrain=terrain, fielded=bodies)
        statue = next(e for e in tl.engagements(board, self.FRONT, soldier('party'), (1,))
                      if 0 in e.members)
        self.assertEqual(sorted(statue.members), [0, 1])

    def test_a_pursuer_that_never_reaches_the_front_waits_to_be_fetched(self):
        # A front it can never reach (off the map): it waits for the party to fetch it.
        boxed = body((12, 1), mov=5, index=0)
        board = dm.Board(None, terrain=plains(24, 3), fielded=[boxed])
        read = tl.engagements(board, [(0, 99)], soldier('party'), self.REACH)
        self.assertEqual([(e.kind, sorted(e.members)) for e in read], [('pocket', [0])])


class EngagementsOnOurMaps(unittest.TestCase):
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _read(self, chapter_id, mode='normal'):
        chapter = pp.load_chapter(chapter_id)
        fields = dif.arriving_fields(chapter, self.CAMPAIGN, mode)
        board, front = tl.boards(chapter, fields)['ours']
        return board, tl.engagements(board, front, soldier('party'), (1, 2))

    def test_ch03_is_all_waiting_enemies(self):
        # Neither ch03 nor its twin ever reaches the deploy front (ADR 0317's first reading).
        _board, read = self._read('ch03')
        self.assertFalse([e for e in read if e.kind == 'wave'])
        self.assertTrue([e for e in read if e.kind == 'pocket'])

    def test_ch04s_waves_are_its_pursuers_strikes_on_the_front(self):
        board, read = self._read('ch04')
        struck = tl.front_contacts(board, tl.our_front(pp.load_chapter('ch04')),
                                   dm.ENGAGE_HORIZON)
        want = collections.Counter(struck[k] for k, b in enumerate(board.bodies)
                                   if dm._moves_like(b) == 'pursuer' and struck[k] is not None)
        self.assertEqual({e.phase: len(e.members) for e in read if e.kind == 'wave'},
                         dict(want))


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

    def test_an_unwritten_chapter_is_not_read(self):
        # ADR 0365: a chapter is read as it is built. The report of a planned one walks
        # neither its draft roster nor its twin's force.
        out = io.StringIO()
        with mock.patch.object(dif, 'chapter_force', side_effect=AssertionError('read draft')), \
                mock.patch.object(dm, 'vanilla_bodies', side_effect=AssertionError('read twin')), \
                contextlib.redirect_stdout(out):
            dif.report('rime-of-the-frostmaiden', 'ch08')
        self.assertIn('NOT WRITTEN YET', out.getvalue())
        self.assertNotIn('threat', out.getvalue())

    def test_a_written_chapter_places_every_body(self):
        chapter = copy.deepcopy(pp.load_chapter('ch04'))
        entry = next(e for e in chapter['enemy_units'] if e.get('count'))
        del entry['positions']
        with self.assertRaisesRegex(ValueError, 'no position'):
            dm.bodies(chapter, 'normal', every_mode=True)


if __name__ == '__main__':
    unittest.main()
