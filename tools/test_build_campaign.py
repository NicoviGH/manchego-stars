#!/usr/bin/env python3
"""Tests for tools/build_campaign.py stat-resolution helpers.

These pin the donor-inheritance primitives the difficulty engine and the character
patcher share, against real vanilla values read from fireemblem8u/src/data_characters.c.
Run:  python3 tools/test_build_campaign.py
"""
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

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
        # member (11 now: 8 founding + Baxby + Trex + Lupin); both would sys.exit otherwise.
        self.assertIn('CLASS_THIEF', bc.CLASS_LOADOUT)
        allcast, _ = bc._classed_cast(self.CAMPAIGN)   # available_at=None -> everyone
        self.assertEqual(len(allcast), 11)
        self.assertGreaterEqual(len(bc.TEST_SPAWN_POSITIONS), len(allcast))
        # ch03's blue field roster = cast_available_at(3); its PREP deploy tiles must cover it.
        field, _ = bc._classed_cast(self.CAMPAIGN, available_at=3)
        chap = bc._load_chapter_yaml(self.CAMPAIGN, bc.CH03_CHAPTER_YAML)
        self.assertGreaterEqual(len(chap['deployment']['deploy_slots']), len(field))

    def test_trex_has_a_death_quote_and_a_dead_slot2_msg_id(self):
        self.assertIn('trex', bc.PC_DEATH_QUOTE_MSGS)
        unit = bc.load_unit(self.CAMPAIGN, 'trex')
        self.assertTrue(unit.get('death_quote'))

    def test_every_classed_cast_member_has_a_death_quote(self):
        # #6 requires a msg id + a quote line per deployable cast member; inject_pc_death_quotes
        # sys.exits otherwise (a build break). This guards every recruit, incl. future ch05 ones.
        for uid, _slot, _cls, _sms in bc.classed_cast(self.CAMPAIGN):
            self.assertIn(uid, bc.PC_DEATH_QUOTE_MSGS, '%s needs a death-quote msg id' % uid)
            self.assertTrue(bc.load_unit(self.CAMPAIGN, uid).get('death_quote'),
                            '%s needs a death_quote line' % uid)


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


class SharedTalkRecruitWiring(unittest.TestCase):
    """The faction-parameterized on-map talk-recruit assembly reused by ch03 (green Trex),
    ch04 (red Lupin), and ch05 (green Basil + red Sahnar). ONE flow: a CHAR-per-recruiter
    list -> a shared talk script whose CUSA flips the target BLUE. A group parley splices a
    `pre_script` (its conversion sweep) in BEFORE the CUSA, so it rides the same recruit path."""

    def test_talk_script_splices_pre_script_before_cusa(self):
        s = bc.talk_recruit_script(0x9BA, 'CHARACTER_DUESSEL', pre_script='    DISA(0xb3)\n')
        self.assertGreater(s.index('DISA(0xb3)'), s.index('TEXTSHOW(0x9BA)'))  # after the talk line
        self.assertLess(s.index('DISA(0xb3)'), s.index('CUSA(CHARACTER_DUESSEL)'))  # before the join

    def test_talk_script_without_pre_script_is_backward_compatible(self):
        # ch03's green recruit passes no pre_script -- the script stays exactly as before.
        s = bc.talk_recruit_script(0x9A5, 'CHARACTER_RENNAC')
        self.assertNotIn('DISA', s)
        self.assertIn('CUSA(CHARACTER_RENNAC)', s)

    def test_wiring_bundles_the_char_list_and_the_talk_script(self):
        char_events, script = bc.talk_recruit_wiring(
            ['CHARACTER_SETH'], 'CHARACTER_DUESSEL', 'EVFLAG_TMP(9)',
            'EventScr_089F2340', 0x9BA, pre_script='    DISA(0xb3)\n')
        self.assertEqual(char_events.count('CHAR('), 1)
        self.assertIn('CHAR(EVFLAG_TMP(9), EventScr_089F2340, CHARACTER_SETH, '
                      'CHARACTER_DUESSEL)', char_events)
        self.assertTrue(char_events.rstrip().endswith('END_MAIN\n}'))
        self.assertIn('CUSA(CHARACTER_DUESSEL)', script)
        self.assertIn('DISA(0xb3)', script)


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

    # The SECOND palette path, and the one that cost a session (#206, Baxby). FE8 also carries
    # a per-CHARACTER battle palette keyed on character x CLASS (gAnimCharaPalConfig), applied
    # AFTER the anim's own palette is loaded -- so it silently overwrites it. A cast member on
    # a vanilla slot whose character had a personal palette for that same class gets repainted:
    # Baxby wears FORDE, whose row is [CLASS_CAVALIER -> 0x57], and Baxby IS a Cavalier, so his
    # custom axe-beak palette was clobbered by Forde's green. Lupin escaped only by luck --
    # Duessel's personal palettes are all magic classes.
    UNIQPALFN = ('    pid = unit_bu1->pCharacterData->number - 1;\n'
                 '    jid = unit_bu1->pClassData->number;\n\n'
                 '    if (valid_l)\n'
                 '        gBanimUniquePal[POS_L] = -1;\n\n'
                 '    for (i = 0; i < 7; i++)\n'
                 '    {\n'
                 '        if (gAnimCharaPalConfig[pid][i] == jid && valid_l)\n'
                 '        {\n'
                 '            gBanimUniquePal[POS_L] = gAnimCharaPalIt[pid][i] - 1;\n'
                 '            break;\n'
                 '        }\n'
                 '    }\n\n'
                 '    pid = unit_bu2->pCharacterData->number - 1;\n'
                 '    jid = unit_bu2->pClassData->number;\n\n'
                 '    if (valid_r)\n'
                 '        gBanimUniquePal[POS_R] = -1;\n\n'
                 '    for (i = 0; i < 7; i++)\n'
                 '    {\n'
                 '        if (gAnimCharaPalConfig[pid][i] == jid && valid_r)\n'
                 '        {\n'
                 '            gBanimUniquePal[POS_R] = gAnimCharaPalIt[pid][i] - 1;\n'
                 '            break;\n'
                 '        }\n'
                 '    }\n')

    def test_unique_pal_guard_suppresses_the_character_palette_on_both_sides(self):
        """A custom (appended) banim keeps its own palette wherever it is standing."""
        from inject import engine_hooks as eh
        out = eh._guard_banim_unique_pal_custom(self.UNIQPALFN, 0xC9)
        self.assertIn('gAnimCharaPalConfig[pid][i] == jid && valid_l '
                      '&& gBanimIdx[POS_L] < 0xC9', out)
        self.assertIn('gAnimCharaPalConfig[pid][i] == jid && valid_r '
                      '&& gBanimIdx[POS_R] < 0xC9', out)

    def test_unique_pal_guard_leaves_vanilla_units_alone(self):
        """A stock banim id is BELOW the threshold, so vanilla's character palette still
        applies -- Seth keeps his personal Paladin colours."""
        from inject import engine_hooks as eh
        out = eh._guard_banim_unique_pal_custom(self.UNIQPALFN, 0xC9)
        self.assertIn('gBanimUniquePal[POS_L] = gAnimCharaPalIt[pid][i] - 1;', out)
        self.assertIn('gBanimUniquePal[POS_R] = gAnimCharaPalIt[pid][i] - 1;', out)

    def test_unique_pal_guard_is_idempotent(self):
        from inject import engine_hooks as eh
        once = eh._guard_banim_unique_pal_custom(self.UNIQPALFN, 0xC9)
        self.assertEqual(eh._guard_banim_unique_pal_custom(once, 0xC9), once)

    def test_unique_pal_guard_noops_when_form_unexpected(self):
        from inject import engine_hooks as eh
        self.assertEqual(eh._guard_banim_unique_pal_custom('something else', 0xC9),
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

    def _asm(self, chests, doors):
        """ch03's own change list, through the shared emitter (#214 generalised it out of a
        ch03-only helper). chests -> the FF5 open-chest tile; doors -> their below-cell floor."""
        changes = [(x, y, 1, 1, [bc.CH03_CHEST_OPEN_TILE], 'chest') for x, y in chests]
        changes += [(x, y, 1, 1, [tile], 'door') for x, y, tile in doors]
        return bc.map_changes_asm('MS_Ch03MapChanges', changes)

    def test_asm_emits_one_change_per_chest_then_per_door_with_unique_ids(self):
        asm = self._asm([(6, 3), (8, 3)], [(6, 10, 98), (2, 3, 66)])
        ids = [int(l.split(',')[0].split()[1]) for l in asm.splitlines()
               if l.strip().startswith('.byte') and 'terminator' not in l]
        self.assertEqual(ids, [0, 1, 2, 3])   # 2 chests then 2 doors, contiguous + unique
        self.assertIn('.byte -1', asm)        # id<0 terminator closes the array

    def test_asm_chests_carry_the_open_chest_tile(self):
        asm = self._asm([(6, 3), (8, 3)], [])
        self.assertEqual(asm.count('.hword %d' % (bc.CH03_CHEST_OPEN_TILE << 2)), 2)

    def test_asm_each_door_gets_its_own_below_tile_word(self):
        asm = self._asm([], [(6, 10, 98), (10, 5, 302)])
        self.assertIn('.hword %d' % (98 << 2), asm)     # open metatile stored as metatile<<2
        self.assertIn('.hword %d' % (302 << 2), asm)
        self.assertEqual(asm.count('MS_Ch03MapChanges_tiles_'), 4)   # 2 defs + 2 refs

    def test_asm_carries_the_door_cell_coords(self):
        asm = self._asm([], [(6, 10, 98)])
        self.assertIn('.byte 0, 6, 10, 1, 1, 0, 0, 0', asm)   # id 0 at (x=6, y=10), 1x1 region

    def test_a_region_whose_tile_count_disagrees_with_its_size_is_rejected(self):
        """The failure mode this guards: a 1x3 snag region carrying one tile writes garbage
        into gBmMapBaseTiles for the other two cells."""
        with self.assertRaises(SystemExit):
            bc.map_changes_asm('MS_X', [(4, 8, 1, 3, [6], 'short')])


class Ch04RuntimeHost(unittest.TestCase):
    """Ch04's first playable host: approved 23-unit vanilla-monster roster, snowy map,
    fog, prep cap, and turn-based reinforcement split. D&D identities stay narrative
    grounding; the player-facing unit names remain the vanilla FE8 monster names."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return bc._load_chapter_yaml(self.CAMPAIGN, bc.CH04_CHAPTER_YAML)

    def test_every_ch04_decomp_output_is_restored_before_reinjection(self):
        self.assertTrue({
            'src/events/ch5-eventinfo.h',
            'src/events/ch5-eventscript.h',
            'graphics/chap_title/chap_title_5.png',
        }.issubset(set(bc.PATCHED_DECOMP_FILES)))

    def test_lupin_is_a_red_on_map_talk_recruit(self):
        # ch04's parley recruit (Joshua-style red->blue). The recruit path is faction-
        # parameterized and reused: Trex/Basil start GREEN, Lupin/Sahnar start RED. Lupin
        # rides a collision-free identity slot (his stat donor stays Kyle).
        recruits = bc.on_map_talk_recruits(self.CAMPAIGN, self._chap()['chapter_number'])
        lupin = [r for r in recruits if r[0] == 'lupin']
        self.assertEqual(len(lupin), 1, "Lupin should be ch04's on-map talk recruit")
        self.assertEqual(lupin[0][1], 'Duessel')
        self.assertEqual(
            bc.recruit_initial_faction(bc.load_unit(self.CAMPAIGN, 'lupin')), 'RED')

    def test_recruit_initial_faction_defaults_green(self):
        # Trex (and future Basil) are the green->blue path; RED is opt-in via recruit.initial_faction.
        self.assertEqual(
            bc.recruit_initial_faction(bc.load_unit(self.CAMPAIGN, 'trex')), 'GREEN')

    def test_host_and_deployment_match_the_approved_ch04_shape(self):
        chap = self._chap()
        self.assertEqual(bc.CH04_HOST_INDEX, 5)
        self.assertEqual(bc.CH04_GOAL_DONOR, bc.CH02_HOST_INDEX)
        self.assertEqual(chap['deployment']['deploy_limit'], 9)
        self.assertEqual(len(chap['deployment']['deploy_slots']), 9)
        cast, _ = bc._classed_cast(self.CAMPAIGN, available_at=4)
        self.assertEqual(len(cast), 10)  # pick 9; Trex has joined after ch03

    def test_player_facing_enemy_names_stay_vanilla(self):
        chap = self._chap()
        self.assertEqual({e['name'] for e in chap['enemy_units']},
                         {'Mauthe Doog', 'Revenant', 'Bonewalker', 'Mogall', 'Entombed'})
        self.assertEqual([e['name'] for e in chap['enemy_units']],
                         [e['fe_name'] for e in chap['enemy_units']])

    def test_roster_splits_10_line_6_turn2_reveal_7_turn3(self):
        # Realigned 2026-07-21 to the vanilla-Ch4 twin: 10 monsters-only line, the turn-2
        # wolf-pack reveal (6), and two turn-3 reinforcement packs (revenant 4 + bonewalker 3).
        chap = self._chap()
        self.assertEqual(len(bc.ch04_enemy_rows(chap)), 10)
        self.assertEqual(len(bc.ch04_enemy_rows(chap, arrives_turn=2)), 6)
        self.assertEqual(len(bc.ch04_enemy_rows(chap, arrives_turn=3)), 7)

    # -- Stage 2b: the turn-2 wolf-pack reveal + the Marty->Lupin parley (in-place) ---------
    def _lupin(self):
        return next(r for r in bc.on_map_talk_recruits(self.CAMPAIGN, 4) if r[0] == 'lupin')

    def _reveal_positions(self):
        return bc._ch04_reveal_wave(self._chap())['positions']

    def test_turn2_reveal_is_five_generic_wolves_plus_lupin_red_leader(self):
        # The pack leader tile becomes Lupin (red, CHARACTER_DUESSEL, Cavalier under the hood);
        # the other 5 stay generic Mauthe Doogs. 5 + Lupin = 6 -> holds the turn-2 parity count.
        rows = bc.ch04_turn2_reveal_rows(self._chap(), self._lupin())
        joined = '\n'.join(rows)
        self.assertEqual(len(rows), 6)
        self.assertEqual(joined.count('CLASS_MAUTHEDOOG'), 5)
        self.assertEqual(joined.count('CHARACTER_DUESSEL'), 1)
        self.assertIn('CLASS_CAVALIER', joined)
        self.assertEqual(joined.count('FACTION_ID_RED'), 6)   # all hostile until the parley
        lx, ly = self._reveal_positions()[0]                  # Lupin sits on the leader tile
        self.assertIn('.charIndex = CHARACTER_DUESSEL,', joined)
        self.assertRegex(joined, r'CHARACTER_DUESSEL,[^{]*?\.xPosition = %d,' % lx)

    def test_turn2_reveal_holds_the_difficulty_parity_count(self):
        # The YAML wave stays 6 for the difficulty read (make difficulty CH=ch04); the
        # 5-generics-plus-Lupin split is injector-side only, so parity is unchanged.
        self.assertEqual(len(bc.ch04_enemy_rows(self._chap(), arrives_turn=2)), 6)
        self.assertEqual(len(bc.ch04_turn2_reveal_rows(self._chap(), self._lupin())), 6)

    def test_each_generic_wolf_gets_its_own_pid(self):
        # CUSN and CHECK_ALIVE both resolve a pid through GetUnitFromCharId, which returns the
        # FIRST match scanning blue->green->red. Five wolves sharing one pid can therefore only
        # ever be converted ONCE (the second CUSN re-finds the wolf it just turned green), which
        # is why the parley had to reload a table instead. One pid each makes them addressable.
        rows = bc.ch04_turn2_reveal_rows(self._chap(), self._lupin())
        pids = re.findall(r'\.charIndex = (\w+),', '\n'.join(rows))
        self.assertEqual(len(pids), 6)
        self.assertEqual(len(set(pids)), 6, 'every wolf needs its own pid: %s' % pids)
        self.assertEqual([p for p in pids if p != 'CHARACTER_DUESSEL'],
                         list(bc.CH04_PACK_PIDS))

    def test_the_pack_pids_are_interchangeable_generic_monster_slots(self):
        # Splitting the shared pid must not change what the wolves ARE. Each new pid is a
        # vanilla generic-monster character entry carrying the same generic name text id and
        # the same (zeroed) personal bases as the doog slot the pack used to share; the wolf's
        # CLASS comes from the unit definition, not the character entry (bmunit.c:697).
        def entry(pid):
            m = re.search(r'\[%s - 1\] = \{(.*?)\n    \},' % pid, VANILLA, re.S)
            self.assertIsNotNone(m, 'no vanilla character entry for %s' % pid)
            return dict(re.findall(r'\.(\w+)\s*=\s*(\w+),', m.group(1)))
        doog = entry('0xb3')
        self.assertEqual(doog['nameTextId'], '0x255')       # the generic-monster name slot
        for pid in bc.CH04_PACK_PIDS:
            e = entry(pid)
            self.assertEqual(e['number'], pid)              # the slot is itself, not an alias
            for field in [f for f in doog if f not in ('number', 'defaultClass')]:
                self.assertEqual(e[field], doog[field],
                                 '%s.%s differs from the doog slot' % (pid, field))

    def test_lycanroc_pack_reskin_is_declared_and_clones_the_doog(self):
        rk = [r for r in bc.enemy_class_reskins(self.CAMPAIGN) if r['id'] == 'lycanroc-pack']
        self.assertEqual(len(rk), 1, 'campaign.yaml must declare the lycanroc-pack reskin')
        rk = rk[0]
        self.assertEqual(rk['base'], 'CLASS_MAUTHEDOOG')     # stats/anim ride along -> parity
        self.assertEqual(rk['slot'], bc.CH04_GREEN_PACK_CLASS)
        self.assertEqual(str(rk['frame']), '32x32')          # 32x32 quadruped on a 16x32 doog
        self.assertEqual(rk['sprite'], 'lycanroc-pack')
        for suffix in ('.png', '_mu.png'):
            self.assertTrue(os.path.isfile(os.path.join(
                bc.REPO, 'campaigns', self.CAMPAIGN, 'map_sprites',
                rk['sprite'] + suffix)), 'missing map_sprites/%s%s' % (rk['sprite'], suffix))
        # Appended class ids must stay unique (0x80/0x81/0x82 are ch03's).
        ids = [r['slot_id'] for r in bc.enemy_class_reskins(self.CAMPAIGN) if r.get('slot_id')]
        self.assertEqual(len(ids), len(set(ids)))

    def test_the_parley_converts_each_wolf_where_it_stands(self):
        # No DISA + LOAD1: clearing the pack and reloading its table put the wolves back on
        # their SPAWN tiles (they teleported home mid-fight) and resurrected any the player had
        # already killed. CUSN flips the unit in place, so the pack stays where it is.
        pre = bc.convert_survivors_green(('0xb3', '0xb4'), 0x40, 'wolf')
        self.assertNotIn('DISA', pre)
        self.assertNotIn('LOAD1', pre)
        self.assertIn('CUSN(0xb3)', pre)
        self.assertIn('CUSN(0xb4)', pre)

    def test_a_wolf_killed_before_the_parley_is_skipped_not_converted(self):
        # UnitKill WIPES a non-blue slot (pCharacterData = NULL, bmunit.c:988) and a CUSN on an
        # unresolvable pid returns EVC_ERROR rather than no-op'ing the way DISA/KILL do
        # (eventscr.c:3317) -- so a bare sweep breaks in exactly the kill-then-parley case this
        # is meant to reward. Each CUSN sits behind its own CHECK_ALIVE, jumping its own label.
        pre = bc.convert_survivors_green(('0xb3', '0xb4'), 0x40, 'wolf')
        for pid in ('0xb3', '0xb4'):
            self.assertLess(pre.index('CHECK_ALIVE(%s)' % pid), pre.index('CUSN(%s)' % pid))
        labels = re.findall(r'LABEL\((0x[0-9A-F]+)\)', pre)
        self.assertEqual(labels, ['0x40', '0x41'])          # one skip target per wolf
        self.assertEqual(re.findall(r'BEQ\((0x[0-9A-F]+)', pre), labels)
        # ...and the BEQ jumps PAST its own conversion, not past the whole sweep.
        self.assertLess(pre.index('CUSN(0xb3)'), pre.index('LABEL(0x40)'))
        self.assertLess(pre.index('LABEL(0x40)'), pre.index('CHECK_ALIVE(0xb4)'))

    # -- #205: vanilla Ch4's villages, restored -------------------------------------------
    def _maps_dir(self):
        return os.path.join(bc.REPO, 'campaigns', self.CAMPAIGN, 'maps')

    def _bern(self):
        import map_tileset_tool as mt
        return mt._tileset_from_dir(os.path.join(self._maps_dir(), 'tilesets', 'snowy-bern'))

    def test_the_village_the_yaml_declares_sits_on_a_visitable_tile(self):
        """The guard #205 needed from the content side. FE8 offers Visit only on village/house
        terrain (bmmenu.c:735), so a `villages:` entry whose tile is scenery is a reward that
        silently does not exist -- which is exactly what shipped, because the snowy reskin had
        mapped vanilla's village metatile onto ruins."""
        bc.assert_village_tiles_visitable(self._chap(), self._maps_dir(), bc.CH04_LAYOUT[1])

    def test_a_village_declared_on_scenery_fails_the_build(self):
        chap = dict(self._chap())
        chap['villages'] = [{'id': 'nowhere', 'tile': [7, 7],
                             'visit_reward': [{'id': 'iron-axe'}]}]
        with self.assertRaises(SystemExit):
            bc.assert_village_tiles_visitable(chap, self._maps_dir(), bc.CH04_LAYOUT[1])

    def test_ch04_wires_its_village_where_vanilla_ch4_did(self):
        # vanilla Ch4: Village(0, EventScr_089F1BD8, 8, 2) -- the ITEM village (the other, at
        # (1,11), is vanilla's recruit village, whose role the Lupin parley took over).
        body = bc.ch04_location_events(self._chap())
        self.assertIn('Village(0, %s, 8, 2)' % bc.CH04_VILLAGE_SCRIPT, body)
        self.assertTrue(body.rstrip().endswith('END_MAIN\n}'))

    def test_the_village_hands_the_visitor_the_authored_reward(self):
        # vanilla's own shape (EventScr_089F1BD8): one text box over the village BG, then
        # SVAL the item into slot 3 and GIVEITEMTO the unit that visited.
        s = bc.ch04_village_script(0x9C3, 'ITEM_AXE_IRON', bc.CH04_OPENING_FOREST_BG)
        self.assertIn('Text_BG(%s, 0x9C3)' % bc.CH04_OPENING_FOREST_BG, s)
        self.assertLess(s.index('Text_BG'), s.index('SVAL(EVT_SLOT_3, ITEM_AXE_IRON)'))
        self.assertLess(s.index('SVAL(EVT_SLOT_3, ITEM_AXE_IRON)'),
                        s.index('GIVEITEMTO(CHAR_EVT_ACTIVE_UNIT)'))

    def test_the_reward_item_is_read_from_the_chapter_yaml(self):
        """#208's lesson applied early: the village's reward and its line are CONTENT, so they
        live in the chapter YAML and the injector reads them."""
        village = self._chap()['villages'][0]
        self.assertEqual('iron-axe', village['visit_reward'][0]['id'])
        self.assertEqual('ITEM_AXE_IRON', bc.CH04_ITEM_IDS['iron-axe'])
        self.assertTrue(village.get('visit_text'), 'the village needs a line to show')

    def test_the_moose_sighting_area_does_not_cover_a_village_doorstep(self):
        """Vanilla's AREA was (0,9)-(14,14) and touched neither village; ours is authored, and
        its first draft started exactly on the axe village's tile -- so stepping up to visit
        would have fired the sighting cutscene instead."""
        x1, y1, x2, y2 = bc.CH04_MOOSE_AREA
        for village in self._chap()['villages']:
            vx, vy = village['tile']
            self.assertFalse(x1 <= vx <= x2 and y1 <= vy <= y2,
                             'the moose AREA covers the %r village at (%d,%d)'
                             % (village['id'], vx, vy))

    # -- #214: the snag -> bridge, and the visited-village tile ---------------------------
    def test_map_changes_emit_one_region_per_change(self):
        """The reusable emitter (ch03's chests/doors, ch04's snag): FE8 finds a change by
        POSITION (GetMapChangeIdAt), so ids only need to stay unique, and each region carries
        its own tile data as metatile<<2 -- the gBmMapBaseTiles encoding."""
        asm = bc.map_changes_asm('MS_TestChanges', [
            (4, 8, 1, 3, [6, 36, 6], 'the snag falls'),
            (8, 2, 1, 1, [32], 'village visited'),
        ])
        self.assertIn('MS_TestChanges:', asm)
        self.assertIn('\t.byte 0, 4, 8, 1, 3, 0, 0, 0', asm)     # 1 wide x 3 tall at (4,8)
        self.assertIn('\t.byte 1, 8, 2, 1, 1, 0, 0, 0', asm)     # 1x1 at (8,2)
        self.assertIn('.hword %d' % (36 << 2), asm)               # tiles are metatile<<2
        self.assertIn('.byte -1,', asm)                           # terminator (id < 0)

    def test_the_snag_becomes_a_crossing_where_the_river_runs(self):
        """The Iron Axe's whole purpose (#214). Vanilla Ch4 puts the snag at (4,8) 1x3 and
        replaces it with plains / BRIDGE_SNAG / plains, so the trunk falls across the river at
        (4,9). Our retile kept that geometry, so the crossing lands where it should."""
        changes = bc.ch04_map_changes(self._chap(), self._maps_dir())
        snag = [c for c in changes if (c[0], c[1]) == bc.CH04_SNAG_POS]
        self.assertEqual(len(snag), 1, 'ch04 must register exactly one snag change')
        x, y, w, h, tiles, _why = snag[0]
        self.assertEqual((w, h), (1, 3))
        ids = bc.terrain_ids()
        tileset = self._bern()
        self.assertEqual(ids['TERRAIN_BRIDGE_REGULAR'], tileset.terrain(tiles[1]),
                         'the middle cell (the river row) must become a crossing')
        # ...and every tile it writes must be PAINTED. snowy-bern declares BRIDGE_SNAG on an
        # unpainted metatile; using it left a black square in the river with a perfectly correct
        # terrain byte, which no data check would have caught (#214).
        for m in tiles:
            self.assertFalse(bc._is_blank_metatile(tileset, m),
                             'map change writes blank metatile %d' % m)

    def test_the_snag_change_covers_the_tile_that_is_actually_a_snag(self):
        """Pins the trap rather than today's answer: the engine adds the obstacle on the
        TERRAIN_SNAG tile (bmtrick.c) and looks the change up by that position, so a change
        authored a row off breaks silently -- the snag stays hittable and nothing happens."""
        width, height, terrain = bc._map_terrain_grid(self._maps_dir(), bc.CH04_LAYOUT[1])
        x, y = bc.CH04_SNAG_POS
        self.assertEqual(bc.terrain_ids()['TERRAIN_SNAG'], terrain[y][x])

    def test_a_visited_village_stops_looking_unvisited(self):
        changes = bc.ch04_map_changes(self._chap(), self._maps_dir())
        village = self._chap()['villages'][0]['tile']
        door = [c for c in changes if [c[0], c[1]] == village]
        self.assertEqual(len(door), 1)
        self.assertEqual(bc.terrain_ids()['TERRAIN_VILLAGE_CLOSED'],
                         self._bern().terrain(door[0][4][0]))

    def test_the_village_line_is_vanillas_own_snag_tutorial(self):
        """Nicolas 2026-08-02: copy vanilla 1:1. The line exists to teach the snag gimmick and
        hand over the tool -- a flavour line throws the function away."""
        text = ' '.join(bc.village_boxes(self._chap()['villages'][0]))
        self.assertIn('snag', text)
        self.assertIn('bridge', text)
        self.assertNotIn('husband', text)   # the placeholder draft this replaces

    # -- #24: the SECOND village, vanilla Ch4's other cottage --------------------------------
    def test_both_of_vanilla_ch4s_villages_are_wired(self):
        """#24's last item. Vanilla Ch4 wires TWO villages -- Village(0, .., 8, 2) and
        Village(0, .., 1, 11) -- and we shipped only the axe one. The cottage at (1,11) stood
        on visitable terrain with no Location entry, so FE8 offered no Visit at all: the player
        saw a house they could not enter."""
        body = bc.ch04_location_events(self._chap())
        self.assertIn('Village(0, %s, 8, 2)' % bc.CH04_VILLAGE_SCRIPT, body)
        self.assertIn('Village(0, %s, 1, 11)' % bc.CH04_COTTAGE_SCRIPT, body)
        self.assertTrue(body.rstrip().endswith('END_MAIN\n}'))

    def test_each_village_owns_its_own_script_and_message_slot(self):
        """Two doors sharing one script show the same line at both -- and, worse, run the
        give-item tail twice."""
        self.assertNotEqual(bc.CH04_VILLAGE_SCRIPT, bc.CH04_COTTAGE_SCRIPT)
        self.assertNotEqual(bc.CH04_VILLAGE_MSG, bc.CH04_COTTAGE_MSG)
        # ...and the new id has to join the ownership registry, or the uniqueness guard that
        # #24 asked for cannot see it (a double-claim overwrites silently and stays green).
        self.assertIn(bc.CH04_COTTAGE_MSG, bc.HOSTED_CHAPTER_MESSAGE_IDS['ch04'])

    def test_each_village_plays_over_winter_art_not_vanillas_green_town(self):
        """ch04 is a snowbound forest under fog, and `BG_NORMAL_VILLAGE` is vanilla's TEMPERATE
        green town -- so the backdrop, which is the whole screen during a village visit, was
        showing summer (Nicolas, 2026-08-05). Both doors take the fogged forest that Pinky's
        opening beat already plays over: there is no TOWN on this map -- both cottages are
        cabins standing in the same woods and the visitor is outside one of them (Nicolas: "if
        we're outside their cabin, just use the bg you put behind pinky in his fog scene").
        """
        for name, slot in bc.CH04_VILLAGE_SLOTS.items():
            self.assertNotEqual('BG_NORMAL_VILLAGE', slot[3],
                                '%s is still on vanilla temperate art' % name)
            self.assertEqual(bc.CH04_OPENING_FOREST_BG, slot[3],
                             '%s should stand outside its cabin, in the fog' % name)

    def test_a_village_script_plays_over_the_backdrop_it_is_given(self):
        s = bc.ch04_village_script(0x9C6, None, 'BG_MS_LONELYWOOD_FOG')
        self.assertIn('Text_BG(BG_MS_LONELYWOOD_FOG, 0x9C6)', s)

    def test_a_village_with_no_reward_hands_over_nothing(self):
        """ch04's economy is deliberately Ch4-lean (decisions.md): the Iron Axe is the whole
        material gift, so the cottage's reward IS its line. The script must drop the give-item
        tail rather than quietly hand over some default."""
        s = bc.ch04_village_script(0x9C6, None, bc.CH04_OPENING_FOREST_BG)
        self.assertIn('Text_BG(%s, 0x9C6)' % bc.CH04_OPENING_FOREST_BG, s)
        self.assertNotIn('SVAL(EVT_SLOT_3', s)
        self.assertNotIn('GIVEITEMTO', s)
        self.assertIn('EVBIT_T(7)', s)      # still marks the visit, so the door shuts

    def test_a_village_line_is_authored_in_boxes_not_reflowed(self):
        """A village line is dialogue: its A-press breaks are authored, not a side effect of
        where a 42-column wrap happens to land. One YAML entry == one GBA box."""
        for village in self._chap()['villages']:
            for box in bc.village_boxes(village):
                lines = bc._wrap_fe_lines(bc._fe_dialogue_text(box), 42)
                self.assertLessEqual(len(lines), 2,
                                     'box overflows its A-press in %r: %r'
                                     % (village['id'], box))

    def test_the_axe_villages_boxes_match_vanillas_own_four(self):
        """Vanilla's MSG_9B5 is FOUR boxes, each broken on a sentence. Flowed as one scalar
        ours reflowed to THREE and buttoned mid-sentence ("a handy bridge if / you could knock
        it over") -- 1:1 in words but not on screen, which is not what 1:1 was asked for."""
        boxes = bc.village_boxes(self._chap()['villages'][0])
        self.assertEqual(4, len(boxes))
        self.assertTrue(boxes[0].rstrip().endswith('south of here?'), boxes[0])
        self.assertTrue(boxes[1].rstrip().endswith('knock it over.'), boxes[1])

    def test_the_cottage_line_drops_the_lore_the_chapter_has_nowhere_else(self):
        """The line's whole job (#24, Nicolas: "at least a lore drop or a hint"). Grounded in
        the DM notes -- "the frost druids did visit, but were largely ignored by villagefolk"
        -- and the book's Ravisin, who "won't rest until the forest is free of loggers". She
        is never NAMED here: the ending owns the chapter's one Ravisin seed (2026-07-03 cut)."""
        text = ' '.join(bc.village_boxes(self._chap()['villages'][1]))
        self.assertIn('White furs', text)
        self.assertIn('southeast', text)
        self.assertNotIn('Ravisin', text)

    def test_both_villages_close_their_doors_when_visited(self):
        changes = bc.ch04_map_changes(self._chap(), self._maps_dir())
        for village in self._chap()['villages']:
            door = [c for c in changes if [c[0], c[1]] == village['tile']]
            self.assertEqual(1, len(door), 'no door change for %r' % village['id'])
            self.assertEqual(bc.terrain_ids()['TERRAIN_VILLAGE_CLOSED'],
                             self._bern().terrain(door[0][4][0]))

    def test_parley_recruiter_is_marty_only(self):
        # Nicolas 2026-07-21: ch04's talker is Marty specifically, NOT ch03's any-party-member.
        # Data-driven from the convertible wave's parley.by; Marty rides the Seth slot.
        self.assertEqual(bc.ch04_parley_recruiters(self.CAMPAIGN, self._chap()),
                         ['CHARACTER_SETH'])

    def test_reveal_cutscene_pans_loads_focuses_lupin_and_plants_the_parley(self):
        # Stage 2c: the turn-2 reveal rides the existing LOAD1 (vanilla EventScr_089F199C shape):
        # pan to the NW fog, burst the pack in, focus Lupin (the commander), then stub beats plant
        # the parley (Lupin commands; Marty flags "talk to it"). Real dialogue is Stage 4.
        s = bc.ch04_reveal_cutscene_script('UnitDef_088B5798', 'CHARACTER_DUESSEL',
                                           (0x9BB, 0x9BC), (2, 2))
        self.assertIn('CAMERA2(2, 2)', s)
        self.assertIn('LOAD1(0x1, UnitDef_088B5798)', s)   # the pack still bursts in
        self.assertIn('CUMO_CHAR(CHARACTER_DUESSEL)', s)   # focus the commander
        self.assertIn('TEXTSHOW(0x9BB)', s)                # Lupin commands
        self.assertIn('TEXTSHOW(0x9BC)', s)                # Marty flags the parley
        self.assertLess(s.index('LOAD1'), s.index('CUMO_CHAR'))   # load before the focus/beats
        self.assertTrue(s.rstrip().endswith('EVBIT_T(7)\n    ENDA\n}'))  # marked done

    def test_parley_recruiter_is_force_deployed_in_the_chapter_slot(self):
        # A Marty-ONLY parley must force-deploy Marty so benching him can't miss the recruit
        # (Nicolas 2026-07-21). Vanilla's per-chapter ForceDeploymentEnt path, no new engine
        # code: {pid, route=ANY(0xFF), chapter=host slot}. Redundant-but-harmless if the player
        # chose Marty as lord (IsCharacterForceDeployed_ already returns true for the lead).
        entries = bc._force_deployment_entries(
            bc.ch04_parley_recruiters(self.CAMPAIGN, self._chap()), bc.CH04_HOST_INDEX)
        self.assertIn('{CHARACTER_SETH, 0xFF, %d}' % bc.CH04_HOST_INDEX, entries)

    def test_roster_uses_the_vanilla_monster_classes_and_weapons(self):
        rows = '\n'.join(bc.ch04_enemy_rows(self._chap()) +
                         bc.ch04_enemy_rows(self._chap(), arrives_turn=2) +
                         bc.ch04_enemy_rows(self._chap(), arrives_turn=3))
        # The twin's own classes/weapons: Mogall (evil eye), melee Revenant (rotten claw),
        # melee Bonewalker (iron sword line / iron lance pack), Entombed (fetid claw), plus
        # the Mauthe Doog fiction swap. NOT the drifted bow-skeleton "phantom arrows".
        for token in ('CLASS_MAUTHEDOOG', 'ITEM_MONSTER_ROTTENCLW',
                      'CLASS_REVENANT',
                      'CLASS_BONEWALKER', 'ITEM_SWORD_IRON', 'ITEM_LANCE_IRON',
                      'CLASS_MOGALL', 'ITEM_MONSTER_EVILEYE',
                      'CLASS_ENTOUMBED', 'ITEM_MONSTER_FETIDCLW'):
            self.assertIn(token, rows)
        for retired in ('CLASS_BONEWALKER_BOW', 'ITEM_BOW_IRON'):
            self.assertNotIn(retired, rows)

    def test_reinforcement_vulnerary_has_exactly_one_dropper(self):
        # The dropping Revenant is the turn-3 area wave (mirrors vanilla Ch4's dropping revenant).
        rows = '\n'.join(bc.ch04_enemy_rows(self._chap(), arrives_turn=3))
        self.assertEqual(rows.count('.itemDrop = 1'), 1)
        self.assertEqual(rows.count('ITEM_VULNERARY'), 1)

    def test_ch04_title_card_has_a_complete_vanilla_glyph_atlas(self):
        card = bc.gen_chapter_title.compose_title('Ch.4: The White Moose')
        self.assertEqual(card.size, (256, 16))
        self.assertIsNotNone(card.getbbox())


class HostChapterEventGroup(unittest.TestCase):
    """A hosted chapter must RUN the ChapterEventGroup its injector fills.

    Vanilla's slot index tracks the chapter number only up to 4: FE8 inserts chapter 5X
    at slot 5, so slot 5's mapEventDataId resolves to Ch5XEvents while inject_ch04 writes
    every event into Ch5EventData. Retargeting a host slot rewrites the MAP ids, and the
    map ids alone are enough to make the chapter look right -- so the failure is silent
    and total: the slot presents OUR 15x15 map while running 5X's roster and scripts
    (24 foreign reds off the footprint, the party never deployed, the cursor initialised
    onto an off-map sentinel). Naming the event group is therefore mandatory, not optional.
    """

    TABLE = 'gChapterDataAssetTable'

    def _vanilla_index(self, symbol):
        """`symbol`'s index in the COMMITTED asset table (our injectors only append, so
        vanilla indices are stable -- but read HEAD anyway, never the built tree)."""
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'asset_table.s')
            with open(path, 'w', encoding='utf-8') as f:
                f.write(bc.vanilla_decomp_text('data/data_8B363C.s'))
            return bc._asm_table_word_index(path, self.TABLE, symbol)

    def _retarget(self, host_index, event_group):
        """Run _retarget_host_chapter against a throwaway copy of vanilla's settings."""
        vanilla = json.loads(bc.vanilla_decomp_text('src/data/chapter_settings.json'))
        donor = 3
        goal_type = vanilla['chapters'][donor]['goal']['windowDataType']
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'chapter_settings.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(vanilla, f)
            original = bc.CHAPTER_SETTINGS_JSON
            bc.CHAPTER_SETTINGS_JSON = path
            try:
                return bc._retarget_host_chapter(
                    host_index, donor, goal_type, 'unreachable in this test',
                    (0, 0, 0, 0), 4, event_group=event_group,
                    goal_text_ids=(0x9C4, 0x9C5))
            finally:
                bc.CHAPTER_SETTINGS_JSON = original

    def test_slot_five_is_chapter_5x_not_chapter_5(self):
        # The trap itself, pinned against vanilla so a decomp bump can't quietly move it.
        vanilla = json.loads(bc.vanilla_decomp_text('src/data/chapter_settings.json'))
        self.assertEqual(vanilla['chapters'][bc.CH04_HOST_INDEX]['mapEventDataId'],
                         self._vanilla_index('Ch5XEvents'))
        self.assertNotEqual(self._vanilla_index('Ch5XEvents'),
                            self._vanilla_index(bc.CH04_EVENT_GROUP))

    def test_ch04_host_slot_is_repointed_off_ch5x_onto_its_own_event_group(self):
        host = self._retarget(bc.CH04_HOST_INDEX, bc.CH04_EVENT_GROUP)
        self.assertEqual(host['mapEventDataId'],
                         self._vanilla_index(bc.CH04_EVENT_GROUP))

    def test_every_hosted_chapter_names_the_event_group_it_fills(self):
        # The earlier slots were correct only because slot index == chapter number there;
        # they are now explicit, so the next hosted chapter cannot inherit the coincidence.
        for host_index, group in (
                (bc.CH01_HOST_INDEX, bc.CH01_EVENT_GROUP),
                (bc.CH02_HOST_INDEX, bc.CH02_EVENT_GROUP),
                (bc.CH03_HOST_INDEX, bc.CH03_EVENT_GROUP),
                (bc.CH04_HOST_INDEX, bc.CH04_EVENT_GROUP)):
            host = self._retarget(host_index, group)
            self.assertEqual(host['mapEventDataId'], self._vanilla_index(group),
                             'host slot %d must run %s' % (host_index, group))

    def test_making_it_explicit_moves_ch04_alone(self):
        """ch01-ch03 must be byte-identical after the repoint -- they were already right,
        so naming the group is a no-op there and the ONLY behaviour change is slot 5."""
        vanilla = json.loads(bc.vanilla_decomp_text('src/data/chapter_settings.json'))
        for host_index, group in ((bc.CH01_HOST_INDEX, bc.CH01_EVENT_GROUP),
                                  (bc.CH02_HOST_INDEX, bc.CH02_EVENT_GROUP),
                                  (bc.CH03_HOST_INDEX, bc.CH03_EVENT_GROUP)):
            self.assertEqual(vanilla['chapters'][host_index]['mapEventDataId'],
                             self._vanilla_index(group),
                             'slot %d already ran %s -- the repoint must not move it'
                             % (host_index, group))
        self.assertNotEqual(vanilla['chapters'][bc.CH04_HOST_INDEX]['mapEventDataId'],
                            self._vanilla_index(bc.CH04_EVENT_GROUP),
                            'ch04 is the one slot the repoint actually changes')


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


class IdempotentInjectionMtimes(unittest.TestCase):
    """The warm-rebuild speed-up: rewind mtimes only for byte-identical files, so
    `make` skips unchanged targets while the ROM stays bit-identical (#build-speed)."""

    def _tmpfile(self, data=b'hello'):
        import tempfile
        fd, path = tempfile.mkstemp()
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        return path

    def test_snapshot_records_mtime_and_hash(self):
        p = self._tmpfile(b'abc')
        snap = bc._snapshot_mtimes([p])
        self.assertIn(p, snap)
        mtime_ns, digest = snap[p]
        self.assertEqual(mtime_ns, os.stat(p).st_mtime_ns)
        self.assertEqual(digest, hashlib.sha1(b'abc').digest())

    def test_snapshot_skips_missing_files(self):
        # A path that does not exist is simply not tracked (no raise).
        self.assertEqual(bc._snapshot_mtimes(['/no/such/file/xyz']), {})

    def test_rewinds_mtime_when_content_unchanged(self):
        # Rewriting a file with IDENTICAL bytes normally bumps mtime; the rewind
        # must restore the snapshot mtime so make treats the target as up to date.
        p = self._tmpfile(b'same-bytes')
        snap = bc._snapshot_mtimes([p])
        os.utime(p, ns=(snap[p][0] + 5_000_000_000, snap[p][0] + 5_000_000_000))
        with open(p, 'wb') as f:          # rewrite identical content (new mtime)
            f.write(b'same-bytes')
        self.assertNotEqual(os.stat(p).st_mtime_ns, snap[p][0])
        n = bc._rewind_unchanged_mtimes(snap)
        self.assertEqual(n, 1)
        self.assertEqual(os.stat(p).st_mtime_ns, snap[p][0])

    def test_does_not_rewind_when_content_changed(self):
        # A genuinely changed file KEEPS its fresh mtime, so make rebuilds it.
        p = self._tmpfile(b'original')
        snap = bc._snapshot_mtimes([p])
        with open(p, 'wb') as f:
            f.write(b'CHANGED')
        changed_mtime = os.stat(p).st_mtime_ns
        n = bc._rewind_unchanged_mtimes(snap)
        self.assertEqual(n, 0)
        self.assertEqual(os.stat(p).st_mtime_ns, changed_mtime)  # not rewound

    def test_footprint_lists_modified_and_untracked_sources(self):
        # The footprint comes from `git status` on the decomp: an mtime rewind is only
        # meaningful for files git already sees as part of the injection (source, not
        # the .gitignored build outputs). Just assert it returns decomp-rooted paths.
        for p in bc._decomp_footprint():
            self.assertTrue(p.startswith(bc.DECOMP), p)


if __name__ == '__main__':
    unittest.main()


class CustomSmsIdsStayUnderTheEngineMask(unittest.TestCase):
    """FE8 looks up a map sprite's geometry through a MASKED index:

        #define GetInfo(id) (unit_icon_wait_table[(id) & ((1<<7)-1)])

    so an SMS id >= 128 silently reads a VANILLA row -- id 128 draws Ephraim Lord's
    sheet at Ephraim Lord's size class. It does not crash and it does not warn: the
    unit just renders as somebody else. The mask is NOT the array bound either
    (gUnitSpriteSlots is u8[0xD0] and ids 128-207 are valid slot-cache indices), which
    is exactly why nothing else catches it (#225).

    Our custom ids start at CUSTOM_SMS_BASE = 107, so the budget is small and finite.
    """

    def test_the_limit_is_read_from_the_decomp_not_hardcoded(self):
        """Ground the ceiling in the engine that enforces it -- if a decomp bump widens
        or narrows the mask, the guard must follow it rather than assert a stale 127."""
        self.assertEqual(bc._sms_id_mask_bits(), 7)
        self.assertEqual(bc.sms_id_max(), 127)

    def test_the_mask_read_fails_loudly_if_the_define_moves(self):
        src = open(os.path.join(bc.REPO, 'tools', 'build_campaign.py'),
                   encoding='utf-8').read()
        body = src[src.index('def _sms_id_mask_bits('):]
        body = body[:body.index('\ndef ')]
        self.assertIn('sys.exit', body)
        self.assertIn('vanilla_decomp_text', body,
                      'read the mask from HEAD -- the working tree is our own artifact')

    def test_every_wait_table_append_goes_through_the_guarded_helper(self):
        """A new sprite pass must not be able to append a row unguarded. The choke point
        is _append_wait_rows; nothing else may append to unit_icon_wait_table[]."""
        src = open(os.path.join(bc.REPO, 'tools', 'build_campaign.py'),
                   encoding='utf-8').read()
        helper = src[src.index('def _append_wait_rows('):]
        helper = helper[:helper.index('\ndef ')]
        outside = src.replace(helper, '')
        self.assertNotIn('_append_table_rows(UNIT_ICON_WAIT_C', outside,
                         'append wait rows via _append_wait_rows, not _append_table_rows')
        self.assertIn('_append_table_rows(UNIT_ICON_WAIT_C', helper,
                      'the helper is the one place allowed to do the raw append')
        self.assertGreaterEqual(outside.count('_append_wait_rows('), 5,
                                'all five sprite passes must route through the guard')

    def test_the_guard_rejects_a_row_past_the_mask(self):
        """The regression: overflowing must fail the BUILD, naming the id and the unit,
        rather than shipping a sprite that renders as a vanilla class."""
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, 'unit_icon_wait_data.c')
            rows = ''.join('\t{0, UNIT_ICON_SIZE_16x16, sheet_%d},\n' % i for i in range(128))
            with open(path, 'w', encoding='utf-8') as f:
                f.write('UnitIconWait unit_icon_wait_table[] = {\n%s};\n' % rows)
            with mock.patch.object(bc, 'UNIT_ICON_WAIT_C', path):
                self.assertEqual(bc._wait_table_len(), 128)   # ids 0..127: exactly full
                with self.assertRaises(SystemExit) as cm:
                    bc._append_wait_rows(['\t{0, UNIT_ICON_SIZE_16x16, x}, // 128 basil'])
            msg = str(cm.exception)
            self.assertIn('128', msg, 'name the overflowing id')
            self.assertIn('basil', msg, 'name the unit that overflowed')
            self.assertIn('127', msg, 'state the ceiling')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_guard_allows_the_last_usable_id(self):
        """127 is usable -- an off-by-one here would cost us a sprite we own."""
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, 'unit_icon_wait_data.c')
            rows = ''.join('\t{0, UNIT_ICON_SIZE_16x16, sheet_%d},\n' % i for i in range(127))
            with open(path, 'w', encoding='utf-8') as f:
                f.write('UnitIconWait unit_icon_wait_table[] = {\n%s};\n' % rows)
            with mock.patch.object(bc, 'UNIT_ICON_WAIT_C', path):
                bc._append_wait_rows(['\t{0, UNIT_ICON_SIZE_16x16, x}, // 127 sahnar'])
                self.assertEqual(bc._wait_table_len(), 128)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_remaining_headroom_is_reported_while_it_is_still_cheap_to_act_on(self):
        """Two ids left is worth knowing BEFORE the build that spends them, so the
        injector prints the headroom and says so loudly when it is nearly gone. (The
        "does the live campaign fit" question is answered end-to-end by the guard
        itself firing during a real build, which CI runs.)"""
        src = open(os.path.join(bc.REPO, 'tools', 'build_campaign.py'),
                   encoding='utf-8').read()
        body = src[src.index('def _append_wait_rows('):]
        body = body[:body.index('\ndef ')]
        self.assertIn('SMS_ID_LOW_WATER', body)
        self.assertIn('print(', body, 'report the headroom, do not only enforce it')


class CastPaletteBankSurvivesEveryRosterScreen(unittest.TestCase):
    """The cast map-sprite palette lives in the purple OBJ bank (0x0B), which vanilla
    treats as scratch: several screens call ApplyUnitSpritePalettes() and then
    immediately ZERO that bank, because no vanilla unit renders from it. A zeroed
    16-colour bank draws every index as colour 0 -- our cast come out as correctly
    shaped BLACK SILHOUETTES (#218; the same failure was fixed once for Pick Units).

    The idiom is spelled differently per screen (`PAL_OBJ(0x0B)` in prep_unitselect,
    `gPaletteBuffer + 0x1B0` in unitlistscreen), so it must be listed per site rather
    than grepped for -- hence PURPLE_BANK_BLANKERS, which is what these tests pin.
    """

    def test_every_known_blanker_names_a_real_decomp_site(self):
        """Each entry must match the CURRENT vanilla source, read from HEAD -- the
        working tree is a build artifact of our own injections."""
        for path, orig, _ in bc.PURPLE_BANK_BLANKERS:
            vanilla = bc.vanilla_decomp_text(os.path.relpath(path, bc.DECOMP))
            self.assertIn(orig, vanilla,
                          '%s no longer contains its purple-bank fill verbatim'
                          % os.path.basename(path))

    def test_the_unit_list_screen_is_covered(self):
        """The regression this class exists for: the Character screen players open
        constantly blanked the whole cast (#218)."""
        sites = [os.path.basename(p) for p, _, _ in bc.PURPLE_BANK_BLANKERS]
        self.assertIn('unitlistscreen.c', sites)
        self.assertIn('prep_unitselect.c', sites)

    def test_each_patch_drops_the_fill_and_keeps_the_palette_load(self):
        """The fix is to delete the zeroing, NOT to reorder or re-load: whatever
        ApplyUnitSpritePalettes just put in bank 0x0B is already correct."""
        for path, orig, hooked in bc.PURPLE_BANK_BLANKERS:
            where = os.path.basename(path)
            self.assertIn('ApplyUnitSpritePalettes();', orig, where)
            self.assertIn('ApplyUnitSpritePalettes();', hooked, where)
            self.assertNotIn('CpuFastFill', hooked,
                             '%s must DROP the fill, not re-spell it' % where)
            self.assertIn('/*', hooked, '%s: say WHY the fill is gone' % where)

    def test_the_hook_rejects_a_site_that_drifted(self):
        """A decomp bump that reworks one of these screens must FAIL the build loudly,
        not silently leave that screen's roster black."""
        src = open(os.path.join(bc.REPO, 'tools', 'build_campaign.py'),
                   encoding='utf-8').read()
        body = src[src.index('def _drop_purple_bank_fills('):]
        body = body[:body.index('\ndef ')]
        self.assertIn('sys.exit', body)


class PreRecruitVariant(unittest.TestCase):
    """A cast member on the field BEFORE he joins you (ch04's Lupin: red as the pack's
    leader, the finalized grey once Marty's parley brings him over).

    The failure this guards is the Trex bug's sibling: a charId-keyed cast-palette
    override is unconditional, so without the faction check Lupin renders in his bespoke
    grey while he is an ENEMY -- and FE reads grey as "already acted".
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_lupin_declares_pre_recruit_roles_covering_every_index_he_uses(self):
        roles = bc.pre_recruit_roles(self.CAMPAIGN, 'lupin')
        self.assertIsNotNone(roles, 'lupin.yaml must declare art.map_sprite.pre_recruit_roles')
        ms = os.path.join(bc.REPO, 'campaigns', self.CAMPAIGN, 'map_sprites')
        for stem in ('lupin.png', 'lupin_mu.png'):
            used = {v for v in Image.open(os.path.join(ms, stem)).getdata() if v}
            self.assertTrue(used <= set(roles), '%s uses undeclared cast indices %s'
                            % (stem, sorted(used - set(roles))))
        # The body must land on the faction ramp (7-10) -- that is what makes him read red.
        self.assertTrue({roles[2], roles[3]} & set(range(7, 11)),
                        'no body index on the faction ramp: he would not change colour by side')

    def test_a_plain_cast_member_has_no_variant(self):
        self.assertIsNone(bc.pre_recruit_roles(self.CAMPAIGN, 'braulo'))

    def test_remap_indices_rewrites_by_role_and_rejects_an_undeclared_index(self):
        tmp = tempfile.mkdtemp(prefix='prv_')
        try:
            src, out = os.path.join(tmp, 's.png'), os.path.join(tmp, 'o.png')
            pal = os.path.join(tmp, 'p.png')
            for path, data in ((src, [0, 1, 3, 11]), (pal, list(range(16)))):
                im = Image.new('P', (len(data), 1))
                im.putpalette([0, 0, 0] * 16)
                im.putdata(data)
                im.save(path)
            bc._remap_indices(src, {1: 15, 3: 9, 11: 13}, pal, out)
            self.assertEqual(list(Image.open(out).getdata()), [0, 15, 9, 13])
            with self.assertRaises(SystemExit) as cm:          # index 11 not declared
                bc._remap_indices(src, {1: 15, 3: 9}, pal, out)
            self.assertIn('11', str(cm.exception))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_every_override_hook_consults_the_variant_before_the_cast_override(self):
        src = open(os.path.join(bc.REPO, 'tools', 'build_campaign.py'), encoding='utf-8').read()
        self.assertIn('gPreRecruitVariant', src)
        # The lookup is gated on faction: a JOINED unit must fall through to the cast look.
        self.assertIn('UNIT_FACTION(%s) != FACTION_BLUE', bc._pre_recruit_lookup('%s'))
        for expr in ('unit', 'proc->unit'):
            self.assertIn('gPreRecruitVariant', bc._pre_recruit_lookup(expr))
        # Sprite + walk return the variant; the palette instead SKIPS the purple bank so
        # GetUnitSpritePalette falls through to the faction switch.
        self.assertIn('return prv->smsId;', src)
        self.assertIn('return prv->muImg;', src)
        self.assertIn('if (prv == 0) {', src)

    def test_the_lookup_is_c89_declarations_first(self):
        # agbcc (GCC 2.95.1) rejects mid-block declarations; CLAUDE.md coding conventions.
        body = [ln.strip() for ln in bc._pre_recruit_lookup('unit').splitlines() if ln.strip()]
        self.assertTrue(body[0].startswith('struct PreRecruitVariant * prv'))
        self.assertNotIn('//', bc._pre_recruit_lookup('unit'))

    def test_the_lookup_reuses_the_caller_s_charId_and_shadows_nothing(self):
        """Every hook already computes the charId for its own table scan, and GetMuImg
        walks its override table with a cursor called `it` -- so the lookup must not
        recompute UNIT_CHAR_ID into a second local, nor name its cursor `it`."""
        c = bc._pre_recruit_lookup('proc->unit')
        self.assertIn('prvIt->charId == charId', c)
        self.assertEqual(c.count('UNIT_CHAR_ID'), 0, 'charId is the caller\'s to compute')
        self.assertNotIn(' it ', c)
        self.assertNotIn('it++', c.replace('prvIt++', ''))
        # Callers with a differently-named charId can say so.
        self.assertIn('prvIt->charId == cid', bc._pre_recruit_lookup('unit', char_var='cid'))

    def test_every_hook_defines_charId_before_the_lookup_uses_it(self):
        """C89 + the reuse above: `int charId = ...` must precede the emitted lookup in
        each of the three hooks, or the generated source will not compile."""
        src = open(os.path.join(bc.REPO, 'tools', 'build_campaign.py'), encoding='utf-8').read()
        for fn in ('_inject_sms_override_hook', '_inject_mu_override_hook',
                   '_inject_palette_bank_hook'):
            body = src[src.index('def %s(' % fn):]
            body = body[:body.index('\ndef ')]
            self.assertLess(body.index('int charId = UNIT_CHAR_ID'),
                            body.index('_pre_recruit_lookup('),
                            '%s must set charId before the pre-recruit lookup' % fn)


class Ch04Stage4Scenes(unittest.TestCase):
    """The ch04 authored-scene machinery (#24 Stage 4) + the two #198-review guards."""

    def setUp(self):
        import yaml
        with open(os.path.join(bc.REPO, 'campaigns', 'rime-of-the-frostmaiden',
                               'chapters', 'ch04-the-white-moose.yaml'), encoding='utf-8') as f:
            self.chap = yaml.safe_load(f)
        self.end_event = next(e for e in self.chap['events']
                              if e.get('trigger') == 'chapter_end')

    # ── the no-Lupin branch ────────────────────────────────────────────────────
    def test_the_no_parley_path_has_a_speaker_for_every_box(self):
        """The reason this branch exists: a player can clear ch04 having killed the pack,
        and then two of the ending's three boxes have no speaker -- including the chapter's
        closing button. Every box must be voiced on BOTH paths (#24 checklist)."""
        _, beats = bc._split_event_beats(self.chap, 'chapter_end', 'end',
                                         (bc.CH04_ENDING_MSG,), card_required=False)
        locked = beats[0]
        fallback = bc.variant_beat(locked, self.end_event['no_lupin_fallback'], 'test')
        self.assertEqual(len(fallback), len(locked))
        for i, box in enumerate(fallback, 1):
            (speaker, text), = box.items()
            self.assertTrue(speaker and text.strip(), 'box %d has no speaker/text' % i)
        self.assertNotIn('lupin', [next(iter(b)) for b in fallback],
                         'the no-parley path must never put Lupin on stage')

    def test_the_unchanged_box_rides_through_both_branches(self):
        """Only boxes 1 and 3 are replaced; Marty's box 2 is the same line on both paths."""
        _, beats = bc._split_event_beats(self.chap, 'chapter_end', 'end',
                                         (bc.CH04_ENDING_MSG,), card_required=False)
        fallback = bc.variant_beat(beats[0], self.end_event['no_lupin_fallback'], 'test')
        self.assertEqual(beats[0][1], fallback[1])
        self.assertEqual(next(iter(fallback[1])), 'marty')

    def test_a_drifted_anchor_fails_loudly_instead_of_mis_swapping(self):
        """`replaces:` anchors exist so a re-ordered locked script cannot silently swap the
        wrong box. Reversing the scene must abort, not quietly produce nonsense."""
        _, beats = bc._split_event_beats(self.chap, 'chapter_end', 'end',
                                         (bc.CH04_ENDING_MSG,), card_required=False)
        with self.assertRaises(SystemExit):
            bc.variant_beat(list(reversed(beats[0])),
                            self.end_event['no_lupin_fallback'], 'test')

    def test_the_fallback_declaration_is_internally_consistent(self):
        fb = self.end_event['no_lupin_fallback']
        self.assertEqual(len(fb['boxes']), len(fb['replaces']))
        self.assertEqual(len(fb['boxes']), len(fb['script']))

    def test_the_branch_emits_both_arms_and_converges(self):
        """branch_on_flag is the vanilla ch19a idiom: CHECK_EVENTID -> BEQ to the fallback
        arm, the set-arm GOTOs past it, and both converge on a shared LABEL."""
        c = bc.branch_on_flag('EVFLAG_TMP(9)', '    SET\n', '    CLEAR\n')
        self.assertIn('CHECK_EVENTID(EVFLAG_TMP(9))', c)
        self.assertIn('BEQ(0x0, EVT_SLOT_C, EVT_SLOT_0)', c)
        self.assertLess(c.index('SET'), c.index('LABEL(0x0)'))
        self.assertLess(c.index('LABEL(0x0)'), c.index('CLEAR'))
        self.assertLess(c.index('CLEAR'), c.index('LABEL(0x1)'))
        # label_base keeps concurrent branches from colliding
        self.assertIn('LABEL(0x4)', bc.branch_on_flag('F', '', '', label_base=4))

    # ── #198 review guards ─────────────────────────────────────────────────────
    def test_every_hosted_chapter_declares_its_own_goal_ids(self):
        """#207: the goal window + status-objective strings are message ids like any other, but
        they arrive by INHERITANCE -- `_retarget_host_chapter` copies a donor slot's goal
        wholesale. ch04's donor is ch02's host slot, which inject_ch02 has already rewritten, so
        ch04 inherited ch02's ids and the two wrote over each other (last injector wins).
        Declaring them makes the existing uniqueness guard binding."""
        pairs = {'ch01': (bc.CH01_GOAL_WINDOW_MSG, bc.CH01_GOAL_STATUS_MSG),
                 'ch02': (bc.CH02_GOAL_WINDOW_MSG, bc.CH02_GOAL_STATUS_MSG),
                 'ch03': (bc.CH03_GOAL_WINDOW_MSG, bc.CH03_GOAL_STATUS_MSG),
                 'ch04': (bc.CH04_GOAL_WINDOW_MSG, bc.CH04_GOAL_STATUS_MSG)}
        flat = [mid for ids in pairs.values() for mid in ids]
        self.assertEqual(len(flat), len(set(flat)),
                         'two hosted chapters share a goal id: %s' % pairs)

    def test_the_goal_ids_are_registered_so_the_guard_binds(self):
        owner = bc.assert_message_ids_unique()
        self.assertEqual('ch04', owner[bc.CH04_GOAL_WINDOW_MSG])
        self.assertEqual('ch04', owner[bc.CH04_GOAL_STATUS_MSG])

    def test_ch04_takes_its_goal_ids_from_the_block_it_owns(self):
        """ch04 hosts on slot 5, so it owns vanilla Ch5's dead 0x9BA-0x9CC block. Its goal ids
        must come from THERE, not from whatever its donor slot happened to hold."""
        for mid in (bc.CH04_GOAL_WINDOW_MSG, bc.CH04_GOAL_STATUS_MSG):
            self.assertTrue(0x9BA <= mid <= 0x9CC,
                            'ch04 goal id 0x%X is outside its host block' % mid)

    def test_two_chapters_sharing_a_goal_id_fail_the_build(self):
        with self.assertRaises(SystemExit):
            bc.assert_message_ids_unique({'ch02': (bc.CH02_GOAL_WINDOW_MSG,),
                                          'ch04': (bc.CH02_GOAL_WINDOW_MSG,)})

    def test_hosted_chapters_do_not_share_message_ids(self):
        owner = bc.assert_message_ids_unique()
        self.assertEqual(owner[bc.CH04_ENDING_MSG], 'ch04')
        # ch04 owns vanilla Ch5's block because it is hosted on slot 5
        for mid in bc.HOSTED_CHAPTER_MESSAGE_IDS['ch04']:
            self.assertTrue(0x9BA <= mid <= 0x9CC, 'ch04 id 0x%X is outside its host block' % mid)

    def test_a_double_claimed_message_id_fails_the_build(self):
        """The failure this guard exists for: verify_text checks runaway text, not slot
        ownership, so a second writer overwrites the first and the build stays green."""
        with self.assertRaises(SystemExit):
            bc.assert_message_ids_unique({'ch04': (0x9BB,), 'ch05': (0x9BB,)})

    def test_the_shipped_pack_pids_are_the_packs_alone(self):
        bc.assert_pack_pids_addressable(self.chap, bc.CH04_PACK_PIDS)

    def test_a_pack_pid_reused_by_another_wave_is_rejected(self):
        """CUSN converts the FIRST unit matching a pid, so a pack pid shared with another wave
        would turn one of ITS units green on Marty's parley -- with the difficulty read still
        looking correct."""
        with self.assertRaises(SystemExit):
            bc.assert_pack_pids_addressable(
                self.chap, bc.CH04_PACK_PIDS[:-1] + (bc.CH04_MONSTER_PIDS['revenant'],))

    def test_two_wolves_sharing_a_pid_is_rejected(self):
        """The defect this replaces (#203): a repeated pid is unaddressable -- the second CUSN
        re-finds the wolf the first one already turned green."""
        dupe = (bc.CH04_PACK_PIDS[0],) + bc.CH04_PACK_PIDS[:-1]
        with self.assertRaises(SystemExit):
            bc.assert_pack_pids_addressable(self.chap, dupe)

    def test_a_pack_pid_colliding_with_the_moose_is_rejected(self):
        """The moose is a scripted neutral its own DISA targets; a pack pid landing on it
        would parley the quarry."""
        with self.assertRaises(SystemExit):
            bc.assert_pack_pids_addressable(
                self.chap, bc.CH04_PACK_PIDS[:-1] + (bc.CH04_MOOSE_PID,))

    # ── the moose beat ─────────────────────────────────────────────────────────
    def test_the_moose_is_loaded_shown_and_removed_in_one_beat(self):
        """It is uncatchable by design: it must never be left on the map to be attacked."""
        s = bc.ch04_moose_script(
            'UnitDef_X', '0xce', 0x9C0, (7, 4), ((9, 7), (9, 8), (14, 14)))
        self.assertLess(s.index('LOAD1(0x1, UnitDef_X)'), s.index('TEXTSHOW(0x9C0)'))
        self.assertLess(s.index('TEXTSHOW(0x9C0)'), s.index('MOVE_DEFINED(0xce)'))
        self.assertLess(s.index('MOVE_DEFINED(0xce)'), s.index('DISA(0xce)'))
        self.assertTrue(s.rstrip().endswith('ENDA\n}'))

    def test_the_moose_camera_stays_at_map_origin_not_centered_on_the_moose(self):
        """A 15-tile map fills the viewport; centering on x=11 exposes wrapped map memory."""
        s = bc.ch04_moose_script(
            'UnitDef_X', '0xce', 0x9C0, (7, 4), ((9, 7), (9, 8), (14, 14)))
        self.assertIn('CAMERA2(7, 4)', s)
        self.assertNotIn('CAMERA2(11, 4)', s)
        self.assertNotIn('CAMERA2(14, 14)', s)
        moose = next(u for u in self.chap['neutral_units'] if u['id'] == 'white-moose')
        self.assertEqual(tuple(moose['camera_at']), (7, 4))

    def test_the_moose_uses_a_continuous_regular_move_queue_over_the_bridge(self):
        """The route is authored: normal movement crosses the bridge before leaving southeast."""
        route = ((9, 7), (9, 8), (14, 14))
        s = bc.ch04_moose_script('UnitDef_X', '0xce', 0x9C0, (7, 4), route)
        self.assertIn('MOVE_DEFINED(0xce)', s)
        self.assertNotIn('MOVE(0x0, 0xce', s)
        for x, y in route:
            self.assertIn('SVAL(EVT_SLOT_1, 0x%X)' % ((y << 6) | x), s)

        moose = next(u for u in self.chap['neutral_units'] if u['id'] == 'white-moose')
        self.assertEqual(tuple(map(tuple, moose['flee_route'])), route)

    def test_the_moose_beat_is_guarded_to_the_party_before_it_loads_anything(self):
        """FE8 polls the Misc list after EVERY unit's action (playerphase.c AND cp_perform.c),
        and EvCheck0B_AREA tests gActiveUnit with no faction check -- so an unguarded AREA over
        the clearing fires for a Revenant on turn 1. Filmed happening (recordch04reveal).

        The guard must come FIRST: everything after it loads the moose, seizes the camera and
        talks. And it must be the un-trigger form, not a bare ENDA -- StartEventFromInfo sets
        the AREA's one-shot flag before calling the script, so aborting without re-arming spends
        the beat forever."""
        s = bc.ch04_moose_script(
            'UnitDef_X', '0xce', 0x9C0, (7, 4), ((9, 7), (9, 8), (14, 14)))
        self.assertIn('SVAL(EVT_SLOT_2, FACTION_ID_BLUE)', s)
        self.assertLess(s.index('CALL(EventScr_UnTriggerIfNotFaction)'),
                        s.index('LOAD1(0x1, UnitDef_X)'))

    def test_the_moose_can_actually_walk_to_the_tile_it_flees_to(self):
        """A scripted MOVE to an unwalkable tile never returns -- the event engine waits on a
        path that does not exist and the chapter hangs. The authored flee tile must be inside
        the region the moose can reach from its own clearing."""
        maps = os.path.join(bc.REPO, 'campaigns', 'rime-of-the-frostmaiden', 'maps')
        _, _, terrain = bc._map_terrain_grid(maps, bc.CH04_LAYOUT[1])
        costs = bc._class_terrain_move_costs(bc.CH04_MOOSE_MOV_TABLE)
        reachable = bc.reachable_tiles(terrain, costs, bc.CH04_MOOSE_POS)
        route = tuple(map(tuple, next(
            u for u in self.chap['neutral_units'] if u['id'] == 'white-moose')['flee_route']))
        for waypoint in route:
            self.assertIn(waypoint, reachable)
        self.assertEqual(route[-1], (14, 14))
        self.assertEqual(route[:2], ((9, 7), (9, 8)))

    def test_the_old_ne_corner_flee_tile_is_rejected(self):
        """Pins the actual trap, not just today's answer: (14, 0) is TERRAIN_PLAINS and looks
        like a fine destination, but a cliff wall seals the NE pocket off from the clearing.
        Good terrain is NOT the test -- connectivity is."""
        maps = os.path.join(bc.REPO, 'campaigns', 'rime-of-the-frostmaiden', 'maps')
        _, _, terrain = bc._map_terrain_grid(maps, bc.CH04_LAYOUT[1])
        costs = bc._class_terrain_move_costs(bc.CH04_MOOSE_MOV_TABLE)
        self.assertGreater(costs[terrain[0][14]], 0, 'the NE corner is walkable terrain')
        self.assertNotIn((14, 0), bc.reachable_tiles(terrain, costs, bc.CH04_MOOSE_POS))

    def test_the_moose_never_speaks(self):
        """Locked as a mute white ghost in ch04, re-locked in ch05: the only voice in the
        beat is the party's."""
        _, beats = bc._split_event_beats(self.chap, 'moose_sighted', 'moose',
                                         (bc.CH04_MOOSE_MSG,), card_required=False)
        speakers = [next(iter(b)) for b in beats[0]]
        self.assertNotIn('white-moose', speakers)
        self.assertNotIn('moose', speakers)
