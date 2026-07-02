#!/usr/bin/env python3
"""Tests for tools/fe_combat.py -- the FE8 combat math the difficulty engine arbitrates on.

Oracles are the decomp's own formulas (fireemblem8u/src/bmbattle.c, cited in fe_combat.py)
with hand-computed expected values, plus canonical vanilla FE8 Ch1 matchups. Run:

    python3 tools/test_fe_combat.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fe_combat as fc


def soldier(spd, con, weapon):
    """Bare combatant for isolating one formula (only the fields that matter set)."""
    return fc.Combatant('t', hp=20, pow=0, skl=0, spd=spd, df=0, res=0, lck=0,
                        con=con, weapon=weapon)


class AttackSpeed(unittest.TestCase):
    def test_no_penalty_when_weapon_lighter_than_con(self):
        # Wt 8 (iron lance) <= Con 13 -> no penalty; AS == Spd.
        u = soldier(spd=5, con=13, weapon=fc.W['iron-lance'])
        self.assertEqual(fc.attack_speed(u), 5)

    def test_weight_penalty_when_weapon_heavier_than_con(self):
        # Eirika (Con 5) on a Wt-15 weapon: 15-5=10 penalty -> AS = max(0, 9-10) = 0.
        u = soldier(spd=9, con=5, weapon=fc.Weapon('heavy', 0, 0, 0, 15, 'axe'))
        self.assertEqual(fc.attack_speed(u), 0)

    def test_floors_at_zero(self):
        # Wolfram: Spd 0, never negative.
        u = soldier(spd=0, con=13, weapon=fc.W['iron-lance'])
        self.assertEqual(fc.attack_speed(u), 0)


class Doubling(unittest.TestCase):
    def test_doubles_at_four_as_lead(self):
        # AS lead of exactly 4 triggers a follow-up (BATTLE_FOLLOWUP_THRESHOLD).
        fast = soldier(spd=7, con=13, weapon=fc.W['iron-axe'])   # AS 7
        slow = soldier(spd=3, con=13, weapon=fc.W['iron-axe'])   # AS 3
        self.assertTrue(fc.doubles(fast, slow))

    def test_no_double_at_three_as_lead(self):
        fast = soldier(spd=6, con=13, weapon=fc.W['iron-axe'])   # AS 6
        slow = soldier(spd=3, con=13, weapon=fc.W['iron-axe'])   # AS 3
        self.assertFalse(fc.doubles(fast, slow))

    def test_spd_zero_armor_gets_doubled_by_a_fighter(self):
        # The Ch1 frailty cliff: Wolfram (Spd 0, iron lance) vs a goblin fighter
        # (Spd 4, iron axe Wt10 Con11 -> AS 4) -- 4-0 = 4, so the fighter doubles.
        wolfram = soldier(spd=0, con=13, weapon=fc.W['iron-lance'])
        fighter = soldier(spd=4, con=11, weapon=fc.W['iron-axe'])
        self.assertTrue(fc.doubles(fighter, wolfram))


class Triangle(unittest.TestCase):
    def test_axe_beats_lance(self):
        self.assertEqual(fc.triangle('axe', 'lance'), 1)

    def test_lance_loses_to_axe(self):
        self.assertEqual(fc.triangle('lance', 'axe'), -1)

    def test_sword_neutral_vs_bow(self):
        self.assertEqual(fc.triangle('sword', 'bow'), 0)

    def test_magic_off_triangle(self):
        self.assertEqual(fc.triangle('magic', 'sword'), 0)


def attacker(pow_, weapon, skl=0, lck=0, con=20):
    return fc.Combatant('a', hp=20, pow=pow_, skl=skl, spd=10, df=0, res=0, lck=lck,
                        con=con, weapon=weapon)


def defender(df=0, res=0, spd=0, lck=0, con=20, weapon=None, tags=frozenset()):
    return fc.Combatant('d', hp=20, pow=0, skl=0, spd=spd, df=df, res=res, lck=lck,
                        con=con, weapon=weapon or fc.W['iron-lance'], tags=tags)


class Damage(unittest.TestCase):
    def test_physical_is_pow_plus_might_minus_def(self):
        atk = attacker(5, fc.W['iron-axe'])              # 5 + 8 mt
        self.assertEqual(fc.damage(atk, defender(df=2, weapon=fc.W['iron-bow'])), 11)

    def test_triangle_advantage_adds_one_might(self):
        atk = attacker(5, fc.W['iron-axe'])              # axe vs lance: +1
        self.assertEqual(fc.damage(atk, defender(df=2, weapon=fc.W['iron-lance'])), 12)

    def test_triangle_disadvantage_subtracts_one_might(self):
        atk = attacker(7, fc.W['iron-lance'])            # lance vs axe: -1
        self.assertEqual(fc.damage(atk, defender(df=2, weapon=fc.W['iron-axe'])), 11)

    def test_magic_resolves_against_res_not_def(self):
        # Sclorbo's lightning vs the armored chief (Def 9, Res 0): ignores the plate.
        atk = attacker(5, fc.W['lightning'])             # 5 + 4 mt, vs Res 0
        self.assertEqual(fc.damage(atk, defender(df=9, res=0)), 9)

    def test_effective_weapon_triples_the_weapon_half(self):
        # Vanilla Eirika rapier (sword) vs the Armor boss with a lance (Def 9): sword
        # is at a triangle DISADVANTAGE to lance (-1); the decomp triples the WEAPON
        # half only, then adds Pow (bmbattle.c ComputeBattleUnitAttack):
        # (7 - 1) x3 + 4 - 9 = 13. (The old model tripled the whole sum -> 21.)
        eirika = attacker(4, fc.W['rapier'])
        boss = defender(df=9, weapon=fc.W['iron-lance'], tags=frozenset({'armor'}))
        self.assertEqual(fc.damage(eirika, boss), 13)

    def test_damage_never_negative(self):
        atk = attacker(1, fc.W['iron-sword'])            # 1 + 5 mt vs Def 20
        self.assertEqual(fc.damage(atk, defender(df=20, weapon=fc.W['iron-axe'])), 0)


class HitChance(unittest.TestCase):
    def test_base_hit_is_skill_and_weapon_minus_avoid(self):
        # Skl 8 -> +16, iron-bow hit 85, Lck 0; vs a still Def (AS 0, Lck 0). Bow is
        # off-triangle so no +/-15. 16 + 85 = 101 -> clamped to 100.
        atk = attacker(0, fc.W['iron-bow'], skl=8)
        self.assertEqual(fc.hit_chance(atk, defender(weapon=fc.W['iron-sword'])), 100)

    def test_luck_adds_half_to_accuracy(self):
        atk = attacker(0, fc.W['iron-bow'], skl=0, lck=10)   # 85 + 10//2 = 90
        self.assertEqual(fc.hit_chance(atk, defender(weapon=fc.W['iron-sword'])), 90)

    def test_triangle_advantage_adds_fifteen_hit(self):
        atk = attacker(0, fc.W['iron-axe'])                  # axe vs lance: +15
        self.assertEqual(fc.hit_chance(atk, defender(weapon=fc.W['iron-lance'])), 90)

    def test_avoid_subtracts_double_as_plus_luck(self):
        # Defender AS 10 (Spd 10, bow Wt5, Con 20) + Lck 5 -> avoid 25. iron-bow 85 - 25.
        atk = attacker(0, fc.W['iron-bow'])
        dfn = defender(spd=10, lck=5, weapon=fc.W['iron-bow'])
        self.assertEqual(fc.hit_chance(atk, dfn), 60)

    def test_terrain_avoid_lowers_hit(self):
        atk = attacker(0, fc.W['iron-bow'])
        dfn = defender(spd=10, lck=5, weapon=fc.W['iron-bow'])   # avoid 25 + forest 20
        self.assertEqual(fc.hit_chance(atk, dfn, terrain_avoid=20), 40)

    def test_clamped_to_zero(self):
        atk = attacker(0, fc.W['iron-bow'])                  # 85 hit
        dfn = defender(spd=50, weapon=fc.W['iron-bow'])      # avoid 100
        self.assertEqual(fc.hit_chance(atk, dfn), 0)


class DamagePerRound(unittest.TestCase):
    def test_single_hit_at_full_accuracy(self):
        # 10 dmg, 100% hit, no double (AS 3 vs 0 -> lead 3) -> 10.0.
        atk = attacker(5, fc.W['iron-bow'], skl=8, con=20)
        atk.spd = 3
        dfn = defender(df=1, weapon=fc.W['iron-sword'])      # AS 0
        self.assertAlmostEqual(fc.damage_per_round(atk, dfn), 10.0)

    def test_doubling_strikes_twice(self):
        atk = attacker(5, fc.W['iron-bow'], skl=8, con=20)   # AS 10 vs 0 -> doubles
        dfn = defender(df=1, weapon=fc.W['iron-sword'])
        self.assertAlmostEqual(fc.damage_per_round(atk, dfn), 20.0)

    def test_partial_accuracy_scales_damage(self):
        # 10 dmg, 50% hit, single -> 5.0.
        atk = attacker(5, fc.W['iron-bow'], skl=0, con=20)
        atk.spd = 3
        dfn = defender(df=1, spd=15, lck=5, weapon=fc.W['iron-bow'])  # avoid 35 -> 50% hit
        self.assertAlmostEqual(fc.damage_per_round(atk, dfn), 5.0)


class RoundsToKill(unittest.TestCase):
    def test_hp_over_damage_per_round(self):
        atk = attacker(5, fc.W['iron-bow'], skl=8, con=20)
        atk.spd = 3
        dfn = defender(df=1, weapon=fc.W['iron-sword'])      # 20 hp, dpr 10 -> 2.0
        self.assertAlmostEqual(fc.rounds_to_kill(atk, dfn), 2.0)

    def test_infinite_when_it_cannot_damage(self):
        atk = attacker(1, fc.W['iron-sword'], skl=8)
        dfn = defender(df=99, weapon=fc.W['iron-axe'])
        self.assertEqual(fc.rounds_to_kill(atk, dfn), float('inf'))


class KillsPerRound(unittest.TestCase):
    def test_capped_at_one_when_it_one_rounds(self):
        # Overkill cap: dealing >= the enemy's HP in a round is still one kill, not more.
        atk = attacker(5, fc.W['iron-bow'], skl=8, con=20)   # dpr 20 vs 20 hp
        dfn = defender(df=1, weapon=fc.W['iron-sword'])
        self.assertEqual(fc.kills_per_round(atk, dfn), 1.0)

    def test_fractional_when_it_takes_multiple_rounds(self):
        atk = attacker(5, fc.W['iron-bow'], skl=8, con=20)
        atk.spd = 3
        dfn = defender(df=1, weapon=fc.W['iron-sword'])      # dpr 10 vs 20 hp -> 0.5
        self.assertAlmostEqual(fc.kills_per_round(atk, dfn), 0.5)

    def test_zero_when_it_cannot_damage(self):
        atk = attacker(1, fc.W['iron-sword'], skl=8)
        dfn = defender(df=99, weapon=fc.W['iron-axe'])
        self.assertEqual(fc.kills_per_round(atk, dfn), 0.0)


class SupportUnit(unittest.TestCase):
    """A staff-only / weaponless unit (weapon=None) -- a fielded healer (#62). It must not
    crash the combat math: it deals no damage as an attacker, but is still a valid defender
    (enemies can hit it, so its durability is computable)."""

    def support(self, spd=8, con=10, df=5, res=5, lck=0):
        return fc.Combatant('healer', hp=24, pow=0, skl=8, spd=spd, df=df, res=res,
                            lck=lck, con=con, weapon=None)

    def test_attack_speed_has_no_weight_penalty(self):
        # No weapon -> no weight to bear -> AS is just Spd (no crash on weapon.wt).
        self.assertEqual(fc.attack_speed(self.support(spd=8)), 8)

    def test_deals_no_damage_as_attacker(self):
        self.assertEqual(fc.damage(self.support(), defender(df=2, weapon=fc.W['iron-lance'])), 0)

    def test_no_throughput_as_attacker(self):
        dfn = defender(df=2, weapon=fc.W['iron-lance'])
        self.assertEqual(fc.damage_per_round(self.support(), dfn), 0.0)
        self.assertEqual(fc.kills_per_round(self.support(), dfn), 0.0)

    def test_can_be_attacked_as_defender(self):
        # An armed enemy still resolves damage/hit against a weaponless defender (triangle
        # is neutral -- the healer has no weapon kind), so durability stays computable.
        atk = attacker(5, fc.W['iron-axe'], skl=8)           # 5 + 8 mt, vs Def 5
        healer = self.support(df=5)
        self.assertEqual(fc.damage(atk, healer), 8)
        self.assertGreater(fc.damage_per_round(atk, healer), 0)


class CanonicalMatchup(unittest.TestCase):
    """End-to-end against a real vanilla FE8 Ch1 matchup -- the model must reproduce it."""

    def test_eirika_one_rounds_the_ch1_armor_boss(self):
        eirika = fc.Combatant('Eirika', hp=16, pow=4, skl=8, spd=9, df=3, res=1, lck=5,
                              con=5, weapon=fc.W['rapier'])
        boss = fc.Combatant('Izobai', hp=20, pow=8, skl=2, spd=1, df=9, res=0, lck=2,
                            con=13, weapon=fc.W['iron-lance'], tags=frozenset({'armor'}))
        self.assertEqual(fc.damage(eirika, boss), 13)        # (7-1)x3 + 4 - 9; x3 on Mt+tri only
        self.assertEqual(fc.hit_chance(eirika, boss), 94)
        self.assertTrue(fc.doubles(eirika, boss))            # AS 9 vs 1
        self.assertEqual(fc.kills_per_round(eirika, boss), 1.0)


if __name__ == '__main__':
    unittest.main()
