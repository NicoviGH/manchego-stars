#!/usr/bin/env python3
"""build_campaign.py -- inject campaign content into the decomp build tree.

Reads campaign data (YAML + authored busts) and writes decomp-native source/asset
files into build/fireemblem8u -- a git worktree of the fireemblem8u submodule
(tools/build_tree.py, #408) -- so a plain `make` compiles a ROM carrying our content.
The submodule itself stays vanilla; the generated files are reproducible build artifacts.

Engine/Content boundary (AGENTS.md): the GENERATOR knows character/chapter names;
the C/asm it EMITS is just data. No campaign name is ever hardcoded in engine C.

This file is the orchestrator: the CLI and `main()`, which is the authoritative pass
list. Every pass lives in `tools/inject/` -- the shared layer (text, scenes, cast, units,
maps, ...), one module per domain pass, and `inject/chapters/` for the chapter injectors.
"""
import argparse
import os
import sys
import time

# The tools/ modules (portrait_tool, map_tileset_tool, ...) sit next to us.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_scopes  # noqa: E402
import build_tree  # noqa: E402
from inject import chapter_data  # noqa: E402
from inject import chapter_frame  # noqa: E402
from inject import event_group  # noqa: E402
from inject import steps  # noqa: E402
from inject.chapter_ids import CH05_ENDING_ARMS  # noqa: E402
from inject.decomp import DECOMP  # noqa: E402
from inject.hosts import injected_chapters  # noqa: E402
from inject.paths import BUILD_SCOPES_PATH  # noqa: E402
from inject.scene_actors import assert_reachable_scenes_load_their_actors  # noqa: E402
from inject.warm import (  # noqa: E402
    _anim_step_cache, _decomp_footprint, _rewind_unchanged_mtimes, _snapshot_mtimes,
    _stamp_build_config, _written_since, load_compiled, normalise_decomp_shebangs,
    record_injected)

def parse_args(argv=None):
    """The CLI, validated: (args, the flags as passed). `injection_fingerprint --reach` reads
    each ROM configuration through this, so it sees the arguments a build would."""
    ap = argparse.ArgumentParser(description='Inject campaign content into the decomp build.')
    ap.add_argument('--campaign', default='rime-of-the-frostmaiden')
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
    args = ap.parse_args(argv)
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
    return args, _requested_flags


def main():
    args, _requested_flags = parse_args()

    # The tree we write into (#408): created on first use, and following a submodule bump.
    build_tree.ensure()
    print('build_campaign: injecting "%s" into %s' % (args.campaign, DECOMP))
    # Before anything else: undo whatever the last submodule checkout did to the decomp's
    # Linux shebangs, or this build dies minutes later on `bad interpreter`.
    normalise_decomp_shebangs(verbose=True)
    # Snapshot the previous build's injection footprint BEFORE we touch anything, so
    # we can rewind mtimes for whatever comes out byte-identical (fast warm rebuilds).
    _mtime_snapshot = _snapshot_mtimes(_decomp_footprint())
    # Everything written from here on is this injection's; the compiled record (#416) is read
    # up front for the same reason as the snapshot.
    _injection_start_ns = time.time_ns()
    _compiled = load_compiled()
    # Watch what every step actually writes: the playtest matrix tells a ch05 edit from a
    # global one by it (#255 phase 2), and a step that writes what it did not declare fails
    # the build (#409).
    _scopes = build_scopes.BuildScopes(
        DECOMP, roots=None if steps.strict() else build_scopes.SCOPE_ROOTS,
        previous=build_scopes.load_manifest(BUILD_SCOPES_PATH))
    _anims = _anim_step_cache(args.campaign)
    # Every pass, in order, each declaring what it writes and needs (#409): inject/steps.py.
    ran = steps.run(steps.STEPS, args, _scopes, _anims)
    prologue_injected = 'inject_prologue' in [step.name for step in ran]
    # LAST, because they read what every injector above actually wrote. Each hosted chapter's
    # settings row and event group were FRAMED from blank (#412): every field written, owned by
    # a total pass, or inherited with a declared reason. These check that every chapter came
    # through the frame, and that no pass wrote an inherited field behind its back.
    print('chapter frame (#412):')
    hosted = injected_chapters(prologue_injected)
    chapter_frame.assert_framed(hosted)
    event_group.assert_census_declared(hosted=hosted)
    chapter_data.assert_census_declared(hosted=hosted)
    print('  every hosted chapter is framed, and every inherited field still reads as its donor\'s')
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
    _wrote = _written_since(_injection_start_ns)
    steps.check_footprint(ran, [os.path.relpath(p, DECOMP) for p in _wrote])
    record_injected(_wrote)
    rewound = _rewind_unchanged_mtimes(_mtime_snapshot, _compiled)
    if rewound:
        print('idempotent injection: rewound %d unchanged file(s) -> make skips them'
              % rewound)
    _stamp_build_config(args.campaign, _requested_flags)
    print('done. Run `make` to compile the ROM.')


if __name__ == '__main__':
    main()
