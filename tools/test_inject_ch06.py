#!/usr/bin/env python3
"""Tests for tools/inject/chapters/ch06.py.

Run:  python3 tools/test_inject_ch06.py
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inject.cast
import inject.chapter_ids
import inject.chapters.ch06
import inject.map_sprites
import inject.maps
import inject.recruit
import inject.text
import inject.villages
import inject.decomp
import inject.hosting
import inject.terrain
import inject.units
from inject import source as injector  # the injector's source, every file of it (#389)


class ItemDropIsCarriedOnce(unittest.TestCase):
    """FE8 drops the LAST item, and a chapter YAML may name the drop in `inventory:` too.

    ch06 is the first chapter whose data spells it both ways; appending unconditionally emitted a
    second copy on three units while `make difficulty` still read PARITY, because the parity model
    prices the YAML rather than the rows the injector emits.
    """

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_a_drop_already_in_inventory_is_not_duplicated(self):
        self.assertEqual(inject.units._items_with_drop_last(['A', 'B'], 'B'), ['A', 'B'])

    def test_a_drop_absent_from_inventory_is_appended(self):
        self.assertEqual(inject.units._items_with_drop_last(['A'], 'B'), ['A', 'B'])

    def test_a_drop_listed_first_is_moved_LAST(self):
        # De-duplicating alone would leave the engine dropping the wrong item.
        self.assertEqual(inject.units._items_with_drop_last(['B', 'A'], 'B'), ['A', 'B'])

    def test_no_ch06_enemy_carries_a_duplicate(self):
        chap = inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapters.ch06.CH06_CHAPTER_YAML)
        rows = inject.chapters.ch06.ch06_enemy_rows(chap) + inject.chapters.ch06.ch06_enemy_rows(
            chap, arrives_turn=inject.chapters.ch06.CH06_HARD_WAVE_TURN)
        for row in rows:
            items = re.search(r'\.items = \{ (.*?) \}', row).group(1).split(', ')
            items = [i for i in items if i != '0']
            self.assertEqual(len(items), len(set(items)), row)

    def test_every_dropper_matches_its_vanilla_donors_item_count(self):
        """The check that would have caught it: our row against the donor unit it is derived
        from. Vanilla's three ch06 droppers carry 2 / 1 / 2 items; ADR 0329's re-classed
        Mercenary carries one more, the Steel Lance it now fights with, ahead of the drop."""
        chap = inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapters.ch06.CH06_CHAPTER_YAML)
        expected = {'shark-rider-halberd': 2, 'merfolk-trident-drop': 2, 'lamia-mender': 2}
        rows = inject.chapters.ch06.ch06_enemy_rows(chap)
        for enemy_id, count in expected.items():
            row = next(r for r in rows if '/* %s --' % enemy_id in r)
            items = re.search(r'\.items = \{ (.*?) \}', row).group(1).split(', ')
            self.assertEqual(len(items), count, '%s: %s' % (enemy_id, row))
            self.assertIn('.itemDrop = 1', row, enemy_id)


class MessieWearsHisOwnArt(unittest.TestCase):
    """Messie is a cutscene actor, not cast, so `classed_cast` never sees him. He rides the
    scripted-neutral path the white moose does: a raw pid of his own, wearing his own sheet."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_his_pid_wears_his_map_sprite(self):
        inject.recruit.assert_custom_art_pid_wired(inject.chapter_ids.CH06_MESSIE_PID, 'messie', 'test')

    def test_his_pid_is_named_messie_and_wears_the_syrene_bust(self):
        """Read Syrene's portraitId out of the decomp, never a literal: the bust the build
        dresses is Syrene's slot, so his on-map unit must point at that same face."""
        unit_id, slot, portrait_id, name = inject.cast.RAW_PID_PORTRAITS[
            inject.chapter_ids.CH06_MESSIE_PID]
        self.assertEqual(('messie', 'Messie'), (unit_id, name))
        self.assertEqual(inject.cast.GUEST_PORTRAIT_MAP['messie'], slot)
        with open(os.path.join(inject.decomp.REPO, 'fireemblem8u', 'src', 'data_characters.c'),
                  encoding='utf-8') as f:
            src = f.read()
        row = src[src.index('[CHARACTER_SYRENE - 1]'):]
        row = row[:row.index('},')]
        self.assertEqual(int(re.search(r'\.portraitId = (0x[0-9a-fA-F]+)', row).group(1), 16),
                         portrait_id)

    def test_the_build_guard_sees_his_declared_art(self):
        """A cutscene actor's `art.map_sprite` block is in scope of the "declared art must be
        wired" guard, or his sheet could fall out of the tables and nothing would say so."""
        declared = inject.map_sprites.declared_map_sprite_units(self.CAMPAIGN)
        self.assertIn('messie', declared)

    def test_a_neutral_with_no_committed_walk_gets_the_glide(self):
        """Messie hauls himself onto the ice, so he moves; a neutral with no hand-drawn walk
        sheet glides on its idle the way the cast do, instead of failing the build."""
        body = injector.def_source('_inject_scripted_neutral_sprites')
        self.assertIn('synth_mu_sheet', body)


class Opening(unittest.TestCase):
    """The locked chapter_start script, wired: beat A over backdrops, beat B on the ice (#26)."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    @classmethod
    def setUpClass(cls):
        cls.chap = inject.hosting._load_chapter_yaml(cls.CAMPAIGN, inject.chapters.ch06.CH06_CHAPTER_YAML)

    def test_the_script_splits_into_hall_ice_and_quip(self):
        card, beats = inject.chapters.ch06.ch06_opening_beats(self.chap)
        self.assertEqual(card, 'Bremen')
        self.assertEqual([inject.text._script_box_count(b) for b in beats], [24, 7, 1])
        self.assertEqual(list(beats[2][0]), ['meesmickle'])

    def test_every_speaker_has_a_seat(self):
        _card, (hall, ice, quip) = inject.chapters.ch06.ch06_opening_beats(self.chap)
        speakers = lambda beat: {k for e in beat for k in e
                                 if k not in inject.text.SCRIPT_DIRECTIVES}
        self.assertLessEqual(speakers(hall), set(inject.chapters.ch06.CH06_OPENING_HOME))
        self.assertLessEqual(speakers(ice) | speakers(quip),
                             set(inject.chapters.ch06.CH06_OPENING_ICE_SEATS))

    def test_the_merfolk_load_in_beat_B_after_the_pan(self):
        """They surface on screen, so they cannot be on the map at prep, and they must arrive
        between the two halves of beat B -- after the camera reaches the lake, before the quip."""
        block = inject.chapters.ch06.ch06_opening_ice_block((7, 1), (10, 12))
        line = 'LOAD1(0x1, %s)' % inject.chapters.ch06.CH06_LINE_TABLE
        ice = 'Text(0x%X)' % inject.chapter_ids.CH06_OPENING_MSGS[1]
        quip = 'Text(0x%X)' % inject.chapter_ids.CH06_OPENING_QUIP_MSG
        self.assertLess(block.index(ice), block.index('CAMERA(10, 12)'))
        self.assertLess(block.index('CAMERA(10, 12)'), block.index(line))
        self.assertLess(block.index(line), block.index(quip))
        with open(inject.chapters.ch06.__file__, encoding='utf-8') as f:
            src = f.read()
        beginning = src[src.index("beginning = ('{"):]
        before_prep = beginning[:beginning.index('CALL(%s)')]
        self.assertNotIn('CH06_LINE_TABLE', before_prep,
                         'the merfolk line is LOADed before prep again')

    def test_the_lake_shot_is_the_boss_tile(self):
        self.assertEqual(inject.chapters.ch06.ch06_lake_camera_tile(self.chap), (10, 12))


class MessieOnTheIce(unittest.TestCase):
    """The boss_defeated scene (#26): Kyogre's awakening, then the locked script."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    @classmethod
    def setUpClass(cls):
        cls.chap = inject.hosting._load_chapter_yaml(cls.CAMPAIGN, inject.chapters.ch06.CH06_CHAPTER_YAML)
        cls.terrain = inject.terrain._map_terrain_grid(
            os.path.join(inject.decomp.REPO, 'campaigns', cls.CAMPAIGN, 'maps'),
            inject.chapters.ch06.CH06_LAYOUT[1])[2]

    def test_he_surfaces_in_water_and_hauls_onto_nerras_tile(self):
        surface, target = inject.chapters.ch06.ch06_messie_route(self.chap, self.terrain)
        self.assertEqual(target, inject.chapters.ch06.ch06_lake_camera_tile(self.chap))
        self.assertEqual(inject.chapters.ch06.TERRAIN_RIVER, self.terrain[surface[1]][surface[0]])

    def test_a_route_he_cannot_walk_is_refused(self):
        """An unwalkable event MOVE hangs the chapter, so the build refuses it first. Judged by
        the Gwyllgi's own cost row: it wades a river (cost 5) but not an outcrop (TILE_2E)."""
        (sx, sy), (tx, ty) = inject.chapters.ch06.ch06_messie_route(self.chap, self.terrain)
        blocked = [row[:] for row in self.terrain]
        blocked[sy + (ty > sy) - (ty < sy)][sx + (tx > sx) - (tx < sx)] = 0x2E   # his first step
        with self.assertRaises(SystemExit):
            inject.chapters.ch06.ch06_messie_route(self.chap, blocked)

    def test_a_surface_on_dry_ice_is_refused(self):
        chap = dict(self.chap, messie=dict(self.chap['messie'], surfaces=[9, 12]))
        with self.assertRaises(SystemExit):
            inject.chapters.ch06.ch06_messie_route(chap, self.terrain)

    def test_he_comes_from_the_north_in_steps_that_shake_and_breaks_the_ice_first(self):
        """Kyogre's discrete steps, each shaking the map (Nicolas, 2026-10-09), and the bay
        breaks before he steps onto it. Every rumble ends before the cry: EARTHQUAKE_END fades
        the SE channel."""
        block = inject.chapters.ch06.ch06_messie_block(self.chap, self.terrain)
        surface, target = inject.chapters.ch06.ch06_messie_route(self.chap, self.terrain)
        self.assertEqual(surface[0], target[0])
        self.assertLess(surface[1], target[1], 'he comes from the north')
        steps = block.count('MOVE_1STEP(')
        self.assertEqual(target[1] - surface[1], steps)
        self.assertEqual(steps + 1, block.count('EARTHQUAKE_START'))   # each step + the break
        self.assertNotIn('MOVE_CLOSEST(', block)                       # no slow slide
        moves = [i for i in range(len(block)) if block.startswith('MOVE_1STEP(', i)]
        brk = block.index('TILECHANGE(%d)' % inject.chapters.ch06.CH06_MESSIE_BREAK_ID)
        self.assertTrue(any(m < brk for m in moves) and any(m > brk for m in moves))
        self.assertLess(block.rindex('EARTHQUAKE_END'), block.index('SOUN(SONG_MS_KYOGRE_CRY)'))
        self.assertLess(block.index('SOUN('), block.index('Text(0x%X)' % inject.chapter_ids.CH06_MESSIE_MSG))

    def test_the_bay_is_water_and_changes_nothing_else(self):
        maps = os.path.join(inject.decomp.REPO, 'campaigns', self.CAMPAIGN, 'maps')
        (x0, y0, w, h, tiles, _why), = inject.chapters.ch06.ch06_messie_bay(self.chap, maps)
        bay = {(x, y): m for x, y, m in self.chap['messie']['bay']}
        for i, m in enumerate(tiles):
            x, y = x0 + i % w, y0 + i // w
            want = bay.get((x, y), inject.maps._read_map_metatile(maps, inject.chapters.ch06.CH06_LAYOUT[1], x, y))
            self.assertEqual(want, m, (x, y))
        island = inject.chapters.ch06.ch06_center_island(self.terrain, (10, 12))
        self.assertTrue({xy for xy in bay if xy in island}, 'the bay cuts into the island')

    def test_the_scene_is_one_message_with_every_speaker_seated(self):
        (msg, body), = inject.chapters.ch06.ch06_messie_messages(self.chap)
        self.assertEqual(inject.chapter_ids.CH06_MESSIE_MSG, msg)
        ev = next(e for e in self.chap['events'] if e['trigger'] == 'boss_defeated')
        speakers = {k for e in ev['script'] for k in e if k not in inject.text.SCRIPT_DIRECTIVES}
        self.assertLessEqual(speakers, set(inject.chapters.ch06.CH06_MESSIE_SEATS))

    def test_he_takes_the_centre_island_alone_and_the_whole_cast_rings_it(self):
        """Nicolas, 2026-10-09: Messie alone on the centre island, every PC around it."""
        block, tiles = inject.chapters.ch06.ch06_messie_gather(self.chap, self.terrain)
        island = inject.chapters.ch06.ch06_center_island(self.terrain, (10, 12))
        self.assertEqual({(9, 11), (10, 11), (11, 11), (9, 12), (10, 12), (10, 13)}, island)
        self.assertFalse(set(tiles.values()) & island)
        cast, _ = inject.cast._classed_cast(self.CAMPAIGN, available_at=6)
        self.assertEqual({row[0] for row in cast}, set(tiles))
        self.assertNotRegex(block, r'MOVE\w*\(\w+, CHARACTER_')   # LOADed, never MOVEd (ADR 0292)
        first_load = block.index('LOAD1(')
        for x, y in island:
            self.assertIn('_EvtParams2(%d, %d)' % (x, y), block[:first_load])

    def test_nobody_outside_the_army_is_loaded_into_it(self):
        """A LOAD of someone not in the army CREATES them (review, #470): every member is
        LOADed behind its own CHECK_EXISTS, so a Sahnar never turned stays away."""
        block, tiles = inject.chapters.ch06.ch06_messie_gather(self.chap, self.terrain)
        self.assertEqual(len(tiles), block.count('CHECK_EXISTS('))
        self.assertEqual(len(tiles), block.count('LOAD1('))
        for uid in tiles:
            check = 'CHECK_EXISTS(CHARACTER_%s)' % inject.cast.PORTRAIT_MAP[uid].upper()
            self.assertIn(check, block, uid)

    def test_a_spare_beside_the_scene_is_refused(self):
        """MOVE_CLOSEST drops the cleared on the free cell nearest the spare (review, #470)."""
        gather = dict(self.chap['messie']['gather'], spare=[6, 12])
        chap = dict(self.chap, messie=dict(self.chap['messie'], gather=gather))
        with self.assertRaises(SystemExit):
            inject.chapters.ch06.ch06_messie_gather(chap, self.terrain)

    def test_a_cast_member_on_his_island_is_refused(self):
        gather = dict(self.chap['messie']['gather'], braulo=[10, 11])
        chap = dict(self.chap, messie=dict(self.chap['messie'], gather=gather))
        with self.assertRaises(SystemExit):
            inject.chapters.ch06.ch06_messie_gather(chap, self.terrain)

    def test_the_scene_plays_before_the_victory_sting(self):
        with open(inject.chapters.ch06.__file__, encoding='utf-8') as f:
            src = f.read()
        self.assertLess(src.index('ch06_messie_block(chap, terrain)'), src.index("MUSC(SONG_VICTORY)"))


class MerfolkSurface(unittest.TestCase):
    """Beat B: the line LOADs on the channels and walks to its YAML posts (#26)."""

    CAMPAIGN = 'rime-of-the-frostmaiden'
    W, L = 0x10, 0x01   # TERRAIN_RIVER, TERRAIN_PLAINS
    COSTS = {0x10: -1, 0x01: 1}

    def costs(self):
        row = [-1] * 0x40
        for terrain, cost in self.COSTS.items():
            row[terrain] = cost
        return row

    def test_the_nearest_water_at_least_two_steps_out_wins(self):
        W, L = self.W, self.L
        terrain = [[W, L, L, L],
                   [L, L, L, W]]
        out = inject.chapters.ch06.surface_spawns(terrain, [('a', (2, 0), self.costs())])
        # Both waters are two steps out ((0,0) via (1,0); (3,1) via (3,0)). Ties break on the
        # tile, so the pick is deterministic.
        self.assertEqual(out['a'], (0, 0))

    def test_a_spawn_is_never_shared(self):
        W, L = self.W, self.L
        terrain = [[W, L, L, L, L]]
        out = inject.chapters.ch06.surface_spawns(
            terrain, [('a', (2, 0), self.costs()), ('b', (3, 0), self.costs())])
        self.assertEqual(out['a'], (0, 0))
        self.assertIsNone(out['b'])     # the only water is taken: b appears where it stands

    def test_water_is_never_walked_THROUGH(self):
        W, L = self.W, self.L
        terrain = [[L, W, W, L]]        # (0,0) is cut off from (3,0) by two channel tiles
        out = inject.chapters.ch06.surface_spawns(terrain, [('a', (3, 0), self.costs())])
        self.assertEqual(out['a'], (2, 0))

    def test_every_line_unit_surfaces_and_walks_to_its_post(self):
        chap = inject.hosting._load_chapter_yaml(self.CAMPAIGN, inject.chapters.ch06.CH06_CHAPTER_YAML)
        maps = os.path.join(inject.decomp.REPO, 'campaigns', self.CAMPAIGN, 'maps')
        spawns = inject.chapters.ch06.ch06_line_spawns(chap, maps)
        self.assertTrue(spawns)
        self.assertEqual([k for k, v in spawns.items() if v is None], [])
        rows = inject.chapters.ch06.ch06_enemy_rows(chap, spawns=spawns)
        self.assertTrue(all('.redaCount = 1,' in r for r in rows))
        # ...and the Difficult wave is untouched: it arrives on turn 4, by its own road.
        wave = inject.chapters.ch06.ch06_enemy_rows(chap, arrives_turn=4)
        self.assertTrue(all('.redaCount = 0,' in r for r in wave))


class BoardingPass(unittest.TestCase):
    """vanilla Ch6's village in a hull: any party member Talks a boat, the crew speaks, the
    east hull pays the Antitoxin, and the ending pays the Orion's Bolt only if both float."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    @classmethod
    def setUpClass(cls):
        cls.chap = inject.hosting._load_chapter_yaml(cls.CAMPAIGN, inject.chapters.ch06.CH06_CHAPTER_YAML)
        cls.events, cls.scripts, cls.messages = inject.chapters.ch06.ch06_boarding_wiring(
            cls.CAMPAIGN, cls.chap)
        cls.boarders = inject.recruit.talk_recruiters(cls.CAMPAIGN, cls.chap['chapter_number'])

    def test_every_boarder_can_board_every_boat_and_a_boat_has_one_flag(self):
        ids = inject.chapter_ids
        for bid, pid in ids.CH06_BOAT_PIDS.items():
            rows = re.findall(r'CHAR\(([^,]+), %s, (\w+), %s\)'
                              % (ids.CH06_BOAT_TALK_SCRIPTS[bid], pid), self.events)
            self.assertEqual(sorted(self.boarders), sorted(r[1] for r in rows), bid)
            self.assertEqual({ids.CH06_BOAT_TALK_FLAGS[bid]}, {r[0] for r in rows}, bid)
        self.assertNotEqual(*ids.CH06_BOAT_TALK_FLAGS.values())

    def test_the_east_hull_gives_the_antitoxin_and_the_west_gives_its_line(self):
        scripts = {s: b for s, b, _c in self.scripts}
        ids = inject.chapter_ids
        east, west = (scripts[ids.CH06_BOAT_TALK_SCRIPTS[b]] for b in ('boat-east', 'boat-west'))
        self.assertIn('SVAL(EVT_SLOT_3, ITEM_ANTITOXIN)', east)
        self.assertNotIn('GIVEITEMTO', west)
        for body in (east, west):
            self.assertIn('Text_BG(BG_SHIP,', body)

    def test_each_authored_line_is_its_own_box_under_its_crews_face(self):
        msgs = dict(self.messages)
        for boat in self.chap['rescue_boats']:
            body = msgs[inject.chapter_ids.CH06_BOAT_TALK_MSGS[boat['id']]]
            self.assertIn('[%s]' % boat['talk']['face'], body)
            self.assertEqual(len(boat['talk']['text']), body.count('[A]'), boat['id'])

    def test_the_save_both_payout_asks_whether_each_hull_is_alive(self):
        body = inject.villages.save_all_bonus_script(inject.chapter_ids.CH06_BOAT_PIDS,
                                                     'ITEM_ORIONSBOLT', check='CHECK_ALIVE')
        for pid in inject.chapter_ids.CH06_BOAT_PIDS.values():
            self.assertIn('CHECK_ALIVE(%s)' % pid, body)
        self.assertLess(body.rindex('BEQ('), body.index('ITEM_ORIONSBOLT'))
        with self.assertRaises(SystemExit):
            inject.villages.save_all_bonus_script({}, 'ITEM_ORIONSBOLT', check='CHECK_FLAG')


if __name__ == '__main__':
    unittest.main()
