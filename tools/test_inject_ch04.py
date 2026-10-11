#!/usr/bin/env python3
"""Tests for tools/inject/chapters/ch04.py.

Run:  python3 tools/test_inject_ch04.py
"""
import os
import re
import sys
import unittest

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.cast
import inject.chapter_ids
import inject.chapters.ch04
import inject.chapters.ch05
import inject.decomp
import inject.hosting
import inject.hosts
import inject.maps
import inject.messages
import inject.recruit
import inject.reskins
import inject.scenes
import inject.terrain
import inject.text
import inject.units
import inject.villages
import inject.warm
import gen_chapter_title
import fe8_talk_font as font
from inject import source as injector  # the injector's source, every file of it (#389)

# Read the COMMITTED decomp, not the working tree -- the build overwrites donor portrait
# slots (Gilliam/Neimi/Moulder/Vanessa), so a working-tree read would be non-hermetic.
VANILLA = inject.decomp.vanilla_decomp_text('src/data_characters.c')


def enemy_rows(chap, **kwargs):
    """ch04's enemy rows, through the shared emitter with ch04's own ids and pid rule."""
    m = inject.chapters.ch04
    return inject.units.enemy_rows(chap, m.CH04_CLASS_IDS, m.CH04_ITEM_IDS, m.ch04_enemy_pid,
                                   **kwargs)


class Ch04RuntimeHost(unittest.TestCase):
    """Ch04's first playable host: approved 23-unit vanilla-monster roster, snowy map,
    fog, prep cap, and turn-based reinforcement split. D&D identities stay narrative
    grounding; the player-facing unit names remain the vanilla FE8 monster names."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def _chap(self):
        return inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapters.ch04.CH04_CHAPTER_YAML)

    def test_every_ch04_decomp_output_is_restored_before_reinjection(self):
        self.assertTrue({
            'src/events/ch5-eventinfo.h',
            'src/events/ch5-eventscript.h',
            'graphics/chap_title/chap_title_5.png',
        }.issubset(set(inject.warm.PATCHED_DECOMP_FILES)))

    def test_lupin_is_a_red_on_map_talk_recruit(self):
        # ch04's parley recruit (Joshua-style red->blue). The recruit path is faction-
        # parameterized and reused: Trex/Basil start GREEN, Lupin/Sahnar start RED. Lupin
        # rides a collision-free identity slot (his stat donor stays Kyle).
        recruits = inject.recruit.on_map_talk_recruits(self.CAMPAIGN, self._chap()['chapter_number'])
        lupin = [r for r in recruits if r[0] == 'lupin']
        self.assertEqual(len(lupin), 1, "Lupin should be ch04's on-map talk recruit")
        self.assertEqual(lupin[0][1], 'Duessel')
        self.assertEqual(
            inject.chapters.ch05.recruit_initial_faction(inject.cast.load_unit(self.CAMPAIGN, 'lupin')), 'RED')

    def test_recruit_initial_faction_defaults_green(self):
        # Trex (and future Basil) are the green->blue path; RED is opt-in via recruit.initial_faction.
        self.assertEqual(
            inject.chapters.ch05.recruit_initial_faction(inject.cast.load_unit(self.CAMPAIGN, 'trex')), 'GREEN')

    def test_host_and_deployment_match_the_approved_ch04_shape(self):
        chap = self._chap()
        self.assertEqual(inject.hosts.CH04_HOST_INDEX, 5)
        self.assertEqual(inject.chapters.ch04.CH04_GOAL_DONOR, inject.hosts.CH02_HOST_INDEX)
        self.assertEqual(chap['deployment']['deploy_limit'], 9)
        self.assertEqual(len(chap['deployment']['deploy_slots']), 9)
        cast, _ = inject.cast._classed_cast(self.CAMPAIGN, available_at=4)
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
        self.assertEqual(len(enemy_rows(chap)), 10)
        self.assertEqual(len(enemy_rows(chap, arrives_turn=2)), 6)
        self.assertEqual(len(enemy_rows(chap, arrives_turn=3)), 7)

    # -- Stage 2b: the turn-2 wolf-pack reveal + the Marty->Lupin parley (in-place) ---------
    def _lupin(self):
        return next(r for r in inject.recruit.on_map_talk_recruits(self.CAMPAIGN, 4) if r[0] == 'lupin')

    def _reveal_positions(self):
        return inject.chapters.ch04._ch04_reveal_wave(self._chap())['positions']

    def test_turn2_reveal_is_five_generic_wolves_plus_lupin_red_leader(self):
        # The pack leader tile becomes Lupin (red, CHARACTER_DUESSEL, Cavalier under the hood);
        # the other 5 stay generic Mauthe Doogs. 5 + Lupin = 6 -> holds the turn-2 parity count.
        rows = inject.chapters.ch04.ch04_turn2_reveal_rows(self._chap(), self._lupin())
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
        self.assertEqual(len(enemy_rows(self._chap(), arrives_turn=2)), 6)
        self.assertEqual(len(inject.chapters.ch04.ch04_turn2_reveal_rows(self._chap(), self._lupin())), 6)

    def test_each_generic_wolf_gets_its_own_pid(self):
        # CUSN and CHECK_ALIVE both resolve a pid through GetUnitFromCharId, which returns the
        # FIRST match scanning blue->green->red. Five wolves sharing one pid can therefore only
        # ever be converted ONCE (the second CUSN re-finds the wolf it just turned green), which
        # is why the parley had to reload a table instead. One pid each makes them addressable.
        rows = inject.chapters.ch04.ch04_turn2_reveal_rows(self._chap(), self._lupin())
        pids = re.findall(r'\.charIndex = (\w+),', '\n'.join(rows))
        self.assertEqual(len(pids), 6)
        self.assertEqual(len(set(pids)), 6, 'every wolf needs its own pid: %s' % pids)
        self.assertEqual([p for p in pids if p != 'CHARACTER_DUESSEL'],
                         list(inject.chapters.ch04.CH04_PACK_PIDS))

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
        for pid in inject.chapters.ch04.CH04_PACK_PIDS:
            e = entry(pid)
            self.assertEqual(e['number'], pid)              # the slot is itself, not an alias
            for field in [f for f in doog if f not in ('number', 'defaultClass')]:
                self.assertEqual(e[field], doog[field],
                                 '%s.%s differs from the doog slot' % (pid, field))

    def test_lycanroc_pack_reskin_is_declared_and_clones_the_doog(self):
        rk = [r for r in inject.reskins.enemy_class_reskins(self.CAMPAIGN) if r['id'] == 'lycanroc-pack']
        self.assertEqual(len(rk), 1, 'campaign.yaml must declare the lycanroc-pack reskin')
        rk = rk[0]
        self.assertEqual(rk['base'], 'CLASS_MAUTHEDOOG')     # stats/anim ride along -> parity
        self.assertEqual(rk['slot'], inject.chapters.ch04.CH04_GREEN_PACK_CLASS)
        self.assertEqual(str(rk['frame']), '32x32')          # 32x32 quadruped on a 16x32 doog
        self.assertEqual(rk['sprite'], 'lycanroc-pack')
        for suffix in ('.png', '_mu.png'):
            self.assertTrue(os.path.isfile(os.path.join(
                inject.decomp.REPO, 'campaigns', self.CAMPAIGN, 'map_sprites',
                rk['sprite'] + suffix)), 'missing map_sprites/%s%s' % (rk['sprite'], suffix))

    def test_the_parley_converts_each_wolf_where_it_stands(self):
        # No DISA + LOAD1: clearing the pack and reloading its table put the wolves back on
        # their SPAWN tiles (they teleported home mid-fight) and resurrected any the player had
        # already killed. CUSN flips the unit in place, so the pack stays where it is.
        pre = inject.chapters.ch04.convert_survivors_green(('0xb3', '0xb4'), 0x40, 'wolf')
        self.assertNotIn('DISA', pre)
        self.assertNotIn('LOAD1', pre)
        self.assertIn('CUSN(0xb3)', pre)
        self.assertIn('CUSN(0xb4)', pre)

    def test_a_wolf_killed_before_the_parley_is_skipped_not_converted(self):
        # UnitKill WIPES a non-blue slot (pCharacterData = NULL, bmunit.c:988) and a CUSN on an
        # unresolvable pid returns EVC_ERROR rather than no-op'ing the way DISA/KILL do
        # (eventscr.c:3317) -- so a bare sweep breaks in exactly the kill-then-parley case this
        # is meant to reward. Each CUSN sits behind its own CHECK_ALIVE, jumping its own label.
        pre = inject.chapters.ch04.convert_survivors_green(('0xb3', '0xb4'), 0x40, 'wolf')
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
        return os.path.join(inject.decomp.REPO, 'campaigns', self.CAMPAIGN, 'maps')

    def _bern(self):
        import map_tileset_tool as mt
        return mt._tileset_from_dir(os.path.join(self._maps_dir(), 'tilesets', 'snowy-bern'))

    def test_the_village_the_yaml_declares_sits_on_a_visitable_tile(self):
        """The guard #205 needed from the content side. FE8 offers Visit only on village/house
        terrain (bmmenu.c:735), so a `villages:` entry whose tile is scenery is a reward that
        silently does not exist -- which is exactly what shipped, because the snowy reskin had
        mapped vanilla's village metatile onto ruins."""
        inject.villages.assert_village_tiles_visitable(self._chap(), self._maps_dir(), inject.chapters.ch04.CH04_LAYOUT[1])

    def test_a_village_declared_on_scenery_fails_the_build(self):
        chap = dict(self._chap())
        chap['villages'] = [{'id': 'nowhere', 'tile': [7, 7],
                             'visit_reward': [{'id': 'iron-axe'}]}]
        with self.assertRaises(SystemExit):
            inject.villages.assert_village_tiles_visitable(chap, self._maps_dir(), inject.chapters.ch04.CH04_LAYOUT[1])

    def test_ch04_wires_its_village_where_vanilla_ch4_did(self):
        # vanilla Ch4: Village(0, EventScr_089F1BD8, 8, 2) -- the ITEM village (the other, at
        # (1,11), is vanilla's recruit village, whose role the Lupin parley took over).
        body = inject.villages.chapter_location_events(
            self._chap(), inject.chapters.ch04.CH04_VILLAGE_SLOTS)
        self.assertIn('Village(0, %s, 8, 2)' % inject.chapter_ids.CH04_VILLAGE_SCRIPT, body)
        self.assertTrue(body.rstrip().endswith('END_MAIN\n}'))

    def test_the_village_hands_the_visitor_the_authored_reward(self):
        # vanilla's own shape (EventScr_089F1BD8): one text box over the village BG, then
        # SVAL the item into slot 3 and GIVEITEMTO the unit that visited.
        s = inject.villages.village_script(0x9C3, 'ITEM_AXE_IRON', inject.chapter_ids.CH04_OPENING_FOREST_BG)
        self.assertIn('Text_BG(%s, 0x9C3)' % inject.chapter_ids.CH04_OPENING_FOREST_BG, s)
        self.assertLess(s.index('Text_BG'), s.index('SVAL(EVT_SLOT_3, ITEM_AXE_IRON)'))
        self.assertLess(s.index('SVAL(EVT_SLOT_3, ITEM_AXE_IRON)'),
                        s.index('GIVEITEMTO(CHAR_EVT_ACTIVE_UNIT)'))

    def test_the_reward_item_is_read_from_the_chapter_yaml(self):
        """#208's lesson applied early: the village's reward and its line are CONTENT, so they
        live in the chapter YAML and the injector reads them."""
        village = self._chap()['villages'][0]
        self.assertEqual('iron-axe', village['visit_reward'][0]['id'])
        self.assertEqual('ITEM_AXE_IRON', inject.chapters.ch04.CH04_ITEM_IDS['iron-axe'])
        self.assertTrue(village.get('visit_text'), 'the village needs a line to show')

    def test_the_moose_sighting_area_does_not_cover_a_village_doorstep(self):
        """Vanilla's AREA was (0,9)-(14,14) and touched neither village; ours is authored, and
        its first draft started exactly on the axe village's tile -- so stepping up to visit
        would have fired the sighting cutscene instead."""
        x1, y1, x2, y2 = inject.chapters.ch04.CH04_MOOSE_AREA
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
        asm = inject.maps.map_changes_asm('MS_TestChanges', [
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
        changes = inject.chapters.ch04.ch04_map_changes(self._chap(), self._maps_dir())
        snag = [c for c in changes if (c[0], c[1]) == inject.chapters.ch04.CH04_SNAG_POS]
        self.assertEqual(len(snag), 1, 'ch04 must register exactly one snag change')
        x, y, w, h, tiles, _why = snag[0]
        self.assertEqual((w, h), (1, 3))
        ids = inject.maps.terrain_ids()
        tileset = self._bern()
        self.assertEqual([7, 36, 11], tiles,
                         'the snag must use vanilla Ch4\'s three-cell downed-log composition')
        self.assertEqual(ids['TERRAIN_BRIDGE_SNAG'], tileset.terrain(tiles[1]),
                         'the middle cell must remain a fallen snag, not a generic bridge')
        # ...and every tile it writes must be PAINTED. snowy-bern declares BRIDGE_SNAG on an
        # unpainted metatile; using it left a black square in the river with a perfectly correct
        # terrain byte, which no data check would have caught (#214).
        for m in tiles:
            self.assertFalse(inject.maps._is_blank_metatile(tileset, m),
                             'map change writes blank metatile %d' % m)

    def test_preferred_snowy_metatile_must_be_painted(self):
        """A preferred slot is only a hint: terrain-correct but blank art must fall back to
        the first painted metatile, just like the ordinary terrain search."""
        want = inject.maps.terrain_ids()['TERRAIN_BRIDGE_SNAG']

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
            inject.maps._snowy_metatile_for(FakeTileset(), 'TERRAIN_BRIDGE_SNAG', prefer=5),
        )

    def test_the_snag_change_covers_the_tile_that_is_actually_a_snag(self):
        """Pins the trap rather than today's answer: the engine adds the obstacle on the
        TERRAIN_SNAG tile (bmtrick.c) and looks the change up by that position, so a change
        authored a row off breaks silently -- the snag stays hittable and nothing happens."""
        width, height, terrain = inject.terrain._map_terrain_grid(self._maps_dir(), inject.chapters.ch04.CH04_LAYOUT[1])
        x, y = inject.chapters.ch04.CH04_SNAG_POS
        self.assertEqual(inject.maps.terrain_ids()['TERRAIN_SNAG'], terrain[y][x])

    def test_a_visited_village_stops_looking_unvisited(self):
        changes = inject.chapters.ch04.ch04_map_changes(self._chap(), self._maps_dir())
        village = self._chap()['villages'][0]['tile']
        door = [c for c in changes if [c[0], c[1]] == village]
        self.assertEqual(len(door), 1)
        self.assertEqual(inject.maps.terrain_ids()['TERRAIN_VILLAGE_CLOSED'],
                         self._bern().terrain(door[0][4][0]))

    def test_the_village_line_is_vanillas_own_snag_tutorial(self):
        """Nicolas 2026-08-02: copy vanilla 1:1. The line exists to teach the snag gimmick and
        hand over the tool -- a flavour line throws the function away."""
        text = ' '.join(line for _who, line in
                        inject.villages.village_boxes(self._chap()['villages'][0]))
        self.assertIn('snag', text)
        self.assertIn('bridge', text)
        self.assertNotIn('husband', text)   # the placeholder draft this replaces

    # -- #24: the SECOND village, vanilla Ch4's other cottage --------------------------------
    def test_both_of_vanilla_ch4s_villages_are_wired(self):
        """#24's last item. Vanilla Ch4 wires TWO villages -- Village(0, .., 8, 2) and
        Village(0, .., 1, 11) -- and we shipped only the axe one. The cottage at (1,11) stood
        on visitable terrain with no Location entry, so FE8 offered no Visit at all: the player
        saw a house they could not enter."""
        body = inject.villages.chapter_location_events(
            self._chap(), inject.chapters.ch04.CH04_VILLAGE_SLOTS)
        self.assertIn('Village(0, %s, 8, 2)' % inject.chapter_ids.CH04_VILLAGE_SCRIPT, body)
        self.assertIn('Village(0, %s, 1, 11)' % inject.chapter_ids.CH04_COTTAGE_SCRIPT, body)
        self.assertTrue(body.rstrip().endswith('END_MAIN\n}'))

    def test_each_village_owns_its_own_script_and_message_slot(self):
        """Two doors sharing one script show the same line at both -- and, worse, run the
        give-item tail twice."""
        self.assertNotEqual(inject.chapter_ids.CH04_VILLAGE_SCRIPT, inject.chapter_ids.CH04_COTTAGE_SCRIPT)
        self.assertNotEqual(inject.chapter_ids.CH04_VILLAGE_MSG, inject.chapter_ids.CH04_COTTAGE_MSG)
        # ...and the new id has to join the ownership registry, or the uniqueness guard that
        # #24 asked for cannot see it (a double-claim overwrites silently and stays green).
        self.assertIn(inject.chapter_ids.CH04_COTTAGE_MSG, inject.messages.HOSTED_CHAPTER_MESSAGE_IDS['ch04'])

    def test_each_village_plays_over_winter_art_not_vanillas_green_town(self):
        """ch04 is a snowbound forest under fog, and `BG_NORMAL_VILLAGE` is vanilla's TEMPERATE
        green town -- so the backdrop, which is the whole screen during a village visit, was
        showing summer (Nicolas, 2026-08-05). Both doors take the fogged forest that Pinky's
        opening beat already plays over: there is no TOWN on this map -- both cottages are
        cabins standing in the same woods and the visitor is outside one of them (Nicolas: "if
        we're outside their cabin, just use the bg you put behind pinky in his fog scene").
        """
        for name, slot in inject.chapter_ids.CH04_VILLAGE_SLOTS.items():
            self.assertNotEqual('BG_NORMAL_VILLAGE', slot[3],
                                '%s is still on vanilla temperate art' % name)
            self.assertEqual(inject.chapter_ids.CH04_OPENING_FOREST_BG, slot[3],
                             '%s should stand outside its cabin, in the fog' % name)

    def test_a_village_script_plays_over_the_backdrop_it_is_given(self):
        s = inject.villages.village_script(0x9C6, None, 'BG_MS_LONELYWOOD_FOG')
        self.assertIn('Text_BG(BG_MS_LONELYWOOD_FOG, 0x9C6)', s)

    def test_a_village_with_no_reward_hands_over_nothing(self):
        """ch04's economy is deliberately Ch4-lean (decisions.md): the Iron Axe is the whole
        material gift, so the cottage's reward IS its line. The script must drop the give-item
        tail rather than quietly hand over some default."""
        s = inject.villages.village_script(0x9C6, None, inject.chapter_ids.CH04_OPENING_FOREST_BG)
        self.assertIn('Text_BG(%s, 0x9C6)' % inject.chapter_ids.CH04_OPENING_FOREST_BG, s)
        self.assertNotIn('SVAL(EVT_SLOT_3', s)
        self.assertNotIn('GIVEITEMTO', s)
        self.assertIn('EVBIT_T(7)', s)      # still marks the visit, so the door shuts

    def test_a_village_line_is_authored_in_boxes_not_reflowed(self):
        """A village line is dialogue: its A-press breaks are authored, not a side effect of
        where a 42-column wrap happens to land. One YAML entry == one GBA box."""
        for village in self._chap()['villages']:
            for _who, box in inject.villages.village_boxes(village):
                lines = inject.text._wrap_fe_lines(inject.text._fe_dialogue_text(box))
                self.assertLessEqual(len(lines), 2,
                                     'box overflows its A-press in %r (%dpx): %r'
                                     % (village['id'], font.text_px(
                                         inject.text._fe_dialogue_text(box)), box))

    def test_the_axe_villages_boxes_match_vanillas_own_four(self):
        """Vanilla's MSG_9B5 is FOUR boxes, each broken on a sentence. Flowed as one scalar
        ours reflowed to THREE and buttoned mid-sentence ("a handy bridge if / you could knock
        it over") -- 1:1 in words but not on screen, which is not what 1:1 was asked for."""
        boxes = [line for _who, line in
                 inject.villages.village_boxes(self._chap()['villages'][0])]
        self.assertEqual(4, len(boxes))
        self.assertTrue(boxes[0].rstrip().endswith('south of here?'), boxes[0])
        self.assertTrue(boxes[1].rstrip().endswith('knock it over.'), boxes[1])

    def test_the_cottage_line_drops_the_lore_the_chapter_has_nowhere_else(self):
        """The line's whole job (#24, Nicolas: "at least a lore drop or a hint"). Grounded in
        the DM notes -- "the frost druids did visit, but were largely ignored by villagefolk"
        -- and the book's Ravisin, who "won't rest until the forest is free of loggers". She
        is never NAMED here: the ending owns the chapter's one Ravisin seed (2026-07-03 cut)."""
        text = ' '.join(line for _who, line in
                        inject.villages.village_boxes(self._chap()['villages'][1]))
        self.assertIn('White furs', text)
        self.assertIn('southeast', text)
        self.assertNotIn('Ravisin', text)

    def test_both_villages_close_their_doors_when_visited(self):
        changes = inject.chapters.ch04.ch04_map_changes(self._chap(), self._maps_dir())
        for village in self._chap()['villages']:
            door = [c for c in changes if [c[0], c[1]] == village['tile']]
            self.assertEqual(1, len(door), 'no door change for %r' % village['id'])
            self.assertEqual(inject.maps.terrain_ids()['TERRAIN_VILLAGE_CLOSED'],
                             self._bern().terrain(door[0][4][0]))

    def test_parley_recruiter_is_marty_only(self):
        # Nicolas 2026-07-21: ch04's talker is Marty specifically, NOT ch03's any-party-member.
        # Data-driven from the convertible wave's parley.by; Marty rides the Seth slot.
        self.assertEqual(inject.recruit.parley_recruiters(inject.chapters.ch04._ch04_reveal_wave(self._chap())),
                         ['CHARACTER_SETH'])

    def test_reveal_cutscene_pans_loads_focuses_lupin_and_plants_the_parley(self):
        # Stage 2c: the turn-2 reveal rides the existing LOAD1 (vanilla EventScr_089F199C shape):
        # pan to the NW fog, burst the pack in, focus Lupin (the commander), then stub beats plant
        # the parley (Lupin commands; Marty flags "talk to it"). Real dialogue is Stage 4.
        s = inject.chapters.ch04.ch04_reveal_cutscene_script('UnitDef_088B5798', 'CHARACTER_DUESSEL',
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
        entries = inject.chapters.ch04._force_deployment_entries(
            inject.recruit.parley_recruiters(inject.chapters.ch04._ch04_reveal_wave(self._chap())), inject.hosts.CH04_HOST_INDEX)
        self.assertIn('{CHARACTER_SETH, 0xFF, %d}' % inject.hosts.CH04_HOST_INDEX, entries)

    def test_roster_uses_the_vanilla_monster_classes_and_weapons(self):
        rows = '\n'.join(enemy_rows(self._chap()) +
                         enemy_rows(self._chap(), arrives_turn=2) +
                         enemy_rows(self._chap(), arrives_turn=3))
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
        rows = '\n'.join(enemy_rows(self._chap(), arrives_turn=3))
        self.assertEqual(rows.count('.itemDrop = 1'), 1)
        self.assertEqual(rows.count('ITEM_VULNERARY'), 1)

    def test_ch04_title_card_has_a_complete_vanilla_glyph_atlas(self):
        card = gen_chapter_title.compose_title('Ch.4: The White Moose')
        self.assertEqual(card.size, (256, 16))
        self.assertIsNotNone(card.getbbox())


class Ch04Stage4Scenes(unittest.TestCase):
    """The ch04 authored-scene machinery (#24 Stage 4) + the two #198-review guards."""

    def setUp(self):
        import yaml
        with open(os.path.join(inject.decomp.REPO, 'campaigns', 'rime-of-the-frostmaiden',
                               'chapters', 'ch04-the-white-moose.yaml'), encoding='utf-8') as f:
            self.chap = yaml.safe_load(f)
        self.end_event = next(e for e in self.chap['events']
                              if e.get('trigger') == 'chapter_end')

    # ── the no-Lupin branch ────────────────────────────────────────────────────
    def test_the_no_parley_path_has_a_speaker_for_every_box(self):
        """The reason this branch exists: a player can clear ch04 having killed the pack,
        and then two of the ending's three boxes have no speaker -- including the chapter's
        closing button. Every box must be voiced on BOTH paths (#24 checklist)."""
        _, beats = inject.scenes._split_event_beats(self.chap, 'chapter_end', 'end',
                                         (inject.chapter_ids.CH04_ENDING_MSG,), card_required=False)
        locked = beats[0]
        fallback = inject.scenes.variant_beat(locked, self.end_event['no_lupin_fallback'], 'test')
        self.assertEqual(len(fallback), len(locked))
        for i, box in enumerate(fallback, 1):
            (speaker, text), = box.items()
            self.assertTrue(speaker and text.strip(), 'box %d has no speaker/text' % i)
        self.assertNotIn('lupin', [next(iter(b)) for b in fallback],
                         'the no-parley path must never put Lupin on stage')

    def test_the_unchanged_box_rides_through_both_branches(self):
        """Only boxes 1 and 3 are replaced; Marty's box 2 is the same line on both paths."""
        _, beats = inject.scenes._split_event_beats(self.chap, 'chapter_end', 'end',
                                         (inject.chapter_ids.CH04_ENDING_MSG,), card_required=False)
        fallback = inject.scenes.variant_beat(beats[0], self.end_event['no_lupin_fallback'], 'test')
        self.assertEqual(beats[0][1], fallback[1])
        self.assertEqual(next(iter(fallback[1])), 'marty')

    def test_a_drifted_anchor_fails_loudly_instead_of_mis_swapping(self):
        """`replaces:` anchors exist so a re-ordered locked script cannot silently swap the
        wrong box. Reversing the scene must abort, not quietly produce nonsense."""
        _, beats = inject.scenes._split_event_beats(self.chap, 'chapter_end', 'end',
                                         (inject.chapter_ids.CH04_ENDING_MSG,), card_required=False)
        with self.assertRaises(SystemExit):
            inject.scenes.variant_beat(list(reversed(beats[0])),
                            self.end_event['no_lupin_fallback'], 'test')

    def test_the_fallback_declaration_is_internally_consistent(self):
        fb = self.end_event['no_lupin_fallback']
        self.assertEqual(len(fb['boxes']), len(fb['replaces']))
        self.assertEqual(len(fb['boxes']), len(fb['script']))

    def test_the_branch_emits_both_arms_and_converges(self):
        """branch_on_flag is the vanilla ch19a idiom: CHECK_EVENTID -> BEQ to the fallback
        arm, the set-arm GOTOs past it, and both converge on a shared LABEL."""
        c = inject.scenes.branch_on_flag('EVFLAG_TMP(9)', '    SET\n', '    CLEAR\n')
        self.assertIn('CHECK_EVENTID(EVFLAG_TMP(9))', c)
        self.assertIn('BEQ(0x0, EVT_SLOT_C, EVT_SLOT_0)', c)
        self.assertLess(c.index('SET'), c.index('LABEL(0x0)'))
        self.assertLess(c.index('LABEL(0x0)'), c.index('CLEAR'))
        self.assertLess(c.index('CLEAR'), c.index('LABEL(0x1)'))
        # label_base keeps concurrent branches from colliding
        self.assertIn('LABEL(0x4)', inject.scenes.branch_on_flag('F', '', '', label_base=4))

    # ── #198 review guards ─────────────────────────────────────────────────────
    def test_every_hosted_chapter_declares_its_own_goal_ids(self):
        """#207: the goal window + status-objective strings are message ids like any other, but
        they arrive by INHERITANCE -- `_retarget_host_chapter` copies a donor slot's goal
        wholesale. ch04's donor is ch02's host slot, which inject_ch02 has already rewritten, so
        ch04 inherited ch02's ids and the two wrote over each other (last injector wins).
        Declaring them makes the existing uniqueness guard binding."""
        pairs = {'ch01': (inject.chapter_ids.CH01_GOAL_WINDOW_MSG, inject.chapter_ids.CH01_GOAL_STATUS_MSG),
                 'ch02': (inject.chapter_ids.CH02_GOAL_WINDOW_MSG, inject.chapter_ids.CH02_GOAL_STATUS_MSG),
                 'ch03': (inject.chapter_ids.CH03_GOAL_WINDOW_MSG, inject.chapter_ids.CH03_GOAL_STATUS_MSG),
                 'ch04': (inject.chapter_ids.CH04_GOAL_WINDOW_MSG, inject.chapter_ids.CH04_GOAL_STATUS_MSG)}
        flat = [mid for ids in pairs.values() for mid in ids]
        self.assertEqual(len(flat), len(set(flat)),
                         'two hosted chapters share a goal id: %s' % pairs)

    def test_the_goal_ids_are_registered_so_the_guard_binds(self):
        owner = inject.messages.assert_message_ids_unique()
        self.assertEqual('ch04', owner[inject.chapter_ids.CH04_GOAL_WINDOW_MSG])
        self.assertEqual('ch04', owner[inject.chapter_ids.CH04_GOAL_STATUS_MSG])

    def test_ch04_takes_its_goal_ids_from_the_block_it_owns(self):
        """ch04 hosts on slot 5, so it owns vanilla Ch5's dead 0x9BA-0x9CC block. Its goal ids
        must come from THERE, not from whatever its donor slot happened to hold."""
        for mid in (inject.chapter_ids.CH04_GOAL_WINDOW_MSG, inject.chapter_ids.CH04_GOAL_STATUS_MSG):
            self.assertTrue(0x9BA <= mid <= 0x9CC,
                            'ch04 goal id 0x%X is outside its host block' % mid)

    def test_two_chapters_sharing_a_goal_id_fail_the_build(self):
        with self.assertRaises(SystemExit):
            inject.messages.assert_message_ids_unique({'ch02': (inject.chapter_ids.CH02_GOAL_WINDOW_MSG,),
                                          'ch04': (inject.chapter_ids.CH02_GOAL_WINDOW_MSG,)})

    def test_hosted_chapters_do_not_share_message_ids(self):
        owner = inject.messages.assert_message_ids_unique()
        self.assertEqual(owner[inject.chapter_ids.CH04_ENDING_MSG], 'ch04')
        # ch04 owns vanilla Ch5's block because it is hosted on slot 5
        for mid in inject.messages.HOSTED_CHAPTER_MESSAGE_IDS['ch04']:
            self.assertTrue(0x9BA <= mid <= 0x9CC, 'ch04 id 0x%X is outside its host block' % mid)

    def test_a_double_claimed_message_id_fails_the_build(self):
        """The failure this guard exists for: verify_text checks runaway text, not slot
        ownership, so a second writer overwrites the first and the build stays green."""
        with self.assertRaises(SystemExit):
            inject.messages.assert_message_ids_unique({'ch04': (0x9BB,), 'ch05': (0x9BB,)})

    def test_the_shipped_pack_pids_are_the_packs_alone(self):
        inject.chapters.ch04.assert_pack_pids_addressable(self.chap, inject.chapters.ch04.CH04_PACK_PIDS)

    def test_a_pack_pid_reused_by_another_wave_is_rejected(self):
        """CUSN converts the FIRST unit matching a pid, so a pack pid shared with another wave
        would turn one of ITS units green on Marty's parley -- with the difficulty read still
        looking correct."""
        with self.assertRaises(SystemExit):
            inject.chapters.ch04.assert_pack_pids_addressable(
                self.chap, inject.chapters.ch04.CH04_PACK_PIDS[:-1] + (inject.chapters.ch04.CH04_MONSTER_PIDS['revenant'],))

    def test_two_wolves_sharing_a_pid_is_rejected(self):
        """The defect this replaces (#203): a repeated pid is unaddressable -- the second CUSN
        re-finds the wolf the first one already turned green."""
        dupe = (inject.chapters.ch04.CH04_PACK_PIDS[0],) + inject.chapters.ch04.CH04_PACK_PIDS[:-1]
        with self.assertRaises(SystemExit):
            inject.chapters.ch04.assert_pack_pids_addressable(self.chap, dupe)

    def test_a_pack_pid_colliding_with_the_moose_is_rejected(self):
        """The moose is a scripted neutral its own DISA targets; a pack pid landing on it
        would parley the quarry."""
        with self.assertRaises(SystemExit):
            inject.chapters.ch04.assert_pack_pids_addressable(
                self.chap, inject.chapters.ch04.CH04_PACK_PIDS[:-1] + (inject.chapter_ids.CH04_MOOSE_PID,))

    # ── the moose beat ─────────────────────────────────────────────────────────
    def test_the_moose_is_loaded_shown_and_removed_in_one_beat(self):
        """It is uncatchable by design: it must never be left on the map to be attacked."""
        s = inject.chapters.ch04.ch04_moose_script(
            'UnitDef_X', '0xce', 0x9C0, (7, 4), ((9, 7), (9, 8), (14, 14)))
        self.assertLess(s.index('LOAD1(0x1, UnitDef_X)'), s.index('TEXTSHOW(0x9C0)'))
        self.assertLess(s.index('TEXTSHOW(0x9C0)'), s.index('MOVE_DEFINED(0xce)'))
        self.assertLess(s.index('MOVE_DEFINED(0xce)'), s.index('DISA(0xce)'))
        self.assertTrue(s.rstrip().endswith('ENDA\n}'))

    def test_the_moose_camera_stays_at_map_origin_not_centered_on_the_moose(self):
        """A 15-tile map fills the viewport; centering on x=11 exposes wrapped map memory."""
        s = inject.chapters.ch04.ch04_moose_script(
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
        row = next(r for r in inject.cast.SCRIPTED_NEUTRAL_SPRITES if r[0] == 'white-moose')
        _uid, char_ids, donor = row
        self.assertEqual('Gwyllgi', donor, 'the wait-row GEOMETRY donor, not the sprite')
        self.assertIn(inject.chapter_ids.CH04_MOOSE_PID, char_ids)
        self.assertIn(inject.chapter_ids.CH05_MOOSE_PID, char_ids)
        self.assertNotEqual(inject.chapter_ids.CH04_MOOSE_PID, inject.chapter_ids.CH05_MOOSE_PID, 'pids are per-chapter')

    def test_a_pid_that_wears_no_custom_art_fails_the_BUILD(self):
        """The per-PID half of the guard. `assert_declared_map_sprites_injected` asks whether an
        ASSET reached a sprite table -- the moose's had, under ch04's pid -- so it could not see
        a second chapter staging the same creature under a pid nothing dressed."""
        inject.recruit.assert_custom_art_pid_wired(inject.chapter_ids.CH04_MOOSE_PID, 'white-moose', 'test')
        inject.recruit.assert_custom_art_pid_wired(inject.chapter_ids.CH05_MOOSE_PID, 'white-moose', 'test')
        with self.assertRaises(SystemExit):
            inject.recruit.assert_custom_art_pid_wired('0x7f', 'white-moose', 'test')
        with self.assertRaises(SystemExit):      # asset in no row at all
            inject.recruit.assert_custom_art_pid_wired(inject.chapter_ids.CH04_MOOSE_PID, 'not-a-creature', 'test')

    def test_both_chapters_actually_CALL_the_pid_guard(self):
        """A guard nothing calls is a comment. Both injectors run it on their own pid."""
        src = injector.injector_source()
        for pid in ('CH04_MOOSE_PID', 'CH05_MOOSE_PID'):
            self.assertIn("assert_custom_art_pid_wired(%s, 'white-moose'" % pid, src)

    def test_one_asset_claims_one_sheet_pair_and_one_sms_slot(self):
        """Two pids are two override ROWS, not two sprites: the sheets and the SMS id are
        claimed once per asset, so a chapter reusing a creature costs table space and nothing
        else. Asserted on the injector's shape, since the tables only exist post-build."""
        body = injector.def_source('_inject_scripted_neutral_sprites')
        self.assertEqual(1, body.count('sms = claim_sms_id()'))
        self.assertLess(body.index('sms = claim_sms_id()'), body.index('for char_id in char_ids:'))

    def test_the_moose_uses_a_continuous_regular_move_queue_over_the_bridge(self):
        """The route is authored: normal movement crosses the bridge before leaving southeast."""
        route = ((9, 7), (9, 8), (14, 14))
        s = inject.chapters.ch04.ch04_moose_script('UnitDef_X', '0xce', 0x9C0, (7, 4), route)
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
        s = inject.chapters.ch04.ch04_moose_script(
            'UnitDef_X', '0xce', 0x9C0, (7, 4), ((9, 7), (9, 8), (14, 14)))
        self.assertIn('SVAL(EVT_SLOT_2, FACTION_ID_BLUE)', s)
        self.assertLess(s.index('CALL(EventScr_UnTriggerIfNotFaction)'),
                        s.index('LOAD1(0x1, UnitDef_X)'))

    def test_the_moose_can_actually_walk_to_the_tile_it_flees_to(self):
        """A scripted MOVE to an unwalkable tile never returns -- the event engine waits on a
        path that does not exist and the chapter hangs. The authored flee tile must be inside
        the region the moose can reach from its own clearing."""
        maps = os.path.join(inject.decomp.REPO, 'campaigns', 'rime-of-the-frostmaiden', 'maps')
        _, _, terrain = inject.terrain._map_terrain_grid(maps, inject.chapters.ch04.CH04_LAYOUT[1])
        costs = inject.terrain._class_terrain_move_costs(inject.chapter_ids.CH04_MOOSE_MOV_TABLE)
        reachable = inject.terrain.reachable_tiles(terrain, costs, inject.chapters.ch04.CH04_MOOSE_POS)
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
        maps = os.path.join(inject.decomp.REPO, 'campaigns', 'rime-of-the-frostmaiden', 'maps')
        _, _, terrain = inject.terrain._map_terrain_grid(maps, inject.chapters.ch04.CH04_LAYOUT[1])
        costs = inject.terrain._class_terrain_move_costs(inject.chapter_ids.CH04_MOOSE_MOV_TABLE)
        self.assertGreater(costs[terrain[0][14]], 0, 'the NE corner is walkable terrain')
        self.assertNotIn((14, 0), inject.terrain.reachable_tiles(terrain, costs, inject.chapters.ch04.CH04_MOOSE_POS))

    def test_the_moose_never_speaks(self):
        """Locked as a mute white ghost in ch04, re-locked in ch05: the only voice in the
        beat is the party's."""
        _, beats = inject.scenes._split_event_beats(self.chap, 'moose_sighted', 'moose',
                                         (inject.chapter_ids.CH04_MOOSE_MSG,), card_required=False)
        speakers = [next(iter(b)) for b in beats[0]]
        self.assertNotIn('white-moose', speakers)
        self.assertNotIn('moose', speakers)


if __name__ == '__main__':
    unittest.main()
