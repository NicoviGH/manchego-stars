#!/usr/bin/env python3
"""Tests for tools/difficulty.py.

The pure metrics layer (durability / throughput / carry) is tested with synthetic
combatants and hand-computed oracles; the I/O layer is tested against real Ch1 data
(our cast's effective stats and the goblin enemy table). Run:

    python3 tools/test_difficulty.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fe_combat as fc
import difficulty as df


def combatant(name='u', hp=20, pow_=0, skl=8, spd=0, dfc=0, res=0, lck=0, con=20,
              weapon='iron-bow', tags=frozenset()):
    return fc.Combatant(name, hp=hp, pow=pow_, skl=skl, spd=spd, df=dfc, res=res,
                        lck=lck, con=con, weapon=fc.W[weapon], tags=tags)


class Durability(unittest.TestCase):
    def test_is_worst_case_rounds_to_be_downed(self):
        # unit (20 HP) vs two attackers: A deals 8/round (-> 2.5 rounds to down),
        # B deals 6/round (-> 3.33). Durability is the worst case: 2.5.
        unit = combatant('unit', hp=20, weapon='iron-lance')
        a = combatant('A', pow_=2, weapon='iron-bow')   # 2 + 6 mt, 100% hit -> 8/round
        b = combatant('B', pow_=0, weapon='iron-bow')   # 0 + 6 mt -> 6/round
        self.assertAlmostEqual(df.durability(unit, [a, b]), 2.5)

    def test_terrain_cover_raises_durability(self):
        unit = combatant('unit', hp=20, weapon='iron-lance')
        a = combatant('A', pow_=2, weapon='iron-bow')
        open_ground = df.durability(unit, [a], terrain_avoid=0)
        forest = df.durability(unit, [a], terrain_avoid=20)
        self.assertGreater(forest, open_ground)


class Throughput(unittest.TestCase):
    def test_party_throughput_sums_each_units_best_capped_kills(self):
        enemy = combatant('E', hp=20, weapon='iron-lance')
        one = combatant('one', pow_=20, weapon='iron-bow')   # 26 dmg >= 20 HP -> kpr 1.0
        half = combatant('half', pow_=4, weapon='iron-bow')  # 10 dmg -> kpr 0.5
        self.assertAlmostEqual(df.party_throughput([one, half], [enemy]), 1.5)

    def test_each_unit_counts_only_its_best_matchup(self):
        # A unit's contribution is its single best target, capped at 1.0 -- not summed
        # across every enemy (it can only kill one per round).
        e1 = combatant('E1', hp=20, weapon='iron-lance')
        e2 = combatant('E2', hp=20, weapon='iron-lance')
        one = combatant('one', pow_=20, weapon='iron-bow')   # one-rounds either -> 1.0
        self.assertAlmostEqual(df.party_throughput([one], [e1, e2]), 1.0)


class Carry(unittest.TestCase):
    def test_returns_best_unit_and_its_rounds_to_kill_the_boss(self):
        boss = combatant('boss', hp=40, dfc=10, weapon='iron-lance')
        strong = combatant('strong', pow_=20, weapon='iron-bow')  # 16 dmg -> 2.5 rounds
        weak = combatant('weak', pow_=4, weapon='iron-bow')       # can't pierce Def 10
        unit, rounds = df.carry(boss, [weak, strong])
        self.assertEqual(unit.name, 'strong')
        self.assertAlmostEqual(rounds, 2.5)


CAMPAIGN = 'rime-of-the-frostmaiden'


class PlayerStatResolution(unittest.TestCase):
    """Effective stats = class base + donor personal base (donor-base inheritance)."""

    def test_wolfram_inherits_gilliams_durable_line(self):
        # Armor Knight class base + Gilliam's real personal line (read from committed source,
        # since Gilliam's slot is build-overwritten): a tanky lord, not naked class.
        u = df.player_combatant(CAMPAIGN, 'wolfram')
        self.assertEqual((u.hp, u.pow, u.skl, u.spd, u.df, u.res, u.lck, u.con),
                         (25, 9, 6, 3, 9, 3, 3, 14))
        self.assertEqual(u.weapon.name, 'iron-lance')

    def test_marty_inherits_ewan_bases_not_shaman_naked(self):
        # The shaman base-donor special-case: bases come from Ewan (Spd +4, Lck +5),
        # NOT Knoll (lv9-inflated) and NOT naked Shaman class (Spd 2, Lck 0).
        u = df.player_combatant(CAMPAIGN, 'marty')
        self.assertEqual((u.hp, u.pow, u.skl, u.spd, u.df, u.res, u.lck, u.con),
                         (18, 4, 3, 6, 2, 4, 5, 7))
        self.assertEqual(u.weapon.name, 'flux')      # resolved via fe_base, not id

    def test_braulo_gets_garcias_personal_line(self):
        # Pirate base + Garcia's line lifts him well off naked class.
        u = df.player_combatant(CAMPAIGN, 'braulo')
        self.assertEqual((u.hp, u.pow, u.skl, u.spd, u.df, u.res, u.lck, u.con),
                         (27, 7, 7, 9, 6, 1, 3, 13))
        self.assertEqual(u.weapon.name, 'iron-axe')


class EnemyStatResolution(unittest.TestCase):
    def test_autolevel_projects_class_base_by_growths(self):
        # Armor Knight base + 3 levels of class growth (round half up): the lv4 boss.
        base = {'baseHP': 17, 'basePow': 5, 'baseSkl': 2, 'baseSpd': 0, 'baseDef': 9,
                'baseRes': 0, 'baseLck': 0, 'baseCon': 13}
        growths = {'growthHP': 80, 'growthPow': 40, 'growthSkl': 30, 'growthSpd': 15,
                   'growthDef': 28, 'growthRes': 20, 'growthLck': 25}
        proj = df.autolevel(base, growths, level=4)
        self.assertEqual((proj['baseHP'], proj['basePow'], proj['baseSkl'],
                          proj['baseSpd'], proj['baseDef'], proj['baseRes'],
                          proj['baseLck'], proj['baseCon']),
                         (19, 6, 3, 0, 10, 1, 1, 13))

    def test_line_goblin_axe_is_fighter_class_base_at_level_one(self):
        enemy = {'id': 'goblin-axe', 'class': 'fighter', 'level': 1,
                 'inventory': [{'id': 'iron-axe', 'fe_base': 'iron-axe'}]}
        units = df.enemy_combatants(enemy)
        self.assertEqual(len(units), 1)            # distinct type; count tracked elsewhere
        u = units[0]
        self.assertEqual((u.hp, u.pow, u.skl, u.spd, u.df, u.con),
                         (20, 5, 2, 4, 2, 11))
        self.assertEqual(u.weapon.name, 'iron-axe')


class LordTeamSweep(unittest.TestCase):
    def test_each_candidate_anchors_a_full_deploy_team_of_best_others(self):
        enemy = combatant('E', hp=20, weapon='iron-lance')
        # Throughput ranking (best kpr vs E): big > mid > small > tiny.
        big = combatant('big', pow_=20, weapon='iron-bow')    # one-rounds -> 1.0
        mid = combatant('mid', pow_=14, weapon='iron-bow')    # 20 dmg -> 1.0 too; use 9
        mid = combatant('mid', pow_=9, weapon='iron-bow')     # 15 dmg -> 0.75
        small = combatant('small', pow_=4, weapon='iron-bow')  # 10 dmg -> 0.5
        tiny = combatant('tiny', pow_=2, weapon='iron-bow')   # 8 dmg -> 0.4
        roster = [tiny, small, mid, big]
        rows = df.lord_team_sweep(roster, [enemy], [], deploy_limit=2)

        # One row per candidate lord, each fielding exactly deploy_limit units incl. itself.
        self.assertEqual({r['lord'].name for r in rows}, {'tiny', 'small', 'mid', 'big'})
        for r in rows:
            self.assertEqual(len(r['team']), 2)
            self.assertIn(r['lord'], r['team'])

        # 'tiny' as lord fills with the single best other ('big'): throughput 0.4 + 1.0.
        tiny_row = next(r for r in rows if r['lord'].name == 'tiny')
        self.assertEqual({u.name for u in tiny_row['team']}, {'tiny', 'big'})
        self.assertAlmostEqual(tiny_row['throughput'], 1.4)


class BulkDurability(unittest.TestCase):
    """Worst-case enemy-rounds-to-down assuming every hit connects (no avoid/RNG)."""

    def test_rounds_when_hits_connect(self):
        unit = combatant('u', hp=20, dfc=0, spd=0, weapon='iron-lance')
        a = combatant('a', pow_=4, spd=0, weapon='iron-bow')   # 10 dmg, single
        self.assertAlmostEqual(df.bulk_durability(unit, [a]), 2.0)

    def test_counts_doubling(self):
        unit = combatant('u', hp=20, dfc=1, spd=0, weapon='iron-lance')
        a = combatant('a', pow_=0, spd=10, weapon='iron-bow')  # 5 dmg x2 (AS 10 vs 0)
        self.assertAlmostEqual(df.bulk_durability(unit, [a]), 2.0)

    def test_ignores_avoid_unlike_durability(self):
        # A dodge-tank (huge avoid) is NOT credited -- bulk is the must-survive worst case.
        unit = combatant('u', hp=20, dfc=0, spd=50, lck=30, weapon='iron-lance')
        a = combatant('a', pow_=4, spd=0, weapon='iron-bow')
        self.assertAlmostEqual(df.bulk_durability(unit, [a]), 2.0)

    def test_infinite_when_it_cannot_be_damaged(self):
        unit = combatant('u', hp=20, dfc=99, weapon='iron-lance')
        a = combatant('a', pow_=4, weapon='iron-bow')
        self.assertEqual(df.bulk_durability(unit, [a]), float('inf'))


class LordFloorSolver(unittest.TestCase):
    def test_zero_for_a_unit_already_above_target(self):
        tank = combatant('tank', hp=40, dfc=8, weapon='iron-lance')
        e = combatant('e', pow_=5, spd=0, weapon='iron-axe')   # bulk 40/6 = 6.7
        f = df.lord_floor_delta(tank, [e], target=3.5)
        self.assertEqual((f.hp, f.df, f.res), (0, 0, 0))
        self.assertTrue(f.reached)

    def test_physical_threat_spends_def_to_cap_then_hp(self):
        # A frail shaman vs the goblin fighter -> reproduces the locked +7 HP / +4 Def.
        mage = combatant('mage', hp=18, dfc=2, spd=6, con=7, weapon='flux')
        fighter = combatant('fighter', pow_=5, spd=4, con=11, weapon='iron-axe')
        f = df.lord_floor_delta(mage, [fighter], target=3.5, def_cap=4)
        self.assertEqual((f.hp, f.df, f.res), (7, 4, 0))
        self.assertTrue(f.reached)

    def test_magic_threat_spends_res_not_def(self):
        # An armor lord vs a magic attacker: Def is inert, so the solver buys Res.
        armor = combatant('armor', hp=25, dfc=9, res=3, spd=3, con=14, weapon='iron-lance')
        mage = combatant('druid', pow_=8, spd=6, con=6, weapon='flux')
        f = df.lord_floor_delta(armor, [mage], target=3.5, def_cap=4, res_cap=4)
        self.assertEqual((f.hp, f.df, f.res), (3, 0, 4))

    def test_flags_unreachable_within_caps(self):
        # Effective-weapon-style burst the caps can't answer -> reached False (a positioning
        # problem, not a stat one).
        flier = combatant('flier', hp=10, dfc=0, spd=0, weapon='iron-lance')
        sniper = combatant('sniper', pow_=20, spd=0, weapon='iron-axe')
        f = df.lord_floor_delta(flier, [sniper], target=3.5, def_cap=2, hp_cap=5)
        self.assertFalse(f.reached)


if __name__ == '__main__':
    unittest.main()
