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
import difficulty as dif                                             # noqa: E402
import map_placement_preview as pp                                   # noqa: E402
import rescue_forecast as rf                                         # noqa: E402
from check import RESCUE_SAFE_ACTIONS                                # noqa: E402

EAST, WEST = (17, 12), (4, 17)


def ch06():
    return pp.load_chapter('ch06')


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

    def test_hit_is_rolled_on_two_rns(self):
        # ADR 0270: the crab's 47 displayed into the west hull's cover is 45% true.
        self.assertAlmostEqual(dm.true_hit(47), 0.45, delta=0.01)
        self.assertGreater(dm.true_hit(80), 0.90)
        self.assertEqual((dm.true_hit(0), dm.true_hit(100)), (0.0, 1.0))

    def test_venin_weapons_poison_and_still_cut(self):
        self.assertTrue({'venin-claw', 'venin-axe'} <= dm.poison_weapons())
        chap = ch06()
        crab = next(a for a in on(hull_board(chap), chap, WEST, 2) if a.body.id == 'ice-crab')
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
        for tile, pursuer in ((EAST, 'merfolk-thrower'), (WEST, 'ice-crab')):
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
        crab_on_east = lambda board: any(a.body.id == 'ice-crab'
                                         for a in on(board, self.chap, EAST, 12))
        self.assertFalse(crab_on_east(self.board))
        self.assertTrue(crab_on_east(dm.Board(self.chap)))


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
        self.chap = ch06()
        self.board = hull_board(self.chap)

    def share(self, tile, by):
        turns = dm.sink_turns(self.board, tile, hull(self.chap, tile), 12, RESCUE_SAFE_ACTIONS)
        return sum(1 for t in turns if t is not None and t <= by) / len(turns)

    def test_east_is_often_still_afloat_at_turn_12(self):
        self.assertTrue(0.1 < 1 - self.share(EAST, 12) < 0.5)

    def test_west_sinking_by_turn_5_is_ordinary_once_poison_counts(self):
        # Without poison the crab needs four connections in four phases: under 5%.
        self.assertTrue(0.25 < self.share(WEST, 5) < 0.6)


if __name__ == '__main__':
    unittest.main()
