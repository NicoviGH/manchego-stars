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
    """The --check gate (#48 (b)): a chapter that claims a vanilla parity reference must
    be at-parity AND reliably measured. Chapters with no curated reference are informational
    and never gate. Wired into CI informatively (no --check) until content authors the Ch2+
    enemy inventories; then the CI step flips to --check to make off-parity a build failure."""

    def _row(self, label, has_ref=True, verdict='OK', boss_drop=False):
        return {'label': label, 'has_ref': has_ref, 'verdict': verdict,
                'boss_drop': boss_drop}

    def test_all_at_parity_with_an_uncurated_chapter_passes(self):
        rows = [self._row('CH1', verdict='OK'),
                self._row('CH8', has_ref=False, verdict=None)]
        self.assertEqual(df.curve_gate_failures(rows), [])

    def test_off_parity_referenced_chapter_fails(self):
        rows = [self._row('CH1', verdict='OK'),
                self._row('CH2', verdict='OFF')]
        self.assertEqual(df.curve_gate_failures(rows), ['CH2'])

    def test_dropped_boss_on_referenced_chapter_fails_even_if_verdict_ok(self):
        # A dropped boss makes the verdict unreliable -- an unreliable OK is not a pass.
        rows = [self._row('CH3', verdict='OK', boss_drop=True)]
        self.assertEqual(df.curve_gate_failures(rows), ['CH3'])

    def test_uncurated_chapter_never_gates_even_with_a_dropped_boss(self):
        rows = [self._row('CH8', has_ref=False, verdict=None, boss_drop=True)]
        self.assertEqual(df.curve_gate_failures(rows), [])


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


_UDEF_SNIPPET = """
CONST_DATA struct UnitDefinition UnitDef_Test[] = {
    {
        .charIndex = CHARACTER_BREGUET,
        .classIndex = CLASS_ARMOR_KNIGHT,
        .allegiance = FACTION_ID_RED,
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


class VanillaUnitDefParser(unittest.TestCase):
    def test_parses_each_entry_class_level_allegiance_items(self):
        defs = df.vanilla_unit_defs(_UDEF_SNIPPET, 'UnitDef_Test')
        self.assertEqual(len(defs), 3)           # the { 0 } terminator is skipped
        self.assertEqual(defs[0], {'classIndex': 'CLASS_ARMOR_KNIGHT', 'level': 4,
                                   'allegiance': 'FACTION_ID_RED',
                                   'items': ['ITEM_LANCE_IRON']})
        self.assertEqual(defs[1]['classIndex'], 'CLASS_SOLDIER')
        self.assertEqual(defs[1]['items'], ['ITEM_LANCE_IRON', 'ITEM_VULNERARY'])
        self.assertEqual(defs[2]['allegiance'], 'FACTION_ID_BLUE')


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
