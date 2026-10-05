#!/usr/bin/env python3
"""Tests for tools/inject/battle_anims.py.

Run:  python3 tools/test_inject_battle_anims.py
"""
import json
import os
import re
import sys
import tempfile
import unittest

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_campaign as bc
import inject.battle_anims
import inject.cast
import inject.chapter_ids
import inject.decomp
import inject.hosting
import inject.raw_pids
import inject.reskins
import inject.test_chapter
import inject.text
from inject.engine_patches import patched_text, vanilla_banim_count
from inject import source as injector  # the injector's source, every file of it (#389)


class BattleAnimPalette(unittest.TestCase):
    def test_opaque_black_gets_a_nontransparent_palette_index(self):
        frame = Image.new('RGBA', (8, 8), (0, 0, 0, 255))
        palette = inject.battle_anims._banim_palette([frame])
        self.assertEqual(palette[0], (0, 0, 0))
        self.assertEqual(palette[1], (0, 0, 0))


class BattleAnimInjection(unittest.TestCase):
    """Pure transforms behind the faked-battle-anim injection (#65 M-A)."""

    BANIM = ('struct BattleAnim banim_data[] = {\n'
             '\t{"arcm_ar1", &banim_arcm_ar1_modes_bin, &banim_arcm_ar1_motion_o, '
             '&banim_arcm_ar1_oam_r_bin, &banim_arcm_ar1_oam_l_bin, &banim_arcm_ar1_agbpal}, // 0x25\n'
             '\t{"arcm_ar1", &banim_arcm_ar1_2_modes_bin, &banim_arcm_ar1_2_motion_o, '
             '&banim_arcm_ar1_2_oam_r_bin, &banim_arcm_ar1_2_oam_l_bin, &banim_arcm_ar1_2_agbpal}, // 0x26\n'
             '};\n')

    def test_append_row_grows_by_one_and_returns_the_new_id(self):
        new, anim_id = inject.battle_anims.banim_append_row(self.BANIM, 'rbg_ar1')
        self.assertEqual(anim_id, 2)                                  # 2 rows -> id 0x2
        self.assertEqual(new.count('\t{"'), 3)                        # grew by exactly one
        self.assertIn('{"rbg_ar1", &banim_rbg_ar1_modes_bin, &banim_rbg_ar1_motion_o, '
                      '&banim_rbg_ar1_oam_r_bin, &banim_rbg_ar1_oam_l_bin, '
                      '&banim_rbg_ar1_agbpal}', new)

    def test_append_row_leaves_the_donor_rows_byte_unchanged(self):
        new, _ = inject.battle_anims.banim_append_row(self.BANIM, 'rbg_ar1')
        for donor in ('arcm_ar1_modes_bin', 'arcm_ar1_2_modes_bin'):
            self.assertEqual(new.count(donor), self.BANIM.count(donor))  # additive only
        self.assertLess(new.index('};'), len(new))                       # still closed

    def test_repoint_conf_changes_only_the_matched_weapon_index(self):
        conf = ('CONST_DATA struct BattleAnimDef AnimConf_088AF150[] = {\n'
                '    { .wtype = 0x0100 | ITYPE_BOW, .index = 0x0026, },\n'
                '    { .wtype = 0x0100 | ITYPE_ITEM, .index = 0x0027, },\n'
                '    { 0 }\n};\n')
        new = inject.battle_anims.banim_repoint_conf(conf, 'AnimConf_088AF150', '0x0100 | ITYPE_BOW', 0xC9)
        self.assertIn('.wtype = 0x0100 | ITYPE_BOW, .index = 0xC9', new)
        self.assertIn('.wtype = 0x0100 | ITYPE_ITEM, .index = 0x0027', new)  # untouched

    def test_clone_conf_appends_a_private_copy_and_leaves_the_donor_vanilla(self):
        conf = ('CONST_DATA struct BattleAnimDef AnimConf_088AF150[] = {\n'
                '    { .wtype = 0x0100 | ITYPE_BOW, .index = 0x0026, },\n'
                '    { 0 }\n};\n')
        new = inject.battle_anims.banim_clone_conf(conf, 'AnimConf_088AF150', 'AnimConf_rbg_ar1',
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
        new = inject.reskins.set_class_field_symbol(text, 'CLASS_A', 'pBattleAnimDef', 'AnimConf_new')
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
        donor_class, wtype, motion, cadence = inject.battle_anims.BANIM_DONORS['knight']
        self.assertEqual(donor_class, 'CLASS_ARMOR_KNIGHT')
        self.assertIn('ITYPE_LANCE', wtype)
        self.assertEqual(motion, 'melee')
        self.assertEqual(cadence, 'lance')

    def test_shaman_donor_maps_to_dark_static_cast_cadence(self):
        # Meesmickle's vanilla Shaman donor retains Flux/Dark binding and its stationary
        # incantation; it is not an Archer bow draw with a recoloured projectile.
        donor_class, wtype, motion, cadence = inject.battle_anims.BANIM_DONORS['shaman']
        self.assertEqual(donor_class, 'CLASS_SHAMAN')
        self.assertIn('ITYPE_DARK', wtype)
        self.assertEqual(motion, 'magic')
        self.assertIsNone(cadence)

    def test_mage_donor_maps_to_anima_static_cast_cadence(self):
        # Rootis (frost snowman) rides his OWN class -- CLASS_MAGE, Anima -- not the shaman:
        # the private AnimConf must repoint the ITYPE_ANIMA slot so the custom anim binds to
        # the tome he actually wields. Same stationary magic cadence as the shaman donor.
        donor_class, wtype, motion, cadence = inject.battle_anims.BANIM_DONORS['mage']
        self.assertEqual(donor_class, 'CLASS_MAGE')
        self.assertIn('ITYPE_ANIMA', wtype)
        self.assertEqual(motion, 'magic')
        self.assertIsNone(cadence)

    def test_every_melee_donor_names_a_known_cadence(self):
        from ref_to_battleframe import _MELEE_CADENCE
        for name, (_dc, _wt, motion, cadence) in inject.battle_anims.BANIM_DONORS.items():
            if motion == 'melee':
                self.assertIn(cadence, _MELEE_CADENCE, name)

    def test_gwyllgi_donor_binds_monster_and_unarmed_to_the_beast_cadence(self):
        # The white moose (#25) rides CLASS_GWYLLGI -- the class it already deploys as, and
        # whose own banim (cer_at1) supplies the cadence Nicolas asked for. The vanilla
        # Gwyllgi AnimConf carries exactly two slots, ITYPE_MONSTER and ITYPE_ITEM, and BOTH
        # are repointed: the moose swings a monster weapon (antlers-and-hooves -> rotten
        # claw), and ITEM is the UNARMED entry. Left vanilla, ITEM draws the stock purple
        # HOUND in the close-up -- the cavalier row's #206 defect on the one chapter whose
        # miniboss is an elk.
        donor_class, wtype, motion, cadence = inject.battle_anims.BANIM_DONORS['gwyllgi']
        self.assertEqual(donor_class, 'CLASS_GWYLLGI')
        self.assertEqual(wtype, ['0x0100 | ITYPE_MONSTER', '0x0100 | ITYPE_ITEM'])
        self.assertEqual(motion, 'melee')
        self.assertEqual(cadence, 'beast')


    def test_unique_append_returns_next_index_and_appends_the_symbol(self):
        new, idx = inject.battle_anims.banim_unique_append(self.CONFIGS, 'AnimConf_brau_ax1')
        self.assertEqual(idx, 3)                       # NULL + 2 existing -> new is index 3
        self.assertIn('    AnimConf_brau_ax1,', new)
        self.assertLess(new.index('AnimConf_brau_ax1'), new.index('};'))  # before close

    def test_unique_append_leaves_existing_rows_unchanged(self):
        new, _ = inject.battle_anims.banim_unique_append(self.CONFIGS, 'AnimConf_brau_ax1')
        self.assertIn('    NULL,\n    AnimConf_Unused_LuciusUnpromoted,', new)

    CHAR = ('    [CHARACTER_EIRIKA - 1] = {\n'
            '        .nameTextId = 0x212,\n'
            '        .number = CHARACTER_EIRIKA,\n'
            '        .defaultClass = CLASS_PIRATE,\n'
            '    },\n')

    def test_set_char_u25_inserts_both_indices(self):
        new = inject.battle_anims.banim_set_char_u25(self.CHAR, 3)
        self.assertIn('._u25 = { 3, 3 },', new)
        self.assertIn('.number = CHARACTER_EIRIKA,', new)   # didn't clobber siblings

    def test_set_char_u25_is_idempotent_and_overwrites(self):
        once = inject.battle_anims.banim_set_char_u25(self.CHAR, 3)
        twice = inject.battle_anims.banim_set_char_u25(once, 7)
        self.assertIn('._u25 = { 7, 7 },', twice)
        self.assertEqual(twice.count('._u25'), 1)           # replaced, not duplicated

    def test_combat_anim_patch_swaps_all_calls_and_widens_out_param(self):
        out = patched_text('src/banim-ekrbattleintro.c')
        self.assertIn('int animid1, animid2;', out)
        self.assertNotIn('u32 animid1', out)
        vanilla = inject.decomp.vanilla_decomp_text('src/banim-ekrbattleintro.c')
        self.assertEqual(out.count('GetBattleAnimationId_WithUnique(unit_bu'),
                         vanilla.count('GetBattleAnimationId(unit_bu'))
        self.assertNotIn('GetBattleAnimationId(unit_bu', out)

    # GetBanimPalette: a CUSTOM (appended) banim must keep its OWN palette. Vanilla forces
    # CLASS_ARCHER/_F/SNIPER/_F to the canonical bow palette (0x25/0x27/0x29/0x2B) regardless
    # of banim_id -- right for the stock anim, but it mis-paints a custom-anim unit deployed
    # AS a real archer (the per-character _u25 path). That was the RBG "cyan" bug (#65).
    def test_banim_palette_guard_short_circuits_custom_ids_before_the_switch(self):
        out = patched_text('src/banim-ekrmain.c')
        fn = out[out.index('int GetBanimPalette('):]
        guard = 'if (banim_id >= 0x%X)' % vanilla_banim_count()
        # the guard returns banim_id for any appended id, BEFORE the class switch runs
        self.assertIn(guard, fn)
        self.assertLess(fn.index(guard), fn.index('switch (jid)'))

    # The SECOND palette path, and the one that cost a session (#206, Baxby). FE8 also carries
    # a per-CHARACTER battle palette keyed on character x CLASS (gAnimCharaPalConfig), applied
    # AFTER the anim's own palette is loaded -- so it silently overwrites it. A cast member on
    # a vanilla slot whose character had a personal palette for that same class gets repainted:
    # Baxby wears FORDE, whose row is [CLASS_CAVALIER -> 0x57], and Baxby IS a Cavalier, so his
    # custom axe-beak palette was clobbered by Forde's green. Lupin escaped only by luck --
    # Duessel's personal palettes are all magic classes.
    def test_unique_pal_guard_suppresses_the_character_palette_on_both_sides(self):
        """A custom (appended) banim keeps its own palette wherever it is standing, and a stock
        id is BELOW the threshold, so Seth keeps his personal Paladin colours."""
        out = patched_text('src/banim-ekrbattleintro.c')
        first_custom = vanilla_banim_count()
        for side, valid in (('POS_L', 'valid_l'), ('POS_R', 'valid_r')):
            self.assertIn('gAnimCharaPalConfig[pid][i] == jid && %s && gBanimIdx[%s] < 0x%X'
                          % (valid, side, first_custom), out)
            self.assertIn('gBanimUniquePal[%s] = gAnimCharaPalIt[pid][i] - 1;' % side, out)


class TestRawPidBattleAnim(unittest.TestCase):
    """A named raw-pid creature can carry a battle anim (#25, the white moose).

    The faked-anim injector binds a unit's private AnimConf through its CharacterData `_u25`.
    Every unit that had one until now was a CAST member riding a vanilla CHARACTER_ slot, so
    the binding hardcoded `[CHARACTER_<slot> - 1]`. The white moose is not cast: it is ch05's
    raw on-map pid 0xb9, a gCharacterData GAP, exactly like Ravisin at 0xb8. The engine does
    not care -- GetBattleAnimationId_WithUnique reads `unit->pCharacterData->_u25`, which is
    the same field on a gap row as on a named one -- so the only thing standing between the
    moose and a battle anim was the injector's marker string.
    """

    def test_moose_battle_anim_is_declared_on_its_chapter_yaml(self):
        # Its pid, class, AI, art recipe and death quote are all authored there already; a
        # pcs/npcs file would be a SECOND definition site for one creature, and would make
        # `classed_cast` treat a miniboss as a deployable cast member.
        self.assertIn('white-moose', inject.cast.RAW_PID_BATTLE_ANIMS)
        chapter_yaml, pid = inject.cast.RAW_PID_BATTLE_ANIMS['white-moose']
        self.assertEqual(chapter_yaml, inject.chapter_ids.CH05_CHAPTER_YAML)
        self.assertEqual(pid, inject.chapter_ids.CH05_MOOSE_PID)

    def test_units_with_battle_anim_finds_the_raw_pid_chapter_unit(self):
        found = dict(inject.battle_anims.units_with_battle_anim('rime-of-the-frostmaiden'))
        self.assertIn('white-moose', found)
        self.assertEqual(found['white-moose']['battle_anim']['clone_from'], 'gwyllgi')

    def test_raw_pid_u25_marker_addresses_the_character_data_gap(self):
        # `[0xb9 - 1]` is how raw_pid_portrait_data already addresses this row; the anim
        # binding must use the SAME designator, not a CHARACTER_ enum the moose does not have.
        self.assertEqual(inject.battle_anims.banim_u25_marker('white-moose'), '[0xb9 - 1]')

    def test_cast_u25_marker_is_unchanged(self):
        # The regression guard: every existing PC still binds through its CHARACTER_ slot.
        self.assertEqual(inject.battle_anims.banim_u25_marker('braulo'), '[CHARACTER_EIRIKA - 1]')
        self.assertEqual(inject.battle_anims.banim_u25_marker('lupin'), '[CHARACTER_DUESSEL - 1]')

    def test_unknown_unit_still_fails_loudly(self):
        with self.assertRaises(SystemExit):
            inject.battle_anims.banim_u25_marker('nobody-at-all')

    def test_the_sandbox_benches_the_moose_under_its_own_pid(self):
        # The TESTCH sandbox is "one bench for every battle animation" (recordenemy's docstring),
        # and it deployed foes by CLASS alone. That is enough for a class-level reskin, but the
        # moose's anim binds per-CHARACTER through _u25 -- so a Gwyllgi deployed under the
        # generic 0x80 monster charIndex plays the stock HOUND, and the bench would prove the
        # opposite of what it was run for. Its foe row must carry charIndex 0xb9.
        body = inject.test_chapter._sandbox_foe_roster('rime-of-the-frostmaiden', 'ch05')
        self.assertIn('.charIndex = 0xb9,', body)
        moose = [b for b in body.split('    {') if '0xb9' in b]
        self.assertEqual(len(moose), 1, 'expected exactly one moose foe row')
        self.assertIn('CLASS_GWYLLGI', moose[0])
        self.assertIn('ITEM_MONSTER_FIREFANG', moose[0])    # the slot its anim repoints
        self.assertNotIn('.autolevel', moose[0])            # a named miniboss, not generic trash

    def test_every_chapter_benches_every_reskin_it_dresses(self):
        # Regression: adding the moose must not push a reskin off the end of the position list.
        # The bench seats one chapter at a time, so every chapter's bench is checked.
        campaign = 'rime-of-the-frostmaiden'
        for ch in inject.test_chapter.bench_chapters(campaign):
            body = inject.test_chapter._sandbox_foe_roster(campaign, ch)
            for reskin in inject.reskins.enemy_class_reskins(campaign):
                if (ch in (reskin.get('dresses') or {})
                        and inject.test_chapter.CLASS_RESKIN_FOE_WEAPON.get(reskin['base'])):
                    self.assertIn(reskin['slot'], body, ch)

    def test_the_default_bench_is_the_newest_chapter(self):
        campaign = 'rime-of-the-frostmaiden'
        newest = inject.test_chapter.bench_chapters(campaign)[-1]
        self.assertEqual(inject.test_chapter._sandbox_foe_roster(campaign),
                         inject.test_chapter._sandbox_foe_roster(campaign, newest))

    def test_every_bench_tile_is_actually_on_the_sandbox_map(self):
        # The strip shipped with a seventh tile at x=16 on a 15-wide map. `_next_sandbox_tile`
        # guards running OUT of tiles and says nothing about a tile that does not EXIST, so the
        # seventh creature deployed off the edge and `recordenemy` failed walking the cursor to
        # a column the map has not got. Two units on the bench hid it: the sixth still fitted.
        w, h = inject.test_chapter.sandbox_map_size('rime-of-the-frostmaiden')
        for x, y in inject.test_chapter.SANDBOX_FOE_POSITIONS:
            self.assertTrue(0 <= x < w and 0 <= y < h,
                            'bench tile (%d,%d) is outside the %dx%d sandbox map' % (x, y, w, h))
        inject.test_chapter.assert_sandbox_bench_fits('rime-of-the-frostmaiden')

    def test_the_sandbox_size_is_read_from_the_map_we_actually_host_on(self):
        # NOT vanilla Ch1's map: inject_winter_tileset repoints the test chapter at our own
        # ChTestSnowMap. Same 15x10 today, so a constant would be right by accident -- and
        # the bench is exactly full, which makes widening that snowfield the next move.
        import json
        with open(os.path.join(inject.decomp.REPO, 'campaigns', 'rime-of-the-frostmaiden', 'maps',
                               'ch-test-snowfield.json'), encoding='utf-8') as f:
            m = json.load(f)
        self.assertEqual(inject.test_chapter.sandbox_map_size('rime-of-the-frostmaiden'),
                         (m['width'], m['height']))

    def test_every_benched_creature_gets_a_distinct_tile(self):
        """No two foes adjacent, and every foe has a MELEE bait tile of its own.

        This used to sort ALL the x values flat and require a gap of 2 -- a proxy for the real
        rule that only held while the bench was ONE row, and a second row (#25) legitimately
        shares columns. The property `recordenemy` needs is stated directly: it walks the ring
        at the bait's distance looking for an on-map, empty tile with no OTHER foe inside the
        bait's own reach, and fails the run if there is none.

        MODELLED AT RANGE 1 ON PURPOSE, and the limit is worth naming: a ranged bait searches a
        WIDER ring and excludes on a wider radius, and which applies depends on the weapons the
        two units happen to be carrying at runtime -- which this cannot see. Range 1 is the
        tightest case for finding a tile and the loosest for exclusion, so passing here is
        necessary, not sufficient. The four `recordenemy` films are what prove the rest.
        """
        tiles = inject.test_chapter.SANDBOX_FOE_POSITIONS
        self.assertEqual(len(set(tiles)), len(tiles), 'two creatures share a tile')
        w, h = inject.test_chapter.sandbox_map_size('rime-of-the-frostmaiden')
        foes = set(tiles)
        adj = lambda t: [(t[0] + dx, t[1] + dy) for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0))]
        on = lambda t: 0 <= t[0] < w and 0 <= t[1] < h
        for t in tiles:
            self.assertTrue(on(t), '%s is off the %dx%d map' % (t, w, h))
            self.assertFalse(foes & set(adj(t)), '%s is orthogonally adjacent to another foe' % (t,))
            clean = [n for n in adj(t)
                     if on(n) and n not in foes and not (foes - {t}) & set(adj(n))]
            self.assertTrue(clean, '%s has no on-map bait tile that touches only it' % (t,))

    def test_the_bench_never_seats_a_foe_on_a_player(self):
        """The bench and the player formation share a map, and nothing else checks it.

        `assert_sandbox_bench_fits` reads the map for BOUNDS only. A bench row placed on one of
        `TEST_SPAWN_POSITIONS`' rows (y=3..7) misses the party only while the two happen to use
        opposite x parities -- which an earlier cut of the second row relied on without saying
        so. Assert the tiles are disjoint, and that no foe is adjacent to a spawn either, since
        a bait needs somewhere to stand.
        """
        foes = set(inject.test_chapter.SANDBOX_FOE_POSITIONS)
        spawns = set(inject.test_chapter.TEST_SPAWN_POSITIONS)
        self.assertFalse(foes & spawns, 'a bench seat lands on a player spawn')
        adj = lambda t: {(t[0] + dx, t[1] + dy) for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0))}
        for f in foes:
            self.assertFalse(adj(f) & spawns,
                             'bench seat %s is adjacent to a player spawn' % (f,))

    def test_the_bench_seats_every_creature_that_needs_one(self):
        # The count that must not silently overflow, per chapter (the bench seats one): one
        # tile per weapon-carrying reskin it dresses plus one per raw-pid creature it owns.
        # Ravisin taking the sixth is what pushed the moose off.
        campaign = 'rime-of-the-frostmaiden'
        for ch in inject.test_chapter.bench_chapters(campaign):
            reskins = sum(1 for r in inject.reskins.enemy_class_reskins(campaign)
                          if ch in (r.get('dresses') or {})
                          and inject.test_chapter.CLASS_RESKIN_FOE_WEAPON.get(r['base']))
            raw = sum(1 for uid, (yml, pid) in inject.cast.RAW_PID_BATTLE_ANIMS.items()
                      if yml.startswith(ch + '-')
                      and inject.cast._chapter_unit(campaign, yml, uid).get('battle_anim'))
            self.assertLessEqual(reskins + raw, len(inject.test_chapter.SANDBOX_FOE_POSITIONS),
                                 '%s over-subscribes the bench; add a tile (on the map)' % ch)

    def test_the_moose_name_spends_no_donor(self):
        # The kobolds' #90 rule, one namespace over: append your own id rather than burn a
        # scarce vanilla slot. A character donor would have cost the campaign a slot for a
        # STRING -- and the obvious beast donor, Morva, is FE8's Great Dragon, which the
        # roadmap's Chardalyn Dragon (ch13-14, a marquee boss) has first claim on.
        unit_id, slot, portrait_id, name = inject.cast.RAW_PID_PORTRAITS[inject.chapter_ids.CH05_MOOSE_PID]
        self.assertEqual((unit_id, name), ('white-moose', 'White Moose'))
        self.assertEqual(slot, inject.chapter_ids.CH05_MOOSE_NAME_MSG)
        self.assertIsInstance(slot, int)          # an id we own, not a donor slot name
        self.assertIsNone(portrait_id)            # named, not dressed
        self.assertNotIn('white-moose', inject.cast.GUEST_PORTRAIT_MAP)

    def test_the_appended_name_id_is_past_the_last_vanilla_message(self):
        # 0xD4B is vanilla's last. An id at or below it would squat on real text.
        self.assertGreater(inject.chapter_ids.CH05_MOOSE_NAME_MSG, 0xD4B)

    def test_a_donor_slot_and_an_owned_id_both_resolve(self):
        self.assertEqual(inject.text.raw_pid_name_text_id(0xD4C), 0xD4C)      # ours, verbatim
        self.assertEqual(inject.text.raw_pid_name_text_id('Riev'), 0x246)     # donor, scanned

    def test_a_raw_pid_can_be_named_without_being_dressed(self):
        # raw_pid_portrait_data always wrote a portraitId. A name-only donor has none, and
        # inserting `.portraitId = 0xNone` would not even compile -- so the write is skipped and
        # the gap row keeps its generic miniPortrait, exactly as vanilla leaves Morva's own row.
        block = ('    [0xb9 - 1] = {\n'
                 '        .nameTextId = 0x255,\n'
                 '        .number = 0xb9,\n'
                 '        .defaultClass = CLASS_GORGON,\n'
                 '        .miniPortrait = 0x4,\n'
                 '    },\n')
        out = inject.raw_pids._bind_raw_pid_identity(block, '[0xb9 - 1]', 0xD4C, None)
        self.assertIn('.nameTextId = 0xD4C,', out)
        self.assertNotIn('.portraitId', out)
        self.assertIn('.miniPortrait = 0x4,', out)

    def test_a_raw_pid_with_a_bust_still_gets_its_portrait_id(self):
        # Regression: Ravisin's binding is unchanged -- she DOES dress Riev (portrait id 0x48).
        block = ('    [0xb8 - 1] = {\n'
                 '        .nameTextId = 0x255,\n'
                 '        .number = 0xb8,\n'
                 '        .defaultClass = CLASS_GORGON,\n'
                 '    },\n')
        out = inject.raw_pids._bind_raw_pid_identity(block, '[0xb8 - 1]', 0x246, 0x48)
        self.assertIn('.nameTextId = 0x246,', out)
        self.assertIn('.portraitId = 0x48,', out)

    def test_the_moose_carries_its_own_beast_lines_weapon(self):
        # ITEM_MONSTER_ROTTENCLW is the REVENANT's claw (ch04's three Revenants hold it) -- a
        # different creature's gear. FIREFANG is the Mauthe Doog's, and the Mauthe Doog is this
        # creature's own unpromoted tier (data_classes.c: CLASS_MAUTHEDOOG.promotion =
        # CLASS_GWYLLGI), so the moose stays inside its own line. HELLFANG, the promoted tier's,
        # is class-correct too but put ONE unit at 20% of the chapter's whole threat -- the
        # entire parity overage in a single slot. Never renamed either way.
        chap = inject.hosting._load_chapter_yaml('rime-of-the-frostmaiden', inject.chapter_ids.CH05_CHAPTER_YAML)
        moose = next(e for e in chap['enemy_units'] if e['id'] == 'white-moose')
        self.assertEqual([i['fe_base'] for i in moose['inventory']], ['fire-fang'])
        self.assertEqual(inject.chapter_ids.CH05_ITEM_IDS['fire-fang'], 'ITEM_MONSTER_FIREFANG')
        self.assertNotIn('rotten-claw', [i['fe_base'] for i in moose['inventory']])

    def test_the_gap_row_takes_a_u25_it_did_not_have(self):
        # gCharacterData's 0xB0-range gaps omit `._u25` entirely (it defaults to {0,0}, which
        # is precisely "no unique anim"). banim_set_char_u25 must INSERT it after `.number`,
        # the same way raw_pid_portrait_data inserts a missing `.portraitId`.
        gap = ('    [0xb9 - 1] = {\n'
               '        .nameTextId = 0x255,\n'
               '        .number = 0xb9,\n'
               '        .defaultClass = CLASS_GORGON,\n'
               '    },\n')
        out = inject.battle_anims.banim_set_char_u25(gap, 11)
        self.assertIn('._u25 = { 11, 11 },', out)
        self.assertIn('.number = 0xb9,', out)

    def test_pegasus_donor_maps_to_pegasus_knight_lance(self):
        # Pinky (the flier) rides CLASS_PEGASUS_KNIGHT with a lance -- the donor supplies the
        # _u25 AnimConf to clone and the ITYPE_LANCE weapon slot to repoint at her IMPORTED
        # swoop. motion/cadence are unused on the import path (the motion.s comes from the
        # .txt) but stay valid so the melee-cadence invariant above holds.
        donor_class, wtype, motion, cadence = inject.battle_anims.BANIM_DONORS['pegasus']
        self.assertEqual(donor_class, 'CLASS_PEGASUS_KNIGHT')
        self.assertIn('ITYPE_LANCE', wtype)

    def test_bishop_donor_binds_staff_light_and_unarmed_to_one_anim(self):
        # ITYPE_ITEM joined on the #25 review: the vanilla Bishop AnimConf carries five slots
        # and ITEM is the UNARMED entry, reachable with both staves spent. Left vanilla, a
        # healer with only a Vulnerary draws a HUMAN BISHOP in the close-up -- the cavalier
        # row's #206 defect. ANIMA/DARK stay vanilla on purpose: this line can equip neither.
        donor_class, wtype, motion, cadence = inject.battle_anims.BANIM_DONORS['bishop']
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
        out = inject.battle_anims.banim_clone_conf(src, 'AnimConf_SRC', 'AnimConf_NEW', wtypes[0], 0x99 + 1)
        for wt in wtypes[1:]:
            out = inject.battle_anims.banim_repoint_conf(out, 'AnimConf_NEW', wt, 0x99 + 1)
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
            res = inject.battle_anims.build_unit_battle_anim(cfg, d, 'testu', 'melee', 'lance')
        self.assertEqual(len(res['sheets']), 3)          # faked = exactly 3 poses
        self.assertIn('banim_testu_script', res['motion_s'])

    def test_imported_battle_anim_builder_reads_txt_and_frames(self):
        # A block with `import:` builds via feditor_to_banim (the #90 N-frame path), bound
        # per-character. Exercised against Pinky's real committed swoop assets -- the ONLY new
        # seam vs the shipped enemy import (which binds per-CLASS).
        anim_dir = os.path.join(inject.decomp.REPO, 'campaigns', 'rime-of-the-frostmaiden',
                                'battle_anims', 'pinky')
        cfg = {'clone_from': 'pegasus',
               'import': {'txt': 'Pinky.txt', 'frames_dir': '.'}}
        res = inject.battle_anims.build_unit_battle_anim(cfg, anim_dir, 'pinky', 'melee', 'lance')
        self.assertEqual(len(res['sheets']), 7)          # six swoop frames + a dodge frame
        self.assertIn('banim_pinky_script', res['motion_s'])
        self.assertEqual(len(res['pal']), 128)           # same agbpal shape as the faked path

    def test_palette_edit_recolours_the_agbpal_and_leaves_the_sheets_alone(self):
        # The per-character import path takes a HAND-EDITED palette (`palette_edit:`,
        # written by tools/banim_palette.py) the same way the class path takes a named
        # recolour fn. A community anim ships the author's colours; the edit is a look
        # call over them, so it may only move the agbpal -- every sheet INDEX must be
        # byte-identical, or it is a re-import wearing a palette's clothes (#25).
        import json
        import tempfile
        anim_dir = os.path.join(inject.decomp.REPO, 'campaigns', 'rime-of-the-frostmaiden',
                                'battle_anims', 'pinky')
        plain = inject.battle_anims.build_unit_battle_anim(
            {'clone_from': 'pegasus', 'import': {'txt': 'Pinky.txt', 'frames_dir': '.'}},
            anim_dir, 'pinky', 'melee', 'lance')
        with tempfile.TemporaryDirectory() as d:
            import banim_palette as bp
            doc = bp.Doc(anim_dir, 'Pinky.txt')
            edit = os.path.join(d, 'pal.json')
            bp.save_edit(edit, doc.palette, {1: (248, 8, 8)})
            # `palette_edit:` is resolved against the anim dir, like `txt`/`frames_dir`
            rel = os.path.relpath(edit, anim_dir)
            cfg = {'clone_from': 'pegasus',
                   'import': {'txt': 'Pinky.txt', 'frames_dir': '.', 'palette_edit': rel}}
            edited = inject.battle_anims.build_unit_battle_anim(cfg, anim_dir, 'pinky', 'melee', 'lance')
            self.assertNotEqual(plain['pal'], edited['pal'])
            self.assertEqual([s.tobytes() for s in plain['sheets']],
                             [s.tobytes() for s in edited['sheets']])
            self.assertEqual(json.load(open(edit))['edited'], {'1': '#f80808'})

    def test_vendored_import_reads_frames_from_the_vendored_tree(self):
        # `vendored: <name>/<mode>` reads txt + frames from engine/battle_anims/_vendored, the
        # way an enemy class reskin's `source:` does, so a cast member can wear a vendored anim
        # without a second copy of its frames; `palette_edit` stays under the campaign dir
        # (it is this unit's look, not the asset's). Trex wears the Dino Dread Fighter (#461).
        anim_dir = os.path.join(inject.decomp.REPO, 'campaigns', 'rime-of-the-frostmaiden',
                                'battle_anims')
        native = inject.battle_anims.build_unit_battle_anim(
            {'clone_from': 'thief',
             'import': {'vendored': 'dino-dread-fighter/sword', 'txt': 'Sword.txt'}},
            anim_dir, 'trex', 'melee', 'sword')
        edited = inject.battle_anims.build_unit_battle_anim(
            {'clone_from': 'thief',
             'import': {'vendored': 'dino-dread-fighter/sword', 'txt': 'Sword.txt',
                        'palette_edit': 'trex/palette.json'}},
            anim_dir, 'trex', 'melee', 'sword')
        self.assertIn('banim_trex_script', native['motion_s'])
        self.assertNotEqual(native['pal'], edited['pal'])
        self.assertEqual([s.tobytes() for s in native['sheets']],
                         [s.tobytes() for s in edited['sheets']])

    def test_thief_donor_repoints_both_of_its_slots(self):
        # CLASS_THIEF's AnimConf is SWORD + ITEM (data_banimconf.c AnimConf_088AF0A0); ITEM is
        # the unarmed entry a Thief reaches holding only keys, so leaving it vanilla draws Colm.
        donor_class, wtypes, _motion, _cadence = inject.battle_anims.BANIM_DONORS['thief']
        self.assertEqual(donor_class, 'CLASS_THIEF')
        self.assertEqual(sorted(wtypes), ['0x0100 | ITYPE_ITEM', '0x0100 | ITYPE_SWORD'])

    def test_a_missing_palette_edit_fails_the_build(self):
        # A typo'd path must stop the build, not silently ship the native colours -- the
        # whole point of the edit is that native was WRONG for this unit.
        anim_dir = os.path.join(inject.decomp.REPO, 'campaigns', 'rime-of-the-frostmaiden',
                                'battle_anims', 'pinky')
        cfg = {'clone_from': 'pegasus',
               'import': {'txt': 'Pinky.txt', 'frames_dir': '.',
                          'palette_edit': 'no-such-palette.json'}}
        with self.assertRaises(IOError):
            inject.battle_anims.build_unit_battle_anim(cfg, anim_dir, 'pinky', 'melee', 'lance')


class BattleSpellPaletteTint(unittest.TestCase):
    """Per-character spell visuals remain data, not campaign-specific engine code."""

    CAMPAIGN = 'rime-of-the-frostmaiden'

    def test_caster_tints_are_scoped_to_each_caster_and_weapon_type(self):
        # Marty's green tint covers all his Dark tomes; Rootis's blue (ice flavor) covers
        # all his Anima tomes. Each is character+weapon-type scoped -- no engine name-check.
        # Both still declare a single `weapon_type:` (not the list form) -- must keep working.
        self.assertTrue(hasattr(inject.battle_anims, 'battle_spell_palette_tints'))
        rows = inject.battle_anims.battle_spell_palette_tints(self.CAMPAIGN)
        self.assertIn(('CHARACTER_SETH', 'ITYPE_DARK', 'BANIM_SPELL_TINT_GREEN'), rows)
        self.assertIn(('CHARACTER_VANESSA', 'ITYPE_ANIMA', 'BANIM_SPELL_TINT_BLUE'), rows)

    def test_sclorbo_cyan_tint_covers_both_staff_and_light_via_weapon_types_list(self):
        # Sclorbo's spell_palette_tint declares `weapon_types: [staff, light]` (a list) --
        # one row per weapon type, both his DEDICATED flame cyan (bright equal G+B), NOT the
        # blue-dominant frost tint Rootis uses.
        rows = inject.battle_anims.battle_spell_palette_tints(self.CAMPAIGN)
        self.assertIn(('CHARACTER_ROSS', 'ITYPE_STAFF', 'BANIM_SPELL_TINT_CYAN'), rows)
        self.assertIn(('CHARACTER_ROSS', 'ITYPE_LIGHT', 'BANIM_SPELL_TINT_CYAN'), rows)

    def test_basil_gold_tint_covers_both_staff_and_light(self):
        # Basil reuses Sclorbo's Bishop donor, so without a tint of his own the army's two
        # healers would cast the SAME cyan -- the one thing the healer split is meant to make
        # visible at a glance. Gold is cyan's mirror (red+green high, blue suppressed) and
        # reads as the goodberry warmth. Same weapon_types list: heal now, Light post-promo.
        rows = inject.battle_anims.battle_spell_palette_tints(self.CAMPAIGN)
        self.assertIn(('CHARACTER_ARTUR', 'ITYPE_STAFF', 'BANIM_SPELL_TINT_GOLD'), rows)
        self.assertIn(('CHARACTER_ARTUR', 'ITYPE_LIGHT', 'BANIM_SPELL_TINT_GOLD'), rows)

    def test_gold_is_a_real_engine_tint_not_a_silent_fallthrough(self):
        # The dispatch in BanimSpellPaletteCopy ends in `else -> Green`, so a colour that is
        # named in YAML and enumerated but NOT branched on would compile, run, and quietly
        # cast GREEN. That failure has no symptom to read, so it gets a test.
        hooks = '\n'.join(patched_text(rel) for rel in ('include/ekrbattle.h',
                                                          'src/banim-ekrutils.c'))
        self.assertIn('BANIM_SPELL_TINT_GOLD = 4', hooks)
        self.assertIn('static u16 BanimSpellTintGold(u16 color)', hooks)
        self.assertIn('gMSSpellTint == BANIM_SPELL_TINT_GOLD', hooks)

    def test_tint_rows_append_a_terminated_campaign_data_table(self):
        src = ('#include "constants/items.h"\n'
               'CONST_DATA struct BattleAnimDef * gUnitSpecificBanimConfigs[] = {\n'
               '    NULL,\n};\n')
        self.assertTrue(hasattr(inject.battle_anims, 'banim_spell_palette_tint_append'))
        out = inject.battle_anims.banim_spell_palette_tint_append(
            src, [('CHARACTER_SETH', 'ITYPE_DARK', 'BANIM_SPELL_TINT_GREEN')])
        self.assertIn('CONST_DATA struct BanimSpellPaletteTint gBanimSpellPaletteTints[]', out)
        self.assertIn('#include "constants/characters.h"', out)
        self.assertIn('{ CHARACTER_SETH, ITYPE_DARK, BANIM_SPELL_TINT_GREEN },', out)
        self.assertIn('{ 0, 0, BANIM_SPELL_TINT_NONE },', out)

    def test_engine_patch_records_the_tint_in_the_dedicated_global(self):
        out = patched_text('src/banim-efxmagic.c')
        out = out[out.index('void StartSpellAnimation(struct Anim *anim)'):]
        self.assertIn('gMSSpellTint = GetBanimSpellPaletteTint(anim);', out)
        self.assertLess(out.index('s16 index'), out.index('gMSSpellTint'))

    def test_tint_rides_a_dedicated_overlay_global_leaving_the_lifecycle_flag_vanilla(self):
        """The tint rides its own EWRAM_OVERLAY(banim) global; gEfxSpellAnimExists stays vanilla."""
        header = patched_text('include/ekrbattle.h')
        battle = patched_text('src/banim-ekrbattle.c')
        utils = patched_text('src/banim-ekrutils.c')
        dispup = patched_text('src/banim-ekrdispup.c')
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
        self.assertTrue(hasattr(inject.battle_anims, 'banim_charge_flash_append'))
        out = inject.battle_anims.banim_charge_flash_append(
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
        out = inject.battle_anims.banim_charge_flash_append(
            src, [('CHARACTER_ROSS', 'ITYPE_STAFF', '0x6F63', 1)])
        self.assertIn('{ CHARACTER_ROSS, ITYPE_STAFF, 0x6F63, 1 },', out)

    def test_named_colour_resolves_to_a_bgr555_hex_target(self):
        # 'blue' is Rootis's ice hue (120,205,255) -> 5-bit per channel, packed BGR555.
        self.assertTrue(hasattr(inject.battle_anims, 'charge_flash_target'))
        self.assertEqual(inject.battle_anims.charge_flash_target('blue'), '0x7F2F')

    def test_cyan_colour_resolves_to_sclorbos_flame_bgr555_target(self):
        # Sclorbo's confirmed flame cyan: RGB(31,219,219) -> BGR555 0x6F63.
        self.assertEqual(inject.battle_anims.charge_flash_target('cyan'), '0x6F63')

    def test_charge_flashes_are_scoped_per_caster_with_bgr555_colour(self):
        # Each caster's charge_flash: {color} -> one character+weapon-scoped row, the weapon
        # type derived from the donor (Rootis mage/anima; Marty & Meesmickle shaman/dark).
        # The three existing casters have no `waveform` in YAML -> default 0 (pulse), the
        # byte-identical existing LUT.
        self.assertTrue(hasattr(inject.battle_anims, 'battle_charge_flashes'))
        rows = inject.battle_anims.battle_charge_flashes(self.CAMPAIGN)
        self.assertIn(('CHARACTER_VANESSA', 'ITYPE_ANIMA', inject.battle_anims.charge_flash_target('blue'), 0), rows)
        self.assertIn(('CHARACTER_SETH', 'ITYPE_DARK', inject.battle_anims.charge_flash_target('green'), 0), rows)
        self.assertIn(('CHARACTER_GILLIAM', 'ITYPE_DARK', inject.battle_anims.charge_flash_target('purple'), 0), rows)

    def test_sclorbos_list_donor_emits_one_build_row_per_weapon_type(self):
        # Sclorbo's bishop donor's wtype is a LIST (['...ITYPE_STAFF', '...ITYPE_LIGHT']) --
        # the charge_flash must arm on BOTH the Heal staff and the post-promo Light tome,
        # each row carrying his cyan target + waveform=1 (build, a single slow swell).
        rows = inject.battle_anims.battle_charge_flashes(self.CAMPAIGN)
        cyan = inject.battle_anims.charge_flash_target('cyan')
        self.assertIn(('CHARACTER_ROSS', 'ITYPE_STAFF', cyan, 1), rows)
        self.assertIn(('CHARACTER_ROSS', 'ITYPE_LIGHT', cyan, 1), rows)

    def test_patch_arms_the_flash_from_the_existing_charge_command(self):
        """The pulse is armed by the elec-charge command ALREADY in the magic body (case 40),
        so the donor-matched animation script is never altered. Injects the lookup + proc."""
        header = patched_text('include/ekrbattle.h')
        efxmisc = patched_text('src/banim-efxmisc.c')
        main = patched_text('src/banim-main.c')
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


if __name__ == '__main__':
    unittest.main()
