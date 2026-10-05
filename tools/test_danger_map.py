#!/usr/bin/env python3
"""Tests for tools/danger_map.py (#430 step 1, #367 proposal 2).

The oracle is the two instrumented ch06 runs on #26, never a synthetic map: the instrument
is only worth trusting if it reproduces what the cartridge did.

  * Run 1 (before #366): the east hull took 11 on enemy phase 1 from three units that walked
    to it -- a soldier onto the door, an armour knight with a javelin, an archer.
  * Run 2 (#366, the ch06 that ships): nothing touches a hull on phase 1; the thrower throws
    at the east hull from phase 2 and it is still afloat at turn 12; the crab works the west
    door from phase 2 and the west hull sinks on turn 5.

Run: python3 tools/test_danger_map.py
"""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import danger_map as dm                                              # noqa: E402
import dataclasses                                                   # noqa: E402
import difficulty as dif                                             # noqa: E402
import fe_combat as fc                                               # noqa: E402
import map_placement_preview as pp                                   # noqa: E402
import rescue_forecast as rf                                         # noqa: E402
from check import RESCUE_SAFE_ACTIONS                                # noqa: E402

EAST, WEST = (17, 12), (4, 17)


def ch06():
    return pp.load_chapter('ch06')


def run_2():
    """ch06 as run 2 played it: before ADR 0313's west hull line, on CLASS_FLEET's 19 HP."""
    chap = copy.deepcopy(ch06())
    for boat in chap['rescue_boats']:
        boat.pop('personal', None)
    return chap


def before_366():
    """ch06 without #366's fix: the ten strikers it moved onto AI_A_08 take their donor's
    plain ActionInRange back, which is what run 1 played."""
    chap = copy.deepcopy(ch06())
    for enemy in chap['enemy_units']:
        if str((enemy.get('ai_override') or {}).get('ai', '')).startswith('{0x8'):
            del enemy['ai_override']
    return chap


def hull(chap, tile):
    return rf.target_combatant(next(b for b in chap['rescue_boats'] if tuple(b['tile']) == tile))


def hull_board(chap):
    return dm.Board(chap, targets=[b['tile'] for b in chap['rescue_boats']],
                    spared_by=RESCUE_SAFE_ACTIONS)


def on(board, chap, tile, phase):
    return dm.attacks_on(board, tile, hull(chap, tile), phase, RESCUE_SAFE_ACTIONS)


class TheEnginesStrike(unittest.TestCase):

    def test_venin_weapons_poison_and_still_cut(self):
        self.assertTrue({'venin-claw', 'venin-axe'} <= dm.poison_weapons())
        chap = ch06()
        crab = next(a for a in on(hull_board(chap), chap, WEST, 2) if a.body.id == 'tentacruel')
        self.assertTrue(crab.strike.poisons)
        self.assertGreater(crab.strike.damage, 0)


class WhoReachesTheHulls(unittest.TestCase):
    """Run 2's pathing, which a scenario asserts every run (ADR 0270)."""

    def setUp(self):
        self.chap = ch06()
        self.board = hull_board(self.chap)

    def test_nothing_reaches_a_hull_on_phase_1(self):
        for tile in (EAST, WEST):
            self.assertEqual(on(self.board, self.chap, tile, 1), [])

    def test_each_hull_is_its_declared_pursuers_from_phase_2(self):
        for tile, pursuer in ((EAST, 'merfolk-thrower'), (WEST, 'tentacruel')):
            for phase in (2, 6, 12):
                self.assertEqual([a.body.id for a in on(self.board, self.chap, tile, phase)],
                                 [pursuer])

    def test_a_civilian_sparing_striker_still_hits_a_player_unit_there(self):
        # AI_A_08 spares the hulls, not the party: the same tile is dangerous to marty.
        spared = on(self.board, self.chap, EAST, 1)
        marty = next(u for u in dif.load_field('rime-of-the-frostmaiden', 'ch06',
                                               leveled=True)[1] if u.name == 'marty')
        self.assertEqual(spared, [])
        self.assertTrue(dm.attacks_on(dm.Board(self.chap), (17, 13), marty, 1))

    def test_an_engaged_pursuer_does_not_also_cross_to_the_other_hull(self):
        # The crab works the west door to the end of run 2; the unconstrained danger zone
        # walks it on to the east hull as well.
        crab_on_east = lambda board: any(a.body.id == 'tentacruel'
                                         for a in on(board, self.chap, EAST, 12))
        self.assertFalse(crab_on_east(self.board))
        self.assertTrue(crab_on_east(dm.Board(self.chap)))


class Engagement(unittest.TestCase):

    def test_a_second_weapons_reach_does_not_erase_the_firsts(self):
        # A sword-and-bow pursuer that can stand only on the west door (mov 0) engages on
        # phase 1 with the sword; the bow's minimum range must not take the door away.
        board = hull_board(ch06())
        unit = board.bodies[0].arms[0]
        probe = dm.Body('probe', 0, (4, 18), 'pursuer', 0x00, 1,
                        'TerrainTable_MovCost_CommonT1Normal', 0,
                        tuple(dataclasses.replace(unit, weapon=fc.W[w])
                              for w in ('iron-sword', 'iron-bow')))
        self.assertEqual(board.engaged(probe), 1)


class TheMob(unittest.TestCase):
    """Run 1: without #366's fix three units walk to the east hull on phase 1."""

    def setUp(self):
        self.chap = before_366()
        self.attacks = on(hull_board(self.chap), self.chap, EAST, 1)

    def test_three_attackers_on_phase_1(self):
        self.assertEqual(len(self.attacks), 3)

    def test_the_archer_walks_through_its_own_line(self):
        # Reds pass through reds (MapFloodCoreStep's bit-0x80 test). Blocking on red bodies
        # stopped the archer short of (17,14), where run 1 recorded it.
        self.assertIn('merfolk-bow', [a.body.id for a in self.attacks])

    def test_one_door_holds_one_melee_attacker(self):
        melee = [a for a in self.attacks if a.body.arms and all(
            arm.weapon.rng == (1, 1) for arm in a.body.arms)]
        self.assertLessEqual(len(melee), 1)


class TheFuses(unittest.TestCase):
    """Run 2's two outcomes must land inside the forecast, not on its tail."""

    def setUp(self):
        self.chap = run_2()
        self.board = hull_board(self.chap)

    def share(self, tile, by):
        turns = dm.sink_turns(self.board, tile, hull(self.chap, tile), 12, RESCUE_SAFE_ACTIONS)
        return sum(1 for t in turns if t is not None and t <= by) / len(turns)

    def test_east_is_often_still_afloat_at_turn_12(self):
        self.assertTrue(0.1 < 1 - self.share(EAST, 12) < 0.5)

    def test_west_sinking_by_turn_5_is_ordinary_once_poison_counts(self):
        # Without poison the crab needs four connections in four phases: under 5%.
        self.assertTrue(0.25 < self.share(WEST, 5) < 0.6)


class VanillasFootSlack(unittest.TestCase):
    """ADR 0313: the ch06 that ships keeps vanilla Ch6's promise -- foot reaches the west door
    (turn 6) before the hull sinks, about nine runs in ten -- and its median is the declared 8."""

    def test_the_west_hull_outlasts_foot_and_sinks_on_its_declared_turn(self):
        chap = ch06()
        board = hull_board(chap)
        turns = dm.sink_turns(board, WEST, hull(chap, WEST), 20, RESCUE_SAFE_ACTIONS)
        early = sum(1 for t in turns if t is not None and t <= 5) / len(turns)
        self.assertLess(early, 0.1)
        self.assertEqual(dm.percentile(turns, 50),
                         next(b['declared_fuse'] for b in chap['rescue_boats']
                              if tuple(b['tile']) == WEST))


if __name__ == '__main__':
    unittest.main()
