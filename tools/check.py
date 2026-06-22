#!/usr/bin/env python3
"""Repo drift guard. ONE source of check logic, run by CI, the git pre-commit hook,
and `make check`. Keeps doc/plan drift from landing.

Catches:
  1. Python tooling that doesn't compile.
  2. Campaign YAML that doesn't parse.
  3. Docs referencing a tools/<x>.py|rb that doesn't exist.
  4. Resurrected "dead concepts" -- abandoned tool names, dead code symbols, retired
     implementation phrases -- in any doc except decisions.md (the ADR log that is
     *supposed* to record what we dropped).

What it does NOT catch: arbitrary prose that contradicts the code without using a
known-dead term. The defense there is single source of truth (link, don't restate)
and the Definition of Done -- see docs/decisions.md Working Conventions.

Exit 0 = clean, 1 = drift found. Run from the repo root.
"""

import glob
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Docs that carry prose facts (decisions.md is handled specially per-check).
DOC_GLOBS = ['docs/**/*.md', 'CLAUDE.md', 'README.md', 'HANDOFF.md']

# Terms that are NEVER legitimate in vision/ops docs: abandoned tools, dead code
# symbols, retired implementation phrases. decisions.md is EXEMPT (its ADRs record
# what we abandoned, e.g. "supersedes the flat-E placeholder"). Context-dependent
# terms (Event Assembler / devkitARM / "damage-type") are intentionally NOT here --
# they appear legitimately in negation ("no Event Assembler").
DEAD_CONCEPTS = [
    r'build-campaign\.ts', r'build-events\.ts', r'pull-srd', r'map-class\.ts',
    r'srd-snapshot', r'open5e-snapshot', r'CLASS_WEAPON', r'WPN_EXP_E',
    r'zeroed.{0,3}growth', r'flat-?E rank', r'pure[- ]class growth',
    r'gen-chapter-index\.rb', r'gen-class-index\.rb',  # ported to Python 2026-06-09
]


def _docs():
    out = []
    for g in DOC_GLOBS:
        out += glob.glob(os.path.join(REPO, g), recursive=True)
    return [d for d in out if os.path.isfile(d)]


def check_python_compiles(fail):
    import compileall
    if not compileall.compile_dir(os.path.join(REPO, 'tools'), quiet=1):
        fail.append('tools/ has a Python file that does not compile')


def check_tests_pass(fail):
    """Run the Python unit tests (tools/test_*.py). The combat math in fe_combat.py is
    the difficulty engine's arbiter -- a silent regression there mis-grades every chapter."""
    import subprocess
    # Several tests read the FE8 decomp via `git -C fireemblem8u show HEAD:...`
    # (vanilla_decomp_text). When the submodule isn't checked out -- the lightweight CI
    # `checks` job omits it (2.3GB) -- they cannot run; that job instead leans on CI's
    # `build` job (submodule + deps), which runs `make test`. Skip here so the drift guard
    # stays decoupled from the heavy checkout. Locally the submodule is present, so the
    # pre-commit hook and `make check` still run the full suite.
    if not os.path.isdir(os.path.join(REPO, 'fireemblem8u', 'src')):
        print('check_tests_pass: skipping unit tests (fireemblem8u submodule not checked '
              'out; the CI build job runs `make test`)')
        return
    for t in sorted(glob.glob(os.path.join(REPO, 'tools', 'test_*.py'))):
        r = subprocess.run([sys.executable, t], capture_output=True, text=True)
        if r.returncode != 0:
            tail = (r.stderr or r.stdout).strip().splitlines()
            fail.append('unit tests fail: %s (%s)' % (
                os.path.relpath(t, REPO), tail[-1] if tail else 'see output'))


def check_yaml_parses(fail):
    import yaml
    for f in glob.glob(os.path.join(REPO, 'campaigns/**/*.yaml'), recursive=True):
        try:
            yaml.safe_load(open(f, encoding='utf-8'))
        except Exception as e:
            fail.append('YAML does not parse: %s (%s)' % (os.path.relpath(f, REPO), e))


def check_chapter_status(fail):
    """Every chapter YAML must declare its maturity: `status: active|planned`. Vertical-slice
    workflow -- `planned` chapters are non-authoritative brainstorm SEED (enemy roster/levels
    re-grounded against vanilla + party data on arrival), `active` ones are built/in-progress
    with grounded combat data. Invariant: a `planned` chapter must NOT be `balance_locked: true`
    -- you cannot lock the parity of a chapter whose enemies are an ungrounded sketch (that
    half-state is exactly what makes the difficulty curve and readers treat a seed as truth)."""
    import yaml
    for f in sorted(glob.glob(os.path.join(
            REPO, 'campaigns/*/chapters/ch*.yaml'))):
        rel = os.path.relpath(f, REPO)
        try:
            d = yaml.safe_load(open(f, encoding='utf-8')) or {}
        except Exception:
            continue                       # parse errors are check_yaml_parses' job
        status = d.get('status')
        if status not in ('active', 'planned'):
            fail.append('%s: missing/invalid `status` (must be active|planned, got %r)'
                        % (rel, status))
        elif status == 'planned' and d.get('balance_locked'):
            fail.append('%s: status:planned cannot be balance_locked:true -- a planned '
                        'chapter is an ungrounded seed; ground it and flip to active first' % rel)


def check_tool_refs_exist(fail):
    pat = re.compile(r'tools/([\w-]+\.(?:py|rb))')
    for d in _docs():
        for m in pat.findall(open(d, encoding='utf-8').read()):
            if not os.path.isfile(os.path.join(REPO, 'tools', m)):
                fail.append('%s references tools/%s which does not exist'
                            % (os.path.relpath(d, REPO), m))


def check_no_dead_concepts(fail):
    pat = re.compile('|'.join(DEAD_CONCEPTS), re.I)
    for d in _docs():
        if os.path.basename(d) == 'decisions.md':
            continue
        for i, line in enumerate(open(d, encoding='utf-8'), 1):
            m = pat.search(line)
            if m:
                fail.append('dead concept %r in %s:%d'
                            % (m.group(0), os.path.relpath(d, REPO), i))


def check_generated_indexes_fresh(fail):
    """docs/CHAPTERS.md + docs/CLASSES.md are GENERATED from campaign YAML; a
    hand edit or a YAML change without a regen is silent drift. Regenerate in
    memory and diff against the committed file."""
    sys.path.insert(0, os.path.join(REPO, 'tools'))
    import gen_chapter_index
    import gen_class_index
    for mod, rel in ((gen_chapter_index, 'docs/CHAPTERS.md'),
                     (gen_class_index, 'docs/CLASSES.md')):
        path = os.path.join(REPO, rel)
        want = mod.generate()[0]
        have = open(path, encoding='utf-8').read() if os.path.isfile(path) else None
        if have != want:
            fail.append('%s is stale vs the YAML -- regenerate: python3 tools/%s.py'
                        % (rel, mod.__name__))


def check_engine_guards_present(fail):
    """Engine-hardening guards + campaign-engine hooks must stay wired into the build.

    The prologue garbage-band crash (debrief in docs/decisions.md) was a chapter whose
    "lord" rides a non-LORD-class slot: FE8's chapter-start cursor centering derefs a NULL
    leader unit, parks the cursor off-map, and an out-of-bounds terrain read runs the text
    decoder away into gBmSt. Our whole cast uses non-lord slots, so EVERY chapter needs
    these two campaign-agnostic guards in build_campaign.py. Removing either silently
    re-introduces the crash, so guard their presence here. (The patches themselves also
    fail the build if the decomp source form changes -- see their `if orig not in text`.)
    The campaign-engine hooks below are likewise build-time string-replaces that leave no
    other trace, so a refactor could silently drop a shipped mechanic -- guard them too.
    """
    # The hooks now live in tools/inject/engine_hooks.py (pipeline-owned) and are
    # orchestrated from tools/build_campaign.py (#50 file seam). Two precise checks per
    # hook: it must be DEFINED in the engine-hooks module AND CALLED from the orchestrator.
    # A refactor that drops either side fails here loudly.
    eh = open(os.path.join(REPO, 'tools', 'inject', 'engine_hooks.py'), encoding='utf-8').read()
    bc = open(os.path.join(REPO, 'tools', 'build_campaign.py'), encoding='utf-8').read()
    for fn, mechanic in (
            ('_patch_player_start_cursor_guard',
             'the prologue garbage-band / off-map-cursor crash guard'),
            ('_patch_terrain_name_guard',
             'the out-of-bounds terrain-name read guard'),
            ('_patch_battle_map_kind_fallback',
             'the no-world-map STORY fallback for slot-2+ chapters'),
            ('_inject_lord_select_engine',
             'the #42 lord-select mechanic (GetPid / force-deploy / Seize / game-over '
             'keyed to the chosen lead)'),
            ('_inject_lord_floor_engine',
             'the #45 lord survivability-floor one-time HP/Def/Res top-up, without which '
             'the glass picks become traps')):
        if ('def %s(' % fn) not in eh:
            fail.append('engine hook %s() not DEFINED in tools/inject/engine_hooks.py '
                        '-- would silently drop %s (see docs/decisions.md)' % (fn, mechanic))
        if ('engine_hooks.%s(' % fn) not in bc:
            fail.append('engine hook %s() never CALLED (engine_hooks.%s(...)) from '
                        'tools/build_campaign.py -- would silently drop %s '
                        '(see docs/decisions.md)' % (fn, fn, mechanic))


# ── Save-layout stability (so testers can carry their .sav across builds) ──────────
# A battery .sav is accepted on a new build iff its validity magics + checksum still
# match (bmsave-lib.c:125-128, ReadSaveBlockInfo). Those magics are constant, so a
# rebuild alone never invalidates a save -- the ONLY thing that can is the save-block
# LAYOUT shifting, which moves the old bytes to wrong offsets and fails the checksum.
# struct GameSaveBlock's size is driven by two array dims; pin them (and the magics) so
# the day a submodule bump grows the roster/chapter arrays, CI goes red and that drop
# (and only that drop) needs the #59 starter-save fallback. Decision: docs/decisions.md
# -> Playtest distribution: carry-forward saves. Source-only grep (no compile), so it
# self-skips with the rest when the submodule is absent.
PINNED_SAVE_LAYOUT = {
    'BWL_ARRAY_NUM': 0x46,   # roster size  -> sizeof(GameSaveBlock.pidStats)
    'WIN_ARRAY_NUM': 0x30,   # chapter count -> sizeof(GameSaveBlock.chapterStats)
    'SAVEMAGIC16': 0x200A,   # save-block validity magic (constant)
    'SAVEMAGIC32': 0x40624,  # save-block validity magic (constant)
}


def _parse_save_layout_constants(text):
    """Pull the pinned save-layout constants out of decomp header text. Handles both the
    `#define BWL_ARRAY_NUM 0x46` form and the `SAVEMAGIC16 = 0x200A,` enum form. The word
    boundary keeps SAVEMAGIC32 from capturing SAVEMAGIC32_ARENA. Missing names are omitted."""
    out = {}
    for name in PINNED_SAVE_LAYOUT:
        m = re.search(r'\b' + re.escape(name) + r'\b\s*=?\s*(0x[0-9A-Fa-f]+|\d+)', text)
        if m:
            out[name] = int(m.group(1), 0)
    return out


def _save_layout_drift(found):
    """Drift messages comparing parsed constants `found` against PINNED_SAVE_LAYOUT."""
    msgs = []
    for name, want in PINNED_SAVE_LAYOUT.items():
        if name not in found:
            msgs.append('save-layout constant %s not found in the decomp -- header '
                        'restructured; testers\' saves may break (see #59)' % name)
        elif found[name] != want:
            msgs.append('save-layout constant %s changed (%#x -> %#x): struct GameSaveBlock '
                        'shifts, so old battery saves fail the checksum and auto-wipe. Ship a '
                        'per-release starter save for this drop (#59 fallback) and re-pin here.'
                        % (name, want, found[name]))
    return msgs


def check_save_layout_stable(fail):
    """Guard that a tester's battery .sav still loads on a new build (#59 carry-forward)."""
    header = os.path.join(REPO, 'fireemblem8u', 'include', 'bmsave.h')
    if not os.path.isfile(header):
        print('check_save_layout_stable: skipping (fireemblem8u submodule not checked out)')
        return
    found = _parse_save_layout_constants(open(header, encoding='utf-8').read())
    fail.extend(_save_layout_drift(found))


# ── Engine/content lane ownership (the seam, enforced) ────────────────────────────
# Single source of truth for which track may edit which file (mirrors the "You own"
# lists in HANDOFF-content.md / HANDOFF-pipeline.md). Anything not listed is SHARED
# (either lane may edit: tools/inject/**, docs/**, HANDOFF*, CLAUDE.md, Makefile, ...).
# Decision: docs/decisions.md -> Engine/content file seam (enforcement). Issue #55.
PIPELINE_EXCLUSIVE_FILES = {
    'tools/difficulty.py', 'tools/fe_combat.py', 'tools/check.py', 'tools/build.sh',
    'tools/worktree-setup.sh', 'tools/test_difficulty.py', 'tools/test_fe_combat.py',
    'tools/test_check_lanes.py', 'tools/test_check_save_layout.py',
    'tools/make_bps.py', 'tools/test_make_bps.py', 'tools/test_llm_player.py',
}
PIPELINE_EXCLUSIVE_DIRS = ('tools/playtest/', 'tools/hooks/', '.github/workflows/')
CONTENT_EXCLUSIVE_FILES = {
    'tools/build_campaign.py', 'tools/portrait_tool.py', 'tools/map_sprite_tool.py',
    'tools/ref_to_bust.py', 'tools/test_build_campaign.py',
}
CONTENT_EXCLUSIVE_DIRS = ('campaigns/',)


def _file_lane(path):
    """The lane that exclusively owns `path` ('pipeline'|'content'), or None if shared."""
    path = path.replace(os.sep, '/')
    if path in PIPELINE_EXCLUSIVE_FILES or path.startswith(PIPELINE_EXCLUSIVE_DIRS):
        return 'pipeline'
    if path in CONTENT_EXCLUSIVE_FILES or path.startswith(CONTENT_EXCLUSIVE_DIRS):
        return 'content'
    return None


def _lane_violations(lane, changed_files):
    """(path, owner) for each changed file the current `lane` may NOT edit. Enforced only when
    you are IN a lane -- i.e. a worktree on an inst/<track> branch, which is where two instances
    run concurrently and could collide. The primary checkout has no lane: it's the unrestricted
    integration/solo tree (only ever one of you there), so nothing is a violation. Shared files
    never violate from either lane."""
    if lane is None:
        return []
    out = []
    for path in changed_files:
        owner = _file_lane(path)
        if owner is not None and owner != lane:
            out.append((path, owner))
    return out


def _git(args):
    import subprocess
    try:
        r = subprocess.run(['git'] + args, cwd=REPO, capture_output=True, text=True)
        return r.stdout.strip()
    except Exception:
        return ''


def _lane_of(name):
    if 'content' in name:
        return 'content'
    if 'pipeline' in name:
        return 'pipeline'
    return None


def _current_lane():
    """This worktree's lane. Branch first -- the `inst/<track>` branch is inherently
    per-worktree, so it self-identifies even though .git/config is shared. In a CI pull
    request the branch is detached, so GITHUB_HEAD_REF (the PR source branch) is used.
    `manchego.lane` is the explicit fallback (e.g. the primary checkout during bootstrapping)."""
    head_ref = os.environ.get('GITHUB_HEAD_REF', '')       # set only in a CI PR
    if head_ref.startswith('inst/'):
        return _lane_of(head_ref)
    branch = _git(['rev-parse', '--abbrev-ref', 'HEAD'])
    if branch.startswith('inst/'):
        return _lane_of(branch)
    lane = _git(['config', 'manchego.lane'])
    return lane if lane in ('pipeline', 'content') else None


def _diff_names(base):
    return [l for l in _git(['diff', '--name-only', base, 'HEAD']).splitlines() if l.strip()]


def _changed_files():
    """Files to check: staged (pre-commit), else the diff vs the base. In a CI pull request
    that base is origin/<GITHUB_BASE_REF>; on a local inst/* branch it's the merge-base with
    main. Empty on main with nothing staged -> the guard no-ops on the integration tree."""
    staged = [l for l in _git(['diff', '--cached', '--name-only']).splitlines() if l.strip()]
    if staged:
        return staged
    base_ref = os.environ.get('GITHUB_BASE_REF', '')       # set only in a CI PR
    if base_ref:
        base = _git(['merge-base', 'HEAD', 'origin/' + base_ref]) or 'origin/' + base_ref
        return _diff_names(base)
    branch = _git(['rev-parse', '--abbrev-ref', 'HEAD'])
    if branch.startswith('inst/'):
        base = _git(['merge-base', 'HEAD', 'origin/main']) or _git(['merge-base', 'HEAD', 'main'])
        if base:
            return _diff_names(base)
    return []


def check_lane_ownership(fail):
    """Block a commit that crosses the engine/content seam (#55) when you're in a lane worktree
    (branch inst/<track>). The primary checkout is unrestricted integration. `git commit
    --no-verify` overrides for a deliberate exception."""
    lane = _current_lane()
    for path, owner in _lane_violations(lane, _changed_files()):
        fail.append('lane: %s is %s-owned, but this worktree is the %s lane -- coordinate via '
                    'an issue instead of crossing the seam (--no-verify to override)'
                    % (path, owner, lane))


def main():
    fail = []
    for check in (check_python_compiles, check_tests_pass, check_yaml_parses,
                  check_chapter_status, check_tool_refs_exist, check_no_dead_concepts,
                  check_generated_indexes_fresh, check_engine_guards_present,
                  check_save_layout_stable, check_lane_ownership):
        check(fail)
    if fail:
        print('DRIFT (%d):' % len(fail))
        for f in fail:
            print('  - ' + f)
        return 1
    print('drift check: clean')
    return 0


if __name__ == '__main__':
    sys.exit(main())
