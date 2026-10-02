#!/usr/bin/env python3
"""Tests for tools/ai_target.py -- the port of FE8's `AiComputeCombatScore`.

Oracles are the decomp (fireemblem8u/src/cp_battle.c:572-780, cp_data.c) with hand-computed
scores. Run:

    python3 tools/test_ai_target.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ai_target
import fe_combat as fc


def unit(name='u', hp=20, pow=5, skl=5, spd=5, df=3, res=0, lck=0, con=10, weapon='iron-axe'):
    return fc.Combatant(name, hp=hp, pow=pow, skl=skl, spd=spd, df=df, res=res, lck=lck,
                        con=con, weapon=fc.W[weapon] if weapon else None)


class CoefficientTables(unittest.TestCase):
    def test_tables_are_read_from_the_decomp(self):
        tables = ai_target.coefficient_tables()
        self.assertEqual(len(tables), 32)
        self.assertEqual(tables[0]['coeffDamageDealt'], 2)
        self.assertEqual(tables[1]['coeffLowHpOpponent'], 2)
        self.assertEqual(tables[1]['coeffDamageTaken'], 0)
        self.assertEqual(tables[0]['bonuses'][:5], [10, 15, 0, 0, 5])

    def test_the_class_term_reads_one_past_the_bonus_array(self):
        # Rank 9 of a 9-entry array is the next table's coeffDamageDealt: table 1's is 1.
        self.assertEqual(ai_target._class_term(0), 1)

    def test_the_weight_table_is_bits_3_to_7_of_the_low_config_byte(self):
        self.assertEqual(ai_target.combat_weight_table((0, 3, 0x08, 0)), 1)
        self.assertEqual(ai_target.combat_weight_table((0, 0, 0x07, 0xFF)), 0)


class CombatScore(unittest.TestCase):
    def test_a_hand_computed_score(self):
        # Axe into sword (triangle -1 Mt / -15 Hit): 10 damage at 62 hit, nobody doubles.
        # Simulated: 18 -> 8, counter 7 -> 13. Table 0:
        #   dealt 2 x (10 x 62 // 100) = 12, opp low HP 20 - 8 = 12, class 1, turn 1,
        #   taken 7 x 100 // 100 = 7, own low HP 20 - 13 = 7  ->  12, x 40 = 480.
        atk = unit()
        dfn = unit('d', hp=18, pow=4, skl=4, spd=4, df=2, weapon='iron-sword')
        self.assertEqual(ai_target.combat_score(atk, dfn, 0), 480)

    def test_a_kill_scores_50_for_damage(self):
        atk = unit(pow=20)
        frail = unit('f', hp=5, df=0, weapon='iron-sword')
        c = ai_target.coefficient_tables()[1]
        # Table 1 weighs turn, damage taken and own HP at 0: dealt 50 + low HP 2 x 20 + class.
        expected = (50 + c['coeffLowHpOpponent'] * 20 + ai_target._class_term(1)) * 40
        self.assertEqual(ai_target.combat_score(atk, frail, 1), expected)

    def test_a_target_that_cannot_answer_is_worth_ten(self):
        atk = unit(df=20)
        armed = unit('a', weapon='iron-axe')
        unarmed = unit('b', weapon=None)
        # Same stats, and Def 20 makes the armed one's counter worth 0 (taken 0); the
        # unarmed one cannot counter at all (-10). Axe into axe or into no weapon: neutral.
        self.assertEqual(ai_target.combat_score(atk, unarmed, 0)
                         - ai_target.combat_score(atk, armed, 0), 10 * 40)

    def test_a_ranged_attacker_picks_the_distance_its_target_cannot_answer(self):
        atk = unit(weapon='hand-axe')
        melee = unit('m', weapon='iron-axe', pow=15)     # axe into axe: no triangle
        bare = unit('b', weapon=None, pow=15)
        self.assertEqual(ai_target.combat_score(atk, melee, 0),
                         ai_target.combat_score(atk, bare, 0))

    def test_a_losing_sum_falls_back_to_the_damage_term(self):
        # Chip damage against a target that counters hard: the sum goes negative, so the
        # score is the damage-dealt term alone, not 0.
        atk = unit(hp=8, pow=3, df=0, weapon='iron-sword')
        brute = unit('x', hp=30, pow=15, df=6, spd=0, weapon='iron-lance')
        dealt = min(40, 2 * (fc.damage(atk, brute) * fc.hit_chance(atk, brute) // 100))
        self.assertEqual(ai_target.combat_score(atk, brute, 0), dealt)

    def test_a_weaponless_attacker_scores_nothing(self):
        self.assertEqual(ai_target.combat_score(unit(weapon=None), unit('d'), 0), 0)


class PickTarget(unittest.TestCase):
    def test_the_ai_prefers_the_kill(self):
        atk = unit(pow=12)
        tough = unit('tough', hp=30, df=8)
        frail = unit('frail', hp=10, df=0)
        self.assertIs(ai_target.pick_target(atk, [tough, frail], 0), frail)

    def test_a_tie_goes_to_the_first(self):
        atk = unit()
        a, b = unit('a'), unit('b')
        self.assertIs(ai_target.pick_target(atk, [a, b], 0), a)
        self.assertIs(ai_target.pick_target(atk, [b, a], 0), b)


if __name__ == '__main__':
    unittest.main()
