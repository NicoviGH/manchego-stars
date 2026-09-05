#!/usr/bin/env python3
"""Tests for tools/difficulty.py.

The pure metrics layer (durability / throughput / carry) is tested with synthetic
combatants and hand-computed oracles; the I/O layer is tested against real Ch1 data
(our cast's effective stats and the goblin enemy table). Run:

    python3 tools/test_difficulty.py
"""
import contextlib
import io
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fe_combat as fc
import difficulty as df
import build_campaign as bc


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


class EnemyPressure(unittest.TestCase):
    """Per-deploy-slot enemy pressure vs a fixed yardstick (the #48 parity metric).

    threat/slot = Σ(enemy dpr vs yardstick) ÷ deploy cap;
    clear-load/slot = Σ(yardstick rounds-to-kill each enemy) ÷ deploy cap.
    The yardstick cancels in an ours-vs-vanilla ratio."""

    def _yard(self):
        return combatant('yard', hp=20, pow_=0, skl=0, spd=0, dfc=0, res=0, lck=0,
                         con=20, weapon='iron-sword')

    def test_threat_and_clearload_per_slot_with_hand_oracle(self):
        yard = self._yard()
        # e1 (iron-lance, +1 triangle vs yard's sword): dpr = (10+7+1)*1*(80+15)/100 = 17.1;
        #   yard->e1 dmg = (5-1)=4 @ (90-15)% = 3.0/round -> 20/3.0 = 6.6667 rounds.
        e1 = combatant('e1', hp=20, pow_=10, skl=0, spd=0, dfc=0, con=20, weapon='iron-lance')
        # e2 (iron-sword, neutral): dpr = (4+5)*1*90/100 = 8.1;
        #   yard->e2 dmg = 5 @ 90% = 4.5/round -> 20/4.5 = 4.4444 rounds.
        e2 = combatant('e2', hp=20, pow_=4, skl=0, spd=0, dfc=0, con=20, weapon='iron-sword')
        threat, clearload = df.enemy_pressure([e1, e2], deploy_cap=2, yardstick=yard)
        self.assertAlmostEqual(threat, (17.1 + 8.1) / 2)
        self.assertAlmostEqual(clearload, (20 / 3.0 + 20 / 4.5) / 2)

    def test_pressure_scales_inversely_with_deploy_cap(self):
        yard = self._yard()
        e1 = combatant('e1', hp=20, pow_=10, skl=0, spd=0, dfc=0, con=20, weapon='iron-lance')
        t2, c2 = df.enemy_pressure([e1], deploy_cap=2, yardstick=yard)
        t4, c4 = df.enemy_pressure([e1], deploy_cap=4, yardstick=yard)
        self.assertAlmostEqual(t2, 2 * t4)
        self.assertAlmostEqual(c2, 2 * c4)


class PressureVerdict(unittest.TestCase):
    def test_within_band_both_metrics_is_ok(self):
        v = df.pressure_verdict((10.0, 5.0), (10.0, 4.5), band=0.25)
        self.assertAlmostEqual(v['threat_ratio'], 1.0)
        self.assertEqual(v['threat'], 'OK')
        self.assertEqual(v['load'], 'OK')          # 5.0/4.5 = 1.11, inside ±25%
        self.assertEqual(v['verdict'], 'OK')

    def test_threat_above_band_is_harder_and_off(self):
        v = df.pressure_verdict((15.0, 4.5), (10.0, 4.5), band=0.25)
        self.assertEqual(v['threat'], 'harder')    # 1.5 ratio
        self.assertEqual(v['verdict'], 'OFF')

    def test_clearload_below_band_is_easier_and_off(self):
        v = df.pressure_verdict((10.0, 2.0), (10.0, 4.5), band=0.25)
        self.assertEqual(v['load'], 'easier')      # 0.44 ratio
        self.assertEqual(v['verdict'], 'OFF')


class CurveGate(unittest.TestCase):
    """The --check gate (#48 (b)): PER-CHAPTER opt-in. We author chapters as we go, so the
    gate enforces a chapter only once content marks it balance-final with `balance_locked:
    true`. A LOCKED chapter must be at-parity, reliably measured, AND have a curated
    reference -- otherwise it fails loudly (you can't lock a hollow/unmeasurable chapter).
    UNLOCKED chapters (unwritten or mid-authoring) are informational and never gate, so an
    in-progress chapter never reddens CI. With zero locks the gate passes (enforces
    nothing), so --check can ship before any chapter is locked. (#48 (b), per-chapter)."""

    def _row(self, label, locked=False, has_ref=True, verdict='OK', boss_drop=False,
             role=()):
        return {'label': label, 'locked': locked, 'has_ref': has_ref,
                'verdict': verdict, 'boss_drop': boss_drop, 'role': list(role)}

    def test_no_locked_chapters_passes_even_when_some_are_off_parity(self):
        # The unwritten-chapters case: CH3-7 read OFF but aren't locked -> no gate.
        rows = [self._row('CH1', locked=True, verdict='OK'),
                self._row('CH3', locked=False, verdict='OFF', boss_drop=True),
                self._row('CH8', locked=False, has_ref=False, verdict=None)]
        self.assertEqual(df.curve_gate_failures(rows), [])

    def test_locked_off_parity_chapter_fails(self):
        rows = [self._row('CH1', locked=True, verdict='OK'),
                self._row('CH2', locked=True, verdict='OFF')]
        self.assertEqual(df.curve_gate_failures(rows), ['CH2'])

    def test_locked_at_parity_chapter_passes(self):
        rows = [self._row('CH1', locked=True, verdict='OK')]
        self.assertEqual(df.curve_gate_failures(rows), [])

    def test_locked_dropped_boss_fails_even_if_verdict_ok(self):
        # A dropped boss makes the verdict unreliable -- an unreliable OK is not a pass.
        rows = [self._row('CH3', locked=True, verdict='OK', boss_drop=True)]
        self.assertEqual(df.curve_gate_failures(rows), ['CH3'])

    def test_locking_a_chapter_with_no_curated_reference_fails(self):
        # Can't lock a chapter the metric can't measure -- a config mistake, surfaced loudly.
        rows = [self._row('CH8', locked=True, has_ref=False, verdict=None)]
        self.assertEqual(df.curve_gate_failures(rows), ['CH8'])

    def test_unlocked_off_parity_chapter_never_gates(self):
        rows = [self._row('CH2', locked=False, verdict='OFF', boss_drop=True)]
        self.assertEqual(df.curve_gate_failures(rows), [])

    def test_locked_chapter_with_a_role_finding_fails_even_at_parity(self):
        # #284: ch02/ch03 shipped paper bosses for months while the aggregate read OK,
        # because a single soft boss dissolves into a 23-unit average and nothing ever READ
        # the per-unit warning. A balance-final chapter with an open role finding is a
        # contradiction, so the gate now reads it.
        rows = [self._row('CH2', locked=True, verdict='OK',
                          role=['boss raider-captain takes 1.2 rounds to kill; ...'])]
        self.assertEqual(df.curve_gate_failures(rows), ['CH2'])

    def test_unlocked_chapter_with_a_role_finding_stays_informational(self):
        # Mid-authoring chapters warn without reddening CI -- same opt-in as every other
        # arm of this gate.
        rows = [self._row('CH6', locked=False, verdict='OK', role=['boss messie takes 2.7 ...'])]
        self.assertEqual(df.curve_gate_failures(rows), [])

    def test_locked_chapter_with_no_role_findings_passes(self):
        rows = [self._row('CH2', locked=True, verdict='OK', role=[])]
        self.assertEqual(df.curve_gate_failures(rows), [])


class VanillaAiBytes(unittest.TestCase):
    """#335: an AI vector as vanilla writes it -> the 4 bytes the engine loads.

    Vanilla writes its own UnitDefinition AI in the decomp's compiled EA macros
    (include/EA_Standard_Library/AI_Helpers.h, reached from events_udefs.c via EAstdlib.h),
    falling back to raw literals for the combinations that have no macro. We read BOTH,
    from the header itself -- a hand-copied macro table here would be a second source of
    truth for the exact bytes this whole feature exists to keep faithful."""

    def test_literal_bytes_pass_through(self):
        self.assertEqual(df.ai_bytes('{0x0, 0x3, 0x9, 0x0}'), (0x00, 0x03, 0x09, 0x00))

    def test_a_two_byte_macro_expands_in_place(self):
        # AI_Helpers.h: #define GuardTileAI 0x03,0x03
        self.assertEqual(df.ai_bytes('{GuardTileAI, 0x9, 0x20}'), (0x03, 0x03, 0x09, 0x20))

    def test_a_four_byte_macro_fills_the_whole_vector(self):
        # #define NeverMoveAI 0x03,0x03,0x04,0x20
        self.assertEqual(df.ai_bytes('{NeverMoveAI}'), (0x03, 0x03, 0x04, 0x20))

    def test_a_missing_ai_block_is_all_zeros(self):
        # No .ai in a UnitDefinition means {0,0,0,0} = ActionInRange + MoveToEnemy, which is
        # a PURSUER. Two of vanilla Ch6's red units are exactly that.
        self.assertEqual(df.ai_bytes(None), (0x00, 0x00, 0x00, 0x00))

    def test_macros_are_read_from_the_decomp_header_not_a_local_copy(self):
        # The guard against the mistake this feature is fixing one level up: every macro the
        # header defines must resolve, so adding one there needs no edit here.
        self.assertIn('AttackInRangeAI', df.AI_MACROS)
        self.assertEqual(df.AI_MACROS['AttackInRangeAI'], (0x00, 0x03))
        self.assertEqual(df.AI_MACROS['DoNothing'], (0x06, 0x03))


class DonorResolution(unittest.TestCase):
    """#335: each of our enemies stands in for a unit in its chapter's vanilla twin, and the
    twin's UnitDefinition already carries that unit's AI. The chapter YAMLs have named their
    counterpart in a comment since they were written ("vanilla brigand @ (7,2) L3 iron-axe");
    `donor:` promotes that prose to a field so the build can read it.

    Keyed on the twin's map COORDINATE, the way the comments already write it. Vanilla stacks
    several units on one tile in places, so the reference may add `class`/`level` to pick one
    -- and an ambiguous reference is an ERROR, never a silent first-match."""

    def test_a_coordinate_resolves_to_that_units_ai(self):
        # vanilla Ch3's brigand at (7,2): AttackInRangeAI, the static line.
        self.assertEqual(df.resolve_donor('FE8 Ch3', [7, 2])['ai'], (0x00, 0x03, 0x09, 0x00))

    def test_the_boss_tile_resolves_to_the_boss(self):
        # Bazba at (14,1) -- GuardTileAI + the GuardTile config bit.
        donor = df.resolve_donor('FE8 Ch3', [14, 1])
        self.assertEqual(donor['ai'], (0x03, 0x03, 0x09, 0x20))
        self.assertEqual(donor['classIndex'], 'CLASS_BRIGAND')

    def test_a_post_two_units_share_is_ambiguous_and_raises(self):
        # The prologue stands its two caravan guards on (14,7) with different AI
        # ({0,0xA,..} scripted approach vs {0,0x12,..} charge-on-turn-2). First-match would
        # silently pick one. Posts are otherwise unique in every twin we use.
        with self.assertRaises(ValueError) as caught:
            df.resolve_donor('FE8 Prologue', [14, 7])
        self.assertIn('disagree', str(caught.exception).lower())

    def test_level_disambiguates_a_shared_post(self):
        self.assertEqual(
            df.resolve_donor('FE8 Prologue', {'at': [14, 7], 'level': 1})['ai'],
            (0x00, 0x0A, 0x00, 0x00))
        self.assertEqual(
            df.resolve_donor('FE8 Prologue', {'at': [14, 7], 'level': 2})['ai'],
            (0x00, 0x12, 0x02, 0x00))

    def test_a_coordinate_no_red_unit_occupies_raises(self):
        with self.assertRaises(ValueError) as caught:
            df.resolve_donor('FE8 Ch3', [0, 0])
        self.assertIn('matches no red unit', str(caught.exception).lower())

    def test_an_uncurated_twin_raises_rather_than_returning_nothing(self):
        with self.assertRaises(ValueError):
            df.resolve_donor('FE8 Ch99', [1, 1])


class EnemyAiBytes(unittest.TestCase):
    """#335: an enemy's AI is BORROWED from its vanilla donor unless the chapter says
    otherwise in writing. No label vocabulary in between -- the labels were the translation
    layer every one of these bugs lived in (`aggressive` meaning one thing in the YAML and
    another in five injectors; `defensive` and `hold_position` being the same bytes under
    two names; ch00's label wired to nothing at all)."""

    def _enemy(self, **kw):
        return dict({'id': 'e', 'class': 'brigand', 'level': 3}, **kw)

    def test_an_enemy_borrows_its_donors_ai(self):
        chap = {'parity_reference': 'FE8 Ch3'}
        self.assertEqual(df.enemy_ai_bytes(chap, self._enemy(donor=[7, 2])),
                         (0x00, 0x03, 0x09, 0x00))

    def test_an_override_replaces_the_donors_ai(self):
        chap = {'parity_reference': 'FE8 Ch3'}
        enemy = self._enemy(donor=[7, 2], ai_override={
            'ai': '{DefaultAI, 0x9, 0x0}', 'why': 'our map moves the fight to the entrance'})
        self.assertEqual(df.enemy_ai_bytes(chap, enemy), (0x00, 0x00, 0x09, 0x00))

    def test_an_override_may_stand_alone_where_we_field_a_unit_vanilla_does_not(self):
        # ch04's wolf pack is six units where vanilla loads four revenants on one corner
        # tile; there is no single donor to point at, so the override IS the declaration.
        chap = {'parity_reference': 'FE8 Ch4'}
        enemy = self._enemy(ai_override={'ai': '{AttackInRangeAI, 0xC, 0x0}',
                                         'why': 'the pack is ours, not a vanilla unit'})
        self.assertEqual(df.enemy_ai_bytes(chap, enemy), (0x00, 0x03, 0x0C, 0x00))

    def test_an_enemy_with_neither_is_an_error_not_a_default(self):
        # A default here is how ch00 shipped an ai_pattern nobody read. Refuse instead.
        chap = {'parity_reference': 'FE8 Ch3'}
        with self.assertRaises(ValueError):
            df.enemy_ai_bytes(chap, self._enemy())

    def test_an_override_without_a_why_is_refused_at_build_time(self):
        # The `why` is the whole difference between a declared divergence and a silenced
        # guard. Reporting it only in the curve gate left it optional for every chapter
        # that is not balance_locked -- which is where new AI actually gets authored.
        chap = {'parity_reference': 'FE8 Ch3'}
        enemy = self._enemy(donor=[7, 2], ai_override={'ai': '{DefaultAI, 0x9, 0x0}'})
        with self.assertRaises(ValueError):
            df.enemy_ai_bytes(chap, enemy)

    def test_an_override_with_a_blank_why_is_refused_too(self):
        chap = {'parity_reference': 'FE8 Ch3'}
        enemy = self._enemy(donor=[7, 2],
                            ai_override={'ai': '{DefaultAI, 0x9, 0x0}', 'why': '   '})
        with self.assertRaises(ValueError):
            df.enemy_ai_bytes(chap, enemy)


class AiDonorFindings(unittest.TestCase):
    """The guard. Same contract as role_findings(): a list of strings, empty == clean."""

    def _chap(self, enemies, ref='FE8 Ch3'):
        return {'parity_reference': ref, 'enemy_units': enemies}

    def test_a_fully_donored_chapter_is_clean(self):
        self.assertEqual(df.ai_donor_findings(
            self._chap([{'id': 'a', 'donor': [7, 2]}, {'id': 'b', 'donor': [14, 1]}])), [])

    def test_an_enemy_with_no_donor_is_reported(self):
        findings = df.ai_donor_findings(self._chap([{'id': 'stray'}]))
        self.assertTrue(any('stray' in f for f in findings), findings)

    def test_an_override_without_a_reason_is_reported(self):
        findings = df.ai_donor_findings(self._chap(
            [{'id': 'a', 'donor': [7, 2], 'ai_override': {'ai': '{DefaultAI, 0x9, 0x0}'}}]))
        self.assertTrue(any('why' in f for f in findings), findings)

    def test_an_unresolvable_donor_is_reported_with_the_reason_it_failed(self):
        findings = df.ai_donor_findings(self._chap([{'id': 'a', 'donor': [14, 7]}],
                                                   ref='FE8 Prologue'))
        self.assertTrue(any('disagree' in f.lower() for f in findings), findings)

    def test_reinforcement_waves_are_checked_too(self):
        # ch02 declares two of its nine reds under `reinforcements:`.
        chap = self._chap([{'id': 'a', 'donor': [7, 2]}])
        chap['reinforcements'] = [{'id': 'late'}]
        findings = df.ai_donor_findings(chap)
        self.assertTrue(any('late' in f for f in findings), findings)

    def test_an_uncurated_twin_yields_no_findings(self):
        self.assertEqual(
            df.ai_donor_findings(self._chap([{'id': 'a'}], ref='FE8 Ch99')), [])


class DonorGroupResolution(unittest.TestCase):
    """A donor reference need not be a coordinate. ch01 and ch06 sit on a DIFFERENT map
    donor from their parity twin (Ch13Eirika and Ch13Ephraim), so no tile of theirs lines up
    with the twin at all -- but their forces pair by role, 1:1. And coordinates are actively
    treacherous as a lone key: ch05's bone-archer reinforcement wave sits on (13,0), where
    vanilla Ch5 happens to park an ARMOR_KNIGHT boss.

    So the reference is a MATCH SPEC over the twin's red force -- coordinate, class, level,
    any combination -- and it resolves when every unit it matches SHARES an AI. Vanilla's
    three L2 soldiers behave identically, so 'the L2 soldiers' is a well-formed donor for our
    group of three; where the matches disagree, it raises and asks for a narrower spec."""

    def test_a_class_spec_resolves_a_whole_group_that_shares_one_ai(self):
        # vanilla Ch3's five L3 brigands are all AttackInRangeAI -- one behaviour, so "the
        # L3 brigands" is a well-formed donor for a group of ours.
        self.assertEqual(
            df.resolve_donor('FE8 Ch3', {'class': 'CLASS_BRIGAND', 'level': 3})['ai'],
            (0x00, 0x03, 0x09, 0x00))

    def test_a_class_spec_spanning_line_and_reinforcements_raises(self):
        # Ch1's three L2 SOLDIERs look interchangeable and are not: the two on the line are
        # AttackInRange, the one in the reinforcement wave PURSUES. Same class, same level,
        # different chapter role -- exactly the collapse that authoring by feel produces.
        with self.assertRaises(ValueError) as caught:
            df.resolve_donor('FE8 Ch1', {'class': 'CLASS_SOLDIER', 'level': 2})
        self.assertIn('disagree', str(caught.exception).lower())

    def test_a_coordinate_still_works_where_the_map_is_the_twins(self):
        self.assertEqual(df.resolve_donor('FE8 Ch3', [7, 2])['ai'], (0x00, 0x03, 0x09, 0x00))

    def test_coordinate_and_class_combine(self):
        self.assertEqual(
            df.resolve_donor('FE8 Ch2', {'at': [14, 9], 'class': 'CLASS_ARCHER'})['ai'],
            (0x00, 0x12, 0x09, 0x00))

    def test_a_spec_matching_nothing_raises(self):
        with self.assertRaises(ValueError) as caught:
            df.resolve_donor('FE8 Ch3', {'class': 'CLASS_PEGASUS_KNIGHT'})
        self.assertIn('matches no red unit', str(caught.exception).lower())


class PerPositionDonors(unittest.TestCase):
    """An entry may carry ONE donor per position. ch04's `mogall` entry places four units on
    vanilla Ch4's four mogall tiles, and those four vanilla mogalls run THREE different AIs
    (AttackInRange x2, pursue, charge-after-one-turn). A single donor per entry would flatten
    that into one behaviour and quietly lose the map's texture -- the same collapse that
    authoring by label produced in the first place."""

    CHAP = {'parity_reference': 'FE8 Ch4'}

    def test_a_list_of_donors_gives_each_position_its_own_ai(self):
        enemy = {'id': 'mogall', 'count': 4,
                 'positions': [[11, 6], [13, 7], [12, 8], [13, 11]],
                 'donor': [[11, 6], [13, 7], [12, 8], [13, 11]]}
        self.assertEqual([df.enemy_ai_bytes(self.CHAP, enemy, i) for i in range(4)],
                         [(0x00, 0x03, 0x0C, 0x00), (0x00, 0x00, 0x0C, 0x00),
                          (0x00, 0x12, 0x0C, 0x00), (0x00, 0x03, 0x0C, 0x00)])

    def test_a_single_donor_still_covers_every_position(self):
        enemy = {'id': 'pack', 'count': 3, 'positions': [[1, 1], [2, 2], [3, 3]],
                 'donor': [11, 6]}
        self.assertEqual([df.enemy_ai_bytes(self.CHAP, enemy, i) for i in range(3)],
                         [(0x00, 0x03, 0x0C, 0x00)] * 3)

    def test_a_donor_list_that_does_not_cover_every_position_raises(self):
        # Silently reusing the last donor would ship a unit nobody grounded.
        enemy = {'id': 'short', 'count': 3, 'positions': [[1, 1], [2, 2], [3, 3]],
                 'donor': [[11, 6], [13, 7]]}
        with self.assertRaises(ValueError) as caught:
            df.enemy_ai_bytes(self.CHAP, enemy, 2)
        self.assertIn('2 donor', str(caught.exception))

    def test_a_bare_coordinate_is_not_read_as_a_list_of_two_donors(self):
        # `donor: [11, 6]` is ONE coordinate, not two donors. Getting this backwards would
        # make every single-donor entry silently per-position.
        enemy = {'id': 'one', 'positions': [[1, 1]], 'donor': [11, 6]}
        self.assertEqual(df.enemy_ai_bytes(self.CHAP, enemy, 0), (0x00, 0x03, 0x0C, 0x00))


class AiGateArm(unittest.TestCase):
    """#335 joins #284's `role` arm on the SAME opt-in. AI is part of parity -- a chapter
    marked balance-final whose force is not grounded in its twin is the same contradiction as
    one carrying an open per-unit finding."""

    def _row(self, label, locked=False, ai=()):
        return {'label': label, 'locked': locked, 'has_ref': True, 'verdict': 'OK',
                'boss_drop': False, 'role': [], 'ai': list(ai)}

    def test_a_locked_chapter_with_an_ungrounded_enemy_fails(self):
        rows = [self._row('CH2', locked=True, ai=['raider-captain: no donor'])]
        self.assertEqual(df.curve_gate_failures(rows), ['CH2'])

    def test_an_unlocked_chapter_stays_advisory(self):
        rows = [self._row('CH6', locked=False, ai=['nerra: no donor'])]
        self.assertEqual(df.curve_gate_failures(rows), [])

    def test_a_locked_chapter_with_every_enemy_grounded_passes(self):
        self.assertEqual(df.curve_gate_failures([self._row('CH3', locked=True)]), [])


class AiFindingsInTheCurveReport(unittest.TestCase):
    """The report must read EACH chapter's own donors. Runs against the real campaign data:
    the wiring is the thing under test, and a report that silently graded the wrong chapter
    would look exactly like a clean one."""

    def _rows(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return {r['label'].split()[0]: r
                    for r in df.curve_report('rime-of-the-frostmaiden')}

    def test_a_fully_donored_chapter_reports_clean(self):
        self.assertEqual(self._rows()['CH3']['ai'], [])

    def test_every_row_carries_the_ai_key_so_the_gate_can_read_it(self):
        self.assertTrue(all('ai' in r for r in self._rows().values()))


class MirrorShare(unittest.TestCase):
    """mirror% -- the share of the TWIN's force a chapter reproduces exactly (class + level).

    It is what separates a copy-x1.00 from a composed-x1.00: the parity ratio is an
    aggregate over stats, so a chapter that transcribes its twin unit for unit and a
    chapter that arrives at the same per-slot pressure from a different force read
    identically. #367's finding was that ch06 is the first, and its x1.00 was a checksum
    on the donor pipeline rather than a measurement.

    vanilla Prologue's red force is 3 fighters: L4, L1, L2.
    """

    def _chap(self, enemies, ref='FE8 Prologue'):
        return {'parity_reference': ref, 'enemy_units': enemies}

    def test_a_force_transcribed_unit_for_unit_is_a_full_mirror(self):
        m = df.mirror_share(self._chap([{'id': 'a', 'class': 'fighter', 'level': 4},
                                        {'id': 'b', 'class': 'fighter', 'level': 1},
                                        {'id': 'c', 'class': 'fighter', 'level': 2}]))
        self.assertEqual((m['shared'], m['twin']), (3, 3))
        self.assertEqual(m['pct'], 100.0)

    def test_a_force_sharing_nothing_with_its_twin_mirrors_zero(self):
        m = df.mirror_share(self._chap([{'id': 'a', 'class': 'mage', 'level': 4}]))
        self.assertEqual((m['shared'], m['pct']), (0, 0.0))

    def test_the_same_class_at_a_different_level_is_not_a_mirror(self):
        # class alone is not the unit: an L9 fighter is not the twin's L1 one.
        m = df.mirror_share(self._chap([{'id': 'a', 'class': 'fighter', 'level': 9}]))
        self.assertEqual(m['shared'], 0)

    def test_a_partial_match_is_a_share_of_the_TWINS_force(self):
        m = df.mirror_share(self._chap([{'id': 'a', 'class': 'fighter', 'level': 4}]))
        self.assertEqual((m['shared'], m['twin']), (1, 3))
        self.assertAlmostEqual(m['pct'], 100.0 / 3)

    def test_count_expands_into_that_many_bodies(self):
        # our two L2 fighters can only mirror the twin's ONE: the intersection is a
        # multiset, so a doubled body does not score twice.
        m = df.mirror_share(self._chap([{'id': 'a', 'class': 'fighter', 'level': 2,
                                         'count': 2}]))
        self.assertEqual(m['shared'], 1)

    def test_a_composition_entry_expands_per_member(self):
        m = df.mirror_share(self._chap([{'id': 'a', 'level': 2,
                                         'composition': ['fighter', 'fighter']}]))
        self.assertEqual(m['shared'], 1)

    def test_fielding_more_than_the_twin_never_reads_above_100(self):
        m = df.mirror_share(self._chap([{'id': 'a', 'class': 'fighter', 'level': 4},
                                        {'id': 'b', 'class': 'fighter', 'level': 1},
                                        {'id': 'c', 'class': 'fighter', 'level': 2},
                                        {'id': 'd', 'class': 'fighter', 'level': 2}]))
        self.assertEqual(m['pct'], 100.0)

    def test_reinforcement_waves_count_as_part_of_our_force(self):
        chap = self._chap([{'id': 'a', 'class': 'fighter', 'level': 4}])
        chap['reinforcements'] = [{'id': 'late', 'class': 'fighter', 'level': 1}]
        self.assertEqual(df.mirror_share(chap)['shared'], 2)

    def test_a_staff_only_unit_still_counts_as_a_body(self):
        # the parity metric DROPS a unit with no modeled weapon; mirror% is about the
        # force's SHAPE, so a healer the twin fields is a unit the chapter did or did not
        # reproduce.
        m = df.mirror_share(self._chap([{'id': 'h', 'class': 'troubadour', 'level': 6}],
                                       ref='FE8 Ch6'))
        self.assertEqual(m['shared'], 1)

    def test_an_uncurated_twin_has_no_mirror_to_measure(self):
        self.assertIsNone(df.mirror_share(self._chap([{'id': 'a'}], ref='FE8 Ch99')))


class PerBodyLevels(unittest.TestCase):
    """`levels:` is a PER-BODY list, and it is what the ROM writes.

    ch02's rear-raider wave declares `count: 2` with `levels: [2, 3]` and no `level:` --
    build_campaign zips positions with levels to emit the two UnitDefinitions. A reader
    that only knows `level:` falls through to the default and models the pair as two L1
    brigands, which is neither what the chapter declares nor what the ROM contains.
    """

    def test_a_levels_list_gives_each_body_its_own_level(self):
        self.assertEqual(df._body_levels({'count': 2, 'levels': [2, 3]}), [2, 3])

    def test_without_levels_every_body_carries_the_entrys_level(self):
        self.assertEqual(df._body_levels({'count': 3, 'level': 5}), [5, 5, 5])

    def test_a_bare_entry_is_one_body_at_level_one(self):
        self.assertEqual(df._body_levels({}), [1])

    def test_levels_disagreeing_with_count_is_a_contradiction_not_a_truncation(self):
        # zip() would silently drop the third body; two declarations of the same fact
        # that disagree is a data error, and the ROM emitter zips them too.
        with self.assertRaises(ValueError):
            df._body_levels({'count': 3, 'levels': [2, 3]})

    def test_a_wave_with_per_body_levels_mirrors_each_of_them(self):
        chap = {'parity_reference': 'FE8 Prologue',
                'enemy_units': [{'id': 'a', 'class': 'fighter', 'count': 2,
                                 'levels': [1, 2]}]}
        self.assertEqual(df.mirror_share(chap)['shared'], 2)


class EveryRosterKeyIsAForce(unittest.TestCase):
    """The module already names its three roster keys once, in AI_ROSTER_KEYS. A force
    builder that hand-rolls two of them silently scores a wave under the third as pure
    divergence."""

    def test_a_wave_under_any_roster_key_counts_as_our_force(self):
        for key in df.AI_ROSTER_KEYS:
            chap = {'parity_reference': 'FE8 Prologue',
                    key: [{'id': 'a', 'class': 'fighter', 'level': 4}]}
            self.assertEqual(df.mirror_share(chap)['shared'], 1, key)


class ReinforcementsAreOurForce(unittest.TestCase):
    """The twin's curated arrays fold its reinforcement waves in unconditionally, so a
    force builder that reads only our opening board compares 7 bodies against 9 and calls
    the missing two divergence. ch06 already discovered this and worked around it by
    declaring its turn-4 wave inside `enemy_units`; ch02 used the `reinforcements:` key
    and was never counted.
    """

    def _ch02(self):
        return bc._load_chapter_yaml('rime-of-the-frostmaiden', bc.chapter_yaml_for('ch02'))

    def test_our_side_fields_as_many_bodies_as_the_twin(self):
        p = df._chapter_pressure(self._ch02())
        self.assertEqual(p['n_ours'], p['n_vanilla'])

    def test_the_wave_is_modeled_at_its_declared_levels(self):
        # `levels: [2, 3]`, so the two bodies must differ -- an L1/L1 pair (the old default)
        # and an L2/L2 pair (count-expansion of one level) both fail here.
        bodies = [u for ed, u in df.chapter_units(self._ch02())
                  if ed.get('id') == 'rear-raiders']
        self.assertEqual(len(bodies), 2)
        brig = df._class_base('CLASS_BRIGAND')
        growths = df._class_growths('CLASS_BRIGAND')
        self.assertEqual(sorted(b.hp for b in bodies),
                         sorted(df.autolevel(brig, growths, lv)['baseHP'] for lv in (2, 3)))

    def test_ch02_transcribes_its_twin_once_its_wave_is_counted(self):
        self.assertEqual(df.mirror_share(self._ch02())['pct'], 100.0)


class OneForceEveryReader(unittest.TestCase):
    """Widening "what is this chapter's force" for the verdict and leaving the readers around
    it on `enemy_units` produces a report that contradicts itself on one page: ch02 printed
    "ours (9 enemies)" two lines above "ours line 7 · reinf 0". Every reader of the force
    reads the same roster."""

    def _ch02(self):
        return bc._load_chapter_yaml('rime-of-the-frostmaiden', bc.chapter_yaml_for('ch02'))

    def test_the_dynamics_split_buckets_the_wave_the_verdict_counted(self):
        g = df.chapter_enemy_groups(self._ch02())
        self.assertEqual(len(g['reinforcements']), 2)
        self.assertEqual(sum(len(v) for v in g.values()),
                         df._chapter_pressure(self._ch02())['n_ours'])

    def test_an_entry_under_a_reinforcement_key_is_a_reinforcement_by_the_KEY(self):
        # ch02's wave carries `trigger_turn`, not `arrives_turn`: the key it is declared
        # under is what makes it a reinforcement, and an arrives_turn test alone read it
        # as turn-1 line.
        chap = {'reinforcements': [{'id': 'w', 'class': 'brigand', 'level': 2,
                                    'inventory': [{'id': 'iron-axe'}]}]}
        g = df.chapter_enemy_groups(chap)
        self.assertEqual(len(g['reinforcements']), 1)
        self.assertEqual(g['line'], [])

    def test_a_staff_only_wave_is_reported_as_unmodeled(self):
        chap = {'reinforcements': [{'id': 'healer', 'class': 'priest', 'level': 3,
                                    'is_boss': True, 'inventory': [{'id': 'heal'}]}]}
        self.assertEqual([d['id'] for d in df.unmodeled_enemies(chap)], ['healer'])

    def test_the_cast_tables_grade_the_same_force_as_the_verdict(self):
        chap, roster, line, bosses, cap, labels = df.load_field(
            'rime-of-the-frostmaiden', 'ch02')
        self.assertEqual(len(line) + len(bosses),
                         df._chapter_pressure(chap)['n_ours'])

    def test_role_findings_grade_a_unit_declared_under_a_reinforcement_key(self):
        # a monstrous boss hidden under `reinforcements:` was invisible to the per-unit
        # gate arm while contributing its threat to the aggregate.
        chap = {'parity_reference': 'FE8 Prologue',
                'reinforcements': [{'id': 'sleeper', 'class': 'general', 'level': 20,
                                    'is_boss': True,
                                    'inventory': [{'id': 'silver-lance'}]}]}
        self.assertTrue(any('sleeper' in f for f in df.role_findings(chap, 'FE8 Prologue')))


class DeclaredLevelsEverywhere(unittest.TestCase):
    def test_a_composition_wave_honors_its_per_body_levels(self):
        chap = {'parity_reference': 'FE8 Prologue',
                'enemy_units': [{'id': 'a', 'composition': ['fighter', 'fighter'],
                                 'levels': [1, 2]}]}
        self.assertEqual(df.mirror_share(chap)['shared'], 2)

    def test_levels_must_agree_with_the_positions_the_rom_zips_them_against(self):
        with self.assertRaises(ValueError):
            df._body_levels({'levels': [2, 3], 'positions': [[0, 6]]})

    def test_a_composition_declares_its_body_count_too(self):
        # the bag's length is the body count, so `levels:` must match it -- indexing past
        # the list would raise IndexError deep in the expander instead of naming the entry.
        with self.assertRaises(ValueError):
            df._body_levels({'id': 'bag', 'composition': ['fighter', 'fighter'],
                             'levels': [1]})

    def test_a_composition_without_levels_is_one_body_per_member(self):
        self.assertEqual(df._body_levels({'composition': ['a', 'b'], 'level': 4}), [4, 4])

    def test_a_boss_carries_ITS_bodys_level_as_its_malus_floor(self):
        # `base_level` is the >= baseLevel gate a difficulty malus floors against. Reading
        # it off `level:` while the body comes from `levels:` gives a boss base_level 1 and
        # a malus the ROM never applies.
        chap = {'enemy_units': [{'id': 'b', 'class': 'general', 'is_boss': True,
                                 'levels': [10],
                                 'inventory': [{'id': 'silver-lance'}]}]}
        shifts = {'tutorial': 4, 'normal': 2, 'difficult': 3}
        plain = df.chapter_units(chap)[0][1]
        shifted = df.chapter_units(chap, mode='tutorial', shifts=shifts)[0][1]
        self.assertEqual(plain.hp, shifted.hp)   # boss is at its baseLevel: no malus

    def test_solo_contributors_counts_BODIES_not_the_count_field(self):
        # a `levels:`-only entry has no `count:`; reading count as 1 made every body of it
        # eligible for the single-unit NOTE.
        self.assertEqual(df._entry_body_count({'levels': [2, 3, 4]}), 3)
        self.assertEqual(df._entry_body_count({'count': 2, 'level': 3}), 2)
        self.assertEqual(df._entry_body_count({'composition': ['a', 'b', 'c']}), 3)


class RoleFindingsGradeTypesNotBodies(unittest.TestCase):
    """`role_findings` asks a per-UNIT question -- is this unit's threat an outlier, is this
    boss too soft -- and the answer is a property of the unit type, not of how many copies
    stand on the map. Expanding it per body repeated every warning `count` times and made
    the boss census count copies: ch08's `count: 4` ice-troll read as "4 units flagged
    is_boss (ice-troll, ice-troll, ice-troll, ice-troll)". `role` is a `--check` gate arm,
    so that reds CI on the first locked chapter with a multi-copy boss entry."""

    def _ch08(self):
        # ch08 is `status: planned`, so it has no host slot and no CH08_CHAPTER_YAML --
        # read the file directly. It is the live case: a `count: 4` boss entry.
        with open(df.chapter_path('rime-of-the-frostmaiden', 'ch08'), encoding='utf-8') as f:
            return bc.yaml.safe_load(f)

    def test_a_multi_copy_boss_entry_is_ONE_boss(self):
        findings = df.role_findings(self._ch08(), self._ch08().get('parity_reference'))
        census = [f for f in findings if 'flagged is_boss' in f]
        self.assertEqual(census, [], census)

    def test_a_warning_is_stated_once_per_unit_type(self):
        findings = df.role_findings(self._ch08(), self._ch08().get('parity_reference'))
        self.assertEqual(len(findings), len(set(findings)), findings)

    def test_bodies_at_DIFFERENT_levels_are_different_types(self):
        # `levels: [2, 3]` is two distinct units and both get graded; `count: 2` is one.
        ed = {'id': 'w', 'class': 'general', 'levels': [19, 20], 'is_boss': True,
              'inventory': [{'id': 'silver-lance'}]}
        self.assertEqual(len(df._entry_combatants(ed, distinct=True)), 2)
        self.assertEqual(len(df._entry_combatants(dict(ed, levels=None, level=20, count=2),
                                                  distinct=True)), 1)


class GuardsSeeTheWholeRoster(unittest.TestCase):
    def test_the_boss_malus_guard_reads_every_roster_key_and_declared_level(self):
        # `_our_base_level` treats every boss as malus-immune; this guard is what makes that
        # true. A boss declared under `reinforcements:`, or one whose level comes from
        # `levels:`, was invisible to it while still riding the assumption.
        donor = sorted(bc.ENEMY_BASE_SLOT.items())[0]
        uid, slot = donor
        over = df._character_base_level(slot) + 5
        chap = {'reinforcements': [{'id': uid, 'is_boss': True, 'levels': [over],
                                    'class': 'general'}]}
        self.assertEqual(df._boss_entries_over_donor_base_level(chap), [uid])

    def test_a_drop_on_a_reinforcement_wave_is_part_of_the_economy(self):
        chap = {'reinforcements': [{'id': 'w', 'item_drop': 'elixir'}]}
        self.assertEqual(df.chapter_economy(chap)['drops'], ['elixir'])

    def test_a_bag_entry_is_graded_on_its_real_article(self):
        # a `composition` entry carrying a personal line was graded at naked class base
        # once the expander stopped applying it -- the #284 failure mode.
        ed = {'id': 'bag', 'composition': ['general'], 'level': 10,
              'personal': {'hp': 20}, 'inventory_by_class': {'general': ['silver-lance']}}
        plain = df._entry_combatants(ed)[0]
        real = df._entry_combatants(ed, real_article=True)[0]
        self.assertEqual(real.hp, plain.hp + 20)


class DeclaredCountsMustAgree(unittest.TestCase):
    def test_positions_and_count_are_cross_checked_even_without_levels(self):
        # `positions` is what build_campaign zips against; a mismatch models a force the
        # ROM never emits, and mirror% now compares body-for-body against the twin on it.
        with self.assertRaises(ValueError):
            df._body_levels({'id': 'w', 'count': 3, 'level': 2,
                             'positions': [[0, 6], [0, 7]]})

    def test_agreeing_declarations_pass(self):
        self.assertEqual(df._body_levels({'count': 2, 'level': 2,
                                          'positions': [[0, 6], [0, 7]]}), [2, 2])


class MirrorShareOnRealChapters(unittest.TestCase):
    """Against the real campaign, because the wiring is the thing under test."""

    def _mirror(self, ch):
        chap = bc._load_chapter_yaml('rime-of-the-frostmaiden', bc.chapter_yaml_for(ch))
        return df.mirror_share(chap)

    def test_ch06_reproduces_its_twin_exactly(self):
        # ch06 IS vanilla Ch6's 27-unit force, re-sited. This is the number that makes its
        # x1.00 legible as a copy (#367).
        self.assertEqual(self._mirror('ch06')['pct'], 100.0)

    def test_a_composed_chapter_reads_well_under_a_copy(self):
        # ch01 fields ten units against a ten-unit twin and mirrors three of them.
        self.assertEqual(self._mirror('ch01')['shared'], 3)


class MirrorInTheCurveReport(unittest.TestCase):
    def _rows(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return {r['label'].split()[0]: r
                    for r in df.curve_report('rime-of-the-frostmaiden')}

    def test_every_row_carries_its_mirror_share(self):
        self.assertEqual(self._rows()['CH6']['mirror']['pct'], 100.0)

    def test_the_curve_prints_mirror_beside_the_parity_ratio(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            df.curve_report('rime-of-the-frostmaiden')
        text = out.getvalue()
        self.assertIn('mirror', text)
        ch06_row = [l for l in text.splitlines() if 'ch06' in l][0]
        self.assertIn('100%', ch06_row)


class MirrorIsModeInvariant(unittest.TestCase):
    """A difficulty mode shifts STATS, never a unit's class or level (`mode_stats` re-projects
    the same level through the chapter's malus/bonus), and the mode-gated bodies -- ch06's
    Hard-only turn-4 wave, vanilla's Hard reinforcement arrays -- are folded into BOTH sides
    unconditionally. So the force's shape is the same in all three modes and mirror% is
    invariant by construction. The report has to say so: it sits on a row whose banner
    declares the other figures mode-shifted."""

    def _text(self, mode=None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            df.curve_report('rime-of-the-frostmaiden', mode=mode)
        return out.getvalue()

    def _mirror_column(self, text):
        return [l.split()[-2] for l in text.splitlines()
                if l.startswith('  CH') and '%' in l]

    def test_the_mode_banner_names_mirror_among_the_unshifted_figures(self):
        self.assertIn('mirror', self._text(mode='difficult').split('NB')[1].split('=====')[0])

    def test_every_mirror_reads_the_same_in_every_mode(self):
        base = self._mirror_column(self._text())
        self.assertTrue(base)
        for mode in ('tutorial', 'normal', 'difficult'):
            self.assertEqual(self._mirror_column(self._text(mode=mode)), base, mode)


class VanillaUnitDestinations(unittest.TestCase):
    """#335: a vanilla unit's `xPosition`/`yPosition` is often a SPAWN tile, not where it
    fights. `redas` is scripted movement data that walks it from there to its post, and the
    last REDA point is the destination.

    This is load-bearing for donors. Vanilla Ch1's whole force enters on (1,9)/(2,9) and
    Ch5's on (0,0)/(10,0)/(12,0) -- matching a donor on those tiles is matching on "entered
    from the north", which is no identity at all. Matched on DESTINATION, every one of our
    23 ch05 units lands exactly on a vanilla unit's post, and Ch1's two seemingly identical
    L2 fighters separate cleanly (they walk to (3,8) and (2,9))."""

    def test_a_unit_with_redas_reports_its_destination_not_its_spawn(self):
        units = df.vanilla_red_units('FE8 Ch1')
        knight = next(u for u in units if u['classIndex'] == 'CLASS_ARMOR_KNIGHT')
        self.assertEqual((2, 9), (knight['xPosition'], knight['yPosition']))
        self.assertEqual((2, 5), knight['position'])

    def test_a_unit_with_no_redas_falls_back_to_its_placed_tile(self):
        # ch03's force is placed statically -- no REDA, so position IS xPosition/yPosition.
        for unit in df.vanilla_red_units('FE8 Ch3'):
            self.assertEqual((unit['xPosition'], unit['yPosition']), unit['position'])

    def test_destinations_separate_units_identical_in_every_other_field(self):
        # The pair that made me reach for `nth`: same class, level and spawn tile, different
        # AI. Their destinations differ, so no ordinal is needed.
        pair = [u for u in df.vanilla_red_units('FE8 Ch1')
                if u['classIndex'] == 'CLASS_FIGHTER' and u['level'] == 2
                and (u['xPosition'], u['yPosition']) == (2, 9)]
        self.assertEqual(2, len(pair))
        self.assertEqual({(3, 8), (2, 9)}, {u['position'] for u in pair})
        self.assertNotEqual(pair[0]['ai'], pair[1]['ai'])

    def test_a_donor_at_matches_the_destination(self):
        self.assertEqual(df.resolve_donor('FE8 Ch1', [3, 8])['ai'], (0x00, 0x00, 0x01, 0x00))
        self.assertEqual(df.resolve_donor('FE8 Ch1', [2, 9])['ai'], (0x00, 0x12, 0x01, 0x00))

    def test_every_ch05_unit_of_ours_stands_on_a_vanilla_destination(self):
        # 23/23 -- the ch05 pairing is DERIVED, not assigned by hand. Matched on spawn tiles
        # it was 9/23, and the nine were coincidences.
        posts = {u['position'] for u in df.vanilla_red_units('FE8 Ch5')}
        with open(df.chapter_path('rime-of-the-frostmaiden', 'ch05'),
                  encoding='utf-8') as source:
            chap = bc.yaml.safe_load(source)
        ours = [tuple(p) for key in df.AI_ROSTER_KEYS
                for e in (chap.get(key) or []) if isinstance(e, dict)
                for p in (e.get('positions') or [])]
        self.assertEqual([], [p for p in ours if p not in posts])


class GreenDonors(unittest.TestCase):
    """A donor may name a unit of any allegiance, defaulting to RED.

    Our protected greens have vanilla counterparts too -- ch02's chwinga stand in for Ross
    and Garcia -- and their AI is as much a design decision as an enemy's. Garcia runs
    {AttackInRangeAI, 0, 0}: strike anything that reaches him, never leave his tile. Reading
    only the red force would leave the units the chapter is ABOUT ungrounded."""

    def test_a_green_donor_resolves(self):
        garcia = df.resolve_donor('FE8 Ch2', {'at': [10, 4], 'allegiance': 'GREEN'})
        self.assertEqual(garcia['charIndex'], 'CHARACTER_GARCIA')
        self.assertEqual(garcia['ai'], (0x00, 0x03, 0x00, 0x00))

    def test_red_is_still_the_default(self):
        # (10,4) holds Garcia (green) and nothing red, so an unqualified spec must miss.
        with self.assertRaises(ValueError):
            df.resolve_donor('FE8 Ch2', [10, 4])

    def test_the_two_greens_are_distinguishable_by_post(self):
        ross = df.resolve_donor('FE8 Ch2', {'at': [10, 5], 'allegiance': 'GREEN'})
        self.assertEqual(ross['charIndex'], 'CHARACTER_ROSS')
        self.assertNotEqual(ross['ai'], (0x00, 0x03, 0x00, 0x00))


class ChapterEnemyForce(unittest.TestCase):
    def test_expands_count_and_composition_into_per_unit_force(self):
        chap = {'enemy_units': [
            {'id': 'g', 'class': 'fighter', 'level': 1, 'count': 3,
             'inventory': [{'id': 'iron-axe'}]},
            {'id': 'r', 'composition': ['fighter', 'fighter', 'soldier'], 'level': 1,
             'count': 3, 'inventory_by_class': {'fighter': ['iron-axe'],
                                                'soldier': ['iron-lance']}},
            {'id': 'boss', 'class': 'armor-knight', 'level': 4, 'is_boss': True,
             'count': 1, 'inventory': [{'id': 'iron-lance'}]},
        ]}
        force = df.chapter_enemy_force(chap)
        self.assertEqual(len(force), 7)            # 3 + 3 + 1, bosses included
        names = [u.weapon.name for u in force]
        self.assertEqual(names.count('iron-axe'), 5)    # 3 fighters + 2 fighters
        self.assertEqual(names.count('iron-lance'), 2)  # 1 soldier + the boss

    def test_unmodeled_enemies_reports_dropped_entries_with_boss_flag(self):
        # The metric drops enemies whose weapon isn't modeled; this surfaces them (esp.
        # bosses) so a skewed verdict is loud, not silent (#51).
        chap = {'enemy_units': [
            {'id': 'sephek', 'class': 'myrmidon', 'level': 5, 'is_boss': True,
             'inventory': [{'id': 'ice-longsword'}]},      # flavor name, no fe_base
            {'id': 'guard', 'class': 'fighter', 'level': 2,
             'inventory': [{'id': 'iron-axe'}]},           # resolves -> not reported
        ]}
        dropped = df.unmodeled_enemies(chap)
        self.assertEqual(dropped, [{'id': 'sephek', 'is_boss': True}])

    def test_unmodeled_enemies_empty_when_all_resolve(self):
        chap = {'enemy_units': [
            {'id': 'guard', 'class': 'fighter', 'level': 2,
             'inventory': [{'id': 'iron-axe'}]}]}
        self.assertEqual(df.unmodeled_enemies(chap), [])

    def test_drops_enemies_with_no_modeled_weapon(self):
        # A healer / unmodeled-weapon enemy carries no threat in this proxy -> excluded
        # (mirrors the vanilla side, which also drops staff/throwaway-only units).
        chap = {'enemy_units': [
            {'id': 'cleric', 'class': 'priest', 'level': 1, 'count': 2,
             'inventory': [{'id': 'heal'}]},          # staff -> not in fc.W
            {'id': 'g', 'class': 'fighter', 'level': 1, 'count': 1,
             'inventory': [{'id': 'iron-axe'}]},
        ]}
        force = df.chapter_enemy_force(chap)
        self.assertEqual([u.weapon.name for u in force], ['iron-axe'])


class WeaponUnlockGating(unittest.TestCase):
    """_weapon_for ignores inventory items whose `unlock` precondition isn't met for the
    modeled (base-class) state (#62). A base Priest's promotion-gated Light tomes don't leak
    into base-class offense; a staff-only loadout resolves to None (the support path)."""

    def test_skips_unlock_gated_weapon(self):
        # The only attacking item is promotion-gated -> no base-class weapon.
        inv = [{'id': 'frostsong', 'fe_base': 'lightning', 'unlock': 'promotion'}]
        self.assertIsNone(df._weapon_for(inv))

    def test_staff_only_loadout_is_support(self):
        # Heal staff (not in fc.W) + a promotion-gated tome -> weaponless support, not the tome.
        inv = [{'id': 'heal-staff', 'fe_base': 'heal'},
               {'id': 'frostsong', 'fe_base': 'lightning', 'unlock': 'promotion'}]
        self.assertIsNone(df._weapon_for(inv))

    def test_ungated_weapon_still_resolves(self):
        # A non-gated weapon ahead of (or behind) a gated one is still picked.
        inv = [{'id': 'iron-sword'},
               {'id': 'frostsong', 'fe_base': 'lightning', 'unlock': 'promotion'}]
        self.assertEqual(df._weapon_for(inv).name, 'iron-sword')


_UDEF_SNIPPET = """
CONST_DATA struct UnitDefinition UnitDef_Test[] = {
    {
        .charIndex = CHARACTER_BREGUET,
        .classIndex = CLASS_ARMOR_KNIGHT,
        .allegiance = FACTION_ID_RED,
        .ai = {GuardTileAI, 0x9, 0x20},
        .xPosition = 11,
        .yPosition = 3,
        .level = 4,
        .items = {
            ITEM_LANCE_IRON,
        },
    },
    {
        .charIndex = 0x80,
        .classIndex = CLASS_SOLDIER,
        .autolevel = 1,
        .allegiance = FACTION_ID_RED,
        .level = 2,
        .items = {
            ITEM_LANCE_IRON,
            ITEM_VULNERARY,
        },
    },
    {
        .charIndex = CHARACTER_EIRIKA,
        .classIndex = CLASS_EIRIKA_LORD,
        .allegiance = FACTION_ID_BLUE,
        .level = 1,
        .items = {
            ITEM_SWORD_RAPIER,
        },
    },
    { 0 },
};
"""


_UDEF_DROP_SNIPPET = """
CONST_DATA struct UnitDefinition UnitDef_Drop[] = {
    {
        .charIndex = 0x8e,
        .classIndex = CLASS_BRIGAND,
        .allegiance = FACTION_ID_RED,
        .level = 3,
        .itemDrop = 1,
        .items = {
            ITEM_AXE_IRON,
            ITEM_VULNERARY,
        },
    },
    {
        .charIndex = 0x8f,
        .classIndex = CLASS_FIGHTER,
        .allegiance = FACTION_ID_RED,
        .level = 2,
        .items = {
            ITEM_AXE_IRON,
        },
    },
    { 0 },
};
"""


class VanillaUnitDefParser(unittest.TestCase):
    def test_parses_each_entry_class_level_allegiance_items(self):
        defs = df.vanilla_unit_defs(_UDEF_SNIPPET, 'UnitDef_Test')
        self.assertEqual(len(defs), 3)           # the { 0 } terminator is skipped
        self.assertEqual(defs[0], {'charIndex': 'CHARACTER_BREGUET',
                                   'ai': (0x03, 0x03, 0x09, 0x20),
                                   'redas': None, 'position': (11, 3),
                                   'xPosition': 11, 'yPosition': 3,
                                   'classIndex': 'CLASS_ARMOR_KNIGHT', 'level': 4,
                                   'allegiance': 'FACTION_ID_RED', 'itemDrop': False,
                                   'items': ['ITEM_LANCE_IRON']})
        self.assertEqual(defs[1]['classIndex'], 'CLASS_SOLDIER')
        self.assertEqual(defs[1]['items'], ['ITEM_LANCE_IRON', 'ITEM_VULNERARY'])
        self.assertEqual(defs[2]['allegiance'], 'FACTION_ID_BLUE')

    def test_captures_named_character_index(self):
        # Named units (allies, bosses) carry a .charIndex; a generic's numeric one is kept too.
        defs = df.vanilla_unit_defs(_UDEF_SNIPPET, 'UnitDef_Test')
        self.assertEqual(defs[0]['charIndex'], 'CHARACTER_BREGUET')
        self.assertEqual(defs[2]['charIndex'], 'CHARACTER_EIRIKA')

    def test_captures_the_ai_vector_and_defaults_it_to_all_zeros(self):
        # #335. A nested .ai must not split the entry (that is what _brace_entries guards),
        # and an entry WITHOUT one is {0,0,0,0} -- a pursuer, not an inert default.
        defs = df.vanilla_unit_defs(_UDEF_SNIPPET, 'UnitDef_Test')
        self.assertEqual(defs[0]['ai'], (0x03, 0x03, 0x09, 0x20))
        self.assertEqual(defs[1]['ai'], (0x00, 0x00, 0x00, 0x00))

    def test_captures_item_drop_bit(self):
        # #176: a unit flagged .itemDrop = 1 drops its LAST item (US_DROP_ITEM, the final
        # inventory slot -- statscreen.c:726). Units without the flag read itemDrop False.
        defs = df.vanilla_unit_defs(_UDEF_DROP_SNIPPET, 'UnitDef_Drop')
        self.assertTrue(defs[0]['itemDrop'])
        self.assertFalse(defs[1]['itemDrop'])


class VanillaEnemies(unittest.TestCase):
    """Integration: extract a parity reference's red enemy force from the decomp (HEAD)."""

    def test_ch1_reference_is_the_ten_escape_enemies(self):
        # Vanilla FE8 Ch1 "Escape!": 7 initial (Breguet L4 armor + 3 soldiers + 3 fighters)
        # + 3 reinforcements. All red, iron lance/axe -- the bar our ch01 mirrors 1:1.
        enemies = df.vanilla_enemies('FE8 Ch1')
        self.assertEqual(len(enemies), 10)
        # Boss is first: armor-knight projected to L4 (class base + 3 levels of growth).
        boss = enemies[0]
        self.assertEqual(boss.weapon.name, 'iron-lance')
        self.assertEqual({u.weapon.name for u in enemies}, {'iron-lance', 'iron-axe'})

    def test_prologue_reference_is_the_three_fighters(self):
        enemies = df.vanilla_enemies('FE8 Prologue')
        self.assertEqual(len(enemies), 3)        # only the fightable PrologueEnemy array
        self.assertEqual({u.weapon.name for u in enemies}, {'iron-axe'})

    def test_unmapped_reference_returns_none(self):
        self.assertIsNone(df.vanilla_enemies('FE8 Ch99'))

    def test_ch2_reference_is_nine_armed_enemies_incl_steel_axe(self):
        # Curated from events_udefs.c (arrays ch2-eventscript references, armed RED only);
        # all 9 resolve (needs steel-axe). Cutscene/skirmish arrays excluded by design.
        enemies = df.vanilla_enemies('FE8 Ch2')
        self.assertEqual(len(enemies), 9)
        self.assertIn('steel-axe', {u.weapon.name for u in enemies})

    def test_ch3_reference_is_ten_armed_enemies(self):
        # The Riev/Caellach/Valter cutscene array (empty items) is NOT this chapter's force.
        enemies = df.vanilla_enemies('FE8 Ch3')
        self.assertEqual(len(enemies), 10)

    def test_ch5_reference_is_twentythree_armed_incl_killing_edge(self):
        enemies = df.vanilla_enemies('FE8 Ch5')
        self.assertEqual(len(enemies), 23)
        self.assertIn('killing-edge', {u.weapon.name for u in enemies})

    def test_ch4_reference_is_all_monster_force_fully_modeled(self):
        # FE8 Ch4 "Ancient Horrors": all-monster map; needs the monster claws + Evil Eye (#53).
        # All 23 armed RED units resolve -- zero unmodeled-weapon drops.
        enemies = df.vanilla_enemies('FE8 Ch4')
        self.assertEqual(len(enemies), 23)
        names = {u.weapon.name for u in enemies}
        self.assertIn('fetid-claw', names)
        self.assertIn('evil-eye', names)

    def test_ch6_reference_resolves_all_armed_only_staff_healers_dropped(self):
        # FE8 Ch6 "Victims of War": needs thunder/halberd/venin-axe/iron-blade/horseslayer +
        # the venin-claw Bael (#53). 27 armed RED; the 2 staff-only healers carry no weapon and
        # are dropped by design, leaving 25 -- no unmodeled-weapon drop remains.
        enemies = df.vanilla_enemies('FE8 Ch6')
        self.assertEqual(len(enemies), 25)
        names = {u.weapon.name for u in enemies}
        self.assertIn('horseslayer', names)
        self.assertIn('venin-claw', names)

    def test_vanilla_only_weapons_all_have_modeled_stats(self):
        # Every difficulty-local vanilla-only item maps to a weapon present in fe_combat.W,
        # and none of them leaked into the content-owned WEAPON_ITEM_ENUM (#53 seam rule).
        for item, key in df.VANILLA_ONLY_ITEM_TO_WEAPON.items():
            self.assertIn(key, fc.W)
            self.assertNotIn(item, df.WEAPON_ITEM_ENUM.values())

    def test_ch13_reference_is_the_hamill_canyon_force(self):
        # 52 armed-RED defs across the 11 curated ch13a arrays (boss squad + main force +
        # Pablo wave + cav/merc/wyvern packs + Amelia); the 2 staff-only healers (sleep,
        # physic) drop by design, leaving 50 -- no unmodeled-weapon drop remains (#123).
        enemies = df.vanilla_enemies('FE8 Ch13')
        self.assertEqual(len(enemies), 50)
        names = {u.weapon.name for u in enemies}
        for expected in ('steel-lance', 'elfire', 'zanbato', 'short-spear',
                         'steel-bow', 'slim-lance'):
            self.assertIn(expected, names)


class VanillaProjection(unittest.TestCase):
    """Forward targets for planned chapters (#123): the vanilla reference's own pressure."""

    def test_uncurated_reference_projects_none(self):
        self.assertIsNone(df.vanilla_projection('FE8 Ch99', 8))

    def test_projection_reports_full_threat_and_finite_clearload(self):
        proj = df.vanilla_projection('FE8 Ch13', 8)
        self.assertEqual(proj['n'], 50)
        self.assertGreater(proj['threat'], 0)
        # promoted walls the early-game yardstick can't dent are EXCLUDED from
        # clear-load (else it reads inf) and surfaced in `proof` instead
        self.assertNotEqual(proj['clearload'], float('inf'))
        self.assertGreater(proj['proof'], 0)

    def test_projection_with_no_walls_matches_enemy_pressure(self):
        # An early reference (all dentable) must project exactly what the parity row
        # computes -- the projection is the same bar, shown before our side exists.
        proj = df.vanilla_projection('FE8 Ch1', 9)
        self.assertEqual(proj['proof'], 0)
        t, l = df.enemy_pressure(df.vanilla_enemies('FE8 Ch1'), 9)
        self.assertAlmostEqual(proj['threat'], t)
        self.assertAlmostEqual(proj['clearload'], l)


class ReportSmoke(unittest.TestCase):
    """The full report() path end-to-end on real chapter data -- the only caller of the
    parity-delta formatting, so it guards the wiring (#61/#62) the metric unit tests can't
    (e.g. a healer in the field, a derived vanilla delta, inf-safe delta formatting)."""

    def _run(self, ch):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            df.report('rime-of-the-frostmaiden', ch)
        return buf.getvalue()

    def test_ch01_report_prints_a_derived_vanilla_delta(self):
        out = self._run('ch01')
        self.assertIn('VANILLA Ch1 PARITY DELTA', out)
        self.assertNotIn('delta skipped', out)

    def test_ch02_report_with_a_fielded_healer_does_not_crash(self):
        # ch02's roster includes the staff-only Sclorbo and the derived vanilla field
        # includes Moulder -- the healer-modeling repro from #62. Must print a delta.
        out = self._run('ch02')
        self.assertIn('VANILLA Ch2 PARITY DELTA', out)
        self.assertIn('(staff)', out)          # Sclorbo rendered as weaponless support


class VanillaAllies(unittest.TestCase):
    """Integration: derive a parity reference's vanilla PLAYER deploy field from the decomp
    (HEAD), keyed off the chapter's parity_reference -- the player-side yardstick (#61). Named
    units resolve to class base + their personal line (mirroring our cast); a staff-only ally
    (Moulder) resolves to weaponless support (mirroring our Sclorbo, #62)."""

    def test_unmapped_reference_returns_none(self):
        self.assertIsNone(df.vanilla_allies('FE8 Ch99'))

    def test_ch1_reference_is_the_four_deploy_units(self):
        # FE8 Ch1 deploy: Eirika + Seth (Ally) + Franz + Gilliam (AllyReinforce), all blue.
        allies = df.vanilla_allies('FE8 Ch1')
        self.assertEqual({u.name for u in allies},
                         {'Eirika', 'Seth', 'Franz', 'Gilliam'})
        eirika = next(u for u in allies if u.name == 'Eirika')
        self.assertEqual(eirika.weapon.name, 'rapier')
        gilliam = next(u for u in allies if u.name == 'Gilliam')
        # Stored personal line + Armor Knight base (from HEAD); not autoleveled.
        self.assertEqual((gilliam.hp, gilliam.pow, gilliam.skl, gilliam.spd,
                          gilliam.df, gilliam.res, gilliam.lck, gilliam.con),
                         (25, 9, 6, 3, 9, 3, 3, 14))

    def test_ch2_reference_fields_moulder_as_staff_only_support(self):
        # FE8 Ch2 deploy adds Moulder (base Priest, heal staff only) -> weaponless support,
        # exactly the healer-modeling #62 handles; the run must not crash.
        allies = df.vanilla_allies('FE8 Ch2')
        self.assertEqual({u.name for u in allies},
                         {'Eirika', 'Seth', 'Franz', 'Gilliam', 'Moulder'})
        moulder = next(u for u in allies if u.name == 'Moulder')
        self.assertIsNone(moulder.weapon)


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

    def test_sclorbo_is_a_support_unit_at_base(self):
        # Base Priest = staff-only; his Light tomes are unlock: promotion (sclorbo.yaml). The
        # heal staff isn't a modeled weapon, so he resolves to weaponless support -> 0
        # throughput (not the inflated 0.84 from crediting a tome he can't wield at base) (#62).
        u = df.player_combatant(CAMPAIGN, 'sclorbo')
        self.assertIsNone(u.weapon)
        goblin = combatant('g', hp=20, dfc=2, weapon='iron-axe')
        self.assertEqual(fc.kills_per_round(u, goblin), 0.0)


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


class ItemEconomy(unittest.TestCase):
    """Vanilla twin economy is extracted from HEAD (#170) -- never the working tree, which the
    build injects our own chapters into. These lock the HEAD-verified numbers so the class of
    bug that had our ch03 chests reported as vanilla Ch4's can't recur silently."""

    def test_item_gold_value_from_head(self):
        self.assertEqual(df.item_gold_value('ITEM_AXE_IRON'), 270)
        self.assertEqual(df.item_gold_value('ITEM_GUIDINGRING'), 10000)
        self.assertEqual(df.item_gold_value('ITEM_BOOSTER_DEF'), 8000)
        self.assertEqual(df.item_gold_value('ITEM_TORCH'), 500)
        self.assertEqual(df.item_gold_value('ITEM_REDGEM'), 5000)
        self.assertEqual(df.item_gold_value('ITEM_NOT_A_REAL_ITEM'), 0)

    def test_ch4_is_lean_two_villages_no_chests(self):
        # The bug fixture: vanilla Ch4 is 2 villages / one Iron Axe (~270g) / ZERO chests.
        # (The worktree's ch4 slot may hold our injected ch03 chests -- reading HEAD ignores them.)
        e = df.vanilla_economy('FE8 Ch4')
        self.assertEqual(e['total_gold'], 270)
        self.assertEqual(e['chests'], [])
        self.assertEqual(e['gifts'], [('ITEM_AXE_IRON', 270)])
        self.assertEqual(e['shops'], [])
        self.assertEqual(e['n_villages'], 2)

    def test_ch5_gifts_include_the_clear_reward_and_two_shops(self):
        # ~27,760g: the Guiding Ring is a clear reward handed to the leader OUTSIDE any Village
        # macro -- the gift scan must still catch it (else we under-count by the biggest item).
        e = df.vanilla_economy('FE8 Ch5')
        self.assertEqual(e['total_gold'], 27760)
        self.assertEqual(e['chests'], [])
        gift_items = dict(e['gifts'])
        self.assertEqual(gift_items['ITEM_GUIDINGRING'], 10000)
        self.assertEqual(gift_items['ITEM_BOOSTER_DEF'], 8000)
        self.assertEqual(gift_items['ITEM_BOOSTER_SKL'], 8000)
        self.assertEqual(gift_items['ITEM_SWORD_ARMORSLAYER'], 1260)
        self.assertEqual(len(e['shops']), 2)          # Armory + Vendor
        self.assertEqual(e['n_villages'], 4)

    def test_ch3_chests_are_read_from_head(self):
        # Vanilla Ch3 (Borgo) is a 4-chest chapter -- proves chest extraction, distinct from the
        # gift/village path, and that the reader isn't confusing vehicles.
        e = df.vanilla_economy('FE8 Ch3')
        chest_items = [i for i, _ in e['chests']]
        self.assertEqual(len(e['chests']), 4)
        self.assertIn('ITEM_LANCE_JAVELIN', chest_items)
        self.assertEqual(e['gifts'], [])

    def test_unmapped_reference_returns_none(self):
        self.assertIsNone(df.vanilla_economy('FE8 Ch99'))

    def test_vanilla_drops_reads_the_last_item_of_each_flagged_red_unit(self):
        # #176: vanilla Ch2's brigand carries { Iron Axe, Vulnerary } with .itemDrop set,
        # so it drops the Vulnerary (the last slot), valued in buy-gold (300g).
        drops = df.vanilla_drops('FE8 Ch2')
        self.assertEqual(drops, [('ITEM_VULNERARY', 300)])

    def test_vanilla_drops_uncurated_reference_is_none(self):
        self.assertIsNone(df.vanilla_drops('FE8 Ch99'))

    def test_ch2_economy_counts_the_vulnerary_drop_in_total(self):
        # The drop channel #170 v1 skipped: it must show under `drops` AND lift total_gold.
        e = df.vanilla_economy('FE8 Ch2')
        self.assertEqual(e['drops'], [('ITEM_VULNERARY', 300)])
        self.assertIn(300, [v for _, v in e['drops']])
        self.assertGreaterEqual(e['total_gold'], 300)   # drops fold into the payout magnitude

    def test_ch3_economy_reports_its_key_drops(self):
        # Vanilla Ch3's two brigands drop a Door Key (50g) and a Chest Key (300g).
        drops = dict(df.vanilla_economy('FE8 Ch3')['drops'])
        self.assertEqual(drops.get('ITEM_DOORKEY'), 50)
        self.assertEqual(drops.get('ITEM_CHESTKEY'), 300)

    def test_ch4_ch5_twins_have_no_drops(self):
        # The lock twins carry zero enemy drops -- the v1 gap didn't affect the ch04/ch05 lock.
        self.assertEqual(df.vanilla_economy('FE8 Ch4')['drops'], [])
        self.assertEqual(df.vanilla_economy('FE8 Ch5')['drops'], [])

    def test_chapter_economy_reads_our_declared_yaml(self):
        chap = {
            'villages': [{'visit_reward': [{'id': 'gold', 'amount': 150},
                                           {'id': 'vulnerary'}]}],
            'chests': [{'contents': [{'id': 'red-gem'}]}],
            'enemy_units': [{'id': 'k', 'item_drop': 'chest-key'}],
            'post_chapter': {'gold_reward': 200, 'available_shops': ['termalaine']},
        }
        ours = df.chapter_economy(chap)
        self.assertEqual(ours['gold'], 350)               # 150 village + 200 post
        self.assertEqual(ours['gifts'], ['vulnerary'])
        self.assertEqual(ours['chests'], ['red-gem'])
        self.assertEqual(ours['drops'], ['chest-key'])
        self.assertEqual(ours['shops'], ['termalaine'])

    def test_chapter_economy_counts_non_village_delivery_vehicles(self):
        """A gift is a gift whatever carries it (#26).

        ch06 hands out vanilla Ch6's own two rewards -- the Antitoxin its village gives and the
        Orion's Bolt its ending gates on CHECK_ALIVE -- but through vehicles this chapter
        invented: a Talk on a rescue boat, and a save-them-all clear bonus. The reader only knew
        villages, chests, drops and post_chapter gold, so it scored ch06 at 400g against the
        twin's ~15,240g and made a faithful chapter look impoverished. The build already emits
        both (ch05 ships save_all_bonus), so this was the REPORT lying, not the chapter."""
        chap = {
            'rescue_boats': [
                {'id': 'boat-east', 'talk': {'reward': [{'id': 'antitoxin', 'amount': 1},
                                                        {'id': 'gold', 'amount': 500}]}},
                {'id': 'boat-west', 'talk': {'reward': []}},
            ],
            'economy': {'save_all_bonus': 'orions-bolt'},
        }
        ours = df.chapter_economy(chap)
        self.assertEqual(ours['gold'], 500)
        self.assertEqual(ours['gifts'], ['antitoxin', 'orions-bolt'])

    def test_chapter_economy_survives_a_chapter_with_no_boats(self):
        self.assertEqual(df.chapter_economy({})['gifts'], [])


class BattlefieldDynamics(unittest.TestCase):
    """Recruit-flips + reinforcement timing (#171), auto-detected from HEAD for the twin and
    read from our YAML. The static bar counts every enemy as a turn-1 kill; these model the two
    vanilla set-pieces (convertible enemies, timed reinforcements) it can't see."""

    # -- vanilla auto-detection --
    def test_vanilla_convertible_from_char_macro(self):
        self.assertEqual(df._vanilla_convertible_chars('ch5'), {'CHARACTER_JOSHUA'})
        self.assertEqual(df._vanilla_convertible_chars('ch4'), set())

    def test_vanilla_reinforcement_turns_from_turn_events(self):
        turns = df._vanilla_reinforcement_turns('ch5')     # bandit waves on 2 / 6 / 8
        self.assertEqual(sorted(turns.values()), [2, 6, 8])

    def test_ch5_groups_split_joshua_and_the_waves(self):
        g = df.vanilla_enemy_groups('FE8 Ch5')
        self.assertEqual(len(g['convertibles']), 1)        # Joshua
        self.assertEqual(len(g['reinforcements']), 6)      # the turn 2/6/8 arrays
        self.assertEqual(sum(len(g[k]) for k in g), 23)    # still the full 23-unit force

    def test_ch4_detects_area_and_timed_reinforcements(self):
        # #177: Ch4 "Ancient Horrors" spawns via non-TurnEventPlayer triggers the v1 missed --
        # a turn-2 Bonewalker wave (raw TURN(..., FACTION_BLUE)) and a zone-entry Revenant wave
        # (a temp-flag-gated TURN set by an AREA trigger). Both must read as arriving after turn 1.
        turns = df._vanilla_reinforcement_turns('ch4')
        self.assertEqual(set(turns), {'UnitDef_088B4C88', 'UnitDef_088B4C24'})
        self.assertEqual(turns['UnitDef_088B4C88'], 2)     # the timed Bonewalker wave
        self.assertTrue(all(t > 1 for t in turns.values()))

    def test_ch4_groups_split_the_seven_reinforcements(self):
        # 16 turn-1 line + (3 Bonewalkers + 4 Revenants) reinforcements = the full 23-monster force.
        g = df.vanilla_enemy_groups('FE8 Ch4')
        self.assertEqual(len(g['line']), 16)
        self.assertEqual(len(g['reinforcements']), 7)
        self.assertEqual(len(g['convertibles']), 0)
        self.assertEqual(sum(len(g[k]) for k in g), 23)

    def test_dynamic_threat_below_static_for_a_reinforced_chapter(self):
        g = df.vanilla_enemy_groups('FE8 Ch5')
        allf = g['line'] + g['reinforcements'] + g['convertibles']
        self.assertLess(df.dynamic_pressure(g, 10)[0], df.enemy_pressure(allf, 10)[0])

    # -- pure metric, hand oracle --
    def test_reinforcements_excluded_from_turn1_threat_kept_in_clearload(self):
        line = [combatant('l', pow_=5)]
        reinf = [combatant('r', pow_=5)]
        g = {'line': line, 'reinforcements': reinf, 'convertibles': []}
        dt, dc = df.dynamic_pressure(g, 1)
        self.assertAlmostEqual(dt, df.enemy_pressure(line, 1)[0])          # reinf not turn-1
        self.assertAlmostEqual(dc, df.enemy_pressure(line + reinf, 1)[1])  # but still cleared

    def test_convertible_is_present_threat_but_discounted_clearload(self):
        line = [combatant('l', pow_=5)]
        conv = [combatant('c', pow_=5)]
        g = {'line': line, 'reinforcements': [], 'convertibles': conv}
        dt, dc = df.dynamic_pressure(g, 1)
        self.assertAlmostEqual(dt, df.enemy_pressure(line + conv, 1)[0])   # on the field turn 1
        exp = (df.enemy_pressure(line, 1)[1]
               + df.CONVERT_CLEAR_DISCOUNT * df.enemy_pressure(conv, 1)[1])
        self.assertAlmostEqual(dc, exp)                                    # recruit, don't grind

    def test_recruit_swing_positive_when_the_convertible_can_fight(self):
        g = {'line': [combatant('l', hp=10, dfc=0)], 'reinforcements': [],
             'convertibles': [combatant('c', pow_=20, spd=20, weapon='iron-sword')]}
        self.assertGreater(df.recruit_swing(g), 0)

    # -- our-side YAML flags --
    def test_chapter_groups_read_convertible_and_arrives_turn(self):
        chap = {'enemy_units': [
            {'id': 'a', 'class': 'fighter', 'level': 1, 'count': 2,
             'inventory': [{'id': 'iron-axe'}]},
            {'id': 'r', 'class': 'soldier', 'level': 1, 'count': 3,
             'inventory': [{'id': 'iron-lance'}], 'arrives_turn': 4},
            {'id': 'c', 'class': 'myrmidon', 'level': 1, 'count': 1,
             'inventory': [{'id': 'iron-sword'}], 'convertible': {'by': 'basil'}},
        ]}
        g = df.chapter_enemy_groups(chap)
        self.assertEqual((len(g['line']), len(g['reinforcements']), len(g['convertibles'])),
                         (2, 3, 1))


class RoleCheck(unittest.TestCase):
    """The per-unit role check (#25 post-mortem): the aggregate parity verdict hides a
    single monstrous unit and a boss that folds, because threat/slot averages both away."""

    REF = 'FE8 Ch5'

    def _chap(self, units):
        return {'enemy_units': units}

    def test_clean_roster_has_no_findings(self):
        """A Saar-shaped boss (armour wall, modest threat) over ordinary line units --
        the profile the vanilla twin actually fields."""
        chap = self._chap([
            {'id': 'grunt', 'class': 'soldier', 'level': 5, 'count': 6,
             'inventory': [{'id': 'iron-lance', 'fe_base': 'iron-lance'}]},
            {'id': 'boss', 'class': 'armor-knight', 'level': 8, 'is_boss': True,
             'inventory': [{'id': 'slim-lance', 'fe_base': 'slim-lance'}]},
        ])
        self.assertEqual(df.role_findings(chap, self.REF), [])

    def test_flags_a_boss_out_threatened_by_a_line_unit(self):
        chap = self._chap([
            {'id': 'monster', 'class': 'gwyllgi', 'level': 6,
             'inventory': [{'id': 'claw', 'fe_base': 'rotten-claw'}]},
            {'id': 'boss', 'class': 'druid', 'level': 7, 'is_boss': True,
             'inventory': [{'id': 'flux', 'fe_base': 'flux'}]},
        ])
        found = df.role_findings(chap, self.REF)
        self.assertTrue(any('out-threatened' in f and 'monster' in f for f in found), found)

    def test_convertible_outlier_is_not_a_role_inversion(self):
        """A convertible is neutralized rather than ground down, so out-hitting the boss
        is a deliberate 'avoid me' hazard -- the ch05 white moose.

        The outlier here must clear the twin's REAL ceiling (Joshua, 21.4 -> bar 26.7) rather
        than its class-base one (6.3 -> bar 7.9). The old fixture (rotten-claw, 14.1) no longer
        reads as an outlier at all, which is exactly the point of the ceiling fix: a unit that
        merely out-hits the twin's GENERICS is not an outlier when the twin fields a 21.4
        recruit of its own."""
        chap = self._chap([
            {'id': 'moose', 'class': 'gwyllgi', 'level': 12, 'convertible': True,
             'inventory': [{'id': 'claw', 'fe_base': 'hell-fang'}]},
            {'id': 'boss', 'class': 'druid', 'level': 7, 'is_boss': True,
             'inventory': [{'id': 'flux', 'fe_base': 'flux'}]},
        ])
        found = df.role_findings(chap, self.REF)
        self.assertFalse(any('out-threatened' in f for f in found), found)
        self.assertTrue(any('moose' in f and 'convertible' in f for f in found), found)

    def test_threat_checks_use_the_real_article_on_both_sides(self):
        """A boss's PERSONAL line is most of what makes it a boss, so the role check has to
        read it -- the same 'real article' the durability check in this function already uses.

        Measured class-base, ch05's Ravisin reads 8.4 against the moose's 11.8 and the check
        cried role inversion; with her personal line she is 12.5 and out-threatens it. FE8
        builds named units this way on BOTH sides: vanilla Ch5's Saar and Joshua are both 6.2
        class-base and 12.2 / 21.4 once applied, indistinguishable from a generic until then.
        """
        chap = self._chap([
            {'id': 'beast', 'class': 'gwyllgi', 'level': 6,
             'inventory': [{'id': 'fang', 'fe_base': 'fire-fang'}]},
            {'id': 'boss', 'class': 'druid', 'level': 7, 'is_boss': True,
             'personal': {'baseHP': 15, 'basePow': 4, 'baseSkl': 3,
                          'baseDef': 5, 'baseRes': 3, 'baseLck': 3},
             'inventory': [{'id': 'flux', 'fe_base': 'flux'}]},
        ])
        found = df.role_findings(chap, self.REF)
        self.assertFalse(any('out-threatened' in f for f in found),
                         'the boss out-threatens the beast once her personal line is read: %s'
                         % found)

    def test_a_real_inversion_still_fires_through_the_personal_line(self):
        """The guard on the fix: applying personal lines must not silence a TRUE inversion."""
        chap = self._chap([
            {'id': 'monster', 'class': 'gwyllgi', 'level': 6,
             'inventory': [{'id': 'claw', 'fe_base': 'hell-fang'}]},
            {'id': 'boss', 'class': 'druid', 'level': 7, 'is_boss': True,
             'personal': {'baseHP': 15, 'basePow': 4, 'baseSkl': 3,
                          'baseDef': 5, 'baseRes': 3, 'baseLck': 3},
             'inventory': [{'id': 'flux', 'fe_base': 'flux'}]},
        ])
        found = df.role_findings(chap, self.REF)
        self.assertTrue(any('out-threatened' in f and 'monster' in f for f in found), found)

    def test_the_twins_ceiling_counts_its_own_named_units(self):
        """The outlier bar was the max CLASS-BASE threat (FE8 Ch5: 6.3), which excludes the
        twin's own named units -- so every named unit we field looked like an outlier against
        a roster of generics. Vanilla Ch5's real ceiling is Joshua at 21.4."""
        self.assertAlmostEqual(df.vanilla_threat_ceiling('FE8 Ch5'), 21.4, delta=0.2)

    def test_a_cast_members_donor_line_counts_too(self):
        """The second half: a unit's personal line has TWO sources. A chapter enemy carries
        `personal:` in the YAML (Ravisin); a CAST member deployed hostile carries it via
        BASE_DONOR (Sahnar rides Joshua's). Reading only the first made ch05's red Myrmidon
        measure 6.2 against the 21.4 she actually fights at."""
        chap = self._chap([
            {'id': 'sahnar', 'class': 'myrmidon', 'level': 5,
             'inventory': [{'id': 'ke', 'fe_base': 'killing-edge'}]},
        ])
        c = df.unit_real_article(chap['enemy_units'][0],
                                df.enemy_combatants(chap['enemy_units'][0])[0])
        self.assertAlmostEqual(fc.damage_per_round(c, df.YARDSTICK), 21.4, delta=0.2)

    def test_names_a_single_unit_that_is_the_whole_overage(self):
        """ch05 measured "PARITY (within band)" at x1.20 while the white moose ALONE was the
        entire overage -- x0.97 without it. threat/slot sums the force and divides by the deploy
        cap, so one unit's 24.6 becomes +2.7 a slot and vanishes under a +-25% band. This prints
        the sentence that had to be computed by hand to catch it."""
        # sized to clear the x1.0 floor, as the real ch05 force does -- the note is about a
        # chapter that PASSES while one unit carries the excess. (#285 raised the vanilla side
        # by giving its named units their real lines, so the grunt count rose with it.)
        chap = self._chap([
            {'id': 'grunt', 'class': 'soldier', 'level': 5, 'count': 20,
             'inventory': [{'id': 'iron-lance', 'fe_base': 'iron-lance'}]},
            {'id': 'monster', 'class': 'gwyllgi', 'level': 6,
             'inventory': [{'id': 'claw', 'fe_base': 'hell-fang'}]},
        ])
        notes = df.solo_contributors(chap, self.REF, 9)
        self.assertEqual(len(notes), 1, notes)
        self.assertIn('monster alone is', notes[0])

    def test_a_big_number_from_a_big_GROUP_is_not_a_solo_contributor(self):
        """A line of eight reavers summing high is a composition choice, not one monster --
        only `count: 1` units qualify."""
        chap = self._chap([
            {'id': 'horde', 'class': 'gwyllgi', 'level': 6, 'count': 12,
             'inventory': [{'id': 'claw', 'fe_base': 'hell-fang'}]},
        ])
        self.assertEqual(df.solo_contributors(chap, self.REF, 9), [])

    def test_a_chapter_at_or_under_parity_says_nothing(self):
        chap = self._chap([
            {'id': 'grunt', 'class': 'soldier', 'level': 1, 'count': 2,
             'inventory': [{'id': 'iron-lance', 'fe_base': 'iron-lance'}]},
        ])
        self.assertEqual(df.solo_contributors(chap, self.REF, 9), [])

    def test_flags_a_boss_that_folds_far_faster_than_the_twins_wall(self):
        chap = self._chap([
            {'id': 'boss', 'class': 'druid', 'level': 7, 'is_boss': True,
             'inventory': [{'id': 'flux', 'fe_base': 'flux'}]},
        ])
        self.assertTrue(any('rounds to kill' in f for f in df.role_findings(chap, self.REF)))

    def test_flags_more_than_one_boss(self):
        chap = self._chap([
            {'id': 'a', 'class': 'armor-knight', 'level': 8, 'is_boss': True,
             'inventory': [{'id': 'iron-lance', 'fe_base': 'iron-lance'}]},
            {'id': 'b', 'class': 'armor-knight', 'level': 8, 'is_boss': True,
             'inventory': [{'id': 'iron-lance', 'fe_base': 'iron-lance'}]},
        ])
        self.assertTrue(any('flagged is_boss' in f for f in df.role_findings(chap, self.REF)))

    def test_boss_on_a_throne_is_not_flagged_as_folding(self):
        """Terrain is read from the declared tile: a Druid folds in 2.9 rounds on open
        ground but survives 6.8 on a throne (+30 avo/+3 def), clearing the threshold."""
        squishy = {'id': 'boss', 'class': 'druid', 'level': 7, 'is_boss': True,
                   'inventory': [{'id': 'flux', 'fe_base': 'flux'}]}
        self.assertTrue(any('rounds to kill' in f
                            for f in df.role_findings(self._chap([squishy]), self.REF)))
        throned = dict(squishy, tile_terrain='throne')
        self.assertFalse(any('rounds to kill' in f
                             for f in df.role_findings(self._chap([throned]), self.REF)))

    def test_uncurated_reference_yields_no_findings(self):
        chap = self._chap([{'id': 'x', 'class': 'soldier', 'level': 1,
                            'inventory': [{'id': 'iron-lance', 'fe_base': 'iron-lance'}]}])
        self.assertEqual(df.role_findings(chap, 'FE8 ChNope'), [])


class PersonalBossLine(unittest.TestCase):
    """FE8's own boss mechanism: a named boss is class base PLUS a personal line (Saar is an
    Armor Knight *plus* HP+13/Def+2/...). Modeled in the role check on BOTH sides -- and
    deliberately NOT in the aggregate, where adding it shifts every curated baseline."""

    REF = 'FE8 Ch5'

    def test_reads_a_vanilla_boss_line(self):
        line = df.vanilla_personal_line('CHARACTER_SAAR')
        self.assertEqual((line['baseHP'], line['baseDef']), (13, 2))

    def test_generic_charindex_has_no_line(self):
        self.assertEqual(df.vanilla_personal_line('0x80'), {})
        self.assertEqual(df.vanilla_personal_line(None), {})

    def test_enemy_combatants_is_still_the_class_base_primitive(self):
        """enemy_combatants stays the raw class-base projection -- the real article is layered
        on by chapter_enemy_force, so the primitive has one job and callers choose the footing."""
        plain = {'id': 'b', 'class': 'druid', 'level': 7,
                 'inventory': [{'id': 'flux', 'fe_base': 'flux'}]}
        withline = dict(plain, personal={'baseHP': 15, 'baseDef': 5})
        self.assertEqual(df.enemy_combatants(plain)[0].hp,
                         df.enemy_combatants(withline)[0].hp)

    def test_the_aggregate_force_carries_personal_lines(self):
        """#285: the aggregate reads the REAL ARTICLE on our side. Measuring a boss off class
        base understated every named unit, and it understated them asymmetrically -- ours by
        `personal:`, the twin's by its own character lines."""
        chap = {'enemy_units': [{'id': 'b', 'class': 'druid', 'level': 7, 'count': 1,
                                 'personal': {'baseHP': 15, 'baseDef': 5},
                                 'inventory': [{'id': 'flux', 'fe_base': 'flux'}]}]}
        force = df.chapter_enemy_force(chap)
        self.assertEqual(force[0].hp, df.enemy_combatants(chap['enemy_units'][0])[0].hp + 15)

    def test_personal_line_lifts_the_boss_in_the_role_check(self):
        plain = {'id': 'boss', 'class': 'druid', 'level': 7, 'is_boss': True,
                 'inventory': [{'id': 'flux', 'fe_base': 'flux'}]}
        self.assertTrue(any('rounds' in f for f in df.role_findings({'enemy_units': [plain]},
                                                                   self.REF)))
        strong = dict(plain, personal={'baseHP': 15, 'baseDef': 5})
        found = df.role_findings({'enemy_units': [strong]}, self.REF)
        self.assertFalse(any('fold too fast' in f for f in found), found)

    def test_a_unit_deployed_on_a_vanilla_slot_inherits_that_slot_s_line(self):
        """The THIRD source of a personal line (#284). ch02's Halvar deploys on the BAZBA slot
        and nothing patches it, so FE8 adds Bazba's own line in the built ROM. Measuring him
        off naked class base understated the boss by 3x and opened an issue against content
        that was never wrong."""
        halvar = {'id': 'raider-captain', 'class': 'brigand', 'level': 6, 'is_boss': True,
                  'inventory': [{'id': 'steel-axe', 'fe_base': 'steel-axe'}]}
        base = df.enemy_combatants(halvar)[0]
        real = df.unit_real_article(halvar, base)
        bazba = df.vanilla_personal_line('CHARACTER_BAZBA')
        self.assertEqual(real.hp, base.hp + bazba['baseHP'])
        self.assertEqual(real.df, base.df + bazba['baseDef'])

    def test_a_unit_on_no_vanilla_slot_is_unchanged(self):
        """A raw-pid creature sits in a CharacterData GAP whose bases are all zero, so it
        really is a naked class base until a `personal:` line is authored AND injected."""
        grell = {'id': 'grell', 'class': 'mogall', 'level': 12,
                 'inventory': [{'id': 'evil-eye', 'fe_base': 'evil-eye'}]}
        base = df.enemy_combatants(grell)[0]
        self.assertEqual(df.unit_real_article(grell, base).hp, base.hp)

    def test_no_mapped_slot_is_one_the_build_zeroes(self):
        """Riding a vanilla slot only counts if the slot survives the build. inject_prologue
        zeroes its guests' personal bases, so Sephek is a naked class base despite deploying
        on O'Neill's slot -- reading him off that line inflated his threat to 2.9x the
        Prologue's ceiling and tripped the gate, which is how this was caught."""
        zeroed = {'CHARACTER_%s' % s for s in bc.PROLOGUE_ZEROED_GUEST_SLOTS}
        self.assertEqual(zeroed & set(bc.ENEMY_BASE_SLOT.values()), set())

    def test_an_authored_line_wins_over_the_slot(self):
        """`personal:` is the explicit authored article; it must not be silently added to a
        slot's line, or a unit riding a named slot would count its bases twice."""
        halvar = {'id': 'raider-captain', 'class': 'brigand', 'level': 6,
                  'personal': {'baseHP': 1},
                  'inventory': [{'id': 'steel-axe', 'fe_base': 'steel-axe'}]}
        base = df.enemy_combatants(halvar)[0]
        self.assertEqual(df.unit_real_article(halvar, base).hp, base.hp + 1)

    def test_stacking_terrain_onto_a_boss_line_is_flagged(self):
        """Personal Def and terrain stack; together they can make a boss undentable."""
        boss = {'id': 'boss', 'class': 'druid', 'level': 7, 'is_boss': True,
                'tile_terrain': 'throne', 'personal': {'baseHP': 15, 'baseDef': 5},
                'inventory': [{'id': 'flux', 'fe_base': 'flux'}]}
        found = df.role_findings({'enemy_units': [boss]}, self.REF)
        self.assertTrue(any('cannot be damaged' in f for f in found), found)


class MetricRoundsToKill(unittest.TestCase):
    """#285: `rounds_to_kill` is a CLIFF at the damage boundary -- one more point of Def takes a
    unit from 12.9 rounds to infinite, because FE8 has no chip-damage floor. Excluding those
    units was the old answer and it is not symmetric: vanilla Ch5's Saar dropped out of the
    twin's clear-load while our Ravisin -- built to Saar's own bar, 13.4 rounds against his
    12.9 -- stayed in, which alone moved ch05 from x0.84 to x1.34. The METRIC floors damage at
    1; the game does not."""

    def _wall(self, df_):
        """A wall that can be MISSED. spd/lck 0 would pin hit chance at 100%, which is the one
        case where a floor without the accuracy divisor happens to be continuous -- i.e. the
        fixture that cannot catch the bug this class exists to prevent."""
        return combatant('wall', hp=36, dfc=df_, spd=6, lck=4, con=20)

    def test_a_dentable_unit_is_untouched_by_the_floor(self):
        u = self._wall(4)
        self.assertEqual(df.metric_rounds_to_kill(u), fc.rounds_to_kill(df.YARDSTICK, u))

    def test_an_undentable_unit_is_finite_not_infinite(self):
        u = self._wall(30)
        self.assertEqual(fc.rounds_to_kill(df.YARDSTICK, u), float('inf'))
        self.assertLess(df.metric_rounds_to_kill(u), float('inf'))

    def test_the_floor_is_monotonic_across_the_damage_cliff(self):
        """The property that makes it a measurement: more Def is never LESS load. Dropping the
        accuracy divisor breaks exactly this -- real Saar read 46.8 rounds at Def 11 and 36.0
        at Def 12, a tougher unit scoring less work."""
        loads = [df.metric_rounds_to_kill(self._wall(d)) for d in range(2, 24)]
        self.assertEqual(loads, sorted(loads), loads)

    def test_the_floor_meets_the_last_dentable_value_without_stepping(self):
        """Stronger than monotonic: a unit taking exactly 1 damage per hit already scores
        hp/(hits x accuracy), so the floor is CONTINUOUS with the curve it extends."""
        one_dmg = max(d for d in range(2, 30)
                      if fc.damage(df.YARDSTICK, self._wall(d)) == 1)
        self.assertAlmostEqual(df.metric_rounds_to_kill(self._wall(one_dmg)),
                               df.metric_rounds_to_kill(self._wall(one_dmg + 1)), places=6)

    def test_a_wall_outweighs_a_merely_tough_unit(self):
        self.assertGreater(df.metric_rounds_to_kill(self._wall(20)),
                           df.metric_rounds_to_kill(self._wall(10)))


class Terrain(unittest.TestCase):
    """Terrain read from the decomp at HEAD (ROM-free): FE8's own Common (foot) tables and
    the vanilla map layouts. For a 1:1 retile the vanilla layout IS our layout."""

    def test_bonus_matches_fe8_tables(self):
        self.assertEqual(df.terrain_bonus('TERRAIN_THRONE'), (30, 3))
        self.assertEqual(df.terrain_bonus('throne'), (30, 3))       # bare name accepted
        self.assertEqual(df.terrain_bonus('TERRAIN_GATE_CASTLE'), (20, 3))
        self.assertEqual(df.terrain_bonus('forest'), (20, 1))
        self.assertEqual(df.terrain_bonus('road'), (0, 0))

    def test_unknown_terrain_is_open_ground(self):
        self.assertEqual(df.terrain_bonus('TERRAIN_NOPE'), (0, 0))
        self.assertEqual(df.terrain_bonus(None), (0, 0))

    def test_on_terrain_folds_defense_and_returns_avoid(self):
        base = combatant('x', dfc=5)
        moved, avo = df.on_terrain(base, 'throne')
        self.assertEqual((moved.df, avo), (8, 30))
        same, avo0 = df.on_terrain(base, None)
        self.assertEqual((same.df, avo0), (5, 0))

    def test_reads_vanilla_ch5_tiles(self):
        """Anchors: Ch5's Joshua stands in the arena (canon), and the boss Saar's post is
        plain ROAD -- his 12.9-round wall is all class Defense, no terrain."""
        self.assertEqual(df.vanilla_terrain_at('Ch5Map', 12, 6), 'TERRAIN_ARENA_REGULAR')
        self.assertEqual(df.vanilla_terrain_at('Ch5Map', 13, 1), 'TERRAIN_ROAD')

    def test_off_map_and_missing_layout_degrade_to_none(self):
        self.assertIsNone(df.vanilla_terrain_at('Ch5Map', 999, 999))
        self.assertIsNone(df.vanilla_terrain_at('NoSuchMap', 0, 0))


class ModeShift(unittest.TestCase):
    """The engine's per-chapter difficulty shift, modeled on the SAME footing for both
    sides of a parity read (#303).

    FE8 applies difficulty as a stat re-projection at unit-load time, NOT as a level
    edit: `UnitApplyBonusLevels` (bmunit.c) dispatches to `UnitAutolevelCore` for the
    Difficult bonus and `UnitAutolevelPenalty` for the Tutorial/Normal malus, and only
    for RED units with `pCharacterData->number >= 0x3C` (eventscr.c:2328).

    Two engine details a naive `level - malus` gets wrong, both pinned here:
      * the penalty FLOORS at the character's baseLevel -- it re-derives from base and
        only re-autolevels `if (level - malus > baseLevel)`, so it can never read below
        pure class base;
      * the Difficult bonus is a SECOND rounding applied on top of the level projection
        (`inc(level-1)` then `inc(bonus)`), not one rounding of `level-1+bonus`.
    """

    BASE = {'baseHP': 20, 'basePow': 5, 'baseSkl': 4, 'baseSpd': 4,
            'baseDef': 3, 'baseRes': 1, 'baseLck': 0, 'baseCon': 8}
    GROWTHS = {'growthHP': 70, 'growthPow': 40, 'growthSkl': 30,
               'growthSpd': 30, 'growthDef': 20, 'growthRes': 10, 'growthLck': 20}
    SHIFTS = {'tutorial': 4, 'normal': 2, 'difficult': 3}

    def test_normal_malus_projects_the_reduced_level(self):
        got = df.mode_stats(self.BASE, self.GROWTHS, 10, 'normal', self.SHIFTS)
        self.assertEqual(got, df.autolevel(self.BASE, self.GROWTHS, 8))

    def test_penalty_floors_at_class_base_instead_of_going_below_it(self):
        # level 3 with the Tutorial malus of 4 would be level -1. The engine re-derives
        # from base and skips the re-autolevel, so the unit reads as pure class base.
        got = df.mode_stats(self.BASE, self.GROWTHS, 3, 'tutorial', self.SHIFTS)
        self.assertEqual(got, self.BASE)

    def test_a_unit_at_base_level_takes_no_penalty_at_all(self):
        # `if (levelCount && level > unit->pCharacterData->baseLevel)` -- a level-1
        # generic is untouched by any malus.
        got = df.mode_stats(self.BASE, self.GROWTHS, 1, 'tutorial', self.SHIFTS)
        self.assertEqual(got, self.BASE)

    def test_difficult_bonus_rounds_separately_from_the_level_projection(self):
        # inc(level-1) then inc(bonus) -- NOT inc(level-1+bonus). growthRes=10 at
        # level 10 gives round(9*0.10)=1 and round(3*0.10)=0 -> 1, where the single
        # rounding of 12*0.10 would give 1 as well; growthSkl=30 separates them:
        # round(9*.30)=3 + round(3*.30)=1 -> 4, vs round(12*.30)=4. Use Def (20%):
        # round(9*.20)=2 + round(3*.20)=1 -> 3, vs round(12*.20)=2. That is the gap.
        got = df.mode_stats(self.BASE, self.GROWTHS, 10, 'difficult', self.SHIFTS)
        naive = df.autolevel(self.BASE, self.GROWTHS, 13)
        self.assertEqual(got['baseDef'], 3 + 2 + 1)
        self.assertNotEqual(got['baseDef'], naive['baseDef'])

    def test_a_zero_shift_leaves_the_projection_untouched(self):
        shifts = {'tutorial': 0, 'normal': 0, 'difficult': 0}
        for mode in ('tutorial', 'normal', 'difficult'):
            self.assertEqual(df.mode_stats(self.BASE, self.GROWTHS, 7, mode, shifts),
                             df.autolevel(self.BASE, self.GROWTHS, 7))


class VanillaChapterShifts(unittest.TestCase):
    """A parity reference's OWN difficulty triple, read from vanilla chapter_settings (#303).

    Resolved by `internalName`, not by slot index: FE8 inserts chapter 5x at slot 5 as
    `I05`, so from there on the slot index stops tracking the chapter number and
    `settings['chapters'][5]` is NOT vanilla Ch5 -- Ch5 is `L05`, at slot 6. The same
    off-by-one that makes _retarget_host_chapter's event_group mandatory.
    """

    def test_ch5_resolves_past_the_inserted_5x_slot(self):
        self.assertEqual(df.vanilla_chapter_shifts('FE8 Ch5'),
                         {'tutorial': 4, 'normal': 2, 'difficult': 3})

    def test_early_chapters_ship_no_malus_at_all(self):
        # L00/L01 are the two chapters vanilla leaves unshifted on Tutorial and Normal.
        self.assertEqual(df.vanilla_chapter_shifts('FE8 Prologue'),
                         {'tutorial': 0, 'normal': 0, 'difficult': 1})
        self.assertEqual(df.vanilla_chapter_shifts('FE8 Ch1'),
                         {'tutorial': 0, 'normal': 0, 'difficult': 1})

    def test_an_eirika_route_reference_resolves_on_its_own_prefix(self):
        self.assertEqual(df.vanilla_chapter_shifts('FE8 Ch13'),
                         {'tutorial': 4, 'normal': 2, 'difficult': 3})

    def test_slot_five_is_not_mistaken_for_chapter_five(self):
        # I05's own triple is 2/0/3 -- if the lookup ever indexes by number this fails.
        self.assertNotEqual(df.vanilla_chapter_shifts('FE8 Ch5'),
                            {'tutorial': 2, 'normal': 0, 'difficult': 3})


class ModeAwareProjection(unittest.TestCase):
    """Both sides of a parity read, shifted by their own chapter's numbers (#303).

    The default stays UNSHIFTED -- that is the authored table, which is what every
    parity verdict before #303 graded, and it is a real configuration in its own right
    (the level the YAML and the decomp's UnitDefinition arrays actually declare).
    """

    DEF = {'id': 'skeleton-line', 'class': 'fighter', 'level': 10,
           'inventory': [{'id': 'iron-axe'}]}
    SHIFTS = {'tutorial': 4, 'normal': 2, 'difficult': 3}

    def test_our_side_unshifted_by_default(self):
        plain = df.enemy_combatants(self.DEF)[0]
        explicit = df.enemy_combatants(self.DEF, mode='normal',
                                       shifts={'tutorial': 0, 'normal': 0, 'difficult': 0})[0]
        self.assertEqual(plain.hp, explicit.hp)
        self.assertEqual(plain.pow, explicit.pow)

    def test_normal_malus_weakens_our_side(self):
        plain = df.enemy_combatants(self.DEF)[0]
        normal = df.enemy_combatants(self.DEF, mode='normal', shifts=self.SHIFTS)[0]
        self.assertLess(normal.hp, plain.hp)

    def test_difficult_bonus_strengthens_our_side(self):
        plain = df.enemy_combatants(self.DEF)[0]
        hard = df.enemy_combatants(self.DEF, mode='difficult', shifts=self.SHIFTS)[0]
        self.assertGreater(hard.hp, plain.hp)

    def test_vanilla_side_shifts_by_its_own_chapter_numbers(self):
        plain = df.vanilla_enemies('FE8 Ch5')
        normal = df.vanilla_enemies('FE8 Ch5', mode='normal')
        self.assertEqual(len(plain), len(normal))
        self.assertLess(sum(e.hp for e in normal), sum(e.hp for e in plain))

    def test_a_red_unit_on_a_playable_slot_is_immune_to_the_shift(self):
        # eventscr.c:2328 gates the shift on `number >= 0x3C`. Vanilla Ch5 deploys
        # Joshua (0x20) RED before his Talk recruit, so he is the one unit in the
        # reference force the engine never shifts -- the exact mirror of our Sahnar,
        # who rides Joshua's own slot.
        plain = {e.name: e for e in df.vanilla_enemies('FE8 Ch5')}
        hard = {e.name: e for e in df.vanilla_enemies('FE8 Ch5', mode='difficult')}
        josh = [n for n in plain if 'JOSHUA' in n.upper()]
        self.assertEqual(len(josh), 1, 'expected exactly one Joshua in the Ch5 red force')
        name = josh[0]
        self.assertEqual(plain[name].hp, hard[name].hp)
        # ...while an ordinary generic in the same force DOES move.
        movers = [n for n in plain if plain[n].hp != hard[n].hp]
        self.assertTrue(movers, 'no generic was shifted at all')

    def test_prologue_reference_is_unchanged_because_it_has_no_malus(self):
        # L00 ships 0/0/1: Normal is the authored table exactly.
        plain = df.vanilla_enemies('FE8 Prologue')
        normal = df.vanilla_enemies('FE8 Prologue', mode='normal')
        self.assertEqual([e.hp for e in plain], [e.hp for e in normal])


class ChapterForceInMode(unittest.TestCase):
    """The our-side force builder, shifted (#303). Both `chapter_units` branches --
    the `composition` bag and the single-class entry -- must honour the mode, or a
    mixed-class chapter silently reports half its force unshifted."""

    SHIFTS = {'tutorial': 4, 'normal': 2, 'difficult': 3}

    def _chap(self):
        return df.load_field('rime-of-the-frostmaiden', 'ch05')[0]

    def test_normal_weakens_the_whole_force(self):
        chap = self._chap()
        plain = df.chapter_enemy_force(chap)
        normal = df.chapter_enemy_force(chap, mode='normal', shifts=self.SHIFTS)
        self.assertEqual(len(plain), len(normal))
        self.assertLess(sum(u.hp for u in normal), sum(u.hp for u in plain))

    def test_difficult_strengthens_the_whole_force(self):
        chap = self._chap()
        plain = df.chapter_enemy_force(chap)
        hard = df.chapter_enemy_force(chap, mode='difficult', shifts=self.SHIFTS)
        self.assertGreater(sum(u.hp for u in hard), sum(u.hp for u in plain))

    def test_a_composition_entry_is_shifted_too(self):
        # A bag entry goes down the _one_enemy branch, which took the mode last.
        ed = {'id': 'bag', 'composition': ['fighter', 'soldier'], 'level': 12,
              'inventory_by_class': {'fighter': ['iron-axe'], 'soldier': ['iron-lance']}}
        chap = {'enemy_units': [ed]}
        plain = df.chapter_enemy_force(chap)
        normal = df.chapter_enemy_force(chap, mode='normal', shifts=self.SHIFTS)
        self.assertEqual(len(plain), 2)
        self.assertTrue(all(n.hp < p.hp for n, p in zip(normal, plain)))


class ChapterPressureInMode(unittest.TestCase):
    """`_chapter_pressure` graded in a named mode (#303).

    The point of the flag is that a verdict says WHICH configuration it graded. Before
    this, every parity line read as general while grading the authored table -- and the
    authored table is a configuration no player meets in any chapter whose normal malus
    is non-zero.

    Both sides shift, each by its own chapter's declared numbers, so a mode read is
    still two tuned tables being compared rather than one tuned against one shifted.
    """

    def _ch(self, chid='ch05'):
        return df.load_field('rime-of-the-frostmaiden', chid)[0]

    def test_default_is_the_unshifted_authored_table(self):
        chap = self._ch()
        self.assertAlmostEqual(df._chapter_pressure(chap)['ours'][0],
                               df._chapter_pressure(chap, mode=None)['ours'][0])

    def test_a_mode_read_names_the_mode_it_graded(self):
        self.assertEqual(df._chapter_pressure(self._ch(), mode='normal')['mode'], 'normal')

    def test_normal_grades_a_weaker_force_than_the_authored_table(self):
        chap = self._ch()
        self.assertLess(df._chapter_pressure(chap, mode='normal')['ours'][0],
                        df._chapter_pressure(chap)['ours'][0])

    def test_parity_holds_in_every_mode(self):
        # The claim #303 rests on: adopting the twin's numbers means the verdict does
        # not depend on which mode is graded. True in all three, in every chapter.
        for chid in ('ch00', 'ch01', 'ch02', 'ch03', 'ch04', 'ch05'):
            chap = df.load_field('rime-of-the-frostmaiden', chid)[0]
            for mode in (None,) + df.MODES:
                p = df._chapter_pressure(chap, mode=mode)
                self.assertEqual(p['verdict']['verdict'], 'OK',
                                 '%s graded %s is %s' % (chid, mode, p['verdict']['verdict']))


class BossesAreImmuneToTheMalus(unittest.TestCase):
    """A boss whose baseLevel >= its deploy level never takes the malus -- model it (#303).

    `UnitAutolevelPenalty` fires only `if (level > pCharacterData->baseLevel)`. Every
    vanilla named boss ships baseLevel >= deploy level (Saar 8/8, Breguet 4/4, Bazba 6/6),
    and after RAW_PID_LEVEL_SOURCES so does every one of ours. So on Tutorial and Normal a
    boss keeps its authored line on BOTH sides.

    The model defaulted `base_level` to 1 and no caller passed anything, so it applied the
    malus to bosses that the ROM leaves alone -- understating both sides' walls in exactly
    the modes where clear-load is measured. It read ch05's Tutorial at clear-load x0.69 and
    called it OFF, a verdict about the model rather than the chapter.
    """

    def test_a_boss_at_its_base_level_keeps_its_line_under_any_malus(self):
        base = {'baseHP': 30, 'basePow': 10, 'baseSkl': 5, 'baseSpd': 5,
                'baseDef': 8, 'baseRes': 6, 'baseLck': 3, 'baseCon': 9}
        growths = {g: 50 for g in bc.GROWTH_FIELDS}
        shifts = {'tutorial': 4, 'normal': 2, 'difficult': 3}
        for mode in ('tutorial', 'normal'):
            self.assertEqual(
                df.mode_stats(base, growths, 8, mode, shifts, base_level=8),
                df.autolevel(base, growths, 8),
                '%s must not touch a boss at its own baseLevel' % mode)

    def test_vanilla_saar_is_unshifted_in_every_mode(self):
        # Saar is baseLevel 8 deploying at 8 -- the reference wall the ch05 read leans on.
        by_mode = {}
        for mode in (None,) + df.MODES:
            force = df.vanilla_enemies('FE8 Ch5', mode=mode)
            saar = [e for e in force if 'SAAR' in e.name.upper()]
            self.assertEqual(len(saar), 1)
            by_mode[mode] = saar[0].hp
        self.assertEqual(by_mode[None], by_mode['tutorial'])
        self.assertEqual(by_mode[None], by_mode['normal'])

    def test_our_ch05_boss_is_unshifted_in_every_mode(self):
        chap = df.load_field('rime-of-the-frostmaiden', 'ch05')[0]
        shifts = bc.chapter_difficulty_shifts(chap)
        hp = {}
        for mode in (None, 'tutorial', 'normal'):
            force = df.chapter_enemy_force(chap, mode=mode,
                                           shifts=shifts if mode else None)
            hp[mode] = max(u.hp for u in force)      # Ravisin is the wall
        self.assertEqual(hp[None], hp['tutorial'])
        self.assertEqual(hp[None], hp['normal'])


class RavisinHoldsSaarsBar(unittest.TestCase):
    """ch05's boss is measured against her twin's REAL durability, not a stale number.

    Her YAML note has read "~13 rounds to kill -- Saar's bar" since she was authored, and
    she hit it exactly. But that bar was measured before #285 taught the model to apply a
    personal line to BOTH sides: once vanilla's bosses stopped being read off naked class
    base, Saar moved to 22.8 rounds and nobody re-checked her. She was holding a bar that
    had moved out from under her, which is why ch05's clear-load sat under vanilla's in
    every mode and fell out of band on Tutorial (x0.74), where the generics floor to class
    base and the boss dominates the ratio.

    Pinned as a RANGE against Saar rather than a constant, so the next change to either
    side's modelling fails here instead of silently re-opening the same gap.
    """

    def _rounds(self, name_match, force):
        return max(df.metric_rounds_to_kill(e) for e in force
                   if name_match(e.name))

    def test_ravisin_is_within_reach_of_saars_measured_durability(self):
        chap = df.load_field('rime-of-the-frostmaiden', 'ch05')[0]
        shifts = bc.chapter_difficulty_shifts(chap)
        ours = df.chapter_enemy_force(chap, mode='normal', shifts=shifts)
        ravisin = max(df.metric_rounds_to_kill(e) for e in ours)
        saar = self._rounds(lambda n: 'SAAR' in n.upper(),
                            df.vanilla_enemies('FE8 Ch5', mode='normal'))
        self.assertGreater(saar, 20, 'Saar moved -- re-read the bar before trusting it')
        self.assertGreater(ravisin, saar * 0.85,
                           'Ravisin %.1f is under Saar %.1f -- ch05 loses its wall' 
                           % (ravisin, saar))
        self.assertLess(ravisin, saar * 1.30,
                        'Ravisin %.1f overshoots Saar %.1f' % (ravisin, saar))

    def test_ch05_clearload_is_in_band_in_every_mode(self):
        chap = df.load_field('rime-of-the-frostmaiden', 'ch05')[0]
        for mode in (None,) + df.MODES:
            p = df._chapter_pressure(chap, mode=mode)
            self.assertEqual(p['verdict']['verdict'], 'OK',
                             'ch05 graded %s is %s (clear-load x%.2f)'
                             % (mode, p['verdict']['verdict'],
                                p['ours'][1] / p['vanilla'][1]))


class OurUnitsOnPlayableSlotsAreImmune(unittest.TestCase):
    """The `>= 0x3C` gate applies to OUR side too, not just the vanilla reference (#303).

    `eventscr.c` shifts a RED unit only when `pCharacterData->number >= 0x3C`, so a cast
    member deployed hostile -- which rides a PLAYABLE slot -- is difficulty-immune. ch05's
    Sahnar is exactly that, and the ROM confirms it: measured across all three modes he
    reads the same stats every time, the one unit in the chapter that never moves.

    The model gated the vanilla side (vanilla Ch5's pre-recruit Joshua) but never threaded
    `shiftable` through OUR force builder, so it shifted Sahnar anyway -- biasing the ch05
    ratios that ch05's own boss bar was then tuned against.
    """

    def _ch05(self):
        chap = df.load_field('rime-of-the-frostmaiden', 'ch05')[0]
        return chap, bc.chapter_difficulty_shifts(chap)

    def test_sahnar_is_identical_in_every_mode(self):
        chap, shifts = self._ch05()
        hp = {}
        for mode in (None,) + df.MODES:
            force = df.chapter_units(chap, mode=mode, shifts=shifts if mode else None)
            sahnar = [u for ed, u in force if ed.get('id') == 'sahnar']
            self.assertEqual(len(sahnar), 1)
            hp[mode] = sahnar[0].hp
        self.assertEqual(len(set(hp.values())), 1,
                         'Sahnar moved across modes: %s' % hp)

    def test_a_generic_in_the_same_chapter_still_moves(self):
        # Guards against "fixed" by making everything immune.
        chap, shifts = self._ch05()
        plain = df.chapter_units(chap)
        hard = df.chapter_units(chap, mode='difficult', shifts=shifts)
        movers = [ed.get('id') for (ed, a), (_e, b) in zip(plain, hard) if a.hp != b.hp]
        self.assertTrue(movers, 'no unit shifted at all')

    def test_the_resolver_reads_the_slot_the_unit_rides(self):
        self.assertFalse(df._our_takes_difficulty_shift({'id': 'sahnar'}))
        self.assertTrue(df._our_takes_difficulty_shift({'id': 'ravisin'}))
        self.assertTrue(df._our_takes_difficulty_shift({'id': 'tomb-reaver'}))


class ModeReadsAreHonestAboutScope(unittest.TestCase):
    """`--mode` must either apply everywhere it claims, or refuse (#303 review).

    A verdict that does not name its configuration is the thing #303 set out to fix, so a
    mode flag that is silently ignored -- or a banner that overstates what was shifted --
    reintroduces the original defect in a new place.
    """

    def test_a_single_chapter_report_honours_the_mode(self):
        chap = df.load_field('rime-of-the-frostmaiden', 'ch05')[0]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            df.report('rime-of-the-frostmaiden', 'ch05', mode='difficult')
        self.assertIn('DIFFICULT', out.getvalue().upper())

    def test_a_reference_with_unknown_difficulty_numbers_refuses_a_mode_read(self):
        # Returning an UNSHIFTED vanilla force here would compare our shifted side against
        # vanilla's authored table and still print a verdict.
        spec = df.PARITY_REFERENCE_UDEFS['FE8 Ch5']
        df.PARITY_REFERENCE_UDEFS['FE8 Creature Campaign'] = spec
        try:
            self.assertIsNone(df.vanilla_chapter_shifts('FE8 Creature Campaign'))
            with self.assertRaises(SystemExit):
                df.vanilla_enemies('FE8 Creature Campaign', mode='normal')
        finally:
            del df.PARITY_REFERENCE_UDEFS['FE8 Creature Campaign']

    def test_role_findings_are_not_reported_as_mode_graded(self):
        # role_findings/vanilla_projection run on the authored table. Under --mode the
        # banner must say so rather than implying everything was shifted.
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            df.curve_report('rime-of-the-frostmaiden', mode='normal')
        text = out.getvalue()
        self.assertIn('role findings', text.lower())
        self.assertIn('authored table', text.lower())


class BossBaseLevelMarginIsGuarded(unittest.TestCase):
    """Our ENEMY_BASE_SLOT bosses sit at ZERO margin against their donor's baseLevel.

    `_our_base_level` treats every boss as penalty-immune. That is enforced for raw pids
    (RAW_PID_LEVEL_SOURCES writes baseLevel = deploy level) but merely TRUE TODAY for the
    three on vanilla slots: Breguet 4/4, Bone 4/4, Bazba 6/6. Bump any of those a level and
    the model silently diverges from the ROM, which would start applying the malus.
    """

    def test_every_slot_boss_still_has_room(self):
        bad = df.bosses_over_their_donor_base_level('rime-of-the-frostmaiden')
        self.assertEqual(bad, [],
                         'boss(es) now deploy ABOVE their donor baseLevel, so the ROM will '
                         'apply the malus while the model assumes immunity: %s' % bad)


if __name__ == '__main__':
    unittest.main()
