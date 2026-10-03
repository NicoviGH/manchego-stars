#!/usr/bin/env python3
"""Tests for tools/inject/cast.py.

Run:  python3 tools/test_inject_cast.py
"""
import os
import re
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject.namespace import injector_constants
from inject.namespace import stubbed
import build_campaign as bc
import inject.cast
import inject.chapter_ids
import inject.chapters.ch02
import inject.chapters.ch03
import inject.chapters.ch05
import inject.death_quotes
import inject.decomp
import inject.hosting
import inject.messages
import inject.names
import inject.portraits
import inject.raw_pids
import inject.recruit
import inject.sms
import inject.stats
import inject.text
import inject.test_chapter
import inject.units
import inject.villages
import portrait_tool
from inject import source as injector  # the injector's source, every file of it (#389)


class TrexRecruitCast(unittest.TestCase):
    """Trex (ch03 recruit, #23) is a full classed cast member: a Thief riding the vanilla
    Rennac slot, donoring from Colm, deployable so his vendored custom sprite renders."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_trex_rides_the_rennac_slot(self):
        self.assertEqual(inject.cast.PORTRAIT_MAP['trex'], 'Rennac')

    def test_trex_donors_from_colm_for_stats_bases_and_growths(self):
        self.assertEqual(inject.stats.STAT_DONOR['trex'], 'CHARACTER_COLM')
        self.assertEqual(inject.stats.BASE_DONOR['trex'], 'CHARACTER_COLM')
        self.assertEqual(inject.stats.GROWTH_DONOR['trex'], 'CHARACTER_COLM')

    def test_trex_resolves_as_a_thief_in_the_classed_cast(self):
        cast = {uid: (slot, cls) for uid, slot, cls, _sms in inject.cast.classed_cast(self.CAMPAIGN)}
        self.assertEqual(cast['trex'], ('Rennac', 'CLASS_THIEF'))

    def test_every_classed_cast_member_has_a_test_loadout(self):
        # inject_test_chapter walks the WHOLE PORTRAIT_MAP and sys.exits on the first class
        # with no CLASS_LOADOUT row -- so a cast member's class change can break the art bench
        # (recordcast/recordanim) without touching a single chapter. Caught exactly that when
        # Basil moved Priest -> Cleric (2026-08-08): CLASS_CLERIC had no row, and ch05's own
        # guard could not see it because Basil is recruited IN ch05 and so is not on its field
        # roster. Assert the invariant, not the one class that happened to be missing.
        allcast, _ = inject.cast._classed_cast(self.CAMPAIGN)   # available_at=None -> everyone
        missing = sorted({ce for _uid, _slot, ce, *_ in allcast if ce not in inject.cast.CLASS_LOADOUT})
        self.assertEqual(missing, [], 'classed cast members with no CLASS_LOADOUT row')

    def test_thief_loadout_and_testch_covers_the_whole_cast(self):
        # inject_test_chapter needs a Thief loadout + one spawn tile per classed cast member
        # (13 now: 8 founding + Baxby + Trex + Lupin + ch05's Basil and Sahnar); both would
        # sys.exit otherwise.
        self.assertIn('CLASS_THIEF', inject.cast.CLASS_LOADOUT)
        allcast, _ = inject.cast._classed_cast(self.CAMPAIGN)   # available_at=None -> everyone
        self.assertEqual(len(allcast), 13)
        self.assertGreaterEqual(len(inject.test_chapter.TEST_SPAWN_POSITIONS), len(allcast))
        # ch03's blue field roster = cast_available_at(3); its PREP deploy tiles must cover it.
        field, _ = inject.cast._classed_cast(self.CAMPAIGN, available_at=3)
        chap = inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH03_CHAPTER_YAML)
        self.assertGreaterEqual(len(chap['deployment']['deploy_slots']), len(field))

    def test_trex_has_a_death_quote_and_a_dead_slot2_msg_id(self):
        self.assertIn('trex', inject.death_quotes.PC_DEATH_QUOTE_MSGS)
        unit = inject.cast.load_unit(self.CAMPAIGN, 'trex')
        self.assertTrue(unit.get('death_quote'))

    def test_every_classed_cast_member_has_a_death_quote(self):
        # #6 requires a msg id + a quote line per deployable cast member; inject_pc_death_quotes
        # sys.exits otherwise (a build break). This guards every recruit, incl. future ch05 ones.
        for uid, _slot, _cls, _sms in inject.cast.classed_cast(self.CAMPAIGN):
            self.assertIn(uid, inject.death_quotes.PC_DEATH_QUOTE_MSGS, '%s needs a death-quote msg id' % uid)
            self.assertTrue(inject.cast.load_unit(self.CAMPAIGN, uid).get('death_quote'),
                            '%s needs a death_quote line' % uid)


class RecruitAvailability(unittest.TestCase):
    """The reusable, data-driven recruit model (#23): a recruit is a classed cast member
    with a `recruit.chapter`; cast_available_at(N) puts it on the field from the chapter
    AFTER it is recruited. Baxby (ch01 cutscene recruit) and Trex (ch03 talk recruit)."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_recruit_chapter_numbers(self):
        for uid, want in (('baxby', 1), ('trex', 3)):
            u = inject.cast.load_unit(self.CAMPAIGN, uid)
            self.assertEqual(inject.hosting.recruit_chapter_number(self.CAMPAIGN, u), want)

    def test_founding_pc_has_no_recruit_chapter(self):
        self.assertIsNone(inject.hosting.recruit_chapter_number(
            self.CAMPAIGN, inject.cast.load_unit(self.CAMPAIGN, 'braulo')))

    def test_availability_climbs_with_the_chapters(self):
        def ids(n):
            return {u for u, *_ in inject.cast._classed_cast(self.CAMPAIGN, available_at=n)[0]}
        ch1, ch2, ch3, ch4 = ids(1), ids(2), ids(3), ids(4)
        self.assertNotIn('baxby', ch1)              # recruited IN ch01 -> not on the ch01 field
        self.assertIn('baxby', ch2)                 # on the field from ch02 (prep)
        self.assertEqual(len(ch1), 8)               # the founding party
        self.assertNotIn('trex', ch3)               # talk-recruited IN ch03 -> placed green, not prep
        self.assertIn('trex', ch4)                  # on the prep roster from ch04
        self.assertIn('baxby', ch3)

    def test_baxby_is_a_cavalier_on_the_forde_slot_donoring_franz(self):
        self.assertEqual(inject.cast.PORTRAIT_MAP['baxby'], 'Forde')
        self.assertEqual(inject.stats.STAT_DONOR['baxby'], 'CHARACTER_FRANZ')
        self.assertNotIn('baxby', inject.cast.GUEST_PORTRAIT_MAP)   # promoted from cutscene-face to real unit
        cast = {u: (s, c) for u, s, c, _ in inject.cast.classed_cast(self.CAMPAIGN)}
        self.assertEqual(cast['baxby'], ('Forde', 'CLASS_CAVALIER'))

    def test_baxby_has_a_death_quote_and_a_dead_slot2_msg_id(self):
        self.assertIn('baxby', inject.death_quotes.PC_DEATH_QUOTE_MSGS)
        self.assertTrue(inject.cast.load_unit(self.CAMPAIGN, 'baxby').get('death_quote'))

    def test_offmap_recruit_joins_the_chapter_after_recruitment(self):
        """The availability filter only SIZES the deploy cap; an off-map cutscene recruit
        (Baxby) needs an explicit between-chapter join-LOAD to enter the saved party. It
        fires the chapter AFTER recruitment, exactly once (#23 recruit-persist)."""
        def ids(n):
            return {u for u, *_ in inject.chapters.ch02.offmap_join_recruits(self.CAMPAIGN, n)}
        self.assertEqual(ids(1), set())        # nobody is recruited before ch01
        self.assertEqual(ids(2), {'baxby'})    # ch01 cutscene recruit joins the party at ch02
        self.assertEqual(ids(3), set())        # already joined at ch02 -> no re-LOAD (no duplicate)

    def test_offmap_join_excludes_on_map_talk_recruits(self):
        """Trex is a Colm-style on-map talk recruit (recruit.via = story): he self-joins via
        CUSA on the map and persists naturally, so he never needs an off-map join-LOAD."""
        for n in range(1, 6):
            self.assertNotIn('trex', {u for u, *_ in inject.chapters.ch02.offmap_join_recruits(self.CAMPAIGN, n)})

    def test_offmap_join_recruit_carries_slot_and_class(self):
        """The join-LOAD row needs the unit's slot + real/deploy class + level, like the cap."""
        rows = inject.chapters.ch02.offmap_join_recruits(self.CAMPAIGN, 2)
        baxby = next(r for r in rows if r[0] == 'baxby')
        uid, slot, class_enum, deploy_class, level = baxby
        self.assertEqual(slot, 'Forde')
        self.assertEqual(class_enum, 'CLASS_CAVALIER')
        self.assertIn(class_enum, inject.cast.CLASS_LOADOUT)   # the join-LOAD arms him from CLASS_LOADOUT


class TalkRecruitWiring(unittest.TestCase):
    """Trex's Colm-style talk recruit (#23 item 2): placed GREEN, recruited when ANY core
    party member Talks to him (one CHAR entry per candidate -> one shared script -> CUSA).
    These pin the pure data + string builders inject_ch03 consumes."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_char_symbol_from_slot(self):
        self.assertEqual(inject.cast.char_symbol('Rennac'), 'CHARACTER_RENNAC')
        self.assertEqual(inject.cast.char_symbol('Eirika'), 'CHARACTER_EIRIKA')

    def test_trex_is_ch03_on_map_talk_recruit_on_the_rennac_slot(self):
        """on_map_talk_recruits(N) = the recruits who join mid-map via Talk in chapter N."""
        rows = inject.recruit.on_map_talk_recruits(self.CAMPAIGN, 3)
        self.assertEqual([r[0] for r in rows], ['trex'])
        uid, slot, class_enum, deploy_class, level = rows[0]
        self.assertEqual(slot, 'Rennac')                 # Trex's on-map CHARACTER symbol slot
        self.assertEqual(class_enum, 'CLASS_THIEF')

    def test_no_talk_recruit_in_a_chapter_without_one(self):
        """ch02 has no on-map talk recruit (Baxby is an off-map cutscene recruit)."""
        self.assertEqual(inject.recruit.on_map_talk_recruits(self.CAMPAIGN, 2), [])

    def test_recruiters_are_the_ch03_field_roster_minus_trex(self):
        """Talker = ANY core party member -> the ch03 blue field roster (cast_available_at(3)).
        Trex himself is never a recruiter (he is the green target, not on the prep roster)."""
        recruiters = inject.chapters.ch03.talk_recruiters(self.CAMPAIGN, 3)
        field = {inject.cast.char_symbol(slot) for _, slot, *_ in inject.cast._classed_cast(self.CAMPAIGN, available_at=3)[0]}
        self.assertEqual(set(recruiters), field)
        self.assertNotIn('CHARACTER_RENNAC', recruiters)   # the target isn't a recruiter
        self.assertGreaterEqual(len(recruiters), 8)        # the founding party at least

    def test_char_entries_one_per_recruiter_sharing_flag_and_script(self):
        """The talker-agnostic wiring: one CHAR(flag, script, recruiter, target) per candidate,
        all pointing at the SAME flag + script + target (so any one talk recruits + disables all)."""
        recruiters = ['CHARACTER_EIRIKA', 'CHARACTER_FRANZ', 'CHARACTER_GILLIAM']
        c = inject.recruit.talk_recruit_char_entries(recruiters, 'CHARACTER_RENNAC',
                                         'EVFLAG_TMP(9)', 'EventScr_TrexTalk')
        self.assertEqual(c.count('CHAR('), 3)
        for r in recruiters:
            self.assertIn('CHAR(EVFLAG_TMP(9), EventScr_TrexTalk, %s, CHARACTER_RENNAC)' % r, c)

    def test_recruit_script_flips_the_target_blue_with_cusa(self):
        """The shared script shows the talk line then CUSA(target) = EvtChangeFaction to BLUE."""
        s = inject.recruit.talk_recruit_script(0x9A5, 'CHARACTER_RENNAC')
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
        return inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH03_CHAPTER_YAML)

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
        field, _ = inject.cast._classed_cast(self.CAMPAIGN, available_at=3)
        self.assertEqual(self._chap()['deployment']['deploy_limit'], len(field))
        self.assertNotIn('trex', {u for u, *_ in field})

    def test_deploy_cap_entries_yields_one_row_per_slot(self):
        """_deploy_cap_entries (the shared ch01/ch02 builder) now succeeds for ch03: one
        never-LOADed ally row per deploy slot, tile coords from the YAML."""
        chap = self._chap()
        field, _ = inject.cast._classed_cast(self.CAMPAIGN, available_at=3)
        leader = 'CHARACTER_%s' % field[0][1].upper()
        rows = inject.units._deploy_cap_entries(chap, field, leader, 'ch03')
        self.assertEqual(len(rows), chap['deployment']['deploy_limit'])
        for (x, y) in chap['deployment']['deploy_slots']:
            self.assertTrue(any('.xPosition = %d,' % x in r and '.yPosition = %d,' % y in r
                                for r in rows))


class Ch05ReliquaryVisits(unittest.TestCase):
    """The four reward sites are a TOMB, so their speakers are the tomb's own risen dead (#25).

    Two things here can break silently and neither shows up in a build log: a resident's
    portrait slot colliding with a cast member's (dressing a slot is GLOBAL, so the collision
    would repaint someone else's face in another chapter), and the visit ids drifting out of
    ch05's claim (the #196 defect, where a beat displayed an id another chapter writes).
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH05_CHAPTER_YAML)

    def test_every_site_has_a_line_and_a_face(self):
        for village in self._chap()['villages']:
            self.assertTrue(village.get('visit_text'),
                            '%s has no line to show' % village['id'])
            self.assertIn(village['id'], inject.chapter_ids.CH05_VILLAGE_SLOTS)
            self.assertIn(village['id'], inject.chapter_ids.CH05_VISIT_FACES,
                          '%s would play faceless -- a message with no [LoadFace] renders '
                          'boxless' % village['id'])

    def test_the_residents_ride_collision_free_portrait_slots(self):
        """Overwriting a portrait slot's graphics is global, so 'free' has to mean free
        everywhere -- not merely absent from PORTRAIT_MAP."""
        slots = [slot for _, slot, _ in inject.chapter_ids.CH05_VISIT_FACES.values()]
        self.assertEqual(len(slots), len(set(slots)), 'two residents share one slot')
        taken = (set(inject.cast.PORTRAIT_MAP.values()) | set(inject.cast.GUEST_PORTRAIT_MAP.values())
                 | set(inject.chapter_ids.CH02_CHWINGA_PORTRAIT_SLOT.values()))
        self.assertFalse(set(slots) & taken,
                         'a resident is dressing a slot someone else already wears')
        # The villager mugs our other chapters SPEAK with, by FID -- ch02's fisher, ch03's
        # crier, ch04's Nimsy and logger. Repainting one of those would change a face in a
        # chapter that has nothing to do with the tomb.
        spoken_for = {inject.chapters.ch02.CH02_FISHER_FID, inject.chapters.ch03.CH03_CRIER_FID, inject.chapter_ids.CH04_NIMSY_FID,
                      '[FID_VillagerMan3]'}
        for _, _, fid in inject.chapter_ids.CH05_VILLAGE_SLOTS.values():
            self.assertNotIn(fid, spoken_for,
                             '%s is already another chapter\'s speaker' % fid)

    def test_every_dressed_slot_gets_its_geometry_normalized(self):
        """Dressing a slot and normalizing its mouth/eye window are two steps, and missing the
        second is SILENT -- green build, passing scenario, corrupted face. It shipped that way
        for the ch02 chwinga and for three of the four ch05 residents: the engine painted the
        blink/talk overlay at the vanilla character's mouth coords, smearing a block of skull
        over the eye sockets. Whatever the next dressed slot is, it has to land in this set.
        """
        normalized = set(inject.portraits.dressed_portrait_slots(self.CAMPAIGN))
        for vid, (_mug, slot, _rc) in inject.chapter_ids.CH05_VISIT_FACES.items():
            self.assertIn(slot, normalized, '%s dresses %s but never normalizes it' % (vid, slot))
        for slot in inject.chapter_ids.CH02_CHWINGA_PORTRAIT_SLOT.values():
            self.assertIn(slot, normalized, 'chwinga slot %s is dressed but not normalized' % slot)
        self.assertLessEqual(set(inject.cast.PORTRAIT_MAP.values()), normalized)

    def test_ch05_claims_the_ids_it_writes(self):
        """These sit OUTSIDE ch05's host block on purpose (see CH05_VILLAGE_SLOTS), which is
        exactly the shape of the #196 defect -- so the claim is what makes it legal."""
        claimed = set(inject.messages.HOSTED_CHAPTER_MESSAGE_IDS['ch05'])
        for vid, (_symbol, msg, _fid) in inject.chapter_ids.CH05_VILLAGE_SLOTS.items():
            self.assertIn(msg, claimed, '%s writes 0x%X but ch05 never claims it' % (vid, msg))
        inject.messages.assert_message_ids_unique()   # and nobody else claims them

    def test_the_authored_boxes_survive_as_a_presses(self):
        """One `visit_text` entry per BOX (ch04's lesson): the pacing IS the A-press breaks,
        and 25 boxes against vanilla Ch5's own 26 is the budget this pass was written to."""
        chap = self._chap()
        total = 0
        for village in chap['villages']:
            boxes = [line for _who, line in inject.villages.village_boxes(village)]
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
        vendor = os.path.join(inject.cast._bust_dir(self.CAMPAIGN), 'vendor')
        for vid, (mug, _slot, recolor) in sorted(inject.chapter_ids.CH05_VISIT_FACES.items()):
            path = os.path.join(vendor, mug)
            self.assertTrue(os.path.isfile(path), 'missing vendored mug for %s' % vid)
            bust = inject.cast._vendor_mug_to_bust(path, recolor)
            self.assertEqual('P', bust.mode)
            self.assertEqual((96, 80), bust.size)
            palette = bust.getpalette()[:48]
            self.assertEqual(list(inject.cast.PORTRAIT_TRANSPARENT_RGB), palette[:3],
                             '%s: index 0 must be the transparent key' % vid)
            self.assertLessEqual(len(set(bust.getdata())), 16)

    def test_the_two_shared_body_skeletons_are_told_apart(self):
        """reliquary-east and -south are the SAME mug with a different jaw, so without a
        recolor the player meets one man twice. Only the two true oranges may move: the third
        tone in that ramp is also the skull's shadow, and recolouring it turns his teeth green.
        """
        vendor = os.path.join(inject.cast._bust_dir(self.CAMPAIGN), 'vendor')
        east = inject.cast._vendor_mug_to_bust(
            os.path.join(vendor, inject.chapter_ids.CH05_VISIT_FACES['reliquary-east'][0]), None)
        mug, _slot, recolor = inject.chapter_ids.CH05_VISIT_FACES['reliquary-south']
        self.assertTrue(recolor, 'the south resident needs a recolor or he is the east one')
        south = inject.cast._vendor_mug_to_bust(os.path.join(vendor, mug), recolor)
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
        bust_dir = inject.cast._bust_dir(self.CAMPAIGN)
        source = os.path.join(bust_dir, 'vendor', inject.portraits.RAVISIN_VENDOR_MUG)
        derived = os.path.join(bust_dir, 'ravisin.png')
        self.assertTrue(os.path.isfile(source), 'missing vendored FE-Repo Aversa source')
        self.assertTrue(os.path.isfile(derived), 'missing deterministic Ravisin bust')

        src = Image.open(source).convert('RGB').crop((0, 0, 96, 80))
        got = Image.open(derived)
        self.assertEqual(('P', (96, 80)), (got.mode, got.size))
        self.assertLessEqual(len(set(got.getdata())), 16)
        transparent_key = src.getpixel((0, 0))
        expected = [
            inject.cast.PORTRAIT_TRANSPARENT_RGB
            if pixel == transparent_key
            else inject.portraits.RAVISIN_RECOLOR.get(pixel, pixel)
            for pixel in src.getdata()
        ]
        self.assertEqual(expected, list(got.convert('RGB').getdata()),
                         'Ravisin must be an exact palette substitution, never redrawn pixels')
        self.assertEqual(0, sum(portrait_tool.clipped_mask(got)),
                         'the approved crown/mantle must clear FE8\'s portrait dead zone')

    def test_ravisin_dresses_collision_free_riev_and_normalizes_its_geometry(self):
        self.assertEqual('Riev', inject.cast.GUEST_PORTRAIT_MAP['ravisin'])
        self.assertEqual(('ravisin', 'Riev', 0x48, 'Ravisin'),
                         inject.cast.RAW_PID_PORTRAITS[inject.chapter_ids.CH05_BOSS_PID])
        slots = list(inject.cast.PORTRAIT_MAP.values()) + list(inject.cast.GUEST_PORTRAIT_MAP.values())
        self.assertEqual(len(slots), len(set(slots)), 'Ravisin collides with another portrait')
        self.assertIn('Riev', inject.portraits.dressed_portrait_slots(self.CAMPAIGN),
                      'dressed Riev slot would keep its vanilla mouth/eye geometry')

    def test_raw_boss_pid_gets_the_riev_identity(self):
        # The fixture carries EVERY registered raw pid, because raw_pid_portrait_data binds all
        # of them -- the moose (0xb9) joined the registry in #25, the grell (0xb7) in #284.
        # The grell is the case that proves the two bindings are independent: it takes a personal
        # line and NO identity, so it must keep the generic 0x255 name plate and gain no portrait.
        source = '''[0xb7 - 1] = {
        .baseLevel = 1,
        .nameTextId = 0x255,
        .number = 0xb7,
        .defaultClass = CLASS_MOGALL,
        .miniPortrait = 0x4,
        .baseHP = 0,
        .basePow = 0,
        .baseSkl = 0,
        .baseSpd = 0,
        .baseDef = 0,
        .baseRes = 0,
        .baseLck = 0,
        .baseCon = 0,
    },
    [0xb6 - 1] = {
        .nameTextId = 0x256,        /* distinct sentinel: this entry is present only so the
                                       baseLevel pass has a block to write (RAW_PID_LEVEL_SOURCES);
                                       it is NOT part of this test's name-plate assertions */
        .number = 0xb6,
        .defaultClass = CLASS_BRIGAND,
        .baseLevel = 1,
    },
    [0xb8 - 1] = {
        .baseLevel = 1,
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
    },
    [0xb9 - 1] = {
        .baseLevel = 1,
        .nameTextId = 0x255,
        .number = 0xb9,
        .defaultClass = CLASS_GORGON,
        .miniPortrait = 0x4,
    },
    [0xbb - 1] = {
        .baseLevel = 1,
        .nameTextId = 0x255,
        .number = 0xbb,
        .defaultClass = CLASS_GARGOYLE,
        .miniPortrait = 0x4,
    },
    [0xbc - 1] = {
        .baseLevel = 1,
        .nameTextId = 0x255,
        .number = 0xbc,
        .defaultClass = CLASS_DEATHGOYLE,
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
        patched = inject.raw_pids.raw_pid_portrait_data(source, self.CAMPAIGN)
        self.assertIn('.nameTextId = 0x246,', patched)
        self.assertIn('.portraitId = 0x48,', patched)
        # Ravisin is the only DRESSED raw pid; the moose and ch06's two boats are named without
        # a bust, and the grell takes neither -- so exactly one name plate stays generic.
        self.assertEqual(1, patched.count('.portraitId'))
        boats = inject.chapter_ids.CH06_BOAT_NAME_MSGS
        self.assertIn('.nameTextId = 0x%X,' % inject.chapter_ids.CH05_MOOSE_NAME_MSG, patched)
        self.assertIn('.nameTextId = 0x%X,' % boats['boat-east'], patched)   # the Burly Ram
        self.assertIn('.nameTextId = 0x%X,' % boats['boat-west'], patched)   # the Pronged Goat
        self.assertEqual(1, patched.count('.nameTextId = 0x255,'))
        # ...and every raw-pid boss leaves with a baseLevel matching its deploy level, so the
        # difficulty malus cannot reset its line (#303, RAW_PID_LEVEL_SOURCES).
        self.assertIn('.baseLevel = 7,', patched)      # Ravisin, level 7
        self.assertIn('.baseLevel = 3,', patched)      # the kobold brute, level 3
        self.assertEqual(5, patched.count('.miniPortrait = 0x4,'))

        for chapter_yaml, uid in ((inject.chapter_ids.CH05_CHAPTER_YAML, 'ravisin'),
                                  (inject.chapter_ids.CH03_CHAPTER_YAML, 'grell')):
            unit = next(enemy for enemy in inject.hosting._load_chapter_yaml(
                self.CAMPAIGN, chapter_yaml)['enemy_units'] if enemy['id'] == uid)
            for field in inject.stats.BASE_FIELDS:
                self.assertIn('.%s = %d,' % (field, unit['personal'].get(field, 0)), patched,
                              '%s personal %s did not reach the character table' % (uid, field))
        # A rescue hull's line rides the same route (ch06's west boat, #26): its block, and
        # only its block, gains the HP.
        west = patched[patched.index('[0xbc - 1]'):]
        west = west[:west.index('},')]
        self.assertIn('.baseHP = 9,', west)

    def test_name_injector_retitles_the_repurposed_riev_slot(self):
        with tempfile.TemporaryDirectory() as tmp:
            texts = os.path.join(tmp, 'texts.txt')
            with open(texts, 'w', encoding='utf-8') as f:
                f.write(inject.decomp.vanilla_decomp_text('texts/texts.txt'))
            with stubbed('TEXTS_TXT', texts):
                inject.text.reserve_appended_messages(verbose=False)   # as the build runs it
                inject.names.inject_names(self.CAMPAIGN, verbose=False)
            with open(texts, encoding='utf-8') as f:
                written = f.read()
        body = re.search(r'## MSG_246\n(.*?)(?=\n## MSG_)', written, re.S).group(1)
        self.assertEqual('Ravisin[.][X]', body.strip())


class BasilHasOneDeathQuote(unittest.TestCase):
    """Basil falls with ONE line, wherever she falls (Nicolas, 2026-08-16).

    FE8 would happily give her two: a chapter-keyed row ahead of her chapter=0xFF one is
    vanilla's own shape for the escort a chapter is built around, and ch05 briefly shipped it.
    It was cut because both boxes were the same interrupted apology about the same undelivered
    berry, so the second bought a mechanism and no line. The berry is the survivor, and it now
    fires everywhere rather than only in the tomb.
    """
    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_the_berry_line_is_her_universal_quote(self):
        basil = inject.cast.load_unit(self.CAMPAIGN, 'basil')
        self.assertEqual("But I haven't-- I still have her berry...", basil['death_quote'])

    def test_she_has_exactly_one_row_and_it_fires_everywhere(self):
        rows = inject.death_quotes.pc_death_quote_rows(self.CAMPAIGN)
        pid = '.pid     = %s,' % inject.cast.char_symbol(inject.cast.PORTRAIT_MAP['basil'])
        hers = [row for row in rows if pid in row]
        self.assertEqual(1, len(hers), 'a second row for one pid is the thing that was cut')
        self.assertIn('.chapter = 0xFF', hers[0])
        self.assertIn('.msg     = 0x%04X,' % inject.death_quotes.PC_DEATH_QUOTE_MSGS['basil'], hers[0])

    def test_no_cast_member_carries_a_chapter_keyed_death_row(self):
        """The general form of the same call: the death-quote pass emits universal rows only.
        A chapter injector cannot add one behind our backs either -- it runs BEFORE this pass,
        which prepends at the head, so its row would never win GetDefeatTalkEntry's first match.
        """
        for row in inject.death_quotes.pc_death_quote_rows(self.CAMPAIGN):
            self.assertIn('.chapter = 0xFF', row)

    def test_ch05_no_longer_authors_a_death_box_of_its_own(self):
        chap = inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH05_CHAPTER_YAML)
        triggers = [e.get('trigger') for e in chap['events']]
        self.assertNotIn('unit_death', triggers)
        self.assertFalse(injector_constants('^CH05_BASIL_DEATH_MSG$'))
        self.assertFalse(injector_constants('^ch05_basil_death_message$'))


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
        self.assertEqual(inject.cast.PORTRAIT_MAP['basil'], 'Artur')
        self.assertEqual(inject.cast.PORTRAIT_MAP['sahnar'], 'Marisa')
        slots = list(inject.cast.PORTRAIT_MAP.values())
        self.assertEqual(len(slots), len(set(slots)), 'two cast members share one slot')
        self.assertFalse(set(slots) & set(inject.cast.GUEST_PORTRAIT_MAP.values()),
                         'a cast slot collides with a cutscene guest slot')

    def test_the_healer_split_is_donor_deep(self):
        # decisions.md differentiates the army's two healers by DONOR (Moulder durable
        # war-priest vs Natasha frail mage-healer), which only exists once Basil has a
        # STAT_DONOR row -- the YAML design record cannot do it alone. Since 2026-08-08 the
        # split is ALSO class-deep (Sclorbo Priest / Basil Cleric), but the donor is still
        # what separates the stat lines, so this stays the guard.
        self.assertEqual(inject.stats.STAT_DONOR['sclorbo'], 'CHARACTER_MOULDER')
        self.assertEqual(inject.stats.STAT_DONOR['basil'], 'CHARACTER_NATASHA')
        self.assertEqual(inject.stats.STAT_DONOR['sahnar'], 'CHARACTER_JOSHUA')
        for uid in ('basil', 'sahnar'):   # no bespoke base/growth split for either
            self.assertEqual(inject.stats.BASE_DONOR[uid], inject.stats.STAT_DONOR[uid])
            self.assertEqual(inject.stats.GROWTH_DONOR[uid], inject.stats.STAT_DONOR[uid])

    def test_both_are_on_map_talk_recruits_of_ch05_with_opposite_factions(self):
        recruits = {r[0]: r for r in inject.recruit.on_map_talk_recruits(self.CAMPAIGN, self.CH05)}
        self.assertEqual(set(recruits), {'basil', 'sahnar'},
                         'ch05 recruits exactly Basil and Sahnar on the map')
        self.assertEqual(recruits['basil'][2], 'CLASS_CLERIC')
        self.assertEqual(recruits['sahnar'][2], 'CLASS_MYRMIDON')
        load = lambda uid: inject.cast.load_unit(self.CAMPAIGN, uid)
        self.assertEqual(inject.chapters.ch05.recruit_initial_faction(load('basil')), 'GREEN')
        self.assertEqual(inject.chapters.ch05.recruit_initial_faction(load('sahnar')), 'RED')

    def test_basil_is_a_cleric_because_priest_promotes_into_the_wrong_weapon_type(self):
        """The whole reason for the class (Nicolas, 2026-08-08). See decisions.md.

        Priest's `ClassData.promotion` is CLASS_SAGE -- an ANIMA mage -- while basil.yaml's
        `battle_anim.spell_palette_tint` declares STAFF + LIGHT, i.e. Bishop. Cleric's default
        is CLASS_BISHOP_F, which IS light, so the class table points him at the class his own
        art already assumes. Pinned against the decomp so the two cannot drift apart again.
        """
        table = inject.sms._vanilla_class_table()
        self.assertEqual(table['CLASS_PRIEST']['promotion'], 'CLASS_SAGE',
                         'Priest still defaults into anima -- the reason Basil left it')
        self.assertEqual(table['CLASS_CLERIC']['promotion'], 'CLASS_BISHOP_F')
        # ...and the YAML's authored branch is the decomp's branch, not a wish.
        display = {'CLASS_BISHOP_F': 'Bishop', 'CLASS_VALKYRIE': 'Valkyrie'}
        branches = inject.sms._promotion_branches()['CLASS_CLERIC']
        promo = inject.cast.load_unit(self.CAMPAIGN, 'basil')['promotion']
        self.assertEqual(sorted(promo['branch']), sorted(display[c] for c in branches))
        self.assertEqual(promo['default'], 'Bishop')

    def test_basil_bases_are_vanilla_cleric_class_data_verbatim(self):
        # basil.yaml claims its stat block is class data "verbatim"; that claim is only worth
        # anything if something checks it. CON is load-bearing beyond flavour: CanUnitRescue
        # is `GetUnitAid(actor) >= UNIT_CON(target)` (bmunit.c), so Cleric's CON 4 is what lets
        # more of the party ferry the ch05 escort than Priest's CON 5 would.
        bases = inject.stats.class_base_stats('CLASS_CLERIC',
                                    inject.decomp.vanilla_decomp_text('src/data_classes.c'))
        fe = inject.cast.load_unit(self.CAMPAIGN, 'basil')['fe_stats']
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
        self.assertEqual(inject.cast.load_unit(self.CAMPAIGN, 'basil').get('gender'), 'female')
        self.assertIn('.attributes = CA_FEMALE',
                      inject.stats._set_gender('{\n    .number = 1,\n}', True))
        self.assertNotIn('CA_FEMALE',
                         inject.stats._set_gender('{\n    .attributes = CA_FEMALE,\n}', False))

    def test_neither_rides_the_ch05_prep_roster(self):
        # They join DURING ch05, so cast_available_at must not seat them in its deploy cap
        # (that is what the roster/cap parity is measured against) -- but ch06 must have them.
        for n, expected in ((self.CH05, False), (self.CH05 + 1, True)):
            seated = {uid for uid, *_ in inject.cast._classed_cast(self.CAMPAIGN, available_at=n)[0]}
            self.assertEqual({'basil', 'sahnar'} <= seated, expected,
                             'wrong prep availability at chapter %d' % n)

    def test_the_gated_recruiter_is_basil_only(self):
        # Sahnar's recruiter is authored data (her `parley.by`), not a roster query -- she does
        # not weigh the argument, she recognises Basil (lore/sahnar.md). Same helper ch04's
        # Marty->Lupin parley uses; the chapter picks parley_recruiters over talk_recruiters.
        sahnar = next(e for e in inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH05_CHAPTER_YAML)
                      ['enemy_units'] if e['id'] == 'sahnar')
        self.assertEqual(inject.recruit.parley_recruiters(sahnar), ['CHARACTER_ARTUR'])

    def test_basils_green_tile_costs_no_deployment_and_can_reach_sahnar(self):
        # The three silent ways a green placement goes wrong (assert_green_recruit_placement).
        # Worth pinning the tile itself: vanilla's Natasha is BLUE and stands on what is now one
        # of our nine deploy slots, so copying the twin 1:1 here -- which is this chapter's
        # standing habit -- would have quietly cost the player a deployment.
        chap = inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH05_CHAPTER_YAML)
        slots = [tuple(s) for s in chap['deployment']['deploy_slots']]
        self.assertNotIn(inject.chapters.ch05.CH05_BASIL_GREEN_POS, slots)
        maps = os.path.join(inject.decomp.REPO, 'campaigns', self.CAMPAIGN, 'maps')
        inject.chapters.ch05.assert_green_recruit_placement(          # sys.exits on any of the three
            chap, maps, inject.chapters.ch05.CH05_LAYOUT[1], inject.chapters.ch05.CH05_BASIL_GREEN_POS,
            inject.chapters.ch05.CH05_BASIL_MOV_TABLE, 'Basil',
            must_reach=tuple(next(e for e in chap['enemy_units']
                                  if e['id'] == 'sahnar')['positions'][0]))

    def test_the_talk_script_flips_sahnar_and_carries_no_pack_conversion(self):
        # ch04 splices a pre_script (the wolf pack's conversion sweep) into the same flow;
        # ch05 has no group to bring over, so the script must be the bare talk -> CUSA.
        script = inject.recruit.talk_recruit_script(inject.chapter_ids.CH05_SAHNAR_TALK_MSG, 'CHARACTER_MARISA')
        self.assertIn('TEXTSHOW(0x%X)' % inject.chapter_ids.CH05_SAHNAR_TALK_MSG, script)
        self.assertIn('CUSA(CHARACTER_MARISA)', script)
        self.assertNotIn('CUSN', script)
        self.assertLess(script.index('TEXTSHOW'), script.index('CUSA'))   # line, then the flip

    def test_each_carries_a_death_quote(self):
        # inject_pc_death_quotes hard-exits without one (#6), so a slot with no quote is a
        # build break, not a missing nicety.
        for uid in ('basil', 'sahnar'):
            self.assertTrue((inject.cast.load_unit(self.CAMPAIGN, uid).get('death_quote') or '').strip(),
                            '%s.yaml needs a death_quote' % uid)


if __name__ == '__main__':
    unittest.main()
