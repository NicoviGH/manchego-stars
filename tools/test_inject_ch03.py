#!/usr/bin/env python3
"""Tests for tools/inject/chapters/ch03.py.

Run:  python3 tools/test_inject_ch03.py
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.cast
import inject.chapter_ids
import inject.chapters.ch03
import inject.decomp
import inject.hosting
import inject.maps
import inject.scenes


class Ch03MidmapExecution(unittest.TestCase):
    """Ch03 midmap RBG-execution beat (#23 item 1): the Icewind Brute is a mid-map miniboss
    whose DEFEAT fires a flagged death cutscene (RBG guns down the beaten Brute) -- the mirror
    of the grell's DefeatBoss WIN, but keyed to a tmp flag + a Misc AFEV instead of the win
    flag. These pin the pure builders inject_ch03 consumes."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapter_ids.CH03_CHAPTER_YAML)

    def test_exactly_one_miniboss_and_it_is_the_brute(self):
        """The RBG-execution trigger = the one enemy flagged `is_miniboss` (the Icewind Brute)."""
        mbs = inject.scenes.midmap_minibosses(self._chap())
        self.assertEqual([e['id'] for e in mbs], ['kobold-steel'])

    def test_miniboss_pid_is_a_clean_sibling_distinct_from_boss_and_generic(self):
        """A unique raw pid so the Brute's flagged death quote keys the trigger to it ALONE --
        not the shared generic 0xaa (all trash) and not the grell's 0xb7 (the WIN)."""
        self.assertNotIn(inject.chapter_ids.CH03_BRUTE_MINIBOSS_PID,
                         (inject.chapters.ch03.CH03_GENERIC_PID, inject.chapter_ids.CH03_BOSS_PID))

    def test_afev_fires_once_on_the_brute_flag(self):
        """The Misc AFEV watches the Brute-defeat flag, runs the midmap script, and guards the
        one-shot with a distinct ent-flag (set after firing) -- else it re-fires every turn."""
        line = inject.chapters.ch03.midmap_afev(inject.chapters.ch03.CH03_MIDMAP_GUARD_FLAG, inject.chapters.ch03.CH03_MIDMAP_SCRIPT,
                              inject.chapters.ch03.CH03_BRUTE_DEFEAT_FLAG)
        self.assertEqual(line, 'AFEV(%s, %s, %s)' % (inject.chapters.ch03.CH03_MIDMAP_GUARD_FLAG,
                                                     inject.chapters.ch03.CH03_MIDMAP_SCRIPT,
                                                     inject.chapters.ch03.CH03_BRUTE_DEFEAT_FLAG))
        self.assertNotEqual(inject.chapters.ch03.CH03_MIDMAP_GUARD_FLAG, inject.chapters.ch03.CH03_BRUTE_DEFEAT_FLAG)

    def test_ch03_tmp_flags_are_all_distinct(self):
        """tmp flags are chapter-local; the midmap's two must not collide with Trex's talk flag."""
        flags = {inject.chapters.ch03.CH03_TREX_TALK_FLAG, inject.chapters.ch03.CH03_BRUTE_DEFEAT_FLAG, inject.chapters.ch03.CH03_MIDMAP_GUARD_FLAG}
        self.assertEqual(len(flags), 3)

    def test_silent_defeat_quote_sets_the_flag_without_a_portrait(self):
        """flag_defeat_quote = a msg=0 gDefeatTalkList entry: SetPidDefeatedFlag still sets the
        flag on death (no CA_BOSS gate), but the faceless quote is suppressed (the cutscene is
        the separate AFEV script). Shared by the grell WIN and the Brute midmap trigger."""
        q = inject.scenes.flag_defeat_quote(inject.chapter_ids.CH03_BRUTE_MINIBOSS_PID, 'CHAPTER_L_4',
                                 inject.chapters.ch03.CH03_BRUTE_DEFEAT_FLAG, 'brute')
        self.assertIn('.pid     = %s' % inject.chapter_ids.CH03_BRUTE_MINIBOSS_PID, q)
        self.assertIn('.chapter = CHAPTER_L_4', q)
        self.assertIn('.flag    = %s' % inject.chapters.ch03.CH03_BRUTE_DEFEAT_FLAG, q)
        self.assertIn('.msg     = 0', q)

    def test_midmap_yaml_splits_into_the_seven_restaged_beats(self):
        """The restaged midmap `script:` splits into 7 beats matching the reserved msg-id block:
        A Pinky / A2 ACTION attack / A3 Brute snarl / B RBG "Say cheese" / B2 ACTION shot /
        B3 Pinky+RBG / C Wolfram. A beat_break drift would desync the zip (guarded by _split_event_beats)."""
        self.assertEqual(len(inject.chapter_ids.CH03_MIDMAP_MSGS), 7)
        _card, beats = inject.scenes._split_event_beats(self._chap(), 'midmap', 'ch03 midmap',
                                             inject.chapter_ids.CH03_MIDMAP_MSGS, card_required=False)
        self.assertEqual(len(beats), 7)

    def test_midmap_action_boxes_faceless_dialogue_beats_faced(self):
        """Routing by face: the two ACTION narration beats (A2 the attack, B2 the shot) are faceless ->
        the opaque auto-centered box; the five dialogue beats (Pinky / Brute / RBG / Pinky+RBG / Wolfram)
        resolve to faces -> map talk bubbles. The Brute is faced via its Caellach mug (fallback)."""
        self.assertEqual(inject.cast.GUEST_PORTRAIT_MAP.get('kobold-brute'), 'Caellach')
        _card, beats = inject.scenes._split_event_beats(self._chap(), 'midmap', 'ch03 midmap',
                                             inject.chapter_ids.CH03_MIDMAP_MSGS, card_required=False)
        fid = inject.scenes._make_fid({'narration': None, 'boy-crier': '[FID_x]'}, 'ch03 midmap test',
                           fallback=inject.cast.GUEST_PORTRAIT_MAP)
        self.assertEqual([inject.chapters.ch03._beat_is_faceless(b, fid) for b in beats],
                         [False, True, False, False, True, False, False])

    def test_beat_is_faceless_detects_a_mugless_speaker(self):
        """The routing mechanism: without the Brute's mug, its snarl beat (A3) also flags faceless ->
        it would ride the opaque box (the fallback for any future mugless NPC), alongside the two
        genuine narration action boxes."""
        _card, beats = inject.scenes._split_event_beats(self._chap(), 'midmap', 'ch03 midmap',
                                             inject.chapter_ids.CH03_MIDMAP_MSGS, card_required=False)
        mugless = inject.scenes._make_fid({'narration': None, 'kobold-brute': None}, 'ch03 midmap test')
        self.assertEqual([inject.chapters.ch03._beat_is_faceless(b, mugless) for b in beats],
                         [False, True, True, False, True, False, False])   # A3 (Brute) faceless w/o a mug


class Ch03TileChanges(unittest.TestCase):
    """The ch03 chest + door tile-changes (#23): one MapChange array flips each chest's
    FF5 navy tile 17->29 on loot and opens each door to the floor tile DIRECTLY BELOW it
    (Nicolas 2026-07-11 -- 'use the tile directly adjacent and below it'). GetMapChangeIdAt
    matches by POSITION, so chests + doors coexist in one array; ids just stay unique."""
    CAMPAIGN = 'rime-of-the-frostmaiden'
    STEM = inject.chapters.ch03.CH03_LAYOUT[1]
    MAPS = os.path.join(inject.decomp.REPO, 'campaigns', 'rime-of-the-frostmaiden', 'maps')

    def test_reads_the_painted_metatile_at_a_cell(self):
        # The retile paints the FF5 navy chest (metatile 17) at (6,3); the .mar stores
        # metatile<<5, so the reader must decode 17 back out.
        self.assertEqual(inject.chapters.ch03._read_map_metatile(self.MAPS, self.STEM, 6, 3), 17)

    def test_door_open_tile_is_the_metatile_directly_below(self):
        # Vanilla Ch3 doors sit at (6,10)/(10,5)/(2,3); the open tile = the cell one row down
        # on the COMMITTED (hand-painted) map -- road tiles (572/492) + the stairs down (626),
        # all passable, so the opened door lets the party through.
        below = [inject.chapters.ch03._read_map_metatile(self.MAPS, self.STEM, x, y + 1)
                 for (x, y) in [(6, 10), (10, 5), (2, 3)]]
        self.assertEqual(below, [572, 626, 492])

    def _asm(self, chests, doors):
        """ch03's own change list, through the shared emitter (#214 generalised it out of a
        ch03-only helper). chests -> the FF5 open-chest tile; doors -> their below-cell floor."""
        changes = [(x, y, 1, 1, [inject.chapters.ch03.CH03_CHEST_OPEN_TILE], 'chest') for x, y in chests]
        changes += [(x, y, 1, 1, [tile], 'door') for x, y, tile in doors]
        return inject.maps.map_changes_asm('MS_Ch03MapChanges', changes)

    def test_asm_emits_one_change_per_chest_then_per_door_with_unique_ids(self):
        asm = self._asm([(6, 3), (8, 3)], [(6, 10, 98), (2, 3, 66)])
        ids = [int(l.split(',')[0].split()[1]) for l in asm.splitlines()
               if l.strip().startswith('.byte') and 'terminator' not in l]
        self.assertEqual(ids, [0, 1, 2, 3])   # 2 chests then 2 doors, contiguous + unique
        self.assertIn('.byte -1', asm)        # id<0 terminator closes the array

    def test_asm_chests_carry_the_open_chest_tile(self):
        asm = self._asm([(6, 3), (8, 3)], [])
        self.assertEqual(asm.count('.hword %d' % (inject.chapters.ch03.CH03_CHEST_OPEN_TILE << 2)), 2)

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
            inject.maps.map_changes_asm('MS_X', [(4, 8, 1, 3, [6], 'short')])


if __name__ == '__main__':
    unittest.main()
