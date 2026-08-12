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
  * scenarios CAN run in parallel within a configuration (--jobs), though it is off
    by default -- measured, and it does not pay here. See execute().
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
MANIFEST = os.path.join(HERE, 'matrix.yaml')
HARNESS = os.path.join(HERE, 'harness.lua')
RUN_SH = os.path.join(HERE, 'run.sh')

# The `make` invocation the runner builds each configuration with.
CAMPAIGN = os.environ.get('CAMPAIGN', 'rime-of-the-frostmaiden')

_SCENARIO_DEF = re.compile(r'^scenarios\.([A-Za-z0-9_]+)\s*=', re.M)


class ManifestError(Exception):
    """The manifest disagrees with reality -- a bad key, a bad reference, a bad ask."""


class Scenario(object):
    """One fully resolved row: defaults + class rules + the scenario's own entry."""

    FIELDS = ('rom', 'host_chapter', 'fps', 'vsync', 'deadline', 'checkpoint',
              'kind', 'manual')

    def __init__(self, name, values, rom_configs, checkpoint_deadline):
        self.name = name
        self.rom = values['rom']
        self.host_chapter = values['host_chapter']
        self.fps = int(values['fps'])
        self.vsync = int(values['vsync'])
        self.deadline = int(values['deadline'])
        self.kind = values['kind']
        self.manual = bool(values.get('manual', False))
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
        with open(path or MANIFEST) as fh:
            return cls(yaml.safe_load(fh))

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
    The exception is a CHECKPOINT: `states/<name>.ss` is a shared file that a scenario will
    MINT if it is missing or stale for this ROM build, so two scenarios wanting the same
    checkpoint would race to write it. Those run serially, one checkpoint at a time.

    (Today every scenario in the gate suite is checkpoint-free, so the gate parallelises
    whole. The split exists so a future checkpointed scenario cannot silently corrupt a
    state file the moment somebody adds it to a suite.)
    """
    parallel, serial = [], []
    for s in scenarios:
        (serial if s.checkpoint else parallel).append(s)
    return parallel, serial


def execute(groups, build, run_scenario, jobs=1, lookup_cached=None):
    """Run the plan. `build`, `run_scenario` and `lookup_cached` are injected so the
    ordering and aggregation logic is testable without a ROM or an emulator.

    A failed build blocks only its own group: the rest of the matrix still runs,
    because one broken configuration should not hide the state of the others.

    `lookup_cached(scenario)` returns a previously earned Outcome, or None. A group
    whose scenarios are ALL cached is never built -- that is the biggest win in the
    feature, because it makes a doc-only or harness-only change cost no `make` and no
    emulator at all (#255). Outcomes are emitted in the group's own order whether they
    ran or not, so the table does not reshuffle itself as the cache fills.

    `jobs` > 1 runs a group's checkpoint-free scenarios concurrently. BUILDS always stay
    serial and never overlap a run: the tree holds ONE `fireemblem8.gba`, so a second `make`
    would swap the ROM out from under a live emulator (and two builds in one tree corrupt
    each other outright -- see CLAUDE.md).

    **`jobs` DEFAULTS TO 1 BECAUSE PARALLELISM WAS MEASURED AND DOES NOT PAY HERE** (2026-08-09,
    8 logical / 4 performance cores). Scenarios run mGBA at `fps: 240` -- deliberately
    unthrottled, so each one is CPU-bound and already saturates a core. Four at a time simply
    divided the same throughput: individual scenarios went 10s -> 67s, total wall did NOT move
    (444s serial vs 439s at jobs=4), and four scenarios blew their WALL-CLOCK deadlines and
    reported ERROR/FAIL -- turning contention into false red. A gate that fails at random is
    worse than a slow one. The knob stays because a machine with many more real cores could
    make it pay, but prove it with a measurement before raising the default. The speed win that
    DID land is the ROM cache below.
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
    """Every harness function reachable from `name`, including itself."""
    seen = seen if seen is not None else set()
    if name in seen or name not in funcs:
        return seen
    seen.add(name)
    body = funcs[name][0]
    for callee in set(re.findall(r'\b(\w+)\s*\(', body)):
        if callee in funcs and callee != name:
            reaches(callee, funcs, seen)
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


def built_rom_config(rom_configs, stamp_path=None):
    """Name the ROM configuration currently sitting in the tree, or None if the stamp
    is missing (an old build) or matches nothing the manifest knows about.

    build_campaign.py writes the stamp; matching is on the EXACT flag set, because
    `canonical` is "no flags" and would otherwise match every build."""
    try:
        with open(stamp_path or BUILD_STAMP) as fh:
            stamp = json.load(fh)
    except (OSError, ValueError):
        return None
    on = {k for k, v in (stamp.get('flags') or {}).items() if v}
    for name, flags in rom_configs.items():
        if set(flags) == on:
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
STAMP_PATH = os.path.join(REPO, '.build-config.json')
ROM_CACHE_DIR = os.path.join(REPO, '.matrix-romcache')
ROM_INPUT_PATHS = ('campaigns', 'engine', 'tools/inject', 'tools/build_campaign.py',
                   'tools/portrait_tool.py', 'tools/feditor_to_banim.py', 'Makefile')


def rom_input_hash(make_flags):
    """A digest of everything the ROM is built from, for cache keying.

    Files are fingerprinted by (path, size, mtime_ns) rather than content: hashing the whole
    campaign tree on every run would cost more than it saves, and the failure mode is the safe
    one -- a touched-but-identical file forces a needless REBUILD, never a stale ROM. The
    unsafe direction (edited content landing on a byte-identical size AND timestamp) does not
    happen with real editors or with git.
    """
    h = hashlib.sha256()
    h.update(('flags:' + ' '.join(make_flags) + '|campaign:' + CAMPAIGN + '\n').encode())
    try:
        head = subprocess.check_output(['git', '-C', os.path.join(REPO, 'fireemblem8u'),
                                        'rev-parse', 'HEAD'], stderr=subprocess.DEVNULL)
        h.update(b'decomp:' + head)
    except (subprocess.CalledProcessError, OSError):
        return None             # cannot pin the decomp -> refuse to cache rather than guess
    for rel in ROM_INPUT_PATHS:
        path = os.path.join(REPO, rel)
        if os.path.isfile(path):
            files = [path]
        elif os.path.isdir(path):
            files = [os.path.join(root, name)
                     for root, dirs, names in os.walk(path)
                     for name in names
                     if not name.startswith('.')
                     and not any(d in root for d in ('__pycache__', '.git'))]
        else:
            continue
        for f in sorted(files):
            try:
                st = os.stat(f)
            except OSError:
                continue
            h.update(('%s|%d|%d\n' % (os.path.relpath(f, REPO), st.st_size,
                                      st.st_mtime_ns)).encode())
    return h.hexdigest()[:32]


def _cache_slot(rom, digest):
    return os.path.join(ROM_CACHE_DIR, '%s-%s' % (rom, digest))


def restore_cached_rom(rom, digest):
    """Copy a cached ROM (and its build stamp) into the tree. True if it was there."""
    if digest is None:
        return False
    slot = _cache_slot(rom, digest)
    gba, stamp = slot + '.gba', slot + '.json'
    if not (os.path.isfile(gba) and os.path.isfile(stamp)):
        return False
    shutil.copyfile(gba, ROM_PATH)
    shutil.copyfile(stamp, STAMP_PATH)
    return True


def store_cached_rom(rom, digest):
    """Snapshot the freshly built ROM + its stamp under this input digest."""
    if digest is None:
        return
    if not (os.path.isfile(ROM_PATH) and os.path.isfile(STAMP_PATH)):
        return                  # nothing to cache (stamp is what run.sh checks the ROM against)
    gba, stamp = ROM_PATH, STAMP_PATH
    os.makedirs(ROM_CACHE_DIR, exist_ok=True)
    slot = _cache_slot(rom, digest)
    shutil.copyfile(gba, slot + '.gba')
    shutil.copyfile(stamp, slot + '.json')
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


def driver_source(here=None):
    """Everything OUTSIDE harness.lua that decides what a scenario does.

    `controller.lua` classifies every state a guarded input is authorised against;
    `symbols.lua`/`procscr.lua` name the memory it reads; `clearbot`/`pathing`/`liveness`
    and friends are dofile'd straight into the run; and `run.sh` chooses the fps, the
    deadline, the checkpoint handling and the wrapper the emulator actually loads. Any of
    them can turn a PASS into a FAIL without harness.lua changing a byte.

    `gen_symbols.py` is in here too, and for a reason worth stating: run.sh regenerates
    symbols.lua/procscr.lua from the ELF AFTER the fingerprint has been taken, so hashing
    only the generated files would let an edit to what they contain slip past the key for
    one run. Hashing the generator as well closes that window.

    harness.lua is pointedly absent: it is keyed by CLOSURE, and folding it in here would
    undo the whole reason the closure exists.
    """
    here = here or HERE
    files = [p for p in glob.glob(os.path.join(here, '*.lua'))
             if not os.path.basename(p).startswith('test_')
             and os.path.basename(p) != 'harness.lua']
    files.append(os.path.join(here, 'run.sh'))
    files.append(os.path.join(here, 'gen_symbols.py'))
    parts = []
    for path in sorted(files):
        if os.path.isfile(path):
            parts.append('%s\n%s' % (os.path.basename(path), _read(path)))
    return '\n'.join(parts)


def scenario_fingerprint(scenario, rom_digest, harness_source=None, driver=None):
    """The cache key, or None when this run may not be cached at all.

    None means "refuse to cache" and is returned whenever an input cannot be pinned: no ROM
    digest (rom_input_hash could not read the decomp HEAD), or a scenario harness.lua does
    not define. Unknown means conservative, never optimistic.
    """
    if rom_digest is None:
        return None
    harness_source = _read(HARNESS) if harness_source is None else harness_source
    driver = driver_source() if driver is None else driver
    funcs = harness_functions(harness_source)
    if scenario.name not in funcs:
        return None
    h = hashlib.sha256()
    h.update(('matrix-verdict-v1\nrom:%s\nentry:%s\n' % (rom_digest, export_env(scenario))).encode())
    h.update(b'driver:\n')
    h.update(driver.encode())
    h.update(b'\nshared:\n')
    h.update(harness_shared(harness_source).encode())
    for name in sorted(reaches(scenario.name, funcs)):
        h.update(('\nfn:%s\n' % name).encode())
        h.update(funcs[name][0].encode())
    return h.hexdigest()[:32]


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
    if not fingerprint or outcome.verdict != 'PASS':
        return
    cache_dir = cache_dir or VERDICT_CACHE_DIR
    slot = _verdict_slot(scenario, fingerprint, cache_dir)
    os.makedirs(cache_dir, exist_ok=True)
    kept = outcome.artifacts
    if outcome.artifacts and os.path.isdir(outcome.artifacts):
        shutil.rmtree(slot, ignore_errors=True)
        shutil.copytree(outcome.artifacts, slot)
        kept = slot
    with open(slot + '.json', 'w') as fh:
        json.dump({'scenario': scenario, 'rom': outcome.rom, 'verdict': outcome.verdict,
                   'seconds': round(outcome.seconds, 1), 'artifacts': kept,
                   'fingerprint': fingerprint, 'stored': time.time()}, fh, indent=2)
    # One slot per scenario: the cache tracks HEAD, not history. The `-` in the glob is
    # load-bearing -- `ch01-*` must not sweep away `ch01win`'s slot.
    for old in glob.glob(os.path.join(cache_dir, '%s-*' % scenario)):
        if os.path.basename(old).startswith('%s-%s' % (scenario, fingerprint)):
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
        if not enabled:
            return
        digests = {}
        for s in scenarios:
            flags = tuple(s.make_flags)
            if flags not in digests:
                digests[flags] = rom_input_hash(s.make_flags)
            self.fingerprints[s.name] = scenario_fingerprint(s, digests[flags])

    def hit(self, scenario):
        return self.lookup(scenario) is not None

    def lookup(self, scenario):
        if not self.enabled:
            return None
        hit = load_cached_verdict(scenario.name, self.fingerprints.get(scenario.name))
        if hit is None:
            return None
        return Outcome(scenario.name, scenario.rom, hit['verdict'], hit.get('seconds', 0.0),
                       hit.get('artifacts', ''), cached=True)

    def store(self, scenario, outcome):
        if self.enabled:
            store_cached_verdict(scenario.name, self.fingerprints.get(scenario.name), outcome)
        return outcome


def parse_verdict(text, returncode):
    """Read run.sh's verdict out of its captured output.

    The harness stamps every line with the frame it was logged on -- the verdict
    line reads `[f007234] RESULT: PASS -- ...`, never starts with RESULT: -- so this
    matches anywhere in the line. run.sh's exit status is the corroborating signal
    (0 only on PASS); if the two disagree, the run did not end cleanly, so fail."""
    verdict = None
    for line in text.splitlines():
        if 'RESULT:' in line:
            verdict = 'PASS' if 'RESULT: PASS' in line else 'FAIL'
    if verdict is None:
        return 'ERROR'          # no verdict at all: crash, timeout, or a refused run
    if verdict == 'PASS' and returncode != 0:
        return 'FAIL'
    return verdict


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
    return Outcome(scenario.name, scenario.rom, verdict, seconds,
                   '/tmp/playtest-%s' % scenario.name, tail)


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
    if args.dry_run:
        return 0

    jobs = args.jobs if args.jobs else int(os.environ.get('MX_JOBS', '1'))
    use_cache = not (args.no_rom_cache or os.environ.get('MX_NO_ROM_CACHE'))
    if jobs > 1:
        print('matrix: running up to %d scenarios at a time (builds stay serial)' % jobs)
    report = execute(groups,
                     build=lambda rom, flags: _build(rom, flags, log_dir, use_cache=use_cache),
                     run_scenario=lambda s: verdicts.store(s, _run_scenario(s, log_dir)),
                     lookup_cached=verdicts.lookup,
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
                     help='scenarios to run at a time within one ROM config (default 1, '
                          'or MX_JOBS). MEASURED AND OFF BY DEFAULT -- see execute()')
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
