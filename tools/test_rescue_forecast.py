#!/usr/bin/env python3
"""Tests for tools/rescue_forecast.py -- the rescue-fuse forecast + guard (#367, #26).

The oracle is ch06's own measured numbers: boat-east's four javelin-range firing cells and
one melee door, boat-west's three and one, and the two instrumented runs on #26 that
`danger_map` is calibrated against (ADR 0312). Every one is pinned against the REAL ch06
chapter YAML + compiled map, never a synthetic stand-in.

Run: python3 tools/test_rescue_forecast.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import difficulty as dif                                              # noqa: E402
import map_placement_preview as pp                                    # noqa: E402
import rescue_forecast as rf                                          # noqa: E402


def ch06():
    return pp.load_chapter('ch06')


class FiringCells(unittest.TestCase):
    """Every cell within weapon range that a foot unit can stand on -- the throughput
    bound: at most one attacker per cell per phase."""

    def setUp(self):
        self.terrain = pp.terrain_grid(ch06())

    def test_boat_east_javelin_range_cells_are_exactly_the_measured_four(self):
        cells = pp.firing_cells(self.terrain, (17, 12), 2)
        self.assertEqual(sorted(cells), sorted([(15, 12), (17, 10), (17, 13), (17, 14)]))

    def test_boat_east_melee_range_is_only_its_declared_door(self):
        cells = pp.firing_cells(self.terrain, (17, 12), 1)
        self.assertEqual(cells, [(17, 13)])

    def test_boat_west_javelin_range_cells_are_exactly_the_measured_three(self):
        cells = pp.firing_cells(self.terrain, (4, 17), 2)
        self.assertEqual(sorted(cells), sorted([(2, 17), (4, 18), (4, 19)]))

    def test_boat_west_melee_range_is_only_its_declared_door(self):
        cells = pp.firing_cells(self.terrain, (4, 17), 1)
        self.assertEqual(cells, [(4, 18)])

    def test_a_cell_ON_the_target_is_never_a_firing_cell(self):
        """Distance 0 is the target's own tile, not a place to stand and shoot from."""
        cells = pp.firing_cells(self.terrain, (17, 12), 2)
        self.assertNotIn((17, 12), cells)


class TargetCombatant(unittest.TestCase):
    """A `rescue_boats:` entry's fighting stats resolve through `difficulty._one_enemy` --
    the SAME path every other enemy in the codebase resolves through -- rather than a
    hand-rolled `_class_base` + `_stats_to_combatant` that skips autolevel, class tags and
    a personal line. ch06's boats are level-1, no-personal `CLASS_FLEET`, so the bypass was
    a no-op there; these pin the three things it would get wrong the day a boat entry
    declares any of them."""

    def test_a_boats_stats_come_from_ONE_of_enemy(self):
        boat = {'id': 'hull', 'class': 'fleet'}
        got = rf.target_combatant(boat)
        want = dif._one_enemy('hull', 'fleet', 1, None)
        self.assertEqual((got.hp, got.pow, got.skl, got.spd, got.df, got.res, got.lck,
                          got.con), (want.hp, want.pow, want.skl, want.spd, want.df,
                                     want.res, want.lck, want.con))

    def test_a_declared_level_is_autoleveled_not_ignored(self):
        """The exact bug: a naive class-base read never grows past L1."""
        l1 = rf.target_combatant({'id': 'hull', 'class': 'armor-knight'})
        l10 = rf.target_combatant({'id': 'hull', 'class': 'armor-knight', 'level': 10})
        self.assertGreater(l10.hp, l1.hp)

    def test_a_class_carrying_an_effectiveness_tag_keeps_it(self):
        """`fe_combat` reads `tags` to resolve effective weapons (a Rapier vs `armor`). A
        hand-rolled Combatant that skips `CLASS_TAGS` is invisible to that -- silently
        wrong, not merely incomplete."""
        boat = rf.target_combatant({'id': 'hull', 'class': 'armor-knight'})
        self.assertIn('armor', boat.tags)

    def test_a_boat_never_carries_a_weapon(self):
        """The one thing the bypass got right on purpose: a rescue target never attacks
        back, so `_one_enemy` is called with `weapon=None` regardless of the boat's class."""
        boat = rf.target_combatant({'id': 'hull', 'class': 'fleet'})
        self.assertIsNone(boat.weapon)


class PursuerForecast(unittest.TestCase):
    """The whole orchestration, end to end, against the chapter YAML -- exactly what the
    guard and `make chapter CH=ch06` read. The numbers are the calibrated model's; run 2
    saw the thrower's first throw on phase 2, the crab on the west door from phase 2, the
    east hull afloat at turn 12 and the west sunk on turn 5."""

    @classmethod
    def setUpClass(cls):
        cls.rows = {(r.enemy_id, r.boat_id): r for r in rf.chapter_forecast(ch06())}

    def test_merfolk_thrower_engages_boat_east_on_turn_2(self):
        row = self.rows[('merfolk-thrower', 'boat-east')]
        self.assertEqual(row.arrival_turn, 2)
        self.assertAlmostEqual(row.damage_per_phase, 2.62, places=2)    # 2RN javelin
        self.assertLessEqual(row.sink_low, 12)
        self.assertGreater(row.sink_high, 12)          # afloat at 12 is inside the band

    def test_tentacruel_engages_boat_west_on_turn_2_and_sinks_on_its_declared_8(self):
        # The 28 HP hull (ADR 0313). Run 2's 19 HP hull is danger_map's calibration case.
        row = self.rows[('tentacruel', 'boat-west')]
        self.assertEqual(row.arrival_turn, 2)
        self.assertAlmostEqual(row.damage_per_phase, 2.73, places=2)
        self.assertEqual(row.sink_expected, 8)
        self.assertGreaterEqual(row.sink_low, 6)       # foot arrives on turn 6

    def test_an_engaged_pursuer_never_reaches_the_other_hull(self):
        self.assertIsNone(self.rows[('merfolk-thrower', 'boat-west')].arrival_turn)
        self.assertIsNone(self.rows[('tentacruel', 'boat-east')].arrival_turn)

    def test_a_difficult_only_pursuer_is_still_forecast(self):
        import copy
        chap = copy.deepcopy(ch06())
        crab = next(e for e in chap['enemy_units'] if e.get('id') == 'tentacruel')
        crab['hard_mode_only'] = True
        rows = [r for r in rf.chapter_forecast(chap) if r.enemy_id == 'tentacruel']
        self.assertTrue(any(r.arrival_turn == 2 for r in rows))

    def test_a_civilian_sparing_pursuer_never_arrives(self):
        import copy
        chap = copy.deepcopy(ch06())
        crab = next(e for e in chap['enemy_units'] if e.get('id') == 'tentacruel')
        crab['ai_override'] = {'ai': '{0x8, 0x0, 0x0, 0x0}', 'why': 'test'}
        rows = [r for r in rf.chapter_forecast(chap) if r.enemy_id == 'tentacruel']
        self.assertTrue(rows and all(r.arrival_turn is None for r in rows))


if __name__ == '__main__':
    unittest.main()
