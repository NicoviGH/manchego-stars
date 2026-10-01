"""Warm-rebuild acceleration: restoring vanilla sources and idempotent injection.

The injector rewinds mtimes on byte-identical outputs so `make` skips them, and caches the
config-invariant anim steps.
"""
import glob
import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import time

from inject import step_cache
import build_scopes
import gen_subtitle_cards
from inject.decomp import DECOMP, git_env, REPO
from inject.paths import BUILD_STAMP, COMPILED_DIR, INJECT_CACHE_DIR, INJECTED_PATHS


# Decomp source files we patch in place. We git-restore them to vanilla at the start
# of every build so injection always runs from a clean base -- idempotent across
# repeated `make`s, and stat-donor growths/ranks always read vanilla values.
PATCHED_DECOMP_FILES = ['texts/texts.txt', 'src/data_characters.c', 'src/portrait_data.c',
                        # #302 traps: apply_chapter_traps rewrites this every build, so it
                        # must reset -- otherwise a rehost or a branch switch carries the
                        # PREVIOUS build's rows into the ROM, which is the very inheritance
                        # the pass exists to remove, one level up.
                        'src/events_trapdata.c',
                        # #265 Arena presentation: campaign palette + chapter face selectors
                        # are generated into the real ArenaUi_Init translation unit; combat
                        # backdrop palettes bind through the Arena's cycling translation unit.
                        'src/uiarena.c', 'src/banim-ekrarena.c',
                        'src/events/ch1-eventudefs.h', 'src/events/ch1-eventinfo.h',
                        'src/events/ch1-eventscript.h', 'src/events/prologue-wm.h',
                        'src/gamecontrol.c', 'src/bmio.c', 'src/bmunit.c', 'src/bmmap.c',
                        'src/bmcamadjust.c',
                        'src/unit_icon_wait_data.c', 'src/unit_icon_move_data.c', 'src/mu.c',
                        'src/bmudisp.c', 'src/prep_unitselect.c',
                        # #218: both roster screens that blank the purple OBJ bank
                        # (PURPLE_BANK_BLANKERS); prep_unitselect.c is listed above
                        'src/unitlistscreen.c',
                        # lord-select (#46): CallLordSelectMenu decl for eventscripts
                        'include/eventcall.h',
                        # enemy class reskins (#21): cloned goblin classes in gClassData;
                        # classes.h gets new class ids appended past 0x7F (#23 Lizardzerker)
                        'src/data_classes.c', 'include/constants/classes.h',
                        # faked battle anims (#65): appended banim_data row + pointer
                        # externs + linker block; the Archer-CLONE class + its new AnimConf
                        # (data_classes.c already listed); the AnimConf's extern decl
                        'src/banim_data.c', 'include/banim_pointer.h',
                        'src/data_banimconf.c', 'include/ekrbattle.h',
                        # #165 caster-scoped spell-palette tint (green Dark magic): the
                        # _patch_banim_spell_palette_tint hook patches these TUs -- the
                        # GetBanimSpellPaletteTint lookup + StartSpellAnimation seam in
                        # efxmagic; the green recolour + palette-copy wrap in ekrutils; the
                        # dedicated gMSSpellTint overlay global in ekrbattle (declared beside
                        # gEfxSpellAnimExists); its teardown reset in ekrdispup. ekrbattle.h
                        # (the enum/struct/table + gMSSpellTint extern) is listed above.
                        'src/banim-efxmagic.c', 'src/banim-ekrutils.c',
                        'src/banim-ekrbattle.c', 'src/banim-ekrdispup.c',
                        # #183 per-caster charge flash: the _patch_banim_charge_flash hook adds
                        # the pulse proc + arm in banim-efxmisc, arms it from the existing
                        # elec-charge command (case 40) in banim-main, and declares the arm in
                        # efxbattle.h. The gMSChargeFlashes table rides data_banimconfunk.c
                        # (listed below); the struct/extern ride ekrbattle.h (listed above).
                        'src/banim-efxmisc.c', 'src/banim-main.c', 'include/efxbattle.h',
                        'linker_script_banim.txt',
                        # #65 M-B (character-unique anims, no class slot): the per-character
                        # config table gets the AnimConf appended; the combat-lookup engine
                        # hook swaps GetBattleAnimationId -> _WithUnique in ekrbattleintro;
                        # GetBanimPalette in ekrmain gets the custom-banim palette guard
                        'src/data_banimconfunk.c', 'src/banim-ekrbattleintro.c',
                        'src/banim-ekrmain.c',
                        # battle ground platforms (#65): vendored snow/ice grounds appended to
                        # battle_terrain_table + the terrain->ground remap (snow chapters)
                        'src/banim_terrain_data.c', 'data/data_banim_terrain.s',
                        'src/data_terrains.c', 'src/banim-battleparse.c', 'include/variables.h',
                        # nat-20 crit flourish (#11): efx proc hook + asset incbins
                        'src/banim-efxhit.c', 'data/data_banim.s',
                        # Goodberry (#21): vulnerary icon swapped by inject_item_icons
                        'graphics/item_icon/item_icon_vulnerary.png',
                        # pink Tourmaline (#23): the additive pal-2 icon route -- inject_item_icons
                        # reskins the Red Gem tiles, inject_item_icon_pal2 appends its icon
                        # palette, and the _patch_draw_icon_pal2 engine hook routes those iconIds
                        # to reserved BG bank 15. The icon/header hooks are NON-idempotent (their
                        # guard hard-exits on a non-vanilla form), so it MUST restore each build.
                        'src/icon.c', 'include/icon.h', 'graphics/item_icon/item_icon_palette.agbpal',
                        'graphics/item_icon/item_icon_red_gem.png',
                        'data/const_data_unit_icon_wait.s', 'data/const_data_unit_icon_move.s',
                        'include/unit_icon_pointer.h',
                        'data/const_data_chapter_maps.s', 'data/data_8B363C.s',
                        'src/data/chapter_settings.json',
                        'src/events/prologue-eventudefs.h', 'src/events/prologue-eventinfo.h',
                        'src/events/prologue-eventscript.h', 'src/data_battlequotes.c',
                        # ch01 host slot (#21): Ch2 events + the shared udefs TU;
                        # slot 2's title card is regenerated by inject_ch01
                        'src/events/ch2-eventinfo.h', 'src/events/ch2-eventscript.h',
                        # ch03 host slot (#23): Ch4 events (slot 4) rewritten by inject_ch03
                        'src/events/ch4-eventinfo.h', 'src/events/ch4-eventscript.h',
                        # ch04 host slot (#24): Ch5 events (slot 5) rewritten by inject_ch04
                        'src/events/ch5-eventinfo.h', 'src/events/ch5-eventscript.h',
                        # ch05 escort AI (#25): repoint_escort_safe_ai_list rewrites AI_A_07's
                        # do-not-attack list from CHARACTER_NATASHA to OUR escort, so Sahnar
                        # refuses to swing at Basil the way vanilla Joshua refuses Natasha. The
                        # patch is NON-idempotent by design -- it hard-exits unless it finds
                        # vanilla's form -- so it MUST restore each build.
                        'src/cp_data.c',
                        # ch05 host slot (#25): slot 6's events. Named "ch6" because FE8
                        # inserted Ch5x at slot 5, so from slot 6 on the slot index and the
                        # vanilla symbol name disagree in the BASE GAME -- see the CH05_*
                        # constant block, which states that offset once for the whole build.
                        'src/events/ch6-eventinfo.h', 'src/events/ch6-eventscript.h',
                        # ch06 host slot (#26): slot 7's events, one further along the same
                        # offset -- slot 7 ships Ch7EventData while ch05 fills Ch6Events
                        'src/events/ch7-eventinfo.h', 'src/events/ch7-eventscript.h',
                        'src/events_udefs.c', 'graphics/chap_title/chap_title_2.png',
                        # host slot's title card (chapTitleId 1); regenerated by
                        # inject_prologue from the chapter YAML's title
                        'graphics/chap_title/chap_title_1.png',
                        # ch02 host slot's title card (chapTitleId 3); regenerated by inject_ch02
                        'graphics/chap_title/chap_title_3.png',
                        # ch03 host slot's title card (chapTitleId 4); regenerated by inject_ch03
                        'graphics/chap_title/chap_title_4.png',
                        # ch04 host slot's title card (chapTitleId 5); regenerated by inject_ch04
                        'graphics/chap_title/chap_title_5.png',
                        # ch05 host slot's title card (chapTitleId 6); regenerated by inject_ch05
                        'graphics/chap_title/chap_title_6.png',
                        # ch06 host slot's title card (chapTitleId 7); regenerated by inject_ch06
                        'graphics/chap_title/chap_title_7.png',
                        # title banner palettes; repointed by inject_title_theme
                        'data/data_A01CC4.s', 'data/data_A21658.s',
                        # opening-montage lore crawl (#43): card slides + LUT timers
                        # + aurora mural incbins, regenerated by inject_opening_montage
                        # on MONTAGE=1 builds
                        'src/opsubtitle.c', 'data/data_opsubtitle.s',
                        # campaign event BGs (#22): inject_backgrounds appends a slot +
                        # enum id + extern decls + incbin symbols per vendored backdrop
                        'data/data_bg.s', 'src/eventscr2.c',
                        'include/constants/backgrounds.h', 'include/bg.h',
                        # world-map tour (#43): drawn-map selector patched in by
                        # inject_world_tour on MONTAGE=1 builds
                        'src/worldmap_rm.c',
                        # battle-map-kind fallback patch (no world map -> STORY)
                        'src/worldmap_path.c',
                        # chapter-title fallback patch (no world map -> ROM chapTitleId,
                        # not a WM skirmish name); regenerated by _patch_chapter_title_wm_fallback
                        'src/chapter_title.c',
                        # lord select (#42): LordSelect_GetPid + force-deploy hook
                        # (eventinfo) and the Seize gate (bmdifficulty); the UnitKill
                        # hook (bmunit.c) and defeat-quote demotions
                        # (data_battlequotes.c) ride files already listed above.
                        # The convoy gate (bmmenu) + the vanilla force-deploy table
                        # (data_event_trigger) are routed through LordSelect too.
                        'src/eventinfo.c', 'src/bmdifficulty.c',
                        'src/bmmenu.c', 'src/data_event_trigger.c',
                        # lord survivability floor (#45 3c): LordFloor_ApplyOnce (eventinfo,
                        # already listed) + its EndPrepScreen call site (prep_sallycursor)
                        'src/prep_sallycursor.c'] + [
                        'graphics/op_subtitle/OpSubtitle_%02d.png' % i
                        for i in range(gen_subtitle_cards.CARD_COUNT)]


# The injection re-emits (very nearly) byte-identical decomp sources every build,
# but the plain writes -- and restore_vanilla_sources' `git checkout` -- bump each
# touched file's mtime. `make` keys off mtime, so it recompiles the translation
# unit AND re-runs the expensive graphics compression / serial banim link even when
# the CONTENT is unchanged from the last build. The dominant costs are the ~354-TU
# recompile cascade from restored widely-included headers (variables.h, ekrbattle.h,
# classes.h) and the serial `arm_compressing_linker.py` rebuild of data_banim.o
# (1752 assets) whenever any banim sheet/motion/agbpal mtime moves.
#
# Fix: snapshot the previous build's injection footprint (content hash + mtime) up
# front, and once injection finishes, rewind the mtime of every file whose bytes are
# byte-for-byte identical. `make` then treats those targets as up to date. This is
# purely an mtime optimisation -- a file is rewound ONLY when its content is
# unchanged, so the compiled ROM is bit-identical. See docs/decisions.md (Build).

def _decomp_footprint():
    """Absolute paths git reports as modified/untracked under the decomp -- i.e. the
    previous build's injection footprint (source files; the .o/.lz/.4bpp build
    outputs are .gitignored, so they are excluded). Never raises: a git hiccup just
    yields an empty snapshot, which preserves correctness and only skips the speed-up."""
    try:
        out = subprocess.run(
            ['git', '-C', DECOMP, 'status', '--porcelain', '-z', '-uall'], env=git_env(),
            check=True, capture_output=True).stdout
    except (subprocess.SubprocessError, OSError):
        return []
    paths = []
    for rec in out.split(b'\0'):
        # porcelain -z record: 'XY <path>' (rename records carry a trailing NUL-
        # separated old path, which harmlessly resolves to a real file too).
        if len(rec) > 3:
            paths.append(os.path.join(
                DECOMP, rec[3:].decode('utf-8', 'surrogateescape')))
    return paths


def _snapshot_mtimes(paths):
    """{abs_path: (mtime_ns, sha1_digest)} for each existing regular file in `paths`."""
    snap = {}
    for p in paths:
        try:
            st = os.stat(p)
            with open(p, 'rb') as f:
                snap[p] = (st.st_mtime_ns, hashlib.sha1(f.read()).digest())
        except OSError:
            pass  # missing / directory / unreadable -> just don't track it
    return snap


def _rewind_unchanged_mtimes(snap, compiled=None):
    """Rewind the mtime of every tracked file whose bytes are unchanged, so make skips its
    (redundant) recompile/recompression. Returns the count rewound. Only ever touches mtime,
    and only for byte-identical content -- never file bytes.

    `compiled` (load_compiled) is consulted first: identical to what `make` last compiled
    means the objects already hold these bytes, whatever injector-only runs wrote since
    (#416). `snap`, the previous injection, is the fallback when there is no such record.
    A tracked file the COMPILE wrote that a checkout has since reverted is put back as the
    compile left it (_restore_compile_output).

    The converse holds too: bytes that DIFFER from what was compiled are left newer than that
    compile. CI pins every tracked source to 2000-01-01 under the last main build's objects
    (#408), so a file injected then but vanilla now would otherwise read as older than the
    object built from its injected bytes."""
    compiled = compiled or {}
    n = 0
    for p in set(snap) | set(compiled):
        try:
            with open(p, 'rb') as f:
                digest = hashlib.sha1(f.read()).digest()
        except OSError:
            continue
        if p in compiled and compiled[p][1] != digest:
            if _restore_compile_output(p, compiled[p]):
                n += 1
                continue
            if os.stat(p).st_mtime_ns <= compiled[p][0]:
                os.utime(p)
                continue
        for base in (compiled, snap):
            if p in base and base[p][1] == digest:
                os.utime(p, ns=(base[p][0], base[p][0]))
                n += 1
                break
    return n


# The rewind above keys off the PREVIOUS INJECTION, which is only what `make` compiled when a
# compile followed it. Anything that injects without compiling -- the fingerprint gate's
# checkout-and-inject per configuration, a manual build_campaign.py, a config switch -- became
# the baseline instead, and the next `make` found every re-emitted file newer than its object:
# 1,529 conversions and all 357 C files, 380s against a 31s warm build (#416). So the Makefile
# records what a SUCCESSFUL compile consumed, and forgets it before every compile (a failed one
# leaves objects no record describes). A forgotten record keeps only the compile's start time.
#
# A compile that bypassed the Makefile would leave the record describing objects it no longer
# matches, so load_compiled voids the record when any file newer than it is neither tracked,
# recorded, nor written by an injection since. Injections accumulate into INJECTED_PATHS until
# the next record for exactly that reason.


def _walk_decomp():
    """(path, mtime_ns) for every decomp file outside git's metadata -- the `.git` directory,
    or the `.git` FILE of a worktree (#408) -- and that is not a link. Links are the toolchain
    build_tree.ensure points into the submodule: neither an injection nor a compile writes one,
    and a fresh checkout makes them newer than any restored record."""
    for root, dirs, files in os.walk(DECOMP):
        dirs[:] = [d for d in dirs if d != '.git']
        for name in files:
            path = os.path.join(root, name)
            if name == '.git' and root == DECOMP:
                continue
            try:
                st = os.lstat(path)
            except OSError:
                continue
            if not stat.S_ISLNK(st.st_mode):
                yield path, st.st_mtime_ns


def _written_since(t0_ns):
    """Every decomp file (outside .git) whose mtime is at or after `t0_ns` -- what this
    injection wrote, including the gitignored copies (the map tilesets' .4bpp) and the
    restored-to-vanilla files that `git status` never lists."""
    return [p for p, mtime_ns in _walk_decomp() if mtime_ns >= t0_ns]


def _injected():
    try:
        with open(INJECTED_PATHS) as fh:
            paths = json.load(fh)
    except (OSError, ValueError):
        return set()
    root = os.path.join(DECOMP, '')     # a list from another tree is not this tree's writes
    return {p for p in paths if p.startswith(root)}


def record_injected(paths):
    """The injector's half of the record: the paths this run wrote, added to what every
    injection since the last compile wrote."""
    paths = sorted(_injected() | set(paths))   # read BEFORE the 'w' open truncates it
    with open(INJECTED_PATHS, 'w') as fh:
        json.dump(paths, fh)


def _tracked():
    """Every file git tracks in the decomp, as absolute paths ([] if git cannot say)."""
    try:
        out = subprocess.run(['git', '-C', DECOMP, 'ls-files', '-z'], env=git_env(),
                             check=True, capture_output=True).stdout
    except (subprocess.SubprocessError, OSError):
        return []
    return [os.path.join(DECOMP, p.decode('utf-8', 'surrogateescape'))
            for p in out.split(b'\0') if p]


def _record_path():
    return os.path.join(COMPILED_DIR, 'record.json')


def _copy_path(digest):
    return os.path.join(COMPILED_DIR, digest.hex())


def _read_record():
    try:
        with open(_record_path()) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def _write_record(record):
    os.makedirs(COMPILED_DIR, exist_ok=True)
    with open(_record_path(), 'w') as fh:
        json.dump(record, fh)


def forget_compiled(now_ns=None):
    """Before a compile: whatever it leaves behind, the old record no longer describes it.
    What remains is when this compile started and which paths the old record covered, for
    record_compiled."""
    old = _read_record()
    if 'compiling_since_ns' in old:
        # The last compile never recorded (it failed): carry ITS lists through, or a failed
        # compile would drop what the one before it regenerated.
        previous, regenerated = old.get('previous', []), old.get('previous_regenerated', [])
    else:
        previous, regenerated = sorted(old.get('files', {})), old.get('regenerated', [])
    _write_record({'compiling_since_ns': time.time_ns() if now_ns is None else now_ns,
                   'previous': previous, 'previous_regenerated': regenerated})


def record_compiled():
    """After a SUCCESSFUL compile: the injected paths as that compile consumed them, plus the
    tracked files a compile regenerated (include/constants/msg.h, via textprocess, only when
    the texts change -- so earlier records' paths carry forward), with a copy of each: a later
    `git checkout` reverts them, and nothing but the compile would write them back."""
    pending = _read_record()
    since = pending.get('compiling_since_ns')
    if since is None:
        return 0
    injected = _injected()
    regenerated = set(pending.get('previous_regenerated', [])) - injected
    for p in _tracked():
        try:
            if p not in injected and os.lstat(p).st_mtime_ns >= since:
                regenerated.add(p)
        except OSError:
            pass
    # The previous record's paths ride forward: this compile consumed them as they are now.
    snap = _snapshot_mtimes(sorted(injected | regenerated | set(pending.get('previous', []))))
    regenerated &= set(snap)
    keep = set()
    for p in regenerated:
        keep.add(_copy_path(snap[p][1]))
        shutil.copyfile(p, _copy_path(snap[p][1]))
    for name in os.listdir(COMPILED_DIR):
        path = os.path.join(COMPILED_DIR, name)
        if path != _record_path() and path not in keep:
            os.remove(path)
    _write_record({'recorded_ns': time.time_ns(), 'tree': DECOMP,
                   'regenerated': sorted(regenerated),
                   'files': {p: [m, d.hex()] for p, (m, d) in snap.items()}})
    try:
        os.remove(INJECTED_PATHS)
    except FileNotFoundError:
        pass
    return len(snap)


def load_compiled():
    """{abs_path: (mtime_ns, sha1_digest)} as the last successful compile consumed them, or
    {} when there is no record or something other than an injection has written the decomp
    since (a compile behind the Makefile's back)."""
    record = _read_record()
    recorded_ns = record.get('recorded_ns')
    if recorded_ns is None or record.get('tree') != DECOMP:
        return {}               # no record, or one describing another tree's objects (#408)
    files = {p: (m, bytes.fromhex(d)) for p, (m, d) in record.get('files', {}).items()}
    accounted = set(files) | _injected() | set(_tracked())
    if any(mtime_ns > recorded_ns and p not in accounted for p, mtime_ns in _walk_decomp()):
        return {}
    return files


def _restore_compile_output(path, recorded):
    """Put back a file the compile wrote, as it wrote it, if the record kept a copy -- which
    it keeps only for tracked files the compile regenerated, never for injected ones."""
    mtime_ns, digest = recorded
    try:
        with open(_copy_path(digest), 'rb') as f:
            data = f.read()
    except OSError:
        return False
    if hashlib.sha1(data).digest() != digest:
        return False
    with open(path, 'wb') as f:
        f.write(data)
    os.utime(path, ns=(mtime_ns, mtime_ns))
    return True


# Where the battle-anim steps write, used ONLY to bootstrap the first entry's pre-state hashes
# (step_cache derives the real path list from what the step actually wrote). `src` and
# `include` are in it because both steps also touch a handful of shared tables there.
BANIM_ROOTS = ('data/banim', 'graphics/banim', 'src', 'include')


def _anim_step_cache(campaign, verbose=True):
    """The cache the two battle-anim steps run through (#309).

    Keyed on everything the ROM is built from EXCEPT the boot flags -- which is precisely the
    claim being made: these steps cannot see a flag, so two configurations of the same source
    must produce the same anim data. The decomp revision is in the key too, because a submodule
    bump moves the tables they append to.

    Falls back to running the steps outright when the key cannot be pinned (no git) or when
    `NO_INJECT_CACHE=1` says to -- the same escape hatch shape as `MX_NO_ROM_CACHE`.
    """
    if os.environ.get('NO_INJECT_CACHE'):
        if verbose:
            print('  (NO_INJECT_CACHE=1 -- battle anims will be re-injected)')
        return step_cache.disabled()
    h = hashlib.sha256()
    h.update(('campaign:' + campaign + '\n').encode())
    try:
        head = subprocess.check_output(['git', '-C', DECOMP, 'rev-parse', 'HEAD'], env=git_env(),
                                       stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, OSError):
        return step_cache.disabled()   # cannot pin the decomp -> recompute rather than guess
    h.update(b'decomp:' + head)
    build_scopes.fingerprint_paths(REPO, build_scopes.ROM_INPUT_PATHS, into=h)
    return step_cache.StepCache(DECOMP, INJECT_CACHE_DIR, h.hexdigest()[:32],
                                roots=BANIM_ROOTS, verbose=verbose)


def _stamp_build_config(campaign, flags):
    """Record which boot flags produced the ROM now in the tree.

    A playtest scenario is bound to a ROM configuration -- a CH04BOOT=1 build cannot
    reach ch02's map -- and the most expensive failure mode in this repo is a scenario
    that FAILs for the honest reason "you are running the wrong ROM". Nothing in the
    .gba says how it was built, so record it here; tools/playtest/matrix.py reads this
    and refuses the run instead of letting mGBA time out for 7 minutes.

    Gitignored: it describes the working tree's build artifact, not the source."""
    # A flag's VALUE is part of the configuration, not just whether it is on. `--ch05-ending`
    # takes an arm name, and three ROMs differ by nothing else -- coerced to bool they all
    # stamped `CH05ENDING: true` and the matrix could not tell them apart, so filming one arm
    # was refused on the grounds that the tree held another. Booleans still stamp as booleans.
    stamp = {'campaign': campaign,
             'flags': {k: (v if isinstance(v, str) else bool(v))
                       for k, v in sorted(flags.items())}}
    try:
        with open(BUILD_STAMP, 'w') as fh:
            json.dump(stamp, fh, indent=2)
    except OSError as exc:      # never fail a build over the stamp
        print('  (could not write %s: %s)' % (BUILD_STAMP, exc))


def restore_vanilla_sources():
    # Restore explicitly from HEAD (not the index): `git checkout -- <file>` pulls from
    # the staging area, so a previously-staged patched file would survive and corrupt the
    # build (e.g. the non-montage monologue-skip leaking into a --montage build). `HEAD --`
    # always resets to the committed vanilla source.
    subprocess.run(['git', '-C', DECOMP, 'checkout', 'HEAD', '--'] + PATCHED_DECOMP_FILES, env=git_env(),
                   check=True)


def normalise_decomp_shebangs(verbose=False):
    """Rewrite the decomp's Linux `#!/bin/python3` shebangs for macOS. Idempotent.

    The decomp's scripts/ ships `#!/bin/python3`, which does not exist on macOS (and /bin is
    SIP-protected, so it cannot be created). ANY `git checkout` in the build tree reverts the
    rewrite: restore_vanilla_sources, the fingerprint gate's reset, a submodule bump. The NEXT
    build then dies on `bad interpreter: No such file or directory`, several minutes in, from
    a Makefile rule that looks unrelated (tsa_generator.py on a BG image). Every build runs
    this, so it is the one place the fix lives; it writes the build tree, never the submodule
    (#408)."""
    if platform.system() != 'Darwin':
        return 0
    fixed = 0
    for path in glob.glob(os.path.join(DECOMP, 'scripts', '**', '*.py'), recursive=True):
        try:
            with open(path, encoding='utf-8') as f:
                text = f.read()
        except (OSError, UnicodeDecodeError):
            continue
        if not text.startswith('#!/bin/python3'):
            continue
        with open(path, 'w', encoding='utf-8') as f:
            f.write('#!/usr/bin/env python3' + text[len('#!/bin/python3'):])
        fixed += 1
    if fixed and verbose:
        print('  normalised %d Linux #!/bin/python3 shebang(s) in fireemblem8u/scripts '
              '(reverted by the last submodule checkout)' % fixed)
    return fixed
