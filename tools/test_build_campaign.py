#!/usr/bin/env python3
"""Tests for tools/build_campaign.py stat-resolution helpers.

These pin the donor-inheritance primitives the difficulty engine and the character
patcher share, against real vanilla values read from fireemblem8u/src/data_characters.c.
Run:  python3 tools/test_build_campaign.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_campaign as bc

# Read the COMMITTED decomp, not the working tree -- the build overwrites donor portrait
# slots (Gilliam/Neimi/Moulder/Vanessa), so a working-tree read would be non-hermetic.
VANILLA = bc.vanilla_decomp_text('src/data_characters.c')


class DonorBaseStats(unittest.TestCase):
    def test_reads_garcias_personal_bases(self):
        # Garcia (braulo's donor): a real personal line on top of the Fighter class.
        self.assertEqual(bc.donor_base_stats(VANILLA, 'CHARACTER_GARCIA'), {
            'baseHP': 8, 'basePow': 3, 'baseSkl': 5, 'baseSpd': 3,
            'baseDef': 3, 'baseRes': 1, 'baseLck': 3, 'baseCon': 3,
        })

    def test_reads_ewans_personal_bases(self):
        # Ewan (the shamans' Ch1-appropriate base donor): fast + lucky mage kid.
        self.assertEqual(bc.donor_base_stats(VANILLA, 'CHARACTER_EWAN'), {
            'baseHP': 2, 'basePow': 2, 'baseSkl': 2, 'baseSpd': 4,
            'baseDef': 0, 'baseRes': 0, 'baseLck': 5, 'baseCon': 0,
        })

    def test_reads_gilliams_personal_bases_from_committed_source(self):
        # Gilliam (wolfram's donor) RIDES a portrait slot the build overwrites; reading
        # the committed source (not the mutated working tree) gives his real durable line.
        self.assertEqual(bc.donor_base_stats(VANILLA, 'CHARACTER_GILLIAM'), {
            'baseHP': 8, 'basePow': 4, 'baseSkl': 4, 'baseSpd': 3,
            'baseDef': 0, 'baseRes': 3, 'baseLck': 3, 'baseCon': 1,
        })


class PersonalBaseDeltas(unittest.TestCase):
    """The personal-base layer a cast slot is patched to: (authored - class) + donor line."""

    def test_zero_when_fe_stats_match_class_and_donor_is_blank(self):
        # Wolfram: fe_stats == Armor Knight class base, Gilliam donor all-0 -> naked class.
        fe = {'HP': 17, 'STR': 5, 'SKL': 2, 'SPD': 0, 'DEF': 9, 'RES': 0, 'LCK': 0,
              'CON': 13, 'MOV': 4}
        cbase = {'baseHP': 17, 'basePow': 5, 'baseSkl': 2, 'baseSpd': 0, 'baseDef': 9,
                 'baseRes': 0, 'baseLck': 0, 'baseCon': 13, 'baseMov': 4}
        donor = {bf: 0 for bf in bc.BASE_FIELDS}
        self.assertEqual(bc.personal_base_deltas(fe, cbase, donor),
                         {bf: 0 for bf in bc.BASE_FIELDS})

    def test_adds_donor_personal_line_on_top_of_a_class_match(self):
        # Braulo: fe_stats == Pirate class base; Garcia's line becomes the personal layer.
        fe = {'HP': 19, 'STR': 4, 'SKL': 2, 'SPD': 6, 'DEF': 3, 'RES': 0, 'LCK': 0, 'CON': 10}
        cbase = {'baseHP': 19, 'basePow': 4, 'baseSkl': 2, 'baseSpd': 6, 'baseDef': 3,
                 'baseRes': 0, 'baseLck': 0, 'baseCon': 10}
        garcia = {'baseHP': 8, 'basePow': 3, 'baseSkl': 5, 'baseSpd': 3, 'baseDef': 3,
                  'baseRes': 1, 'baseLck': 3, 'baseCon': 3}
        self.assertEqual(bc.personal_base_deltas(fe, cbase, garcia), garcia)

    def test_authored_divergence_stacks_on_the_donor_line(self):
        # A deliberate fe_stats bump over class base stacks on top of the donor base.
        self.assertEqual(bc.personal_base_deltas({'HP': 21}, {'baseHP': 19}, {'baseHP': 8}),
                         {'baseHP': 10})

    def test_ignores_class_only_mov(self):
        out = bc.personal_base_deltas({'HP': 1, 'MOV': 9}, {'baseHP': 1}, {'baseHP': 0})
        self.assertNotIn('baseMov', out)


class FeItemEnum(unittest.TestCase):
    """Resolve a YAML inventory entry to its vanilla ITEM_ enum -- via fe_base (a flavor
    name over a vanilla weapon) else the id itself (a plain vanilla weapon). Lets the
    prologue injector drive the boss weapon from the ch00 YAML, not a hardcode (#52)."""

    def test_resolves_flavor_weapon_via_fe_base(self):
        # Sephek's "ice-longsword" is flavor; fe_base steel-sword supplies the real item.
        self.assertEqual(bc.fe_item_enum({'id': 'ice-longsword', 'fe_base': 'steel-sword'}),
                         'ITEM_SWORD_STEEL')

    def test_resolves_plain_weapon_via_id(self):
        self.assertEqual(bc.fe_item_enum({'id': 'iron-axe'}), 'ITEM_AXE_IRON')


class DonorMaps(unittest.TestCase):
    def test_shamans_take_ewan_bases_but_keep_dark_rank_donor(self):
        # Bases from Ewan (Ch1-appropriate); ranks stay on Knoll (ITYPE_DARK), so the
        # Dark tome still equips. Growths split: Marty->Knoll (Druid), Mees->Ewan (Summoner).
        self.assertEqual(bc.BASE_DONOR['marty'], 'CHARACTER_EWAN')
        self.assertEqual(bc.BASE_DONOR['meesmickle'], 'CHARACTER_EWAN')
        self.assertEqual(bc.STAT_DONOR['meesmickle'], 'CHARACTER_KNOLL')   # rank donor
        self.assertEqual(bc.GROWTH_DONOR['marty'], 'CHARACTER_KNOLL')
        self.assertEqual(bc.GROWTH_DONOR['meesmickle'], 'CHARACTER_EWAN')


class LordFloorRows(unittest.TestCase):
    """The per-lord survivability-floor table (#45 3b) the build emits as gLordFloorDeltas[]
    and the engine applies once at chapter start (#45 3c). One (hp, def, res) row per lord
    candidate, in the menu order the C table is indexed by. Oracle: difficulty --lord-floor."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_ch1_deltas_match_the_floor_solver(self):
        # vs Ch1 enemies @target 3.5: the shamans are the glass picks (+7HP/+4Def); the armor
        # tanks (braulo/wolfram) already clear the floor, so they take nothing.
        rows = {uid: (hp, df, res) for uid, hp, df, res in bc.lord_floor_rows(
            self.CAMPAIGN, ['marty', 'meesmickle', 'pinky', 'braulo', 'wolfram'])}
        self.assertEqual(rows['marty'], (7, 4, 0))
        self.assertEqual(rows['meesmickle'], (7, 4, 0))
        self.assertEqual(rows['pinky'], (0, 4, 0))
        self.assertEqual(rows['braulo'], (0, 0, 0))
        self.assertEqual(rows['wolfram'], (0, 0, 0))

    def test_rows_preserve_candidate_order(self):
        # gLordFloorDeltas[] is indexed parallel to gLordSelectCandidates[], so the row order
        # MUST match the menu order it is handed -- a reorder would mis-assign every floor.
        order = ['wolfram', 'marty', 'pinky']
        self.assertEqual([uid for uid, *_ in bc.lord_floor_rows(self.CAMPAIGN, order)], order)


class LordSelectPitches(unittest.TestCase):
    """The qualitative candidate blurbs (#46) the build emits as gLordSelectPitchMsg[],
    drawn by lord_select_screen.c as the cursor lands on each candidate. One (uid, pitch)
    per candidate, in the menu order the C table is indexed by -- PARALLEL to
    gLordSelectCandidates[]. The pitch is hand-authored YAML (lord_pitch:), never derived
    from stats; the build HARD-FAILS if any candidate lacks one (no silent gaps)."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_returns_each_candidates_authored_pitch_in_order(self):
        rows = bc.lord_select_pitches(self.CAMPAIGN, ['braulo', 'pinky', 'wolfram'])
        self.assertEqual([uid for uid, _ in rows], ['braulo', 'pinky', 'wolfram'])
        self.assertEqual(rows[0][1],
                         bc.load_unit(self.CAMPAIGN, 'braulo')['lord_pitch'])
        self.assertEqual(rows[1][1],
                         bc.load_unit(self.CAMPAIGN, 'pinky')['lord_pitch'])

    def test_preserves_candidate_order(self):
        # gLordSelectPitchMsg[] is indexed parallel to gLordSelectCandidates[]: a reorder
        # would show the wrong blurb under every cursor position.
        order = ['wolfram', 'marty', 'pinky']
        self.assertEqual([uid for uid, _ in bc.lord_select_pitches(self.CAMPAIGN, order)],
                         order)

    def test_hard_fails_when_a_candidate_lacks_a_pitch(self):
        # Baxby (an NPC) carries no lord_pitch -> the build must refuse rather than ship a
        # blank card (the "no silent gaps" lock, Nicolas 2026-06-20).
        with self.assertRaises(SystemExit):
            bc.lord_select_pitches(self.CAMPAIGN, ['braulo', 'baxby'])


class BattleAnimInjection(unittest.TestCase):
    """Pure transforms behind the faked-battle-anim injection (#65 M-A)."""

    BANIM = ('struct BattleAnim banim_data[] = {\n'
             '\t{"arcm_ar1", &banim_arcm_ar1_modes_bin, &banim_arcm_ar1_motion_o, '
             '&banim_arcm_ar1_oam_r_bin, &banim_arcm_ar1_oam_l_bin, &banim_arcm_ar1_agbpal}, // 0x25\n'
             '\t{"arcm_ar1", &banim_arcm_ar1_2_modes_bin, &banim_arcm_ar1_2_motion_o, '
             '&banim_arcm_ar1_2_oam_r_bin, &banim_arcm_ar1_2_oam_l_bin, &banim_arcm_ar1_2_agbpal}, // 0x26\n'
             '};\n')

    def test_append_row_grows_by_one_and_returns_the_new_id(self):
        new, anim_id = bc.banim_append_row(self.BANIM, 'rbg_ar1')
        self.assertEqual(anim_id, 2)                                  # 2 rows -> id 0x2
        self.assertEqual(new.count('\t{"'), 3)                        # grew by exactly one
        self.assertIn('{"rbg_ar1", &banim_rbg_ar1_modes_bin, &banim_rbg_ar1_motion_o, '
                      '&banim_rbg_ar1_oam_r_bin, &banim_rbg_ar1_oam_l_bin, '
                      '&banim_rbg_ar1_agbpal}', new)

    def test_append_row_leaves_the_donor_rows_byte_unchanged(self):
        new, _ = bc.banim_append_row(self.BANIM, 'rbg_ar1')
        for donor in ('arcm_ar1_modes_bin', 'arcm_ar1_2_modes_bin'):
            self.assertEqual(new.count(donor), self.BANIM.count(donor))  # additive only
        self.assertLess(new.index('};'), len(new))                       # still closed

    def test_repoint_conf_changes_only_the_matched_weapon_index(self):
        conf = ('CONST_DATA struct BattleAnimDef AnimConf_088AF150[] = {\n'
                '    { .wtype = 0x0100 | ITYPE_BOW, .index = 0x0026, },\n'
                '    { .wtype = 0x0100 | ITYPE_ITEM, .index = 0x0027, },\n'
                '    { 0 }\n};\n')
        new = bc.banim_repoint_conf(conf, 'AnimConf_088AF150', '0x0100 | ITYPE_BOW', 0xC9)
        self.assertIn('.wtype = 0x0100 | ITYPE_BOW, .index = 0xC9', new)
        self.assertIn('.wtype = 0x0100 | ITYPE_ITEM, .index = 0x0027', new)  # untouched

    def test_clone_conf_appends_a_private_copy_and_leaves_the_donor_vanilla(self):
        conf = ('CONST_DATA struct BattleAnimDef AnimConf_088AF150[] = {\n'
                '    { .wtype = 0x0100 | ITYPE_BOW, .index = 0x0026, },\n'
                '    { 0 }\n};\n')
        new = bc.banim_clone_conf(conf, 'AnimConf_088AF150', 'AnimConf_rbg_ar1',
                                  '0x0100 | ITYPE_BOW', 0xC9)
        # donor entry byte-unchanged
        self.assertIn('AnimConf_088AF150[] = {\n    { .wtype = 0x0100 | ITYPE_BOW, '
                      '.index = 0x0026, },', new)
        # a NEW conf appended, with the bow entry repointed
        self.assertIn('struct BattleAnimDef AnimConf_rbg_ar1[] =', new)
        self.assertIn('.wtype = 0x0100 | ITYPE_BOW, .index = 0xC9', new)


class BattlePlatformTerrain(unittest.TestCase):
    """Terrain category -> snow ground index (#65). base = first vendored ground slot;
    offsets 0=Snowdrift, 1=Snow Uneven (rough), 2=Ice."""

    def test_open_ground_is_snowdrift_on_the_open_tileset(self):
        # plains/road/floor read as open drift on the snow-OPEN tileset (prologue).
        self.assertEqual(bc._terrain_snow_ground('PLAINS', 115, False), 115)
        self.assertEqual(bc._terrain_snow_ground('ROAD', 115, False), 115)

    def test_open_ground_becomes_rough_on_the_rough_tileset(self):
        # the Ch1 snow-ROUGH tileset sends the same open ground to Snow Uneven.
        self.assertEqual(bc._terrain_snow_ground('PLAINS', 115, True), 116)
        self.assertEqual(bc._terrain_snow_ground('ROAD', 115, True), 116)

    def test_rough_terrain_is_always_uneven(self):
        for t in ('MOUNTAIN', 'PEAK', 'CLIFF', 'VALLEY'):
            self.assertEqual(bc._terrain_snow_ground(t, 115, False), 116)
            self.assertEqual(bc._terrain_snow_ground(t, 115, True), 116)

    def test_water_terrain_is_always_ice(self):
        for t in ('LAKE', 'SEA', 'RIVER', 'WATER', 'GLACIER'):
            self.assertEqual(bc._terrain_snow_ground(t, 115, False), 117)
            self.assertEqual(bc._terrain_snow_ground(t, 115, True), 117)  # even on the rough tileset


if __name__ == '__main__':
    unittest.main()
