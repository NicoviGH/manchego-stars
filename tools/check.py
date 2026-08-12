#!/usr/bin/env python3
"""Repo drift guard. ONE source of check logic, run by CI, the git pre-commit hook,
and `make check`. Keeps doc/plan drift from landing.

Catches (main() is the authoritative list -- one check_* per gate): compile/parse
gates (Python tooling, unit tests, campaign YAML), doc/comment drift (dangling
tools/docs references, resurrected "dead concepts" -- abandoned tool names, dead
symbols, retired implementation phrases -- everywhere except decisions.md, the ADR
log that is *supposed* to record what we dropped, and test_* fixtures), generated
indexes freshness, chapter status/deployment schema, injection order, the
engine-hook guards, the engine/content boundary, save-layout stability, and
advisory lane ownership.

What it does NOT catch: arbitrary prose that contradicts the code without using a
known-dead term. The defense there is single source of truth (link, don't restate)
and the Definition of Done -- see docs/decisions.md Working Conventions.

Exit 0 = clean, 1 = drift found. Run from the repo root.
"""

import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Docs that carry prose facts (decisions.md is handled specially per-check).
DOC_GLOBS = ['docs/**/*.md', 'CLAUDE.md', 'README.md', 'HANDOFF.md']

# Terms that are NEVER legitimate in vision/ops docs OR hand-written code comments:
# abandoned tools, dead code symbols, retired implementation phrases. decisions.md
# and this file are EXEMPT (the ADR log records what we dropped; this list names it).
# Context-dependent terms (Event Assembler / devkitARM / "damage-type") are
# intentionally NOT here -- they appear legitimately in negation ("no Event
# Assembler").
#
# REGISTRY DISCIPLINE (decisions.md 2026-07-02 "Comments are testimony"): when a
# change RETIRES a mechanism or term, add its key phrases here in the same commit.
# The 2026-07-02 stale-comment incident ("zeroed personal growths" surviving in a
# build_campaign.py header long after donor-parity replaced it, then leaking into
# an ADR) happened because this scan covered docs only and the growth patterns were
# too narrow to match the comment's phrasing -- both fixed below.
DEAD_CONCEPTS = [
    r'build-campaign\.ts', r'build-events\.ts', r'pull-srd', r'map-class\.ts',
    r'srd-snapshot', r'open5e-snapshot', r'CLASS_WEAPON', r'WPN_EXP_E',
    r'zeroed.{0,24}growths?', r'flat-?E rank', r'pure[- ]class (?:growth|rate)',
    r'gen-chapter-index\.rb', r'gen-class-index\.rb',  # ported to Python 2026-06-09
    # retired by the 2026-07-02 comment sweep:
    r'clone_into',                     # #65 clone-class approach -> per-character _u25
    r'tileset_stem\s*=',               # _register_chapter_map reads the layout's stamp
    r'BATTLE_FOLLOWUP_THRESHOLD',      # misnomer; real: BATTLE_FOLLOWUP_SPEED_THRESHOLD
    # Marty's "spore covenant" (2026-07-29): a ch05 villain-foil thread we drifted away
    # from while writing the chapter and never actually used in a beat. Retired so it
    # can't creep back into his character. Marty's voice is lore/marty.md Voice, full stop.
    r'spore covenant', r'composter vs\.? the taxidermist',
    r'two necromancers, opposite covenants',
    # retired by #203 (2026-08-01): ch04's parley converts the wolf pack IN PLACE -- one
    # CHECK_ALIVE-guarded CUSN per wolf -- so there is no clear-and-reload to describe, and
    # the green allies are Mauthe Doogs in the NPC palette, not a Lycanroc table.
    r'pack table[- ]swaps?', r'table[- ]swaps? the (?:\d+ |five )?generic',
    r'green Lycanroc (?:NPC )?(?:pack|all(?:y|ies))',
    # retired by #220 (2026-08-03): common playtest mechanics are state-driven.
    r'bootToMap.{0,40}alternat(?:e|es|ing).{0,12}(?:A.{0,3}START|START.{0,3}A)',
    r'chooseAttack.{0,50}row 0 blind',
    # retired by #238 (2026-08-06): the base-tiles grid comes from SYM like every other
    # symbol. The literal it held drifted and made ch03's doors and chests read as broken.
    r'GBMMAPBASETILES_ADDR',
    # NOT registered here: `hasPrepScreen`. It IS a dead field (FE7 leftover, chapterdata.h:37 --
    # false for every chapter, including ones that plainly have prep) and citing it as evidence is
    # exactly the mistake that produced a bogus "our prep is a divergence" claim on 2026-07-29.
    # But `build_campaign.py` already documents it as dead in the docstring a reader would hit
    # first, and DEAD_CONCEPTS would flag that warning too -- a guard that rejects its own warning
    # is worse than none. The durable fix is a pointer in CLAUDE.md's Source-of-Truth table.
]

# Hand-written source whose comments carry doctrine -- the same drift surface as
# docs. The decomp submodule, generated artifacts, and caches are not ours to lint.
CODE_GLOBS = ['tools/*.py', 'tools/inject/*.py', 'tools/playtest/*.py',
              'tools/playtest/*.lua', 'tools/*.sh', 'tools/playtest/*.sh',
              'engine/**/*.c', 'engine/**/*.h', 'Makefile']


def _docs():
    out = []
    for g in DOC_GLOBS:
        out += glob.glob(os.path.join(REPO, g), recursive=True)
    return [d for d in out if os.path.isfile(d)]


def _handwritten_sources():
    out = []
    for g in CODE_GLOBS:
        out += glob.glob(os.path.join(REPO, g), recursive=True)
    # check.py hosts the DEAD_CONCEPTS registry and test_* files quote dead phrases
    # as regression fixtures -- both exempt, like decisions.md.
    me = os.path.abspath(__file__)
    return [p for p in out
            if os.path.isfile(p) and os.path.abspath(p) != me
            and not os.path.basename(p).startswith('test_')]


def check_python_compiles(fail):
    import compileall
    if not compileall.compile_dir(os.path.join(REPO, 'tools'), quiet=1):
        fail.append('tools/ has a Python file that does not compile')


def check_tests_pass(fail):
    """Run the Python unit tests (tools/test_*.py AND tools/playtest/test_*.py). The combat
    math in fe_combat.py is the difficulty engine's arbiter -- a silent regression there
    mis-grades every chapter.

    The playtest directory was outside this glob until 2026-08-06 (#236), so its Python
    tests -- the pure formatting/diff logic that is supposed to keep the emulator out of
    the loop -- ran only when someone invoked them by hand. `unittest discover -s tools`
    does not reach them either (the directory is not an importable package), so the glob
    is the only gate. Coverage nothing runs is not coverage."""
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
    for t in sorted(glob.glob(os.path.join(REPO, 'tools', 'test_*.py'))
                    + glob.glob(os.path.join(REPO, 'tools', 'playtest', 'test_*.py'))):
        r = subprocess.run([sys.executable, t], capture_output=True, text=True)
        if r.returncode != 0:
            tail = (r.stderr or r.stdout).strip().splitlines()
            fail.append('unit tests fail: %s (%s)' % (
                os.path.relpath(t, REPO), tail[-1] if tail else 'see output'))


# gen_symbols.py outputs, gitignored and absent in CI -- a gate that fails on a missing
# generated file is a gate nobody can keep green.
GENERATED_LUA = ('tools/playtest/symbols.lua', 'tools/playtest/procscr.lua')

# DISCOVERED, not listed: harness.lua dofiles nine chunks and the hand-written tuple named
# four, so a syntax error in recorder.lua or liveness.lua killed every scenario with this
# gate green (#241). Same defect #138 closed for chapters -- a list you must remember to
# update is not a gate.
LUA_CHUNKS = tuple(sorted(
    os.path.relpath(p, REPO)
    for p in glob.glob(os.path.join(REPO, 'tools', 'playtest', '*.lua'))
    if os.path.relpath(p, REPO) not in GENERATED_LUA))


def lua_compile_error(path):
    """None if the chunk COMPILES, else the interpreter's message.

    Two traps, both of which make this silently useless if you get them wrong:
      * `loadfile` returns `nil, err`; it does not raise. The probe must test the
        result explicitly or it exits 0 on a broken file and asserts nothing.
      * the path goes in through the environment, not as an argv tail. `lua -e CODE
        FILE` treats FILE as a script to *execute*, so the probe would run harness.lua
        -- which fails on missing emulator globals and looks like a compile error.
    """
    env = dict(os.environ, LUA_CHUNK_PATH=path)
    probe = ('local f, err = loadfile(os.getenv("LUA_CHUNK_PATH"))\n'
             'if not f then io.stderr:write(tostring(err)) os.exit(1) end\n')
    r = subprocess.run([shutil.which('lua') or 'lua', '-e', probe],
                       capture_output=True, text=True, env=env)
    if r.returncode == 0:
        return None
    detail = (r.stderr or r.stdout).strip().splitlines()
    return detail[-1] if detail else 'unknown error'


def check_lua_chunks_load(fail):
    """The playtest Lua must COMPILE. Nothing else checks this: check_playtest_matrix
    only parses harness.lua textually for scenario names, and a syntax/limit error is
    invisible until mGBA loads it minutes later.

    The specific hazard is Lua's ceiling of 200 local variables per function. harness.lua
    is one ~6,700-line main chunk sitting AT that ceiling, so a routine edit can cross it
    -- and crossing it kills every scenario simultaneously, a total outage rather than a
    single red row. #236 crossed it and caught it only by hand. How much room is actually
    left is MEASURED by check_lua_local_headroom below, never written down.

    loadfile COMPILES without executing, so the emulator globals the chunk needs at
    runtime (emu, SYM, PLAYTEST_*) are irrelevant here."""
    if shutil.which('lua') is None:
        # CI's lightweight `checks` job has no Lua, same reasoning as check_tests_pass.
        print('check_lua_chunks_load: skipping (no lua on PATH; brew install lua)')
        return
    for rel in LUA_CHUNKS:
        err = lua_compile_error(os.path.join(REPO, rel))
        if err:
            fail.append('%s does not compile: %s' % (rel, err))


def lua_local_headroom(path, probe_max=8):
    """How many more top-level `local`s `path` can take before it stops compiling.

    Measured by appending them, because there is no way to ask Lua: the limit counts
    what the compiler allocates, not what a regex can see (upvalues, `for` control
    variables, locals inside the chunk's own blocks).
    """
    with open(path, encoding='utf-8') as f:
        body = f.read()
    for extra in range(probe_max + 1):
        probe = body + '\n' + ''.join(
            'local __headroom_probe%d = %d\n' % (i, i) for i in range(extra + 1))
        fd, tmp = tempfile.mkstemp(suffix='.lua')
        try:
            with os.fdopen(fd, 'w') as f:
                f.write(probe)
            if lua_compile_error(tmp) is not None:
                return extra
        finally:
            os.unlink(tmp)
    return probe_max


def check_lua_local_headroom(fail, paths=None):
    """Report the REMAINING local slots in the playtest chunks, and fail at zero.

    The margin used to be prose -- "two free slots", repeated in harness.lua, in this
    file and in HANDOFF.md -- and it was wrong in all three places within one PR of being
    written, because #240 spent a slot and updated no comment. A hand-maintained number
    about a limit whose breach kills every scenario at once is the wrong shape, so it is
    computed here and printed on every run (#241).

    Zero is a build failure rather than a warning: at zero the next helper anyone adds
    takes the whole harness down, and the fix (hang it off INSPECT/TUNE, or move logic to
    controller.lua) is cheap only while it is still a choice."""
    if shutil.which('lua') is None:
        print('check_lua_local_headroom: skipping (no lua on PATH; brew install lua)')
        return
    for path in (paths or (os.path.join(REPO, 'tools/playtest/harness.lua'),)):
        free = lua_local_headroom(path)
        rel = os.path.relpath(path, REPO)
        print('%s: %d top-level local slot(s) free of Lua\'s 200-local ceiling' % (rel, free))
        if free == 0:
            fail.append(
                '%s has NO room under the 200-local ceiling -- the next top-level local '
                'stops the whole chunk loading and every scenario dies at once. Hang the '
                'new helper off an existing table (INSPECT, TUNE) or move it to '
                'controller.lua.' % rel)


def check_hosted_chapters_declared(fail):
    """Every hosted chapter must declare the ChapterEventGroup its injector fills, and no
    two may claim one host slot.

    `inject.hosts.hosted_chapters()` enforces both while DISCOVERING chapters from the
    registry's constants; this runs it early, without the decomp submodule, so a bad
    declaration fails in 0s rather than at ROM-build time. The deeper check -- that the
    retargeted slot actually resolves to that group in the vanilla asset table -- lives in
    HostChapterEventGroup (tools/test_build_campaign.py), which needs the submodule.

    Why it is worth a rule at all: retargeting a host slot's MAP ids alone is enough to
    make a chapter look right while it runs the host slot's roster and scripts, so this
    class of mistake is silent and total (docs/adding-a-chapter.md step 4).

    Imports inject.hosts, NEVER build_campaign: this job installs pyyaml and nothing else,
    and build_campaign pulls in Pillow at module scope -- the first version of this lint
    failed every push with "No module named 'PIL'", a red check naming the wrong problem.
    Same rule check_purple_bank_blankers_known states for its own constants (#241)."""
    sys.path.insert(0, os.path.join(REPO, 'tools'))
    try:
        from inject import hosts
    except Exception as exc:                      # pragma: no cover - import guard
        fail.append('inject.hosts does not import: %s' % exc)
        return
    finally:
        sys.path.remove(os.path.join(REPO, 'tools'))
    try:
        hosts.hosted_chapters()
    except ValueError as exc:
        fail.append('hosted chapters: %s' % exc)
        return
    try:
        stranded = hosts.undeclared_injectors()
    except (OSError, SyntaxError) as exc:         # pragma: no cover - source-read guard
        fail.append('hosted chapters: cannot read build_campaign.py: %s' % exc)
        return
    if stranded:
        fail.append(
            'inject_%s exists but enrols nothing -- declare %s_HOST_INDEX + '
            '%s_EVENT_GROUP in tools/inject/hosts.py, or every guard built on the registry '
            'passes with one chapter fewer and no complaint'
            % (stranded[0], stranded[0].upper(), stranded[0].upper()))


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
    ('inject_enemy_class_reskins', 'inject_enemy_class_battle_anims',
     'the class battle-anim binds .pBattleAnimDef on the reskin clone classes'),
    ('inject_enemy_class_reskins', 'inject_ch01',
     "ch01's goblin grunts ride the reskinned clone classes"),
    ('inject_winter_tileset', 'inject_ch01',
     'chapter maps register against the tileset asset-table labels'),
    ('inject_winter_tileset', 'inject_prologue',
     'the prologue map registers against the tileset asset-table labels'),
    ('inject_ch01', 'inject_prologue',
     'inject_prologue overwrites the slot-1 Seize goal template inject_ch01 copies'),
    ('inject_ch03', 'inject_ch04',
     'chapter hosts are injected in campaign order; ch04 borrows ch02\'s stable Rout goal'),
    ('inject_ch04', 'inject_ch05',
     "chapter hosts are injected in campaign order; chain_ch04_to_ch05 rewrites ch04's "
     'dev-placeholder landing, which inject_ch04 must have written first'),
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


def check_playtest_matrix(fail):
    """tools/playtest/matrix.yaml is the single source of "what does this scenario
    need" (ROM configuration, host chapter, checkpoint, timing) -- so it has to keep
    describing harness.lua. A scenario added to the harness without a manifest row
    would otherwise inherit the canonical/host-1 defaults silently and fail in mGBA
    for a reason that has nothing to do with the change under test (#231)."""
    sys.path.insert(0, os.path.join(REPO, 'tools', 'playtest'))
    try:
        import matrix as mx
    except ImportError as exc:
        fail.append('tools/playtest/matrix.py does not import (%s)' % exc)
        return
    try:
        m = mx.Manifest.load()
    except Exception as exc:                      # noqa: BLE001 -- report, don't crash the lint
        fail.append('tools/playtest/matrix.yaml does not load (%s)' % exc)
        return

    harness = mx.harness_scenarios()
    for name in sorted(harness - set(m.scenarios)):
        fail.append('harness.lua defines scenario %s with no matrix.yaml row' % name)
    for name in sorted(set(m.scenarios) - harness):
        fail.append('matrix.yaml has a row for %s, which harness.lua no longer defines' % name)

    for name in m.scenarios:
        if name not in harness:
            continue
        try:
            s = m.resolve(name)
        except mx.ManifestError as exc:
            fail.append('matrix.yaml: %s' % exc)
            continue
        # A checkpoint built under one ROM configuration is discarded as hash-stale by a
        # consumer running under another -- an invisible double cost, so pin the pair.
        if s.checkpoint and not s.dynamic_checkpoint:
            builder = s.checkpoint_builder
            if builder not in m.scenarios:
                fail.append('matrix.yaml: %s wants checkpoint %s but %s is not a scenario'
                            % (name, s.checkpoint, builder))
            elif m.resolve(builder).rom != s.rom:
                fail.append('matrix.yaml: %s (%s) and its builder %s (%s) disagree on the ROM'
                            % (name, s.rom, builder, m.resolve(builder).rom))

    for suite, members in sorted(m.suites.items()):
        if not members:
            fail.append('matrix.yaml: suite %s is empty' % suite)
        for name in members:
            if name not in m.scenarios:
                fail.append('matrix.yaml: suite %s names unknown scenario %s' % (suite, name))
                continue
            s = m.resolve(name)
            if s.kind == 'checkpoint':
                fail.append('matrix.yaml: suite %s names %s, a checkpoint builder'
                            % (suite, name))
            if s.rom == 'any':
                fail.append('matrix.yaml: suite %s names %s, which is chapter-generic '
                            'and has no ROM of its own' % (suite, name))
            if s.manual:
                fail.append('matrix.yaml: suite %s names %s, which needs manual setup'
                            % (suite, name))


# Functions in harness.lua that may hold a raw press() even though a verdict scenario can
# reach them. Each is a deliberate exception with its own reason -- NOT a backlog.
BLIND_PRESS_ALLOWED = {
    # press() itself, and the two places the contract is IMPLEMENTED. guardedInput is the
    # thing that re-observes, re-authorises and verifies; it has to press eventually.
    'press': 'the emulator primitive every guarded input is built on',
    'guardedInput': 'the guarded input itself -- this is where the contract presses',
    'awaitControllerState': 'traced, enumerated cancel while backing out of an unwanted state',
    # A save slot takes TWO confirms and SaveMenu_SaveSlotSelectLoop stays the idle callback
    # across both, so the first press has no state change to be verified against. Legality is
    # re-checked before every press and the loop stops on the OUTCOME (the prompt closing).
    'driveSaveSlot': 'two confirms with no distinguishing postcondition; verified on the outcome',
    # The fuzzer's whole purpose is unguarded, weighted-random input. Driving it through the
    # controller would mean it could only ever send inputs the controller already calls legal,
    # which is precisely the space a fuzzer exists to leave.
    'fuzzDrive': 'random input IS the scenario -- guarding it would defeat the fuzzer',
    # Capturing a battle anim means sitting in a loop that dismisses whatever quote boxes the
    # engine raises mid-combat. The press is NOT blind: it fires only when
    # ProcScr_BattleEventEngine is observed live, it is re-observed every iteration, and the
    # loop stops on the OUTCOME (combat ended, or the caller's doneFn). Same shape as
    # driveSaveSlot -- no distinguishing postcondition per press, verified on the outcome.
    'shootCombatFrames': 'observed-proc dismissal inside a combat capture; verified on the outcome',
}

# The call graph this gate scopes from lives in matrix.py (`harness_functions`/`reaches`),
# with the rest of the code that reads harness.lua -- the verdict cache keys on the same
# closure, and two answers to "what does this scenario depend on" is one answer too many.


def check_verdict_scenarios_are_guarded(fail):
    """A scenario that produces a VERDICT may not drive the UI with a raw press().

    A blind press cannot tell "the scene advanced" from "FE8 swallowed that input", so a
    green run from one is not evidence -- ch01win rode straight through the very Yes/No
    prompt that cost #232 three sessions, and passed. Every input a verdict scenario sends
    now goes through guardedInput: observed state -> enumerated legal action -> verified
    postcondition (#238).

    Scope comes from matrix.yaml's `kind`, never from the scenario NAME: recordsupply and
    recordunitlist are verdict scenarios despite the prefix, and recordunitlist is in the
    gate suite. Capture (`record`) and `diagnostic` scenarios are out -- blind input is
    harmless where nothing is asserted."""
    sys.path.insert(0, os.path.join(REPO, 'tools', 'playtest'))
    try:
        import matrix as mx
        m = mx.Manifest.load()
    except Exception:                             # noqa: BLE001 -- check_playtest_matrix reports it
        return
    with open(os.path.join(REPO, 'tools/playtest/harness.lua'), encoding='utf-8') as fh:
        funcs = mx.harness_functions(fh.read())

    for name in sorted(m.scenarios):
        try:
            if m.resolve(name).kind != 'verdict':
                continue
        except mx.ManifestError:
            continue
        # A verdict scenario the harness no longer defines would otherwise drop out of this
        # gate in silence -- renamed in Lua, still listed in the manifest, and never checked
        # again. check_playtest_matrix reports the pairing separately; this refuses to pretend
        # it reviewed something it could not find.
        if name not in funcs:
            fail.append('verdict scenario %s has no function in harness.lua, so the '
                        'blind-press gate cannot review it (#238)' % name)
            continue
        for reached in sorted(mx.reaches(name, funcs)):
            if reached in BLIND_PRESS_ALLOWED:
                continue
            count = len(re.findall(r'\bpress\(', funcs[reached][0]))
            if count:
                where = reached if reached == name else '%s (via %s)' % (reached, name)
                fail.append(
                    'verdict scenario %s drives the UI with %d raw press() call(s) in %s -- '
                    'use guardedInput/selectSemantic, or classify the state it needs (#238)'
                    % (name, count, where))


# GBA address space. 0x04-0x07 are ARCHITECTURAL (MMIO, palette, VRAM, OAM) -- fixed by the
# hardware, so a literal there is a constant, not a symbol. 0x02/0x03 (EWRAM/IWRAM) and
# 0x08/0x09 (ROM) are where OUR symbols live, and those move on every engine change.
# The leading zero is OPTIONAL: 0x8091AEC is the usual GBA shorthand, and it is literally the
# form the decomp's own symbol names encode (sub_8091AEC). Requiring `0x0` would miss exactly
# the spelling the next stale literal is most likely to be written in.
_DRIFTING_ADDR = re.compile(r'0x0?[2389][0-9A-Fa-f]{6}\b')


def check_no_hardcoded_symbol_addresses(fail):
    """The playtest Lua may not hard-code a ROM/EWRAM address. gen_symbols.py exists for
    exactly this -- "BSS/EWRAM addresses shift when engine code changes, so the Lua harness
    must never hard-code them" -- and one literal that slipped through proved the point: the
    base-tiles grid was pinned at 0x085AF5DC, the engine grew, and that address came to hold
    0x000004AB. ch03door and ch03chest then failed on their PRECONDITION, before driving a
    single input, and read for months like broken doors and chests. Nothing was wrong with
    the tile-change wiring (#238).

    A wrong address is the worst failure shape available here: it does not crash, it reads
    plausible garbage, and it indicts the feature instead of the harness.

    symbols.lua and procscr.lua are GENERATED (they are nothing but addresses) and test_* files
    use fake ones as fixtures, so all three are exempt -- the same carve-outs the other scans
    use."""
    for path in sorted(glob.glob(os.path.join(REPO, 'tools/playtest/*.lua'))):
        name = os.path.basename(path)
        if name.startswith('test_') or name in ('symbols.lua', 'procscr.lua'):
            continue
        with open(path, encoding='utf-8') as fh:
            for n, line in enumerate(fh, 1):
                if line.strip().startswith('--'):
                    continue
                for hit in _DRIFTING_ADDR.findall(line):
                    fail.append('%s:%d hard-codes the ROM/EWRAM address %s -- read it from '
                                'SYM (add it to gen_symbols.py WANTED); those addresses move '
                                'on every engine change (#238)'
                                % (os.path.relpath(path, REPO), n, hit))


def check_tool_refs_exist(fail):
    """A doc or code comment naming tools/<x>.py|rb, or a docs/<x>.md path, must
    point at a file that exists -- dangling pointers are the cheapest-to-catch form
    of comment rot (2026-07-02 comment-drift ADR)."""
    # (?<![\w/]) keeps "texttools/x.py" or "fireemblem8u/tools/..." from reading as
    # our tools/; a missing-but-gitignored target is a declared build artifact
    # (e.g. playtest/symbols.lua), not a dangling pointer.
    tool_pat = re.compile(r'(?<![\w/])tools/([\w./-]*[\w-]\.(?:py|rb|lua|sh))')
    doc_pat = re.compile(r'(?<![\w/])docs/([\w./-]*[\w-]\.md)')

    def _gitignored(rel):
        return subprocess.run(['git', 'check-ignore', '-q', rel], cwd=REPO).returncode == 0

    for d in _docs() + _handwritten_sources():
        text = open(d, encoding='utf-8').read()
        rel = os.path.relpath(d, REPO)
        for prefix, pat in (('tools', tool_pat), ('docs', doc_pat)):
            for m in pat.findall(text):
                target = '%s/%s' % (prefix, m)
                if not os.path.isfile(os.path.join(REPO, target)) and not _gitignored(target):
                    fail.append('%s references %s which does not exist' % (rel, target))


def check_no_dead_concepts(fail):
    """Retired terms/mechanisms must not survive in docs OR hand-written code
    comments (the 2026-07-02 incident: a superseded mechanism lived on in a
    build_campaign.py header and got copied into an ADR as fact)."""
    pat = re.compile('|'.join(DEAD_CONCEPTS), re.I)
    for d in _docs() + _handwritten_sources():
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
    these two campaign-agnostic guards (defined in tools/inject/engine_hooks.py, called
    from build_campaign.py). Removing either silently
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
            ('_patch_chapter_title_wm_fallback',
             'the no-world-map chapter-title fallback (GetChapterTitleWM -> ROM chapTitleId); '
             'without it a story chapter on a spawn-node slot (e.g. ch03 = Za\'ha Woods) '
             'renders the WM skirmish name instead of its own title card'),
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
             'palette -- the RBG cyan mis-render'),
            ('_patch_banim_unique_pal_custom_guard',
             'the #206 per-CHARACTER banim-palette guard (gAnimCharaPalConfig may not repaint '
             'an appended banim); without it any cast member whose vanilla SLOT had a personal '
             'palette for the class it deploys as is silently miscoloured -- Baxby, on Forde\'s '
             'slot, wore Forde\'s green Cavalier palette over his own axe-beak one'),
            ('_patch_banim_spell_palette_tint',
             'the #165 caster-scoped spell-palette tint seam (data-driven green Dark magic); '
             'without it Marty\'s Flux (and any future tinted tome) silently reverts to the '
             'vanilla spell palette'),
            ('_patch_banim_charge_flash',
             'the #183 per-caster charge flash (the caster\'s sprite pulses its signature '
             'colour on the wind-up beat, armed from the existing elec-charge command); '
             'without it the casters silently lose their charge tell'),
            ('_inject_crit_d20_flourish',
             'the #11 nat-20 crit flourish (a d20 pops on the SpellFx layer at the '
             'crit-flash teardown) -- the d20, the whole D&D thesis, would silently '
             'vanish from crits'),
            ('_patch_draw_icon_pal2',
             'the #23 additive item-icon palette hook (DrawIcon routes gMSPal2IconIds to '
             'reserved BG bank 15); without it the pink Tourmaline silently reverts to pal-0 colours'),
            ('_patch_arena_presentation',
             'the #265 Arena presentation seam (ArenaUi_Init selects a generated campaign '
             'palette and chapter attendant with vanilla fallbacks); without it the winter '
             'palette and undead attendant are generated but never displayed'),
            ('_patch_arena_battle_background',
             'the #265 Arena combat backdrop seam (fade-in and three-state cycle share the '
             'generated winter palettes); without it Arena fights remain warm or flash a '
             'stale vanilla phase')):
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


def check_purple_bank_blankers_known(fail):
    """No vanilla screen may blank the cast map-sprite OBJ bank (0x0B) unnoticed.

    #218: our custom cast render from purple OBJ bank 0x0B. Vanilla treats that bank as
    scratch -- a screen calls ApplyUnitSpritePalettes() and then zeroes it, because nothing
    of vanilla's own renders from there. A zeroed 16-colour bank draws every index as
    colour 0, so the whole cast comes out as correctly shaped BLACK SILHOUETTES: right
    sheet, right position, no colour.

    We found two such screens by hand (Pick Units, then the Character list) and only found
    the second because the first was reported as a bug -- they are spelled differently
    (`PAL_OBJ(0x0B)` vs the raw `gPaletteBuffer + 0x1B0`, which is 0x100 + 0x0B*0x10). This
    check closes that: every literal reference to bank 0x0B in a palette fill anywhere in
    the decomp must be a site build_campaign.PURPLE_BANK_BLANKERS already patches out. A
    third screen -- new, or arriving with a decomp bump -- fails here instead of silently
    blackening a roster.
    """
    src_dir = os.path.join(REPO, 'fireemblem8u', 'src')
    if not os.path.isdir(src_dir):
        print('check_purple_bank_blankers_known: skipping (fireemblem8u submodule not '
              'checked out)')
        return
    bc = open(os.path.join(REPO, 'tools', 'build_campaign.py'), encoding='utf-8').read()
    # Which decomp files PURPLE_BANK_BLANKERS covers. Its entries are (PATH_CONST, orig,
    # hooked), so read the constant names out of the tuple rather than importing
    # build_campaign (which would pull in Pillow/yaml for a lint).
    block = bc[bc.index('PURPLE_BANK_BLANKERS = ('):]
    block = block[:block.index('\n)')]
    known = {name.lower() for name in re.findall(r'^\s*\((\w+)_C,', block, re.M)}

    # MUST read HEAD, not the working tree: the build patches these very fills out, so a
    # post-build tree shows nothing and the check would pass vacuously. (Same doctrine as
    # vanilla_decomp_text -- our decomp edits are build artifacts.)
    import subprocess
    env = {k: v for k, v in os.environ.items()
           if not k.startswith('GIT_')}
    # bank 0x0B, both spellings: PAL_OBJ(0x0B|0xB|11) and the raw gPaletteBuffer offset
    # (0x1B0 == 0x100 + 0x0B*0x10).
    pattern = (r'CpuFastFill\( *0, *(PAL_OBJ\( *(0x0?[Bb]|11) *\)'
               r'|gPaletteBuffer \+ 0x1B0)')
    r = subprocess.run(['git', '-C', os.path.join(REPO, 'fireemblem8u'), 'grep', '-nE',
                        pattern, 'HEAD', '--', 'src'],
                       capture_output=True, text=True, env=env)
    if r.returncode not in (0, 1):                   # 1 == no matches, which is fine
        fail.append('check_purple_bank_blankers_known: git grep failed: %s'
                    % (r.stderr or '').strip())
        return
    for line in r.stdout.splitlines():
        m = re.match(r'HEAD:src/(\w+)\.c:', line)
        if not m:
            continue
        if m.group(1).lower() not in known:
            fail.append(
                'src/%s.c blanks the cast map-sprite OBJ bank 0x0B but is not in '
                'build_campaign.PURPLE_BANK_BLANKERS -- the cast would render as black '
                'silhouettes on that screen (#218). Add it there, do not silence this.'
                % m.group(1))


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
# match (bmsave-lib.c ReadGlobalSaveInfo, the magic16/magic32/checksum condition; the
# per-block form is ReadSaveBlockInfo). Those magics are constant, so a
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
    """Run git against REPO. `cwd=` alone is NOT enough: git exports GIT_DIR /
    GIT_INDEX_FILE / GIT_WORK_TREE while a hook runs, and those OVERRIDE cwd -- so under
    pre-commit this inspected whatever repo invoked the hook rather than REPO. Harmless
    while they are the same repo, but it made the guard untestable (a fixture repo was
    silently ignored in favour of the real one) and it is the documented footgun in
    docs/decisions.md "Operational Gotchas". Target REPO with -C and a stripped env."""
    import subprocess
    try:
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        r = subprocess.run(['git', '-C', REPO] + args, capture_output=True, text=True,
                           env=env)
        return r.stdout.strip()
    except Exception:
        return ''


# ── HANDOFF may only be authored on main (2026-07-30) ──────────────────────────
# HANDOFF.md describes GLOBAL live state, but it is a tracked repo-root file, so every
# branch and worktree gets a private copy that stops describing the project and starts
# describing "the project as this branch last saw it". Merge the branch and its stale copy
# overwrites main's. That is not hypothetical: the ch05 merge (2026-07-30) put ch04 back to
# a "WIP checkpoint" four committed stages out of date, and the only reason it surfaced was
# that `git pull` refused to clobber an unrelated local edit.
#
# It had already been caught once, on 2026-07-21, and the mitigation was a HANDOFF note
# saying "keep the copies in sync". Nine days later it failed. Remembering is not a control,
# so this is the control: a branch may not INVENT its own HANDOFF.
#
# Two states pass, and the second is what makes the rule livable:
#   * UNTOUCHED  -- the branch never edited HANDOFF (git's 3-way merge then keeps main's
#     version, so main advancing while the branch is open is harmless and must not fail);
#   * SYNCED     -- the branch's copy is byte-identical to main's tip, which is the ideal
#     state for a worktree, since people read HANDOFF where they are working.
# Anything else is a branch carrying live state it does not own.

HANDOFF_FILE = 'HANDOFF.md'


def _handoff_branch_state():
    """('ok', '') | ('diverged', detail) | ('unknown', reason) for HANDOFF.md on this branch.

    'unknown' (shallow clone, detached HEAD, no origin/main) never fails the build -- a guard
    that cannot see the base must not invent a violation."""
    branch = os.environ.get('GITHUB_HEAD_REF', '') or _git(['rev-parse', '--abbrev-ref', 'HEAD'])
    if branch in ('main', 'master', 'HEAD', ''):
        return 'ok', ''
    base_ref = os.environ.get('GITHUB_BASE_REF', '') or 'main'
    main_ref = next((r for r in ('origin/' + base_ref, base_ref)
                     if _git(['rev-parse', '--verify', '--quiet', r])), '')
    if not main_ref:
        return 'unknown', 'no %s ref in this clone' % base_ref
    base = _git(['merge-base', 'HEAD', main_ref])
    if not base:
        return 'unknown', 'no merge-base with %s (shallow clone?)' % main_ref
    staged = [l for l in _git(['diff', '--cached', '--name-only']).splitlines() if l.strip()]
    edited = (HANDOFF_FILE in staged
              or HANDOFF_FILE in _diff_names(base))
    if not edited:
        return 'ok', ''                                  # UNTOUCHED
    if not _git(['diff', '--name-only', main_ref, 'HEAD', '--', HANDOFF_FILE]) and not staged:
        return 'ok', ''                                  # SYNCED to main's tip
    if HANDOFF_FILE in staged:
        return 'diverged', 'staged for commit on `%s`' % branch
    return 'diverged', ('committed on `%s` and it differs from %s'
                        % (branch, main_ref))


def check_handoff_only_on_main(fail):
    """HANDOFF.md is live state and live state is global -- author it on main, never on a
    feature branch. See the block comment above for the incident this encodes."""
    state, detail = _handoff_branch_state()
    if state == 'diverged':
        fail.append(
            '%s %s. Live state is global and belongs on main -- a branch copy silently '
            'overwrites main\'s when it merges (this cost us ch04\'s state on 2026-07-30). '
            'Fix: `git checkout main -- %s`, which also leaves the worktree showing TRUE live '
            'state for whoever reads it there. On a long-lived branch, where main\'s HANDOFF '
            'may move again, `git checkout $(git merge-base main HEAD) -- %s` instead zeroes '
            'the branch\'s net diff so it stays clean -- at the cost of a stale copy in the '
            'worktree. Either way, refresh HANDOFF on main AFTER the merge, never on the '
            'branch.' % (HANDOFF_FILE, detail, HANDOFF_FILE, HANDOFF_FILE))
    elif state == 'unknown':
        print('  note: HANDOFF branch guard skipped -- %s' % detail)


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
    (every hook in its guarded tuple -- count-free on purpose, the tuple is the truth); desk
    ownership is reviewed at the PR. The glob map (above) is the seed
    of the desk map. Dormant on `feat/*` branches (no lane), which is the steady state."""
    for path, owner in _lane_violations(_current_lane(), _changed_files()):
        print('  note: %s is historically %s-side -- if this PR spans desks, name the contract in review'
              % (path, owner))


def main():
    fail = []
    for check in (check_python_compiles, check_lua_chunks_load,
                  check_lua_local_headroom, check_hosted_chapters_declared,
                  check_tests_pass, check_yaml_parses,
                  check_chapter_status, check_chapter_deployment_schema,
                  check_injection_order, check_playtest_matrix,
                  check_verdict_scenarios_are_guarded,
                  check_no_hardcoded_symbol_addresses,
                  check_tool_refs_exist, check_no_dead_concepts,
                  check_generated_indexes_fresh, check_engine_guards_present,
                  check_purple_bank_blankers_known,
                  check_engine_campaign_agnostic,
                  check_save_layout_stable, check_handoff_only_on_main,
                  check_lane_ownership):
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
