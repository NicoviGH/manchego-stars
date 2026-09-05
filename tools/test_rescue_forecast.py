#!/usr/bin/env python3
"""Tests for tools/rescue_forecast.py -- the rescue-fuse forecast + guard (#367, #26).

The oracle here is ch06's own measured numbers (given, not re-derived): boat-east's four
javelin-range firing cells and one melee door, boat-west's three and one, merfolk-thrower's
2.76 dmg/phase and total inability to reach a firing cell on the contested snapshot, and
ice-crab's 2.82 dmg/phase, turn-2 arrival, and ~turn-9 forecast sink against a declared 8.
Every one of these is pinned against the REAL ch06 chapter YAML + compiled map, never a
synthetic stand-in, because the whole value of this tool is that it reproduces a chapter
nobody hand-checked correctly the first time.

Run: python3 tools/test_rescue_forecast.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fe_combat as fc                                                # noqa: E402
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
        cells = rf.firing_cells(self.terrain, (17, 12), 2)
        self.assertEqual(sorted(cells), sorted([(15, 12), (17, 10), (17, 13), (17, 14)]))

    def test_boat_east_melee_range_is_only_its_declared_door(self):
        cells = rf.firing_cells(self.terrain, (17, 12), 1)
        self.assertEqual(cells, [(17, 13)])

    def test_boat_west_javelin_range_cells_are_exactly_the_measured_three(self):
        cells = rf.firing_cells(self.terrain, (4, 17), 2)
        self.assertEqual(sorted(cells), sorted([(2, 17), (4, 18), (4, 19)]))

    def test_boat_west_melee_range_is_only_its_declared_door(self):
        cells = rf.firing_cells(self.terrain, (4, 17), 1)
        self.assertEqual(cells, [(4, 18)])

    def test_a_cell_ON_the_target_is_never_a_firing_cell(self):
        """Distance 0 is the target's own tile, not a place to stand and shoot from."""
        cells = rf.firing_cells(self.terrain, (17, 12), 2)
        self.assertNotIn((17, 12), cells)


class ArrivalToFiringCells(unittest.TestCase):
    """The clock's first half: does a pursuer even get a shot, and when.

    Pinned against the exact ch06 finding (#26): the east pursuer's own allies cork every
    one of its four firing cells on the contested (turn-1-blocked) snapshot, so its declared
    fuse describes a unit that never arrives; the west pursuer reaches its one door on turn 2.
    """

    def setUp(self):
        self.chap = ch06()
        self.terrain = pp.terrain_grid(self.chap)
        self.blocked = pp.enemy_bodies(self.chap)

    def test_merfolk_thrower_cannot_reach_any_east_firing_cell(self):
        cells = rf.firing_cells(self.terrain, (17, 12), 2)
        table, mov = pp.class_movement('soldier')
        arrival = rf.arrival_to_cells(self.terrain, (14, 9), table, mov, cells, self.blocked)
        self.assertIsNone(arrival)

    def test_ice_crab_reaches_its_door_on_turn_2(self):
        cells = rf.firing_cells(self.terrain, (4, 17), 1)
        table, mov = pp.class_movement('bael')
        arrival = rf.arrival_to_cells(self.terrain, (7, 20), table, mov, cells, self.blocked)
        self.assertEqual(arrival, 2)

    def test_an_empty_cell_list_never_arrives(self):
        table, mov = pp.class_movement('bael')
        self.assertIsNone(rf.arrival_to_cells(self.terrain, (7, 20), table, mov, [], set()))

    def test_the_source_itself_may_be_a_firing_cell(self):
        table, mov = pp.class_movement('bael')
        arrival = rf.arrival_to_cells(self.terrain, (7, 20), table, mov, [(7, 20)], set())
        self.assertEqual(arrival, 1)


def _hull_on_forest():
    """CLASS_FLEET's real base stats (19 HP, 5 Def), fighting on FOREST (+1 Def / +20 avoid)
    -- the oracle's own combatant, resolved the same way `difficulty.on_terrain` resolves
    any defender."""
    import difficulty as dif
    hull = fc.Combatant('hull', hp=19, pow=1, skl=1, spd=2, df=5, res=0, lck=0, con=25,
                        weapon=None)
    return dif.on_terrain(hull, 'TERRAIN_FOREST')          # (combatant, terrain_avoid)


class DamagePerPhase(unittest.TestCase):
    """Thin pass-through to fe_combat -- never a second combat model. Pinned against the
    two ch06 pursuers' measured numbers."""

    def test_merfolk_thrower_deals_the_measured_2_76(self):
        hull, avo = _hull_on_forest()
        thrower = fc.Combatant('merfolk-thrower', hp=25, pow=6, skl=2, spd=2, df=1, res=1,
                               lck=2, con=6, weapon=fc.W['javelin'])
        self.assertAlmostEqual(fc.damage_per_round(thrower, hull, avo), 2.76, places=2)

    def test_ice_crab_deals_the_measured_2_82(self):
        hull, avo = _hull_on_forest()
        crab = fc.Combatant('ice-crab', hp=25, pow=6, skl=3, spd=3, df=6, res=1, lck=0,
                            con=12, weapon=fc.W['venin-claw'])
        self.assertAlmostEqual(fc.damage_per_round(crab, hull, avo), 2.82, places=2)


class SinkBand(unittest.TestCase):
    """A rescue clock is a HIT RATE (decisions.md), so the sink turn is reported as a BAND.

    `sink_band` returns phases-from-arrival, not turns -- the caller adds the arrival turn.
    """

    def test_a_weaponless_attacker_never_sinks_anything(self):
        hull, avo = _hull_on_forest()
        nobody = fc.Combatant('nobody', hp=1, pow=0, skl=0, spd=0, df=0, res=0, lck=0,
                              con=1, weapon=None)
        self.assertIsNone(rf.sink_band(hull.hp, nobody, hull, avo))

    def test_zero_damage_against_the_target_never_sinks_it(self):
        hull, avo = _hull_on_forest()
        toothless = fc.Combatant('toothless', hp=10, pow=0, skl=0, spd=0, df=0, res=0,
                                 lck=0, con=1, weapon=fc.Weapon('nub', 0, 90, 0, 1, 'sword'))
        self.assertIsNone(rf.sink_band(hull.hp, toothless, hull, avo))

    def test_the_point_estimate_matches_hp_over_damage_per_phase(self):
        """The literal spec: forecast sink turn = arrival + HP / damage_per_phase. `expected`
        is that quantity (in phases, ceiling'd -- a turn is whole)."""
        import math
        hull, avo = _hull_on_forest()
        crab = fc.Combatant('ice-crab', hp=25, pow=6, skl=3, spd=3, df=6, res=1, lck=0,
                            con=12, weapon=fc.W['venin-claw'])
        band = rf.sink_band(hull.hp, crab, hull, avo)
        dpr = fc.damage_per_round(crab, hull, avo)
        self.assertEqual(band.expected, math.ceil(hull.hp / dpr))
        # The oracle: arrival(2) + this expected phase count lands turn 9.
        self.assertEqual(2 + band.expected, 9)

    def test_the_band_widens_around_the_point_estimate_never_narrows_to_it(self):
        hull, avo = _hull_on_forest()
        crab = fc.Combatant('ice-crab', hp=25, pow=6, skl=3, spd=3, df=6, res=1, lck=0,
                            con=12, weapon=fc.W['venin-claw'])
        band = rf.sink_band(hull.hp, crab, hull, avo)
        self.assertLessEqual(band.low, band.expected)
        self.assertGreaterEqual(band.high, band.expected)

    def test_the_low_bound_never_beats_every_hit_connecting(self):
        """No amount of luck sinks a hull faster than one hit per phase connecting every
        time -- the deterministic floor."""
        import math
        hull, avo = _hull_on_forest()
        crab = fc.Combatant('ice-crab', hp=25, pow=6, skl=3, spd=3, df=6, res=1, lck=0,
                            con=12, weapon=fc.W['venin-claw'])
        band = rf.sink_band(hull.hp, crab, hull, avo)
        dmg = fc.damage(crab, hull)
        hits = 2 if fc.doubles(crab, hull) else 1
        floor_phases = math.ceil(math.ceil(hull.hp / dmg) / hits)
        self.assertGreaterEqual(band.low, floor_phases)

    def test_a_declared_fuse_of_8_falls_inside_the_west_band(self):
        """The oracle's own sanity check: ch06's declared west fuse (turn 8) should sit
        inside the arrival + band this tool reports, or the design note and the model
        disagree about the same hull."""
        hull, avo = _hull_on_forest()
        crab = fc.Combatant('ice-crab', hp=25, pow=6, skl=3, spd=3, df=6, res=1, lck=0,
                            con=12, weapon=fc.W['venin-claw'])
        band = rf.sink_band(hull.hp, crab, hull, avo)
        arrival = 2
        self.assertLessEqual(arrival + band.low, 8)
        self.assertGreaterEqual(arrival + band.high, 8)

    def test_a_higher_hit_chance_narrows_the_band(self):
        """More certainty -> tighter spread. A sanity check on the shape of the model, not
        a fourth combat system: everything here is fe_combat's own hit/damage math."""
        hull, avo = _hull_on_forest()
        iffy = fc.Combatant('iffy', hp=25, pow=0, skl=0, spd=0, df=0, res=0, lck=0, con=20,
                            weapon=fc.Weapon('poke', 3, 40, 0, 1, 'sword'))
        sure = fc.Combatant('sure', hp=25, pow=0, skl=20, spd=0, df=0, res=0, lck=0, con=20,
                            weapon=fc.Weapon('poke', 3, 90, 0, 1, 'sword'))
        target = fc.Combatant('t', hp=20, pow=0, skl=0, spd=0, df=0, res=0, lck=0, con=1,
                              weapon=None)
        wide = rf.sink_band(target.hp, iffy, target, 0)
        narrow = rf.sink_band(target.hp, sure, target, 0)
        self.assertGreater(wide.high - wide.low, narrow.high - narrow.low)


class ConcurrentAttackerCap(unittest.TestCase):
    """The throughput bound generalised past one door: `ch06's two hulls each have exactly
    ONE melee door so this is not load-bearing there, but later chapters will have wider
    targets` -- so it is pinned on synthetic grids wide enough to exercise it, plus ch06's
    real single-door case."""

    def setUp(self):
        self.terrain = pp.terrain_grid(ch06())

    def test_ch06_boat_east_caps_melee_at_its_one_door(self):
        cap = rf.concurrent_attacker_cap(self.terrain, (17, 12), [1, 1, 1])
        self.assertEqual(cap, 1)

    def test_ch06_boat_east_caps_javelin_range_attackers_at_four(self):
        cap = rf.concurrent_attacker_cap(self.terrain, (17, 12), [2, 2, 2, 2, 2])
        self.assertEqual(cap, 4)

    def test_a_mixed_group_each_takes_its_own_cell(self):
        """One melee attacker (needs the one door) plus one range-2 attacker (any of four
        cells, one of which is the door) -- a correct MATCHING gives each its own cell."""
        cap = rf.concurrent_attacker_cap(self.terrain, (17, 12), [1, 2])
        self.assertEqual(cap, 2)

    def test_a_second_melee_attacker_with_no_other_cell_goes_unmatched(self):
        """Two melee attackers both need the ONE door; only one gets it. The two range-2
        attackers still get their own cells from the other three, so the matching is 3 of
        4, not 4 of 4 -- the melee slot is the bottleneck, not the whole group."""
        cap = rf.concurrent_attacker_cap(self.terrain, (17, 12), [1, 1, 2, 2])
        self.assertEqual(cap, 3)

    def test_no_attackers_is_a_cap_of_zero(self):
        self.assertEqual(rf.concurrent_attacker_cap(self.terrain, (17, 12), []), 0)


class PursuerForecast(unittest.TestCase):
    """The whole orchestration, end to end, against the chapter YAML -- exactly what the
    guard and `make chapter CH=ch06` read."""

    def setUp(self):
        self.chap = ch06()
        self.terrain = pp.terrain_grid(self.chap)

    def _entry(self, uid):
        import difficulty as dif
        return next(e for e in dif.chapter_roster_entries(self.chap) if e.get('id') == uid)

    def _boat(self, bid):
        return next(b for b in self.chap['rescue_boats'] if b['id'] == bid)

    def test_merfolk_thrower_never_engages_boat_east(self):
        row = rf.pursuer_forecast(self.chap, self.terrain, self._entry('merfolk-thrower'),
                                  0, self._boat('boat-east'))
        self.assertIsNone(row.arrival_turn)
        self.assertIsNone(row.sink_low)
        self.assertIsNone(row.sink_expected)
        self.assertIsNone(row.sink_high)

    def test_ice_crab_engages_boat_west_on_turn_2_and_sinks_around_9(self):
        row = rf.pursuer_forecast(self.chap, self.terrain, self._entry('ice-crab'),
                                  0, self._boat('boat-west'))
        self.assertEqual(row.arrival_turn, 2)
        self.assertAlmostEqual(row.damage_per_phase, 2.82, places=2)
        self.assertEqual(row.sink_expected, 9)
        self.assertLessEqual(row.sink_low, 8)
        self.assertGreaterEqual(row.sink_high, 8)


if __name__ == '__main__':
    unittest.main()
