#!/usr/bin/env python3
"""build_campaign.py -- inject campaign content into the fireemblem8u decomp build.

Reads campaign data (YAML + authored busts) and writes decomp-native source/asset
files into the fireemblem8u submodule working tree, so a plain `make` compiles a
ROM carrying our content. The generated files are reproducible build artifacts --
restore vanilla with `git -C fireemblem8u checkout <path>`.

Engine/Content boundary (AGENTS.md): the GENERATOR knows character/chapter names;
the C/asm it EMITS is just data. No campaign name is ever hardcoded in engine C.

This file is the orchestrator: the CLI and `main()`, which is the authoritative pass
list. Every pass lives in `tools/inject/` -- the shared layer (text, scenes, cast, units,
maps, ...), one module per domain pass, and `inject/chapters/` for the chapter injectors.
"""
import argparse
import os
import sys

# The tools/ modules (portrait_tool, map_tileset_tool, ...) sit next to us.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_scopes  # noqa: E402
from inject import chapter_data  # noqa: E402
from inject import engine_hooks  # noqa: E402
from inject import event_group  # noqa: E402
from inject.arena import inject_arena_attendant_portraits, inject_arena_presentation  # noqa: E402
from inject.backgrounds import inject_backgrounds  # noqa: E402
from inject.battle_anims import inject_battle_anims  # noqa: E402
from inject.boot import _configure_boot, TEST_CHAPTER_INDEX  # noqa: E402
from inject.chapter_ids import CH05_ENDING_ARMS  # noqa: E402
from inject.chapter_settings import apply_chapter_difficulty, apply_chapter_fog  # noqa: E402
from inject.chapters.ch01 import inject_ch01, inject_northlook_bitey  # noqa: E402
from inject.chapters.ch02 import inject_ch02, inject_ch02_chwinga_faces  # noqa: E402
from inject.chapters.ch03 import inject_ch03  # noqa: E402
from inject.chapters.ch04 import chain_ch03_to_ch04, inject_ch04  # noqa: E402
from inject.chapters.ch05 import chain_ch04_to_ch05, inject_ch05, inject_ch05_visit_faces  # noqa: E402
from inject.chapters.ch06 import chain_ch05_to_ch06, inject_ch06  # noqa: E402
from inject.chapters.prologue import inject_prologue  # noqa: E402
from inject.crit_flourish import inject_crit_flourish  # noqa: E402
from inject.death_quotes import inject_pc_death_quotes  # noqa: E402
from inject.decomp import DECOMP  # noqa: E402
from inject.hosts import (  # noqa: E402
    CH01_HOST_INDEX, CH03_HOST_INDEX, CH04_HOST_INDEX, CH05_HOST_INDEX, CH06_HOST_INDEX,
    injected_chapters, PROLOGUE_HOST_INDEX)
from inject.item_icons import inject_item_icon_pal2, inject_item_icons  # noqa: E402
from inject.map_sprites import inject_map_sprites  # noqa: E402
from inject.maps import inject_winter_tileset  # noqa: E402
from inject.messages import (  # noqa: E402
    assert_literals_are_claimed, assert_message_blocks_disjoint, assert_message_ids_unique,
    assert_named_raw_pids_are_exclusive, live_ids_in_declared_blocks)
from inject.names import inject_item_names, inject_names  # noqa: E402
from inject.paths import BUILD_SCOPES_PATH  # noqa: E402
from inject.platforms import inject_battle_platforms  # noqa: E402
from inject.portraits import inject_portraits, patch_portrait_geometry  # noqa: E402
from inject.raw_pids import patch_raw_pid_portraits  # noqa: E402
from inject.reskins import inject_enemy_class_battle_anims, inject_enemy_class_reskins  # noqa: E402
from inject.scene_actors import assert_reachable_scenes_load_their_actors  # noqa: E402
from inject.sms import sms_alloc_report, sms_alloc_reset  # noqa: E402
from inject.stats import patch_character_data  # noqa: E402
from inject.test_chapter import inject_test_chapter  # noqa: E402
from inject.title import inject_title_screen, inject_title_theme  # noqa: E402
from inject.traps import apply_chapter_traps  # noqa: E402
from inject.warm import (  # noqa: E402
    _anim_step_cache, _decomp_footprint, _rewind_unchanged_mtimes, _snapshot_mtimes,
    _stamp_build_config, normalise_decomp_shebangs, restore_vanilla_sources)


def main():
    ap = argparse.ArgumentParser(description='Inject campaign content into the decomp build.')
    ap.add_argument('--campaign', default='rime-of-the-frostmaiden')
    ap.add_argument('--portraits-only', action='store_true',
                    help='only inject portrait assets (skip names + characters)')
    ap.add_argument('--montage', action='store_true',
                    help='wire the #43 opening montage (lore crawl) instead of the '
                         'dev boot cut; dev builds keep the straight-to-map boot')
    ap.add_argument('--test-chapter', action='store_true',
                    help='PLAYTEST build: New Game boots straight into a Ch1 sandbox '
                         'with the whole cast deployed + the (reskinned) foes, cutscenes '
                         'stripped -- skips the prologue grind for fast in-engine testing. '
                         'Mutually exclusive with the prologue (both host chapter slot 1).')
    ap.add_argument('--lord-boot', action='store_true',
                    help='DEBUG fast-boot (#46, implies --test-chapter): the Ch1 sandbox '
                         'opens straight into the lord-select prep screen on New Game, so '
                         'iterating on that screen is compile-time only -- no playthrough '
                         'grind (see decisions.md / the debug-fast-boot convention).')
    ap.add_argument('--ch01-boot', action='store_true',
                    help='PLAYTEST build (#353): New Game boots straight into Ch1 "The Iron '
                         'Trail" on slot 2. ch01 is the chapter that FOUNDS the party -- its '
                         'opening LOADs the company at the Northlook and then runs PREP -- so '
                         'this boot needs no armed seed table, unlike --ch03/04/05-boot. '
                         'Mutually exclusive with the prologue: confirming anything in ch01 '
                         'otherwise costs a full prologue playthrough (~24,000 frames).')
    ap.add_argument('--ch03-boot', action='store_true',
                    help='PLAYTEST build (#23): New Game boots straight into the Ch3 '
                         '"Termalaine Mine" on slot 4 -- the party deployed at the left '
                         'entrance + the 10 vanilla-Ch3-parity foes, cutscenes stripped '
                         '(fast-boot map load-test; mutually exclusive with the prologue).')
    ap.add_argument('--ch04-boot', action='store_true',
                    help='PLAYTEST build (#24): New Game boots straight into the Ch4 '
                         '"White Moose" snowy forest on slot 5 with an armed party, fog, '
                         'and the approved 16 + 4 + 3 vanilla-monster force.')
    ap.add_argument('--ch05-boot', action='store_true',
                    help='PLAYTEST build (#25): New Game boots straight into the Ch5 '
                         '"Elven Tomb" on slot 6 with an armed party, the 16 risen '
                         'tomb-guard on vanilla Ch5\'s own fighting tiles, and the three '
                         'eruption waves.')
    ap.add_argument('--ch06-boot', action='store_true',
                    help='PLAYTEST build (#26): New Game boots straight into Ch6 "The Maer '
                         'Monster" on slot 7 with an armed party, the merfolk line on its '
                         'authored placement, and both marooned boats green in their pockets.')
    ap.add_argument('--ch05-moose', action='store_true',
                    help='DEBUG build (#25): with --ch05-boot, New Game lands straight on '
                         'scene 7 (the moose charge). Skips the four backdrop scenes, '
                         'Preparations, the join and Sahnar\'s monologue -- ~52 A-presses of '
                         'already-approved footage -- so iterating on a late beat costs a '
                         'BUILD and not a playthrough.')
    ap.add_argument('--ch05-ending', choices=CH05_ENDING_ARMS, default=None,
                    help='DEBUG build (#25): with --ch05-boot, New Game lands straight on the '
                         'ENDING in the named roster state -- `full` (Basil alive, Sahnar '
                         'recruited), `no-sahnar` (the berry exchange cut) or `basil-died` '
                         '(scene 17). Reaching the ending honestly is the whole opening, '
                         'Preparations and a boss kill, and there are three of these to look '
                         'at.')
    ap.add_argument('--ch05-lupin', action='store_true',
                    help='PLAYTEST build (#25): with --ch05-boot, LOAD Lupin onto the roster '
                         'before ch05\'s opening so scene 4\'s CHECK_ALIVE branch takes its '
                         'ALIVE arm. The plain boot ROM cannot reach that arm at all.')
    args = ap.parse_args()
    # --ch05-lupin MODIFIES --ch05-boot rather than competing with it (it repoints nothing), so
    # it is not in the mutual-exclusion list below -- but on its own it would silently build a
    # plain canonical ROM with one extra unit table nothing loads.
    if args.ch05_moose and not args.ch05_boot:
        sys.exit('ERROR: --ch05-moose only means anything with --ch05-boot: it SKIPS '
                 'Preparations, so the boot seed is the only thing left that puts a party on '
                 'the map.')
    if args.ch05_ending and not args.ch05_boot:
        sys.exit('ERROR: --ch05-ending only means anything with --ch05-boot: it SKIPS '
                 'Preparations, so the boot seed is the only thing left that puts a party on '
                 'the map -- and the ending hands its reward to the party LEADER.')
    if args.ch05_ending and args.ch05_moose:
        sys.exit('ERROR: --ch05-ending and --ch05-moose both REPLACE ch05\'s beginning script, '
                 'so only one can win. Pick the beat you mean to look at.')
    if args.ch05_lupin and not args.ch05_boot:
        sys.exit('ERROR: --ch05-lupin only means anything with --ch05-boot: it exists to make '
                 'the opening branch\'s ALIVE arm reachable from a COLD boot.')
    # Snapshot the flags AS PASSED, before --lord-boot implies --test-chapter below:
    # the build stamp has to describe the `make` invocation, not the derived state.
    _requested_flags = {'TESTCH': args.test_chapter, 'LORDBOOT': args.lord_boot,
                        'MONTAGE': args.montage, 'CH01BOOT': args.ch01_boot,
                        'CH03BOOT': args.ch03_boot,
                        'CH04BOOT': args.ch04_boot, 'CH05BOOT': args.ch05_boot,
                        'CH05LUPIN': args.ch05_lupin, 'CH05MOOSE': args.ch05_moose,
                        'CH05ENDING': args.ch05_ending, 'CH06BOOT': args.ch06_boot}
    if args.lord_boot:
        args.test_chapter = True  # the fast-boot rides the sandbox
    # Each fast-boot repoints New Game at its own slot, so at most one may win. Named
    # explicitly rather than counted, so the error says which flags actually clash.
    _boots = [name for name, on in (('--ch01-boot', args.ch01_boot),
                                    ('--ch03-boot', args.ch03_boot),
                                    ('--ch04-boot', args.ch04_boot),
                                    ('--ch05-boot', args.ch05_boot),
                                    ('--ch06-boot', args.ch06_boot)) if on]
    if len(_boots) > 1:
        sys.exit('ERROR: %s are mutually exclusive -- each repoints New Game at its own '
                 'chapter slot' % ' and '.join(_boots))

    print('build_campaign: injecting "%s" into %s' % (args.campaign, DECOMP))
    # Before anything else: undo whatever the last submodule checkout did to the decomp's
    # Linux shebangs, or this build dies minutes later on `bad interpreter`.
    normalise_decomp_shebangs(verbose=True)
    # Snapshot the previous build's injection footprint BEFORE we touch anything, so
    # we can rewind mtimes for whatever comes out byte-identical (fast warm rebuilds).
    _mtime_snapshot = _snapshot_mtimes(_decomp_footprint())
    # Watch what each chapter injector actually writes, so the playtest matrix can tell a
    # ch05 edit from a global one and stop re-running the prologue for it (#255 phase 2).
    # Only the CHAPTER steps are wrapped: everything else falls through to `global`, which
    # every scenario depends on, so the conservative answer is also the default one.
    _scopes = build_scopes.BuildScopes(
        DECOMP, previous=build_scopes.load_manifest(BUILD_SCOPES_PATH))
    _anims = _anim_step_cache(args.campaign)
    print('portraits:')
    inject_portraits(args.campaign)
    inject_arena_attendant_portraits(args.campaign)
    if not args.portraits_only:
        restore_vanilla_sources()  # clean base each build (idempotent; vanilla donor reads)
        print('engine hardening:')
        engine_hooks._patch_player_start_cursor_guard()
        print('  GetPlayerStartCursorPosition: fall back to first player unit if leader undeployed')
        engine_hooks._patch_terrain_name_guard()
        print('  GetTerrainName: bounds-guarded against OOB terrain ids (defensive)')
        engine_hooks._patch_battle_map_kind_fallback()
        print('  GetBattleMapKind: no-world-map fallback = STORY (slot 2+ chapters)')
        engine_hooks._patch_chapter_title_wm_fallback()
        print('  GetChapterTitleWM: no-world-map fallback = ROM chapTitleId (not a WM skirmish name)')
        engine_hooks._inject_lord_select_engine()
        print('  lord select (#42): GetPid + force-deploy/Seize/game-over keyed to the chosen lead')
        engine_hooks._inject_lord_floor_engine()  # after lord-select: anchors on its LordSelect_GetPid
        print('  lord floor (#45 3c): chosen lead\'s survivability top-up baked in once at ch start')
        engine_hooks._patch_banim_character_unique()
        print('  banim (#65): combat anim lookup -> GetBattleAnimationId_WithUnique (per-character _u25)')
        engine_hooks._patch_banim_palette_custom_guard()
        print('  banim (#65): GetBanimPalette -> custom (appended) banims keep own palette (RBG cyan fix)')
        engine_hooks._patch_banim_unique_pal_custom_guard()
        print('  banim (#206): the per-CHARACTER palette no longer overwrites a custom banim\'s own '
              '(Baxby wore Forde\'s green)')
        engine_hooks._patch_banim_spell_palette_tint()
        print('  banim (#165): character/weapon spell palettes support campaign-declared tints')
        engine_hooks._patch_banim_charge_flash()
        print('  banim (#183): casters pulse their signature colour on the wind-up charge beat')
        engine_hooks._patch_draw_icon_pal2()
        print('  item icons (#23): DrawIcon routes gMSPal2IconIds from BG bank 4 to custom bank 15')
        engine_hooks._patch_arena_presentation()
        print('  Arena (#265): ArenaUi_Init selects optional campaign palette + chapter face')
        engine_hooks._patch_arena_battle_background()
        print('  Arena (#265): battle fade-in and palette cycle share campaign backdrop data')
        inject_arena_presentation(args.campaign)
        print('names:')
        inject_names(args.campaign)
        print('item names:')
        inject_item_names(args.campaign)
        print('item icons:')
        inject_item_icons(args.campaign)
        inject_item_icon_pal2(args.campaign)
        print('characters:')
        patch_character_data(args.campaign)
        patch_raw_pid_portraits(args.campaign)
        print('portrait geometry:')
        patch_portrait_geometry(args.campaign)
        print('map sprites:')
        # One SMS id pool for the whole build -- both sprite passes below spend from it (#227).
        sms_alloc_reset(args.campaign, verbose=True)
        inject_map_sprites(args.campaign)
        print('enemy class reskins (#21):')
        inject_enemy_class_reskins(args.campaign)  # after map sprites (SMS ids), before ch01
        sms_alloc_report()
        # The two most expensive steps in the build (17.1s + 8.5s of a ~50s `make`, measured
        # 2026-08-23) and the two that NO boot flag reaches -- every ROM configuration pays
        # them to produce byte-identical data, and the matrix builds five for one gate. So
        # they are cached on their inputs (#309). Both run BEFORE the first flag-dependent
        # step, which is what makes them config-invariant; `check.py` holds that ordering.
        print('enemy class battle anims (#90):')
        _anims.run(inject_enemy_class_battle_anims, args.campaign)  # after reskins (binds the clone)
        print('battle anims (#65):')
        _anims.run(inject_battle_anims, args.campaign)
        print('winter tileset:')
        inject_winter_tileset(args.campaign)
        print('battle platforms (#65):')
        inject_battle_platforms(args.campaign)
        print('crit flourish (#11):')
        inject_crit_flourish(args.campaign)
        print('title theme:')
        inject_title_theme(args.campaign)
        print('title screen:')
        inject_title_screen(args.campaign)
        print('event backgrounds (#22):')
        inject_backgrounds(args.campaign)  # vendored winter BGs -> new gConvoBackgroundData slots
        # Ownership gate (#198 review): fail the build BEFORE any injector writes text if two
        # hosted chapters claim one message id -- a double-claim is otherwise silent, since
        # verify_text checks runaway text, not who owns a slot.
        assert_message_ids_unique()
        assert_named_raw_pids_are_exclusive()
        assert_literals_are_claimed()
        assert_message_blocks_disjoint()   # the setup that would make a collision inevitable
        # And the third of the same family. It ran only from the tests, so `make check` caught
        # it but a plain `make` with an edited block table still produced a ROM -- and the whole
        # point of these is to fail the BUILD rather than let a collision ship.
        drawn_over = live_ids_in_declared_blocks()
        if drawn_over:
            sys.exit('ERROR: declared message block(s) drawn over ids the build already '
                     'spends: %s' % ', '.join(drawn_over))
        print('chapter 1 (#21):')
        _scopes.run(inject_ch01, args.campaign, boot=args.ch01_boot)  # MUST precede inject_prologue (vanilla goal read)
        inject_northlook_bitey()    # 'Ol Bitey over the tavern hearth (Beat 1 set dressing)
        print('chapter 2 (#22):')
        _scopes.run(inject_ch02, args.campaign)  # hosts slot 3; ch01's ending MNC2(0x3) lands here
        _scopes.run(inject_ch02_chwinga_faces, args.campaign)  # green chwinga bust + Mote/Rime/Glimmer names
        print('chapter 3 (#23):')
        _scopes.run(inject_ch03, args.campaign, boot=args.ch03_boot)
        print('chapter 4 (#24):')
        _scopes.run(inject_ch04, args.campaign, boot=args.ch04_boot)
        chain_ch03_to_ch04()
        print('chapter 5 (#25):')
        _scopes.run(inject_ch05, args.campaign, boot=args.ch05_boot,
                    lupin_proof=args.ch05_lupin, moose_only=args.ch05_moose,
                    ending_arm=args.ch05_ending)
        _scopes.run(inject_ch05_visit_faces, args.campaign)  # the four reliquary residents' skeleton busts
        chain_ch04_to_ch05()
        print('chapter 6 (#26):')
        _scopes.run(inject_ch06, args.campaign, boot=args.ch06_boot)
        chain_ch05_to_ch06()
        prologue_injected = False     # only the canonical New Game path below runs it
        if args.ch06_boot:
            print('CH06 BOOT (playtest: New Game -> Maer Dualdon, party + merfolk + boats):')
            _configure_boot(CH06_HOST_INDEX)
        elif args.ch05_boot:
            print('CH05 BOOT (playtest: New Game -> the Elven Tomb, party + foes deployed):')
            _configure_boot(CH05_HOST_INDEX)
        elif args.ch04_boot:
            print('CH04 BOOT (playtest: New Game -> White Moose forest, party + foes deployed):')
            _configure_boot(CH04_HOST_INDEX)
        elif args.ch03_boot:
            print('CH03 BOOT (playtest: New Game -> Termalaine Mine, party + foes deployed):')
            _configure_boot(CH03_HOST_INDEX)
        elif args.ch01_boot:
            # No seed table here on purpose: ch01's own opening LOADs the company and runs
            # PREP, so a cold start founds its party exactly as the canonical chapter does.
            print('CH01 BOOT (playtest: New Game -> the Iron Trail, party founded by ch01):')
            _configure_boot(CH01_HOST_INDEX)
        else:
            if args.test_chapter:
                print('TEST CHAPTER (playtest: New Game -> Ch1 sandbox, cast deployed):')
                inject_test_chapter(args.campaign, lord_boot=args.lord_boot)   # slot 1 sandbox, in place of the prologue
                _configure_boot(TEST_CHAPTER_INDEX)  # sandbox never montages
            else:
                print('prologue (New Game target):')
                _scopes.run(inject_prologue, args.campaign, montage=args.montage)
                prologue_injected = True
                _configure_boot(PROLOGUE_HOST_INDEX, montage=args.montage)
        print('death quotes (#6):')
        inject_pc_death_quotes(args.campaign)
        # LAST of the chapter passes: every hosted slot now exists, so this is where the
        # registry can insist each one DECLARED its difficulty numbers instead of keeping
        # the donor's (#303). Order-independent against _retarget_host_chapter (which does
        # not touch these fields), but running it last keeps "what the slot carries" one
        # decision made in one place.
        # Fog is the fifth and last chapter_settings field that could be inherited unexamined
        # (#365). Two injectors wrote it inline and five chapters kept whatever their squatted
        # slot shipped -- including ch06, whose host slot 7 is one of vanilla's five FOGGED
        # slots. Total pass, so "no injector wrote a line for this chapter" is unreachable.
        print('fog (#365):')
        apply_chapter_fog(args.campaign, verbose=True)
        print('difficulty modes (#303):')
        apply_chapter_difficulty(args.campaign, verbose=True)
        # Same pass, same reason: `.traps` is a ChapterEventGroup field our injectors fill
        # but never wrote, so a chapter kept its donor's. ch06 fills Ch7EventData, and vanilla
        # Ch7 carries two ballistae -- writing the declaration makes that impossible (#302).
        print('traps (#302):')
        apply_chapter_traps(args.campaign, verbose=True)
        # LAST, because it reads what every injector above actually wrote: every
        # ChapterEventGroup field must be WRITTEN or DECLARED-INHERITED, and anything nobody
        # has ruled on fails the build here rather than being found by shipping a bug (#313).
        print('event group census (#313):')
        event_group.assert_census_declared(hosted=injected_chapters(prologue_injected))
        print('  every ChapterEventGroup field is written or declared-inherited')
        # The same question about the OTHER struct a hosted chapter squats. Five
        # chapter_settings fields have shipped inherited-unexamined -- goal text ids (#207),
        # battle grounds (#289), the difficulty triple (#303), `.traps` (#302), fog (#365) --
        # each found one at a time by something else going wrong. This rules on all 98 at
        # once, so there is no sixth to find that way (#396).
        print('chapter data census (#396):')
        chapter_data.assert_census_declared(hosted=injected_chapters(prologue_injected))
        print('  every ROMChapterData field is written, pass-owned or declared-inherited')
        # The census rules on the twenty FIELDS; this rules on everything those fields lead
        # to. Our injectors edit a host slot's event-script file without rewriting every scene
        # in it, so untouched vanilla scenes sit in the files we write -- five of them staging
        # CHARACTER_EIRIKA, which is braulo. They are unreachable today because the injectors
        # overwrote the scenes that pointed at them, which is a fact about this build's output
        # and not a property anything held in place. Held here now (#398).
        print('reachable scene actors (#398):')
        assert_reachable_scenes_load_their_actors(
            hosted=injected_chapters(prologue_injected), verbose=True)
    # Close the scope manifest BEFORE the mtime rewind below: the rewind moves mtimes
    # backwards on byte-identical files, and this attribution watches mtimes.
    _scope_manifest = _scopes.write_manifest(
        BUILD_SCOPES_PATH,
        touched=[os.path.relpath(p, DECOMP) for p in _decomp_footprint()])
    print('build scopes: %s' % ', '.join(
        '%s=%d file(s)' % (scope, len(entry['paths']))
        for scope, entry in sorted(_scope_manifest.items())))
    rewound = _rewind_unchanged_mtimes(_mtime_snapshot)
    if rewound:
        print('idempotent injection: rewound %d unchanged file(s) -> make skips them'
              % rewound)
    _stamp_build_config(args.campaign, _requested_flags)
    print('done. Run `make` to compile the ROM.')


if __name__ == '__main__':
    main()
