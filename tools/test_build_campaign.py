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
import textwrap
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


class PrologueRosterFromYaml(unittest.TestCase):
    """The prologue roster is DATA, not a hardcode.

    #255's invalidation probe caught the opposite: bumping `level:` under the ch00 YAML's
    `enemy_units` moved no injected byte, and two full ROM builds -- edited and not --
    came out byte-identical, because inject_prologue emitted literals while its comment
    claimed it read the YAML. The values agreed by hand, so nothing looked wrong; a
    rebalance authored in YAML would simply not have shipped. These pin the wiring.
    """

    SLOTS = ('Eirika', 'Seth', 'ONeill')
    CLASSES = ('CLASS_FIGHTER', 'CLASS_HERO')
    GUEST_ITEMS = ('ITEM_AXE_HANDAXE, ITEM_VULNERARY', 'ITEM_SWORD_STEEL, ITEM_AXE_HANDAXE')

    def by_id(self, **over):
        units = {
            'hlin-trollbane': {'level': 3, 'position': [8, 5]},
            'scramsax': {'level': 1, 'position': [13, 9]},
            'sephek-kaltro': {'level': 5, 'position': [14, 8],
                              'inventory': [{'id': 'ice-longsword',
                                             'fe_base': 'steel-sword'}]},
            'caravan-guard': {'level': 2, 'count': 2, 'positions': [[14, 7], [13, 7]],
                              'inventory': [{'id': 'iron-axe'}]},
        }
        for uid, fields in over.items():                 # kwarg ids use _ for -
            units[uid.replace('_', '-')].update(fields)
        return units

    def blocks(self, **over):
        return bc._prologue_roster_blocks(self.by_id(**over), self.SLOTS, self.CLASSES,
                                          self.GUEST_ITEMS)

    def test_boss_level_tracks_the_yaml(self):
        self.assertIn('.level = 5,', self.blocks()[1])
        self.assertIn('.level = 6,', self.blocks(sephek_kaltro={'level': 6})[1])

    def test_boss_position_tracks_the_yaml(self):
        enemy = self.blocks(sephek_kaltro={'position': [3, 4]})[1]
        self.assertIn('.xPosition = 3,', enemy)
        self.assertIn('.yPosition = 4,', enemy)

    def test_boss_weapon_still_tracks_the_yaml(self):
        # #52's wiring, kept: the flavor "ice-longsword" resolves through fe_base.
        self.assertIn('ITEM_SWORD_STEEL', self.blocks()[1])

    def test_guest_level_and_position_track_the_yaml(self):
        ally = self.blocks(hlin_trollbane={'level': 4, 'position': [1, 2]})[0]
        self.assertIn('.level = 4,', ally)
        self.assertIn('.xPosition = 1,', ally)
        self.assertIn('.yPosition = 2,', ally)

    def test_guard_count_drives_how_many_are_emitted(self):
        self.assertEqual(self.blocks()[1].count('CLASS_FIGHTER'), 2)
        one = self.blocks(caravan_guard={'count': 1, 'positions': [[14, 7]]})[1]
        self.assertEqual(one.count('CLASS_FIGHTER'), 1)

    def test_guard_count_disagreeing_with_positions_is_fatal(self):
        # Silently emitting `count` guards at the first `count` positions would ship a
        # roster nobody authored. Fail the build instead.
        with self.assertRaises(SystemExit):
            self.blocks(caravan_guard={'count': 3})

    def test_more_guards_than_spare_slots_is_fatal(self):
        with self.assertRaises(SystemExit):
            self.blocks(caravan_guard={'count': 3, 'positions': [[1, 1], [2, 2], [3, 3]]})


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

    def test_every_classed_cast_member_has_a_test_loadout(self):
        # inject_test_chapter walks the WHOLE PORTRAIT_MAP and sys.exits on the first class
        # with no CLASS_LOADOUT row -- so a cast member's class change can break the art bench
        # (recordcast/recordanim) without touching a single chapter. Caught exactly that when
        # Basil moved Priest -> Cleric (2026-08-08): CLASS_CLERIC had no row, and ch05's own
        # guard could not see it because Basil is recruited IN ch05 and so is not on its field
        # roster. Assert the invariant, not the one class that happened to be missing.
        allcast, _ = bc._classed_cast(self.CAMPAIGN)   # available_at=None -> everyone
        missing = sorted({ce for _uid, _slot, ce, *_ in allcast if ce not in bc.CLASS_LOADOUT})
        self.assertEqual(missing, [], 'classed cast members with no CLASS_LOADOUT row')

    def test_thief_loadout_and_testch_covers_the_whole_cast(self):
        # inject_test_chapter needs a Thief loadout + one spawn tile per classed cast member
        # (13 now: 8 founding + Baxby + Trex + Lupin + ch05's Basil and Sahnar); both would
        # sys.exit otherwise.
        self.assertIn('CLASS_THIEF', bc.CLASS_LOADOUT)
        allcast, _ = bc._classed_cast(self.CAMPAIGN)   # available_at=None -> everyone
        self.assertEqual(len(allcast), 13)
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

    def test_bishop_donor_binds_staff_light_and_unarmed_to_one_anim(self):
        # ITYPE_ITEM joined on the #25 review: the vanilla Bishop AnimConf carries five slots
        # and ITEM is the UNARMED entry, reachable with both staves spent. Left vanilla, a
        # healer with only a Vulnerary draws a HUMAN BISHOP in the close-up -- the cavalier
        # row's #206 defect. ANIMA/DARK stay vanilla on purpose: this line can equip neither.
        donor_class, wtype, motion, cadence = bc.BANIM_DONORS['bishop']
        self.assertEqual(donor_class, 'CLASS_BISHOP')
        self.assertEqual(motion, 'magic')
        self.assertEqual(wtype, ['0x0100 | ITYPE_STAFF', '0x0100 | ITYPE_LIGHT',
                                 '0x0100 | ITYPE_ITEM'])
        # A Bishop-shaped AnimConf fixture: the three slots we repoint, at vanilla indices.
        src = ('CONST_DATA struct BattleAnimDef AnimConf_SRC[] = {\n'
               '    { .wtype = 0x0100 | ITYPE_STAFF, .index = 0x0082, },\n'
               '    { .wtype = 0x0100 | ITYPE_LIGHT, .index = 0x0082, },\n'
               '    { .wtype = 0x0100 | ITYPE_ITEM, .index = 0x0081, },\n'
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

    def test_basil_gold_tint_covers_both_staff_and_light(self):
        # Basil reuses Sclorbo's Bishop donor, so without a tint of his own the army's two
        # healers would cast the SAME cyan -- the one thing the healer split is meant to make
        # visible at a glance. Gold is cyan's mirror (red+green high, blue suppressed) and
        # reads as the goodberry warmth. Same weapon_types list: heal now, Light post-promo.
        rows = bc.battle_spell_palette_tints(self.CAMPAIGN)
        self.assertIn(('CHARACTER_ARTUR', 'ITYPE_STAFF', 'BANIM_SPELL_TINT_GOLD'), rows)
        self.assertIn(('CHARACTER_ARTUR', 'ITYPE_LIGHT', 'BANIM_SPELL_TINT_GOLD'), rows)

    def test_gold_is_a_real_engine_tint_not_a_silent_fallthrough(self):
        # The dispatch in BanimSpellPaletteCopy ends in `else -> Green`, so a colour that is
        # named in YAML and enumerated but NOT branched on would compile, run, and quietly
        # cast GREEN. That failure has no symptom to read, so it gets a test.
        hooks = open(os.path.join(bc.REPO, 'tools', 'inject', 'engine_hooks.py'),
                     encoding='utf-8').read()
        self.assertIn('BANIM_SPELL_TINT_GOLD = 4', hooks)
        self.assertIn('static u16 BanimSpellTintGold(u16 color)', hooks)
        self.assertIn('gMSSpellTint == BANIM_SPELL_TINT_GOLD', hooks)

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
        s = bc.village_script(0x9C3, 'ITEM_AXE_IRON', bc.CH04_OPENING_FOREST_BG)
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
        self.assertEqual([7, 36, 11], tiles,
                         'the snag must use vanilla Ch4\'s three-cell downed-log composition')
        self.assertEqual(ids['TERRAIN_BRIDGE_SNAG'], tileset.terrain(tiles[1]),
                         'the middle cell must remain a fallen snag, not a generic bridge')
        # ...and every tile it writes must be PAINTED. snowy-bern declares BRIDGE_SNAG on an
        # unpainted metatile; using it left a black square in the river with a perfectly correct
        # terrain byte, which no data check would have caught (#214).
        for m in tiles:
            self.assertFalse(bc._is_blank_metatile(tileset, m),
                             'map change writes blank metatile %d' % m)

    def test_preferred_snowy_metatile_must_be_painted(self):
        """A preferred slot is only a hint: terrain-correct but blank art must fall back to
        the first painted metatile, just like the ordinary terrain search."""
        want = bc.terrain_ids()['TERRAIN_BRIDGE_SNAG']

        class FakeTileset:
            def terrain(self, metatile):
                return want if metatile in (5, 7) else 0

            def metatile_image(self, metatile):
                pixels = [(0, 0, 0)] * 255
                pixels.append((1, 1, 1) if metatile == 7 else (0, 0, 0))
                image = Image.new('RGB', (16, 16))
                image.putdata(pixels)
                return image

        self.assertEqual(
            7,
            bc._snowy_metatile_for(FakeTileset(), 'TERRAIN_BRIDGE_SNAG', prefer=5),
        )

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
        s = bc.village_script(0x9C6, None, 'BG_MS_LONELYWOOD_FOG')
        self.assertIn('Text_BG(BG_MS_LONELYWOOD_FOG, 0x9C6)', s)

    def test_a_village_with_no_reward_hands_over_nothing(self):
        """ch04's economy is deliberately Ch4-lean (decisions.md): the Iron Axe is the whole
        material gift, so the cottage's reward IS its line. The script must drop the give-item
        tail rather than quietly hand over some default."""
        s = bc.village_script(0x9C6, None, bc.CH04_OPENING_FOREST_BG)
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
        self.assertEqual(bc.parley_recruiters(bc._ch04_reveal_wave(self._chap())),
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
            bc.parley_recruiters(bc._ch04_reveal_wave(self._chap())), bc.CH04_HOST_INDEX)
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


class Ch05ReliquaryVisits(unittest.TestCase):
    """The four reward sites are a TOMB, so their speakers are the tomb's own risen dead (#25).

    Two things here can break silently and neither shows up in a build log: a resident's
    portrait slot colliding with a cast member's (dressing a slot is GLOBAL, so the collision
    would repaint someone else's face in another chapter), and the visit ids drifting out of
    ch05's claim (the #196 defect, where a beat displayed an id another chapter writes).
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return bc._load_chapter_yaml(self.CAMPAIGN, bc.CH05_CHAPTER_YAML)

    def test_every_site_has_a_line_and_a_face(self):
        for village in self._chap()['villages']:
            self.assertTrue(village.get('visit_text'),
                            '%s has no line to show' % village['id'])
            self.assertIn(village['id'], bc.CH05_VILLAGE_SLOTS)
            self.assertIn(village['id'], bc.CH05_VISIT_FACES,
                          '%s would play faceless -- a message with no [LoadFace] renders '
                          'boxless' % village['id'])

    def test_the_residents_ride_collision_free_portrait_slots(self):
        """Overwriting a portrait slot's graphics is global, so 'free' has to mean free
        everywhere -- not merely absent from PORTRAIT_MAP."""
        slots = [slot for _, slot, _ in bc.CH05_VISIT_FACES.values()]
        self.assertEqual(len(slots), len(set(slots)), 'two residents share one slot')
        taken = (set(bc.PORTRAIT_MAP.values()) | set(bc.GUEST_PORTRAIT_MAP.values())
                 | set(bc.CH02_CHWINGA_PORTRAIT_SLOT.values()))
        self.assertFalse(set(slots) & taken,
                         'a resident is dressing a slot someone else already wears')
        # The villager mugs our other chapters SPEAK with, by FID -- ch02's fisher, ch03's
        # crier, ch04's Nimsy and logger. Repainting one of those would change a face in a
        # chapter that has nothing to do with the tomb.
        spoken_for = {bc.CH02_FISHER_FID, bc.CH03_CRIER_FID, bc.CH04_NIMSY_FID,
                      '[FID_VillagerMan3]'}
        for _, _, fid in bc.CH05_VILLAGE_SLOTS.values():
            self.assertNotIn(fid, spoken_for,
                             '%s is already another chapter\'s speaker' % fid)

    def test_every_dressed_slot_gets_its_geometry_normalized(self):
        """Dressing a slot and normalizing its mouth/eye window are two steps, and missing the
        second is SILENT -- green build, passing scenario, corrupted face. It shipped that way
        for the ch02 chwinga and for three of the four ch05 residents: the engine painted the
        blink/talk overlay at the vanilla character's mouth coords, smearing a block of skull
        over the eye sockets. Whatever the next dressed slot is, it has to land in this set.
        """
        normalized = set(bc.dressed_portrait_slots(self.CAMPAIGN))
        for vid, (_mug, slot, _rc) in bc.CH05_VISIT_FACES.items():
            self.assertIn(slot, normalized, '%s dresses %s but never normalizes it' % (vid, slot))
        for slot in bc.CH02_CHWINGA_PORTRAIT_SLOT.values():
            self.assertIn(slot, normalized, 'chwinga slot %s is dressed but not normalized' % slot)
        self.assertLessEqual(set(bc.PORTRAIT_MAP.values()), normalized)

    def test_ch05_claims_the_ids_it_writes(self):
        """These sit OUTSIDE ch05's host block on purpose (see CH05_VILLAGE_SLOTS), which is
        exactly the shape of the #196 defect -- so the claim is what makes it legal."""
        claimed = set(bc.HOSTED_CHAPTER_MESSAGE_IDS['ch05'])
        for vid, (_symbol, msg, _fid) in bc.CH05_VILLAGE_SLOTS.items():
            self.assertIn(msg, claimed, '%s writes 0x%X but ch05 never claims it' % (vid, msg))
        bc.assert_message_ids_unique()   # and nobody else claims them

    def test_the_authored_boxes_survive_as_a_presses(self):
        """One `visit_text` entry per BOX (ch04's lesson): the pacing IS the A-press breaks,
        and 25 boxes against vanilla Ch5's own 26 is the budget this pass was written to."""
        chap = self._chap()
        total = 0
        for village in chap['villages']:
            boxes = bc.village_boxes(village)
            self.assertEqual(len(boxes), len(village['visit_text']))
            for box in boxes:
                self.assertLessEqual(len(textwrap.wrap(box, 42)), 2,
                                     '%s: box over two lines at the Text_BG wrap: %r'
                                     % (village['id'], box))
            total += len(boxes)
        self.assertEqual(25, total)

    def test_a_vendored_mug_converts_to_an_fe8_bust(self):
        """The community sheets do not agree on a background key -- Glaceo's set uses one green
        and Eden/L95's another -- so the converter reads the corner pixel. Hardcoding either
        leaves a green box behind the other artist's faces."""
        vendor = os.path.join(bc._bust_dir(self.CAMPAIGN), 'vendor')
        for vid, (mug, _slot, recolor) in sorted(bc.CH05_VISIT_FACES.items()):
            path = os.path.join(vendor, mug)
            self.assertTrue(os.path.isfile(path), 'missing vendored mug for %s' % vid)
            bust = bc._vendor_mug_to_bust(path, recolor)
            self.assertEqual('P', bust.mode)
            self.assertEqual((96, 80), bust.size)
            palette = bust.getpalette()[:48]
            self.assertEqual(list(bc.PORTRAIT_TRANSPARENT_RGB), palette[:3],
                             '%s: index 0 must be the transparent key' % vid)
            self.assertLessEqual(len(set(bust.getdata())), 16)

    def test_the_two_shared_body_skeletons_are_told_apart(self):
        """reliquary-east and -south are the SAME mug with a different jaw, so without a
        recolor the player meets one man twice. Only the two true oranges may move: the third
        tone in that ramp is also the skull's shadow, and recolouring it turns his teeth green.
        """
        vendor = os.path.join(bc._bust_dir(self.CAMPAIGN), 'vendor')
        east = bc._vendor_mug_to_bust(
            os.path.join(vendor, bc.CH05_VISIT_FACES['reliquary-east'][0]), None)
        mug, _slot, recolor = bc.CH05_VISIT_FACES['reliquary-south']
        self.assertTrue(recolor, 'the south resident needs a recolor or he is the east one')
        south = bc._vendor_mug_to_bust(os.path.join(vendor, mug), recolor)
        self.assertNotEqual(list(east.convert('RGB').getdata()),
                            list(south.convert('RGB').getdata()))
        # The skull's shadow tone stays put -- it is not part of the pauldron ramp.
        self.assertNotIn((152, 112, 72), recolor)
        south_rgb = set(south.convert('RGB').getdata())
        self.assertIn((152, 112, 72), south_rgb, 'the skull shading was recoloured away')


class RavisinPortrait(unittest.TestCase):
    """Ravisin is a named raw-pid boss, not a cast member (#19 / #25).

    Her approved art is a deterministic palette edit of Garytop's FE-Repo Aversa mug.
    The source sheet stays the authority; the derived bust may change colours only, never
    geometry. Because her on-map pid is 0xb8 rather than a CHARACTER_* identity slot, the
    raw CharacterData entry also needs an explicit portraitId or battle/status screens remain
    faceless even after the Riev portrait graphics are dressed.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_approved_vendor_palette_edit_changes_only_declared_colours(self):
        bust_dir = bc._bust_dir(self.CAMPAIGN)
        source = os.path.join(bust_dir, 'vendor', bc.RAVISIN_VENDOR_MUG)
        derived = os.path.join(bust_dir, 'ravisin.png')
        self.assertTrue(os.path.isfile(source), 'missing vendored FE-Repo Aversa source')
        self.assertTrue(os.path.isfile(derived), 'missing deterministic Ravisin bust')

        src = Image.open(source).convert('RGB').crop((0, 0, 96, 80))
        got = Image.open(derived)
        self.assertEqual(('P', (96, 80)), (got.mode, got.size))
        self.assertLessEqual(len(set(got.getdata())), 16)
        transparent_key = src.getpixel((0, 0))
        expected = [
            bc.PORTRAIT_TRANSPARENT_RGB
            if pixel == transparent_key
            else bc.RAVISIN_RECOLOR.get(pixel, pixel)
            for pixel in src.getdata()
        ]
        self.assertEqual(expected, list(got.convert('RGB').getdata()),
                         'Ravisin must be an exact palette substitution, never redrawn pixels')
        self.assertEqual(0, sum(bc.portrait_tool.clipped_mask(got)),
                         'the approved crown/mantle must clear FE8\'s portrait dead zone')

    def test_ravisin_dresses_collision_free_riev_and_normalizes_its_geometry(self):
        self.assertEqual('Riev', bc.GUEST_PORTRAIT_MAP['ravisin'])
        self.assertEqual(('ravisin', 'Riev', 0x48, 'Ravisin'),
                         bc.RAW_PID_PORTRAITS[bc.CH05_BOSS_PID])
        slots = list(bc.PORTRAIT_MAP.values()) + list(bc.GUEST_PORTRAIT_MAP.values())
        self.assertEqual(len(slots), len(set(slots)), 'Ravisin collides with another portrait')
        self.assertIn('Riev', bc.dressed_portrait_slots(self.CAMPAIGN),
                      'dressed Riev slot would keep its vanilla mouth/eye geometry')

    def test_raw_boss_pid_gets_the_riev_identity(self):
        source = '''[0xb8 - 1] = {
        .nameTextId = 0x255,
        .defaultClass = CLASS_ARCH_MOGALL,
        .miniPortrait = 0x4,
        .baseHP = 0,
        .basePow = 0,
        .baseSkl = 0,
        .baseSpd = 0,
        .baseDef = 0,
        .baseRes = 0,
        .baseLck = 0,
        .baseCon = 0,
    },'''
        patched = bc.raw_pid_portrait_data(source, self.CAMPAIGN)
        self.assertIn('.nameTextId = 0x246,', patched)
        self.assertNotIn('.nameTextId = 0x255,', patched)
        self.assertIn('.portraitId = 0x48,', patched)
        self.assertEqual(1, patched.count('.portraitId'))
        self.assertIn('.miniPortrait = 0x4,', patched)

        ravisin = next(enemy for enemy in bc._load_chapter_yaml(
            self.CAMPAIGN, bc.CH05_CHAPTER_YAML)['enemy_units']
            if enemy['id'] == 'ravisin')
        for field in bc.BASE_FIELDS:
            self.assertIn('.%s = %d,' % (field, ravisin['personal'].get(field, 0)), patched)

    def test_name_injector_retitles_the_repurposed_riev_slot(self):
        with tempfile.TemporaryDirectory() as tmp:
            texts = os.path.join(tmp, 'texts.txt')
            with open(texts, 'w', encoding='utf-8') as f:
                f.write(bc.vanilla_decomp_text('texts/texts.txt'))
            with mock.patch.object(bc, 'TEXTS_TXT', texts):
                bc.inject_names(self.CAMPAIGN, verbose=False)
            with open(texts, encoding='utf-8') as f:
                written = f.read()
        body = re.search(r'## MSG_246\n(.*?)(?=\n## MSG_)', written, re.S).group(1)
        self.assertEqual('Ravisin[.][X]', body.strip())


class Ch05EruptionWarning(unittest.TestCase):
    """The turn-2 race warning belongs to ch05's HOST block, not its vanilla-Ch5 twin.

    The YAML label ``vanilla 0x9C5`` describes scene anatomy. Literal 0x9C5 is ch04's
    status-objective string, so using it here silently overwrites another chapter while
    every text decoder remains green. The warning also has to precede Sahnar's LOAD: the
    final locked box is Ravisin deciding to use the blade under the stone.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return bc._load_chapter_yaml(self.CAMPAIGN, bc.CH05_CHAPTER_YAML)

    def test_warning_owns_a_named_id_from_ch05s_real_host_block(self):
        self.assertTrue(hasattr(bc, 'CH05_ERUPTION_MSG'),
                        'ch05 needs a named host-block id for the eruption warning')
        self.assertEqual(0x9E4, bc.CH05_ERUPTION_MSG)
        self.assertTrue(0x9E4 <= bc.CH05_ERUPTION_MSG <= 0x9F3)
        self.assertNotEqual(bc.CH04_GOAL_STATUS_MSG, bc.CH05_ERUPTION_MSG)
        self.assertIn(bc.CH05_ERUPTION_MSG, bc.HOSTED_CHAPTER_MESSAGE_IDS['ch05'])
        self.assertEqual('ch05', bc.assert_message_ids_unique()[bc.CH05_ERUPTION_MSG])

    def test_locked_four_boxes_emit_one_faced_ravisin_message(self):
        self.assertTrue(hasattr(bc, 'ch05_eruption_message'),
                        'the locked YAML beat needs a message emitter')
        event = next(e for e in self._chap()['events'] if e['trigger'] == 'eruption_turn')
        self.assertEqual(4, len(event['script']))
        self.assertEqual({'ravisin'}, {next(iter(box)) for box in event['script']})
        for box in event['script']:
            self.assertLessEqual(len(bc._wrap_fe_lines(next(iter(box.values())), 29)), 2)

        body = bc.ch05_eruption_message(self._chap())
        self.assertIn('[LoadFace][FID_Riev]', body)
        self.assertEqual(4, body.count('[A]'))
        for box in event['script']:
            for word in next(iter(box.values())).replace("'", '').split()[:3]:
                self.assertIn(word, body)

    def test_turn_two_stages_the_arriving_dead_before_the_warning(self):
        self.assertTrue(hasattr(bc, 'ch05_wave_script'),
                        'the wave script needs a testable owner for its ordering')
        script = bc.ch05_wave_script(2, 'MS_Ch05WaveT2')
        self.assertEqual(1, script.count('TEXTSHOW(0x%X)' % bc.CH05_ERUPTION_MSG))
        self.assertIn('CUMO_CHAR(%s)' % bc.CH05_BOSS_PID, script)
        self.assertLess(script.index('LOAD1(0x1, MS_Ch05WaveT2)'),
                        script.index('CUMO_CHAR(%s)' % bc.CH05_BOSS_PID))
        self.assertLess(script.index('CUMO_CHAR(%s)' % bc.CH05_BOSS_PID),
                        script.index('TEXTSHOW(0x%X)' % bc.CH05_ERUPTION_MSG))

    def test_the_eruption_no_longer_raises_sahnar(self):
        """She is summoned ON SCREEN by Ravisin in scene 3 and stands on the arena from turn 1
        (#25, 2026-08-14) -- vanilla's own shape, where Joshua LOADs after the prep CALL. The
        eruption keeps its six reinforcements; a LOAD of her table here would put a second
        Sahnar on the board."""
        for turn in (2, 3, 5):
            script = bc.ch05_wave_script(turn, 'MS_Ch05WaveT%d' % turn)
            self.assertNotIn(bc.CH05_SAHNAR_TABLE, script)

    def test_later_waves_do_not_repeat_the_turn_two_warning(self):
        self.assertTrue(hasattr(bc, 'ch05_wave_script'),
                        'the wave script needs a testable owner for its ordering')
        for turn in (3, 5):
            script = bc.ch05_wave_script(turn, 'MS_Ch05WaveT%d' % turn)
            self.assertNotIn('TEXTSHOW(', script)
            self.assertNotIn('CUMO_CHAR(', script)


class Ch05RavisinDeathQuote(unittest.TestCase):
    """Ravisin's locked death box speaks without changing the DefeatBoss flag path."""
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return bc._load_chapter_yaml(self.CAMPAIGN, bc.CH05_CHAPTER_YAML)

    def _event(self):
        return next(e for e in self._chap()['events'] if e['trigger'] == 'boss_death')

    def test_death_quote_owns_the_next_named_id_in_ch05s_real_host_block(self):
        self.assertTrue(hasattr(bc, 'CH05_RAVISIN_DEATH_MSG'),
                        'Ravisin needs a named host-block id for her death quote')
        self.assertEqual(0x9E5, bc.CH05_RAVISIN_DEATH_MSG)
        self.assertTrue(0x9E4 <= bc.CH05_RAVISIN_DEATH_MSG <= 0x9F3)
        self.assertIn(bc.CH05_RAVISIN_DEATH_MSG, bc.HOSTED_CHAPTER_MESSAGE_IDS['ch05'])
        self.assertEqual('ch05', bc.assert_message_ids_unique()[bc.CH05_RAVISIN_DEATH_MSG])

    def test_locked_one_box_emits_ravisins_live_face_from_the_event_yaml(self):
        event = self._event()
        self.assertEqual('vanilla 0x9C8', event['slot'])
        self.assertEqual([{'ravisin': 'Frostmaiden... the winter is yours...'}], event['script'])
        self.assertTrue(hasattr(bc, 'ch05_ravisin_death_message'),
                        'the locked YAML beat needs a message emitter')

        body = bc.ch05_ravisin_death_message(self._chap())
        flowed = body.replace('[LF]\n', ' ')
        self.assertIn('[LoadFace][FID_Riev]', body)
        self.assertEqual(1, body.count('[A]'))
        self.assertIn('Frostmaiden', flowed)
        self.assertIn('the winter is yours', flowed)
        self.assertNotIn('I gave you everything', flowed)

    def test_flagged_defeat_entry_shows_the_quote_and_preserves_the_win_flag(self):
        self.assertTrue(hasattr(bc, 'ch05_ravisin_defeat_quote'),
                        'ch05 needs a testable owner for Ravisin defeat-talk wiring')
        quote = bc.ch05_ravisin_defeat_quote()
        self.assertIn('.pid     = %s' % bc.CH05_BOSS_PID, quote)
        self.assertIn('.chapter = %s' % bc.chapter_label_constant(bc.CH05_HOST_INDEX), quote)
        self.assertIn('.flag    = EVFLAG_DEFEAT_BOSS', quote)
        self.assertIn('.msg     = 0x%X' % bc.CH05_RAVISIN_DEATH_MSG, quote)
        self.assertNotIn('.msg     = 0,', quote)


class Ch05SahnarTalkRecruit(unittest.TestCase):
    """The chapter's payoff: Basil chaperoned across turns the risen Sahnar (#25).

    This scene shipped WIRED and UNWRITTEN for months, pointed at vanilla 0x9CC -- the
    Natasha->Joshua recruit ours is the twin of. On paper that is the legitimate placeholder
    pattern; on screen it was a bug, because our speakers wear the Artur and Marisa slots
    while 0x9CC loads Natasha's and Joshua's. What the player saw was Hlin Trollbane's bust
    (dressed onto the Natasha slot) talking to vanilla Joshua. So the face assertions below
    are the regression, not decoration: a decoder is green either way.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return bc._load_chapter_yaml(self.CAMPAIGN, bc.CH05_CHAPTER_YAML)

    def _event(self):
        return next(e for e in self._chap()['events'] if e['trigger'] == 'sahnar_talk')

    def test_talk_moved_off_vanillas_id_into_ch05s_real_host_block(self):
        self.assertNotEqual(0x9CC, bc.CH05_SAHNAR_TALK_MSG,
                            'the Talk still reads vanilla Ch5 prose in vanilla Ch5 faces')
        self.assertEqual(0x9E8, bc.CH05_SAHNAR_TALK_MSG)
        self.assertTrue(0x9E4 <= bc.CH05_SAHNAR_TALK_MSG <= 0x9F3)
        self.assertIn(bc.CH05_SAHNAR_TALK_MSG, bc.HOSTED_CHAPTER_MESSAGE_IDS['ch05'])
        self.assertEqual('ch05', bc.assert_message_ids_unique()[bc.CH05_SAHNAR_TALK_MSG])

    def test_the_yaml_slot_label_stays_an_anatomy_citation(self):
        """`vanilla 0x9CC` names the scene we MINE. It is not a destination -- and leaving the
        label alone while moving the id is the whole point of the two being different fields."""
        self.assertEqual('vanilla 0x9CC', self._event()['slot'])

    def test_locked_sixteen_boxes_emit_our_two_faces_and_never_vanillas(self):
        event = self._event()
        self.assertEqual(16, len(event['script']))
        self.assertEqual({'sahnar', 'basil'}, {next(iter(box)) for box in event['script']})

        body = bc.ch05_sahnar_talk_message(self._chap())
        self.assertIn('[LoadFace][FID_Artur]', body)     # Basil
        self.assertIn('[LoadFace][FID_Marisa]', body)    # Sahnar
        self.assertNotIn('[FID_Natasha]', body)          # the bug: Hlin's dressed slot
        self.assertNotIn('[FID_Joshua]', body)           # the bug: vanilla's recruit
        # Prose flowed free of every text code: the authored sentences straddle both the
        # [LF] line break and the [A] page break, so asserting on either shape asserts on the
        # wrap rather than on the words.
        prose = ' '.join(re.sub(r'\[[^\]]*\]', ' ', body).split())
        self.assertIn('...Basil?', prose)                # the recognition IS the word
        self.assertIn('Only my true enemy has been revealed', prose)
        self.assertIn('Can I give you a berry now?', prose)    # last box, deliberately unanswered

    def test_the_two_shot_stages_recruiter_left_and_the_turned_unit_right(self):
        """ch04's parley idiom: the recruiter holds the party's side, the unit being turned
        holds the other, so neither podium swaps faces mid-scene."""
        body = bc.ch05_sahnar_talk_message(self._chap())
        self.assertIn('[OpenMidLeft][LoadFace][FID_Artur]', body)
        self.assertIn('[OpenMidRight][LoadFace][FID_Marisa]', body)
        self.assertNotIn('[ClearFace]', body)

    def test_every_box_fits_the_map_talk_bubble(self):
        """The Talk rides TEXTSHOW -> PutTalkBubble, whose right-side branch computes
        x = 29 - width with no clamp: a line over 29 runs off the tilemap (the ch03 crier bug)."""
        body = bc.ch05_sahnar_talk_message(self._chap())
        for line in body.split('\n'):
            printable = re.sub(r'\[[^\]]*\]', '', line)
            self.assertLessEqual(len(printable), 29, 'bubble overflow: %r' % line)

    def test_talk_script_shows_the_moved_id_then_flips_sahnar_blue(self):
        _chars, script = bc.talk_recruit_wiring(
            ['CHARACTER_ARTUR'], 'CHARACTER_MARISA', bc.CH05_SAHNAR_TALK_FLAG,
            bc.CH05_SAHNAR_TALK_SCRIPT, bc.CH05_SAHNAR_TALK_MSG)
        self.assertIn('TEXTSHOW(0x%X)' % bc.CH05_SAHNAR_TALK_MSG, script)
        self.assertNotIn('TEXTSHOW(0x9CC)', script)
        self.assertLess(script.index('TEXTSHOW(0x%X)' % bc.CH05_SAHNAR_TALK_MSG),
                        script.index('CUSA(CHARACTER_MARISA)'))


class Ch05OpeningBackdropScenes(unittest.TestCase):
    """ch05's opening plays three locked scenes at the tomb before the party arrives (#25).

    The chapter shipped with `CH05_BEGINNING_SCRIPT` running LOMA -> the line LOAD1s -> prep
    -> the join, SILENTLY: our own script, with no TEXTSHOW anywhere in it. These are the
    first three of the eleven scenes #25 still owed.

    CHANNEL is inherited rather than chosen. Vanilla Ch5's BeginningScene plays 0x9BA-0x9BE
    over a backdrop and only reaches TEXTSTART (on-map bubbles) once the party is physically
    on the street, so our twins are backdrop scenes too -- which is also the only thing that
    CAN work this early, PutTalkBubble having no staged unit to anchor to.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return bc._load_chapter_yaml(self.CAMPAIGN, bc.CH05_CHAPTER_YAML)

    def test_the_three_ids_are_owned_unique_and_inside_ch05s_host_block(self):
        self.assertEqual([0x9E9, 0x9EA, 0x9EB],
                         [msg for _s, msg, _b, _w in bc.CH05_OPENING_SLOTS])
        claimed = set(bc.HOSTED_CHAPTER_MESSAGE_IDS['ch05'])
        owner = bc.assert_message_ids_unique()
        for _slot, msg, _boxes, _what in bc.CH05_OPENING_SLOTS:
            self.assertTrue(0x9E4 <= msg <= 0x9F3, 'outside ch05\'s Ch6 host block')
            self.assertIn(msg, claimed)
            self.assertEqual('ch05', owner[msg])

    def test_the_yaml_slot_labels_stay_anatomy_citations(self):
        """`vanilla 0x9BB` names the scene we MINE. ch04 hosts on slot 5 and WRITES that id --
        pointing a ch05 scene at it would play ch04's text in ch04's faces."""
        for slot, msg, _boxes, _what in bc.CH05_OPENING_SLOTS:
            self.assertNotEqual(int(slot.split()[1], 16), msg)
            self.assertIn(int(slot.split()[1], 16),
                          bc.HOSTED_CHAPTER_MESSAGE_IDS['ch04'])

    def test_each_scene_keeps_its_locked_box_count_and_speakers(self):
        chap = self._chap()
        expected = {'vanilla 0x9BB': (19, {'basil', 'sahnar'}),
                    'vanilla 0x9BC': (16, {'sephek', 'ravisin'}),
                    'vanilla 0x9BD': (7, {'ravisin', 'basil'})}
        for slot, _msg, boxes, _what in bc.CH05_OPENING_SLOTS:
            script = bc._chapter_event_by_slot(chap, 'chapter_start', slot, 'test')['script']
            want_boxes, want_speakers = expected[slot]
            self.assertEqual(want_boxes, boxes, '%s: table box count' % slot)
            # Box count excludes stage directions (`exits:`): they cost no A-press.
            self.assertEqual(want_boxes, bc._script_box_count(script),
                             '%s: YAML box count' % slot)
            self.assertEqual(want_speakers,
                             {next(iter(b)) for b in script
                              if next(iter(b)) not in bc.SCRIPT_DIRECTIVES})

    def test_every_speaker_wears_our_face_and_never_the_donor_slots_own(self):
        """The #276 regression, one scene earlier: our cast wears vanilla slots, so a scene
        pointed at the wrong id plays the DONOR's face and words and every decoder stays green."""
        bodies = dict(bc.ch05_opening_messages(self._chap()))
        self.assertIn('[LoadFace][FID_Artur]', bodies[0x9E9])       # Basil
        self.assertIn('[LoadFace][FID_Marisa]', bodies[0x9E9])      # Sahnar
        self.assertIn('[LoadFace][FID_ONeill]', bodies[0x9EA])      # Sephek Kaltro
        self.assertIn('[LoadFace][FID_Riev]', bodies[0x9EA])        # Ravisin
        self.assertIn('[LoadFace][FID_Riev]', bodies[0x9EB])
        self.assertIn('[LoadFace][FID_Artur]', bodies[0x9EB])
        for body in bodies.values():
            self.assertNotIn('[FID_Natasha]', body)   # Hlin's dressed slot, not Basil's
            self.assertNotIn('[FID_Joshua]', body)

    def test_every_face_tag_the_opening_emits_is_defined_in_textdefs(self):
        """[FID_O_Neill] is not a tag -- textdefs.txt defines [FID_ONeill]. Sephek's portrait
        SLOT is spelled 'O_Neill' in GUEST_PORTRAIT_MAP and 'ONEILL' in PROLOGUE_SEPHEK_SLOT,
        and only the second is one _fid_tag can map, so the wrong source emits a tag the ROM
        has no face for. Caught here because nothing downstream complains: this is the same
        shape as #276, where every text decoder was green while the wrong face was on screen."""
        defined = set(re.findall(r'^\[(FID_\w+)\]',
                                 bc.vanilla_decomp_text('texts/textdefs.txt'), re.M))
        self.assertIn('FID_ONeill', defined)          # the fixture is real
        self.assertNotIn('FID_O_Neill', defined)      # and the near-miss is not
        for msg, body in bc.ch05_opening_messages(self._chap()):
            for tag in re.findall(r'\[(FID_\w+)\]', body):
                self.assertIn(tag, defined, '0x%X emits an undefined face tag' % msg)
        # BOTH spellings of every guest slot must resolve, not just the one this scene happens
        # to use -- otherwise the next scene to reach a guest through _cutscene_fid's
        # GUEST_PORTRAIT_MAP fallback re-opens the same silent hole.
        for unit, slot in bc.GUEST_PORTRAIT_MAP.items():
            for spelling in (slot, slot.upper()):
                tag = bc._fid_tag(spelling).strip('[]')
                self.assertIn(tag, defined,
                              '%s (slot %r via %r) resolves to an undefined face tag %s'
                              % (unit, slot, spelling, tag))

    def test_a_speaker_holds_one_SIDE_across_the_whole_opening(self):
        """Ravisin speaks in scene 2 and again in scene 3, its immediate sequel. A per-scene
        default would seat her mid-LEFT in one and mid-right in the other, and a character who
        crosses the screen between adjacent scenes reads as a different person.

        Her exact rung is allowed to shift by one and does: scene 3 raises Sahnar beside her, and
        two faces need an empty rung between them, so Ravisin moves MidRight -> Right to open
        FarRight up (see `assert_silent_faces_have_elbow_room`). That costs nothing on screen --
        the two scenes are separate messages with a full fade through black between them, so
        there is no visible move. Vanilla makes the same shift WITHIN a message, and has to
        animate it (`[OpenMidRight][MoveRight]`, MSG_904)."""
        bodies = dict(bc.ch05_opening_messages(self._chap()))
        right = ('[OpenRight]', '[OpenMidRight]', '[OpenFarRight]')
        for msg in (0x9EA, 0x9EB):
            self.assertTrue(
                any('%s[LoadFace][FID_Riev]' % tag in bodies[msg] for tag in right),
                'Ravisin left the right-hand side in 0x%X' % msg)
        self.assertIn('[OpenMidLeft][LoadFace][FID_Artur]', bodies[0x9E9])
        self.assertIn('[OpenMidLeft][LoadFace][FID_Artur]', bodies[0x9EB])

    def test_the_locked_prose_survives_the_wrap(self):
        bodies = dict(bc.ch05_opening_messages(self._chap()))
        prose = {m: ' '.join(re.sub(r'\[[^\]]*\]', ' ', b).split()) for m, b in bodies.items()}
        self.assertIn('I wish I could share my berries with her', prose[0x9E9])
        self.assertIn('I know old things', prose[0x9E9])
        self.assertIn('I bring the Frostmaiden\'s will', prose[0x9EA])
        self.assertIn('She was a queen\'s blade once', prose[0x9EA])
        # The warning clause, pinned because it was WRONG once and the failure was invisible:
        # "warmer than they look" reads as a dismissal, since "warm" is the cult's own word for
        # the living-and-sick (ravisin.md), so the box undercut its own "Do not take them
        # lightly". Nothing downstream can tell a warning from an insult.
        self.assertIn('tougher than they look', prose[0x9EA])
        self.assertNotIn('warmer than they look', prose[0x9EA])
        self.assertIn('It never once occurred to me she might be of use', prose[0x9EB])

    def test_the_scenes_wrap_at_the_full_screen_42_not_the_bubble_29(self):
        """These play over a BACG, where the window is full-screen. The 29 exists for
        PutTalkBubble's unclamped right edge, and there is no bubble here."""
        bodies = dict(bc.ch05_opening_messages(self._chap()))
        widest = 0
        for body in bodies.values():
            for line in body.split('\n'):
                widest = max(widest, len(re.sub(r'\[[^\]]*\]', '', line)))
        self.assertLessEqual(widest, 42)
        self.assertGreater(widest, 29, 'wrapped at the bubble width, not the scenic width')

    def test_the_block_raises_one_backdrop_plays_all_three_then_fades_out(self):
        """ONE tomb backdrop across the three tomb scenes, as vanilla spends
        BG_SERAFEW_VILLAGE on four consecutive ones. (Scene 4 then CUTS to the ridge -- a
        different place, so a second BACG; that seam is Ch05ArrivalSceneAndTheNoLupinBranch's.)"""
        block = bc.ch05_opening_backdrop_block()
        tomb = block[:block.index('BACG(%s)' % bc.CH05_ARRIVAL_BG)]
        self.assertEqual(1, tomb.count('BACG('), 'one backdrop, held across the three scenes')
        self.assertIn('BACG(%s)' % bc.CH05_OPENING_BG, block)
        self.assertLess(block.index('REMOVEPORTRAITS'), block.index('BACG('),
                        'BACG only decompresses while activeTextType is REMOVEPORTRAITS')
        self.assertLess(block.index('BACG('), block.index('FADU(16)'))
        for _slot, msg, _boxes, _what in bc.CH05_OPENING_SLOTS:
            self.assertIn('Text(0x%X)' % msg, block)
        first, last = (block.index('Text(0x%X)' % bc.CH05_OPENING_SLOTS[0][1]),
                       block.index('Text(0x%X)' % bc.CH05_OPENING_SLOTS[-1][1]))
        self.assertLess(first, last, 'scenes must run in player order')
        self.assertTrue(block.rstrip().endswith('*/'))
        self.assertIn('FADI(16)', block.rstrip().split('\n')[-1])

    def test_separate_moments_fade_through_black_between_them(self):
        """Vanilla gives each of 0x9BC/0x9BD a full Text_BG fade cycle. Played as a hard cut,
        three different moments read as one continuous conversation."""
        block = bc.ch05_opening_backdrop_block()
        tomb = block[:block.index('BACG(%s)' % bc.CH05_ARRIVAL_BG)]
        self.assertEqual(len(bc.CH05_OPENING_SLOTS), tomb.count('FADI(16)'),
                         'one fade between each pair of tomb scenes, plus the cut away')
        self.assertEqual(len(bc.CH05_OPENING_SLOTS) + 1, block.count('FADI(16)'),
                         'and one more closing the ridge out into LOMA')

    def test_the_opening_never_reaches_for_Text_BG(self):
        """Text_BG ends in EventScr_TextShowWithFadeIn -- CLEAN then FADU back onto the MAP.
        Before LOMA that map is still the host slot's, so each scene would fade up on vanilla
        Ch6's terrain."""
        self.assertNotIn('Text_BG', bc.ch05_opening_backdrop_block())

    def test_the_backdrop_is_a_registered_campaign_bg_with_a_source_png(self):
        names = [enum for enum, _stem, _credit in bc.CAMPAIGN_BGS]
        self.assertIn(bc.CH05_OPENING_BG, names)
        stem = next(s for e, s, _c in bc.CAMPAIGN_BGS if e == bc.CH05_OPENING_BG)
        png = os.path.join(bc.REPO, 'campaigns', self.CAMPAIGN, 'backgrounds', stem + '.png')
        self.assertTrue(os.path.isfile(png), png)

    def test_the_vendored_backdrop_stays_inside_the_six_banks_the_fades_apply(self):
        """Bremen is banked at 8 and cannot be shown through a fade for exactly this reason
        (HANDOFF). A BG the opening fades in AND out of has to be under that ceiling."""
        from PIL import Image
        stem = next(s for e, s, _c in bc.CAMPAIGN_BGS if e == bc.CH05_OPENING_BG)
        im = Image.open(os.path.join(bc.REPO, 'campaigns', self.CAMPAIGN,
                                     'backgrounds', stem + '.png'))
        self.assertEqual('P', im.mode)
        self.assertEqual((240, 160), im.size)
        banks = max(int(i) // 16 for i in set(im.getdata())) + 1
        self.assertLessEqual(banks, 6, '%d banks -- the fade procs apply only six' % banks)


class ASpeakerWhoLeavesMidSceneFadesOut(unittest.TestCase):
    """`exits:` is the script directive for a speaker who WALKS OFF while the scene runs on.

    Found by Nicolas watching ch05's opening (2026-08-14): Sahnar goes, and then Basil delivers
    three boxes about her absence — *"...And there she stays."* — with Sahnar still standing at
    her podium the whole time. The stage direction was in the YAML as a comment ("She goes. A few
    steps on root-feet.") and nothing rendered it.

    `_script_to_message`'s podium manager infers a face LOAD from who speaks next, but it cannot
    infer a face EXIT: nobody speaks from that podium again, so it has no reason to touch it. Its
    own docstring names this as the one control it does not infer. `[OpenX][ClearFace]` is FE8's
    own answer — scene.c fades that podium's face over ~16 frames and frees its gFaces slot.
    """
    def _msg(self, script, staging=None):
        return bc._script_to_message(script, staging or {
            'basil':  ('[OpenMidLeft]', '[FID_Artur]'),
            'sahnar': ('[OpenMidRight]', '[FID_Marisa]')}, width=42)

    def test_the_leaving_speakers_podium_is_cleared_where_she_goes(self):
        out = self._msg([{'sahnar': 'Go on, now.'},
                         {'exits': 'sahnar'},
                         {'basil': '...And there she stays.'}])
        self.assertIn('[OpenMidRight][ClearFace]', out)
        self.assertLess(out.index('[OpenMidRight][ClearFace]'),
                        out.index('...And there she stays.'),
                        'she has to be gone BEFORE the line about her being gone')

    def test_the_remaining_speaker_is_untouched(self):
        out = self._msg([{'basil': 'one'}, {'sahnar': 'two'},
                         {'exits': 'sahnar'}, {'basil': 'three'}])
        self.assertEqual(1, out.count('[FID_Artur]'), 'Basil must not be reloaded or cleared')
        self.assertNotIn('[OpenMidLeft][ClearFace]', out)

    def test_an_exit_breaks_the_same_speaker_coalescing(self):
        """Basil's boxes either side of the exit must NOT merge into one block, or the
        [ClearFace] would land after both and the fade would play too late."""
        out = self._msg([{'sahnar': 'Go on, now.'}, {'basil': 'before'},
                         {'exits': 'sahnar'}, {'basil': 'after'}])
        self.assertLess(out.index('before'), out.index('[OpenMidRight][ClearFace]'))
        self.assertLess(out.index('[OpenMidRight][ClearFace]'), out.index('after'))

    def test_a_speaker_who_returns_gets_a_fresh_face(self):
        out = self._msg([{'sahnar': 'one'}, {'exits': 'sahnar'},
                         {'basil': 'two'}, {'sahnar': 'three'}])
        self.assertEqual(2, out.count('[LoadFace][FID_Marisa]'))

    def test_exiting_someone_who_is_not_on_screen_fails_loudly(self):
        """A drifted directive is a silent no-op otherwise, which is how the bug it fixes
        got shipped in the first place."""
        with self.assertRaises(SystemExit):
            self._msg([{'basil': 'one'}, {'exits': 'sahnar'}])

    def test_the_directive_is_not_counted_as_a_box(self):
        """Box counts are locked per scene. A stage direction is not an A-press."""
        script = [{'basil': 'one'}, {'exits': 'sahnar'}, {'basil': 'two'}]
        self.assertEqual(2, bc._script_box_count(script))

    def test_ch05_scene_1_actually_carries_it(self):
        chap = bc._load_chapter_yaml('rime-of-the-frostmaiden', bc.CH05_CHAPTER_YAML)
        script = bc._chapter_event_by_slot(chap, 'chapter_start', 'vanilla 0x9BB', 'test')['script']
        exits = [i for i, e in enumerate(script) if 'exits' in e]
        self.assertEqual(1, len(exits), 'Sahnar leaves exactly once')
        self.assertEqual('sahnar', script[exits[0]]['exits'])
        self.assertEqual('...And there she stays.',
                         bc._fe_dialogue_text(next(iter(script[exits[0] + 1].values()))),
                         'the exit sits immediately before the line about her absence')
        body = dict(bc.ch05_opening_messages(chap))[0x9E9]
        self.assertLess(body.index('[OpenMidRight][ClearFace]'), body.index('And there she stays'))


class TheDashGlueRespectsTheLineWidth(unittest.TestCase):
    """`_wrap_fe_lines` keeps a bare '--' off the start of a line by gluing it to the word
    before it -- but it did that without re-measuring, so a line that ended exactly at the
    width came out two characters over. Found by ch05's scene 4, whose Wolfram line lands
    on the boundary ("...There was fighting here --" = 44 against the scenic 42), and it
    reaches every chapter: the glue is in the shared wrapper, not in any one scene.
    """
    def test_the_glued_dash_never_pushes_a_line_past_the_width(self):
        line = 'Struck off edges. There was fighting here -- a great deal of it.'
        for width in (29, 40, 41, 42, 43, 44):
            for out in bc._wrap_fe_lines(line, width):
                self.assertLessEqual(len(out), width, '%r at width %d' % (out, width))

    def test_the_width_holds_across_every_dash_position_in_a_line(self):
        """One sentence exercises one boundary. Walk the dash through every gap at every
        width near it, so the fix is not merely right for the line that found the bug."""
        words = 'Struck off edges there was fighting here a great deal of it'.split()
        for i in range(1, len(words)):
            text = ' '.join(words[:i] + ['--'] + words[i:])
            for width in range(20, 45):
                for out in bc._wrap_fe_lines(text, width):
                    if out.endswith(' --') and ' ' not in out[:-3]:
                        continue          # atomic word+dash: see the docstring's RESIDUAL
                    self.assertLessEqual(len(out), width,
                                         '%r at width %d (dash after %r)' % (out, width, words[i - 1]))

    def test_an_unfittable_word_plus_dash_stays_atomic_rather_than_splitting(self):
        """The one case the width CANNOT hold, stated so it is a known shape and not a
        surprise: the pair is indivisible, so it goes out over-width and alone. Found in
        review of the fix, which had only moved the overflow rather than removed it."""
        out = bc._wrap_fe_lines('I Auril-the-Frostmaiden-herse -- yes.', 29)
        self.assertIn('Auril-the-Frostmaiden-herse --', out)
        over = [l for l in out if len(l) > 29]
        self.assertEqual(['Auril-the-Frostmaiden-herse --'], over,
                         'only the atomic pair may exceed the width')

    def test_the_dash_still_never_opens_a_line(self):
        """The reason the glue exists. When it cannot fit, the WORD moves down with it."""
        for width in (29, 40, 41, 42, 43, 44):
            for out in bc._wrap_fe_lines('There was fighting here -- a great deal of it.', width):
                self.assertFalse(out.startswith('--'), '%r at width %d' % (out, width))

    def test_a_dash_that_fits_is_still_glued_where_it_was(self):
        self.assertEqual(['a b --', 'c'], bc._wrap_fe_lines('a b -- c', 6))


class Ch05ArrivalSceneAndTheNoLupinBranch(unittest.TestCase):
    """Scene 4 -- the party crests the ridge -- and the branch the whole chapter waits on (#25).

    It is the fourth backdrop scene and the FIRST with a `no_lupin_fallback`, so it is where the
    mechanism gets built. Four more scenes reuse it: Basil's join, Proof #1 in the Talk recruit,
    and both endings.

    The signal is `CHECK_ALIVE`, not a flag. `eventscr.c` returns 0 for a unit that is not found
    at all OR is `US_DEAD`, so never-recruited and recruited-then-killed collapse into the one
    arm we want; and because it reads the ROSTER rather than the field it also survives ch05's
    9-of-10 deploy, where a recruited Lupin can be sitting on the bench. Vanilla's own answer --
    ch14a branches its ending on CHECK_ALIVE(CHARACTER_JOSHUA), Joshua being vanilla Ch5's
    optional Talk recruit and Sahnar's donor.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return bc._load_chapter_yaml(self.CAMPAIGN, bc.CH05_CHAPTER_YAML)

    def _scene(self):
        slot, _msg, _boxes, _what = bc.CH05_ARRIVAL_SLOT
        return bc._chapter_event_by_slot(self._chap(), 'chapter_start', slot, 'test')

    # ── ids ────────────────────────────────────────────────────────────────────
    def test_both_ids_are_owned_unique_and_inside_ch05s_host_block(self):
        _slot, msg, _boxes, _what = bc.CH05_ARRIVAL_SLOT
        claimed = set(bc.HOSTED_CHAPTER_MESSAGE_IDS['ch05'])
        owner = bc.assert_message_ids_unique()
        for mid in (msg, bc.CH05_ARRIVAL_NO_LUPIN_MSG):
            self.assertTrue(0x9E4 <= mid <= 0x9F5, 'outside ch05\'s Ch6 host block')
            self.assertIn(mid, claimed)
            self.assertEqual('ch05', owner[mid])
        self.assertEqual((0x9EC, 0x9ED), (msg, bc.CH05_ARRIVAL_NO_LUPIN_MSG),
                         "#25's allocation table")

    def test_the_fallback_costs_one_extra_id_not_four(self):
        """The wrong instinct is to split the scene around the differing box, which would spend
        four ids on a 7-box scene with one substitution. Duplicating text is free; ids are what
        is scarce, so the WHOLE variant scene goes to a second id and the branch picks."""
        self.assertEqual(1, len(self._scene()['no_lupin_fallback']['boxes']))
        written = dict(bc.ch05_opening_messages(self._chap()))
        arrival = [mid for mid in written
                   if mid in (bc.CH05_ARRIVAL_SLOT[1], bc.CH05_ARRIVAL_NO_LUPIN_MSG)]
        self.assertEqual(2, len(arrival), 'one scene, one variant, two ids')

    def test_the_yaml_slot_label_stays_an_anatomy_citation(self):
        slot, msg, _boxes, _what = bc.CH05_ARRIVAL_SLOT
        self.assertNotEqual(int(slot.split()[1], 16), msg)
        self.assertIn(int(slot.split()[1], 16), bc.HOSTED_CHAPTER_MESSAGE_IDS['ch04'])

    # ── the substitution ───────────────────────────────────────────────────────
    def test_the_chapters_first_line_has_a_speaker_on_both_paths(self):
        """Box 1 is the FIRST LINE OF THE CHAPTER and it is Lupin's, so a no-parley player
        would open ch05 on a speaker who is not there."""
        scene = self._scene()
        locked = scene['script']
        fallback = bc.variant_beat(locked, scene['no_lupin_fallback'], 'test')
        self.assertEqual('lupin', next(iter(locked[0])))
        self.assertEqual(len(locked), len(fallback))
        for i, box in enumerate(fallback, 1):
            (speaker, text), = box.items()
            self.assertTrue(speaker and text.strip(), 'box %d has no speaker/text' % i)
        self.assertNotIn('lupin', [next(iter(b)) for b in fallback],
                         'the no-parley path must never put Lupin on stage')
        self.assertEqual('pinky', next(iter(fallback[0])),
                         'box 1 goes to Pinky, continuing ch04\'s own no-Lupin tracker')

    def test_the_six_unchanged_boxes_ride_through_both_branches(self):
        scene = self._scene()
        fallback = bc.variant_beat(scene['script'], scene['no_lupin_fallback'], 'test')
        self.assertEqual(scene['script'][1:], fallback[1:])
        self.assertEqual('pinky', next(iter(fallback[-1])),
                         'Pinky keeps the closing spot on both paths')

    def test_a_drifted_anchor_fails_loudly_instead_of_mis_swapping(self):
        scene = self._scene()
        with self.assertRaises(SystemExit):
            bc.variant_beat(list(reversed(scene['script'])),
                            scene['no_lupin_fallback'], 'test')

    def test_one_box_may_be_replaced_by_SEVERAL(self):
        """A substitute chosen as prose can be too long for the channel it lands in -- ch05's
        on-map fallbacks are, at the bubble's 29. The author then has to place the extra
        A-press, so a `script:` entry may be a LIST of boxes standing in for the one named
        box. `boxes:`/`replaces:`/`script:` still agree one-for-one; only the substitute is
        plural, which is what keeps this the same mechanism rather than a second one."""
        beat = [{'a': 'one'}, {'b': 'two'}, {'c': 'three'}]
        out = bc.variant_beat(beat, {'boxes': [2], 'replaces': ['two'],
                                     'script': [[{'b': 'two-a'}, {'b': 'two-b'}]]}, 'test')
        self.assertEqual([{'a': 'one'}, {'b': 'two-a'}, {'b': 'two-b'}, {'c': 'three'}], out)

    def test_a_plural_substitute_does_not_shift_a_later_replacement(self):
        """The `boxes:` indices are read against the ORIGINAL beat. Splicing left to right
        without saying so would move every box after the first substitution, and the anchor
        assertion would then blame the locked script for moving."""
        beat = [{'a': 'one'}, {'b': 'two'}, {'c': 'three'}]
        out = bc.variant_beat(beat, {'boxes': [1, 3], 'replaces': ['one', 'three'],
                                     'script': [[{'a': 'x'}, {'a': 'y'}], {'c': 'z'}]}, 'test')
        self.assertEqual([{'a': 'x'}, {'a': 'y'}, {'b': 'two'}, {'c': 'z'}], out)

    def test_every_ch05_fallback_declares_one_schema_not_two(self):
        """ch05 authored its five blocks with singular `box:`/`replaces:` while variant_beat --
        ch04's, already shipping -- reads LISTS. Normalising the YAML is what kept this at one
        mechanism; a reader that accepts both shapes is the second one."""
        chap = self._chap()
        blocks = [e['no_lupin_fallback'] for e in chap['events'] if 'no_lupin_fallback' in e]
        self.assertEqual(5, len(blocks), "#25's five conditional scenes")
        for fb in blocks:
            self.assertNotIn('box', fb, 'singular `box:` is the second schema')
            self.assertIsInstance(fb['boxes'], list)
            self.assertIsInstance(fb['replaces'], list)
            self.assertEqual(len(fb['boxes']), len(fb['replaces']))
            self.assertEqual(len(fb['boxes']), len(fb['script']))

    # ── the branch itself ──────────────────────────────────────────────────────
    def test_the_branch_asks_the_roster_and_never_a_flag(self):
        """A flag would have to survive a chapter boundary, and a FIELD test would send a player
        who recruited Lupin and benched him down the no-Lupin arm."""
        code = bc.branch_on_check_alive(bc.CH05_LUPIN_CHARACTER, '    HAVE\n', '    NONE\n')
        self.assertIn('CHECK_ALIVE(%s)' % bc.CH05_LUPIN_CHARACTER, code)
        self.assertNotIn('CHECK_EVENTID', code)
        self.assertNotIn('CHECK_DEPLOYED', code)
        self.assertEqual('CHARACTER_DUESSEL', bc.CH05_LUPIN_CHARACTER,
                         "Lupin's MAP identity is his portrait slot, not his STAT_DONOR")

    def test_the_two_arms_converge_on_one_label(self):
        code = bc.branch_on_check_alive('CHARACTER_X', '    HAVE\n', '    NONE\n')
        self.assertIn('BEQ(0x0, EVT_SLOT_C, EVT_SLOT_0)', code)
        self.assertLess(code.index('HAVE'), code.index('LABEL(0x0)'))
        self.assertLess(code.index('LABEL(0x0)'), code.index('NONE'))
        self.assertLess(code.index('NONE'), code.index('LABEL(0x1)'))
        self.assertIn('LABEL(0x4)', bc.branch_on_check_alive('C', '', '', label_base=4))

    def test_both_branch_primitives_are_one_skeleton_with_two_predicates(self):
        """branch_on_flag and branch_on_check_alive differ ONLY in their PREDICATE -- the line
        that loads slot C, and the comment naming what a jump means. Compared with those gone,
        the two must be the same code; if they ever diverge, one of them is a second mechanism."""
        strip = lambda c: [re.sub(r'/\*.*?\*/', '', l).rstrip() for l in c.split('\n')
                           if 'CHECK_ALIVE' not in l and 'CHECK_EVENTID' not in l]
        self.assertEqual(strip(bc.branch_on_flag('EVFLAG_TMP(9)', '    A\n', '    B\n')),
                         strip(bc.branch_on_check_alive('CHARACTER_X', '    A\n', '    B\n')))

    def test_the_beginning_script_picks_the_arm_around_the_arrival_text(self):
        block = bc.ch05_opening_backdrop_block()
        self.assertIn('CHECK_ALIVE(%s)' % bc.CH05_LUPIN_CHARACTER, block)
        self.assertIn('Text(0x%X)' % bc.CH05_ARRIVAL_SLOT[1], block)
        self.assertIn('Text(0x%X)' % bc.CH05_ARRIVAL_NO_LUPIN_MSG, block)
        # exactly one of the two plays: the alive arm GOTOs past the fallback
        self.assertLess(block.index('CHECK_ALIVE'),
                        block.index('Text(0x%X)' % bc.CH05_ARRIVAL_SLOT[1]))
        self.assertLess(block.index('Text(0x%X)' % bc.CH05_ARRIVAL_SLOT[1]),
                        block.index('Text(0x%X)' % bc.CH05_ARRIVAL_NO_LUPIN_MSG))
        self.assertIn('GOTO(', block)

    def test_the_three_tomb_scenes_play_before_the_branch(self):
        """Player order: the tomb, then the ridge. The branch is the LAST thing before LOMA."""
        block = bc.ch05_opening_backdrop_block()
        for _slot, msg, _boxes, _what in bc.CH05_OPENING_SLOTS:
            self.assertLess(block.index('Text(0x%X)' % msg), block.index('CHECK_ALIVE'))

    # ── the second backdrop ────────────────────────────────────────────────────
    def test_the_arrival_cuts_to_its_own_backdrop_and_re_arms_the_load_mode(self):
        """BACG only decompresses while activeTextType is REMOVEPORTRAITS/_1A22 (eventscr.c:1316);
        the Text() beats above left it at TEXTSTART, so a bare second BACG is a no-op and the tomb
        stays in VRAM. The ch03/ch04 stale-BG bug, one chapter later."""
        block = bc.ch05_opening_backdrop_block()
        self.assertEqual(2, block.count('BACG('), 'the tomb, then the ridge')
        self.assertIn('BACG(%s)' % bc.CH05_ARRIVAL_BG, block)
        second = block.index('BACG(%s)' % bc.CH05_ARRIVAL_BG)
        rearm = block.rindex('REMOVEPORTRAITS', 0, second)
        self.assertLess(block.index('Text(0x%X)' % bc.CH05_OPENING_SLOTS[-1][1]), rearm,
                        're-arm has to come AFTER the tomb scenes that reset it')
        self.assertIn('FADI(16)', block[block.index(
            'Text(0x%X)' % bc.CH05_OPENING_SLOTS[-1][1]):rearm],
            'fade the tomb out before cutting to the ridge')

    def test_the_arrival_backdrop_is_registered_with_a_source_png_inside_six_banks(self):
        from PIL import Image
        names = [enum for enum, _stem, _credit in bc.CAMPAIGN_BGS]
        self.assertIn(bc.CH05_ARRIVAL_BG, names)
        stem = next(s for e, s, _c in bc.CAMPAIGN_BGS if e == bc.CH05_ARRIVAL_BG)
        png = os.path.join(bc.REPO, 'campaigns', self.CAMPAIGN, 'backgrounds', stem + '.png')
        self.assertTrue(os.path.isfile(png), png)
        im = Image.open(png)
        self.assertEqual('P', im.mode)
        self.assertEqual((240, 160), im.size)
        banks = max(int(i) // 16 for i in set(im.getdata())) + 1
        self.assertLessEqual(banks, 6, '%d banks -- the fade procs apply only six' % banks)

    # ── the two bodies ─────────────────────────────────────────────────────────
    def test_both_bodies_wear_our_faces_and_wrap_at_the_scenic_42(self):
        bodies = dict(bc.ch05_opening_messages(self._chap()))
        locked, fallback = bodies[bc.CH05_ARRIVAL_SLOT[1]], bodies[bc.CH05_ARRIVAL_NO_LUPIN_MSG]
        # Face slots are PORTRAIT_MAP's, never STAT_DONOR's -- Wolfram's stats come from Gilliam
        # and his face from Franz, and a scene that reached for the donor would put a stranger on
        # screen with every text decoder still green (#276's shape).
        self.assertIn('[LoadFace][FID_Duessel]', locked)      # Lupin
        self.assertNotIn('[FID_Duessel]', fallback)
        for body in (locked, fallback):
            self.assertIn('[LoadFace][FID_Franz]', body)      # Wolfram
            self.assertIn('[LoadFace][FID_Seth]', body)       # Marty
            self.assertIn('[LoadFace][FID_Neimi]', body)      # Pinky
            self.assertNotIn('[FID_Gilliam]', body)
            self.assertNotIn('[FID_Knoll]', body)
            self.assertNotIn('[FID_Vanessa]', body)
            widest = max(len(re.sub(r'\[[^\]]*\]', '', line)) for line in body.split('\n'))
            self.assertLessEqual(widest, 42)

    def test_a_speaker_holds_one_podium_across_both_arms(self):
        bodies = dict(bc.ch05_opening_messages(self._chap()))
        for body in (bodies[bc.CH05_ARRIVAL_SLOT[1]],
                     bodies[bc.CH05_ARRIVAL_NO_LUPIN_MSG]):
            for spk, podium in bc.CH05_ARRIVAL_PODIUMS.items():
                tag = bc._fid_tag(bc.PORTRAIT_MAP[spk])
                if tag in body:
                    self.assertIn('%s[LoadFace]%s' % (podium, tag), body,
                                  '%s must sit at %s in both arms' % (spk, podium))

    def test_the_four_speakers_fit_the_face_budget(self):
        """FACE_SLOT_COUNT is 4. A fifth podium evicts one mid-scene."""
        self.assertLessEqual(len(set(bc.CH05_ARRIVAL_PODIUMS.values())), 4)
        scene = self._scene()
        fallback = bc.variant_beat(scene['script'], scene['no_lupin_fallback'], 'test')
        for beat in (scene['script'], fallback):
            self.assertLessEqual(len({next(iter(b)) for b in beat}), 4)

    def test_the_locked_prose_survives_the_wrap(self):
        bodies = dict(bc.ch05_opening_messages(self._chap()))
        plain = {m: ' '.join(re.sub(r'\[[^\]]*\]', ' ', b).split()) for m, b in bodies.items()}
        locked = plain[bc.CH05_ARRIVAL_SLOT[1]]
        fallback = plain[bc.CH05_ARRIVAL_NO_LUPIN_MSG]
        self.assertIn('The trail leads here', locked)
        self.assertIn('The tracks stop here, Father', fallback)
        for body in (locked, fallback):
            self.assertIn('This was a training arena', body)   # Wolfram's Forge seed
            self.assertIn('This magic is familiar', body)      # Marty's hook
            self.assertIn('Father, I see it', body)            # Pinky's closer


class Ch05BasilJoinsAfterPrep(unittest.TestCase):
    """Scene 5 -- Basil trundles up, cracks the tourist joke, and JOINS (#25).

    The opening's FIRST on-map beat, and the first place the inherited channel had to be
    overruled. Vanilla plays its twin (0x9C2) BEFORE the prep CALL, because vanilla stages
    its speaking party with explicit LOAD1s; ours is placed BY prep, so before the CALL the
    field holds the risen line, Ravisin and a green shrub and nobody the shrub could be
    talking to. So the beat goes after `CALL(prep)` -- vanilla's own after-prep shape
    (`FADU(16)` -> `CUMO_*` -> `STAL` -> `CURE` -> `TEXTSTART`), which is exactly what its
    0x9C3/0x9C4 do -- and it lands adjacent to the CUSA that was already there, so the line
    that asks and the flip that answers are one beat instead of two across a screen.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return bc._load_chapter_yaml(self.CAMPAIGN, bc.CH05_CHAPTER_YAML)

    def _scene(self):
        slot, _msg, _boxes, _what = bc.CH05_BASIL_JOIN_SLOT
        return bc._chapter_event_by_slot(self._chap(), 'chapter_start', slot, 'test')

    def _script(self):
        return bc.ch05_beginning_script(self._chap(), 'CHARACTER_ARTUR',
                                        bc.CH05_SAHNAR_TABLE, 'CHARACTER_MARISA')

    # ── ids ────────────────────────────────────────────────────────────────────
    def test_both_ids_are_owned_unique_and_inside_ch05s_host_block(self):
        _slot, msg, _boxes, _what = bc.CH05_BASIL_JOIN_SLOT
        claimed = set(bc.HOSTED_CHAPTER_MESSAGE_IDS['ch05'])
        owner = bc.assert_message_ids_unique()
        for mid in (msg, bc.CH05_BASIL_JOIN_NO_LUPIN_MSG):
            self.assertTrue(0x9E4 <= mid <= 0x9F5, 'outside ch05\'s Ch6 host block')
            self.assertIn(mid, claimed)
            self.assertEqual('ch05', owner[mid])
        self.assertEqual((0x9EE, 0x9EF), (msg, bc.CH05_BASIL_JOIN_NO_LUPIN_MSG),
                         "#25's allocation table")

    def test_the_yaml_slot_label_stays_an_anatomy_citation(self):
        """`vanilla 0x9C2` names the scene we MINE. It is also ch04's own no-parley ending,
        which is what the join beat once pointed at -- the collision guard's founding case."""
        slot, msg, _boxes, _what = bc.CH05_BASIL_JOIN_SLOT
        self.assertNotEqual(int(slot.split()[1], 16), msg)
        self.assertIn(int(slot.split()[1], 16), bc.HOSTED_CHAPTER_MESSAGE_IDS['ch04'])

    # ── the channel ────────────────────────────────────────────────────────────
    def test_both_bodies_wrap_at_the_bubble_29_not_the_scenic_42(self):
        """The first beat that rides TEXTSHOW -> PutTalkBubble, whose right-side branch
        computes x = 29 - width with no clamp: a line over 29 runs off the tilemap."""
        for _msg, body in bc.ch05_basil_join_messages(self._chap()):
            for line in body.split('\n'):
                printable = re.sub(r'\[[^\]]*\]', '', line)
                self.assertLessEqual(len(printable), 29, 'bubble overflow: %r' % line)

    def test_basil_keeps_the_mid_left_she_holds_in_the_talk_recruit(self):
        for _msg, body in bc.ch05_basil_join_messages(self._chap()):
            self.assertIn('[OpenMidLeft][LoadFace][FID_Artur]', body)
            self.assertNotIn('[FID_Natasha]', body)     # her STAT_DONOR, never her face

    def test_the_scene_is_three_locked_basil_boxes(self):
        self.assertEqual(3, bc.CH05_BASIL_JOIN_SLOT[2])
        self.assertEqual(['basil'] * 3, [next(iter(b)) for b in self._scene()['script']])

    # ── the substitution ───────────────────────────────────────────────────────
    def test_the_fallback_moves_basils_trigger_off_lupin_and_onto_the_party(self):
        """Box 2 is Basil reading the WOLF, and ch04's parley is optional. The variant makes
        the party itself the revelation: everyone she has met belonged to Ravisin."""
        scene = self._scene()
        fallback = bc.variant_beat(scene['script'], scene['no_lupin_fallback'], 'test')
        self.assertEqual([2], scene['no_lupin_fallback']['boxes'])
        self.assertIn('Wolf.', next(iter(scene['script'][1].values())))
        for box in fallback:
            self.assertNotIn('Wolf', next(iter(box.values())))
        self.assertEqual(scene['script'][0], fallback[0], 'the tourist joke is shared')
        self.assertEqual(scene['script'][-1], fallback[-1], 'the ask is shared')

    def test_the_no_lupin_arm_spends_a_fourth_a_press_on_an_AUTHORED_break(self):
        """Basil's substitute turn is 74 characters and this is a 29-wide bubble, so it cannot
        be one box. Left flowed, the wrapper chose the A-press and put it mid-clause; the YAML
        now authors two boxes instead. The break lands after the shock, not on the full stop --
        her run-on then arrives whole, which is the Ewan register her bible calls for.

        The arms are not required to be the same length. Only to each stand up."""
        scene = self._scene()
        fallback = bc.variant_beat(scene['script'], scene['no_lupin_fallback'], 'test')
        self.assertEqual(3, len(scene['script']))
        self.assertEqual(4, len(fallback))
        self.assertEqual("...You're none of hers.", next(iter(fallback[1].values())))
        self.assertTrue(next(iter(fallback[2].values())).startswith('Not one of you.'))
        # and no box of either arm splits under the wrap -- an [A] the AUTHOR did not place
        for _msg, body in bc.ch05_basil_join_messages(self._chap()):
            for page in body.split('[A]')[:-1]:
                self.assertLessEqual(len([l for l in page.split('[LF]') if l.strip()]), 2,
                                     'the wrapper paged this box, not the author: %r' % page)

    def test_the_fallback_costs_one_extra_id_not_three(self):
        written = dict(bc.ch05_basil_join_messages(self._chap()))
        self.assertEqual({bc.CH05_BASIL_JOIN_SLOT[1], bc.CH05_BASIL_JOIN_NO_LUPIN_MSG},
                         set(written), 'one scene, one variant, two ids')

    def test_the_locked_prose_survives_the_wrap(self):
        plain = {m: ' '.join(re.sub(r'\[[^\]]*\]', ' ', b).split())
                 for m, b in bc.ch05_basil_join_messages(self._chap())}
        locked = plain[bc.CH05_BASIL_JOIN_SLOT[1]]
        fallback = plain[bc.CH05_BASIL_JOIN_NO_LUPIN_MSG]
        self.assertIn('Oh! Tourists', locked)                 # the joke, both arms
        self.assertIn('Oh! Tourists', fallback)
        self.assertIn("You're hers", locked)
        self.assertIn('none of hers', fallback)
        for body in (locked, fallback):
            self.assertIn('Take me to her', body)             # the ask the CUSA answers

    # ── placement in the beginning script ──────────────────────────────────────
    def test_the_join_plays_AFTER_prep_because_the_party_is_PLACED_by_prep(self):
        """The one place scene 5 does not inherit its twin's channel. Vanilla LOAD1s its
        speaking party before the prep CALL; ours arrives through Pick Units, so a beat
        placed there would have Basil addressing an empty pocket."""
        script = self._script()
        prep = script.index('CALL(%s)' % bc.CH05_PREP_SCRIPT)
        text = script.index('TEXTSHOW(0x%X)' % bc.CH05_BASIL_JOIN_SLOT[1])
        self.assertLess(prep, text)
        self.assertLess(text, script.index('CUSA('), 'she asks, then she flips')

    def test_the_beat_fades_up_and_finds_basil_before_it_speaks(self):
        """The shared prep prologue fades to black and leaves it there, so anything VISIBLE
        after the CALL brings its own FADU -- vanilla's 0x9C3 does exactly this. Then the
        bubble needs a unit: PutTalkBubble anchors to whoever the camera holds."""
        script = self._script()
        prep = script.index('CALL(%s)' % bc.CH05_PREP_SCRIPT)
        text = script.index('TEXTSHOW(0x%X)' % bc.CH05_BASIL_JOIN_SLOT[1])
        tail = script[prep:text]
        self.assertIn('FADU(16)', tail)
        self.assertIn('CUMO_CHAR(CHARACTER_ARTUR)', tail)
        self.assertLess(tail.index('FADU(16)'), tail.index('CUMO_CHAR'))
        self.assertIn('CURE', tail)

    def test_the_second_branch_does_not_reuse_the_first_branchs_labels(self):
        """Two branches in ONE event list. `BEQ`/`GOTO` scan the list for a matching LABEL,
        so a second branch left at label_base 0 would jump into the arrival's arms."""
        script = self._script()
        self.assertEqual(2, script.count('CHECK_ALIVE(%s)' % bc.CH05_LUPIN_CHARACTER),
                         'the arrival and the join each ask the roster')
        for label in ('LABEL(0x0)', 'LABEL(0x1)', 'LABEL(0x2)', 'LABEL(0x3)'):
            self.assertEqual(1, script.count(label), '%s is not unique' % label)

    def test_exactly_one_arm_of_the_join_plays(self):
        script = self._script()
        locked = script.index('TEXTSHOW(0x%X)' % bc.CH05_BASIL_JOIN_SLOT[1])
        fallback = script.index('TEXTSHOW(0x%X)' % bc.CH05_BASIL_JOIN_NO_LUPIN_MSG)
        self.assertLess(script.index('CHECK_ALIVE', script.index('CALL(%s)'
                                     % bc.CH05_PREP_SCRIPT)), locked)
        self.assertLess(locked, fallback)
        self.assertIn('GOTO(0x3)', script)

    def test_the_backdrop_half_still_runs_before_LOMA_and_the_join_after(self):
        """Regression on the whole opening's order, which is what a reader loses first."""
        script = self._script()
        order = [script.index(needle) for needle in (
            'Text(0x%X)' % bc.CH05_OPENING_SLOTS[0][1],       # scene 1, on the backdrop
            'Text(0x%X)' % bc.CH05_ARRIVAL_SLOT[1],           # scene 4, on the ridge
            'LOMA(',
            'CALL(%s)' % bc.CH05_PREP_SCRIPT,
            'TEXTSHOW(0x%X)' % bc.CH05_BASIL_JOIN_SLOT[1],    # scene 5, on the map
            'CUSA(',
            'TEXTSHOW(0x%X)' % bc.CH05_SAHNAR_ALONE_SLOT[1])] # scene 6, on the map
        self.assertEqual(sorted(order), order)


class SilentPresenceDirective(unittest.TestCase):
    """`present:` — a character is on screen for a scene and never speaks (#25).

    It exists because ch05's scene 3 has to SHOW Ravisin's raised Sahnar without spending a box
    on it. Nicolas, 2026-08-14: "you don't need to even add lines... just add sahnars portrait
    to the scene."

    It renders as a PRELOAD, and that is the engine's call rather than a design one:
    `TalkPrepNextChar` reopens the talk bubble whenever the active face differs from the
    speaking one, so a silent face loaded mid-message opens a bubble of its own and the scene
    plays with two stacked bubbles. Vanilla's silent loads are all preloads (MSG_0954, 095D,
    095E); it never loads a face mid-message without having it speak next.
    """
    STAGING = {'a': ('[OpenMidLeft]', '[FID_Artur]'),
               'b': ('[OpenMidRight]', '[FID_Riev]'),
               'c': ('[OpenFarRight]', '[FID_Marisa]')}

    def _msg(self, script, **kw):
        return bc._script_to_message(script, self.STAGING, width=42, **kw)

    def test_it_loads_the_face_without_opening_a_box(self):
        out = self._msg([{'present': 'c'}, {'a': 'one'}, {'a': 'two'}])
        self.assertIn('[OpenFarRight][LoadFace][FID_Marisa]', out)
        self.assertEqual(2, out.count('[A]'), 'a presence is staging, not an A-press')

    def test_it_is_not_a_box(self):
        self.assertIn('present', bc.SCRIPT_DIRECTIVES)
        self.assertEqual(2, bc._script_box_count(
            [{'present': 'c'}, {'a': 'one'}, {'a': 'two'}]))

    def test_the_face_is_PRELOADED_before_any_text(self):
        """The engine's rule, not ours. `TalkPrepNextChar` reopens the talk bubble whenever the
        active face differs from the speaking one, so a silent face loaded mid-message opens a
        bubble of its own and the scene plays with two stacked bubbles -- filmed 2026-08-14.
        Vanilla's silent loads are all preloads (MSG_0954, 095D, 095E); it never loads a face
        mid-message without having it speak next (MSG_904, 092C, 095A)."""
        out = self._msg([{'a': 'one'}, {'present': 'c'}, {'a': 'two'}])
        self.assertLess(out.index('[LoadFace][FID_Marisa]'), out.index('one'),
                        'a silent face must be up before the first bubble opens')

    def test_it_does_not_break_same_speaker_coalescing(self):
        """It is not a mid-scene event, so it must not split a speaker's consecutive turns into
        two blocks: their two pages stay inside ONE [OpenX] run, joined by [A][LF]. A re-opened
        podium between them would be a second bubble by another road."""
        out = self._msg([{'present': 'c'}, {'a': 'one'}, {'a': 'two'}])
        self.assertIn('one[A][LF]\ntwo[A]', out)
        # the only [OpenMidLeft]s are the load and the single block that follows it
        self.assertEqual(2, out.count('[OpenMidLeft]'))

    def test_a_presence_with_no_podium_is_refused(self):
        with self.assertRaises(SystemExit):
            self._msg([{'present': 'nobody'}, {'a': 'one'}])

    def test_staged_names_sees_silent_presences_and_departures(self):
        script = [{'a': 'one'}, {'present': 'c'}, {'exits': 'a'}]
        self.assertEqual({'a', 'c'}, bc._script_staged_names(script))

    def test_a_present_character_may_LATER_leave(self):
        """Staged silently, then walks off -- a legal scene, and the `exits:` guard used to
        hard-exit the build on it: the preload recorded the podium under an anonymous sentinel,
        so the leaver looked like an impostor holding somebody else's seat."""
        out = self._msg([{'present': 'c'}, {'a': 'one'}, {'exits': 'c'}, {'a': 'two'}])
        self.assertIn('[OpenFarRight][ClearFace]', out)
        self.assertLess(out.index('one'), out.index('[OpenFarRight][ClearFace]'))

    def test_an_anonymous_preload_still_cannot_be_exited(self):
        """The sentinel still does its job for callers passing `preload` directly: nobody
        holds those podiums by name, so `exits:` on one is still the error it always was."""
        with self.assertRaises(SystemExit):
            self._msg([{'a': 'one'}, {'exits': 'c'}],
                      preload=[('[OpenFarRight]', '[FID_Marisa]')])

    def test_sharing_a_podium_with_a_speaker_is_refused_too(self):
        """Distance 0, not just 1 -- and it is the WORSE case: the renderer clears the silent
        face outright the moment its podium-holder speaks, so it is destroyed before the first
        box rather than merely buried. The shared podium tables pair names onto tags, so this
        is the easy way to hit it."""
        script = [{'ravisin': 'one'}, {'present': 'sahnar'}]
        with self.assertRaises(SystemExit):
            bc.assert_silent_faces_have_elbow_room(
                script, {'ravisin': '[OpenMidRight]', 'sahnar': '[OpenMidRight]'}, 'test')


class Ch05RavisinRaisesSahnarOnScreen(unittest.TestCase):
    """Scene 3 stages the summon with a PORTRAIT and no dialogue (#25, 2026-08-14).

    The design change that unblocked scene 6 — Sahnar stops being a turn-2 riser and goes on
    the map from turn 1, woken on screen by Ravisin — lands here, and it lands for free: the
    seven locked boxes are untouched and the scene gains an `enters:` directive instead of a
    line. Scene 3's power is that it is QUIET (the inverted-doubt beat, a friend being shut
    down), and a spoken resurrection would have buried it.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return bc._load_chapter_yaml(self.CAMPAIGN, bc.CH05_CHAPTER_YAML)

    def _scene(self):
        return bc._chapter_event_by_slot(self._chap(), 'chapter_start', 'vanilla 0x9BD', 'test')

    def _body(self):
        return dict(bc.ch05_opening_messages(self._chap()))[0x9EB]

    def test_the_summon_costs_no_box_and_the_lock_is_intact(self):
        script = self._scene()['script']
        self.assertEqual(7, bc._script_box_count(script), 'still the seven locked boxes')
        self.assertEqual('sahnar', next(e['present'] for e in script if 'present' in e))
        self.assertNotIn('sahnar', {k for e in script for k in e if k != 'present'},
                         'she is raised, she does not speak -- her first words are scene 6')

    def test_she_is_on_screen_for_the_WHOLE_scene_and_the_contrast_is_the_summon(self):
        """She is staged first, not mid-scene -- the engine allows no other placement (see
        `SilentPresenceDirective`). The beat still reads, because it reads off the CONTRAST:
        absent through scene 2, standing at Ravisin's shoulder through all of scene 3. So
        "It never once occurred to me she might be of use" is an appraisal to her face, and
        "It's not your concern." is said over her."""
        script = self._scene()['script']
        keys = [next(iter(e)) for e in script]
        self.assertEqual(0, keys.index('present'), 'staged before the first box')
        body = self._body()
        plain = ' '.join(re.sub(r'\[[^\]]*\]', ' ', body).split())
        self.assertLess(plain.index("A queen's blade"), plain.index('might be of use'))
        self.assertLess(plain.index('might be of use'), plain.index("It's not your concern"))
        self.assertLess(body.index('[LoadFace][FID_Marisa]'), body.index("A queen's blade"))
        # and she is absent from scene 2, which is what makes her presence here legible at all
        self.assertNotIn('[FID_Marisa]', dict(bc.ch05_opening_messages(self._chap()))[0x9EA])

    def test_no_second_bubble__the_silent_face_is_up_before_the_first_box(self):
        """The defect Nicolas caught on film: two stacked speech bubbles, because the first cut
        loaded her mid-message and `TalkPrepNextChar` reopens the bubble whenever the active
        face differs from the speaking one. Preloading leaves the message in vanilla's own
        MSG_0954 shape -- every silent face up front, then text.

        NB an `[A]` followed by `[OpenX][LoadFace]` is NOT the bug and must not be asserted
        against: that is an ordinary speaker change (Basil's, three lines below), it ships in
        every scene we have, and the newly loaded face speaks immediately."""
        body = self._body()
        self.assertTrue(body.startswith('[OpenFarRight][LoadFace][FID_Marisa]\n'
                                        '[OpenRight][LoadFace][FID_Riev]'),
                        'both faces must be up before the first box: %r' % body[:120])
        # nobody is loaded again once the talking starts EXCEPT a speaker taking their own turn
        first_text = body.index("A queen's blade")
        for match in re.finditer(r'\[Open\w+\]\[LoadFace\](\[FID_\w+\])', body):
            if match.start() > first_text:
                self.assertEqual('[FID_Artur]', match.group(1),
                                 'only a speaker may load mid-message, and only to speak next')

    def test_the_raised_face_gets_a_whole_empty_rung_of_elbow_room(self):
        """The defect this scene taught, found by FILMING (2026-08-14). Podiums are a ladder and
        neighbouring rungs OVERLAP; FE8 draws the active speaker on top. For a scene of speakers
        that is harmless -- scene 4 seats four across adjacent rungs and each is drawn over the
        others when its turn comes. A face raised by `enters:` never takes a turn, so on a
        neighbouring rung it stays underneath for the whole scene: Sahnar's first pass put her on
        FarRight beside Ravisin on MidRight, and she played as a hood behind Ravisin's shoulder.

        Ravisin therefore moves to Right, leaving MidRight EMPTY between the two -- vanilla's own
        stable two-face right side (MSG_904, MSG_092C, MSG_0937, MSG_0954)."""
        self.assertEqual({'ravisin': '[OpenRight]', 'sahnar': '[OpenFarRight]'},
                         bc.CH05_OPENING_PODIUM_OVERRIDES['vanilla 0x9BD'])
        gap = (bc.PODIUM_ORDER.index('[OpenFarRight]') - bc.PODIUM_ORDER.index('[OpenRight]'))
        self.assertEqual(2, gap, 'a whole rung must sit empty between them')
        body = self._body()
        self.assertIn('[OpenFarRight][LoadFace][FID_Marisa]', body)
        self.assertIn('[OpenRight][LoadFace][FID_Riev]', body)
        self.assertEqual(1, body.count('[LoadFace][FID_Riev]'))
        self.assertNotIn('[OpenMidRight]', body, 'the rung between them stays empty')
        self.assertNotIn('[ClearFace]', body, 'nobody is evicted: three faces, four slots')

    def test_a_silent_face_next_door_to_a_speaker_is_refused(self):
        """The guard, on the exact shape that shipped wrong."""
        script = [{'ravisin': 'one'}, {'present': 'sahnar'}, {'ravisin': 'two'}]
        bc.assert_silent_faces_have_elbow_room(
            script, {'ravisin': '[OpenRight]', 'sahnar': '[OpenFarRight]'}, 'test')
        with self.assertRaises(SystemExit):
            bc.assert_silent_faces_have_elbow_room(
                script, {'ravisin': '[OpenMidRight]', 'sahnar': '[OpenFarRight]'}, 'test')

    def test_speakers_may_still_sit_on_adjacent_rungs(self):
        """Scene 4 does exactly this and is shipped and filmed. The rule is about SILENCE, not
        adjacency -- a guard that banned adjacency outright would have rejected it."""
        bc.assert_silent_faces_have_elbow_room(
            [{'a': 'x'}, {'b': 'y'}], {'a': '[OpenMidRight]', 'b': '[OpenFarRight]'}, 'test')
        self.assertEqual({'lupin': '[OpenFarLeft]', 'wolfram': '[OpenMidLeft]',
                          'marty': '[OpenMidRight]', 'pinky': '[OpenFarRight]'},
                         bc.CH05_ARRIVAL_PODIUMS)

    def test_the_face_arrives_before_basil_asks_after_her(self):
        body = self._body()
        self.assertLess(body.index('[LoadFace][FID_Marisa]'),
                        body.index('What will you do with her?'))
        self.assertLess(body.index('What will you do with her?'),
                        body.index("It's not your concern."))


class Ch05SahnarIsJoshuaAndBasilIsNatasha(unittest.TestCase):
    """Sahnar plays the way vanilla Joshua plays -- INCLUDING his refusal to hit the escort.

    `AI_A_07` is `gAiScript_ActionInRange_ExceptNatasha`. The refusal does not live in the
    `.ai` bytes: `AiScriptCmd_05_DoStandardAction` routes through
    `AiIsUnitEnemyAndNotInScrList`, which tests each candidate's `pCharacterData->number`
    against a list of character ids -- and vanilla's list holds `CHARACTER_NATASHA` literally.
    Copy the bytes alone and `0x7` degrades to plain `AI_A_00`, leaving a fragile Cleric a
    legal target for a Killing Edge. So the list is repointed at Basil.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _sahnar(self):
        chap = bc._load_chapter_yaml(self.CAMPAIGN, bc.CH05_CHAPTER_YAML)
        return next(e for e in chap['enemy_units'] if e['id'] == 'sahnar')

    def test_she_carries_joshuas_exact_ai_bytes(self):
        self.assertEqual('duelist_hold', self._sahnar()['ai_pattern'])
        self.assertEqual('{0x7, 0x3, 0x9, 0x0}', bc.CH05_AI['duelist_hold'])

    def test_the_list_has_exactly_one_client_which_is_what_makes_it_safe(self):
        """`.ai = {0x7,` appears ONCE in all of FE8 -- `UnitDef_088B5914`, vanilla Ch5's
        Joshua. Read from decomp HEAD, never the built tree, which holds our injections."""
        udefs = bc.vanilla_decomp_text('src/events_udefs.c')
        self.assertEqual(1, udefs.count('.ai = {0x7,'))
        bc.assert_escort_safe_ai_has_one_client('{0x7, 0x3, 0x9, 0x0}')

    def test_a_second_client_is_refused(self):
        with mock.patch.dict(bc.CH05_AI, {'someone_else': '{0x7, 0x0, 0x0, 0x0}'}):
            with self.assertRaises(SystemExit):
                bc.assert_escort_safe_ai_has_one_client('{0x7, 0x3, 0x9, 0x0}')

    def test_the_sweep_covers_EVERY_chapter_not_just_ch05(self):
        """The list is global, so the hazard is a FUTURE chapter reaching for `{0x7,` on its
        own account -- exactly the case a ch05-only scan cannot see. Scoping it to CH05_AI was
        the first cut and it defeated the guard's own purpose."""
        with mock.patch.dict(bc.CH04_AI, {'borrowed': '{0x7, 0x3, 0x9, 0x0}'}):
            with self.assertRaises(SystemExit):
                bc.assert_escort_safe_ai_has_one_client('{0x7, 0x3, 0x9, 0x0}')
        # and the sweep really is finding more than one table
        self.assertGreater(len([n for n in dir(bc) if re.fullmatch(r'CH\d\d_AI', n)]), 1)

    def test_the_repoint_swaps_natasha_for_our_escort_and_keeps_the_shape(self):
        """`AiIsInShortList` takes `const u16*` and stops on a zero entry, so the u8 array
        `{ id, 0, 0, 0 }` is the two-entry short list `{ id, TERMINATOR }`. Keep the shape."""
        vanilla = ('u8 CONST_DATA %s[] = { CHARACTER_NATASHA, 0, 0, 0 };'
                   % bc.ESCORT_SAFE_AI_LIST)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, 'cp_data.c')
            with open(path, 'w', encoding='utf-8') as f:
                f.write('/* head */\n%s\n/* tail */\n' % vanilla)
            with mock.patch.object(bc, 'CP_DATA_C', path):
                bc.repoint_escort_safe_ai_list('CHARACTER_ARTUR', 'test escort')
                patched = open(path, encoding='utf-8').read()
                self.assertIn('u8 CONST_DATA %s[] = { CHARACTER_ARTUR, 0, 0, 0 };'
                              % bc.ESCORT_SAFE_AI_LIST, patched)
                self.assertNotIn('CHARACTER_NATASHA', patched)
                # NON-IDEMPOTENT ON PURPOSE: a second run has nothing to match, and a silent
                # pass would ship an unprotected escort. cp_data.c is in PATCHED_DECOMP_FILES
                # so it is restored from HEAD each build.
                with self.assertRaises(SystemExit):
                    bc.repoint_escort_safe_ai_list('CHARACTER_ARTUR', 'test escort')

    def test_cp_data_is_restored_from_HEAD_every_build(self):
        self.assertIn('src/cp_data.c', bc.PATCHED_DECOMP_FILES)


class Ch05SahnarAloneOnTheArena(unittest.TestCase):
    """Scene 6 -- Sahnar alone at the sarcophagus, as a PLAIN ON-MAP BUBBLE (#25).

    This scene was the opening's problem child for exactly as long as Sahnar was a turn-2
    riser: with nothing of hers on the field, no talk bubble had a unit to anchor to, and the
    standing note priced it as needing a BACKDROP of its own -- the one place the twin was
    said to fail us. Nicolas's 2026-08-14 call moved her summon into scene 3, which puts her
    on the arena tile from turn 1 exactly as vanilla's `UnitDef_088B5914` puts Joshua there,
    and the exception evaporated. The beat is now vanilla's 0x9C3 down to the camera move, and
    all six locked boxes are untouched.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return bc._load_chapter_yaml(self.CAMPAIGN, bc.CH05_CHAPTER_YAML)

    def _scene(self):
        slot, _msg, _boxes, _what = bc.CH05_SAHNAR_ALONE_SLOT
        return bc._chapter_event_by_slot(self._chap(), 'chapter_start', slot, 'test')

    def _script(self):
        return bc.ch05_beginning_script(self._chap(), 'CHARACTER_ARTUR',
                                        bc.CH05_SAHNAR_TABLE, 'CHARACTER_MARISA')

    # ── the id ─────────────────────────────────────────────────────────────────
    def test_the_id_is_0x9F0_owned_unique_and_inside_ch05s_host_block(self):
        _slot, msg, _boxes, _what = bc.CH05_SAHNAR_ALONE_SLOT
        self.assertEqual(0x9F0, msg, "#25's allocation table")
        self.assertTrue(0x9E4 <= msg <= 0x9F5, "outside ch05's Ch6 host block")
        self.assertIn(msg, set(bc.HOSTED_CHAPTER_MESSAGE_IDS['ch05']))
        self.assertEqual('ch05', bc.assert_message_ids_unique()[msg])

    def test_the_yaml_slot_label_stays_an_anatomy_citation(self):
        """`vanilla 0x9C3` names the scene we MINE -- Joshua's own solo beat on this tile."""
        slot, msg, _boxes, _what = bc.CH05_SAHNAR_ALONE_SLOT
        self.assertNotEqual(int(slot.split()[1], 16), msg)

    def test_it_costs_ONE_id_because_she_never_mentions_the_wolf(self):
        self.assertNotIn('no_lupin_fallback', self._scene())
        self.assertEqual(1, len(bc.ch05_sahnar_alone_message(self._chap())))

    # ── the channel ────────────────────────────────────────────────────────────
    def test_the_body_wraps_at_the_bubble_29_not_the_scenic_42(self):
        """It rides TEXTSHOW -> PutTalkBubble, whose right-side branch computes x = 29 - width
        with no clamp: a line over 29 runs off the tilemap (the ch03 crier bug)."""
        for _msg, body in bc.ch05_sahnar_alone_message(self._chap()):
            for line in body.split('\n'):
                printable = re.sub(r'\[[^\]]*\]', '', line)
                self.assertLessEqual(len(printable), 29, 'bubble overflow: %r' % line)

    def test_she_keeps_the_mid_right_she_holds_in_scene_1_and_the_talk(self):
        """A character who changes seats between her scenes reads as a different person --
        and mid-right is also the podium vanilla's own 0x9C3 gives Joshua on this tile."""
        self.assertEqual({'sahnar': '[OpenMidRight]'}, bc.CH05_SAHNAR_ALONE_PODIUMS)
        for _msg, body in bc.ch05_sahnar_alone_message(self._chap()):
            self.assertIn('[OpenMidRight][LoadFace][FID_Marisa]', body)
            self.assertNotIn('[FID_Joshua]', body)      # her STAT_DONOR, never her face

    def test_every_locked_word_survives_the_staging_change(self):
        """The scene moved from a 42-wide backdrop to a 29-wide bubble. What that is allowed
        to cost is an A-PRESS; what it is not allowed to cost is a word."""
        self.assertEqual(['sahnar'] * 7, [next(iter(b)) for b in self._scene()['script']])
        plain = ' '.join(re.sub(r'\[[^\]]*\]', ' ',
                                bc.ch05_sahnar_alone_message(self._chap())[0][1]).split())
        for locked in ('...Someone has come.',
                       'Four thousand years, and someone has finally come.',
                       '...I was given a purpose. To defend this tomb.',
                       'No one ever came. I stopped counting somewhere in the middle.',
                       '...Well. Something has come now.',
                       'I will defend this tomb. It is my purpose.'):
            self.assertIn(locked, plain, 'the 2026-07-29 lock lost a word')

    def test_the_one_box_that_cannot_fit_29_breaks_where_the_AUTHOR_put_it(self):
        """"No one ever came. I stopped counting somewhere in the middle." is 60 characters:
        three lines at the bubble's 29, and a box holds two. Left flowed, the wrapper picked
        the A-press and split it mid-clause ("...somewhere in the" / "middle."). The break is
        authored at the full stop, so the understatement gets its own press."""
        self.assertEqual(7, bc.CH05_SAHNAR_ALONE_SLOT[2])
        boxes = [next(iter(b.values())) for b in self._scene()['script']]
        self.assertEqual('No one ever came.', boxes[3])
        self.assertEqual('I stopped counting somewhere in the middle.', boxes[4])
        body = bc.ch05_sahnar_alone_message(self._chap())[0][1]
        self.assertEqual(7, body.count('[A]'))
        # and NO box of the scene splits under the wrap -- an [A] the author did not place
        for page in body.split('[A]')[:-1]:
            self.assertLessEqual(len([l for l in page.split('[LF]') if l.strip()]), 2,
                                 'the wrapper paged this box, not the author: %r' % page)

    # ── placement in the beginning script ──────────────────────────────────────
    def test_the_camera_frames_the_arena_BEFORE_she_loads(self):
        """Vanilla's order, and it is the whole reveal: CUMO_AT the tile, hold, and only then
        LOAD1, so the player watches the duelist arrive instead of finding her there."""
        script = self._script()
        x, y = next(e for e in self._chap()['enemy_units']
                    if e['id'] == 'sahnar')['positions'][0]
        self.assertEqual((12, 6), (x, y), "vanilla Joshua's own tile, which is the arena")
        cumo = script.index('CUMO_AT(%d, %d)' % (x, y))
        load = script.index('LOAD1(0x1, %s)' % bc.CH05_SAHNAR_TABLE)
        text = script.index('TEXTSHOW(0x%X)' % bc.CH05_SAHNAR_ALONE_SLOT[1])
        self.assertLess(cumo, load)
        self.assertLess(load, script.index('CUMO_CHAR(CHARACTER_MARISA)'))
        self.assertLess(script.index('CUMO_CHAR(CHARACTER_MARISA)'), text)

    def test_the_arena_framing_is_a_CAMERA_and_not_an_inherited_corner(self):
        """`CUMO_AT` draws a cursor and never scrolls (`EventDisplayCursor_Loop` ->
        `PutMapCursor`). This beat had no CAMERA at all and was framed by whatever `LOMA` left
        -- the map's north-west, which happens to hold the arena. It filmed correctly and was
        resting on an accident; anything that moved the reload origin would have played the
        scene off-screen with no error to read. Vanilla pairs the two here too."""
        script = self._script()
        x, y = bc.ch05_sahnar_station(self._chap())[0]
        self.assertIn('CAMERA(%d, %d)' % (x, y), script)
        self.assertLess(script.index('CAMERA(%d, %d)' % (x, y)),
                        script.index('CUMO_AT(%d, %d)' % (x, y)),
                        'the scroll comes before the pointer')

    def test_she_WALKS_OFF_the_arena_tile_or_the_chapter_loses_its_arena(self):
        """The regression this slice shipped and code review caught. (12,6) is
        TERRAIN_ARENA_REGULAR *and* the arena tutorial's own `AREA(..., 12, 6, 12, 6)` trigger,
        so a hostile parked there makes the arena unenterable for the entire chapter and
        silently kills the `arena-wager` debut (#264/#265). Vanilla walks Joshua off it the
        instant he lands (`MOVE(0x0, CHARACTER_JOSHUA, 9, 7)`); dropping that MOVE as
        'deliberate' is what broke it."""
        load, guard = bc.ch05_sahnar_station(self._chap())
        self.assertEqual((12, 6), load, "vanilla Joshua's LOAD tile, which is the arena")
        self.assertEqual((9, 7), guard, "vanilla Joshua's walk-off tile")
        self.assertNotEqual(load, guard, 'she may not end where she lands')
        script = self._script()
        self.assertIn('MOVE(0x0, CHARACTER_MARISA, 9, 7)', script)
        self.assertLess(script.index('LOAD1(0x1, %s)' % bc.CH05_SAHNAR_TABLE),
                        script.index('MOVE(0x0, CHARACTER_MARISA, 9, 7)'))
        self.assertLess(script.index('MOVE(0x0, CHARACTER_MARISA, 9, 7)'),
                        script.index('TEXTSHOW(0x%X)' % bc.CH05_SAHNAR_ALONE_SLOT[1]),
                        'she is off the arena before she speaks')

    def test_a_missing_walk_off_is_refused_rather_than_shipped(self):
        chap = self._chap()
        sahnar = next(e for e in chap['enemy_units'] if e['id'] == 'sahnar')
        del sahnar['walks_to']
        with self.assertRaises(SystemExit):
            bc.ch05_sahnar_station(chap)

    def test_the_escort_is_measured_to_where_she_actually_STANDS(self):
        """Basil's walk is checked against Sahnar's fighting tile, not her load tile -- they
        are different tiles now, and the load tile is one she is never on when the Talk
        happens."""
        src = open(os.path.join(bc.REPO, 'tools', 'build_campaign.py'),
                   encoding='utf-8').read()
        self.assertIn('must_reach=ch05_sahnar_station(chap)[1]', src)

    def test_she_loads_ONCE_and_after_prep_where_vanilla_loads_joshua(self):
        script = self._script()
        self.assertEqual(1, script.count('LOAD1(0x1, %s)' % bc.CH05_SAHNAR_TABLE))
        self.assertLess(script.index('CALL(%s)' % bc.CH05_PREP_SCRIPT),
                        script.index('LOAD1(0x1, %s)' % bc.CH05_SAHNAR_TABLE))

    def test_it_brings_no_second_fade_up_because_scene_5_already_did(self):
        """The prep prologue leaves the screen black and scene 5 pays the FADU for both. A
        second one here would flash the map back through black between two adjacent beats."""
        script = self._script()
        # Bounded at scene 7's first box: the bellow AFTER it brings a deliberate fade cycle
        # of its own (a full-screen CG over the map), which is not this scene's business.
        gap = script[script.index('TEXTSHOW(0x%X)' % bc.CH05_BASIL_JOIN_SLOT[1]):
                     script.index('TEXTSHOW(0x%X)' % bc.CH05_MOOSE_CHARGE_SLOT[1])]
        self.assertNotIn('FADU', gap)
        self.assertNotIn('FADI', gap)


class Ch05TheMooseCharges(unittest.TestCase):
    """Scene 7 -- the last beat before turn 1: Pinky asks, and the moose answers (#25).

    Two things are being protected here, and neither is the text.

    The first is the ID. The beat is a setup and a punchline across a WORDLESS action, which
    normally means two messages and two hosted ids -- and #25's allocation has exactly one
    spare left. `stage_cut:` renders vanilla's own `[BreakTalk]`, a pause the event script
    resumes with `TEXTCONT`, so the gap costs nothing.

    The second is the moose's POSITION. Its pen at (10,0) is parity-locked (threat 14.1,
    cornered against the map's top edge) and the charge is a cutscene lunge, not a placement:
    it runs out and is snapped back off camera before the fight starts. Nicolas asked for the
    charge to LAND on the start tile; row 0 is the map's top edge, so there is no tile behind
    it to come from, and forward-and-checked is the same net-zero the other way round.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return bc._load_chapter_yaml(self.CAMPAIGN, bc.CH05_CHAPTER_YAML)

    def _scene(self):
        slot, _msg, _boxes, _what = bc.CH05_MOOSE_CHARGE_SLOT
        return bc._chapter_event_by_slot(self._chap(), 'chapter_start', slot, 'test')

    def _body(self):
        return ''.join(b for _m, b in bc.ch05_moose_charge_message(self._chap()))

    def _script(self):
        return bc.ch05_beginning_script(self._chap(), 'CHARACTER_ARTUR',
                                        bc.CH05_SAHNAR_TABLE, 'CHARACTER_MARISA')

    # ── the id ─────────────────────────────────────────────────────────────────
    def test_the_id_is_0x9F1_owned_unique_and_inside_ch05s_host_block(self):
        _slot, msg, _boxes, _what = bc.CH05_MOOSE_CHARGE_SLOT
        self.assertEqual(0x9F1, msg, "#25's allocation table")
        self.assertTrue(0x9E4 <= msg <= 0x9F5, "outside ch05's Ch6 host block")
        self.assertIn(msg, set(bc.HOSTED_CHAPTER_MESSAGE_IDS['ch05']))
        self.assertEqual('ch05', bc.assert_message_ids_unique()[msg])

    def test_the_yaml_slot_label_stays_an_anatomy_citation(self):
        """`vanilla 0x9C4` names the scene we MINE -- Natasha alone before the map. We take
        its POSITION and not its content, and we never write that id."""
        slot, msg, _boxes, _what = bc.CH05_MOOSE_CHARGE_SLOT
        self.assertNotEqual(int(slot.split()[1], 16), msg)

    def test_the_wordless_beat_costs_no_second_id(self):
        """The whole reason `stage_cut:` exists. Two boxes with an engine action between
        them is ONE message with a `[BreakTalk]`, not two messages with two ids."""
        ids = [m for m, _b in bc.ch05_moose_charge_message(self._chap())]
        self.assertEqual([bc.CH05_MOOSE_CHARGE_SLOT[1], bc.CH05_MOOSE_QUIP_MSG], ids)
        for i in ids:
            self.assertIn(i, set(bc.HOSTED_CHAPTER_MESSAGE_IDS['ch05']))
            self.assertEqual('ch05', bc.assert_message_ids_unique()[i])

    def test_a_scene_that_loses_its_stage_cut_is_refused(self):
        """Without the pause the two boxes run together and the charge plays after both --
        the joke told backwards, and nothing else would notice."""
        chap = self._chap()
        slot = bc.CH05_MOOSE_CHARGE_SLOT[0]
        event = bc._chapter_event_by_slot(chap, 'chapter_start', slot, 'test')
        event['script'] = [e for e in event['script'] if 'stage_cut' not in e]
        with self.assertRaises(SystemExit):
            bc.ch05_moose_charge_message(chap)

    def test_the_bellow_is_a_full_screen_CG_and_not_a_portrait(self):
        """Nicolas's art and Nicolas's idea (2026-08-15): the moose fills the screen between
        Pinky's question and the run. It is a BACG rather than a bust for the reason he raised
        himself -- a 96x80 portrait is drawn inside the talk window's envelope and those antlers
        do not fit it, while a BACG owns all 240x160 and has no envelope at all."""
        block = bc.ch05_moose_charge_block(bc.CH05_MOOSE_PID,
                                           bc.ch05_moose_station(self._chap()),
                                           bc.ch05_party_camera_tile(self._chap()))
        self.assertIn('BACG(%s)' % bc.CH05_MOOSE_BELLOW_BG, block)
        self.assertIn((bc.CH05_MOOSE_BELLOW_BG, 'bg_WhiteMoose', '{Nicolas}'), bc.CAMPAIGN_BGS)
        # REMOVEPORTRAITS does double duty: it re-arms the BACG load mode (without it the BG
        # is a no-op -- the ch03/ch04 stale-BG bug) AND clears the faces, so the CG comes up
        # on a clean screen instead of behind Pinky's bust.
        self.assertLess(block.index('REMOVEPORTRAITS'), block.index('BACG('))
        # CLEAN is the restore, and it is the bit that was missing: without it the map comes
        # back wearing the CG's PALETTE (filmed 2026-08-15 -- a snowfield in moose-red).
        # `EventScr_RemoveBGIfNeeded` only does a conditional FADU and cannot do this job.
        # Vanilla's own order, from EventScr_TextShowWithFadeIn: FADI -> CLEAN -> FADU.
        bell = block[block.index('BACG('):]
        self.assertIn('CLEAN', bell)

    def test_the_bellow_carries_no_text_but_DOES_cost_the_last_spare_id(self):
        """The image itself is wordless. What costs an id is that a scene change tears the talk
        down, so the punchline cannot resume the question's message and becomes its own --
        0x9D2, ch05's one spare. The block is now exactly spent; do not assume slack."""
        block = bc.ch05_moose_charge_block(bc.CH05_MOOSE_PID,
                                           bc.ch05_moose_station(self._chap()),
                                           bc.ch05_party_camera_tile(self._chap()))
        bellow = block[block.index('REMOVEPORTRAITS'):block.index('MOVE_DEFINED')]
        for texty in ('Text_BG', 'TEXTSHOW', 'TEXTSTART'):
            self.assertNotIn(texty, bellow, 'the IMAGE itself carries no text')

    def test_the_bellow_lands_BETWEEN_the_question_and_the_run(self):
        """Nicolas's order, verbatim: "pinky's why isn't he running -> *moose bellows* ->
        *moose runs* -> meesmickle quip"."""
        block = bc.ch05_moose_charge_block(bc.CH05_MOOSE_PID,
                                           bc.ch05_moose_station(self._chap()),
                                           bc.ch05_party_camera_tile(self._chap()))
        self.assertLess(block.index('TEXTSHOW('), block.index('BACG('), 'question, then bellow')
        self.assertLess(block.index('BACG('), block.index('MOVE_DEFINED'), 'bellow, then run')
        self.assertLess(block.index('MOVE_DEFINED'), block.index('TEXTSHOW(0x%X)' % bc.CH05_MOOSE_QUIP_MSG), 'run, then quip')

    def test_the_CG_fits_the_SIX_banks_the_fade_procs_apply(self):
        """It fades in and out, and the fade/transition procs only apply six palettes -- the
        rule Bremen's unreferenced 8-bank CG exists to teach. Asserted on the committed asset."""
        png = os.path.join(bc.REPO, 'campaigns', self.CAMPAIGN, 'backgrounds',
                           'bg_WhiteMoose.png')
        im = Image.open(png)
        self.assertEqual((240, 160), im.size)
        self.assertEqual('P', im.mode)
        banks = {im.getpixel((x * 8, y * 8)) // 16
                 for x in range(240 // 8) for y in range(160 // 8)}
        self.assertLessEqual(max(banks) + 1, 6,
                             'a 7th/8th bank would not survive the fade')

    def test_the_talk_is_ENDED_before_the_screen_changes(self):
        """Nicolas, watching the first film (2026-08-15): "he runs under it and he's covered".
        `[BreakTalk]` only LOCKS the talk proc, so the last speaker's box hangs over the whole
        action. `[CloseSpeechSlow]` is `ClearTalkBubble()` and nothing else -- faces stay loaded
        and the talk state survives, so `TEXTCONT` brings the window back for Meesmickle."""
        # Superseded by the CUT: with a full-screen bellow between them the talk ENDS after
        # the question (REMA) rather than pausing, so the bubble comes down on its own and the
        # punchline is a fresh message. `[CloseSpeechSlow]` is kept for `stage_break` scenes.
        script = self._script()
        beat = script[script.index('TEXTSHOW(0x%X)' % bc.CH05_MOOSE_CHARGE_SLOT[1]):]
        self.assertLess(beat.index('REMA'), beat.index('BACG('),
                        'the talk is down before the screen changes')
        self.assertNotIn('[BreakTalk]', self._body())

    def test_a_break_between_two_turns_by_ONE_speaker_is_refused(self):
        """The bubble reopens on `!TalkHasCorrectBubble()`, which compares the speaking face
        slot and width -- so a break with the same speaker on both sides resumes onto a bubble
        the engine still believes is correct and prints into a cleared window. It would look
        like the text simply vanished, which is not a thing to discover on film."""
        script = [{'pinky': 'One.'}, {'stage_cut': 'business'}, {'pinky': 'Two.'}]
        staging = {'pinky': ('[OpenMidLeft]', '[FID_Neimi]')}
        with self.assertRaises(SystemExit):
            bc._script_to_message(script, staging, width=29)
        with self.assertRaises(SystemExit):      # ...and a break with nothing after it
            bc._script_to_message([{'pinky': 'One.'}, {'stage_cut': 'business'}],
                                  staging, width=29)

    def test_a_stage_break_is_a_pause_and_not_a_box(self):
        """Scene box counts are locked and asserted against the YAML, so a directive that
        counted as an A-press would make every such assertion off by one."""
        self.assertIn('stage_cut', bc.SCRIPT_DIRECTIVES)
        self.assertEqual(2, bc.CH05_MOOSE_CHARGE_SLOT[2])
        self.assertEqual(3, len(self._scene()['script']))    # two boxes and the direction
        self.assertEqual(2, bc._script_box_count(self._scene()['script']))
        self.assertEqual(2, self._body().count('[A]'))

    def test_the_stage_direction_lives_in_the_data_not_in_a_comment(self):
        """It is the middle beat of the scene, so it is authored where the other two are."""
        direction = next(e['stage_cut'] for e in self._scene()['script']
                         if 'stage_cut' in e)
        for locked in ('BELLOWS', 'comes', 'straight at them'):
            self.assertIn(locked, direction)

    # ── the channel ────────────────────────────────────────────────────────────
    def test_the_body_wraps_at_the_bubble_29_not_the_scenic_42(self):
        for line in self._body().split('\n'):
            printable = re.sub(r'\[[^\]]*\]', '', line)
            self.assertLessEqual(len(printable), 29, 'bubble overflow: %r' % line)

    def test_both_locked_boxes_survive_word_for_word(self):
        self.assertEqual(['pinky', 'stage_cut', 'meesmickle'],
                         [next(iter(b)) for b in self._scene()['script']])
        plain = ' '.join(re.sub(r'\[[^\]]*\]', ' ', self._body()).split())
        for locked in ("...It's not running. Why isn't it running?!", 'You had to ask?'):
            self.assertIn(locked, plain, 'the 2026-07-29 lock lost a word')

    def test_pinky_keeps_the_far_right_he_holds_in_the_arrival(self):
        """He closes scene 4 on either arm and opens this one; a character who changes seats
        between his scenes reads as a different person each time. Meesmickle takes the widest
        two-shot the ladder offers against it, so setup and punchline come from opposite sides."""
        self.assertEqual(bc.CH05_ARRIVAL_PODIUMS['pinky'],
                         bc.CH05_MOOSE_CHARGE_PODIUMS['pinky'])
        seats = [bc.PODIUM_ORDER.index(p) for p in bc.CH05_MOOSE_CHARGE_PODIUMS.values()]
        self.assertGreater(abs(seats[0] - seats[1]), 1, 'neighbouring rungs overlap')
        self.assertIn('[OpenFarRight][LoadFace][FID_Neimi]', self._body())
        self.assertIn('[OpenMidLeft][LoadFace][FID_Gilliam]', self._body())

    # ── the charge ─────────────────────────────────────────────────────────────
    def test_the_charge_is_net_zero_so_the_fight_starts_where_parity_says(self):
        """It breaks out of the pen on screen and is put straight back. The pen is the tile
        the difficulty read is grounded on -- a charge that RELOCATED it would move a threat-14
        monster four tiles closer to the party for free."""
        pen, start, route = bc.ch05_moose_station(self._chap())
        self.assertEqual((10, 0), pen, "the parity-locked pen, vanilla's own rim tile")
        self.assertNotEqual(pen, route[-1], 'a charge that goes nowhere is not a charge')
        script = self._script()
        put = script.index('MOVE(0xffff, %s, %d, %d)' % (bc.CH05_MOOSE_PID, *start))
        run = script.index('MOVE_DEFINED(%s)' % bc.CH05_MOOSE_PID)
        back = script.index('MOVE(0xffff, %s, %d, %d)' % (bc.CH05_MOOSE_PID, *pen))
        self.assertLess(put, run, 'it is placed before it runs')
        self.assertLess(run, script.index('TEXTSHOW(0x%X)' % bc.CH05_MOOSE_QUIP_MSG), 'it charges BEFORE the punchline')
        self.assertLess(script.index('TEXTSHOW(0x%X)' % bc.CH05_MOOSE_QUIP_MSG), back, 'and is snapped back after it')

    def test_the_run_is_an_authored_multi_leg_route_not_one_MOVE(self):
        """Lengthened 2026-08-15 (Nicolas): four tiles straight down was over before it read.
        The path is the beat now -- top-right corner, left along the rim, then down at the
        party -- so it is a REDA queue, which turns where the author says rather than wherever
        the pathfinder cuts the corner. Row 0's walkable stretch is only x=10..14, which is what
        makes the corner start legal at all."""
        pen, start, route = bc.ch05_moose_station(self._chap())
        self.assertEqual((14, 0), start, 'the top-right corner')
        self.assertEqual(((10, 0), (10, 4)), route, 'left along the rim, then down')
        self.assertGreater(len(route), 1, 'a single leg is the straight line this replaced')
        self.assertIn(pen, route, 'the run passes THROUGH the pen it is hauled back to')
        script = self._script()
        for x, y in route:                       # one REDA pair per waypoint
            self.assertIn('SVAL(EVT_SLOT_1, 0x%X)' % ((y << 6) | x), script)
        self.assertNotIn('MOVE(0x0, %s' % bc.CH05_MOOSE_PID, script)

    def test_a_route_ending_on_the_pen_is_refused(self):
        """Then the snap-back is a no-op and the lunge is never undone on screen -- the run is
        meant to pass the pen and keep going at the party."""
        chap = self._chap()
        moose = next(e for e in chap['enemy_units'] if e['id'] == 'white-moose')
        moose['charge_route'] = [[10, 0]]
        with self.assertRaises(SystemExit):
            bc.ch05_moose_station(chap)

    def test_both_repositions_are_instant_and_unseen(self):
        """`Event2F_MoveUnit` short-circuits a negative speed to a bare `MoveUnit_` -- vanilla's
        own off-screen reposition (`ch14a` resets Carlyle with `MOVE(0xffff, ...)`). The first
        lands before the camera arrives, the second after it has cut south to the party, so
        neither is ever on screen."""
        script = self._script()
        pen, start, _route = bc.ch05_moose_station(self._chap())
        party = bc.ch05_party_camera_tile(self._chap())
        put = script.index('MOVE(0xffff, %s, %d, %d)' % (bc.CH05_MOOSE_PID, *start))
        back = script.index('MOVE(0xffff, %s, %d, %d)' % (bc.CH05_MOOSE_PID, *pen))
        self.assertLess(put, script.index('CAMERA(%d, %d)' % start),
                        'placed before the camera gets there')
        self.assertLess(script.index('REMA', script.index('TEXTSHOW(0x%X)' % bc.CH05_MOOSE_QUIP_MSG)), back,
                        'the bubble is down before the reset')
        self.assertLess(script.index('CAMERA(%d, %d)' % party), back,
                        'the camera is on the party before the reset')

    def test_an_unreachable_charge_tile_is_a_hang_and_is_gated(self):
        """MOVE + ENUN to a tile the unit cannot WALK to never returns -- ch04's own soft-lock,
        on this same animal. The flood fill runs at injection time."""
        src = open(os.path.join(bc.REPO, 'tools', 'build_campaign.py'),
                   encoding='utf-8').read()
        self.assertIn("'the white moose (ch05 scene 7)'", src)
        maps_dir = os.path.join(bc.REPO, 'campaigns', self.CAMPAIGN, 'maps')
        _pen, start, route = bc.ch05_moose_station(self._chap())
        for leg in route:      # every leg, from where the run BEGINS -- not from the pen
            bc.assert_scripted_move_reachable(maps_dir, bc.CH05_LAYOUT[1], start, leg,
                                              bc.CH04_MOOSE_MOV_TABLE, 'test')

    def test_a_missing_charge_tile_is_refused_rather_than_shipped(self):
        chap = self._chap()
        moose = next(e for e in chap['enemy_units'] if e['id'] == 'white-moose')
        del moose['charge_route']
        with self.assertRaises(SystemExit):
            bc.ch05_moose_station(chap)

    # ── the camera ─────────────────────────────────────────────────────────────
    def test_no_party_unit_is_named_for_the_camera(self):
        """ch05 deploys 9 of a 10-unit pool, so BOTH of this scene's speakers can be benched --
        and a benched unit is still in the array (US_NOT_DEPLOYED) at stale coordinates, so
        `CUMO_CHAR` would pan to nowhere rather than fail. The bubble does not need a unit:
        `StartTalkOpen` anchors it to the speaking FACE SLOT."""
        block = bc.ch05_moose_charge_block(bc.CH05_MOOSE_PID,
                                           bc.ch05_moose_station(self._chap()),
                                           bc.ch05_party_camera_tile(self._chap()))
        self.assertNotIn('CUMO_CHAR', block)
        self.assertIn('CUMO_AT', block)

    def test_every_framing_is_a_CAMERA_and_not_a_bare_CUMO(self):
        """`EventDisplayCursor_Loop` calls `PutMapCursor` and nothing else -- a CUMO draws a
        cursor and never scrolls. The first cut of this wiring used CUMO alone for both
        framings; the run showed the map never cutting south, because what was moving the view
        was whatever `LOMA` left behind. Vanilla pairs the two ahead of its own 0x9C4."""
        block = bc.ch05_moose_charge_block(bc.CH05_MOOSE_PID,
                                           bc.ch05_moose_station(self._chap()),
                                           bc.ch05_party_camera_tile(self._chap()))
        _pen, start, _route = bc.ch05_moose_station(self._chap())
        party = bc.ch05_party_camera_tile(self._chap())
        for tile in (start, party):
            self.assertIn('CAMERA(%d, %d)' % tile, block)
            self.assertLess(block.index('CAMERA(%d, %d)' % tile),
                            block.index('CUMO_AT(%d, %d)' % tile),
                            'the scroll comes before the pointer')
        self.assertEqual(block.count('CAMERA'), block.count('CUMO_AT'))

    def test_the_map_comes_up_on_the_PARTY_for_turn_1(self):
        """Vanilla's 0x9C4 ends framed on the deploy pocket and so does ours. It is also what
        hides the snap back: the moose's pen is off the bottom of that view."""
        block = bc.ch05_moose_charge_block(bc.CH05_MOOSE_PID,
                                           bc.ch05_moose_station(self._chap()),
                                           bc.ch05_party_camera_tile(self._chap()))
        party = bc.ch05_party_camera_tile(self._chap())
        self.assertLess(block.index('REMA'), block.index('CAMERA(%d, %d)' % party),
                        'the bubble is down before the cut')

    def test_the_frame_holds_ONE_position_across_the_break(self):
        """`[BreakTalk]` only LOCKS the talk proc -- the bubble stays up and the faces stay
        loaded -- so a camera move inside the message would scroll the map out from under an
        open bubble. The frame goes where the LINE is about, and stays there until REMA."""
        block = bc.ch05_moose_charge_block(bc.CH05_MOOSE_PID,
                                           bc.ch05_moose_station(self._chap()),
                                           bc.ch05_party_camera_tile(self._chap()))
        _pen, start, _route = bc.ch05_moose_station(self._chap())
        head = block[:block.index('REMA')]
        self.assertEqual(1, head.count('CUMO_AT'))
        self.assertIn('CUMO_AT(%d, %d)' % start, head)

    def test_the_party_framing_is_asserted_against_the_real_deploy_slots(self):
        """Vanilla's own `CAMERA(5, 18)` for this beat, and ours because the retile lifts Ch5's
        nine start tiles 1:1. A re-paint that moved the pocket would leave the last shot before
        turn 1 holding on an empty corner, silently."""
        chap = self._chap()
        self.assertEqual((5, 18), bc.ch05_party_camera_tile(chap))
        self.assertIn([5, 18], chap['deployment']['deploy_slots'])
        chap['deployment']['deploy_slots'] = [[0, 0]]
        with self.assertRaises(SystemExit):
            bc.ch05_party_camera_tile(chap)

    # ── placement in the beginning script ──────────────────────────────────────
    def test_the_debug_boot_lands_ON_the_beat_and_skips_the_approved_footage(self):
        """`--ch05-moose`. Scene 7 is the last beat of a ~52-A-press opening, so every film of
        it replayed four backdrop scenes, PREP, the join and Sahnar's monologue to reach ten
        seconds of moose -- Nicolas stopped a run over exactly that (2026-08-15). Iterating on a
        late beat has to cost a BUILD, not a playthrough."""
        seed = '    LOAD1(0x1, %s)\n    ENUN\n' % bc.CH05_BOOT_SEED_TABLE
        dbg = bc.ch05_beginning_script(self._chap(), 'CHARACTER_ARTUR', bc.CH05_SAHNAR_TABLE,
                                       'CHARACTER_MARISA', seed_load=seed, moose_only=True)
        self.assertIn('TEXTSHOW(0x%X)' % bc.CH05_MOOSE_CHARGE_SLOT[1], dbg)
        self.assertIn('LOMA(0x%X)' % bc.CH05_HOST_INDEX, dbg)
        self.assertIn(bc.CH05_LINE_TABLE, dbg, 'the line is where the MOOSE comes from')
        self.assertIn(bc.CH05_BOOT_SEED_TABLE, dbg, 'and the seed is the party to cut back to')
        for skipped in (bc.CH05_OPENING_BG, bc.CH05_ARRIVAL_BG,
                        'CALL(%s)' % bc.CH05_PREP_SCRIPT,
                        'TEXTSHOW(0x%X)' % bc.CH05_BASIL_JOIN_SLOT[1],
                        'TEXTSHOW(0x%X)' % bc.CH05_SAHNAR_ALONE_SLOT[1]):
            self.assertNotIn(skipped, dbg, 'the debug boot replays nothing already approved')

    def test_the_debug_boot_refuses_to_exist_without_a_party(self):
        """It skips Preparations, so `--ch05-boot`'s seed is the only thing left that would put
        one on the map -- and the beat ends by cutting south to look at it."""
        with self.assertRaises(SystemExit):
            bc.ch05_beginning_script(self._chap(), 'CHARACTER_ARTUR', bc.CH05_SAHNAR_TABLE,
                                     'CHARACTER_MARISA', moose_only=True)

    def test_the_shipping_script_is_untouched_by_the_debug_flag(self):
        """A debug boot that changed the real opening would be worse than no debug boot."""
        real = self._script()
        for beat in (bc.CH05_BASIL_JOIN_SLOT[1], bc.CH05_SAHNAR_ALONE_SLOT[1],
                     bc.CH05_MOOSE_CHARGE_SLOT[1]):
            self.assertIn('TEXTSHOW(0x%X)' % beat, real)
        self.assertIn('CALL(%s)' % bc.CH05_PREP_SCRIPT, real)

    def test_it_is_the_LAST_beat_before_the_map(self):
        script = self._script()
        self.assertLess(script.index('TEXTSHOW(0x%X)' % bc.CH05_SAHNAR_ALONE_SLOT[1]),
                        script.index('TEXTSHOW(0x%X)' % bc.CH05_MOOSE_CHARGE_SLOT[1]))
        self.assertLess(script.index('TEXTSHOW(0x%X)' % bc.CH05_MOOSE_CHARGE_SLOT[1]),
                        script.index('ENUT(8)'))

    def test_it_plays_AFTER_prep_and_brings_no_fade_of_its_own(self):
        """Scene 5 already brought the screen up after the prep prologue's fade to black; 6
        and 7 ride it. A fade here would flash the map through black on the last beat."""
        script = self._script()
        self.assertLess(script.index('CALL(%s)' % bc.CH05_PREP_SCRIPT),
                        script.index('TEXTSHOW(0x%X)' % bc.CH05_MOOSE_CHARGE_SLOT[1]))
        # It inherits scene 5's fade-up, so nothing between the join and its own first box
        # goes dark. What follows that box IS a fade cycle, and deliberately: the bellow is a
        # full-screen CG over the map, so it fades down to the image and back up to the map.
        gap = script[script.index('TEXTSHOW(0x%X)' % bc.CH05_BASIL_JOIN_SLOT[1]):
                     script.index('TEXTSHOW(0x%X)' % bc.CH05_MOOSE_CHARGE_SLOT[1])]
        self.assertNotIn('FADU', gap)
        self.assertNotIn('FADI', gap)
        bellow = script[script.index('TEXTSHOW(0x%X)' % bc.CH05_MOOSE_CHARGE_SLOT[1]):
                        script.index('TEXTSHOW(0x%X)' % bc.CH05_MOOSE_QUIP_MSG)]
        # The image CUTS in -- nothing fades before it, or the beat reads as leaving the
        # scene rather than as something appearing over it (Nicolas: "seamless, as if it was
        # part of the dialogue"). Coming BACK needs a short fade because CLEAN blanks.
        self.assertEqual(0, bellow.count('FADI'), 'nothing fades down to the image')
        self.assertNotIn('FADU(16)', bellow, 'and nothing fades up like a new scene')
        self.assertIn('FADU(4)', bellow, 'CLEAN blanks, so the map needs a short fade back')

    def test_the_moose_is_already_on_the_map_and_is_not_loaded_again(self):
        """It has stood in the turn-1 line since before prep -- this beat only has to look at
        it. A LOAD1 here would put a second moose on the rim."""
        script = self._script()
        self.assertNotIn('LOAD1(0x1, %s)' % bc.CH05_MOOSE_PID, script)
        moose = next(e for e in self._chap()['enemy_units'] if e['id'] == 'white-moose')
        self.assertIsNone(moose.get('arrives_turn'), 'it rides the turn-1 line')

    def test_the_music_drops_out_under_the_bellow(self):
        """Vanilla's own punctuation at exactly this kind of pause (MSG_9BF's BreakTalk gap),
        and it leaves "You had to ask?" landing in silence a beat before the map's own track."""
        script = self._script()
        self.assertLess(script.index('MUSCMID(SONG_SILENT)'), script.index('TEXTSHOW(0x%X)' % bc.CH05_MOOSE_QUIP_MSG))

    def test_the_moose_still_does_not_speak(self):
        """Locked 2026-07-03 as a mute white ghost, and re-locked by this chapter. The charge
        is stage direction; nothing gives it a box."""
        self.assertNotIn('white-moose', [next(iter(b)) for b in self._scene()['script']])
        self.assertNotIn('moose:', str(self._scene()['script']))


class Ch05ArenaTutorial(unittest.TestCase):
    """The Elven Tomb inherits vanilla Ch5's arena lesson on a live tile trigger (#264).

    The YAML's ``vanilla 0x9D5 + 0x9D6`` label is anatomy, not permission to write into
    ch04's host block. The live tutorial therefore owns two ids from ch05's real Ch6 host
    block and reaches them through a one-shot event on the arena tile itself.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return bc._load_chapter_yaml(self.CAMPAIGN, bc.CH05_CHAPTER_YAML)

    def _event(self):
        return next(e for e in self._chap()['events']
                    if e['trigger'] == 'arena_tile_visited')

    def test_the_two_messages_are_named_owned_and_inside_ch05s_host_block(self):
        self.assertEqual(0x9E6, bc.CH05_ARENA_FOUND_MSG)
        self.assertEqual(0x9E7, bc.CH05_ARENA_RULES_MSG)
        claimed = set(bc.HOSTED_CHAPTER_MESSAGE_IDS['ch05'])
        for msg in (bc.CH05_ARENA_FOUND_MSG, bc.CH05_ARENA_RULES_MSG):
            self.assertTrue(0x9E4 <= msg <= 0x9F3)
            self.assertIn(msg, claimed)
            self.assertEqual('ch05', bc.assert_message_ids_unique()[msg])

    def test_the_locked_six_boxes_keep_vanillas_one_plus_five_anatomy(self):
        event = self._event()
        self.assertEqual('vanilla 0x9D5 + 0x9D6', event['slot'])
        self.assertEqual(6, len(event['script']))
        self.assertEqual({'tutorial'}, {next(iter(box)) for box in event['script']})

        found, rules = bc.ch05_arena_messages(self._chap())
        self.assertEqual(1, found.count('[A]'))
        self.assertEqual(5, rules.count('[A]'))
        self.assertIn('[ToggleRed]arena', found)
        for phrase in ('one-on-one', 'twice', 'will not', 'press the B Button quickly'):
            self.assertIn(phrase, rules)

    def test_the_misc_list_fires_once_on_exactly_the_arena_tile(self):
        self.assertEqual('EVFLAG_TMP(13)', bc.CH05_ARENA_TUTORIAL_FLAG)
        location = bc.ch05_location_events(self._chap())
        misc = bc.ch05_misc_events()
        area = ('AREA(%s, %s, 12, 6, 12, 6)'
                % (bc.CH05_ARENA_TUTORIAL_FLAG, bc.CH05_ARENA_TRIGGER_SCRIPT))
        self.assertNotIn(area, location)
        self.assertEqual(1, misc.count(area))
        self.assertIn('DefeatBoss(%s)' % bc.CH05_ENDING_SCRIPT, misc)
        self.assertIn('CauseGameOverIfLordDies', misc)

    def test_the_trigger_preserves_tutorial_mode_and_vanillas_event_shape(self):
        trigger = bc.ch05_arena_trigger_script()
        self.assertIn('SVAL(EVT_SLOT_2, FACTION_ID_BLUE)', trigger)
        self.assertIn('CALL(EventScr_UnTriggerIfNotFaction)', trigger)
        self.assertLess(trigger.index('CALL(EventScr_UnTriggerIfNotFaction)'),
                        trigger.index('CALL(EventScr_CallOnTutorialMode)'))
        self.assertIn('SVAL(EVT_SLOT_2, %s)' % bc.CH05_ARENA_TUTORIAL_SCRIPT, trigger)
        self.assertIn('CALL(EventScr_CallOnTutorialMode)', trigger)

        tutorial = bc.ch05_arena_tutorial_script()
        self.assertLess(tutorial.index('TEXTSHOW(0x%X)' % bc.CH05_ARENA_FOUND_MSG),
                        tutorial.index('CAMERA(12, 6)'))
        self.assertIn('CURSOR_FLASHING(12, 6)', tutorial)
        self.assertLess(tutorial.index('CAMERA(12, 6)'),
                        tutorial.index('TEXTSHOW(0x%X)' % bc.CH05_ARENA_RULES_MSG))
        self.assertIn('ENUT(234)', tutorial)


class ArenaPresentation(unittest.TestCase):
    """Arena presentation is campaign/chapter data over untouched vanilla mechanics (#265)."""
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_the_welcome_screen_recolors_only_the_sky_and_the_awnings(self):
        delta = bc.arena_presentation_config(self.CAMPAIGN)['welcome_delta']
        base = bc.ARENA_FRONT_BASE_BANK
        sky = {(15 - base) * 16 + i for i in range(1, 9)} | {(12 - base) * 16 + 1}
        awnings = {(13 - base) * 16 + i for i in (1, 2, 3, 4, 10, 11, 15)}
        self.assertEqual(sky | awnings, set(delta),
                         'the coliseum EXTERIOR keeps its warm sandstone -- winter arrives '
                         'through the weather and the banners only (#265)')
        self.assertTrue(all(0 <= word <= 0x7FFF for word in delta.values()))

    def test_the_welcome_masonry_is_never_named_at_all(self):
        # The rejected first pass held luminance and crushed the stone's saturation from
        # 0.29-0.74 to 0.10-0.20, which is why it read as washed out while passing every
        # numeric check we had. The masonry bank is now simply unmentionable.
        delta = bc.arena_presentation_config(self.CAMPAIGN)['welcome_delta']
        base = bc.ARENA_FRONT_BASE_BANK
        for i in range(2, 16):
            self.assertNotIn((12 - base) * 16 + i, delta,
                             'masonry index %d must stay byte-identical to vanilla' % i)

    def test_the_welcome_delta_only_rewrites_the_words_it_names(self):
        synthetic = [0x0200 + i for i in range(64)]
        delta = bc.arena_welcome_palette_delta(
            {'background': [{'bank': 13, 'index': 4, 'color': '#FFFFFF'}]}, 'fixture.yaml')
        words = bc.arena_welcome_palette_words(delta, vanilla=synthetic)
        target = (13 - bc.ARENA_FRONT_BASE_BANK) * 16 + 4
        self.assertEqual(0x7FFF, words[target])
        for i in range(64):
            if i != target:
                self.assertEqual(synthetic[i], words[i])

    # The combat backdrop is a DELTA over vanilla. These tests are written against a synthetic
    # vanilla palette wherever they can be, so they assert the composition rather than the
    # contents of a ROM that CI does not have (CI builds against 16MB of /dev/urandom).
    SYNTHETIC_VANILLA = {phase: [0x0100 + i for i in range(64)] for phase in 'ABC'}

    def test_live_campaign_recolors_the_floor_and_banners_and_nothing_else(self):
        delta = bc.arena_presentation_config(self.CAMPAIGN)['combat_delta']
        base = bc.ARENA_BATTLE_BG_BASE_BANK
        floor = {(9 - base) * 16 + i for i in (1, 2, 3, 4, 5, 6, 8, 9, 10)}
        banners = {(8 - base) * 16 + i for i in (4, 8)}
        self.assertEqual(floor | banners, set(delta),
                         'the coliseum may lose ONLY its sand floor and its red banners -- '
                         'every other word is vanilla stone, wood, gold or crowd (#265)')
        self.assertTrue(all(0 <= word <= 0x7FFF for word in delta.values()))

    def test_composition_preserves_a_words_per_phase_difference(self):
        # Vanilla animates three of its 64 words. A delta must leave any word it does not
        # name differing across A/B/C exactly as it did, or the ten-frame cycle flattens.
        animated = 40
        vanilla = {phase: [0x0100 + i for i in range(64)] for phase in 'ABC'}
        for offset, phase in enumerate('ABC'):
            vanilla[phase][animated] = 0x2000 + offset
        delta = bc.arena_combat_palette_delta(
            {'background': [{'bank': 9, 'index': 3, 'color': '#FFFFFF'}]}, 'fixture.yaml')
        phases = bc.arena_combat_palette_words(delta, vanilla=vanilla)['background']
        self.assertEqual([0x2000, 0x2001, 0x2002], [phase[animated] for phase in phases],
                         'an unnamed word must keep animating across the three phases')

    def test_the_delta_only_rewrites_the_words_it_names(self):
        delta = bc.arena_combat_palette_delta(
            {'background': [{'bank': 9, 'index': 3, 'color': '#FFFFFF'}]}, 'fixture.yaml')
        out = bc.arena_combat_palette_words(delta, vanilla=self.SYNTHETIC_VANILLA)
        target = (9 - bc.ARENA_BATTLE_BG_BASE_BANK) * 16 + 3
        for phase, words in zip('ABC', out['background']):
            self.assertEqual(0x7FFF, words[target])
            for i in range(64):
                if i != target:
                    self.assertEqual(self.SYNTHETIC_VANILLA[phase][i], words[i])

    def test_the_delta_refuses_the_transparent_key(self):
        with self.assertRaises(SystemExit) as caught:
            bc.arena_combat_palette_delta(
                {'background': [{'bank': 8, 'index': 0, 'color': '#FFFFFF'}]}, 'fixture.yaml')
        self.assertIn('transparent key', str(caught.exception))

    def test_malformed_combat_delta_names_the_config_path_and_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = os.path.join(tmp, 'campaigns', 'fixture')
            os.makedirs(os.path.join(campaign, 'chapters'))
            config_path = os.path.join(campaign, 'campaign.yaml')
            with open(config_path, 'w') as f:
                f.write(textwrap.dedent('''
                    arena_presentation:
                      combat:
                        background: [["#000000"]]
                '''))
            with mock.patch.object(bc, 'REPO', tmp), \
                    mock.patch.object(bc, 'hosted_chapters', return_value=[]):
                with self.assertRaises(SystemExit) as caught:
                    bc.arena_presentation_config('fixture')
            self.assertIn(config_path, str(caught.exception))
            self.assertIn('arena_presentation.combat.background', str(caught.exception))

    def test_an_out_of_range_bank_names_the_four_banks_the_backdrop_owns(self):
        with self.assertRaises(SystemExit) as caught:
            bc.arena_combat_palette_delta(
                {'background': [{'bank': 3, 'index': 5, 'color': '#FFFFFF'}]}, 'fixture.yaml')
        self.assertIn('[6, 7, 8, 9]', str(caught.exception))

    def test_ch05_declares_a_real_collision_free_attendant_portrait(self):
        cfg = bc.arena_presentation_config(self.CAMPAIGN)
        override = cfg['chapters'][bc.CH05_HOST_INDEX]
        self.assertTrue(os.path.isfile(override['portrait_path']))
        self.assertEqual('Glen', override['face_slot'])
        self.assertEqual(0x4B, override['face_id'])
        taken = (set(bc.PORTRAIT_MAP.values()) | set(bc.GUEST_PORTRAIT_MAP.values())
                 | set(bc.CH02_CHWINGA_PORTRAIT_SLOT.values())
                 | {slot for _mug, slot, _rc in bc.CH05_VISIT_FACES.values()})
        self.assertNotIn(override['face_slot'], taken)

    def test_attendant_scales_the_fe_repo_chibi_to_fill_the_counter_envelope(self):
        override = bc.arena_presentation_config(self.CAMPAIGN)['chapters'][bc.CH05_HOST_INDEX]
        bust = bc._vendor_mug_to_arena_bust(override['portrait_path'])
        painted = Image.new('1', bust.size)
        painted.putdata([pixel != 0 for pixel in bust.getdata()])
        self.assertEqual((24, 0, 72, 48), painted.getbbox())
        sheet = Image.open(override['portrait_path']).convert('RGB')
        source = sheet.crop((96, 16, 128, 48)).resize(
            (48, 48), Image.Resampling.NEAREST)
        actual = bust.crop((24, 0, 72, 48)).convert('RGB')
        key = sheet.getpixel((0, 0))
        self.assertEqual(
            [bc.PORTRAIT_TRANSPARENT_RGB if pixel == key else pixel
             for pixel in source.getdata()],
            list(actual.getdata()))

    def test_welcome_delta_validation_names_the_config_path_and_field(self):
        with self.assertRaises(SystemExit) as caught:
            bc.arena_welcome_palette_delta({'background': []}, '/tmp/campaign.yaml')
        self.assertIn('/tmp/campaign.yaml', str(caught.exception))
        self.assertIn('arena_presentation.welcome.background', str(caught.exception))
        with self.assertRaises(SystemExit) as caught:
            bc.arena_welcome_palette_delta(
                {'background': [{'bank': 13, 'index': 4, 'color': 'ice'}]},
                '/tmp/campaign.yaml')
        self.assertIn('arena_presentation.welcome.background[0]', str(caught.exception))
        self.assertIn('#RRGGBB', str(caught.exception))

    def _attendant_fixture(self, tmp, face_slot, portrait='ravisin.png'):
        campaign = os.path.join(tmp, 'campaigns', 'fixture')
        os.makedirs(os.path.join(campaign, 'chapters'), exist_ok=True)
        with open(os.path.join(campaign, 'campaign.yaml'), 'w') as f:
            f.write('{}\n')
        shutil.copy(os.path.join(bc._bust_dir(self.CAMPAIGN), 'ravisin.png'),
                    os.path.join(campaign, portrait))
        chapter_path = os.path.join(campaign, 'chapters', 'ch05-fixture.yaml')
        with open(chapter_path, 'w') as f:
            f.write(textwrap.dedent('''
                chapter_number: 5
                arena_presentation:
                  attendant:
                    portrait: %s
                    face_slot: %s
            ''' % (portrait, face_slot)))
        return chapter_path

    def test_an_attendant_may_not_squat_on_a_slot_the_cast_already_owns(self):
        # inject_arena_attendant_portraits runs AFTER inject_portraits, so a collision would
        # overwrite a player character's face with a green build and no warning.
        with tempfile.TemporaryDirectory() as tmp:
            chapter_path = self._attendant_fixture(tmp, bc.PORTRAIT_MAP['braulo'])
            with mock.patch.object(bc, 'REPO', tmp), \
                    mock.patch.object(bc, 'hosted_chapters', return_value=[]):
                with self.assertRaises(SystemExit) as caught:
                    bc.arena_presentation_config('fixture')
            self.assertIn(chapter_path, str(caught.exception))
            self.assertIn('already dressed by the campaign cast', str(caught.exception))

    def test_two_chapters_may_not_share_a_slot_with_different_attendants(self):
        overrides = {
            6: {'face_slot': 'Glen', 'portrait_path': '/a.png', 'face_id': 0x4B,
                'chapter_path': '/ch05.yaml'},
            7: {'face_slot': 'Glen', 'portrait_path': '/b.png', 'face_id': 0x4B,
                'chapter_path': '/ch06.yaml'},
        }
        with mock.patch.object(bc, 'arena_presentation_config',
                               return_value={'chapters': overrides}):
            with self.assertRaises(SystemExit) as caught:
                bc.inject_arena_attendant_portraits('fixture', verbose=False)
        self.assertIn('/ch06.yaml', str(caught.exception))
        self.assertIn('already dressed with a different portrait', str(caught.exception))

    def test_missing_attendant_portrait_names_the_chapter_and_asset_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            campaign = os.path.join(tmp, 'campaigns', 'fixture')
            chapters = os.path.join(campaign, 'chapters')
            os.makedirs(chapters)
            with open(os.path.join(campaign, 'campaign.yaml'), 'w') as f:
                f.write('{}\n')
            chapter_path = os.path.join(chapters, 'ch05-fixture.yaml')
            with open(chapter_path, 'w') as f:
                f.write(textwrap.dedent('''
                    chapter_number: 5
                    arena_presentation:
                      attendant:
                        portrait: portraits/vendor/missing.png
                        face_slot: Glen
                '''))
            with mock.patch.object(bc, 'REPO', tmp):
                with self.assertRaises(SystemExit) as caught:
                    bc.arena_presentation_config('fixture')
            self.assertIn(chapter_path, str(caught.exception))
            self.assertIn('portraits/vendor/missing.png', str(caught.exception))

    def test_vendored_attendant_is_the_exact_pinned_fe_repo_file_and_is_credited(self):
        override = bc.arena_presentation_config(self.CAMPAIGN)['chapters'][bc.CH05_HOST_INDEX]
        with open(override['portrait_path'], 'rb') as f:
            self.assertEqual(
                'b5a1bbfb2e2c20fc6c77c689936784166277c1652faf37c7f6c91935cea6583f',
                hashlib.sha256(f.read()).hexdigest())
        with open(os.path.join(bc.REPO, 'CREDITS.md'), encoding='utf-8') as f:
            credits = f.read()
        self.assertIn('Generic Pretsel', credits)
        self.assertIn('3abc62d4f0a12d300911b51788719f950c5f45b9', credits)

    def test_missing_configuration_generates_untouched_vanilla_fallbacks(self):
        source = bc.arena_presentation_source(None, {})
        self.assertIn('return gPal_ArenaBuildingFront;', source)
        self.assertIn('return 0x67;', source)
        self.assertNotIn('gMSArenaBuildingFrontPalette[', source)

    def test_live_binding_selects_ch05_and_falls_back_for_other_chapters(self):
        cfg = bc.arena_presentation_config(self.CAMPAIGN)
        words = bc.arena_welcome_palette_words(cfg['welcome_delta'],
                                               vanilla=[0x0200 + i for i in range(64)])
        source = bc.arena_presentation_source(words, cfg['chapters'])
        self.assertIn('gMSArenaBuildingFrontPalette[64]', source)
        self.assertIn('case %d:' % bc.CH05_HOST_INDEX, source)
        self.assertIn('return 0x4B;', source)
        self.assertIn('return 0x67;', source)

    def test_engine_hook_reaches_real_arena_ui_init_without_replacing_art_or_tsa(self):
        vanilla = bc.vanilla_decomp_text('src/uiarena.c')
        patched = eh._patch_arena_presentation_text(vanilla)
        init = patched[patched.index('void ArenaUi_Init'):patched.index('void sub_80B5970')]
        self.assertIn('StartTalkFace(GetArenaPresentationFace()', init)
        self.assertIn('ApplyPalettes(GetArenaPresentationPalette(), 0xC, 4);', init)
        self.assertIn('Decompress(gGfx_ArenaBuildingFront,', init)
        self.assertIn('CallARM_FillTileRect(gBG3TilemapBuffer, gTsa_ArenaBuildingFront,', init)
        self.assertNotIn('StartTalkFace(0x67,', init)
        self.assertNotIn('ApplyPalettes(gPal_ArenaBuildingFront,', init)

    def test_combat_backdrop_hook_uses_the_cycle_binding_from_frame_zero(self):
        vanilla = bc.vanilla_decomp_text('src/banim-ekrarena.c')
        transform = getattr(eh, '_patch_arena_battle_background_text', lambda text: text)
        patched = transform(vanilla)
        self.assertIn('extern u16 * CONST_DATA PalArray_ArenaBattleBg[];', patched)
        self.assertIn('CpuFastCopy(PalArray_ArenaBattleBg[0], gPaletteBuffer + 0x60, 0x80);',
                      patched)
        self.assertIn('LZ77UnCompVram(Img_ArenaBattleBg,', patched)
        self.assertIn('LZ77UnCompWram(Tsa_ArenaBattleBg,', patched)
        self.assertIn('0, 10,\n        1, 10,\n        2, 10,', patched)

    def test_combat_backdrop_source_repoints_all_three_phases_with_vanilla_fallback(self):
        cfg = bc.arena_presentation_config(self.CAMPAIGN)
        vanilla = bc.vanilla_decomp_text('src/banim-ekrarena.c')
        generate = getattr(bc, 'arena_battle_background_source',
                           lambda text, _phases: text)
        configured = generate(vanilla, bc.arena_combat_palette_words(
            cfg['combat_delta'], vanilla=self.SYNTHETIC_VANILLA)['background'])
        for suffix in 'ABC':
            self.assertIn('gMSArenaBattleBgPalette%s[64]' % suffix, configured)
        cycle = configured[configured.index('u16 * CONST_DATA PalArray_ArenaBattleBg[] ='):]
        self.assertIn('gMSArenaBattleBgPaletteA,', cycle)
        self.assertIn('gMSArenaBattleBgPaletteB,', cycle)
        self.assertIn('gMSArenaBattleBgPaletteC,', cycle)

        fallback = generate(vanilla, None)
        self.assertNotIn('gMSArenaBattleBgPalette', fallback)
        fallback_cycle = fallback[fallback.index('u16 * CONST_DATA PalArray_ArenaBattleBg[] ='):]
        self.assertIn('Pal_ArenaBattleBg_A,', fallback_cycle)
        self.assertIn('Pal_ArenaBattleBg_B,', fallback_cycle)
        self.assertIn('Pal_ArenaBattleBg_C,', fallback_cycle)


    def test_vanilla_arena_path_bypasses_the_normal_terrain_platform(self):
        vanilla = bc.vanilla_decomp_text('src/banim-ekrdispup.c')
        setup = vanilla[vanilla.index('void EfxClearScreenFx(void)'):
                        vanilla.index('void sub_8051E00(void)')]
        self.assertIn('if (GetBattleAnimArenaFlag() == false)\n        sub_8051E00();', setup)
        self.assertIn('else\n        CpuFastFill16(0, gBG2TilemapBuffer, 0x800);', setup)

    def test_arena_source_is_restored_and_both_pipeline_steps_are_live(self):
        self.assertIn('src/uiarena.c', bc.PATCHED_DECOMP_FILES)
        self.assertIn('src/banim-ekrarena.c', bc.PATCHED_DECOMP_FILES)
        self.assertIn('src/banim_terrain_data.c', bc.PATCHED_DECOMP_FILES)
        with open(os.path.join(bc.REPO, 'tools', 'build_campaign.py'),
                  encoding='utf-8') as f:
            build = f.read()
        self.assertIn('engine_hooks._patch_arena_presentation()', build)
        self.assertIn('inject_arena_presentation(args.campaign)', build)


class Ch05VillageRaidRace(unittest.TestCase):
    """ch05's declared structure: the eruption's dead race the party for the four reliquaries,
    and saving all four pays out (#25). Vanilla Ch5 is the reference for both halves -- it wires
    the same four tiles on EVFLAG_TMP(8..11), sends all six of its reinforcements in on AI_B_04
    (PillageThenPursue), and gates a Guiding Ring on four CHECK_EVENTIDs at the ending.

    None of it was wired here while the YAML claimed it was, so every test in this class pins a
    piece that shipped absent rather than wrong.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return bc._load_chapter_yaml(self.CAMPAIGN, bc.CH05_CHAPTER_YAML)

    def test_each_reliquary_owns_an_event_id_ch05_does_not_already_spend(self):
        """We cannot copy vanilla's 8..11. ch05's opening ends on ENUT(8) -- which is
        EvtSetFlag, not un-trigger, and a vanilla prep idiom (ch12a/ch18a) -- and the Sahnar
        Talk holds 7. A site on either would start the chapter already visited: its VILL and its
        raider hook both disarmed, and the payout counting a door nobody opened."""
        flags = bc.CH05_VILLAGE_FLAGS
        self.assertEqual(set(flags), {v['id'] for v in self._chap()['villages']},
                         'every reliquary needs an id, and only the reliquaries')
        self.assertEqual(len(set(flags.values())), len(flags), 'two sites share one flag')
        self.assertNotIn('0', flags.values(), 'flag 0 is EVFLAG_ALWAYS_FALSE')
        for spent in (bc.CH05_SAHNAR_TALK_FLAG, 'EVFLAG_TMP(8)'):
            self.assertNotIn(spent, flags.values(),
                             '%s is already spent elsewhere in ch05' % spent)

    def test_the_location_list_arms_every_reliquary_with_its_flag(self):
        """Declaring the flags is not wiring them. The Location list is the only place the
        engine reads them, and it shipped `Village(0, ..)` for all four."""
        body = bc.ch05_location_events(self._chap())
        for vid, flag in bc.CH05_VILLAGE_FLAGS.items():
            self.assertIn('Village(%s, %s,' % (flag, bc.CH05_VILLAGE_SLOTS[vid][0]), body)
        self.assertNotIn('Village(0,', body, 'an unflagged site cannot be raided or counted')
        self.assertIn('Armory(', body)        # the elven store rides the same list
        self.assertIn('Vendor(', body)

    def _changes(self):
        return bc.ch05_map_changes(self._chap(), self._maps_dir())

    def _maps_dir(self):
        return os.path.join(bc.REPO, 'campaigns', self.CAMPAIGN, 'maps')

    def _tileset(self):
        import map_tileset_tool as mt
        return mt._tileset_from_dir(os.path.join(self._maps_dir(), 'tilesets', bc.CH05_TILESET))

    def test_a_raided_site_is_ruined_across_vanillas_own_footprint(self):
        """AiPillageAction looks the change up at (x, y - 1) -- the tile ABOVE the door, where
        Village()'s destruction LOCA sits -- so a change on the door alone is never found and
        the site survives its own sacking. Vanilla answers with a 3x2 at (x-1, y-1), which
        covers the lookup tile AND the door, and we inherit its footprint with its geometry."""
        changes = self._changes()
        tileset, ruins = self._tileset(), bc.terrain_ids()['TERRAIN_RUINS_REGULAR']
        for village in self._chap()['villages']:
            x, y = village['tile']
            block = [c for c in changes if (c[0], c[1]) == (x - 1, y - 1)]
            self.assertEqual(1, len(block), 'no ruin change for %r' % village['id'])
            _x, _y, w, h, tiles, _why = block[0]
            self.assertEqual((3, 2), (w, h))
            self.assertEqual(6, len(tiles))
            for m in tiles:
                self.assertEqual(ruins, tileset.terrain(m),
                                 'metatile %d is not ruins -- a "destroyed" site FE8 still '
                                 'reads as a village stays lootable and visitable' % m)
                self.assertFalse(bc._is_blank_metatile(tileset, m),
                                 'ruin writes blank metatile %d' % m)

    def test_a_visited_site_shuts_its_door(self):
        changes = self._changes()
        for village in self._chap()['villages']:
            door = [c for c in changes if list(c[:4]) == village['tile'] + [1, 1]]
            self.assertEqual(1, len(door), 'no door change for %r' % village['id'])
            self.assertEqual(bc.terrain_ids()['TERRAIN_VILLAGE_CLOSED'],
                             self._tileset().terrain(door[0][4][0]))

    def test_the_ruins_are_registered_before_the_doors(self):
        """Order is the whole correctness argument, and it is invisible in a screenshot.
        GetMapChangeIdAt keeps the LAST region covering a tile (bmtrick.c), and the 3x2 ruin
        overlaps its own door. Doors-first would make VISITING a site ruin the building."""
        changes = self._changes()
        doors = {tuple(v['tile']) for v in self._chap()['villages']}
        last_ruin = max(i for i, c in enumerate(changes) if (c[0], c[1]) not in doors)
        first_door = min(i for i, c in enumerate(changes) if (c[0], c[1]) in doors)
        self.assertLess(last_ruin, first_door,
                        'a door change ahead of a ruin change: visiting would ruin the site')

    def test_every_eruption_wave_races_the_sites(self):
        """Vanilla Ch5 sends ALL SIX of its reinforcements in on AI_B_04 -- three pairs, turns
        2/6/8, every one a pillager. Ours spawn on those same three tile-pairs, so 'we do what
        vanilla does' (Nicolas, 2026-08-09) means all three waves raid. Without a pillage AI on
        the board nothing on the map can reach a reliquary and the race is prose."""
        waves = [e for e in self._chap()['enemy_units'] if e.get('arrives_turn')
                 and e['id'] != 'sahnar']
        self.assertEqual(3, len(waves), 'ch05 has three eruption waves')
        for wave in waves:
            self.assertEqual('raider', wave.get('ai_pattern'),
                             '%s does not race the reliquaries' % wave['id'])
        self.assertEqual('{0x0, 0x4, 0x9, 0x0}', bc.CH05_AI['raider'],
                         "vanilla Ch5's own raider AI, byte for byte (AI_B_04 = "
                         'AiScr_AiB_PillageThenPursue)')

    def test_a_raider_row_carries_the_pillage_ai_into_the_table(self):
        rows = '\n'.join(bc.ch05_enemy_rows(self._chap(), arrives_turn=2, exclude=('sahnar',)))
        self.assertIn('.ai = {0x0, 0x4, 0x9, 0x0},', rows)

    # -- the payout: vanilla's Guiding-Ring-on-all-four, which is why the flags exist ---------
    def test_the_bonus_is_withheld_unless_every_site_survived(self):
        """Vanilla's shape exactly: one CHECK_EVENTID per site, each branching PAST the gift the
        moment a flag is unset, so any single unset id skips the whole payout."""
        body = bc.save_all_bonus_script({'a': 'EVFLAG_TMP(9)', 'b': 'EVFLAG_TMP(10)'},
                                        'ITEM_GUIDINGRING')
        self.assertEqual(2, body.count('CHECK_EVENTID('))
        self.assertIn('CHECK_EVENTID(EVFLAG_TMP(9))', body)
        self.assertIn('CHECK_EVENTID(EVFLAG_TMP(10))', body)
        self.assertEqual(2, body.count('BEQ('), 'every check needs its own skip branch')
        skip = re.search(r'BEQ\((0x[0-9A-F]+), EVT_SLOT_C, EVT_SLOT_0\)', body).group(1)
        self.assertIn('LABEL(%s)' % skip, body)
        self.assertLess(body.index('GIVEITEMTO'), body.index('LABEL(%s)' % skip),
                        'the gift must sit INSIDE the branch it is gated by')

    def test_the_bonus_goes_to_the_leader_not_the_last_unit_to_move(self):
        """CHAR_EVT_ACTIVE_UNIT is the village idiom -- the unit who walked in. There is no
        active unit at the ending, so the payout uses vanilla's CHAR_EVT_PLAYER_LEADER."""
        body = bc.save_all_bonus_script({'a': 'EVFLAG_TMP(9)'}, 'ITEM_GUIDINGRING')
        self.assertIn('SVAL(EVT_SLOT_3, ITEM_GUIDINGRING)', body)
        self.assertIn('GIVEITEMTO(CHAR_EVT_PLAYER_LEADER)', body)

    def test_ch05_pays_out_a_vanilla_item_at_its_ending(self):
        """The bonus is vanilla Ch5's own Guiding Ring. It used to be a `crest-of-cold-iron`,
        an item that existed in no table and was handed over by nothing -- and the campaign
        renames items only for the Goodberry and Tourmaline (Nicolas, 2026-08-09)."""
        bonus = self._chap()['economy']['save_all_bonus']
        self.assertIn(bonus, bc.CH05_ITEM_IDS, 'the save-all bonus must be a real FE item')
        self.assertEqual('ITEM_GUIDINGRING', bc.CH05_ITEM_IDS[bonus])
        ending = bc.ch05_ending_script(self._chap())
        self.assertEqual(4, ending.count('CHECK_EVENTID('), 'all four sites gate the payout')
        self.assertIn('SVAL(EVT_SLOT_3, ITEM_GUIDINGRING)', ending)
        self.assertTrue(ending.rstrip().endswith('ENDA\n}'))

    def test_the_ring_is_handed_over_before_the_screen_goes_black(self):
        """Vanilla restores the screen (`EventScr_RemoveBGIfNeeded`) immediately ahead of its own
        GIVEITEMTO, and on a full pack the reason is not cosmetic: the give runs
        HandleNewItemGetFromDrop, which opens a BLOCKING convoy/discard menu. Behind a FADI the
        player is operating that menu blind."""
        ending = bc.ch05_ending_script(self._chap())
        self.assertLess(ending.index('GIVEITEMTO'), ending.index('FADI(16)'),
                        'the ring is handed over under a black screen')

    def test_the_payout_gates_only_on_sites_the_location_list_armed(self):
        """The ending used to gate on the module dict while the Location list armed whatever the
        YAML declared. Drop a village and the ring becomes unobtainable, with a green build."""
        chap = self._chap()
        chap['villages'] = chap['villages'][:2]
        ending = bc.ch05_ending_script(chap)
        self.assertEqual(2, ending.count('CHECK_EVENTID('),
                         'the payout must check exactly the sites that exist')

    def test_no_ch05_enemy_drops_anything(self):
        """Vanilla Ch5 has ZERO droppers -- Saar included. Ravisin used to carry a `drops:`
        block naming the crest, on a key the injector never reads, so it was decoration that
        read like wiring."""
        for enemy in self._chap()['enemy_units']:
            self.assertNotIn('drops', enemy, '%s carries a dead `drops:` key' % enemy['id'])
            self.assertNotIn('item_drop', enemy, '%s drops loot vanilla Ch5 never does'
                             % enemy['id'])


class Ch05RecruitIdentities(unittest.TestCase):
    """Basil and Sahnar are CAST MEMBERS, not scenery (#25).

    Both shipped their art a slice ahead of their wiring (#179/#181) and then sat inert,
    because a unit with no PORTRAIT_MAP slot has no identity to ride: no name, no bust, no
    stat line, no map sprite, no death quote, and -- the blocker #25 kept hitting -- nothing
    for a Talk to address. This class pins the identity half; the ch05 event wiring that
    USES it is Ch05TalkRecruits.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'
    CH05 = 5

    def test_both_ride_collision_free_identity_slots(self):
        # Same call as Trex->Rennac and Lupin->Duessel: a vanilla slot absent from our
        # ch00-08 and referenced nowhere else, so dressing it can collide with nothing.
        self.assertEqual(bc.PORTRAIT_MAP['basil'], 'Artur')
        self.assertEqual(bc.PORTRAIT_MAP['sahnar'], 'Marisa')
        slots = list(bc.PORTRAIT_MAP.values())
        self.assertEqual(len(slots), len(set(slots)), 'two cast members share one slot')
        self.assertFalse(set(slots) & set(bc.GUEST_PORTRAIT_MAP.values()),
                         'a cast slot collides with a cutscene guest slot')

    def test_the_healer_split_is_donor_deep(self):
        # decisions.md differentiates the army's two healers by DONOR (Moulder durable
        # war-priest vs Natasha frail mage-healer), which only exists once Basil has a
        # STAT_DONOR row -- the YAML design record cannot do it alone. Since 2026-08-08 the
        # split is ALSO class-deep (Sclorbo Priest / Basil Cleric), but the donor is still
        # what separates the stat lines, so this stays the guard.
        self.assertEqual(bc.STAT_DONOR['sclorbo'], 'CHARACTER_MOULDER')
        self.assertEqual(bc.STAT_DONOR['basil'], 'CHARACTER_NATASHA')
        self.assertEqual(bc.STAT_DONOR['sahnar'], 'CHARACTER_JOSHUA')
        for uid in ('basil', 'sahnar'):   # no bespoke base/growth split for either
            self.assertEqual(bc.BASE_DONOR[uid], bc.STAT_DONOR[uid])
            self.assertEqual(bc.GROWTH_DONOR[uid], bc.STAT_DONOR[uid])

    def test_both_are_on_map_talk_recruits_of_ch05_with_opposite_factions(self):
        recruits = {r[0]: r for r in bc.on_map_talk_recruits(self.CAMPAIGN, self.CH05)}
        self.assertEqual(set(recruits), {'basil', 'sahnar'},
                         'ch05 recruits exactly Basil and Sahnar on the map')
        self.assertEqual(recruits['basil'][2], 'CLASS_CLERIC')
        self.assertEqual(recruits['sahnar'][2], 'CLASS_MYRMIDON')
        load = lambda uid: bc.load_unit(self.CAMPAIGN, uid)
        self.assertEqual(bc.recruit_initial_faction(load('basil')), 'GREEN')
        self.assertEqual(bc.recruit_initial_faction(load('sahnar')), 'RED')

    def test_basil_is_a_cleric_because_priest_promotes_into_the_wrong_weapon_type(self):
        """The whole reason for the class (Nicolas, 2026-08-08). See decisions.md.

        Priest's `ClassData.promotion` is CLASS_SAGE -- an ANIMA mage -- while basil.yaml's
        `battle_anim.spell_palette_tint` declares STAFF + LIGHT, i.e. Bishop. Cleric's default
        is CLASS_BISHOP_F, which IS light, so the class table points him at the class his own
        art already assumes. Pinned against the decomp so the two cannot drift apart again.
        """
        table = bc._vanilla_class_table()
        self.assertEqual(table['CLASS_PRIEST']['promotion'], 'CLASS_SAGE',
                         'Priest still defaults into anima -- the reason Basil left it')
        self.assertEqual(table['CLASS_CLERIC']['promotion'], 'CLASS_BISHOP_F')
        # ...and the YAML's authored branch is the decomp's branch, not a wish.
        display = {'CLASS_BISHOP_F': 'Bishop', 'CLASS_VALKYRIE': 'Valkyrie'}
        branches = bc._promotion_branches()['CLASS_CLERIC']
        promo = bc.load_unit(self.CAMPAIGN, 'basil')['promotion']
        self.assertEqual(sorted(promo['branch']), sorted(display[c] for c in branches))
        self.assertEqual(promo['default'], 'Bishop')

    def test_basil_bases_are_vanilla_cleric_class_data_verbatim(self):
        # basil.yaml claims its stat block is class data "verbatim"; that claim is only worth
        # anything if something checks it. CON is load-bearing beyond flavour: CanUnitRescue
        # is `GetUnitAid(actor) >= UNIT_CON(target)` (bmunit.c), so Cleric's CON 4 is what lets
        # more of the party ferry the ch05 escort than Priest's CON 5 would.
        bases = bc.class_base_stats('CLASS_CLERIC',
                                    bc.vanilla_decomp_text('src/data_classes.c'))
        fe = bc.load_unit(self.CAMPAIGN, 'basil')['fe_stats']
        for yaml_key, field in (('HP', 'baseHP'), ('MAG', 'basePow'), ('SKL', 'baseSkl'),
                                ('SPD', 'baseSpd'), ('DEF', 'baseDef'), ('RES', 'baseRes'),
                                ('CON', 'baseCon'), ('MOV', 'baseMov')):
            self.assertEqual(fe[yaml_key], bases[field],
                             'basil.yaml %s drifted from CLASS_CLERIC.%s' % (yaml_key, field))
        self.assertEqual(fe['CON'], 4, 'the escort-rescue margin is CON 4, not Priest CON 5')

    def test_basil_declares_female_so_the_artur_slot_bit_is_rewritten(self):
        # Gender rides YAML, not the slot -- _set_gender rewrites .attributes on whatever
        # character slot the unit wears, explicitly clearing what leaks from the vanilla
        # entry. So a female Cleric on the male Artur slot needs no slot change. (CA_FEMALE
        # is inert on a foot unit anyway: both readers, GetUnitAid and koido.c, gate on
        # CA_MOUNTEDAID first -- it matters only if he ever promotes to mounted Valkyrie.)
        self.assertEqual(bc.load_unit(self.CAMPAIGN, 'basil').get('gender'), 'female')
        self.assertIn('.attributes = CA_FEMALE',
                      bc._set_gender('{\n    .number = 1,\n}', True))
        self.assertNotIn('CA_FEMALE',
                         bc._set_gender('{\n    .attributes = CA_FEMALE,\n}', False))

    def test_neither_rides_the_ch05_prep_roster(self):
        # They join DURING ch05, so cast_available_at must not seat them in its deploy cap
        # (that is what the roster/cap parity is measured against) -- but ch06 must have them.
        for n, expected in ((self.CH05, False), (self.CH05 + 1, True)):
            seated = {uid for uid, *_ in bc._classed_cast(self.CAMPAIGN, available_at=n)[0]}
            self.assertEqual({'basil', 'sahnar'} <= seated, expected,
                             'wrong prep availability at chapter %d' % n)

    def test_the_gated_recruiter_is_basil_only(self):
        # Sahnar's recruiter is authored data (her `parley.by`), not a roster query -- she does
        # not weigh the argument, she recognises Basil (lore/sahnar.md). Same helper ch04's
        # Marty->Lupin parley uses; the chapter picks parley_recruiters over talk_recruiters.
        sahnar = next(e for e in bc._load_chapter_yaml(self.CAMPAIGN, bc.CH05_CHAPTER_YAML)
                      ['enemy_units'] if e['id'] == 'sahnar')
        self.assertEqual(bc.parley_recruiters(sahnar), ['CHARACTER_ARTUR'])

    def test_basils_green_tile_costs_no_deployment_and_can_reach_sahnar(self):
        # The three silent ways a green placement goes wrong (assert_green_recruit_placement).
        # Worth pinning the tile itself: vanilla's Natasha is BLUE and stands on what is now one
        # of our nine deploy slots, so copying the twin 1:1 here -- which is this chapter's
        # standing habit -- would have quietly cost the player a deployment.
        chap = bc._load_chapter_yaml(self.CAMPAIGN, bc.CH05_CHAPTER_YAML)
        slots = [tuple(s) for s in chap['deployment']['deploy_slots']]
        self.assertNotIn(bc.CH05_BASIL_GREEN_POS, slots)
        maps = os.path.join(bc.REPO, 'campaigns', self.CAMPAIGN, 'maps')
        bc.assert_green_recruit_placement(          # sys.exits on any of the three
            chap, maps, bc.CH05_LAYOUT[1], bc.CH05_BASIL_GREEN_POS,
            bc.CH05_BASIL_MOV_TABLE, 'Basil',
            must_reach=tuple(next(e for e in chap['enemy_units']
                                  if e['id'] == 'sahnar')['positions'][0]))

    def test_the_talk_script_flips_sahnar_and_carries_no_pack_conversion(self):
        # ch04 splices a pre_script (the wolf pack's conversion sweep) into the same flow;
        # ch05 has no group to bring over, so the script must be the bare talk -> CUSA.
        script = bc.talk_recruit_script(bc.CH05_SAHNAR_TALK_MSG, 'CHARACTER_MARISA')
        self.assertIn('TEXTSHOW(0x%X)' % bc.CH05_SAHNAR_TALK_MSG, script)
        self.assertIn('CUSA(CHARACTER_MARISA)', script)
        self.assertNotIn('CUSN', script)
        self.assertLess(script.index('TEXTSHOW'), script.index('CUSA'))   # line, then the flip

    def test_each_carries_a_death_quote(self):
        # inject_pc_death_quotes hard-exits without one (#6), so a slot with no quote is a
        # build break, not a missing nicety.
        for uid in ('basil', 'sahnar'):
            self.assertTrue((bc.load_unit(self.CAMPAIGN, uid).get('death_quote') or '').strip(),
                            '%s.yaml needs a death_quote' % uid)


class HostedChapterEnumeration(unittest.TestCase):
    """Which chapters are hosted must be DISCOVERED, not listed by hand.

    HostChapterEventGroup below is the guard written after the ch04 disaster, and it
    iterated a hand-written tuple of (HOST_INDEX, EVENT_GROUP) pairs. A hand-written
    list does not extend: ch05 would have been the first chapter NOT covered by the very
    test written to prevent that class of failure -- and ch05 hosts deeper into the slot
    divergence than ch04 did, since vanilla's slot index stops tracking chapter number
    at 4. Enumerating from the registry's constants closes that (#138).

    The registry itself moved to inject/hosts.py so a CI job without Pillow can lint it;
    its behaviour (collisions, missing groups, self-enrolment) is tested in tools/
    test_hosts.py. What is asserted HERE is the seam: build_campaign re-exports it, and
    every chapter this module injects is enrolled in it (#241).
    """

    def test_finds_every_currently_hosted_chapter(self):
        got = {c.name: c.host_index for c in bc.hosted_chapters()}
        self.assertEqual(got, {'prologue': bc.PROLOGUE_HOST_INDEX,
                               'ch01': bc.CH01_HOST_INDEX, 'ch02': bc.CH02_HOST_INDEX,
                               'ch03': bc.CH03_HOST_INDEX, 'ch04': bc.CH04_HOST_INDEX,
                               'ch05': bc.CH05_HOST_INDEX})

    def test_each_entry_carries_the_event_group_its_injector_fills(self):
        groups = {c.name: c.event_group for c in bc.hosted_chapters()}
        self.assertEqual(groups['ch04'], bc.CH04_EVENT_GROUP)
        self.assertEqual(groups['ch01'], bc.CH01_EVENT_GROUP)
        self.assertEqual(groups['prologue'], bc.PROLOGUE_EVENT_GROUP)

    def test_it_is_ordered_by_chapter_number(self):
        """Not by name -- 'ch01' sorts before 'prologue', and a name sort against a
        sorted() scan is a test that cannot fail."""
        self.assertEqual([c.name for c in bc.hosted_chapters()],
                         ['prologue', 'ch01', 'ch02', 'ch03', 'ch04', 'ch05'])

    def test_every_injector_in_this_module_is_enrolled(self):
        """Discovery only covers a chapter that spells its constants right. An
        inject_ch06 with a typo'd CH06_HOST_INDEX would be silently unhosted, and every
        guard built on the registry would pass with one chapter fewer."""
        self.assertEqual(bc.undeclared_injectors(), [])


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
        # Enumerated, NOT listed: a hand-written tuple would leave the next chapter
        # uncovered by the guard written for exactly its failure (#138).
        chapters = bc.hosted_chapters()
        self.assertTrue(chapters, 'no hosted chapters discovered')
        for chapter in chapters:
            host = self._retarget(chapter.host_index, chapter.event_group)
            self.assertEqual(host['mapEventDataId'], self._vanilla_index(chapter.event_group),
                             '%s: host slot %d must run %s'
                             % (chapter.name, chapter.host_index, chapter.event_group))

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


class SmsFreeListReclaimsDeadVanillaRows(unittest.TestCase):
    """We assign map sprites per CHARACTER where vanilla assigns them per CLASS, so every
    custom cast member needs its own wait row. That is the design. What was NOT the design
    is that CUSTOM_SMS_BASE only ever appended, leaving ~71 vanilla rows -- classes this
    campaign can never field, even after promotions -- sitting unused below it while we ran
    into the engine's 127 ceiling (#227, follow-up to #225).

    The dangerous part of reclaiming is that "unused" is not the same as "unreferenced":
    src/bmudisp.c renders ballista/trap sprites by LITERAL id, with no class involved.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_the_trap_rendered_rows_are_reserved(self):
        """RenderUnitSprites passes 0x5B/0x5C/0x5D (ballista traps, by trap->extra) and
        0x66 (trap type 0xD) as literal SMS ids. No class points at them, so a class-only
        reachability scan calls them free -- and reusing one renders a PC on any map with
        a ballista. This is the #218 failure shape, so it is pinned here."""
        for literal in (0x5B, 0x5C, 0x5D, 0x66):
            self.assertIn(literal, bc.SMS_RESERVED_IDS,
                          'SMS id 0x%02X is rendered by literal id in bmudisp.c' % literal)
        self.assertEqual(bc.SMS_RESERVED_IDS & bc.sms_free_rows(self.CAMPAIGN), set(),
                         'a reserved trap row was handed out as free')

    def test_the_reserved_literals_still_exist_in_the_decomp(self):
        """If a decomp bump changes which ids bmudisp renders by literal, the reservation
        list is stale and silently wrong -- so it is checked against HEAD, not trusted."""
        text = bc.vanilla_decomp_text('src/bmudisp.c')
        found = {int(m, 16) for m in
                 re.findall(r'(?:UseUnitSprite|GetInfo)\(0x([0-9A-Fa-f]+)\)', text)}
        self.assertEqual(found, bc.SMS_RESERVED_IDS,
                         'bmudisp.c literal SMS ids changed: %s vs reserved %s'
                         % (sorted(found), sorted(bc.SMS_RESERVED_IDS)))

    def test_a_class_we_field_is_never_free(self):
        """The whole safety property: no row reachable by a class this campaign can field
        may be reused."""
        free = bc.sms_free_rows(self.CAMPAIGN)
        reachable = bc.sms_reachable_rows(self.CAMPAIGN)
        self.assertEqual(free & reachable, set(),
                         'these rows are both free and reachable: %s'
                         % sorted(free & reachable))

    def test_both_promotion_branches_are_followed(self):
        """FE8 lets the player pick EITHER branch (gPromoJidLut[][2]). ClassData.promotion
        names only one, and following it alone missed Bishop, Ranger, Rogue, Summoner and
        Wyvern Knight (F) -- rows a PC can promote into (Nicolas, 2026-08-05)."""
        reachable = bc.sms_reachable_rows(self.CAMPAIGN)
        for second_branch in ('CLASS_SWORDMASTER', 'CLASS_BISHOP', 'CLASS_RANGER',
                              'CLASS_ROGUE', 'CLASS_SUMMONER'):
            self.assertTrue(bc.sms_rows_for_classes([second_branch]) <= reachable,
                            '%s is a reachable promotion branch; its row must not be free'
                            % second_branch)

    def test_the_whole_player_class_tree_is_reserved_not_just_todays_roster(self):
        """The roster is NOT final -- there are characters we have not written yet, so a
        row that looks dead today can belong to a future recruit's class. Reserve every
        class a player unit could ever hold or become, not merely the ones in YAML now."""
        reachable = bc.sms_reachable_rows(self.CAMPAIGN)
        # Classes no current PC holds, from branches of the tree we do not field.
        for unfielded in ('CLASS_WYVERN_RIDER', 'CLASS_TROUBADOUR', 'CLASS_MONK',
                          'CLASS_JOURNEYMAN', 'CLASS_PUPIL'):
            self.assertTrue(bc.sms_rows_for_classes([unfielded]) <= reachable,
                            '%s is player-holdable; reserve it against a future recruit'
                            % unfielded)

    def test_hand_reserved_classes_are_never_free(self):
        """Things no computation can infer: a bard/dancer recruit we have not written, and
        Frostmaiden's white dragon."""
        free = bc.sms_free_rows(self.CAMPAIGN)
        self.assertEqual(bc.sms_rows_for_classes(bc.SMS_RESERVED_CLASSES) & free, set())

    def test_a_declared_art_donor_is_never_free(self):
        """Donors are named by SHEET (art.map_sprite.base: 'Cyclops'), so the CLASS_ token
        scan misses them -- and naming a vanilla class as a donor is a fair signal we might
        field it too."""
        donors = bc._declared_donor_bases(self.CAMPAIGN)
        self.assertIn('Cyclops', donors, 'fixture check: a donor base is declared')
        free = bc.sms_free_rows(self.CAMPAIGN)
        self.assertEqual(bc.sms_rows_for_classes(
            {'CLASS_' + d.upper() for d in donors}) & free, set())

    def test_reclaiming_actually_buys_us_room(self):
        """The point of the exercise. Before #227 we had 2 ids of headroom, and the
        conservative policy still has to beat that by an order of magnitude."""
        self.assertGreater(len(bc.sms_free_rows(self.CAMPAIGN)), 12,
                           'conservative reclaim should still free well over a dozen rows')

    def test_the_free_list_is_computed_not_hardcoded(self):
        src = open(os.path.join(bc.REPO, 'tools', 'build_campaign.py'),
                   encoding='utf-8').read()
        body = src[src.index('def sms_free_rows('):]
        body = body[:body.index('\ndef ')]
        self.assertIn('sms_reachable_rows(', body,
                      'derive the free list from live reachability every build')
        self.assertNotRegex(body, r'\[\s*\d+\s*,\s*\d+\s*,\s*\d+',
                            'no hardcoded row list -- recompute it')

    def test_allocation_prefers_free_rows_then_appends(self):
        """Free rows first (they are the point), append as the fallback, and #225's
        ceiling guard still owns the append path."""
        free = sorted(bc.sms_free_rows(self.CAMPAIGN))
        got = bc.allocate_sms_ids(self.CAMPAIGN, len(free) + 3)
        self.assertEqual(got[:len(free)], free, 'free rows must be spent first, in order')
        for extra in got[len(free):]:
            self.assertGreaterEqual(extra, bc.CUSTOM_SMS_BASE,
                                    'overflow past the free list must append, not wrap')
        self.assertEqual(len(set(got)), len(got), 'allocation handed out a duplicate id')

    def test_allocation_never_exceeds_the_engine_ceiling(self):
        with self.assertRaises(SystemExit):
            bc.allocate_sms_ids(self.CAMPAIGN, 400)


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
        self.assertNotIn('_append_table_rows(UNIT_ICON_WAIT_C', src,
                         'wait rows are placed by _write_wait_row, never blind-appended')
        self.assertGreaterEqual(src.count('_write_wait_row('), 6,
                                'all five sprite passes + the definition')

    def _table(self, tmp, nrows):
        path = os.path.join(tmp, 'unit_icon_wait_data.c')
        rows = ''.join('\t{0, UNIT_ICON_SIZE_16x16, sheet_%d},\n' % i for i in range(nrows))
        with open(path, 'w', encoding='utf-8') as f:
            f.write('UnitIconWait unit_icon_wait_table[] = {\n%s};\n' % rows)
        return path

    def test_the_guard_rejects_a_row_past_the_mask(self):
        """The regression: overflowing must fail the BUILD, naming the id, rather than
        shipping a sprite that renders as a vanilla class."""
        tmp = tempfile.mkdtemp()
        try:
            path = self._table(tmp, 128)                     # ids 0..127: exactly full
            with mock.patch.object(bc, 'UNIT_ICON_WAIT_C', path):
                self.assertEqual(bc._wait_table_len(), 128)
                with self.assertRaises(SystemExit) as cm:
                    bc._write_wait_row(128, '\t{0, UNIT_ICON_SIZE_16x16, x}, // 128 basil')
            msg = str(cm.exception)
            self.assertIn('128', msg, 'name the overflowing id')
            self.assertIn('127', msg, 'state the ceiling')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_guard_allows_the_last_usable_id(self):
        """127 is usable -- an off-by-one here would cost us a sprite we own."""
        tmp = tempfile.mkdtemp()
        try:
            with mock.patch.object(bc, 'UNIT_ICON_WAIT_C', self._table(tmp, 127)):
                bc._write_wait_row(127, '\t{0, UNIT_ICON_SIZE_16x16, x}, // 127 sahnar')
                self.assertEqual(bc._wait_table_len(), 128)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_row_that_would_land_off_its_own_id_is_rejected(self):
        """The id/row desync #227 closes: an appended row must land at exactly the index
        its id names, or every later unit renders its neighbour's sheet."""
        tmp = tempfile.mkdtemp()
        try:
            with mock.patch.object(bc, 'UNIT_ICON_WAIT_C', self._table(tmp, 50)):
                with self.assertRaises(SystemExit) as cm:
                    bc._write_wait_row(60, '\t{0, UNIT_ICON_SIZE_16x16, x}, // 60 gap')
            self.assertIn('desync', str(cm.exception))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_a_reclaimed_row_is_replaced_in_place_not_appended(self):
        """Reclaiming means overwriting the dead vanilla row, leaving the table length
        unchanged -- if it appended instead, the id would name the wrong index."""
        tmp = tempfile.mkdtemp()
        try:
            with mock.patch.object(bc, 'UNIT_ICON_WAIT_C', self._table(tmp, 107)) as path:
                bc._write_wait_row(48, '\t{0, UNIT_ICON_SIZE_16x16, mine}, // 48 braulo')
                self.assertEqual(bc._wait_table_len(), 107, 'table length must not grow')
                with open(bc.UNIT_ICON_WAIT_C, encoding='utf-8') as f:
                    body = [ln for ln in f.read().splitlines() if ln.lstrip().startswith('{')]
                self.assertIn('braulo', body[48], 'row 48 must hold the new sprite')
                self.assertIn('sheet_47', body[47], 'its neighbours must be untouched')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_the_remaining_headroom_is_reported_while_it_is_still_cheap_to_act_on(self):
        """Running low is worth knowing BEFORE the build that runs out, so the allocator
        reports what is left and says so loudly when it is nearly gone."""
        src = open(os.path.join(bc.REPO, 'tools', 'build_campaign.py'),
                   encoding='utf-8').read()
        body = src[src.index('def sms_alloc_report('):]
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
    """A cast member on the field BEFORE it joins you (ch04's Lupin: red as the pack's
    leader, the finalized grey once Marty's parley brings him over; ch05's Basil green and
    Sahnar red until the tomb's two Talks).

    The failure this guards is the Trex bug's sibling: a charId-keyed cast-palette
    override is unconditional, so without the faction check Lupin renders in his bespoke
    grey while he is an ENEMY -- and FE reads grey as "already acted".
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'
    # Every cast member placed on a NON-BLUE side before its recruit talk. The value is the
    # cast index carrying the unit's BODY mass -- the one that has to land on the faction
    # ramp, or the unit does not change colour when it joins.
    ON_FIELD_BEFORE_JOINING = {'lupin': (2, 3), 'basil': (10,), 'sahnar': (1, 10)}

    def test_every_pre_recruit_unit_covers_each_index_it_uses(self):
        ms = os.path.join(bc.REPO, 'campaigns', self.CAMPAIGN, 'map_sprites')
        for uid, body in self.ON_FIELD_BEFORE_JOINING.items():
            roles = bc.pre_recruit_roles(self.CAMPAIGN, uid)
            self.assertIsNotNone(
                roles, '%s.yaml must declare art.map_sprite.pre_recruit_roles' % uid)
            for stem in (uid + '.png', uid + '_mu.png'):
                used = {v for v in Image.open(os.path.join(ms, stem)).getdata() if v}
                self.assertTrue(used <= set(roles), '%s uses undeclared cast indices %s'
                                % (stem, sorted(used - set(roles))))
            # The body must land on the faction ramp (7-10) -- that is what makes it read red.
            self.assertTrue({roles[i] for i in body} & set(range(7, 11)),
                            '%s: no body index on the faction ramp -- it would not change '
                            'colour by side' % uid)

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

    def test_BOTH_chapters_moose_pids_wear_the_wyrdeer_art(self):
        """The bug Nicolas caught off a playtest frame (2026-08-14).

        A pid is per-chapter and the sprite tables are keyed on pid, so ONE asset needs a row
        for EVERY pid that stages it. The registry named ch04's 0xce alone, ch05's moose (0xb9)
        matched nothing in `GetUnitSMSId`'s override scan, and the chapter's cornered elk
        rendered as CLASS_GWYLLGI's stock hound on the red enemy palette -- with the Wyrdeer
        sheets committed and ch05's YAML claiming they had shipped a fortnight earlier."""
        row = next(r for r in bc.SCRIPTED_NEUTRAL_SPRITES if r[0] == 'white-moose')
        _uid, char_ids, donor = row
        self.assertEqual('Gwyllgi', donor, 'the wait-row GEOMETRY donor, not the sprite')
        self.assertIn(bc.CH04_MOOSE_PID, char_ids)
        self.assertIn(bc.CH05_MOOSE_PID, char_ids)
        self.assertNotEqual(bc.CH04_MOOSE_PID, bc.CH05_MOOSE_PID, 'pids are per-chapter')

    def test_a_pid_that_wears_no_custom_art_fails_the_BUILD(self):
        """The per-PID half of the guard. `assert_declared_map_sprites_injected` asks whether an
        ASSET reached a sprite table -- the moose's had, under ch04's pid -- so it could not see
        a second chapter staging the same creature under a pid nothing dressed."""
        bc.assert_custom_art_pid_wired(bc.CH04_MOOSE_PID, 'white-moose', 'test')
        bc.assert_custom_art_pid_wired(bc.CH05_MOOSE_PID, 'white-moose', 'test')
        with self.assertRaises(SystemExit):
            bc.assert_custom_art_pid_wired('0x7f', 'white-moose', 'test')
        with self.assertRaises(SystemExit):      # asset in no row at all
            bc.assert_custom_art_pid_wired(bc.CH04_MOOSE_PID, 'not-a-creature', 'test')

    def test_both_chapters_actually_CALL_the_pid_guard(self):
        """A guard nothing calls is a comment. Both injectors run it on their own pid."""
        src = open(os.path.join(bc.REPO, 'tools', 'build_campaign.py'),
                   encoding='utf-8').read()
        for pid in ('CH04_MOOSE_PID', 'CH05_MOOSE_PID'):
            self.assertIn("assert_custom_art_pid_wired(%s, 'white-moose'" % pid, src)

    def test_one_asset_claims_one_sheet_pair_and_one_sms_slot(self):
        """Two pids are two override ROWS, not two sprites: the sheets and the SMS id are
        claimed once per asset, so a chapter reusing a creature costs table space and nothing
        else. Asserted on the injector's shape, since the tables only exist post-build."""
        src = open(os.path.join(bc.REPO, 'tools', 'build_campaign.py'),
                   encoding='utf-8').read()
        body = src[src.index('def _inject_scripted_neutral_sprites'):]
        body = body[:body.index('\ndef ', 1)]
        self.assertEqual(1, body.count('sms = claim_sms_id()'))
        self.assertLess(body.index('sms = claim_sms_id()'), body.index('for char_id in char_ids:'))

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


class DecompShebangsSurviveASubmoduleCheckout(unittest.TestCase):
    """The decomp ships Linux `#!/bin/python3` shebangs that do not exist on macOS, and ANY
    `git checkout` inside the submodule reverts the fix -- so the next build dies on
    `bad interpreter`, minutes in, from a Makefile rule that looks unrelated.

    tools/build.sh handled it, but CLAUDE.md documents plain `make`, which bypassed the
    wrapper -- so the failure kept recurring. Every build runs build_campaign, so the fix
    lives there now and this pins it.
    """

    def test_the_build_normalises_shebangs_before_injecting(self):
        src = open(os.path.join(bc.REPO, 'tools', 'build_campaign.py'),
                   encoding='utf-8').read()
        body = src[src.index('def main():'):]
        self.assertIn('normalise_decomp_shebangs(', body,
                      'every build must re-apply the fix, not just tools/build.sh')

    def test_it_rewrites_only_the_linux_shebang_and_is_idempotent(self):
        tmp = tempfile.mkdtemp()
        try:
            scripts = os.path.join(tmp, 'scripts')
            os.makedirs(scripts)
            broken = os.path.join(scripts, 'gen.py')
            fine = os.path.join(scripts, 'ok.py')
            other = os.path.join(scripts, 'nohash.py')
            with open(broken, 'w') as f:
                f.write('#!/bin/python3\nprint(1)\n')
            with open(fine, 'w') as f:
                f.write('#!/usr/bin/env python3\nprint(2)\n')
            with open(other, 'w') as f:
                f.write('print(3)\n')
            with mock.patch.object(bc, 'DECOMP', tmp), \
                    mock.patch.object(bc.platform, 'system', lambda: 'Darwin'):
                self.assertEqual(bc.normalise_decomp_shebangs(), 1)
                self.assertEqual(bc.normalise_decomp_shebangs(), 0, 'must be idempotent')
            self.assertTrue(open(broken).read().startswith('#!/usr/bin/env python3'))
            self.assertEqual(open(broken).read().splitlines()[1], 'print(1)',
                             'only the shebang line may change')
            self.assertTrue(open(fine).read().startswith('#!/usr/bin/env python3'))
            self.assertEqual(open(other).read(), 'print(3)\n')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_it_is_a_no_op_off_macos(self):
        with mock.patch.object(bc.platform, 'system', lambda: 'Linux'):
            self.assertEqual(bc.normalise_decomp_shebangs(), 0)


class CampaignOwnedUnitTables(unittest.TestCase):
    """Campaign rosters live in symbols NAMED for our chapter, not in whichever vanilla
    table the host slot's stripped cutscenes happened to leave unreferenced.

    Squatting cost us twice: the symbol name lied (ch04's moose rides a table our own
    source calls "dead Ch5 unit table"), and it rationed each chapter to the tables its
    host slot freed -- slot 5 freed seven, slot 6 frees three, and ch05 needs seven."""

    HEADER = ('extern CONST_DATA struct UnitDefinition UnitDef_Event_PrologueAlly[];\n'
              'extern CONST_DATA struct UnitDefinition UnitDef_088B61A8[];\n')
    ROWS = ['    {\n        .charIndex = 0xaa,\n    },']

    def test_definition_appends_a_terminated_table_under_our_prefix(self):
        out = bc.unit_table_definition('/* udefs */\n', 'MS_Ch05Line', self.ROWS, 'ch05 line')
        self.assertIn('CONST_DATA struct UnitDefinition MS_Ch05Line[] = {', out)
        self.assertIn('.charIndex = 0xaa,', out)
        self.assertIn('{ 0 },', out, 'the table must carry its terminator')
        self.assertTrue(out.startswith('/* udefs */\n'), 'existing content is preserved')

    def test_definition_leaves_the_vanilla_table_it_replaces_untouched(self):
        udefs = ('CONST_DATA struct UnitDefinition UnitDef_088B61A8[] = {\n'
                 '    { .charIndex = 0x80, },\n};\n')
        out = bc.unit_table_definition(udefs, 'MS_Ch05Line', self.ROWS, 'ch05 line')
        self.assertIn(udefs, out, 'appending must not disturb the vanilla roster')

    def test_extern_is_added_once_and_is_idempotent(self):
        once = bc.unit_table_extern(self.HEADER, 'MS_Ch05Line', 'ch05 line')
        twice = bc.unit_table_extern(once, 'MS_Ch05Line', 'ch05 line')
        self.assertEqual(once, twice)
        self.assertEqual(twice.count('MS_Ch05Line[];'), 1)

    def test_extern_declares_before_the_scripts_that_name_it(self):
        out = bc.unit_table_extern(self.HEADER, 'MS_Ch05Line', 'ch05 line')
        self.assertIn('extern CONST_DATA struct UnitDefinition MS_Ch05Line[];', out)
        # agbcc needs the decl in the extern block, not appended past the file's tail
        self.assertLess(out.index('MS_Ch05Line'), out.index('UnitDef_088B61A8'))

    def test_a_symbol_without_the_prefix_is_refused(self):
        # The prefix is the whole guarantee: an un-prefixed name is indistinguishable from
        # the vanilla tables, which is the confusion this retires.
        for bad in ('UnitDef_088B61A8', 'Ch05Line'):
            with self.assertRaises(SystemExit):
                bc.unit_table_definition('', bad, self.ROWS, 'ch05 line')
            with self.assertRaises(SystemExit):
                bc.unit_table_extern(self.HEADER, bad, 'ch05 line')


class ChapterLabelConstants(unittest.TestCase):
    """CHAPTER_L_* names and their VALUES diverge from slot 5 on, because FE8 inserted
    Ch5x at slot 5. Guessing the name from the slot number is right by accident for slots
    1-4 and wrong from 6 -- and wrong FAILS SILENTLY: a gDefeatTalkList entry keyed to the
    wrong .chapter never matches, so the boss dies, no flag is set, DefeatBoss never fires,
    and the chapter simply cannot be won."""

    HEADER = ('enum {\n'
              '    CHAPTER_L_PROLOGUE = 0x00,\n'
              '    CHAPTER_L_4 = 0x04, // Ch4: Ancient Horrors\n'
              '    CHAPTER_L_5X = 0x05, // Ch5x: Unbroken Heart\n'
              '    CHAPTER_L_5 = 0x06, // Ch5: The Empire\'s Reach\n'
              '    CHAPTER_L_6 = 0x07, // Ch6: Victims of War\n'
              '};\n')

    def test_slot_six_is_chapter_l_5_not_chapter_l_6(self):
        # ch05 hosts on slot 6. This single assertion is the whole point of the helper.
        self.assertEqual(bc.chapter_label_constant(6, self.HEADER), 'CHAPTER_L_5')

    def test_the_name_matches_the_number_only_below_the_ch5x_insert(self):
        self.assertEqual(bc.chapter_label_constant(4, self.HEADER), 'CHAPTER_L_4')
        self.assertEqual(bc.chapter_label_constant(5, self.HEADER), 'CHAPTER_L_5X')
        self.assertEqual(bc.chapter_label_constant(7, self.HEADER), 'CHAPTER_L_6')

    def test_an_unnamed_slot_is_refused_rather_than_guessed(self):
        with self.assertRaises(SystemExit):
            bc.chapter_label_constant(0x40, self.HEADER)

    def test_it_reads_the_real_decomp_header(self):
        # Guards the parse against a chapters.h reformat, and pins the live ch05 answer.
        self.assertEqual(bc.chapter_label_constant(bc.CH05_HOST_INDEX), 'CHAPTER_L_5')
        self.assertEqual(bc.chapter_label_constant(bc.CH03_HOST_INDEX), 'CHAPTER_L_4')


class EventGroupRosterPointer(unittest.TestCase):
    """Declaring our own roster table is half the job -- the ENGINE reads the roster through
    the ChapterEventGroup. A table nobody points at is inert, and the slot silently keeps
    deploying the vanilla one: ch05 shipped one build that put the party on vanilla Ch6's
    start tiles, four of them inside walls, while PREP ran and the load-test PASSed."""

    INFO = ('CONST_DATA EventListScr EventListScr_Ch6_Turn[] = {\n    END_MAIN\n};\n\n'
            'CONST_DATA struct ChapterEventGroup Ch6Events = {\n'
            '    .turnBasedEvents = EventListScr_Ch6_Turn,\n'
            '    .playerUnitsInNormal = UnitDef_Event_Ch6Ally,\n'
            '    .playerUnitsInHard   = UnitDef_Event_Ch6Ally,\n'
            '};\n')

    def test_it_repoints_the_named_field(self):
        out = bc.point_event_group_at(self.INFO, 'Ch6Events', 'playerUnitsInNormal',
                                      'MS_Ch05DeployCap')
        self.assertIn('.playerUnitsInNormal = MS_Ch05DeployCap,', out)
        # the OTHER difficulty is a separate decision and must not move on its own
        self.assertIn('.playerUnitsInHard   = UnitDef_Event_Ch6Ally,', out)

    def test_it_does_not_touch_fields_outside_the_group(self):
        out = bc.point_event_group_at(self.INFO, 'Ch6Events', 'playerUnitsInNormal',
                                      'MS_Ch05DeployCap')
        self.assertIn('EventListScr EventListScr_Ch6_Turn[] = {', out)
        self.assertIn('.turnBasedEvents = EventListScr_Ch6_Turn,', out)

    def test_a_missing_field_is_refused(self):
        with self.assertRaises(SystemExit):
            bc.point_event_group_at(self.INFO, 'Ch6Events', 'nosuchField', 'MS_Ch05DeployCap')

    def test_the_live_ch05_group_deploys_our_table(self):
        """The regression itself. Runs against the injected tree, so it only means anything
        after a build -- skipped on a clean checkout rather than passing vacuously."""
        if not os.path.exists(bc.CH05_EVENTINFO_H):
            self.skipTest('decomp not present')
        with open(bc.CH05_EVENTINFO_H, encoding='utf-8') as f:
            if 'struct ChapterEventGroup %s' % bc.CH05_EVENT_GROUP not in f.read():
                self.skipTest('host slot not injected in this tree')
        bc.assert_event_group_roster(bc.CH05_EVENTINFO_H, bc.CH05_EVENT_GROUP,
                                     bc.CH05_ALLY_TABLE)


class VillageGiftsInheritVanilla(unittest.TestCase):
    """On a retile, WHICH gift sits on WHICH tile is vanilla's decision.

    Worth a gate because the failure is invisible to every other one: swap two gifts and the
    item set, the economy total and the parity verdict are all unchanged, while the chapter's
    risk/reward inverts. ch05 shipped with booster-def and torch swapped -- the richest gift
    ended up on the safest site, and the cheapest on the one the turn-2 raiders reach first."""

    INFO = ('CONST_DATA EventListScr EventListScr_Ch5_Location[] = {\n'
            '    Armory(ShopList_Event_Ch5Armory, 2, 1)\n'
            '    Village(EVFLAG_TMP(8),  EventScr_A, 12, 10)\n'
            '    Village(EVFLAG_TMP(9),  EventScr_B, 12, 19)\n'
            '    END_MAIN\n};\n')
    SCRIPT = ('CONST_DATA EventListScr EventScr_A[] = {\n'
              '    SVAL(EVT_SLOT_3, 0xe)\n    GIVEITEMTO(CHAR_EVT_ACTIVE_UNIT)\n};\n'
              'CONST_DATA EventListScr EventScr_B[] = {\n'
              '    SVAL(EVT_SLOT_3, 0x60)\n    GIVEITEMTO(CHAR_EVT_ACTIVE_UNIT)\n};\n')
    ITEMS = {'armorslayer': 'ITEM_SWORD_ARMORSLAYER', 'booster-def': 'ITEM_BOOSTER_DEF',
             'torch': 'ITEM_TORCH'}

    def _gifts(self):
        return bc.vanilla_village_gifts('Ch5Map', self.INFO, self.SCRIPT)

    def _chap(self, tile, gift):
        return {'map': {'vanilla_layout': 'Ch5Map'},
                'villages': [{'id': 'v', 'tile': list(tile),
                              'visit_reward': [{'id': gift, 'amount': 1}]}]}

    def test_it_reads_the_gift_out_of_the_village_script(self):
        # the tile is in the Location list, the ITEM is a raw id inside the script it names --
        # which is why it is easy to have the data and never actually look at it
        self.assertEqual(self._gifts(),
                         {(12, 10): 'ITEM_SWORD_ARMORSLAYER', (12, 19): 'ITEM_BOOSTER_DEF'})

    def test_a_matching_gift_passes(self):
        bc.assert_village_gifts_match_vanilla(
            self._chap((12, 19), 'booster-def'), self.ITEMS, self._gifts())

    def test_a_swapped_gift_is_refused(self):
        with self.assertRaises(SystemExit) as caught:
            bc.assert_village_gifts_match_vanilla(
                self._chap((12, 19), 'torch'), self.ITEMS, self._gifts())
        self.assertIn('vanilla_gift_divergence', str(caught.exception),
                      'the error must name the escape hatch')

    def test_a_declared_divergence_is_allowed(self):
        chap = self._chap((12, 19), 'torch')
        chap['villages'][0]['vanilla_gift_divergence'] = 'the tomb has no armoury tier yet'
        bc.assert_village_gifts_match_vanilla(chap, self.ITEMS, self._gifts())

    def test_a_site_vanilla_does_not_have_is_left_alone(self):
        # a village we ADDED, not moved -- nothing to inherit
        bc.assert_village_gifts_match_vanilla(
            self._chap((3, 3), 'torch'), self.ITEMS, self._gifts())

    def test_a_from_scratch_canvas_is_skipped(self):
        chap = self._chap((12, 19), 'torch')
        chap['map'] = {}                      # no vanilla_layout -> no vanilla to inherit
        bc.assert_village_gifts_match_vanilla(chap, self.ITEMS, self._gifts())

    def test_an_unmapped_reward_id_is_refused(self):
        with self.assertRaises(SystemExit):
            bc.assert_village_gifts_match_vanilla(
                self._chap((12, 19), 'nonesuch'), self.ITEMS, self._gifts())

    def test_the_live_ch05_villages_inherit_vanilla(self):
        chap = bc._load_chapter_yaml('rime-of-the-frostmaiden', bc.CH05_CHAPTER_YAML)
        bc.assert_village_gifts_match_vanilla(chap, bc.CH05_ITEM_IDS)


class CampaignOwnedEventScripts(unittest.TestCase):
    """The script twin of campaign-owned unit tables. A host slot frees only the scripts its
    stripped cutscenes stop referencing -- slot 6 leaves five, and ch05 needs three waves plus
    one per village. Naming our own removes the budget, and MS_Ch05VisitSouth says what it runs
    where EventScr_089F2AE4 says nothing."""

    HEADER = 'extern CONST_DATA EventListScr EventScr_9EEA58[];\n'

    def test_extern_is_added_once_and_is_idempotent(self):
        once = bc.event_script_extern(self.HEADER, 'MS_Ch05VisitSouth', 'south reliquary')
        twice = bc.event_script_extern(once, 'MS_Ch05VisitSouth', 'south reliquary')
        self.assertEqual(once, twice)
        self.assertEqual(twice.count('MS_Ch05VisitSouth[];'), 1)

    def test_an_unprefixed_symbol_is_refused(self):
        with self.assertRaises(SystemExit):
            bc.event_script_extern(self.HEADER, 'EventScr_089F2AE4', 'squatting')

    def test_a_declared_but_undefined_script_fails_the_build(self):
        """declare_event_script APPENDS, while the injector rewrites the same file wholesale from
        a copy read earlier -- so declaring before the bulk write silently discards every script.
        It happened, and the only symptom was a link error naming the reference, not the loss."""
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, 'ch6-eventscript.h')
            with open(path, 'w') as f:
                f.write('CONST_DATA EventListScr MS_Ch05VisitNorth[] = {\n    ENDA\n};\n')
            bc.assert_event_scripts_defined(path, ['MS_Ch05VisitNorth'])   # present -> quiet
            with self.assertRaises(SystemExit) as caught:
                bc.assert_event_scripts_defined(
                    path, ['MS_Ch05VisitNorth', 'MS_Ch05VisitSouth'])
            self.assertIn('MS_Ch05VisitSouth', str(caught.exception))
            self.assertIn('AFTER', str(caught.exception), 'the error must name the ordering')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class LocationEventsAreBuiltFromTheYaml(unittest.TestCase):
    """An empty Location list makes every reward on the map unobtainable while the map still
    draws it -- ch04's unreachable Iron Axe, and ch05's four villages plus an armory and vendor."""

    VILLAGES = [{'id': 'a', 'tile': [12, 19], 'visit_reward': [{'id': 'booster-def'}]},
                {'id': 'b', 'tile': [5, 1]}]
    SLOTS = {'a': 'MS_Ch05VisitSouth', 'b': 'MS_Ch05VisitNorth'}

    def test_each_village_rides_its_own_script_at_its_own_tile(self):
        body = bc.location_events(self.VILLAGES, self.SLOTS)
        self.assertIn('Village(0, MS_Ch05VisitSouth, 12, 19)', body)
        self.assertIn('Village(0, MS_Ch05VisitNorth, 5, 1)', body)
        self.assertTrue(body.rstrip().endswith('END_MAIN\n}'))

    def test_a_village_with_no_reward_says_so_rather_than_naming_an_item(self):
        body = bc.location_events(self.VILLAGES, self.SLOTS)
        self.assertIn('the line is the reward', body)

    def test_a_village_given_an_event_id_carries_it_into_the_macro(self):
        """The event id is the whole village-raid race (#25). `Village(eid, ..)` expands to the
        VILL *and* a LOCA on the tile above -- the destruction hook AiPillageAction fires -- and
        SearchAvailableEvent skips an entry whose flag is SET. So the flag is what records a
        visit, what disarms the raider, and what the save-all payout later reads with
        CHECK_EVENTID. Flag 0 is EVFLAG_ALWAYS_FALSE: CheckChapterFlag(0) returns 0 forever, so
        a 0 village is never visited, never safe, and can never be counted."""
        body = bc.location_events(self.VILLAGES, self.SLOTS,
                                  flags={'a': 'EVFLAG_TMP(9)', 'b': 'EVFLAG_TMP(10)'})
        self.assertIn('Village(EVFLAG_TMP(9), MS_Ch05VisitSouth, 12, 19)', body)
        self.assertIn('Village(EVFLAG_TMP(10), MS_Ch05VisitNorth, 5, 1)', body)

    def test_shops_need_no_script_and_no_text(self):
        body = bc.location_events([], {}, (('Armory', 'ShopList_Event_Ch5Armory', 2, 1),
                                          ('Vendor', 'ShopList_Event_Ch5Vendor', 6, 10)))
        self.assertIn('Armory(ShopList_Event_Ch5Armory, 2, 1)', body)
        self.assertIn('Vendor(ShopList_Event_Ch5Vendor, 6, 10)', body)

    def test_village_reward_item_uses_the_chapters_own_map(self):
        """It used to close over CH04_ITEM_IDS, which made a shared helper silently ch04-only:
        ch05's stat boosters are not in that dict, so the first reuser would die on a KeyError."""
        village = {'id': 'a', 'visit_reward': [{'id': 'booster-def'}]}
        self.assertEqual(bc.village_reward_item(village, {'booster-def': 'ITEM_BOOSTER_DEF'}),
                         'ITEM_BOOSTER_DEF')
        self.assertIsNone(bc.village_reward_item({'id': 'b'}, {}))
