#!/usr/bin/env python3
"""Tests for tools/build_campaign.py stat-resolution helpers.

These pin the donor-inheritance primitives the difficulty engine and the character
patcher share, against real vanilla values read from fireemblem8u/src/data_characters.c.
Run:  python3 tools/test_build_campaign.py
"""
import os
import re
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


class TrexRecruitCast(unittest.TestCase):
    """Trex (ch03 recruit, #23) is a full classed cast member: a Thief riding the vanilla
    Rennac slot, donoring from Colm, deployable so his vendored custom sprite renders."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_trex_rides_the_rennac_slot(self):
        self.assertEqual(bc.PORTRAIT_MAP['trex'], 'Rennac')

    def test_trex_donors_from_colm_for_stats_bases_and_growths(self):
        self.assertEqual(bc.STAT_DONOR['trex'], 'CHARACTER_COLM')
        self.assertEqual(bc.BASE_DONOR['trex'], 'CHARACTER_COLM')
        self.assertEqual(bc.GROWTH_DONOR['trex'], 'CHARACTER_COLM')

    def test_trex_resolves_as_a_thief_in_the_classed_cast(self):
        cast = {uid: (slot, cls) for uid, slot, cls, _sms in bc.classed_cast(self.CAMPAIGN)}
        self.assertEqual(cast['trex'], ('Rennac', 'CLASS_THIEF'))

    def test_thief_loadout_and_testch_covers_the_whole_cast(self):
        # inject_test_chapter needs a Thief loadout + one spawn tile per classed cast
        # member (10 now: 8 founding + Baxby + Trex); both would sys.exit otherwise.
        self.assertIn('CLASS_THIEF', bc.CLASS_LOADOUT)
        allcast, _ = bc._classed_cast(self.CAMPAIGN)   # available_at=None -> everyone
        self.assertEqual(len(allcast), 10)
        self.assertGreaterEqual(len(bc.TEST_SPAWN_POSITIONS), len(allcast))
        # ch03's blue field roster = cast_available_at(3); its deploy tiles must cover it.
        field, _ = bc._classed_cast(self.CAMPAIGN, available_at=3)
        self.assertGreaterEqual(len(bc.CH03_SPAWN_POSITIONS), len(field))

    def test_trex_has_a_death_quote_and_a_dead_slot2_msg_id(self):
        self.assertIn('trex', bc.PC_DEATH_QUOTE_MSGS)
        unit = bc.load_unit(self.CAMPAIGN, 'trex')
        self.assertTrue(unit.get('death_quote'))


class RecruitAvailability(unittest.TestCase):
    """The reusable, data-driven recruit model (#23): a recruit is a classed cast member
    with a `recruit.chapter`; cast_available_at(N) puts it on the field from the chapter
    AFTER it is recruited. Baxby (ch01 cutscene recruit) and Trex (ch03 talk recruit)."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_recruit_chapter_numbers(self):
        for uid, want in (('baxby', 1), ('trex', 3)):
            u = bc.load_unit(self.CAMPAIGN, uid)
            self.assertEqual(bc.recruit_chapter_number(self.CAMPAIGN, u), want)

    def test_founding_pc_has_no_recruit_chapter(self):
        self.assertIsNone(bc.recruit_chapter_number(
            self.CAMPAIGN, bc.load_unit(self.CAMPAIGN, 'braulo')))

    def test_availability_climbs_with_the_chapters(self):
        def ids(n):
            return {u for u, *_ in bc._classed_cast(self.CAMPAIGN, available_at=n)[0]}
        ch1, ch2, ch3, ch4 = ids(1), ids(2), ids(3), ids(4)
        self.assertNotIn('baxby', ch1)              # recruited IN ch01 -> not on the ch01 field
        self.assertIn('baxby', ch2)                 # on the field from ch02 (prep)
        self.assertEqual(len(ch1), 8)               # the founding party
        self.assertNotIn('trex', ch3)               # talk-recruited IN ch03 -> placed green, not prep
        self.assertIn('trex', ch4)                  # on the prep roster from ch04
        self.assertIn('baxby', ch3)

    def test_baxby_is_a_cavalier_on_the_forde_slot_donoring_franz(self):
        self.assertEqual(bc.PORTRAIT_MAP['baxby'], 'Forde')
        self.assertEqual(bc.STAT_DONOR['baxby'], 'CHARACTER_FRANZ')
        self.assertNotIn('baxby', bc.GUEST_PORTRAIT_MAP)   # promoted from cutscene-face to real unit
        cast = {u: (s, c) for u, s, c, _ in bc.classed_cast(self.CAMPAIGN)}
        self.assertEqual(cast['baxby'], ('Forde', 'CLASS_CAVALIER'))

    def test_baxby_has_a_death_quote_and_a_dead_slot2_msg_id(self):
        self.assertIn('baxby', bc.PC_DEATH_QUOTE_MSGS)
        self.assertTrue(bc.load_unit(self.CAMPAIGN, 'baxby').get('death_quote'))

    def test_offmap_recruit_joins_the_chapter_after_recruitment(self):
        """The availability filter only SIZES the deploy cap; an off-map cutscene recruit
        (Baxby) needs an explicit between-chapter join-LOAD to enter the saved party. It
        fires the chapter AFTER recruitment, exactly once (#23 recruit-persist)."""
        def ids(n):
            return {u for u, *_ in bc.offmap_join_recruits(self.CAMPAIGN, n)}
        self.assertEqual(ids(1), set())        # nobody is recruited before ch01
        self.assertEqual(ids(2), {'baxby'})    # ch01 cutscene recruit joins the party at ch02
        self.assertEqual(ids(3), set())        # already joined at ch02 -> no re-LOAD (no duplicate)

    def test_offmap_join_excludes_on_map_talk_recruits(self):
        """Trex is a Colm-style on-map talk recruit (recruit.via = story): he self-joins via
        CUSA on the map and persists naturally, so he never needs an off-map join-LOAD."""
        for n in range(1, 6):
            self.assertNotIn('trex', {u for u, *_ in bc.offmap_join_recruits(self.CAMPAIGN, n)})

    def test_offmap_join_recruit_carries_slot_and_class(self):
        """The join-LOAD row needs the unit's slot + real/deploy class + level, like the cap."""
        rows = bc.offmap_join_recruits(self.CAMPAIGN, 2)
        baxby = next(r for r in rows if r[0] == 'baxby')
        uid, slot, class_enum, deploy_class, level = baxby
        self.assertEqual(slot, 'Forde')
        self.assertEqual(class_enum, 'CLASS_CAVALIER')
        self.assertIn(class_enum, bc.CLASS_LOADOUT)   # the join-LOAD arms him from CLASS_LOADOUT


class TalkRecruitWiring(unittest.TestCase):
    """Trex's Colm-style talk recruit (#23 item 2): placed GREEN, recruited when ANY core
    party member Talks to him (one CHAR entry per candidate -> one shared script -> CUSA).
    These pin the pure data + string builders inject_ch03 consumes."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_char_symbol_from_slot(self):
        self.assertEqual(bc.char_symbol('Rennac'), 'CHARACTER_RENNAC')
        self.assertEqual(bc.char_symbol('Eirika'), 'CHARACTER_EIRIKA')

    def test_trex_is_ch03_on_map_talk_recruit_on_the_rennac_slot(self):
        """on_map_talk_recruits(N) = the recruits who join mid-map via Talk in chapter N."""
        rows = bc.on_map_talk_recruits(self.CAMPAIGN, 3)
        self.assertEqual([r[0] for r in rows], ['trex'])
        uid, slot, class_enum, deploy_class, level = rows[0]
        self.assertEqual(slot, 'Rennac')                 # Trex's on-map CHARACTER symbol slot
        self.assertEqual(class_enum, 'CLASS_THIEF')

    def test_no_talk_recruit_in_a_chapter_without_one(self):
        """ch02 has no on-map talk recruit (Baxby is an off-map cutscene recruit)."""
        self.assertEqual(bc.on_map_talk_recruits(self.CAMPAIGN, 2), [])

    def test_recruiters_are_the_ch03_field_roster_minus_trex(self):
        """Talker = ANY core party member -> the ch03 blue field roster (cast_available_at(3)).
        Trex himself is never a recruiter (he is the green target, not on the prep roster)."""
        recruiters = bc.talk_recruiters(self.CAMPAIGN, 3)
        field = {bc.char_symbol(slot) for _, slot, *_ in bc._classed_cast(self.CAMPAIGN, available_at=3)[0]}
        self.assertEqual(set(recruiters), field)
        self.assertNotIn('CHARACTER_RENNAC', recruiters)   # the target isn't a recruiter
        self.assertGreaterEqual(len(recruiters), 8)        # the founding party at least

    def test_char_entries_one_per_recruiter_sharing_flag_and_script(self):
        """The talker-agnostic wiring: one CHAR(flag, script, recruiter, target) per candidate,
        all pointing at the SAME flag + script + target (so any one talk recruits + disables all)."""
        recruiters = ['CHARACTER_EIRIKA', 'CHARACTER_FRANZ', 'CHARACTER_GILLIAM']
        c = bc.talk_recruit_char_entries(recruiters, 'CHARACTER_RENNAC',
                                         'EVFLAG_TMP(9)', 'EventScr_TrexTalk')
        self.assertEqual(c.count('CHAR('), 3)
        for r in recruiters:
            self.assertIn('CHAR(EVFLAG_TMP(9), EventScr_TrexTalk, %s, CHARACTER_RENNAC)' % r, c)

    def test_recruit_script_flips_the_target_blue_with_cusa(self):
        """The shared script shows the talk line then CUSA(target) = EvtChangeFaction to BLUE."""
        s = bc.talk_recruit_script(0x9A5, 'CHARACTER_RENNAC')
        self.assertIn('TEXTSHOW(0x9A5)', s)
        self.assertIn('CUSA(CHARACTER_RENNAC)', s)
        self.assertTrue(s.rstrip().endswith('ENDA\n}') or s.rstrip().endswith('ENDA'))


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
    """The qualitative candidate blurbs (#46) the build emits as sLordSelectPitchMsg[],
    drawn by LordSelect_DrawCard as the cursor lands on each candidate. One (uid, pitch)
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
        # sLordSelectPitchMsg[] is indexed parallel to gLordSelectCandidates[]: a reorder
        # would show the wrong blurb under every cursor position.
        order = ['wolfram', 'marty', 'pinky']
        self.assertEqual([uid for uid, _ in bc.lord_select_pitches(self.CAMPAIGN, order)],
                         order)

    def test_hard_fails_when_a_candidate_lacks_a_pitch(self):
        # Baxby (an NPC) carries no lord_pitch -> the build must refuse rather than ship a
        # blank card (the "no silent gaps" lock, Nicolas 2026-06-20).
        with self.assertRaises(SystemExit):
            bc.lord_select_pitches(self.CAMPAIGN, ['braulo', 'baxby'])


class TerminatorParity(unittest.TestCase):
    """_term_pad guards FE8's Huffman terminator: the utf8 packer pairs printable bytes
    two-at-a-time, so a printable run with an ODD length swallows the byte after it. When
    that byte is [X] (0x00) the decoder runs into the next message. The parity that matters
    is the FINAL run (printables after the last control code), NOT the whole message
    (decisions.md, refined 2026-06-25 for the multi-line lord-select pitches, #46)."""

    def test_single_run_even_is_left_alone(self):
        self.assertEqual(bc._term_pad('Seth[X]'), 'Seth[X]')        # 4 even -> no pad

    def test_single_run_odd_is_padded(self):
        self.assertEqual(bc._term_pad('Franz[X]'), 'Franz[.][X]')   # 5 odd -> pad

    def test_multiline_even_total_but_odd_final_run_is_padded(self):
        # The bug class: earlier [LF] runs are odd, so the TOTAL is even (old code skipped
        # the pad) yet the FINAL run is odd and eats [X]. Mirrors Pinky's 16+19+13 pitch.
        self.assertEqual(bc._term_pad('a[LF]cde[X]'), 'a[LF]cde[.][X]')   # total 4 even, final 3 odd
        self.assertEqual(bc._term_pad('Flying[LF]over[LF]bows[X]'),       # 6+4+4=14 even, final 4 even
                         'Flying[LF]over[LF]bows[X]')                     # -> no pad (final even)

    def test_multiline_odd_total_but_even_final_run_is_not_padded(self):
        # The inverse: odd total would have tripped the old whole-message rule, but the
        # final run is even, so [X] is safe and no pad is wanted.
        self.assertEqual(bc._term_pad('abc[LF]de[X]'), 'abc[LF]de[X]')    # total 5 odd, final 2 even

    def test_control_codes_do_not_count_toward_the_final_run(self):
        # The final run is the printables after the LAST control tag; an [A]/[LF] resets it.
        self.assertEqual(bc._term_pad('hello[A][X]'), 'hello[A][X]')      # final run empty -> no pad

    def test_no_terminator_is_a_noop(self):
        self.assertEqual(bc._term_pad('odd'), 'odd')


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


class CharacterUniqueBanim(unittest.TestCase):
    """Per-character battle anims (#65 M-B): the scalable, no-class-slot path. A unit's
    AnimConf is appended to gUnitSpecificBanimConfigs[] and the character's _u25 indexes it;
    an engine hook swaps the combat lookup to GetBattleAnimationId_WithUnique."""

    CONFIGS = ('CONST_DATA struct BattleAnimDef * gUnitSpecificBanimConfigs[] = {\n'
               '    NULL,\n'
               '    AnimConf_Unused_LuciusUnpromoted,\n'
               '    AnimConf_Unused_LuciusPromoted,\n'
               '};\n')

    def test_knight_donor_maps_to_armor_knight_lance_cadence(self):
        # wolfram et al. ride CLASS_ARMOR_KNIGHT (display "Knight") with a lance and the
        # heavy armored thrust cadence (decomp banim_armm_sp1), not the Pirate axe.
        donor_class, wtype, motion, cadence = bc.BANIM_DONORS['knight']
        self.assertEqual(donor_class, 'CLASS_ARMOR_KNIGHT')
        self.assertIn('ITYPE_LANCE', wtype)
        self.assertEqual(motion, 'melee')
        self.assertEqual(cadence, 'lance')

    def test_every_melee_donor_names_a_known_cadence(self):
        from ref_to_battleframe import _MELEE_CADENCE
        for name, (_dc, _wt, motion, cadence) in bc.BANIM_DONORS.items():
            if motion == 'melee':
                self.assertIn(cadence, _MELEE_CADENCE, name)

    def test_unique_append_returns_next_index_and_appends_the_symbol(self):
        new, idx = bc.banim_unique_append(self.CONFIGS, 'AnimConf_brau_ax1')
        self.assertEqual(idx, 3)                       # NULL + 2 existing -> new is index 3
        self.assertIn('    AnimConf_brau_ax1,', new)
        self.assertLess(new.index('AnimConf_brau_ax1'), new.index('};'))  # before close

    def test_unique_append_leaves_existing_rows_unchanged(self):
        new, _ = bc.banim_unique_append(self.CONFIGS, 'AnimConf_brau_ax1')
        self.assertIn('    NULL,\n    AnimConf_Unused_LuciusUnpromoted,', new)

    CHAR = ('    [CHARACTER_EIRIKA - 1] = {\n'
            '        .nameTextId = 0x212,\n'
            '        .number = CHARACTER_EIRIKA,\n'
            '        .defaultClass = CLASS_PIRATE,\n'
            '    },\n')

    def test_set_char_u25_inserts_both_indices(self):
        new = bc.banim_set_char_u25(self.CHAR, 3)
        self.assertIn('._u25 = { 3, 3 },', new)
        self.assertIn('.number = CHARACTER_EIRIKA,', new)   # didn't clobber siblings

    def test_set_char_u25_is_idempotent_and_overwrites(self):
        once = bc.banim_set_char_u25(self.CHAR, 3)
        twice = bc.banim_set_char_u25(once, 7)
        self.assertIn('._u25 = { 7, 7 },', twice)
        self.assertEqual(twice.count('._u25'), 1)           # replaced, not duplicated

    def test_combat_anim_hook_swaps_all_calls_and_widens_out_param(self):
        from inject import engine_hooks as eh
        src = ('    u32 animid1, animid2;\n'
               '    a = GetBattleAnimationId(unit_bu1, animdef1, bu1->weapon, &animid1);\n'
               '    b = GetBattleAnimationId(unit_bu2, animdef2, bu2->weapon, &animid2);\n')
        out = eh._swap_combat_anim_to_unique(src)
        self.assertIn('int animid1, animid2;', out)
        self.assertNotIn('u32 animid1', out)
        self.assertEqual(out.count('GetBattleAnimationId_WithUnique(unit_bu'), 2)
        self.assertNotIn('GetBattleAnimationId(unit_bu', out)

    def test_combat_anim_hook_is_idempotent(self):
        from inject import engine_hooks as eh
        src = ('    u32 animid1, animid2;\n'
               '    a = GetBattleAnimationId(unit_bu1, animdef1, bu1->weapon, &animid1);\n')
        once = eh._swap_combat_anim_to_unique(src)
        self.assertEqual(eh._swap_combat_anim_to_unique(once), once)

    # GetBanimPalette: a CUSTOM (appended) banim must keep its OWN palette. Vanilla forces
    # CLASS_ARCHER/_F/SNIPER/_F to the canonical bow palette (0x25/0x27/0x29/0x2B) regardless
    # of banim_id -- right for the stock anim, but it mis-paints a custom-anim unit deployed
    # AS a real archer (the per-character _u25 path). That was the RBG "cyan" bug (#65).
    PALFN = ('int GetBanimPalette(int banim_id, enum ekr_battle_unit_position pos)\n'
             '{\n'
             '    u32 jid;\n'
             '    struct BattleUnit *bu;\n\n'
             '    if (EKR_POS_L == pos)\n'
             '        bu = gpEkrBattleUnitLeft;\n'
             '    else\n'
             '        bu = gpEkrBattleUnitRight;\n\n'
             '    jid = bu->unit.pClassData->number;\n'
             '    switch (jid) {\n'
             '    case CLASS_ARCHER:\n'
             '        return 0x25;\n'
             '    default:\n'
             '        return banim_id;\n'
             '    }\n'
             '}\n')

    def test_banim_palette_guard_short_circuits_custom_ids_before_the_switch(self):
        from inject import engine_hooks as eh
        out = eh._guard_banim_palette_custom(self.PALFN, 0xC9)
        # the guard returns banim_id for any appended id, BEFORE the class switch runs
        self.assertIn('if (banim_id >= 0xC9)', out)
        self.assertLess(out.index('if (banim_id >= 0xC9)'),
                        out.index('switch (jid)'))
        # vanilla switch body is left intact
        self.assertIn('case CLASS_ARCHER:\n        return 0x25;', out)

    def test_banim_palette_guard_is_idempotent(self):
        from inject import engine_hooks as eh
        once = eh._guard_banim_palette_custom(self.PALFN, 0xC9)
        self.assertEqual(eh._guard_banim_palette_custom(once, 0xC9), once)

    def test_banim_palette_guard_noops_when_form_unexpected(self):
        from inject import engine_hooks as eh
        self.assertEqual(eh._guard_banim_palette_custom('something else', 0xC9),
                         'something else')


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


class AppendedClassSlot(unittest.TestCase):
    """Extend gClassData past the vanilla 0x7F tail so an enemy reskin can ride a NEW
    class slot (#23: the Lizardzerker) once the three ballista-empties are used up. Two
    pure text transforms: insert the enum constant + append a cloned gClassData entry."""

    HEADER = ('enum {\n'
              '    CLASS_MERCENARY           = 0x05,\n'
              '    CLASS_JOURNEYMAN_T1       = 0x7E,\n'
              '    CLASS_PUPIL_T1            = 0x7F,\n'
              '\n'
              '    // Hiding the game\'s misery\n'
              '    CLASS_OBSTACLE = CLASS_EPHRAIM_LORD,\n'
              '};\n')

    CDATA = ('CONST_DATA struct ClassData gClassData[] = {\n'
             '    [CLASS_MERCENARY - 1] = {\n'
             '        .SMSId = 0x10,\n'
             '        .number = CLASS_MERCENARY,\n'
             '        .pMapSpriteAnim = &gUnknown_08X,\n'
             '    },\n'
             '    [CLASS_PUPIL_T1 - 1] = {\n'
             '        .SMSId = 0x11,\n'
             '        .number = CLASS_PUPIL_T1,\n'
             '    },\n'
             '};\n')

    def test_enum_insert_places_the_new_constant_after_the_last_numeric_class(self):
        new = bc.class_enum_insert(self.HEADER, 'CLASS_MNC_LIZARDZERKER', 0x80)
        self.assertIn('CLASS_MNC_LIZARDZERKER = 0x80,', new)
        # after the vanilla 0x7F tail, before the CLASS_OBSTACLE alias block
        self.assertLess(new.index('CLASS_PUPIL_T1'), new.index('CLASS_MNC_LIZARDZERKER'))
        self.assertLess(new.index('CLASS_MNC_LIZARDZERKER'), new.index('CLASS_OBSTACLE'))
        # parseable by the existing enum reader -> 0x80
        self.assertEqual(dict(re.findall(r'(CLASS_MNC_LIZARDZERKER)\s*=\s*(0x[0-9A-Fa-f]+)',
                                         new)).get('CLASS_MNC_LIZARDZERKER'), '0x80')

    def test_enum_insert_is_idempotent(self):
        once = bc.class_enum_insert(self.HEADER, 'CLASS_MNC_LIZARDZERKER', 0x80)
        twice = bc.class_enum_insert(once, 'CLASS_MNC_LIZARDZERKER', 0x80)
        self.assertEqual(once, twice)
        self.assertEqual(twice.count('CLASS_MNC_LIZARDZERKER = 0x80,'), 1)

    def test_classdata_append_clones_the_base_body_under_the_new_designator(self):
        new = bc.classdata_append_clone(self.CDATA, 'CLASS_MERCENARY', 'CLASS_MNC_LIZARDZERKER')
        self.assertIn('[CLASS_MNC_LIZARDZERKER - 1] = {', new)
        # the clone carries the base body verbatim (SMSId/anim ride along; the reskin loop
        # repoints .number/.SMSId afterward via the existing _set_field path)
        clone = new[new.index('[CLASS_MNC_LIZARDZERKER - 1]'):]
        self.assertIn('.SMSId = 0x10,', clone)
        self.assertIn('.pMapSpriteAnim = &gUnknown_08X,', clone)

    def test_classdata_append_leaves_the_base_entry_byte_unchanged(self):
        new = bc.classdata_append_clone(self.CDATA, 'CLASS_MERCENARY', 'CLASS_MNC_LIZARDZERKER')
        base = self.CDATA[self.CDATA.index('[CLASS_MERCENARY - 1]'):self.CDATA.index('[CLASS_PUPIL_T1 - 1]')]
        self.assertIn(base, new)                       # donor block untouched
        self.assertLess(new.index('[CLASS_MNC_LIZARDZERKER - 1]'), new.rindex('};'))  # inside the array

    def test_classdata_append_is_idempotent(self):
        once = bc.classdata_append_clone(self.CDATA, 'CLASS_MERCENARY', 'CLASS_MNC_LIZARDZERKER')
        twice = bc.classdata_append_clone(once, 'CLASS_MERCENARY', 'CLASS_MNC_LIZARDZERKER')
        self.assertEqual(once, twice)
        self.assertEqual(twice.count('[CLASS_MNC_LIZARDZERKER - 1] = {'), 1)


if __name__ == '__main__':
    unittest.main()
