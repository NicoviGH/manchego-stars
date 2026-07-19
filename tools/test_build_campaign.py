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

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_campaign as bc
from inject import engine_hooks as eh

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


class BattleAnimPalette(unittest.TestCase):
    def test_opaque_black_gets_a_nontransparent_palette_index(self):
        frame = Image.new('RGBA', (8, 8), (0, 0, 0, 255))
        palette = bc._banim_palette([frame])
        self.assertEqual(palette[0], (0, 0, 0))
        self.assertEqual(palette[1], (0, 0, 0))


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
        # ch03's blue field roster = cast_available_at(3); its PREP deploy tiles must cover it.
        field, _ = bc._classed_cast(self.CAMPAIGN, available_at=3)
        chap = bc._load_chapter_yaml(self.CAMPAIGN, bc.CH03_CHAPTER_YAML)
        self.assertGreaterEqual(len(chap['deployment']['deploy_slots']), len(field))

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


class Ch03PrepDeploy(unittest.TestCase):
    """Ch03 real PREP deploy (#23 item 3): the field roster picks in via Preparations,
    exactly like ch01/ch02 -- a never-LOADed deploy-cap template (UnitDef_Event_Ch4Ally)
    sized to cast_available_at(3), + a PREP CALL. These pin the YAML + cap builder the
    inject_ch03 beginning scene consumes."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return bc._load_chapter_yaml(self.CAMPAIGN, bc.CH03_CHAPTER_YAML)

    def test_deploy_slots_authored_and_sized_to_the_cap(self):
        """deploy_limit = vanilla FE8 Ch3's 9; deploy_slots is authored 1:1 with it (the
        schema _deploy_cap_entries enforces: len(slots) == deploy_limit)."""
        dep = self._chap()['deployment']
        self.assertEqual(dep['deploy_limit'], 9)
        self.assertEqual(len(dep['deploy_slots']), 9)
        for xy in dep['deploy_slots']:
            self.assertEqual(len(xy), 2)   # [col, row]

    def test_cap_covers_the_ch03_field_roster(self):
        """The cap fields the whole ch03 roster = cast_available_at(3) (8 founding + Baxby);
        Trex is EXCLUDED (he joins mid-map, green, via Talk -- like vanilla Colm)."""
        field, _ = bc._classed_cast(self.CAMPAIGN, available_at=3)
        self.assertEqual(self._chap()['deployment']['deploy_limit'], len(field))
        self.assertNotIn('trex', {u for u, *_ in field})

    def test_deploy_cap_entries_yields_one_row_per_slot(self):
        """_deploy_cap_entries (the shared ch01/ch02 builder) now succeeds for ch03: one
        never-LOADed ally row per deploy slot, tile coords from the YAML."""
        chap = self._chap()
        field, _ = bc._classed_cast(self.CAMPAIGN, available_at=3)
        leader = 'CHARACTER_%s' % field[0][1].upper()
        rows = bc._deploy_cap_entries(chap, field, leader, 'ch03')
        self.assertEqual(len(rows), chap['deployment']['deploy_limit'])
        for (x, y) in chap['deployment']['deploy_slots']:
            self.assertTrue(any('.xPosition = %d,' % x in r and '.yPosition = %d,' % y in r
                                for r in rows))


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

    def test_set_class_field_symbol_repoints_only_that_class(self):
        # The class-level enemy-anim path (#90): point a reskin clone's .pBattleAnimDef at a
        # new class-level AnimConf, leaving sibling classes' anim binding untouched.
        text = ('    [CLASS_A - 1] = {\n        .number = CLASS_A,\n'
                '        .pBattleAnimDef = AnimConf_old,\n    },\n'
                '    [CLASS_B - 1] = {\n        .pBattleAnimDef = AnimConf_keep,\n    },\n')
        new = bc.set_class_field_symbol(text, 'CLASS_A', 'pBattleAnimDef', 'AnimConf_new')
        self.assertIn('[CLASS_A - 1] = {\n        .number = CLASS_A,\n'
                      '        .pBattleAnimDef = AnimConf_new,', new)
        self.assertIn('.pBattleAnimDef = AnimConf_keep', new)   # CLASS_B untouched


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

    def test_shaman_donor_maps_to_dark_static_cast_cadence(self):
        # Meesmickle's vanilla Shaman donor retains Flux/Dark binding and its stationary
        # incantation; it is not an Archer bow draw with a recoloured projectile.
        donor_class, wtype, motion, cadence = bc.BANIM_DONORS['shaman']
        self.assertEqual(donor_class, 'CLASS_SHAMAN')
        self.assertIn('ITYPE_DARK', wtype)
        self.assertEqual(motion, 'magic')
        self.assertIsNone(cadence)

    def test_mage_donor_maps_to_anima_static_cast_cadence(self):
        # Rootis (frost snowman) rides his OWN class -- CLASS_MAGE, Anima -- not the shaman:
        # the private AnimConf must repoint the ITYPE_ANIMA slot so the custom anim binds to
        # the tome he actually wields. Same stationary magic cadence as the shaman donor.
        donor_class, wtype, motion, cadence = bc.BANIM_DONORS['mage']
        self.assertEqual(donor_class, 'CLASS_MAGE')
        self.assertIn('ITYPE_ANIMA', wtype)
        self.assertEqual(motion, 'magic')
        self.assertIsNone(cadence)

    def test_every_melee_donor_names_a_known_cadence(self):
        from ref_to_battleframe import _MELEE_CADENCE
        for name, (_dc, _wt, motion, cadence) in bc.BANIM_DONORS.items():
            if motion == 'melee':
                self.assertIn(cadence, _MELEE_CADENCE, name)

    def test_pegasus_donor_maps_to_pegasus_knight_lance(self):
        # Pinky (the flier) rides CLASS_PEGASUS_KNIGHT with a lance -- the donor supplies the
        # _u25 AnimConf to clone and the ITYPE_LANCE weapon slot to repoint at her IMPORTED
        # swoop. motion/cadence are unused on the import path (the motion.s comes from the
        # .txt) but stay valid so the melee-cadence invariant above holds.
        donor_class, wtype, motion, cadence = bc.BANIM_DONORS['pegasus']
        self.assertEqual(donor_class, 'CLASS_PEGASUS_KNIGHT')
        self.assertIn('ITYPE_LANCE', wtype)

    def test_bishop_donor_binds_staff_and_light_to_one_anim(self):
        donor_class, wtype, motion, cadence = bc.BANIM_DONORS['bishop']
        self.assertEqual(donor_class, 'CLASS_BISHOP')
        self.assertEqual(motion, 'magic')
        self.assertEqual(wtype, ['0x0100 | ITYPE_STAFF', '0x0100 | ITYPE_LIGHT'])
        # A Bishop-shaped AnimConf fixture: STAFF + LIGHT both at the vanilla index 0x82.
        src = ('CONST_DATA struct BattleAnimDef AnimConf_SRC[] = {\n'
               '    { .wtype = 0x0100 | ITYPE_STAFF, .index = 0x0082, },\n'
               '    { .wtype = 0x0100 | ITYPE_LIGHT, .index = 0x0082, },\n'
               '    { 0 }\n};\n')
        wtypes = wtype if isinstance(wtype, list) else [wtype]
        out = bc.banim_clone_conf(src, 'AnimConf_SRC', 'AnimConf_NEW', wtypes[0], 0x99 + 1)
        for wt in wtypes[1:]:
            out = bc.banim_repoint_conf(out, 'AnimConf_NEW', wt, 0x99 + 1)
        # Source table is left byte-vanilla (isolation).
        self.assertIn('AnimConf_SRC[] = {\n    { .wtype = 0x0100 | ITYPE_STAFF, .index = 0x0082, }', out)
        # New clone has BOTH slots repointed to 0x9A.
        new_block = out.split('AnimConf_NEW[] =', 1)[1]
        self.assertIn('.wtype = 0x0100 | ITYPE_STAFF, .index = 0x9A', new_block)
        self.assertIn('.wtype = 0x0100 | ITYPE_LIGHT, .index = 0x9A', new_block)

    def test_faked_battle_anim_builder_uses_the_three_pose_generator(self):
        # A block with `frames:` (no import) builds via ref_to_battleframe (the #65 faked path).
        from PIL import Image
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            for nm in ('r', 'w', 'p'):
                Image.new('RGBA', (24, 24), (200, 40, 40, 255)).save(
                    os.path.join(d, nm + '.png'))
            cfg = {'clone_from': 'knight',
                   'frames': ['r.png', 'w.png', 'p.png']}
            res = bc.build_unit_battle_anim(cfg, d, 'testu', 'melee', 'lance')
        self.assertEqual(len(res['sheets']), 3)          # faked = exactly 3 poses
        self.assertIn('banim_testu_script', res['motion_s'])

    def test_imported_battle_anim_builder_reads_txt_and_frames(self):
        # A block with `import:` builds via feditor_to_banim (the #90 N-frame path), bound
        # per-character. Exercised against Pinky's real committed swoop assets -- the ONLY new
        # seam vs the shipped enemy import (which binds per-CLASS).
        anim_dir = os.path.join(bc.REPO, 'campaigns', 'rime-of-the-frostmaiden',
                                'battle_anims', 'pinky')
        cfg = {'clone_from': 'pegasus',
               'import': {'txt': 'Pinky.txt', 'frames_dir': '.'}}
        res = bc.build_unit_battle_anim(cfg, anim_dir, 'pinky', 'melee', 'lance')
        self.assertEqual(len(res['sheets']), 7)          # six swoop frames + a dodge frame
        self.assertIn('banim_pinky_script', res['motion_s'])
        self.assertEqual(len(res['pal']), 128)           # same agbpal shape as the faked path

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


class BattleSpellPaletteTint(unittest.TestCase):
    """Per-character spell visuals remain data, not campaign-specific engine code."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_caster_tints_are_scoped_to_each_caster_and_weapon_type(self):
        # Marty's green tint covers all his Dark tomes; Rootis's blue (ice flavor) covers
        # all his Anima tomes. Each is character+weapon-type scoped -- no engine name-check.
        # Both still declare a single `weapon_type:` (not the list form) -- must keep working.
        self.assertTrue(hasattr(bc, 'battle_spell_palette_tints'))
        rows = bc.battle_spell_palette_tints(self.CAMPAIGN)
        self.assertIn(('CHARACTER_SETH', 'ITYPE_DARK', 'BANIM_SPELL_TINT_GREEN'), rows)
        self.assertIn(('CHARACTER_VANESSA', 'ITYPE_ANIMA', 'BANIM_SPELL_TINT_BLUE'), rows)

    def test_sclorbo_cyan_tint_covers_both_staff_and_light_via_weapon_types_list(self):
        # Sclorbo's spell_palette_tint declares `weapon_types: [staff, light]` (a list) --
        # one row per weapon type, both his DEDICATED flame cyan (bright equal G+B), NOT the
        # blue-dominant frost tint Rootis uses.
        rows = bc.battle_spell_palette_tints(self.CAMPAIGN)
        self.assertIn(('CHARACTER_ROSS', 'ITYPE_STAFF', 'BANIM_SPELL_TINT_CYAN'), rows)
        self.assertIn(('CHARACTER_ROSS', 'ITYPE_LIGHT', 'BANIM_SPELL_TINT_CYAN'), rows)

    def test_tint_rows_append_a_terminated_campaign_data_table(self):
        src = ('#include "constants/items.h"\n'
               'CONST_DATA struct BattleAnimDef * gUnitSpecificBanimConfigs[] = {\n'
               '    NULL,\n};\n')
        self.assertTrue(hasattr(bc, 'banim_spell_palette_tint_append'))
        out = bc.banim_spell_palette_tint_append(
            src, [('CHARACTER_SETH', 'ITYPE_DARK', 'BANIM_SPELL_TINT_GREEN')])
        self.assertIn('CONST_DATA struct BanimSpellPaletteTint gBanimSpellPaletteTints[]', out)
        self.assertIn('#include "constants/characters.h"', out)
        self.assertIn('{ CHARACTER_SETH, ITYPE_DARK, BANIM_SPELL_TINT_GREEN },', out)
        self.assertIn('{ 0, 0, BANIM_SPELL_TINT_NONE },', out)

    def test_engine_hook_records_the_tint_in_the_dedicated_global(self):
        src = ('void StartSpellAnimation(struct Anim *anim)\n'
               '{\n'
               '    s16 index = gEkrSpellAnimIndex[GetAnimPosition(anim)];\n'
               '}\n')
        self.assertTrue(hasattr(eh, '_spell_palette_tint_start'))
        out = eh._spell_palette_tint_start(src)
        self.assertIn('gMSSpellTint = GetBanimSpellPaletteTint(anim);', out)
        self.assertLess(out.index('s16 index'), out.index('gMSSpellTint'))

    def test_tint_rides_a_dedicated_overlay_global_leaving_the_lifecycle_flag_vanilla(self):
        """The tint rides its own EWRAM_OVERLAY(banim) global; gEfxSpellAnimExists stays vanilla."""
        patched = ('BANIM_EKRBATTLE_H', 'BANIM_EFXMAGIC_C', 'BANIM_EKRUTILS_C',
                   'BANIM_EKRBATTLE_C', 'BANIM_EKRDISPUP_C')
        before = {name: open(getattr(eh, name), encoding='utf-8').read() for name in patched}

        try:
            eh._patch_banim_spell_palette_tint()
            with open(eh.BANIM_EKRBATTLE_H, encoding='utf-8') as f:
                header = f.read()
            with open(eh.BANIM_EKRBATTLE_C, encoding='utf-8') as f:
                battle = f.read()
            with open(eh.BANIM_EKRUTILS_C, encoding='utf-8') as f:
                utils = f.read()
            with open(eh.BANIM_EKRDISPUP_C, encoding='utf-8') as f:
                dispup = f.read()
            # A dedicated global, declared beside the proven-writable lifecycle flag.
            self.assertIn('extern u8 gMSSpellTint;', header)
            self.assertIn('EWRAM_OVERLAY(banim) u8 gMSSpellTint = BANIM_SPELL_TINT_NONE;', battle)
            # The abandoned transient global is gone everywhere (the plural
            # gBanimSpellPaletteTints table is the legitimate data symbol).
            self.assertIsNone(re.search(r'gBanimSpellPaletteTint\b', header))
            self.assertIsNone(re.search(r'gBanimSpellPaletteTint\b', utils))
            # SpellFx_Begin's lifecycle flag is untouched (no tint guard smuggled in).
            begin = utils[utils.index('void SpellFx_Begin'):]
            begin = begin[:begin.index('void SpellFx_Finish')]
            self.assertIn('gEfxSpellAnimExists = true;', begin)
            self.assertNotIn('BANIM_SPELL_TINT', begin)
            # The palette copy reads the dedicated global, not the lifecycle flag, and
            # dispatches per tint id (NONE = passthrough, BLUE = ice recolor, CYAN = flame
            # cyan, else green).
            palette_copy = utils[utils.index('static void BanimSpellPaletteCopy'):]
            self.assertIn('if (gMSSpellTint == BANIM_SPELL_TINT_NONE)', palette_copy)
            self.assertIn('BANIM_SPELL_TINT_BLUE', palette_copy)
            self.assertIn('BANIM_SPELL_TINT_CYAN', palette_copy)
            self.assertNotIn('gEfxSpellAnimExists', palette_copy)
            # The dedicated flame-cyan tint function exists and pins BOTH green and blue high
            # (distinct from the blue-dominant BanimSpellTintBlue).
            self.assertIn('static u16 BanimSpellTintCyan(u16 color)', utils)
            self.assertIn('BANIM_SPELL_TINT_CYAN = 3,', header)
            # Teardown clears the tint beside the vanilla lifecycle reset.
            self.assertIn('gMSSpellTint = BANIM_SPELL_TINT_NONE;', dispup)
        finally:
            for name, text in before.items():
                with open(getattr(eh, name), 'w', encoding='utf-8') as f:
                    f.write(text)


class BattleChargeFlash(unittest.TestCase):
    """Per-caster charge flash (#183): the caster's own sprite pulses toward a signature
    colour on the wind-up beat. Colour + character binding stay data, not engine code."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_flash_rows_append_a_terminated_table_with_bgr555_targets(self):
        # The generated table carries the target colour as a raw BGR555 u16 so the engine
        # blends toward it directly -- no per-colour enum needed for any hue. Rows are
        # (character, weapon_type, target, waveform); 0 = pulse (the existing 3-throb LUT).
        src = ('#include "constants/items.h"\n'
               'CONST_DATA struct BattleAnimDef * gUnitSpecificBanimConfigs[] = {\n'
               '    NULL,\n};\n')
        self.assertTrue(hasattr(bc, 'banim_charge_flash_append'))
        out = bc.banim_charge_flash_append(
            src, [('CHARACTER_VANESSA', 'ITYPE_ANIMA', '0x7E6F', 0)])
        self.assertIn('CONST_DATA struct BanimChargeFlash gMSChargeFlashes[]', out)
        self.assertIn('#include "constants/characters.h"', out)
        self.assertIn('{ CHARACTER_VANESSA, ITYPE_ANIMA, 0x7E6F, 0 },', out)
        self.assertIn('{ 0, 0, 0, 0 },', out)   # zero-character terminator

    def test_flash_row_carries_the_build_waveform(self):
        # waveform=1 (build) rides the same row shape -- Sclorbo's slow single-swell glow.
        src = ('#include "constants/items.h"\n'
               'CONST_DATA struct BattleAnimDef * gUnitSpecificBanimConfigs[] = {\n'
               '    NULL,\n};\n')
        out = bc.banim_charge_flash_append(
            src, [('CHARACTER_ROSS', 'ITYPE_STAFF', '0x6F63', 1)])
        self.assertIn('{ CHARACTER_ROSS, ITYPE_STAFF, 0x6F63, 1 },', out)

    def test_named_colour_resolves_to_a_bgr555_hex_target(self):
        # 'blue' is Rootis's ice hue (120,205,255) -> 5-bit per channel, packed BGR555.
        self.assertTrue(hasattr(bc, 'charge_flash_target'))
        self.assertEqual(bc.charge_flash_target('blue'), '0x7F2F')

    def test_cyan_colour_resolves_to_sclorbos_flame_bgr555_target(self):
        # Sclorbo's confirmed flame cyan: RGB(31,219,219) -> BGR555 0x6F63.
        self.assertEqual(bc.charge_flash_target('cyan'), '0x6F63')

    def test_charge_flashes_are_scoped_per_caster_with_bgr555_colour(self):
        # Each caster's charge_flash: {color} -> one character+weapon-scoped row, the weapon
        # type derived from the donor (Rootis mage/anima; Marty & Meesmickle shaman/dark).
        # The three existing casters have no `waveform` in YAML -> default 0 (pulse), the
        # byte-identical existing LUT.
        self.assertTrue(hasattr(bc, 'battle_charge_flashes'))
        rows = bc.battle_charge_flashes(self.CAMPAIGN)
        self.assertIn(('CHARACTER_VANESSA', 'ITYPE_ANIMA', bc.charge_flash_target('blue'), 0), rows)
        self.assertIn(('CHARACTER_SETH', 'ITYPE_DARK', bc.charge_flash_target('green'), 0), rows)
        self.assertIn(('CHARACTER_GILLIAM', 'ITYPE_DARK', bc.charge_flash_target('purple'), 0), rows)

    def test_sclorbos_list_donor_emits_one_build_row_per_weapon_type(self):
        # Sclorbo's bishop donor's wtype is a LIST (['...ITYPE_STAFF', '...ITYPE_LIGHT']) --
        # the charge_flash must arm on BOTH the Heal staff and the post-promo Light tome,
        # each row carrying his cyan target + waveform=1 (build, a single slow swell).
        rows = bc.battle_charge_flashes(self.CAMPAIGN)
        cyan = bc.charge_flash_target('cyan')
        self.assertIn(('CHARACTER_ROSS', 'ITYPE_STAFF', cyan, 1), rows)
        self.assertIn(('CHARACTER_ROSS', 'ITYPE_LIGHT', cyan, 1), rows)

    def test_hook_arms_the_flash_from_the_existing_charge_command(self):
        """The pulse is armed by the elec-charge command ALREADY in the magic body (case 40),
        so the donor-matched animation script is never altered. Injects the lookup + proc."""
        self.assertTrue(hasattr(eh, '_patch_banim_charge_flash'))
        patched = ('BANIM_EKRBATTLE_H', 'BANIM_EFXMISC_C', 'BANIM_MAIN_C')
        before = {name: open(getattr(eh, name), encoding='utf-8').read() for name in patched}
        try:
            eh._patch_banim_charge_flash()
            header = open(eh.BANIM_EKRBATTLE_H, encoding='utf-8').read()
            efxmisc = open(eh.BANIM_EFXMISC_C, encoding='utf-8').read()
            main = open(eh.BANIM_MAIN_C, encoding='utf-8').read()
            # data contract: a per-character/weapon table of BGR555 targets + a waveform pick.
            self.assertIn('struct BanimChargeFlash', header)
            self.assertIn('gMSChargeFlashes[]', header)
            self.assertIn('u8 waveform;', header)
            # the arm reads the CURRENT attacker (character + weapon), like the spell tint.
            self.assertIn('void MSChargeFlashArm(struct Anim *anim)', efxmisc)
            self.assertIn('GetItemType(bu->weaponBefore)', efxmisc)
            # two LUTs: the vanilla 3-throb pulse (byte-identical) and a new single-swell build.
            self.assertIn('static const u8 sMSChargeFlashSine[55] = { 0, 1, 3, 6, 10, 13, 17, '
                          '20, 22, 23, 22, 20, 17, 13, 10, 6, 3, 1, 0, 1, 3, 6, 10, 13, 17, 20, '
                          '22, 23, 22, 20, 17, 13, 10, 6, 3, 1, 0, 1, 3, 6, 10, 13, 17, 20, 22, '
                          '23, 22, 20, 17, 13, 10, 6, 3, 1, 0 };', efxmisc)
            self.assertIn('static const u8 sMSChargeFlashBuild[55]', efxmisc)
            # proc + arm pick the LUT per-row via a waveform field.
            self.assertIn('proc->waveform', efxmisc)
            self.assertIn('it->waveform', efxmisc)
            self.assertIn('proc->waveform ? sMSChargeFlashBuild[proc->timer] : '
                          'sMSChargeFlashSine[proc->timer]', efxmisc)
            # armed from the existing start-attack command (case 0x07) -- no motion.s change,
            # and ~one settle beat before the wind-up arm-raise.
            self.assertIn('MSChargeFlashArm(anim)', main)
            self.assertIn('case 0x07:', main)
        finally:
            for name, text in before.items():
                with open(getattr(eh, name), 'w', encoding='utf-8') as f:
                    f.write(text)


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


class Ch03MidmapExecution(unittest.TestCase):
    """Ch03 midmap RBG-execution beat (#23 item 1): the Icewind Brute is a mid-map miniboss
    whose DEFEAT fires a flagged death cutscene (RBG guns down the beaten Brute) -- the mirror
    of the grell's DefeatBoss WIN, but keyed to a tmp flag + a Misc AFEV instead of the win
    flag. These pin the pure builders inject_ch03 consumes."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return bc._load_chapter_yaml(self.CAMPAIGN, bc.CH03_CHAPTER_YAML)

    def test_exactly_one_miniboss_and_it_is_the_brute(self):
        """The RBG-execution trigger = the one enemy flagged `is_miniboss` (the Icewind Brute)."""
        mbs = bc.midmap_minibosses(self._chap())
        self.assertEqual([e['id'] for e in mbs], ['kobold-steel'])

    def test_miniboss_pid_is_a_clean_sibling_distinct_from_boss_and_generic(self):
        """A unique raw pid so the Brute's flagged death quote keys the trigger to it ALONE --
        not the shared generic 0xaa (all trash) and not the grell's 0xb7 (the WIN)."""
        self.assertNotIn(bc.CH03_BRUTE_MINIBOSS_PID,
                         (bc.CH03_GENERIC_PID, bc.CH03_BOSS_PID))

    def test_afev_fires_once_on_the_brute_flag(self):
        """The Misc AFEV watches the Brute-defeat flag, runs the midmap script, and guards the
        one-shot with a distinct ent-flag (set after firing) -- else it re-fires every turn."""
        line = bc.midmap_afev(bc.CH03_MIDMAP_GUARD_FLAG, bc.CH03_MIDMAP_SCRIPT,
                              bc.CH03_BRUTE_DEFEAT_FLAG)
        self.assertEqual(line, 'AFEV(%s, %s, %s)' % (bc.CH03_MIDMAP_GUARD_FLAG,
                                                     bc.CH03_MIDMAP_SCRIPT,
                                                     bc.CH03_BRUTE_DEFEAT_FLAG))
        self.assertNotEqual(bc.CH03_MIDMAP_GUARD_FLAG, bc.CH03_BRUTE_DEFEAT_FLAG)

    def test_ch03_tmp_flags_are_all_distinct(self):
        """tmp flags are chapter-local; the midmap's two must not collide with Trex's talk flag."""
        flags = {bc.CH03_TREX_TALK_FLAG, bc.CH03_BRUTE_DEFEAT_FLAG, bc.CH03_MIDMAP_GUARD_FLAG}
        self.assertEqual(len(flags), 3)

    def test_silent_defeat_quote_sets_the_flag_without_a_portrait(self):
        """flag_defeat_quote = a msg=0 gDefeatTalkList entry: SetPidDefeatedFlag still sets the
        flag on death (no CA_BOSS gate), but the faceless quote is suppressed (the cutscene is
        the separate AFEV script). Shared by the grell WIN and the Brute midmap trigger."""
        q = bc.flag_defeat_quote(bc.CH03_BRUTE_MINIBOSS_PID, 'CHAPTER_L_4',
                                 bc.CH03_BRUTE_DEFEAT_FLAG, 'brute')
        self.assertIn('.pid     = %s' % bc.CH03_BRUTE_MINIBOSS_PID, q)
        self.assertIn('.chapter = CHAPTER_L_4', q)
        self.assertIn('.flag    = %s' % bc.CH03_BRUTE_DEFEAT_FLAG, q)
        self.assertIn('.msg     = 0', q)

    def test_midmap_yaml_splits_into_the_seven_restaged_beats(self):
        """The restaged midmap `script:` splits into 7 beats matching the reserved msg-id block:
        A Pinky / A2 ACTION attack / A3 Brute snarl / B RBG "Say cheese" / B2 ACTION shot /
        B3 Pinky+RBG / C Wolfram. A beat_break drift would desync the zip (guarded by _split_event_beats)."""
        self.assertEqual(len(bc.CH03_MIDMAP_MSGS), 7)
        _card, beats = bc._split_event_beats(self._chap(), 'midmap', 'ch03 midmap',
                                             bc.CH03_MIDMAP_MSGS, card_required=False)
        self.assertEqual(len(beats), 7)

    def test_midmap_action_boxes_faceless_dialogue_beats_faced(self):
        """Routing by face: the two ACTION narration beats (A2 the attack, B2 the shot) are faceless ->
        the opaque auto-centered box; the five dialogue beats (Pinky / Brute / RBG / Pinky+RBG / Wolfram)
        resolve to faces -> map talk bubbles. The Brute is faced via its Caellach mug (fallback)."""
        self.assertEqual(bc.GUEST_PORTRAIT_MAP.get('kobold-brute'), 'Caellach')
        _card, beats = bc._split_event_beats(self._chap(), 'midmap', 'ch03 midmap',
                                             bc.CH03_MIDMAP_MSGS, card_required=False)
        fid = bc._make_fid({'narration': None, 'boy-crier': '[FID_x]'}, 'ch03 midmap test',
                           fallback=bc.GUEST_PORTRAIT_MAP)
        self.assertEqual([bc._beat_is_faceless(b, fid) for b in beats],
                         [False, True, False, False, True, False, False])

    def test_beat_is_faceless_detects_a_mugless_speaker(self):
        """The routing mechanism: without the Brute's mug, its snarl beat (A3) also flags faceless ->
        it would ride the opaque box (the fallback for any future mugless NPC), alongside the two
        genuine narration action boxes."""
        _card, beats = bc._split_event_beats(self._chap(), 'midmap', 'ch03 midmap',
                                             bc.CH03_MIDMAP_MSGS, card_required=False)
        mugless = bc._make_fid({'narration': None, 'kobold-brute': None}, 'ch03 midmap test')
        self.assertEqual([bc._beat_is_faceless(b, mugless) for b in beats],
                         [False, True, True, False, True, False, False])   # A3 (Brute) faceless w/o a mug


class Ch03TileChanges(unittest.TestCase):
    """The ch03 chest + door tile-changes (#23): one MapChange array flips each chest's
    FF5 navy tile 17->29 on loot and opens each door to the floor tile DIRECTLY BELOW it
    (Nicolas 2026-07-11 -- 'use the tile directly adjacent and below it'). GetMapChangeIdAt
    matches by POSITION, so chests + doors coexist in one array; ids just stay unique."""
    CAMPAIGN = 'rime-of-the-frostmaiden'
    STEM = bc.CH03_LAYOUT[1]
    MAPS = os.path.join(bc.REPO, 'campaigns', 'rime-of-the-frostmaiden', 'maps')

    def test_reads_the_painted_metatile_at_a_cell(self):
        # The retile paints the FF5 navy chest (metatile 17) at (6,3); the .mar stores
        # metatile<<5, so the reader must decode 17 back out.
        self.assertEqual(bc._read_map_metatile(self.MAPS, self.STEM, 6, 3), 17)

    def test_door_open_tile_is_the_metatile_directly_below(self):
        # Vanilla Ch3 doors sit at (6,10)/(10,5)/(2,3); the open tile = the cell one row down
        # on the COMMITTED (hand-painted) map -- road tiles (572/492) + the stairs down (626),
        # all passable, so the opened door lets the party through.
        below = [bc._read_map_metatile(self.MAPS, self.STEM, x, y + 1)
                 for (x, y) in [(6, 10), (10, 5), (2, 3)]]
        self.assertEqual(below, [572, 626, 492])

    def test_asm_emits_one_change_per_chest_then_per_door_with_unique_ids(self):
        asm = bc._ch03_tile_changes_asm([(6, 3), (8, 3)], [(6, 10, 98), (2, 3, 66)])
        ids = [int(l.split(',')[0].split()[1]) for l in asm.splitlines()
               if l.strip().startswith('.byte') and 'terminator' not in l]
        self.assertEqual(ids, [0, 1, 2, 3])   # 2 chests then 2 doors, contiguous + unique
        self.assertIn('.byte -1', asm)        # id<0 terminator closes the array

    def test_asm_chests_share_the_open_chest_tile_word(self):
        asm = bc._ch03_tile_changes_asm([(6, 3), (8, 3)], [])
        self.assertEqual(asm.count('.word MS_Ch03ChestOpenTile'), 2)
        self.assertIn('.hword %d' % (bc.CH03_CHEST_OPEN_TILE << 2), asm)

    def test_asm_each_door_gets_its_own_below_tile_word(self):
        asm = bc._ch03_tile_changes_asm([], [(6, 10, 98), (10, 5, 302)])
        self.assertIn('.word MS_Ch03DoorOpenTile_0', asm)
        self.assertIn('.word MS_Ch03DoorOpenTile_1', asm)
        self.assertIn('.hword %d' % (98 << 2), asm)     # open metatile stored as metatile<<2
        self.assertIn('.hword %d' % (302 << 2), asm)

    def test_asm_carries_the_door_cell_coords(self):
        asm = bc._ch03_tile_changes_asm([], [(6, 10, 98)])
        self.assertIn('.byte 0, 6, 10, 1, 1, 0, 0, 0', asm)   # id 0 at (x=6, y=10), 1x1 region


class ItemIconPal2(unittest.TestCase):
    """Custom-coloured icons append a third source palette and draw from reserved BG bank 15.

    The two vanilla banks are shared UI state and must never be repainted; text can use bank 5.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_bgr555_packs_5bit_channels(self):
        self.assertEqual(bc._bgr555('#000000'), 0)
        self.assertEqual(bc._bgr555('#ffffff'), 0x7FFF)          # 31|31<<5|31<<10
        self.assertEqual(bc._bgr555('#ff0000'), 0x001F)          # red in low 5 bits
        self.assertEqual(bc._bgr555('#0000ff'), 0x7C00)          # blue in high 5 bits

    def test_pal2_palette_is_16_bgr555_entries(self):
        colors = ['#000000'] * 16
        b = bc._item_icon_pal2_bytes(colors)
        self.assertEqual(len(b), 32)                             # 16 colors x 2 bytes
        self.assertEqual(b, b'\x00' * 32)

    def test_pal2_palette_rejects_wrong_length(self):
        with self.assertRaises(SystemExit):
            bc._item_icon_pal2_bytes(['#000000'] * 15)

    def test_pal2_appends_third_bank_without_repainting_vanilla_banks(self):
        vanilla = bytearray(range(64))
        out = bc._append_item_icon_pal2(vanilla, ['#000000'] * 16)
        self.assertEqual(out[:64], vanilla)
        self.assertEqual(out[64:], b'\x00' * 32)

    def test_redgem_resolves_to_pal2_icon_id_136(self):
        # ITEM_REDGEM (the Tourmaline) is the campaign's one custom-palette icon; its iconId is 136.
        self.assertEqual(bc._pal2_icon_ids(self.CAMPAIGN), [136])

    def test_iconids_asm_lists_ids_then_terminator(self):
        asm = bc._ms_pal2_iconids_asm([136, 5])
        self.assertIn('.global gMSPal2IconIds', asm)
        self.assertIn('.hword 136', asm)
        self.assertIn('.hword 5', asm)
        self.assertIn('.hword 0xFFFF', asm)                     # terminator (no valid iconId is 0xFFFF)

    def test_hook_loads_custom_bank_fifteen_without_changing_vanilla_load(self):
        source = ('#include "hardware.h"\n\n'
                  'void LoadIconPalettes(u32 Dest)\n'
                  '{\n'
                  '    ApplyPalettes(item_icon_palette[0], Dest, 2);\n'
                  '}\n\n'
                  'void DrawIcon(int IconIndex, int TileX, int TileY, int TILEREF)\n'
                  '{\n'
                  '    if (TILEREF == 0xFFFF) {\n'
                  '    } else {\n'
                  '        u16 Tile = GetIconTileIndex(IconIndex) + OamPalBase;\n'
                  '    }\n'
                  '}\n')
        out = eh._patch_draw_icon_pal2_text(source)
        self.assertIn('ApplyPalettes(item_icon_palette[0], Dest, 2);', out)
        self.assertNotIn('ApplyPalette(item_icon_palette[2], 15);\n}', out)
        self.assertIn('gMSPal2IconIds', out)
        self.assertIn('(OamPalBase & 0xF000) == 0x4000', out)
        self.assertIn('ApplyPalette(item_icon_palette[2], 15);', out)
        self.assertIn('OamPalBase = (OamPalBase & 0x0FFF) | 0xF000;', out)


if __name__ == '__main__':
    unittest.main()
