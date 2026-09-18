#!/usr/bin/env python3
"""Tests for tools/exp_curve.py -- the exp economy and the party-level band it derives.

Two halves, and the first is the load-bearing one. The FORMULAS are transcribed from
`fireemblem8u/src/bmbattle.c` at HEAD, so every expectation here is hand-computed from that
source and cited in the test name or its comment: a transcription whose expectations were
read off our own implementation would test nothing. The SIMULATION half then pins the
properties the band is read for -- that it is monotone, that it is grounded in the real
roster, and that the generated block in docs/fe8-pacing-reference.md matches what the model
says today.

Run:  python3 tools/test_exp_curve.py
"""
import collections
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import exp_curve as ec


class ClassDataReads(unittest.TestCase):
    """The three ClassData fields the exp math reads, straight from data_classes.c."""

    def test_soldier_relative_power_is_two(self):
        # data_classes.c [CLASS_SOLDIER - 1] .classRelativePower = 2 -- vanilla prices a
        # Soldier BELOW a Fighter, which is why a soldier line pays more exp per body.
        self.assertEqual(2, ec.class_relative_power('CLASS_SOLDIER'))

    def test_pirate_relative_power_is_three(self):
        self.assertEqual(3, ec.class_relative_power('CLASS_PIRATE'))

    def test_a_class_with_no_attributes_line_reads_as_zero_attributes(self):
        # CLASS_PIRATE has no `.attributes =` line at all; the read must not crash or
        # inherit a neighbour's flags.
        self.assertEqual(frozenset(), ec.class_attributes('CLASS_PIRATE'))

    def test_hero_is_promoted(self):
        self.assertIn('CA_PROMOTED', ec.class_attributes('CLASS_HERO'))

    def test_thief_carries_the_thief_attribute(self):
        self.assertIn('CA_THIEF', ec.class_attributes('CLASS_THIEF'))

    def test_a_promoted_classs_promotion_field_points_BACK_at_its_base_class(self):
        # Not a typo in the decomp and not one here: GetUnitPowerLevel reads
        # `unit->pClassData->promotion` on a PROMOTED unit, and for promoted classes that
        # field holds the class they came FROM (Paladin -> Cavalier).
        self.assertEqual('CLASS_CAVALIER', ec.class_promotion('CLASS_PALADIN'))


class ExpLevel(unittest.TestCase):
    """GetUnitExpLevel -- bmbattle.c: level, +20 when promoted."""

    def test_unpromoted_exp_level_is_the_level(self):
        self.assertEqual(7, ec.exp_level(ec.Fighter('merfolk', 'CLASS_SOLDIER', 7)))

    def test_promoted_exp_level_adds_twenty(self):
        self.assertEqual(25, ec.exp_level(ec.Fighter('hero', 'CLASS_HERO', 5)))


class RoundExp(unittest.TestCase):
    """GetUnitRoundExp -- (31 - (actorExpLevel - targetExpLevel)) / actor classRelativePower,
    floored at 0 BEFORE the divide, C integer division after it."""

    def test_even_levels_pay_ten_to_a_relative_power_three_actor(self):
        actor = ec.Fighter('braulo', 'CLASS_PIRATE', 1)
        target = ec.Fighter('grunt', 'CLASS_FIGHTER', 1)
        self.assertEqual(10, ec.round_exp(actor, target))       # 31 // 3

    def test_a_relative_power_two_actor_gains_more_from_the_same_body(self):
        actor = ec.Fighter('sclorbo', 'CLASS_PRIEST', 1)        # crp 2
        target = ec.Fighter('grunt', 'CLASS_FIGHTER', 1)
        self.assertEqual(15, ec.round_exp(actor, target))       # 31 // 2

    def test_fighting_above_your_level_pays_more(self):
        actor = ec.Fighter('braulo', 'CLASS_PIRATE', 1)
        target = ec.Fighter('boss', 'CLASS_FIGHTER', 10)
        self.assertEqual(13, ec.round_exp(actor, target))       # (31 + 9) // 3

    def test_the_bracket_floors_at_zero_before_the_divide(self):
        actor = ec.Fighter('vet', 'CLASS_HERO', 20)             # exp level 40
        target = ec.Fighter('grunt', 'CLASS_FIGHTER', 1)
        self.assertEqual(0, ec.round_exp(actor, target))        # 31 - 39 < 0 -> 0


class PowerLevel(unittest.TestCase):
    """GetUnitPowerLevel -- level * classRelativePower, plus 20 * the promotion field's own
    relative power when the class is promoted and names one."""

    def test_unpromoted_power_is_level_times_relative_power(self):
        self.assertEqual(14, ec.power_level(ec.Fighter('merfolk', 'CLASS_SOLDIER', 7)))

    def test_promoted_power_adds_twenty_base_class_levels(self):
        # Paladin L1: 1*3 + 20 * classRelativePower(CLASS_CAVALIER) = 3 + 60.
        self.assertEqual(63, ec.power_level(ec.Fighter('knight', 'CLASS_PALADIN', 1)))


class KillBonus(unittest.TestCase):
    """GetUnitClassKillExpBonus + GetUnitKillExpBonus on the COMMON route
    (gPlaySt.chapterModeIndex == 1), which is the only mode our campaign ever runs in."""

    def test_a_boss_body_is_worth_forty_more(self):
        self.assertEqual(40, ec.class_kill_exp_bonus(
            ec.Fighter('nerra', 'CLASS_SHAMAN', 10, boss=True)))

    def test_a_thief_class_body_is_worth_twenty_more(self):
        self.assertEqual(20, ec.class_kill_exp_bonus(
            ec.Fighter('sneak', 'CLASS_THIEF', 3)))

    def test_an_entoumbed_body_is_worth_forty_more_by_class_alone(self):
        self.assertEqual(40, ec.class_kill_exp_bonus(
            ec.Fighter('tomb', 'CLASS_ENTOUMBED', 1)))

    def test_killing_below_your_level_HALVES_the_actor_power_penalty(self):
        # The common-route branch: target power 2 (L1 Soldier, crp 2) <= actor power 21
        # (L7 Pirate, crp 3), so the subtraction is actor/2 = 10 -> 20 + (2 - 10).
        actor = ec.Fighter('braulo', 'CLASS_PIRATE', 7)
        target = ec.Fighter('grunt', 'CLASS_SOLDIER', 1)
        self.assertEqual(12, ec.kill_exp_bonus(actor, target))

    def test_killing_above_your_level_pays_the_full_difference(self):
        # target power 30 (L10 Shaman, crp 3) > actor power 3 -> 20 + (30 - 3).
        actor = ec.Fighter('braulo', 'CLASS_PIRATE', 1)
        target = ec.Fighter('nerra', 'CLASS_SHAMAN', 10)
        self.assertEqual(47, ec.kill_exp_bonus(actor, target))

    def test_the_bonus_never_goes_negative(self):
        actor = ec.Fighter('vet', 'CLASS_PALADIN', 20)          # power 80
        target = ec.Fighter('grunt', 'CLASS_SOLDIER', 1)        # power 2
        self.assertEqual(0, ec.kill_exp_bonus(actor, target))   # 20 + (2 - 40) < 0


class BattleExpGain(unittest.TestCase):
    """GetBattleUnitExpGain -- round exp + kill bonus, clamped to 1..100."""

    def test_a_kill_pays_round_exp_plus_the_kill_bonus(self):
        actor = ec.Fighter('braulo', 'CLASS_PIRATE', 1)
        target = ec.Fighter('grunt', 'CLASS_SOLDIER', 1)
        # round 31//3 = 10; bonus 20 + (power 2 - power 3//2) = 21. Hand-computed, so this
        # fails if either half is re-derived from the other.
        self.assertEqual(31, ec.battle_exp_gain(actor, target))

    def test_the_gain_is_capped_at_one_hundred(self):
        actor = ec.Fighter('rookie', 'CLASS_JOURNEYMAN', 1)     # crp 1 -> round exp 31+
        target = ec.Fighter('nerra', 'CLASS_SHAMAN', 10, boss=True)
        self.assertEqual(100, ec.battle_exp_gain(actor, target))

    def test_the_gain_never_drops_below_one(self):
        actor = ec.Fighter('vet', 'CLASS_PALADIN', 20)
        target = ec.Fighter('grunt', 'CLASS_SOLDIER', 1)
        self.assertEqual(1, ec.battle_exp_gain(actor, target))


class ChapterBodies(unittest.TestCase):
    """The two roster readers. Both sides must count the same KIND of thing, which is the
    error #368 found in the parity metric: our side read only `enemy_units` while the twin's
    curated arrays fold their reinforcement waves in."""

    def setUp(self):
        self.campaign = 'rime-of-the-frostmaiden'

    def test_ch06_fields_exactly_as_many_bodies_as_its_twin(self):
        # ch06 is a literal transcription of FE8 Ch6's force (100% mirror, decisions.md ->
        # "A parity ratio does not say how much of the twin it COPIED"), so a body-count
        # mismatch here is a reader bug, not a design change.
        ours = ec.chapter_bodies(ec.load_chapter(self.campaign, 'ch06'))
        twin = ec.vanilla_bodies('FE8 Ch6')
        self.assertEqual(len(twin), len(ours))

    def test_a_composition_bag_places_one_body_per_listed_class(self):
        # ch01's reinforcement wave is `composition: [fighter, fighter, soldier]`.
        bodies = ec.chapter_bodies(ec.load_chapter(self.campaign, 'ch01'))
        classes = collections.Counter(b.class_enum for b in bodies)
        self.assertGreaterEqual(classes['CLASS_FIGHTER'], 2)
        self.assertGreaterEqual(classes['CLASS_SOLDIER'], 1)

    def test_a_reinforcement_wave_under_its_own_key_is_counted(self):
        # ch02 declares its rear-raider pair under `reinforcements:` with `levels: [2, 3]`.
        # Reading only `enemy_units` scored 7 bodies against the twin's 9 for four chapters.
        levels = [b.level for b in ec.chapter_bodies(ec.load_chapter(self.campaign, 'ch02'))]
        self.assertIn(2, levels)
        self.assertIn(3, levels)

    def test_a_boss_on_a_vanilla_slot_carries_CA_BOSS(self):
        bodies = ec.chapter_bodies(ec.load_chapter(self.campaign, 'ch06'))
        nerra = [b for b in bodies if b.name == 'nerra']
        self.assertEqual(1, len(nerra))
        self.assertTrue(nerra[0].boss, 'nerra rides CHARACTER_NOVALA, who carries CA_BOSS')

    def test_a_boss_on_a_RAW_pid_carries_none(self):
        # Ravisin has no ENEMY_BASE_SLOT row, so her CharacterData is all zeros in the built
        # ROM -- she pays 40 less kill exp than the vanilla boss she is measured against.
        # This is a finding, not a bug in the reader, and the model must not paper over it.
        bodies = ec.chapter_bodies(ec.load_chapter(self.campaign, 'ch05'))
        ravisin = [b for b in bodies if b.name == 'ravisin']
        self.assertEqual(1, len(ravisin))
        self.assertFalse(ravisin[0].boss)

    def test_the_prologue_boss_carries_CA_BOSS_though_his_stat_line_is_zeroed(self):
        # Sephek rides PROLOGUE_SEPHEK_SLOT (ONEILL) and DefeatBoss fires on his death
        # BECAUSE he keeps that slot's CA_BOSS. inject_prologue zeroes his personal STATS,
        # which is why he is not in ENEMY_BASE_SLOT -- zeroing a stat line does not clear an
        # attribute, and reading the boss question off the stat table underpays the whole
        # prologue by a 40-exp kill bonus.
        bodies = ec.chapter_bodies(ec.load_chapter(self.campaign, 'ch00'))
        sephek = [b for b in bodies if b.name == 'sephek-kaltro']
        self.assertEqual(1, len(sephek))
        self.assertTrue(sephek[0].boss)

    def test_both_gorgon_egg_classes_count_as_special_exp(self):
        # UNIT_IS_GORGON_EGG (bmunit.h) tests CLASS_GORGONEGG *and* CLASS_GORGONEGG2, so a
        # guard that knows only the first still mis-prices half the eggs in the game.
        self.assertIn('CLASS_GORGONEGG', ec.SPECIAL_EXP_CLASSES)
        self.assertIn('CLASS_GORGONEGG2', ec.SPECIAL_EXP_CLASSES)

    def test_no_hosted_chapter_fields_a_class_the_exp_model_cannot_price(self):
        self.assertEqual([], ec.unmodelled_special_exp_bodies(self.campaign))


class Simulation(unittest.TestCase):
    """The curve itself. These pin the PROPERTIES the band is read for -- not the literal
    numbers, which move with every roster edit and are published in the doc block instead."""

    @classmethod
    def setUpClass(cls):
        cls.rows = ec.simulate('rime-of-the-frostmaiden')

    def test_a_fixed_roster_chapter_splits_its_exp_across_the_units_it_FIELDS(self):
        """ch00 has no deploy cap because it has no Pick Units -- it fields Hlin and
        Scramsax and nobody else. Falling back to the whole 13-unit roster would split the
        prologue thirteen ways and understate what its twin pays vanilla's two-unit field
        by a factor of six."""
        row = [r for r in self.rows if r['chapter_number'] == 0][0]
        self.assertEqual(2, row['field_cap'])

    def test_every_hosted_chapter_gets_a_row_in_chapter_order(self):
        numbers = [r['chapter_number'] for r in self.rows]
        self.assertEqual(sorted(numbers), numbers)
        self.assertGreaterEqual(len(numbers), 7)     # ch00-ch06 are hosted today

    def test_a_recruit_earns_nothing_from_the_chapters_it_was_not_in(self):
        """basil and sahnar join in ch05 and every recruit joins at level 1. Crediting them
        with ch01-ch04 would hand four units an exp history they never had and pull the
        typical column up with it (`build_campaign.recruit_chapter_number` is the same
        answer `cast_available_at` sizes the deploy caps from)."""
        before = [r for r in self.rows if r['chapter_number'] == 4][0]
        self.assertEqual(1, before['levels']['basil'])
        self.assertGreater(before['levels']['braulo'], 1)

    def test_a_recruit_starts_earning_once_it_has_joined(self):
        joined = [r for r in self.rows if r['chapter_number'] == 6][0]
        self.assertGreater(joined['levels']['basil'], 1)

    def test_the_party_level_never_goes_backwards(self):
        levels = [r['level_after'] for r in self.rows]
        self.assertEqual(sorted(levels), levels)

    def test_the_band_describes_units_that_have_been_there_all_along(self):
        """benched/typical/fed are three SHARES of one career, so they have to be read over
        the same population -- the founding party. Mixing a ch05 recruit into the low edge
        pinned it at L1 for every chapter after a recruitment, which stops being a statement
        about how much a unit is fed and becomes one about when it joined."""
        last = self.rows[-1]
        self.assertGreater(last['band_low'], 1)

    def test_the_newest_recruit_is_reported_separately(self):
        """The recruit floor is the other number a design question needs -- basil and sahnar
        join in ch05 at level 1, and a chapter that assumes L5 of everyone is wrong about
        two units on the field."""
        joined = [r for r in self.rows if r['chapter_number'] == 5][0]
        self.assertEqual(1, joined['newest'])

    def test_the_band_brackets_the_even_split(self):
        for r in self.rows:
            self.assertLessEqual(r['band_low'], r['level_after'])
            self.assertLessEqual(r['level_after'], r['band_high'])

    def test_our_exp_yield_stays_within_twelve_percent_of_the_twin(self):
        """#367's finding: the exp economy is honest -- every chapter within +/-12% of its
        vanilla twin. It is asserted here because exp is the only quantity that INTEGRATES
        across chapters, so nothing else in the gate can see it drift.

        A chapter that trips this is not automatically wrong: a chapter reusing a twin an
        earlier chapter already spent (ch07 reuses FE8 Ch6) hands the party an extra
        chapter of exp the vanilla curve does not contain, and that is the alarm #367 asked
        for. Read the row, then decide."""
        off = ['%s %.2fx' % (r['id'], r['yield_ratio']) for r in self.rows
               if r['yield_ratio'] is not None and abs(r['yield_ratio'] - 1.0) > 0.12]
        self.assertEqual([], off)

    def test_the_party_lands_where_the_vanilla_partys_lands(self):
        """The cross-check that makes the absolute number trustworthy: feed the same party
        the TWIN's rosters instead of ours and it must reach the same level, within one."""
        for r in self.rows:
            if r['twin_level_after'] is None:
                continue
            self.assertLessEqual(abs(r['level_after'] - r['twin_level_after']), 1,
                                 '%s: ours L%s vs twin L%s'
                                 % (r['id'], r['level_after'], r['twin_level_after']))


class GeneratedBlock(unittest.TestCase):
    def test_the_pacing_doc_block_is_fresh(self):
        have = open(ec.PACING_DOC, encoding='utf-8').read()
        self.assertEqual(ec.rewrite(have), have,
                         'docs/fe8-pacing-reference.md\'s party-level band is stale -- '
                         'regenerate: python3 tools/exp_curve.py --write')

    def test_the_fence_is_present_exactly_once(self):
        have = open(ec.PACING_DOC, encoding='utf-8').read()
        self.assertEqual(1, have.count(ec.BEGIN))
        self.assertEqual(1, have.count(ec.END))

    def test_a_final_chapter_with_no_curated_twin_renders_instead_of_crashing(self):
        """Every hosted chapter has a curated `parity_reference` today. The next one may
        land before its twin is curated, and the failure then must be a row that says so --
        not a TypeError out of the renderer that takes the whole test module with it."""
        rows = [dict(r) for r in ec.simulate()]
        rows[-1].update(reference='FE8 Ch7', twin_bodies=None, twin_pot=None,
                        yield_ratio=None, twin_level_after=None)
        self.assertIn('--', ec.render(rows))

    def test_rewriting_a_doc_with_no_fence_is_refused(self):
        with self.assertRaises(ValueError):
            ec.rewrite('# a doc with no generated block\n')


if __name__ == '__main__':
    unittest.main(verbosity=2)
