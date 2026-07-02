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
    for rel, d in _chapters():
        status = d.get('status')
        if status not in ('active', 'planned'):
            fail.append('%s: missing/invalid `status` (must be active|planned, got %r)'
                        % (rel, status))
        elif status == 'planned' and d.get('balance_locked'):
            fail.append('%s: status:planned cannot be balance_locked:true -- a planned '
                        'chapter is an ungrounded seed; ground it and flip to active first' % rel)


def _chapters():
    """Yield (relpath, parsed_dict) for every chapter YAML. THE chapter iterator --
    per-chapter gates consume this so the glob + parse-error policy (parse errors
    are check_yaml_parses' job) lives in one place."""
    import yaml
    for f in sorted(glob.glob(os.path.join(REPO, 'campaigns/*/chapters/ch*.yaml'))):
        try:
            d = yaml.safe_load(open(f, encoding='utf-8')) or {}
        except Exception:
            continue
        yield os.path.relpath(f, REPO), d


def _int_pair(v):
    """True for a [col, row] coordinate pair of real ints (bool is an int subtype
    but a YAML `yes` is never a coordinate)."""
    return (isinstance(v, list) and len(v) == 2
            and all(isinstance(c, int) and not isinstance(c, bool) for c in v))


def _unit_entry_violations(rel, kind, entries):
    """Entries of a roster list (player_units / green_allies) must be mappings
    carrying what the injectors index: id/class/level/position ([col, row])."""
    msgs = []
    for g in entries or []:
        if not isinstance(g, dict):
            msgs.append('%s: %s entry %r must be a mapping (id/class/level/'
                        'position ...)' % (rel, kind, g))
            continue
        missing = [k for k in ('id', 'class', 'level', 'position') if k not in g]
        if missing:
            msgs.append('%s: %s entry %r missing %s'
                        % (rel, kind, g.get('id', '?'), ', '.join(missing)))
        elif not _int_pair(g['position']):
            msgs.append('%s: %s entry %r position must be a [col, row] int pair '
                        '(got %r)' % (rel, kind, g['id'], g['position']))
    return msgs


def _chapter_deployment_violations(rel, d):
    """Schema violations for one parsed chapter YAML (pure; unit-tested in
    test_check_chapter_schema.py). The normalized shape (#107, audit 2.2): ALL
    deployment data lives under the `deployment:` block (deploy_limit,
    deploy_slots, note, green_allies); `player_units:` is the one alternative,
    reserved for a fixed-roster chapter with no prep screen (`is_prologue: true`
    gates it structurally, not by convention)."""
    msgs = []
    for legacy in ('deploy_limit', 'deploy_slots'):
        if legacy in d:
            msgs.append('%s: top-level `%s` -- deployment data lives under the '
                        '`deployment:` block (#107 normalized schema)' % (rel, legacy))
    has_pu, has_dep = 'player_units' in d, 'deployment' in d
    if has_pu == has_dep:
        msgs.append('%s: a chapter expresses its roster as EITHER `player_units:` '
                    '(fixed roster, no prep screen) OR a `deployment:` block -- '
                    'found %s' % (rel, 'both' if has_pu else 'neither'))
    if has_pu:
        if not d.get('is_prologue'):
            msgs.append('%s: `player_units:` is the fixed-roster prologue shape -- '
                        'a prep-screen chapter takes a `deployment:` block '
                        '(is_prologue: true gates the exception)' % rel)
        msgs.extend(_unit_entry_violations(rel, 'player_units', d['player_units']))
    if not has_dep:
        return msgs
    dep = d.get('deployment')
    if not isinstance(dep, dict):
        msgs.append('%s: `deployment:` must be a mapping' % rel)
        return msgs
    limit = dep.get('deploy_limit')
    limit_ok = isinstance(limit, int) and not isinstance(limit, bool) and limit > 0
    if limit is not None and not limit_ok:
        msgs.append('%s: deployment.deploy_limit must be a positive int (got %r)'
                    % (rel, limit))
    slots = dep.get('deploy_slots')
    if slots is not None and not isinstance(slots, list):
        msgs.append('%s: deployment.deploy_slots must be a list of [col, row] '
                    'pairs (got %r)' % (rel, slots))
        slots = None
    if slots is not None:
        bad = [s for s in slots if not _int_pair(s)]
        if bad:
            msgs.append('%s: deployment.deploy_slots entries must be [col, row] '
                        'int pairs (first bad: %r)' % (rel, bad[0]))
        # One typo shouldn't cascade: the match rule only fires when the limit
        # itself parsed clean (missing limit still counts as a mismatch).
        if (limit is None or limit_ok) and len(slots) != limit:
            msgs.append('%s: deployment.deploy_slots (%d) must match '
                        'deployment.deploy_limit (%r) -- the slot list IS the cap '
                        'template' % (rel, len(slots), limit))
    if d.get('status') == 'active' and limit is None:
        msgs.append('%s: an active chapter with a `deployment:` block needs a '
                    'machine-readable deployment.deploy_limit (prose notes are for '
                    'planned seeds)' % rel)
    msgs.extend(_unit_entry_violations(rel, 'deployment.green_allies',
                                       dep.get('green_allies')))
    return msgs


def check_chapter_deployment_schema(fail):
    """The normalized chapter deployment schema (#107): kills the audit-2.2 drift
    where no two chapters expressed their roster the same way (four shapes across
    9 files). The injectors and difficulty.py read ONE shape; this gate keeps new
    chapters on it."""
    for rel, d in _chapters():
        fail.extend(_chapter_deployment_violations(rel, d))


# ── Injection ordering (audit 2.6 / #110) ─────────────────────────────────────
# The documented MUST-precede pairs in build_campaign.main(). These lived only in
# comments ("MUST precede inject_prologue"); one reorder breaks the build at its
# most expensive point. check_engine_guards_present pins presence; this pins order.
INJECTION_ORDER = [
    ('_inject_lord_select_engine', '_inject_lord_floor_engine',
     'lord floor anchors on lord-select\'s LordSelect_GetPid'),
    ('inject_map_sprites', 'inject_enemy_class_reskins',
     'reskins consume the SMS ids map-sprite injection creates'),
    ('inject_enemy_class_reskins', 'inject_ch01',
     "ch01's goblin grunts ride the reskinned clone classes"),
    ('inject_winter_tileset', 'inject_ch01',
     'chapter maps register against the tileset asset-table labels'),
    ('inject_winter_tileset', 'inject_prologue',
     'the prologue map registers against the tileset asset-table labels'),
    ('inject_ch01', 'inject_prologue',
     'inject_prologue overwrites the slot-1 Seize goal template inject_ch01 copies'),
]


def _injection_call_sequence(text):
    """First-call order of top-level steps in build_campaign.main(). Textual order
    == execution order there (the only branch chooses BETWEEN later steps, never
    hoists one earlier)."""
    m = re.search(r'\ndef main\(\):.*', text, re.S)
    if not m:
        return []
    names = re.findall(r'^\s+(?:engine_hooks\.)?(\w+)\(', m.group(0), re.M)
    seen, order = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            order.append(n)
    return order


def _injection_order_violations(order):
    msgs = []
    pos = {n: i for i, n in enumerate(order)}
    for before, after, why in INJECTION_ORDER:
        missing = [n for n in (before, after) if n not in pos]
        if missing:
            msgs.append('injection-order constraint references unknown step(s) %s '
                        '-- renamed/removed? update INJECTION_ORDER in check.py'
                        % ', '.join(missing))
        elif pos[before] > pos[after]:
            msgs.append('build_campaign.main(): %s must run before %s -- %s'
                        % (before, after, why))
    return msgs


def check_injection_order(fail):
    """Injection steps run in a dependency order that used to live only in main()'s
    comments (audit 2.6): pin the documented MUST-precede pairs."""
    path = os.path.join(REPO, 'tools', 'build_campaign.py')
    fail.extend(_injection_order_violations(
        _injection_call_sequence(open(path, encoding='utf-8').read())))


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
             'the glass picks become traps'),
            ('_patch_banim_character_unique',
             'the #65 per-character battle-anim hook (combat -> GetBattleAnimationId_WithUnique, '
             'reading _u25); without it every PC custom anim silently reverts to its class anim'),
            ('_patch_banim_palette_custom_guard',
             'the #65 GetBanimPalette guard (a custom appended banim keeps its OWN palette); '
             'without it a custom-anim unit on an archer/sniper class mis-loads the vanilla bow '
             'palette -- the RBG cyan mis-render')):
        if ('def %s(' % fn) not in eh:
            fail.append('engine hook %s() not DEFINED in tools/inject/engine_hooks.py '
                        '-- would silently drop %s (see docs/decisions.md)' % (fn, mechanic))
        if ('engine_hooks.%s(' % fn) not in bc:
            fail.append('engine hook %s() never CALLED (engine_hooks.%s(...)) from '
                        'tools/build_campaign.py -- would silently drop %s '
                        '(see docs/decisions.md)' % (fn, fn, mechanic))


# ── Engine campaign-agnosticism (the Engine/Content Boundary Rule, mechanized) ─────
# Hand-written engine code must never name a campaign character: build_campaign INJECTS
# names into the fireemblem8u working tree at build time, so the committed engine sources
# stay reusable for any campaign ("braulo" belongs in YAML, not a .c). This was a
# code-review rule (CLAUDE.md Engine/Content Boundary Rule); now a gate. Scope = what WE
# author -- engine/** + the engine-hook injectors; the fireemblem8u submodule is vanilla +
# build-injected and never committed by us, so it's deliberately excluded. Decision:
# docs/decisions.md -> Coordination model (mechanize the name-in-C check).
ENGINE_SOURCE_GLOBS = ('engine/**/*.c', 'engine/**/*.h', 'engine/**/*.s',
                       'tools/inject/engine_hooks.py', 'tools/inject/decomp.py')


def _campaign_character_ids():
    """Lowercased character ids from every pcs/npcs YAML -- the campaign-specific tokens
    engine code must not hardcode. Read off the `id:` line so the lightweight checks job
    needs no YAML load."""
    ids = set()
    for sub in ('pcs', 'npcs'):
        for f in glob.glob(os.path.join(REPO, 'campaigns/**', sub, '*.yaml'), recursive=True):
            m = re.search(r'(?m)^id:\s*([A-Za-z0-9_-]+)', open(f, encoding='utf-8').read())
            if m:
                ids.add(m.group(1).lower())
    return ids


def _engine_name_hits(ids, text):
    """(token, lineno) for each campaign character id named in `text`. Word-boundaried and
    case-insensitive, so 'brie' never matches 'brief' but 'BRAULO' in a comment is caught.
    Pure (no I/O) so it's unit-tested directly."""
    if not ids:
        return []
    pat = re.compile(r'\b(' + '|'.join(re.escape(i) for i in sorted(ids)) + r')\b', re.I)
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        m = pat.search(line)
        if m:
            hits.append((m.group(1).lower(), n))
    return hits


def check_engine_campaign_agnostic(fail):
    ids = _campaign_character_ids()
    if not ids:
        return
    for g in ENGINE_SOURCE_GLOBS:
        for path in glob.glob(os.path.join(REPO, g), recursive=True):
            rel = os.path.relpath(path, REPO)
            for tok, n in _engine_name_hits(ids, open(path, encoding='utf-8').read()):
                fail.append('engine: %s:%d names campaign character %r -- engine code must be '
                            'campaign-agnostic; inject it from YAML (CLAUDE.md Engine/Content '
                            'Boundary Rule)' % (rel, n, tok))


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


# ── Desk map (advisory since feature-flow) ────────────────────────────────────────
# Which "desk" historically owns which file. Since 2026-06-24 this is an ADVISORY signal
# (check_lane_ownership notes a cross-desk change), NOT a gate -- the hard invariant is
# check_engine_campaign_agnostic. Anything not listed is shared (tools/inject/**, docs/**,
# HANDOFF.md, CLAUDE.md, Makefile, ...). Decision: docs/decisions.md -> Coordination model (#66).
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
    """ADVISORY since 2026-06-24 (feature-flow, decisions.md -> Coordination model): NOT a gate.
    Fixed lanes were retired because features routinely span the engine/content seam (e.g. an
    anim capture = its record* scenario + the sandbox build it fires on), and a hard glob block
    sawed such a feature in half. So this no longer fails -- it just surfaces, on a legacy
    `inst/<track>` branch, that a change touches the other desk's historical files, so the PR
    review names the cross-desk contract. The HARD invariant is now check_engine_guards_present
    (the 5 engine hooks); desk ownership is reviewed at the PR. The glob map (above) is the seed
    of the desk map. Dormant on `feat/*` branches (no lane), which is the steady state."""
    for path, owner in _lane_violations(_current_lane(), _changed_files()):
        print('  note: %s is historically %s-side -- if this PR spans desks, name the contract in review'
              % (path, owner))


def main():
    fail = []
    for check in (check_python_compiles, check_tests_pass, check_yaml_parses,
                  check_chapter_status, check_chapter_deployment_schema,
                  check_injection_order,
                  check_tool_refs_exist, check_no_dead_concepts,
                  check_generated_indexes_fresh, check_engine_guards_present,
                  check_engine_campaign_agnostic,
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
