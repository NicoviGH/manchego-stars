#!/usr/bin/env python3
"""The playtest matrix runner (#231, #222 workstream 1).

One command runs a grouped live regression matrix: every ROM configuration is
built at most once, its scenarios run concurrently, and the run ends in a compact
verdict table plus artifacts on disk.

Three things keep it quick, all of which matter because the full matrix used to cost
7+ minutes and so got skipped or over-run:
  * a VERDICT CACHE: a green scenario whose four inputs are byte-identical does not
    re-run at all, and a group with nothing left to run is never even built. This is
    the one that makes the matrix incremental -- see `scenario_fingerprint` (#255);
  * a ROM CACHE keyed on everything the ROM is built FROM -- a harness-only change
    reuses all four builds instead of remaking them (~170s);
  * scenarios run in PARALLEL within a configuration (--jobs, on by default on a
    machine with the cores for it) -- 3.2x once verdict runs went headless. Headed
    scenarios still run one at a time. See execute().
Use `make matrix SUITE=<chapter>` while iterating; the full matrix is the push gate.

    make matrix                        # the merge gate
    make matrix SUITE=ch04             # everything ch04, one build
    tools/playtest/matrix.py run --scenarios ch04moose,ch04snag
    tools/playtest/matrix.py run --suite ch05 --dry-run   # what would actually run
    tools/playtest/matrix.py list

`matrix.yaml` is the single source of truth for what a scenario needs: its ROM
configuration, its PT_HOST_CHAPTER, its checkpoint, and its fps/vsync/deadline
policy. `run.sh` resolves through this module rather than keeping a second copy
of that table -- so "which ROM does ch04moose need" has exactly one answer, and
`check.py` can prove the manifest still describes `harness.lua`.

Why grouping matters more than it looks: checkpoints (`states/<name>.ss`) are
ROM-hash-stamped, so switching ROM configuration invalidates every one of them,
and `ckpt_ch02start` replays the whole ch00->ch01->ch02 chain to rebuild a single
state. A badly ordered matrix costs far more than a duplicate `make`.
"""
import argparse
import fnmatch
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, 'tools'))     # build_scopes, inject.hosts
import build_scopes                                 # noqa: E402  the build's own bookkeeping

MANIFEST = os.path.join(HERE, 'matrix.yaml')
HARNESS = os.path.join(HERE, 'harness.lua')
RUN_SH = os.path.join(HERE, 'run.sh')

# The most scenarios ever measured running at once (#310, 2026-08-22): 4 headless mGBA
# processes on 8 logical / 4 performance cores, 3.2x with no per-scenario slowdown. It is a
# CAP on the derived default, not a target -- a bigger machine may claim more only once
# somebody has measured it there.
MEASURED_JOBS = 4

# The `make` invocation the runner builds each configuration with.
CAMPAIGN = os.environ.get('CAMPAIGN', 'rime-of-the-frostmaiden')

_SCENARIO_DEF = re.compile(r'^scenarios\.([A-Za-z0-9_]+)\s*=', re.M)


class ManifestError(Exception):
    """The manifest disagrees with reality -- a bad key, a bad reference, a bad ask."""


class Scenario(object):
    """One fully resolved row: defaults + class rules + the scenario's own entry."""

    FIELDS = ('rom', 'host_chapter', 'fps', 'vsync', 'deadline', 'checkpoint',
              'kind', 'manual', 'headless')

    def __init__(self, name, values, rom_configs, checkpoint_deadline):
        self.name = name
        self.rom = values['rom']
        self.host_chapter = values['host_chapter']
        self.fps = int(values['fps'])
        self.vsync = int(values['vsync'])
        self.deadline = int(values['deadline'])
        self.kind = values['kind']
        self.manual = bool(values.get('manual', False))
        # Headless is DECLARED, not inferred at run time (#308). `auto` derives it from
        # kind -- a verdict scenario asserts on memory and needs no pixels -- but a
        # scenario may say `headless: false` outright, and two do: recordunitlist and
        # recordsupply are verdict scenarios BY WHAT THEY ASSERT (decisions.md -> set
        # kind by what a scenario asserts, never by its name prefix) while still dropping
        # frames for make_gif.py. Deriving from kind alone would silently strip those.
        headless = values.get('headless', 'auto')
        if headless == 'auto':
            headless = (values['kind'] == 'verdict')
        self.headless = bool(headless)
        self.checkpoint_deadline = checkpoint_deadline
        ckpt = values.get('checkpoint')
        # recordscene picks its checkpoint at runtime from PT_STATE; there is no
        # static builder to name, so the manifest says `dynamic` and run.sh asks
        # the environment instead.
        self.dynamic_checkpoint = (ckpt == 'dynamic')
        self.checkpoint = None if ckpt in (None, 'dynamic') else ckpt
        if self.dynamic_checkpoint:
            self.checkpoint = 'dynamic'
        self._rom_configs = rom_configs

    @property
    def checkpoint_builder(self):
        """By convention (and run.sh's original case block) checkpoint X is minted
        by scenario ckpt_X."""
        if not self.checkpoint or self.dynamic_checkpoint:
            return None
        return 'ckpt_' + self.checkpoint

    @property
    def make_flags(self):
        return _flags_for(self.rom, self._rom_configs)

    def __repr__(self):
        return '<Scenario %s rom=%s host=%s>' % (self.name, self.rom, self.host_chapter)


def _flags_for(rom, rom_configs):
    if rom == 'any':
        return []
    return ['%s=%s' % (k, v) for k, v in rom_configs[rom].items()]


class Group(object):
    """Every scenario that shares one ROM configuration -- i.e. one `make`."""

    def __init__(self, rom, make_flags, scenarios):
        self.rom = rom
        self.make_flags = make_flags
        self.scenarios = scenarios

    def __repr__(self):
        return '<Group %s x%d>' % (self.rom, len(self.scenarios))


def merge_declared(data):
    """Fold chapter-declared rows and suites into a parsed `matrix.yaml` document."""
    import declared

    rows, suites = declared.matrix_rows(), declared.matrix_suites()
    clash = sorted(set(rows) & set(data['scenarios'] or {}))
    if clash:
        raise ManifestError(
            'declared in BOTH a chapter YAML and matrix.yaml: %s -- delete the matrix.yaml '
            'row, the chapter owns it now (#314)' % ', '.join(clash))
    data['scenarios'] = dict(data['scenarios'] or {}, **rows)
    have = data.get('suites') or {}
    clash = sorted(set(suites) & set(have))
    if clash:
        raise ManifestError(
            'suite(s) %s are DERIVED from the chapter YAML now -- delete the matrix.yaml '
            'copy, which can only fall behind (#314)' % ', '.join(clash))
    have.update(suites)
    data['suites'] = have
    return data


class Manifest(object):
    def __init__(self, data):
        self.defaults = data['defaults']
        self.rom_configs = data['rom_configs']
        self.classes = data.get('classes') or []
        self.scenarios = data['scenarios']
        self.suites = data.get('suites') or {}
        self.checkpoint_deadline = data.get('checkpoint_deadline', 900)

    @classmethod
    def load(cls, path=None):
        """The manifest as shipped, PLUS every chapter-declared case (#314).

        A chapter YAML's `playtest:` block derives its own rows and its own suite, so
        `matrix.yaml` no longer carries a hand-written copy of them. Merging here rather
        than in `__init__` keeps the synthetic manifests the pure tests build from reaching
        into the campaign.

        A name in both files RAISES. Silently letting one win would recreate exactly the
        hand-sync this replaced, with the added twist that which copy ran would depend on
        merge order -- so the scenario could differ from the one someone was reading.
        """
        with open(path or MANIFEST) as fh:
            data = yaml.safe_load(fh)
        return cls(merge_declared(data))

    # -- resolution ---------------------------------------------------------

    def resolve(self, name):
        """defaults < class rules (in order) < the scenario's own entry.

        The class rules are the direct port of run.sh's `case "$SCENARIO"`
        statements, and they keep the same semantics: a later rule overrides an
        earlier one key by key, and omitted keys fall through.
        """
        if name not in self.scenarios:
            raise ManifestError(
                '%s is not in matrix.yaml (if it is new in harness.lua, add a row)' % name)
        values = dict(self.defaults)
        for rule in self.classes:
            if fnmatch.fnmatchcase(name, rule['match']):
                values.update({k: v for k, v in rule.items() if k != 'match'})
        values.update(self.scenarios[name] or {})
        unknown = set(values) - set(Scenario.FIELDS)
        if unknown:
            raise ManifestError('%s: unknown key(s) %s' % (name, ', '.join(sorted(unknown))))
        if values['rom'] != 'any' and values['rom'] not in self.rom_configs:
            raise ManifestError('%s: unknown rom config %r' % (name, values['rom']))
        return Scenario(name, values, self.rom_configs, self.checkpoint_deadline)

    def resolve_rom(self, rom):
        if rom != 'any' and rom not in self.rom_configs:
            raise ManifestError('unknown rom config %r' % rom)
        return _flags_for(rom, self.rom_configs)

    # -- selection ----------------------------------------------------------

    def select(self, suite=None, scenarios=None, all_verdicts=False):
        if suite:
            if suite not in self.suites:
                raise ManifestError('unknown suite %r (have: %s)'
                                    % (suite, ', '.join(sorted(self.suites))))
            return list(self.suites[suite])
        if scenarios:
            for name in scenarios:
                self.resolve(name)
            return list(scenarios)
        if all_verdicts:
            return [n for n in self.scenarios
                    if self.resolve(n).kind == 'verdict' and not self.resolve(n).manual]
        raise ManifestError('nothing selected: pass --suite, --scenarios or --all')

    # -- planning -----------------------------------------------------------

    def plan(self, names, rom=None):
        """Group the selection by ROM configuration and order it for cheapness.

        Groups run in the manifest's `rom_configs` declaration order. Inside a
        group, checkpointless scenarios go first so a cheap failure surfaces
        before a long checkpoint build, and scenarios sharing a checkpoint stay
        contiguous so each `.ss` is earned once and loaded repeatedly.
        """
        if rom:
            self.resolve_rom(rom)
        resolved = []
        for name in names:
            s = self.resolve(name)
            if rom:
                s.rom = rom
            elif s.rom == 'any':
                raise ManifestError(
                    '%s is chapter-generic: say --rom <config> (and PT_HOST_CHAPTER)' % name)
            resolved.append(s)

        order = [r for r in self.rom_configs if r in {s.rom for s in resolved}]
        groups = []
        for rom_name in order:
            members = [s for s in resolved if s.rom == rom_name]
            groups.append(Group(rom_name, self.resolve_rom(rom_name), _order(members)))
        return groups


def _order(members):
    """Checkpointless first, then checkpoint-backed grouped by first appearance."""
    plain = [s for s in members if not s.checkpoint]
    buckets = {}
    for s in members:
        if s.checkpoint:
            buckets.setdefault(s.checkpoint, []).append(s)
    backed = []
    for bucket in buckets.values():
        backed.extend(bucket)
    return plain + backed


# -- execution --------------------------------------------------------------

class Outcome(object):
    def __init__(self, scenario, rom, verdict, seconds, artifacts, log_tail='', cached=False):
        self.scenario = scenario
        self.rom = rom
        self.verdict = verdict
        self.seconds = seconds
        self.artifacts = artifacts
        self.log_tail = log_tail
        self.cached = cached

    def as_dict(self):
        return {'scenario': self.scenario, 'rom': self.rom, 'verdict': self.verdict,
                'seconds': round(self.seconds, 1), 'artifacts': self.artifacts,
                'cached': self.cached}


class Report(object):
    def __init__(self, outcomes, builds, duplicate_builds, seconds):
        self.outcomes = outcomes
        self.builds = builds
        self.duplicate_builds = duplicate_builds
        self.seconds = seconds

    @property
    def failures(self):
        return [o for o in self.outcomes if o.verdict != 'PASS']

    @property
    def cached(self):
        return len([o for o in self.outcomes if o.cached])

    @property
    def ran(self):
        return len(self.outcomes) - self.cached

    @property
    def ok(self):
        return not self.failures

    @property
    def exit_code(self):
        return 0 if self.ok else 1

    def as_dict(self):
        return {'ok': self.ok, 'builds': self.builds,
                'duplicate_builds': self.duplicate_builds,
                'seconds': round(self.seconds, 1),
                'outcomes': [o.as_dict() for o in self.outcomes]}


def scenario_lanes(scenarios):
    """Split a group's scenarios into (parallel_safe, serial) lists.

    Scenarios are independent mGBA runs against an already-built ROM, each writing its own
    `/tmp/playtest-<name>` -- so within one ROM configuration they can run concurrently.
    Two things pull a scenario back out of that lane:

      * a CHECKPOINT: `states/<name>.ss` is a shared file that a scenario will MINT if it
        is missing or stale for this ROM build, so two scenarios wanting the same
        checkpoint would race to write it. Those run serially, one checkpoint at a time;
      * a HEADED run (#310). Parallelism is gated on `headless`, not on checkpoint-freedom
        alone: four GUI mGBA windows contend for the compositor and each still renders
        every frame, which is what the 2026-08-09 measurement caught. A headless run
        renders nothing and does not contend -- see execute().

    A MIXED group is not forced serial whole: its headless scenarios still run in the
    parallel lane, and the headed ones run afterwards on the caller's thread, alone. So a
    headed scenario never overlaps anything, headless or otherwise.
    """
    parallel, serial = [], []
    for s in scenarios:
        (serial if (s.checkpoint or not s.headless) else parallel).append(s)
    return parallel, serial


def resolve_jobs(arg=None, env=None, cpus=None):
    """How many scenarios run at a time when nobody says: `--jobs`, else `MX_JOBS`, else
    derived from the machine.

    The derived default is `cpus // 2`, capped at MEASURED_JOBS, floored at 1 -- half the
    logical cores is the performance-core count on the Mac this was measured on (8 logical
    / 4 performance -> 4), and an unthrottled mGBA is CPU-bound enough that a box without
    spare cores would only divide the same throughput. The cap is there because 4 is what
    was actually measured; a bigger machine has to be measured before it may claim more.
    """
    if arg:
        return max(1, int(arg))
    env = os.environ if env is None else env
    if env.get('MX_JOBS'):
        return max(1, int(env['MX_JOBS']))
    if cpus is None:
        cpus = os.cpu_count() or 1
    return max(1, min(MEASURED_JOBS, cpus // 2))


def execute(groups, build, run_scenario, jobs=1, lookup_cached=None, after_build=None):
    """Run the plan. `build`, `run_scenario` and `lookup_cached` are injected so the
    ordering and aggregation logic is testable without a ROM or an emulator.

    A failed build blocks only its own group: the rest of the matrix still runs,
    because one broken configuration should not hide the state of the others.

    `lookup_cached(scenario)` returns a previously earned Outcome, or None. A group
    whose scenarios are ALL cached is never built -- that is the biggest win in the
    feature, because it makes a doc-only or harness-only change cost no `make` and no
    emulator at all (#255). Outcomes are emitted in the group's own order whether they
    ran or not, so the table does not reshuffle itself as the cache fills.

    `jobs` > 1 runs a group's parallel-lane scenarios concurrently (see `scenario_lanes`:
    checkpoint-free AND headless). BUILDS always stay serial and never overlap a run: the
    tree holds ONE `fireemblem8.gba`, so a second `make` would swap the ROM out from under a
    live emulator (and two builds in one tree corrupt each other outright -- see CLAUDE.md).

    **`jobs` DEFAULTS TO PARALLEL, BECAUSE HEADLESS CHANGED THE MEASUREMENT** (#310). The
    same four verdict scenarios, one build, `--no-verdict-cache`, on the same Mac: 71s at
    `--jobs 1` against 22s at `--jobs 4`, all four PASS, zero deadline blowouts, and the
    per-scenario times IDENTICAL serial and parallel (15/14/20/20 against 15/15/21/21) --
    which is what no contention at all looks like.

    The old result was right and is not being overturned: 2026-08-09 measured 444s serial
    against 439s at `jobs=4` with four scenarios blowing their WALL-CLOCK deadlines, and
    that measurement was CONDITIONAL ON BEING HEADED -- four Qt windows contending for the
    compositor while each rendered every frame. #308 deleted the rendering; the condition
    changed, not the arithmetic. Which is also why headed scenarios are still serial here:
    for them the 2026-08-09 number is the live one.
    """
    outcomes = []
    built = []
    started = time.time()
    for group in groups:
        slot = {}                       # scenario identity -> its Outcome
        pending = []
        for s in group.scenarios:
            hit = lookup_cached(s) if lookup_cached else None
            if hit is None:
                pending.append(s)
            else:
                slot[id(s)] = hit
        if pending:
            built.append(group.rom)
            if not build(group.rom, group.make_flags):
                for s in pending:
                    slot[id(s)] = Outcome(s.name, group.rom, 'BLOCKED', 0.0, '',
                                          'ROM configuration %s failed to build' % group.rom)
            else:
                # Building can REMOVE work, not just precede it. A scope manifest only
                # exists once the build that produced it has run, so a configuration whose
                # ROM inputs moved cannot be keyed on scopes until now -- and a ch05 edit
                # then turns out to have left every other chapter's scenarios untouched
                # (#255 phase 2). Ask again before spending an emulator on any of them.
                if after_build:
                    after_build(group.rom)
                if lookup_cached:
                    rechecked = []
                    for s in pending:
                        hit = lookup_cached(s)
                        if hit is None:
                            rechecked.append(s)
                        else:
                            slot[id(s)] = hit
                    pending = rechecked
                parallel, serial = scenario_lanes(pending)
                if jobs > 1 and len(parallel) > 1:
                    from concurrent.futures import ThreadPoolExecutor
                    with ThreadPoolExecutor(max_workers=min(jobs, len(parallel))) as pool:
                        for s, outcome in zip(parallel, pool.map(run_scenario, parallel)):
                            slot[id(s)] = outcome
                else:
                    for s in parallel:
                        slot[id(s)] = run_scenario(s)
                for s in serial:
                    slot[id(s)] = run_scenario(s)
        outcomes.extend(slot[id(s)] for s in group.scenarios)
    return Report(outcomes, builds=len(built),
                  duplicate_builds=len(built) - len(set(built)),
                  seconds=time.time() - started)


# -- rendering --------------------------------------------------------------

def human_duration(seconds):
    seconds = int(round(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return '%dh%02dm%02ds' % (h, m, s)
    if m:
        return '%dm%02ds' % (m, s)
    return '%ds' % s


def render_table(report):
    """The `source` column is not decoration: a cached green must never read as a fresh
    one, or the table starts asserting things this run never observed (#255)."""
    rows = [(o.rom, o.scenario, o.verdict, 'cached' if o.cached else 'ran',
             human_duration(o.seconds), o.artifacts)
            for o in report.outcomes]
    head = ('variant', 'scenario', 'verdict', 'source', 'time', 'artifacts')
    widths = [max(len(head[i]), max([len(r[i]) for r in rows] or [0]))
              for i in range(len(head))]
    line = lambda cells: '  '.join(c.ljust(widths[i]) for i, c in enumerate(cells)).rstrip()
    out = [line(head), '  '.join('-' * w for w in widths)]
    out.extend(line(r) for r in rows)
    out.append('')
    out.append('%d scenario(s), %d ran, %d cached, %d build(s), %d duplicate build(s), %s wall'
               % (len(report.outcomes), report.ran, report.cached, report.builds,
                  report.duplicate_builds, human_duration(report.seconds)))
    return '\n'.join(out)


def render_failures(report):
    if report.ok:
        return ''
    out = []
    for o in report.failures:
        out.append('%s [%s] -> %s' % (o.scenario, o.rom, o.verdict))
        if o.artifacts:
            out.append('  artifacts: %s' % o.artifacts)
        for tail_line in (o.log_tail or '').splitlines():
            out.append('  | %s' % tail_line)
        out.append('')
    return '\n'.join(out)


# -- the run.sh interface ---------------------------------------------------

def export_env(scenario):
    """Shell assignments run.sh evals. Every value is single-quoted so an empty
    checkpoint stays empty rather than becoming the word None."""
    pairs = [
        ('MX_ROM', scenario.rom),
        ('MX_MAKE_FLAGS', ' '.join(scenario.make_flags)),
        ('MX_HOST_CHAPTER', scenario.host_chapter),
        ('MX_FPS', scenario.fps),
        ('MX_VSYNC', scenario.vsync),
        ('MX_DEADLINE', scenario.deadline),
        ('MX_CHECKPOINT', '' if scenario.dynamic_checkpoint else (scenario.checkpoint or '')),
        ('MX_CHECKPOINT_BUILDER', scenario.checkpoint_builder or ''),
        ('MX_CHECKPOINT_DYNAMIC', '1' if scenario.dynamic_checkpoint else ''),
        ('MX_CHECKPOINT_DEADLINE', scenario.checkpoint_deadline),
        ('MX_KIND', scenario.kind),
        ('MX_HEADLESS', '1' if scenario.headless else ''),
    ]
    return '\n'.join("%s='%s'" % (k, '' if v is None else v) for k, v in pairs)


def harness_scenarios(path=None):
    """Every `scenarios.X = function()` defined in harness.lua."""
    with open(path or HARNESS) as fh:
        return set(_SCENARIO_DEF.findall(fh.read()))


# -- reading harness.lua's shape --------------------------------------------
#
# harness.lua is ONE Lua chunk, so "which part of it does this scenario depend on" has to
# be answered by reading the source. Two consumers need that answer and they must agree,
# so it lives here with the rest of the code that reads harness.lua: check.py's #238
# blind-press gate (which functions does a verdict scenario reach?) and the verdict cache
# below (what invalidates a scenario's PASS?).

LUA_FUNC_DEF = re.compile(
    r'^(?:local function (\w+)|scenarios\.(\w+) = function|(\w+) = function)', re.M)
# A top-level function's body is INDENTED; only its terminator sits in column 0.
_LUA_TOP_END = re.compile(r'^end\b')


def _strip_comments(lines):
    """Drop Lua comments so a comment edit cannot move a hash or a press count.

    Trailing ones too, not just whole lines: `local x = 1 -- press(A)` otherwise trips
    the press gate on prose. Lua has no string type that survives this naively, but no
    line in these files puts `--` inside a literal.
    """
    return '\n'.join(l.split('--')[0] for l in lines)


def _harness_marks(lines):
    marks = []
    for i, line in enumerate(lines):
        m = LUA_FUNC_DEF.match(line)
        if m:
            marks.append((i, m.group(1) or m.group(2) or m.group(3),
                          'scenario' if m.group(2) else 'helper'))
    marks.append((len(lines), None, None))
    return marks


def harness_functions(source):
    """{name: (body, kind)} for every top-level function in harness.lua.

    Attribution is by ENCLOSING FUNCTION, not by distance to the next `scenarios.X`.
    Splitting on scenario definitions charges every intervening `local function` helper to
    whichever scenario happens to sit above it -- which is how #238's own scope list came to
    name `retreat` (0 presses of its own) and miss `reachRbgCh01` (8)."""
    lines = source.split('\n')
    marks = _harness_marks(lines)
    out = {}
    for (start, name, kind), (end, _, _) in zip(marks, marks[1:]):
        out[name] = (_strip_comments(lines[start:end]), kind)
    return out


def reaches(name, funcs, seen=None):
    """Every harness function reachable from `name`, including itself.

    MENTIONS, not calls. `waitFor(shared)` and `{ fn = onlyForB }` hand a helper over
    without calling it at the reference site, so following call syntax alone lets it
    escape the closure -- and an edit to it would leave the verdict key still. Matching
    every known function NAME in the body over-reaches (a local shadowing a helper's name
    drags it in), and over-reaching only ever costs an extra re-run.
    """
    seen = seen if seen is not None else set()
    if name in seen or name not in funcs:
        return seen
    seen.add(name)
    for mentioned in set(re.findall(r'\b(\w+)\b', funcs[name][0])):
        if mentioned in funcs and mentioned != name:
            reaches(mentioned, funcs, seen)
    return seen


def harness_shared(source):
    """Everything in harness.lua that no single function's closure can account for.

    `harness_functions` charges a chunk to the function that opens it, so top-level data
    declared BETWEEN two helpers -- `TUNE`, `CALLBACK_NAMES`, the constants -- is glommed
    onto whichever helper happens to precede it. That data feeds every observation, so a
    fingerprint built only from a closure would miss an edit to it and serve a stale PASS.

    So partition instead: each chunk is a function BODY (closure-attributable) plus a
    RESIDUE after its column-0 terminator (shared by everyone). A chunk with no such
    terminator -- a one-line `local function yield() ... end` -- is unattributable, and
    unattributable means shared, never dropped. Preamble + every residue = every line the
    closures do not already cover, which is what makes the cache SOUND rather than hopeful.
    """
    lines = source.split('\n')
    marks = _harness_marks(lines)
    out = [_strip_comments(lines[:marks[0][0]])]
    for (start, _, _), (end, _, _) in zip(marks, marks[1:]):
        chunk = lines[start:end]
        term = next((j for j in range(1, len(chunk)) if _LUA_TOP_END.match(chunk[j])), None)
        out.append(_strip_comments(chunk if term is None else chunk[term + 1:]))
    return '\n'.join(out)


# -- the wrong-ROM guard ----------------------------------------------------

BUILD_STAMP = os.path.join(REPO, '.build-config.json')


def _flag_matches(stamped, declared):
    """Does a stamped flag value answer to what the manifest declares? See built_rom_config."""
    if isinstance(declared, str) or isinstance(stamped, str):
        return str(stamped) == str(declared)
    return bool(stamped) == bool(declared)


def built_rom_config(rom_configs, stamp_path=None):
    """Name the ROM configuration currently sitting in the tree, or None if the stamp
    is missing (an old build) or matches nothing the manifest knows about.

    build_campaign.py writes the stamp; matching is on the EXACT flag set, because
    `canonical` is "no flags" and would otherwise match every build.

    VALUES COUNT, not just which flags are on. ch05's three ending arms set the same two flags
    and differ only in what CH05ENDING says, so a presence-only match collapsed all three onto
    whichever the manifest listed first -- and refused to film the other two, naming a build the
    tree did not hold. A stamp that carries only booleans (written before this, or by a flag
    that really is a boolean) cannot name such an arm; it resolves to None, which is already
    this function's "unknown, stay out of the way" answer rather than a guess."""
    try:
        with open(stamp_path or BUILD_STAMP) as fh:
            stamp = json.load(fh)
    except (OSError, ValueError):
        return None
    on = {k: v for k, v in (stamp.get('flags') or {}).items() if v}
    for name, flags in rom_configs.items():
        if set(flags) != set(on):
            continue
        # Compare VALUES, normalised on BOTH sides. Keying the check on the manifest side
        # being a `str` looked equivalent and is not: YAML 1.1 types `on`/`yes`/`no` as
        # booleans, so an arm written unquoted would make the clause vacuous and quietly
        # restore the presence-only matching this exists to fix. Whenever EITHER side names a
        # string, compare strings; otherwise both are plain on/off and being in `on` is all
        # they have to say -- which is what keeps `FLAG: 1` matching a stamped `true` instead
        # of failing on '1' != 'True'. A legacy stamp holding True where an arm name belongs
        # compares 'True' against the arm and matches nothing, which is the intent.
        if all(_flag_matches(on[k], v) for k, v in flags.items()):
            return name
    return None


def check_rom(manifest, scenario, stamp_path=None):
    """Return an error string if the built ROM cannot host this scenario, else None."""
    if scenario.rom == 'any':
        return None
    built = built_rom_config(manifest.rom_configs, stamp_path)
    if built is None or built == scenario.rom:
        return None     # unknown stamp: stay out of the way rather than block a run
    want = ' '.join(scenario.make_flags) or '(no flags)'
    return ('%s needs the %s ROM (make %s) but the tree holds a %s build.\n'
            '  Build it first:  make CAMPAIGN=%s %s fireemblem8.gba -j$(nproc)'
            % (scenario.name, scenario.rom, want, built, CAMPAIGN,
               ' '.join(scenario.make_flags)))


# -- live wiring ------------------------------------------------------------

# -- ROM cache --------------------------------------------------------------
#
# The tree holds ONE fireemblem8.gba, so a 4-configuration matrix rebuilds four times even
# when nothing that feeds a ROM has changed -- and a harness-only edit (very common: three in
# one afternoon) paid ~170s of `make` to produce four byte-identical files. The cache keeps a
# built ROM per (configuration, input hash) and copies it back into place instead.
#
# WHAT COUNTS AS AN INPUT is the whole safety argument: anything the ROM is built FROM. The
# campaign data, the injectors and engine sources, the Makefile, the make flags, and the
# DECOMP HEAD (our decomp edits are build artifacts restored from HEAD each build, so the
# commit is the real input). `harness.lua`, `matrix.py` and `matrix.yaml` are deliberately
# absent -- they drive the emulator, never the ROM, which is exactly the case this speeds up.
# The ROM lands INSIDE the submodule (the top-level target delegates: `make -C
# fireemblem8u fireemblem8.gba`), while the config stamp is written at the repo root.
# Getting this pair wrong is silent -- store_cached_rom just finds nothing to copy and
# every run rebuilds, which is exactly how the first cut of this cache did nothing.
ROM_PATH = os.path.join(REPO, 'fireemblem8u', 'fireemblem8.gba')
ELF_PATH = os.path.join(REPO, 'fireemblem8u', 'fireemblem8.elf')
STAMP_PATH = os.path.join(REPO, '.build-config.json')
# What build_campaign.py recorded each injection step as having written (#255 phase 2).
SCOPES_PATH = os.path.join(REPO, '.build-scopes.json')
ROM_CACHE_DIR = os.path.join(REPO, '.matrix-romcache')
ROM_INPUT_PATHS = build_scopes.ROM_INPUT_PATHS


def rom_input_hash(make_flags, paths=None):
    """A digest of everything the ROM is built from, for cache keying.

    The file fingerprint itself is `build_scopes.fingerprint_paths` -- shared with the
    injection step cache (#309), because "have the inputs moved" must have one answer.
    """
    h = hashlib.sha256()
    h.update(('flags:' + ' '.join(make_flags) + '|campaign:' + CAMPAIGN + '\n').encode())
    try:
        head = subprocess.check_output(['git', '-C', os.path.join(REPO, 'fireemblem8u'),
                                        'rev-parse', 'HEAD'], stderr=subprocess.DEVNULL)
        h.update(b'decomp:' + head)
    except (subprocess.CalledProcessError, OSError):
        return None             # cannot pin the decomp -> refuse to cache rather than guess
    build_scopes.fingerprint_paths(REPO, ROM_INPUT_PATHS if paths is None else paths, into=h)
    return h.hexdigest()[:32]


# What one build leaves behind that a later run reads back. The .elf is NOT optional and
# leaving it out was a live bug: `gen_symbols.py` reads `fireemblem8.elf` to emit the symbol
# tables the harness dofiles, and the boot flags MOVE symbols -- a ch05boot ELF and a
# canonical ELF disagree on 58 of the names the harness reads (gUnitLookup, gItemData,
# Menu_OnIdle, ...). Restoring a cached .gba while the tree kept the previous config's .elf
# therefore ran every scenario against the wrong addresses, and the gate spans FOUR
# configurations, so a warm run restored three of them that way. It costs 44 MB per slot;
# reading the wrong memory costs a debugging session that finds nothing.
#
# `.scopes.json` travels for the same reason: a restored ROM must bring the manifest of
# what the build that produced it wrote, or the verdict key reads whatever build ran last.
ROM_CACHE_ARTIFACTS = (('.gba', ROM_PATH), ('.elf', ELF_PATH), ('.json', STAMP_PATH),
                       ('.scopes.json', SCOPES_PATH))


def _cache_slot(rom, digest):
    return os.path.join(ROM_CACHE_DIR, '%s-%s' % (rom, digest))


def restore_cached_rom(rom, digest, cache_dir=None):
    """Copy a cached ROM, its ELF and its build stamp into the tree. True if all were there.

    All or nothing: half a slot is worse than none, because a .gba without its .elf is
    exactly the wrong-symbols failure above.
    """
    if digest is None:
        return False
    slot = os.path.join(cache_dir, '%s-%s' % (rom, digest)) if cache_dir \
        else _cache_slot(rom, digest)
    if not all(os.path.isfile(slot + ext) for ext, _ in ROM_CACHE_ARTIFACTS):
        return False
    for ext, dest in ROM_CACHE_ARTIFACTS:
        shutil.copyfile(slot + ext, dest)
    return True


def store_cached_rom(rom, digest):
    """Snapshot the freshly built ROM, its ELF and its stamp under this input digest."""
    if digest is None:
        return
    if not all(os.path.isfile(src) for _, src in ROM_CACHE_ARTIFACTS):
        return                  # nothing to cache (stamp is what run.sh checks the ROM against)
    os.makedirs(ROM_CACHE_DIR, exist_ok=True)
    slot = _cache_slot(rom, digest)
    for ext, src in ROM_CACHE_ARTIFACTS:
        shutil.copyfile(src, slot + ext)
    for old in glob.glob(os.path.join(ROM_CACHE_DIR, '%s-*' % rom)):
        if not os.path.basename(old).startswith('%s-%s' % (rom, digest)):
            try:
                os.remove(old)  # one slot per configuration: the cache tracks HEAD, not history
            except OSError:
                pass


def _build(rom, make_flags, log_dir, quiet=True, use_cache=True):
    digest = rom_input_hash(make_flags) if use_cache else None
    if restore_cached_rom(rom, digest):
        print('== %s: cached ROM reused (no ROM input changed)' % rom)
        return True
    cmd = ['make', 'CAMPAIGN=' + CAMPAIGN] + list(make_flags) + [
        'fireemblem8.gba', '-j%d' % (os.cpu_count() or 4)]
    print('== building %s: %s' % (rom, ' '.join(cmd)))
    log_path = os.path.join(log_dir, 'build-%s.log' % rom)
    with open(log_path, 'w') as log:
        proc = subprocess.run(cmd, cwd=REPO, stdout=log,
                              stderr=subprocess.STDOUT if quiet else None)
    if proc.returncode != 0:
        print('   BUILD FAILED -- see %s' % log_path)
        return False
    store_cached_rom(rom, digest)
    return True


# -- verdict cache ----------------------------------------------------------
#
# The scenario COUNT should keep growing -- that is coverage, and capping it means deleting
# proof. What must stop growing is the number that EXECUTE per change (#255).
#
# THE SOUNDNESS RULE, which is the whole licence to skip: a scenario's verdict is a pure
# function of exactly four inputs -- the ROM it boots, its own Lua body, the harness helpers
# it transitively reaches, and its matrix.yaml entry (ROM flag, host chapter, checkpoint,
# timing). Plus controller.lua, which decides every classification it guards on. If all of
# those are byte-identical a PASS cannot become a FAIL. **A FAIL is never cached** -- a flaky
# red must always re-run; only green is skippable.
#
# WHAT IS DELIBERATELY NOT IN THE KEY: harness.lua as a whole file. It is one Lua chunk and
# nearly every task edits it, so a whole-file hash would invalidate all 17 scenarios on every
# commit and the cache would never hit -- the feature would be theatre. The closure above is
# the correct granularity, and `harness_shared` is what keeps the closure honest.
#
# HONEST CEILING: keying on rom_input_hash means any build_campaign.py or campaign.yaml edit
# invalidates every scenario, and nearly every feature task touches build_campaign.py. This
# phase buys doc-only changes, harness-only changes, and repeat runs while debugging
# something else. Build-attributed scoping (#255 phase 2) is where that ceiling lifts.
VERDICT_CACHE_DIR = os.path.join(REPO, '.matrix-verdictcache')


def _read(path):
    with open(path) as fh:
        return fh.read()


# `local NAME = dofile(PLAYTEST_DIR .. "/thing.lua")` -- the only way harness.lua takes a
# module, so the binding table is READ rather than kept.
_DOFILE_BINDING = re.compile(
    r'^local\s+(\w+)\s*=\s*dofile\(PLAYTEST_DIR\s*\.\.\s*"/([\w.]+)"\)', re.M)


def driver_modules(harness_source=None):
    """{module filename: the local it is bound to} for every module harness.lua dofiles.

    A bare `dofile(...)` with no binding (the generated symbol tables) is not a module in
    this sense -- nothing can reference it selectively, and those are excluded from the key
    anyway.
    """
    harness_source = _read(HARNESS) if harness_source is None else harness_source
    return {mod: name for name, mod in _DOFILE_BINDING.findall(harness_source)}


def scenario_driver_modules(scenario_name, harness_source=None):
    """The dofile'd modules this scenario can actually reach.

    A module counts as reached when its binding appears in the scenario's own closure, or
    in harness.lua's shared text. The BINDING LINES are stripped out of the shared text
    first, and that detail is the whole feature: `local CLEARBOT = dofile(...)` is
    top-level, so leaving it in would make every module reachable by everyone and the split
    would do precisely nothing.
    """
    harness_source = _read(HARNESS) if harness_source is None else harness_source
    modules = driver_modules(harness_source)
    funcs = harness_functions(harness_source)
    text = _DOFILE_BINDING.sub('', harness_shared(harness_source))
    for name in reaches(scenario_name, funcs):
        text += '\n' + funcs[name][0]
    return {mod for mod, binding in modules.items()
            if re.search(r'\b%s\b' % re.escape(binding), text)}


def driver_source(here=None):
    """Everything OUTSIDE harness.lua that decides what a scenario does.

    `controller.lua` classifies every state a guarded input is authorised against;
    `symbols.lua`/`procscr.lua` name the memory it reads; `clearbot`/`pathing`/`liveness`
    and friends are dofile'd straight into the run; and `run.sh` chooses the fps, the
    deadline, the checkpoint handling and the wrapper the emulator actually loads. Any of
    them can turn a PASS into a FAIL without harness.lua changing a byte.

    `gen_symbols.py` is in here, but the tables it EMITS (`symbols.lua`, `procscr.lua`) are
    pointedly not: run.sh rewrites them from the ELF after the fingerprint has been taken,
    so hashing them would make every engine change cost TWO re-runs before the cache
    converged -- and a matrix alternating between ROM configurations might never converge at
    all. Their content is already implied by inputs that ARE in the key: the ELF comes from
    the same sources as `rom_input_hash`, and the emitter is right here.

    harness.lua is absent for the opposite reason: it is keyed by CLOSURE, and folding it in
    here would undo the whole reason the closure exists.
    """
    here = here or HERE
    generated = ('symbols.lua', 'procscr.lua')
    files = [p for p in glob.glob(os.path.join(here, '*.lua'))
             if not os.path.basename(p).startswith('test_')
             and os.path.basename(p) not in generated
             and os.path.basename(p) != 'harness.lua']
    files.append(os.path.join(here, 'run.sh'))
    files.append(os.path.join(here, 'gen_symbols.py'))
    out = {}
    for path in sorted(files):
        if os.path.isfile(path):
            out[os.path.basename(path)] = _read(path)
    return out


# Driver files that are not dofile'd modules, so nothing can reach them selectively:
# `run.sh` is the launcher (it chooses the fps, the deadline and the wrapper for every
# run), and `gen_symbols.py` emits the tables every scenario reads.
GLOBAL_DRIVER_FILES = ('run.sh', 'gen_symbols.py')


def scenario_driver_text(scenario_name, files=None, harness_source=None):
    """The driver text whose contents can change THIS scenario's verdict."""
    files = driver_source() if files is None else files
    reached = scenario_driver_modules(scenario_name, harness_source)
    parts = []
    for name in sorted(files):
        if not (name in GLOBAL_DRIVER_FILES or name in reached):
            continue
        parts.append('%s\n%s' % (name, files[name]))
    return '\n'.join(parts)


# The PT_* knobs run.sh reads from the AMBIENT environment and passes into the wrapper.
# They are not in `matrix.yaml` and not in `export_env`, so without them
# `PT_SEED=7 matrix.py run --scenarios fuzz_ch01` collides with the seed-1 key and is
# served a cached PASS it never earned. Kept in sync with run.sh by
# `test_every_PT_var_run_sh_reads_is_in_the_key`. PT_HOST_CHAPTER is deliberately absent:
# matrix.py sets it FROM the manifest entry, which `export_env` already covers.
PLAYTEST_ENV_KEYS = ('PT_SEED', 'PT_CHAR', 'PT_ROUNDS', 'PT_STATE', 'PT_TAG', 'PT_UNTIL',
                     'PT_SPEED', 'PT_MAXFRAMES', 'PT_PRESSEVERY', 'PT_SHOTEVERY', 'PT_FPS',
                     'PT_DIFFICULTY',
                     # The #345 watchdog knobs. Neither should change a verdict -- they bound
                     # how patient run.sh is, not what the scenario proves -- but the guard
                     # that keeps this list honest cannot tell, and a run killed early by a
                     # tightened PT_STALL_S must not be served later as a cached PASS.
                     'PT_STALL_S', 'PT_MAX_WALL_S',
                     'PT_PROVIDER', 'PT_MODEL', 'PT_BASE_URL', 'PT_LLM_DIR',
                     # PT_SOUND cannot change a VERDICT -- it unmutes the emulator and nothing
                     # else -- but it is in the key anyway, because the guard that keeps this
                     # list honest cannot tell a harmless knob from a decisive one and should
                     # not have to. The cost is one extra run when a listen-through follows a
                     # muted PASS, which is exactly when you wanted to run it again.
                     'PT_SOUND',
                     # PT_HEADED forces a verdict scenario back onto the Qt frontend (#308).
                     # It genuinely changes the run: headed restores emu:screenshot(), which
                     # harness.lua skips under mgba-headless. Serving a headed PASS for a
                     # headless run -- or the reverse -- would cache across two different
                     # execution paths, which is precisely what this key exists to prevent.
                     'PT_HEADED')


# -- what a scenario can possibly depend on (#255 phase 2) ------------------
#
# The build tells us what each injection step WROTE (tools/build_scopes.py). This says what
# each scenario READS, and the two meet at the verdict key: a scenario re-runs only when a
# scope it depends on has moved.
#
# The chapter dependency is a RANGE, not a point. A scenario boots somewhere and plays
# FORWARD, and a checkpoint-backed one replays that whole chain -- `ckpt_ch02start` replays
# ch00 -> ch01 -> ch02 to mint its state. Scoping a scenario to its host chapter alone would
# be precisely the hand-declared impact map #255 exists to avoid.
#
# Slot numbers come from `tools/inject/hosts.py`, the file that ENROLS a chapter, so adding
# ch06 is one line there and nothing here.
def _host_slots():
    """{host slot -> build scope}, read from the injector's own enrolment constants."""
    from inject import hosts
    slots = {hosts.PROLOGUE_HOST_INDEX: 'chapter:prologue'}
    for name in dir(hosts):
        m = re.match(r'^CH(\d\d)_HOST_INDEX$', name)
        if m:
            slots[getattr(hosts, name)] = 'chapter:ch%s' % m.group(1)
    return slots


def _boot_slot(scenario, slots):
    """The slot a scenario's ROM configuration starts New Game at.

    A `CH05BOOT=1` build boots straight into ch05, so nothing before it is ever played --
    that is where most of phase 2's saving comes from. The TESTCH sandbox replaces the
    prologue on slot 1 and is written by a step naming no chapter, so its content already
    lives in `global`; it contributes no chapter of its own.
    """
    flags = {f.split('=')[0] for f in scenario.make_flags}
    for flag in sorted(flags):
        m = re.match(r'^CH(\d\d)BOOT$', flag)
        if m:
            for slot, scope in slots.items():
                if scope == 'chapter:ch%s' % m.group(1):
                    return slot
    if 'TESTCH' in flags or 'LORDBOOT' in flags:
        return None
    return min(slots)


_CHAPTER_RECORD = re.compile(r'"chapter":(\d+)')


def observed_chapters(log_text):
    """The chapter slots a run actually reached, or None if the log never said.

    Every controller observation carries `world.chapter`, so a scenario's own log is a
    record of where it went -- the runtime counterpart of the build's scope manifest, and
    derived the same way: from what actually happened, not from what anybody declared.
    """
    slots = sorted({int(n) for n in _CHAPTER_RECORD.findall(log_text or '')})
    return slots or None


def scenario_scopes(scenario, slots=None, observed=None):
    """Every build scope whose contents could change this scenario's verdict.

    `observed` is the chapter slots a previous run of this scenario actually visited. With
    it, the scenario depends on exactly those chapters. Without it -- a cold cache -- the
    answer is every chapter from its boot point FORWARD, because `matrix.yaml`'s
    `host_chapter` is the harness's `PT_HOST_CHAPTER` hint (default 1), not the last
    chapter played: `ch01win` boots at the prologue and plays into ch01 while declaring
    host_chapter 1. Reading it as an upper bound let ch01's map change without re-running
    the scenario that plays it.

    Why the observed set is safe to trust: for a change to send a scenario somewhere NEW,
    that change has to be in a scope it already depends on -- a chapter it visits, or
    `global`, where the chapter-chaining steps live because their names name two chapters.
    So it re-runs, and re-observes, before the new chapter can matter.
    """
    slots = slots or _host_slots()
    scopes = {'global'}
    boot = _boot_slot(scenario, slots)
    if boot is None:
        # The TESTCH sandbox replaces the prologue on slot 1 and is written by a step
        # naming no chapter, so its content already lives in `global`.
        return scopes
    scopes.add(slots[boot])
    if observed is not None:
        for slot in observed:
            if slot in slots:
                scopes.add(slots[slot])
        return scopes
    for slot, scope in slots.items():
        if slot >= boot:
            scopes.add(scope)
    return scopes


# The ROM inputs NO scope can see. Everything else reaches the ROM as a file some injector
# WRITES, which the scope manifest observes -- but the decomp's own sources are COMPILED
# (we only patch a handful), so a submodule bump touching an engine file no injector writes
# rebuilds the ROM and moves not one scope digest. `engine/` and the Makefile are the same
# shape. Narrow on purpose: campaign data is what changes constantly, and it stays
# scope-attributed.
ENGINE_INPUT_PATHS = ('Makefile', 'engine')


def engine_input_hash():
    """A digest of the ROM inputs that never pass through an observed injector write."""
    return rom_input_hash([], paths=ENGINE_INPUT_PATHS)


def scenario_fingerprint(scenario, rom_digest, harness_source=None, driver=None, env=None,
                         scopes=None, engine=None, observed=None, driver_files=None):
    """The cache key, or None when this run may not be cached at all.

    None means "refuse to cache" and is returned whenever an input cannot be pinned: no ROM
    digest (rom_input_hash could not read the decomp HEAD), or a scenario harness.lua does
    not define. Unknown means conservative, never optimistic.

    `scopes` is the build's own scope manifest (tools/build_scopes.py). Given one, the ROM
    half of the key becomes the digests of just the scopes this scenario depends on, so a
    ch05 edit stops re-running the prologue -- the whole of #255 phase 2. Without one
    (`None`: an older cache slot, or a build that emitted nothing) the key falls back to
    `rom_input_hash`, which is phase 1's coarse but correct answer.
    """
    if rom_digest is None:
        return None
    harness_source = _read(HARNESS) if harness_source is None else harness_source
    if driver is None:
        files = dict(driver_source())
        # Tests (and only tests) hand in overrides for individual driver files.
        files.update(driver_files or {})
        driver = scenario_driver_text(scenario.name, files, harness_source)
    env = os.environ if env is None else env
    funcs = harness_functions(harness_source)
    if scenario.name not in funcs:
        return None
    h = hashlib.sha256()
    if scopes is None:
        rom_part = 'rom:%s' % rom_digest
    else:
        # Absent is NOT the same as unchanged: a scope the scenario depends on that the
        # build never wrote has to key differently from one that came out identical, or
        # "the step vanished" and "the step did not move" are the same verdict.
        rom_part = 'engine:%s|scopes:%s' % (
            engine_input_hash() if engine is None else engine,
            ','.join('%s=%s' % (scope, (scopes.get(scope) or {}).get('digest', 'absent'))
                     for scope in sorted(scenario_scopes(scenario, observed=observed))))
    h.update(('matrix-verdict-v1\n%s\nentry:%s\n' % (rom_part, export_env(scenario))).encode())
    for key in PLAYTEST_ENV_KEYS:
        value = env.get(key)
        # run.sh DEFAULTS PT_DIFFICULTY, so unset and an explicit "normal" are the same run.
        # Normalising here keeps them on one cache key instead of paying for the same watched
        # run twice (the other keys have no default -- absent really is a different run).
        if key == 'PT_DIFFICULTY' and not value:
            value = 'normal'
        if value:
            h.update(('env:%s=%s\n' % (key, value)).encode())
    h.update(b'driver:\n')
    h.update(driver.encode())
    h.update(b'\nshared:\n')
    h.update(harness_shared(harness_source).encode())
    # A checkpoint-backed scenario replays through its `ckpt_X` builder, which run.sh
    # invokes directly -- nothing in Lua calls it, so it lands in neither the closure nor
    # the shared residue. Without this, editing ckpt_ch02start leaves ch02baxby's key still.
    closure = reaches(scenario.name, funcs)
    if scenario.checkpoint_builder:
        closure = closure | reaches(scenario.checkpoint_builder, funcs)
    for name in sorted(closure):
        h.update(('\nfn:%s\n' % name).encode())
        h.update(funcs[name][0].encode())
    return h.hexdigest()[:32]


def _observed_path(scenario, cache_dir=None):
    """Where a scenario's observed traversal lives.

    Deliberately NOT keyed by fingerprint: it has to be readable in order to COMPUTE the
    fingerprint. Storing a wider set than reality only costs a re-run, and a narrower one
    cannot happen -- see `scenario_scopes` for why.
    """
    return os.path.join(cache_dir or VERDICT_CACHE_DIR, '%s.chapters.json' % scenario)


def load_observed(scenario, cache_dir=None):
    """{'chapters': [...], 'rules': [...]} from this scenario's last run, or {}."""
    try:
        with open(_observed_path(scenario, cache_dir)) as fh:
            seen = json.load(fh)
    except (OSError, ValueError):
        return {}
    if isinstance(seen, list):            # pre-2.5 file: chapters only
        return {'chapters': seen or None}
    return seen if isinstance(seen, dict) else {}


def load_observed_chapters(scenario, cache_dir=None):
    return load_observed(scenario, cache_dir).get('chapters') or None


def store_observed(scenario, log_text, cache_dir=None):
    """Record where this run went and which rules decided it, whatever its verdict -- a
    FAIL's traversal is just as true as a PASS's, and refusing to learn from it would keep
    the next key coarse."""
    seen = {'chapters': observed_chapters(log_text)}
    if not any(seen.values()):
        return
    cache_dir = cache_dir or VERDICT_CACHE_DIR
    os.makedirs(cache_dir, exist_ok=True)
    with open(_observed_path(scenario, cache_dir), 'w') as fh:
        json.dump(seen, fh)


def _verdict_slot(scenario, fingerprint, cache_dir=None):
    return os.path.join(cache_dir or VERDICT_CACHE_DIR, '%s-%s' % (scenario, fingerprint))


def load_cached_verdict(scenario, fingerprint, cache_dir=None):
    """The stored verdict for this exact fingerprint, or None. Only ever a PASS."""
    if not fingerprint:
        return None
    try:
        with open(_verdict_slot(scenario, fingerprint, cache_dir) + '.json') as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None             # missing or corrupt: a miss, not a crash
    if data.get('verdict') != 'PASS':
        return None
    return data


def store_cached_verdict(scenario, fingerprint, outcome, cache_dir=None):
    """Keep a green verdict AND its artifacts, so a cached PASS stays inspectable.

    A cached green nobody can look at is a green nobody can audit, so the run's log and
    screenshots travel with the verdict and the stored `artifacts` path points at them --
    `/tmp/playtest-<name>` will have been overwritten by whatever ran last. That costs a few
    MB per scenario (ch05arena: 198 frames, 4.7 MB) and it is deliberate: one slot per
    scenario, gitignored, and the whole gate lands around 100 MB.
    """
    cache_dir = cache_dir or VERDICT_CACHE_DIR
    keep = None
    if fingerprint and outcome.verdict == 'PASS':
        keep = _verdict_slot(scenario, fingerprint, cache_dir)
        os.makedirs(cache_dir, exist_ok=True)
        kept = outcome.artifacts
        if outcome.artifacts and os.path.isdir(outcome.artifacts):
            shutil.rmtree(keep, ignore_errors=True)
            shutil.copytree(outcome.artifacts, keep)
            kept = keep
        with open(keep + '.json', 'w') as fh:
            json.dump({'scenario': scenario, 'rom': outcome.rom, 'verdict': outcome.verdict,
                       'seconds': round(outcome.seconds, 1), 'artifacts': kept,
                       'fingerprint': fingerprint, 'stored': time.time()}, fh, indent=2)
    # One slot per scenario: the cache tracks HEAD, not history. The `-` in the glob is
    # load-bearing -- `ch01-*` must not sweep away `ch01win`'s slot.
    #
    # This runs for a FAIL too, and that is the point. A red on the same key means the
    # inputs did not move but the verdict did, so the stored green is now a lie; leaving it
    # there makes the next matrix run report a scenario green while it is red right now.
    # A fresh red always wins over a stored green.
    for old in glob.glob(os.path.join(cache_dir, '%s-*' % scenario)):
        if keep and os.path.basename(old).startswith(os.path.basename(keep)):
            continue
        if os.path.isdir(old):
            shutil.rmtree(old, ignore_errors=True)
        else:
            try:
                os.remove(old)
            except OSError:
                pass


class VerdictCache(object):
    """Wires the fingerprint to `execute()`'s two injected hooks.

    Every fingerprint is taken BEFORE anything is built or run, so the key describes the
    tree the verdict will be earned against rather than whatever the build left behind.
    """

    def __init__(self, scenarios, enabled=True):
        self.enabled = enabled
        self.fingerprints = {}
        # Only a VERDICT scenario may be skipped. A `record` scenario exists to refill
        # /tmp/playtest-<name> with motion frames that make_gif.py then reads by hand,
        # and a `diagnostic` asserts nothing -- serving either from cache hands the
        # caller whatever ran last under that path.
        self._scenarios = [s for s in scenarios if s.kind == 'verdict']
        self._digests = {}
        self.refresh()

    def refresh(self, built_rom=None):
        """(Re)compute the keys. Called once up front, and AGAIN after each build.

        The second call is what phase 2 needs: a scope manifest only exists once the build
        that produced it has run, so a configuration whose ROM inputs moved cannot be keyed
        on scopes until it is built. Before the build we key off the manifest stored in the
        ROM cache slot -- which is exactly right when the ROM is unchanged, and is what
        keeps phase 1's "a fully cached group is never built" path alive.
        """
        for s in self._scenarios:
            flags = tuple(s.make_flags)
            if flags not in self._digests:
                self._digests[flags] = rom_input_hash(s.make_flags)
            digest = self._digests[flags]
            if built_rom is not None and s.rom != built_rom:
                continue
            self.fingerprints[s.name] = scenario_fingerprint(
                s, digest,
                scopes=self._scope_manifest(s.rom, digest, fresh=built_rom is not None),
                observed=load_observed_chapters(s.name))

    def _scope_manifest(self, rom, digest, fresh=False):
        """The build's own account of what it wrote, or None (fall back to the ROM key)."""
        if fresh:
            return build_scopes.load_manifest(SCOPES_PATH)
        if digest is None:
            return None
        return build_scopes.load_manifest(_cache_slot(rom, digest) + '.scopes.json')

    def hit(self, scenario):
        return self.lookup(scenario) is not None

    def scoped(self, scenario):
        """True when this scenario's key already knows what the build wrote. False means
        the answer is still the coarse whole-ROM one and will sharpen after the build."""
        if not self.enabled or scenario.kind != 'verdict':
            return True
        return self._scope_manifest(
            scenario.rom, self._digests.get(tuple(scenario.make_flags))) is not None

    def lookup(self, scenario):
        if not self.enabled:
            return None
        hit = load_cached_verdict(scenario.name, self.fingerprints.get(scenario.name))
        if hit is None:
            return None
        return Outcome(scenario.name, scenario.rom, hit['verdict'], hit.get('seconds', 0.0),
                       hit.get('artifacts', ''), cached=True)

    def store(self, scenario, outcome):
        """Storing is only half of this: a RED must evict a stored green even with the
        cache disabled, or `MX_NO_CACHE=1` becomes a way to fail a scenario and leave the
        lie in place. A disabled PASS still writes nothing -- bypassing the cache is not
        the same as clearing it."""
        log = os.path.join(outcome.artifacts or '', 'playtest.log')
        if os.path.isfile(log):
            with open(log, errors='replace') as fh:
                store_observed(scenario.name, fh.read())
        fingerprint = self.fingerprints.get(scenario.name) if self.enabled else None
        if fingerprint or outcome.verdict != 'PASS':
            store_cached_verdict(scenario.name, fingerprint, outcome)
        return outcome


def parse_verdict(text, returncode):
    """Read run.sh's verdict out of its captured output.

    The harness stamps every line with the frame it was logged on -- the verdict
    line reads `[f007234] RESULT: PASS -- ...`, never starts with RESULT: -- so this
    matches anywhere in the line. run.sh's exit status is the corroborating signal
    (0 only on PASS); if the two disagree, the run did not end cleanly, so fail.

    ERROR and FAIL are DIFFERENT FACTS and the table has to keep them apart. "The scenario
    proved something false" is a finding about the game; "the run never finished" is a finding
    about the machine, and run.sh says which by writing `RESULT: ERROR -- ...`. Reading every
    non-PASS RESULT line as FAIL downgraded those: one SUITE=all sweep ran its long canonical
    scenarios at ~15fps instead of 240 under contention, timed out, and tabled eight chapters as
    broken. Every one passed when re-run serially -- but not before the FAILs had been chased as
    real.

    Since #345 run.sh no longer kills on WALL time at all: the deadline is a FRAME budget, so
    contention changes how long a run takes and not whether it passes. The ERROR arm still
    matters -- `OVERRAN its frame budget` and `STALLED: no frame progress` are both real, and
    both are findings about the run rather than about the game."""
    verdict = None
    for line in text.splitlines():
        if 'RESULT:' in line:
            if 'RESULT: PASS' in line:
                verdict = 'PASS'
            elif 'RESULT: ERROR' in line:
                verdict = 'ERROR'
            else:
                verdict = 'FAIL'
    if verdict is None:
        return 'ERROR'          # no verdict at all: crash, or a refused run
    if verdict == 'ERROR':
        return 'ERROR'          # a run that did not finish is not evidence about the game
    if verdict == 'PASS' and returncode != 0:
        return 'FAIL'
    return verdict


def progress_line(outcome):
    """What a scenario prints when it FINISHES. Dispatch lines alone stopped being progress
    the moment four scenarios started at once (#310): they all appear immediately and then
    nothing moves until the table. This is the other half -- name, verdict and time, in the
    order they actually complete."""
    return '   %-8s %-24s %s' % (outcome.verdict, outcome.scenario,
                                 human_duration(outcome.seconds))


def _run_scenario(scenario, log_dir):
    env = dict(os.environ)
    env['PT_HOST_CHAPTER'] = str(scenario.host_chapter)
    started = time.time()
    print('-- %s [%s]' % (scenario.name, scenario.rom))
    proc = subprocess.run([RUN_SH, scenario.name], cwd=REPO, env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    seconds = time.time() - started
    text = proc.stdout.decode('utf-8', 'replace')
    with open(os.path.join(log_dir, '%s.log' % scenario.name), 'w') as fh:
        fh.write(text)
    verdict = parse_verdict(text, proc.returncode)
    tail = '' if verdict == 'PASS' else '\n'.join(text.strip().splitlines()[-12:])
    outcome = Outcome(scenario.name, scenario.rom, verdict, seconds,
                      '/tmp/playtest-%s' % scenario.name, tail)
    print(progress_line(outcome))
    return outcome


RESULTS_NAME = 'results.json'


def results_path(log_dir):
    return os.path.join(log_dir, RESULTS_NAME)


def clear_results(log_dir):
    """Drop a previous run's verdict file so nothing can read it as this run's."""
    try:
        os.remove(results_path(log_dir))
    except OSError:
        pass


def cmd_run(args):
    m = Manifest.load()
    names = m.select(suite=args.suite,
                     scenarios=args.scenarios.split(',') if args.scenarios else None,
                     all_verdicts=args.all)
    groups = m.plan(names, rom=args.rom)
    log_dir = args.out
    os.makedirs(log_dir, exist_ok=True)
    # A run takes minutes, so the verdict file is what everything downstream polls for.
    # Leaving the last run's copy in place means a poller reads STALE verdicts the
    # instant it starts -- and a crashed run leaves them there looking authoritative.
    # (Same hazard run.sh already clears for the LLM handshake files.)
    clear_results(log_dir)

    verdicts = VerdictCache([s for g in groups for s in g.scenarios],
                            enabled=not (args.no_verdict_cache or os.environ.get('MX_NO_CACHE')))
    total = sum(len(g.scenarios) for g in groups)
    print('matrix: %d scenario(s) across %d ROM configuration(s) -> %s'
          % (total, len(groups), log_dir))
    # Naming what is already earned BEFORE anything runs is what makes --dry-run answer
    # "what would this actually cost me" -- and it is how you check an invalidation
    # without spending an emulator run to see it.
    for g in groups:
        print('  %-10s %s' % (g.rom, ' '.join(
            s.name + ('(cached)' if verdicts.hit(s) else '') for s in g.scenarios)))
    # Honest about what this listing can and cannot know. A configuration whose ROM inputs
    # moved has no scope manifest yet -- it only exists once the build that produced it has
    # run -- so every one of its scenarios reads as "will run" here and most of them will
    # turn out to be cached once the build says what it actually wrote (#255 phase 2).
    if any(not verdicts.scoped(s) for g in groups for s in g.scenarios):
        print('matrix: a ROM configuration changed -- what it actually re-runs is decided '
              'after its build')
    if args.dry_run:
        return 0

    jobs = resolve_jobs(args.jobs)
    use_cache = not (args.no_rom_cache or os.environ.get('MX_NO_ROM_CACHE'))
    if jobs > 1:
        print('matrix: running up to %d headless scenarios at a time '
              '(builds and headed runs stay serial)' % jobs)
    report = execute(groups,
                     build=lambda rom, flags: _build(rom, flags, log_dir, use_cache=use_cache),
                     run_scenario=lambda s: verdicts.store(s, _run_scenario(s, log_dir)),
                     lookup_cached=verdicts.lookup,
                     after_build=verdicts.refresh,
                     jobs=jobs)
    print('')
    print(render_table(report))
    if not report.ok:
        print('')
        print(render_failures(report))
    with open(results_path(log_dir), 'w') as fh:
        json.dump(report.as_dict(), fh, indent=2)
    print('results: %s' % results_path(log_dir))
    return report.exit_code


def cmd_resolve(args):
    print(export_env(Manifest.load().resolve(args.scenario)))
    return 0


def cmd_check_rom(args):
    m = Manifest.load()
    problem = check_rom(m, m.resolve(args.scenario))
    if problem:
        print('matrix: %s' % problem, file=sys.stderr)
        return 1
    return 0


def cmd_list(args):
    m = Manifest.load()
    if args.suites:
        for name in sorted(m.suites):
            print('%-10s %s' % (name, ' '.join(m.suites[name])))
        return 0
    for name in m.scenarios:
        s = m.resolve(name)
        print('%-20s %-10s host=%-4s %-10s %s'
              % (name, s.rom, s.host_chapter, s.kind, s.checkpoint or ''))
    return 0


def main(argv=None):
    # A matrix run is tens of minutes of builds and emulator time. Line-buffer so
    # `make matrix > log` shows progress as it happens instead of dumping at the end.
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except AttributeError:      # pragma: no cover -- python < 3.7
        pass
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest='cmd')

    run = sub.add_parser('run', help='build each ROM config once, run its scenarios')
    run.add_argument('--suite')
    run.add_argument('--scenarios')
    run.add_argument('--all', action='store_true', help='every non-manual verdict scenario')
    run.add_argument('--rom', help='force one ROM config (needed for chapter-generic scenarios)')
    run.add_argument('--out', default='/tmp/playtest-matrix')
    run.add_argument('--dry-run', action='store_true')
    run.add_argument('--jobs', type=int, default=None,
                     help='scenarios to run at a time within one ROM config (or MX_JOBS; '
                          'defaults to half the cores, capped at %d). Headless scenarios '
                          'only -- headed ones stay serial. See execute()' % MEASURED_JOBS)
    run.add_argument('--no-rom-cache', action='store_true',
                     help='always `make`, never reuse a cached ROM (or MX_NO_ROM_CACHE=1)')
    run.add_argument('--no-verdict-cache', action='store_true',
                     help='re-run every scenario even if its inputs are unchanged '
                          '(or MX_NO_CACHE=1)')
    run.set_defaults(fn=cmd_run)

    res = sub.add_parser('resolve', help='emit shell assignments for run.sh')
    res.add_argument('scenario')
    res.set_defaults(fn=cmd_resolve)

    chk = sub.add_parser('check-rom', help='does the built ROM host this scenario?')
    chk.add_argument('scenario')
    chk.set_defaults(fn=cmd_check_rom)

    lst = sub.add_parser('list', help='list scenarios (or --suites)')
    lst.add_argument('--suites', action='store_true')
    lst.set_defaults(fn=cmd_list)

    args = ap.parse_args(argv)
    if not getattr(args, 'fn', None):
        ap.print_help()
        return 2
    try:
        return args.fn(args)
    except ManifestError as exc:
        print('matrix: %s' % exc, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
