#!/usr/bin/env python3
"""Tests for tools/unit_load.py's `growth_steps`: LoadUnit's path as data (#490, ADR 0354).

Both the wiki's ranges and difficulty.py's model read these steps, so a branch
that drifts from the decomp misreads every chapter at once. Each test names the decomp
function it pins (fireemblem8u/src/bmunit.c, eventscr.c:2328).

Run: python3 tools/test_unit_load.py
"""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import difficulty as df
import fe_combat as fc
import unit_load as ul


class CanUseWeapon(unittest.TestCase):
    """`CanUnitUseWeapon` at load (bmitem.c), with `UnitAutolevelWExp`'s rank raise."""

    def test_a_class_with_no_rank_in_the_type_cannot_use_it(self):
        """ch06's trident-drop Soldier carries an Iron Blade only to drop it (ADR 0329)."""
        self.assertFalse(ul.can_use_weapon('ITEM_BLADE_IRON', 'CLASS_SOLDIER'))

    def test_a_flagged_unit_reaches_any_rank_in_a_type_it_holds(self):
        """A Soldier holds D lances; autolevelled, a Steel Lance (D) and a Silver (A) both work."""
        self.assertTrue(ul.can_use_weapon('ITEM_LANCE_SILVER', 'CLASS_SOLDIER', autolevel=True))

    def test_an_unflagged_unit_needs_the_rank(self):
        self.assertFalse(ul.can_use_weapon('ITEM_LANCE_SILVER', 'CLASS_SOLDIER', autolevel=False))
        self.assertTrue(ul.can_use_weapon('ITEM_LANCE_IRON', 'CLASS_SOLDIER', autolevel=False))

    def test_a_monster_weapon_needs_the_monster_lock(self):
        self.assertFalse(ul.can_use_weapon('ITEM_MONSTER_FETIDCLW', 'CLASS_SOLDIER'))
        self.assertTrue(ul.can_use_weapon('ITEM_MONSTER_FETIDCLW', 'CLASS_ENTOUMBED',
                                          attributes=frozenset({'CA_LOCK_3'})))


class GrowthSteps(unittest.TestCase):
    def test_an_unflagged_unit_loads_bare_whatever_its_level(self):
        """LoadUnit only calls UnitAutolevel for a `.autolevel` definition."""
        self.assertEqual(ul.growth_steps(12, autolevel=False), [])

    def test_a_flagged_unit_grows_level_minus_one_on_class_growths(self):
        self.assertEqual(ul.growth_steps(5), [(4, 'class')])

    def test_a_promoted_class_takes_nine_bonus_levels_first(self):
        """UnitAutolevel: GetCurrentPromotedLevelBonus() before level - 1."""
        self.assertEqual(ul.growth_steps(1, promoted=True), [(9, 'class')])
        self.assertEqual(ul.growth_steps(3, promoted=True), [(9, 'class'), (2, 'class')])

    def test_the_promoted_bonus_is_nineteen_on_difficult(self):
        self.assertEqual(ul.growth_steps(1, promoted=True, mode='difficult'), [(19, 'class')])

    def test_a_realistic_unit_levels_on_personal_growths_from_its_base_level(self):
        """UnitAutolevelRealistic: an autolevelled CA_BOSS / pid < 0x40."""
        self.assertEqual(ul.growth_steps(10, realistic=True, base_level=6), [(4, 'personal')])
        self.assertEqual(ul.growth_steps(6, realistic=True, base_level=6), [])

    def test_difficult_adds_its_bonus_after_the_load_flagged_or_not(self):
        """UnitApplyBonusLevels > 0 -> UnitAutolevelCore, with no level gate."""
        self.assertEqual(ul.growth_steps(5, shift=2, mode='difficult'), [(4, 'class'), (2, 'class')])
        self.assertEqual(ul.growth_steps(5, autolevel=False, shift=2, mode='difficult'),
                         [(2, 'class')])

    def test_the_normal_penalty_reautolevels_even_an_unflagged_unit(self):
        """UnitAutolevelPenalty rebuilds from base and calls UnitAutolevel at level - malus."""
        self.assertEqual(ul.growth_steps(8, autolevel=False, shift=2), [(5, 'class')])
        self.assertEqual(ul.growth_steps(8, shift=2), [(5, 'class')])

    def test_the_penalty_reautolevels_a_promoted_unit_with_its_bonus(self):
        self.assertEqual(ul.growth_steps(4, promoted=True, shift=1),
                         [(9, 'class'), (2, 'class')])

    def test_the_penalty_skips_a_unit_at_or_under_its_base_level(self):
        """`level > baseLevel` gates the whole penalty."""
        self.assertEqual(ul.growth_steps(5, shift=2, base_level=5), [(4, 'class')])

    def test_a_penalty_that_lands_at_the_base_level_leaves_it_bare(self):
        """Stats are rebuilt from base, and `levelCount > baseLevel` skips the re-autolevel."""
        self.assertEqual(ul.growth_steps(3, shift=2), [])


class LoadsRealistically(unittest.TestCase):
    def test_a_ca_boss_character_loads_realistically(self):
        self.assertTrue(df._loads_realistically('CHARACTER_BAZBA', 'CLASS_BRIGAND'))

    def test_a_generic_pid_does_not(self):
        self.assertFalse(df._loads_realistically('0x8e', 'CLASS_BRIGAND'))


class Caps(unittest.TestCase):
    def test_a_loaded_unit_never_exceeds_its_class_maxima(self):
        """UnitCheckStatCaps: a high-level, high-growth line stops at the class cap."""
        caps = ul.class_line('CLASS_SOLDIER')[2]
        c = df._enemy_from_enum('x', 'CLASS_SOLDIER', 20, None,
                                personal={'baseHP': 60, 'basePow': 30})
        self.assertLessEqual(c.hp, caps['HP'])
        self.assertLessEqual(c.pow, caps['Pow'])


class EnemyCareers(unittest.TestCase):
    """The parity model rolls a red unit's load as the engine does (#510 step 4):
    `GetAutoleveledStatIncrease` (bmbattle.c) per stat, per `growth_steps` chunk."""
    SHIFTS = {'tutorial': 3, 'normal': 1, 'difficult': 4}

    def test_one_increase_stays_inside_the_engines_bounds_and_reaches_both(self):
        rng = random.Random(1)
        for gn in (0, 35, 90, 400, 765, 1900):
            seen = {ul.autolevel_increase(gn, rng) for _ in range(4000)}
            self.assertEqual((min(seen), max(seen)), ul._increase_bounds(gn), gn)

    def test_every_career_falls_inside_the_load_range(self):
        """The ranges `INSPECT.redStats` proved in the engine (ADR 0354) bound every draw."""
        for mode in ul.MODES:
            unit = df._enemy_from_enum('x', 'CLASS_FIGHTER', 10, fc.W['iron-axe'],
                                       mode=mode, shifts=self.SHIFTS)
            rng = ul.load('CLASS_FIGHTER', 10, shifts=self.SHIFTS, mode=mode)
            for c in df.enemy_careers(unit):
                for f, stat in df._GROWN_FIELDS:
                    lo, hi = rng[stat]
                    self.assertTrue(lo <= getattr(c, f) <= hi, (mode, stat, getattr(c, f)))

    def test_the_careers_center_on_the_mean_line(self):
        unit = df._enemy_from_enum('x', 'CLASS_FIGHTER', 15, fc.W['iron-axe'])
        careers = df.enemy_careers(unit)
        for f, _stat in df._GROWN_FIELDS:
            median = sorted(getattr(c, f) for c in careers)[len(careers) // 2]
            self.assertLessEqual(abs(median - getattr(unit, f)), 1, f)

    def test_a_unit_that_does_not_grow_has_one_career(self):
        """Unflagged and unshifted: LoadUnit's class + personal base, nothing rolled."""
        unit = df._enemy_from_enum('x', 'CLASS_FIGHTER', 10, fc.W['iron-axe'], autolevel=False)
        self.assertEqual(df.enemy_careers(unit), [unit])

    def test_a_career_never_exceeds_the_class_maxima(self):
        caps = ul.class_line('CLASS_SOLDIER')[2]
        unit = df._enemy_from_enum('x', 'CLASS_SOLDIER', 20, fc.W['iron-lance'],
                                   personal={'baseHP': 20, 'basePow': 12})
        for c in df.enemy_careers(unit):
            self.assertLessEqual(c.hp, caps['HP'])
            self.assertLessEqual(c.pow, caps['Pow'])

    def test_the_matchup_reads_a_body_once_per_career(self):
        """Against a one-line party, a rolled body's reading is the average of its careers'."""
        unit = df._enemy_from_enum('x', 'CLASS_FIGHTER', 10, fc.W['iron-axe'])
        member = fc.Combatant('m', hp=22, pow=7, skl=8, spd=8, df=5, res=2, lck=5, con=7,
                              weapon=fc.W['iron-sword'])
        whole = df.party_matchup([(unit, 0)], {'m': [member]})
        careers = df.enemy_careers(unit)
        one = [df.party_matchup([(c, 0)], {'m': [member]}) for c in careers]
        for key in ('threat', 'clear'):
            self.assertAlmostEqual(whole[key], sum(m[key] for m in one) / len(one), places=9)


if __name__ == '__main__':
    unittest.main()
