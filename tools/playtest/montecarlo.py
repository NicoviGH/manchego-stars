#!/usr/bin/env python3
"""The bot's run pool (#510 step 9 PR F, Task 11): many runs of the ROM at once, one
`mgba-headless` each, every record kept.

    python3 tools/playtest/montecarlo.py attempts --env <campaign env .json> --attempts 8 \\
        [--jobs 4] [--out runs.jsonl] [--vanilla] [--seed 1]

`attempts` plays attempts 1..N of the chapter at the env's `from` start side by side (env
`attempt = k` per worker; campaign.lua) and names the lowest that cleared with everyone alive.
That is what the campaign's own loop finds: every attempt loads the same start state, the
game's RNG in it, and the styles are drawn without reading a result, so attempt k plays the
same alone as after k - 1 failures.

A worker is `run.sh <scenario>` with PT_RUN_TAG, so copies of one scenario share no run dir,
leftover kill or save (run.sh). Its records are read from the emulator's own stdout
(`mgba-stdout.log` in its run dir) and each is appended WHOLE to the runs file: one os.write
of one line on an O_APPEND descriptor, so writers never interleave. A worker that leaves no
BOTRUN record is recorded as `crashed` with its run dir, or as `no_style` when its campaign
says the chapter start has fewer styles than the attempt asked for.

`paired_verdict` says where one chapter-and-mode cell stands from its Manchego Stars/twin pairs,
on one endpoint: did a protected unit die anywhere in attempt 1 (ADR 0385). It is read at 50, 100
and 200 pairs with exact Clopper-Pearson bounds split over the bounds, the looks and the frozen
cell count, and labelled EQUIVALENT (inside +-10 points), HARDER, EASIER or INCONCLUSIVE.
`pilot` plays one chapter cell on the 50 pilot seeds first and chooses paired or marginal
analysis; `cell` then plays the confirmatory seeds with that choice.

    python3 tools/playtest/montecarlo.py starts --game ours|vanilla [--count 10] [--jobs 8]
    python3 tools/playtest/montecarlo.py pilot --chapter 3 [--starts 10]
    python3 tools/playtest/montecarlo.py cell --analysis paired \
        (--chapter <n> [--starts 10] | --ours <env .json> --vanilla <env .json> \
         --ours-chapter <i> --vanilla-chapter <i> [--mode normal]) [--jobs 4]

A chapter cell (Manchego Stars chapter n and its twin) plays attempt 1 from pinned chapter starts, each
from its own New Game campaign with its own seed, so each start carries its own dice and party
(T100e): seed s plays the ((s - the set's first seed) mod K)-th of an arm's K starts, the
first K pinned (by seed) that reached the chapter. `starts` plays and pins those campaigns
(the `starts` seed set, campaign `cs-s<seed>`) in each game's store (cell-starts.json beside
runs.jsonl): the store is the ROM's, so a Manchego Stars ROM change means
`starts --game ours` again.

Before a cell or pilot is read, both arms' first attempts pass FR-029's invariants
(`validity`): environment-clean at 90% or more, no sandbox-fault death, blindspot and
unclassified attempts under 10%, no unlabelled over-cap death, no unjustified seize skip, and
the twin losing someone under 85% of the time. A cell that fails one is NOT READABLE, naming
it, and stops there. Each `pilot` and `cell` appends its record to references/sim/cells.jsonl.

    python3 tools/playtest/montecarlo.py report [cells.jsonl] [--decision party|enemy|chapter \
        [--components a,b]] [--post]

`report` says one instrument's cells in sentences (FR-031): the header, the canary, one sentence
a cell, the anomalies with their `story` commands, the validity failures and the descriptive
data, each beside the twin; `--decision` reads only that decision's components (FR-032);
`--post` writes it under build/ and prints the `gh issue comment 510` command, never running it.

    python3 tools/playtest/montecarlo.py story <trace .jsonl[.gz]>

`story` reads one run's trace (botrun.lua) as plain text, turn by turn, with the game's own
forecast and every blow.

    python3 tools/playtest/montecarlo.py suite [--held-out | --freeze [--override WHY]] [--kept] [--jobs 8]

`suite` plays the difficulty instrument's frozen suite (#510 step 9; matrix.yaml's
`instrument:` section, ADR 0387): attempt 1 of each pinned chapter start, from its saved state,
under each of its seeds, and checks each failing-decision snapshot still loads to its board.
The tuning seeds print each run and are judged on the frozen baseline (suite-frozen.json,
ADR 0395): an invariant that held and fails, a new stall, an unlabelled fallback, and SC-003's
calls more than 20% over the frozen count; a death the frozen run did not have is said, a
signal that never blocks (T107a). --held-out plays the held-out
seeds too, said only as counts, and gives the promotion result; --freeze does that and writes
the frozen baseline when the candidate is promoted (--override WHY freezes a refused one, on
Nicolas's word, and keeps WHY in the file). --kept judges this instrument's kept runs
again instead of playing them (after a replay witnessed a new death, so the suite says its
label). It refuses a start that
no longer matches its pin, and any job over 8 wall-hours (SC-007), before anything runs.

    python3 tools/playtest/montecarlo.py audit <runs .jsonl> --diag <log> [--diag <log> ...]

    python3 tools/playtest/montecarlo.py replay <runs .jsonl> \\
        --record <campaign>/<seed>/<chapter>/<attempt> --mode force|full_info|deep \\
        [--force <act key> ...] [--trace <filed trace>] [--char 0xNN] \\
        [--ref N]

`replay` plays one diagnostic replay of a suite run's death from that run's own task, pinned at
the last decision that moved the dead unit, and appends only its DIAG lines to diag.jsonl beside
the runs file: never a record. It refuses a run of another instrument than the code now. `audit`
labels each death of one instrument's runs from those DIAG lines: a label counts only when a
matched replay of a different plan avoided the death (ADR 0392). Every other death stays
unclassified, its own grading shown as proposed only, and a DIAG line that matches no run is an
orphan, counted.

`cell` plays one chapter-and-mode cell to its verdict. Pair s is campaign s of each game: from
New Game, the game seeded once with s and never again, as a player's own save; each chapter is
retried until it clears clean (campaign.lua), and the pair's result is the campaign's FIRST
attempt at the cell's chapter. One sweep's campaigns serve every chapter's cell. Runs are kept in
each game's store (`run.sh --simdir`/runs.jsonl), stamped with a hash of the whole campaign env,
the mode and the bot code; a kept campaign with the same stamp is read, never played again. A
run without a game result (a crash, a campaign that never reached the chapter) is never guessed
at: the cell stops and reports what that run said.

Comparing two versions of the bot: play both on the SAME env. A new claim changes
`Campaign.drawStyle`, so "attempt k" is a different style and an old table cannot be compared.
To baseline main when the branch changes only playtest Lua (the ROM and the Python stay the
branch's), swap main's Lua in place: `git stash -u`, `git show origin/main:<f> > <f>` for each
changed file, run, `git checkout -- tools/playtest` and `git clean -f tools/playtest` (a file
only main has would block the pop), `git stash pop`. Never a worktree. Time
base and branch back to back, or compare `costs.game_calls`, which load does not move. Read only
the suite's `tuning` records (`rec.suite.set`) while changing the bot: the held-out seeds stay
unseen until the verdict, or they stop being held out.
"""
import argparse
import collections
import concurrent.futures
import functools
import gzip
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_SH = os.path.join(HERE, 'run.sh')
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

BOTRUN, CAMPAIGN = 'BOTRUN', 'CAMPAIGN'


def is_bot(r):
    """Whether record `r` is a BOTRUN record, not a campaign's end (records_of)."""
    return r.get('kind') != 'campaign'


def bot_records(records):
    """The BOTRUN records of a runs file, in its order: the last is the newest."""
    return [r for r in records if is_bot(r)]


def parse_lines(text, prefix):
    """Every `<prefix> <json>` line of `text` (an emulator's stdout, or run.sh's echo of the
    log, where each line carries a `[f<frame>] ` tag), decoded."""
    pat = re.compile(r'^(?:\[f\d+\] )?%s (\{.*\})\s*$' % re.escape(prefix))
    out = []
    for line in text.splitlines():
        m = pat.match(line)
        if m:
            out.append(json.loads(m.group(1)))
    return out


def append_record(path, rec, prefix=None):
    """Append `rec` to `path` as ONE line, in one write on an O_APPEND descriptor: two
    workers' records never interleave, and a reader never sees half of one. With `prefix`, the
    line is `<prefix> <json>`, as the emulator printed it (parse_lines reads it back)."""
    head = prefix + ' ' if prefix else ''
    data = (head + json.dumps(rec, sort_keys=True) + '\n').encode('utf-8')
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        if os.write(fd, data) != len(data):
            raise OSError('montecarlo: a short write to %s' % path)
    finally:
        os.close(fd)


RUN_ROOT = '/tmp'     # where run.sh puts a tagged run's dir (its `out`)
KEEP_FAILED = 20      # failing runs' dirs kept at once, newest first (~15 MB each)
STALE_S = 24 * 3600   # an unmarked run dir idle this long is a dead process's, never a live run
FAILED_MARK = 'FAILED'


def run_dir(scenario, tag, root=None):
    """Where run.sh keeps a tagged run (its PT_RUN_TAG)."""
    return os.path.join(root or RUN_ROOT, 'playtest-%s@%s' % (scenario, tag))


def is_tagged_dir(path, root):
    """True for run.sh's `<root>/playtest-<scenario>@<tag>` dir, and nothing else: the only
    dirs the pool ever deletes (a launch may name any path)."""
    name = os.path.basename(path)
    return (os.path.dirname(os.path.abspath(path)) == os.path.abspath(root)
            and name.startswith('playtest-') and '@' in name and os.path.isdir(path))


def tagged_dirs(root):
    """Every tagged run dir under `root`."""
    try:
        names = os.listdir(root)
    except OSError:
        return []
    return [p for p in (os.path.join(root, n) for n in names) if is_tagged_dir(p, root)]


def last_touched(path):
    """The newest mtime anywhere in a run dir: a live run appends to its log, so a run that
    is still playing never looks idle, however long it has been going."""
    newest = os.path.getmtime(path)
    for top, dirs, files in os.walk(path):
        for n in dirs + files:
            try:
                newest = max(newest, os.path.getmtime(os.path.join(top, n)))
            except OSError:
                pass
    return newest


def prune_runs(root=None, keep=KEEP_FAILED, stale_s=STALE_S, now=None):
    """Bound the tagged run dirs under `root` (#574). A failing run's dir carries FAILED_MARK
    and is kept for its report, but only the `keep` newest; an unmarked dir is a run still
    playing (left alone) or one whose process died (deleted once idle `stale_s`). A passing
    run's dir is never here: its Pool deletes it the moment the run ends."""
    root = root or RUN_ROOT
    now = time.time() if now is None else now
    failed, gone = [], []
    for d in tagged_dirs(root):
        mark = os.path.join(d, FAILED_MARK)
        try:
            if os.path.exists(mark):
                failed.append((os.path.getmtime(mark), d))
            elif now - last_touched(d) > stale_s:
                gone.append(d)
        except OSError:
            continue   # another pool removed it between the listing and the look
    failed.sort(reverse=True)
    gone += [d for _, d in failed[keep:]]
    for d in gone:
        shutil.rmtree(d, ignore_errors=True)
    return sorted(gone)


PASSED_BOT = ('won', 'lost')          # a BOTRUN record's game results
# a campaign's ends that are its own answer: `bot_fault`/`infeasible` are verdicts (campaign.lua
# noClean), and kept as FAILED they would crowd real crashes out of KEEP_FAILED
PASSED_CAMPAIGN = ('done', 'played', 'bot_fault', 'infeasible')


def passing(recs):
    """A run that needs no dir to explain it: every BOTRUN record a game result in a clean
    environment, and the campaign (if any) ended on its own answer. Anything else -- a crash,
    a stall, an environment fault, a campaign that crashed or ran out of styles -- keeps its
    dir as evidence."""
    for r in recs:
        if not is_bot(r):
            if r.get('outcome') not in PASSED_CAMPAIGN:
                return False
        elif r.get('outcome') not in PASSED_BOT or r.get('env_status', 'clean') != 'clean':
            return False
    return bool(recs)


def settle_run_dir(where, passed, root=None, keep=KEEP_FAILED):
    """Once a run's records are in the runs file: delete a passing run's dir; mark a failing
    one's and prune the kept ones to `keep`. Cleanup never costs a run: an error here (a full
    disk) is said and dropped."""
    root = root or RUN_ROOT
    if not where or not is_tagged_dir(where, root):
        return
    try:
        if passed:
            shutil.rmtree(where, ignore_errors=True)
            return
        open(os.path.join(where, FAILED_MARK), 'w').close()
        prune_runs(root, keep)
    except OSError as err:
        print('montecarlo: could not settle %s: %s' % (where, err), file=sys.stderr)


def launch(task, tag, log_path):
    """Run one task through run.sh; return the emulator's stdout (its records) and run dir."""
    scenario = task.get('scenario', 'campaign')
    env = dict(os.environ, PT_RUN_TAG=tag, PT_SEED=str(task.get('seed', 1)))
    if 'campaign' in task:
        env['PT_CAMPAIGN'] = json.dumps(task['campaign'])
    if task.get('vanilla'):
        env['PT_VANILLA'] = '1'
    if task.get('mode'):
        env['PT_DIFFICULTY'] = task['mode']
    env['PT_INSTRUMENT'] = task.get('instrument') or instrument_id()
    if task.get('diag'):   # a diagnostic replay (`replay`): harness.lua prints DIAG lines only
        env['PT_DIAG'] = json.dumps(task['diag'])
    if task.get('pinned'):   # a snapshot's check (`suite`): one PINNED line, nothing played
        env['PT_PINNED'] = task['pinned']
    if task.get('bench'):   # an experiment's benched units (`pilot --bench-vanilla`)
        env['PT_BENCH'] = json.dumps(task['bench'])
    with open(log_path, 'w') as log:
        subprocess.run([RUN_SH, scenario], env=env, stdout=log, stderr=subprocess.STDOUT,
                       check=False)
    where = run_dir(scenario, tag)
    try:
        with open(os.path.join(where, 'mgba-stdout.log'), errors='replace') as fh:
            return fh.read(), where
    except FileNotFoundError:
        return '', where


def log_tail(path, n=30):
    """The last lines of a worker's log: what run.sh and the emulator said before it ended."""
    try:
        with open(path, errors='replace') as fh:
            return fh.read().splitlines()[-n:]
    except OSError:
        return []


def records_of(task, text, where, log_path):
    """A worker's records: its BOTRUN lines, and its campaign's last CAMPAIGN line (the one
    without a chapter: how the campaign ended, and why) as a record of kind `campaign`; each
    names its run dir. A worker that left neither says why it has none, from its log."""
    recs = parse_lines(text, BOTRUN)
    ends = [c for c in parse_lines(text, CAMPAIGN) if c.get('chapter') is None]
    for c in ends[-1:]:
        c['kind'] = 'campaign'
        recs.append(c)
    attempt = (task.get('campaign') or {}).get('attempt')
    bot = any(is_bot(r) for r in recs)
    for r in recs:
        r['run_dir'] = where
        if r.get('outcome') == 'crashed':
            r['log'], r['log_tail'] = log_path, log_tail(log_path)
        # the campaign crashed (load, arrive, save, cap) before its bot reported: the
        # environment did not hold. A no_style or done end is the campaign's own answer.
        if not bot and r.get('outcome') == 'crashed':
            r['env_status'] = unread()
    if recs:
        return recs
    return [{'outcome': 'crashed', 'attempt': attempt, 'seed': task.get('seed'), 'run_dir': where,
             'log': log_path, 'log_tail': log_tail(log_path), 'env_status': unread(),
             'why': 'the worker left no BOTRUN or CAMPAIGN record'}]


def unread():
    """The env_status of a worker that left no record (botrun.lua's, T009): a crash, and
    outcome-dependent, since nothing says whether play had begun."""
    return {'fault': 'crash', 'outcome_dependent': True}


def keep_trace(rec, out):
    """File a run's trace (botrun.lua's TRACE, left in its run dir) beside the runs file,
    gzipped, under a name no other run takes; the record then names it relative to the runs
    file's directory. A record whose trace is missing keeps no `trace`."""
    name = rec.get('trace')
    if not name or not rec.get('run_dir'):
        return
    src = os.path.join(rec['run_dir'], name)
    if not os.path.exists(src):
        rec.pop('trace')
        return
    rel = os.path.join('traces', str(rec.get('campaign') or 'run'), '%s-s%s-a%s-%s.jsonl.gz' % (
        rec.get('chapter'), rec.get('seed'), rec.get('attempt'), uuid.uuid4().hex[:8]))
    dest = os.path.join(os.path.dirname(os.path.abspath(out)), rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(src, 'rb') as fin, gzip.open(dest, 'wb') as fout:
        shutil.copyfileobj(fin, fout)
    rec['trace'] = rel
    # each anomaly's story command, naming the trace where it is kept (botrun.lua records
    # only the turn: the trace's final place is known here)
    for a in rec.get('anomalies') or []:
        a['narrate'] = narrate(dest, a.get('turn'))


def unique_tag(prefix):
    """A run tag no other launch shares: `prefix`, the pid, and a random part. A reused tag
    would let run.sh wipe an earlier run's kept failing dir (a `cell` makes a Pool per look),
    and two launches in one second, or a pid the OS has reused, must still differ."""
    return '%s-%d-%s' % (prefix, os.getpid(), uuid.uuid4().hex[:8])


class Pool:
    """`jobs` workers at once. `launch(task, tag, log_path) -> (stdout text, run dir)` runs one
    task (the real one drives run.sh; tests pass a fake). A task's `stamp` is written into
    each of its records, and its records go to its own `out` when it names one (the suite
    files each game's in that game's store). Each record carries `wall_s`, its worker's
    wall time."""

    def __init__(self, jobs=8, out='runs.jsonl', log_dir=None, launch=launch, run_root=None,
                 keep_failed=KEEP_FAILED):
        self.jobs, self.out, self.launch = jobs, out, launch
        self.log_dir = log_dir or os.path.join(os.path.dirname(os.path.abspath(out)), 'workers')
        self.run_root, self.keep_failed = run_root or RUN_ROOT, keep_failed

    def run(self, tasks):
        """Yield every record as its worker finishes, each appended to `out` first. A passing
        run's dir is deleted as it ends; a failing one's is kept, the newest `keep_failed`."""
        os.makedirs(self.log_dir, exist_ok=True)
        prune_runs(self.run_root, self.keep_failed)
        base = unique_tag('pool')   # one base a batch, each worker `<base>-<i>`

        def one(i, task):
            tag = '%s-%d' % (base, i)
            log_path = os.path.join(self.log_dir, tag + '.log')
            out = task.get('out') or self.out
            began = time.monotonic()
            try:
                text, where = self.launch(task, tag, log_path)
            except Exception as err:   # a worker that dies is a record, never a lost run
                attempt = (task.get('campaign') or {}).get('attempt')
                recs = [{'outcome': 'crashed', 'attempt': attempt, 'seed': task.get('seed'),
                         'log': log_path, 'env_status': unread(),
                         'run_dir': run_dir(task.get('scenario', 'campaign'), tag,
                                            self.run_root),
                         'why': '%s: %s' % (type(err).__name__, err)}]
            else:
                recs = records_of(task, text, where, log_path)
            wall = time.monotonic() - began
            for r in recs:
                r.update(task.get('stamp') or {})
                r['wall_s'] = wall
                keep_trace(r, out)
            # every record names the one run dir (records_of, and the crash record above); a
            # passing run's is deleted below, so its records stop naming it
            where, passed = recs[0].get('run_dir'), passing(recs)
            if passed:
                for r in recs:
                    r.pop('run_dir', None)
            return out, recs, where, passed

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.jobs) as ex:
            futures = [ex.submit(one, i, t) for i, t in enumerate(tasks)]
            for f in concurrent.futures.as_completed(futures):
                out, recs, where, passed = f.result()
                for rec in recs:
                    append_record(out, rec)
                # only once its records are on disk: a kill before this keeps the dir
                settle_run_dir(where, passed, self.run_root, self.keep_failed)
                for rec in recs:
                    yield rec


def attempt_tasks(env, n, seed=1, vanilla=False):
    """Attempts 1..n of the chapter at `env`'s `from` start, one task each."""
    if env.get('from') is None:
        raise ValueError('montecarlo: attempts need an env with `from` (a saved chapter start)')
    return [{'campaign': dict(env, attempt=k), 'seed': seed, 'vanilla': vanilla,
             'stamp': {'task_attempt': k}} for k in range(1, n + 1)]


def narrate(trace, turn):
    """The command that tells an anomaly's turns from its run's kept trace."""
    return 'python3 tools/playtest/montecarlo.py story %s --turn %s' % (trace, turn)


@functools.lru_cache(maxsize=None)
def botrun_names(path=os.path.join(HERE, 'botrun.lua')):
    """The death causes in precedence order, and each detail of "other" with its family, read
    from botrun.lua's M.CAUSES and M.DETAILS: the one list, never restated here."""
    with open(path) as fh:
        text = fh.read()
    causes = re.search(r'M\.CAUSES = \{([^}]*)\}', text)
    details = re.search(r'M\.DETAILS = \{(.*?)\n\}', text, re.S)
    return (tuple(re.findall(r'"(\w+)"', causes.group(1))),
            dict(re.findall(r'(\w+) = "(\w+)"', details.group(1))))


def hex_id(c):
    """A character id as the records hold it, when no name is at hand: the one fallback every
    sentence that names a unit uses."""
    return '0x%02X' % c if isinstance(c, int) else str(c)


def namer(names):
    """`who` for a sentence from name table `names` ({id: name}): a unit's name, or its id
    (hex_id) when the table has none, or an empty one."""
    return lambda c: names.get(c) or hex_id(c)


def plural(n, word, many=None):
    """'1 death', '2 deaths': `n` and `word`, plural unless n is 1 (`many` when the plural is
    not word + 's')."""
    return '%d %s' % (n, word if n == 1 else (many or word + 's'))


def death(d, who=hex_id):
    """One blue or green death, in words: who, when, to whom, and from a graded record (#510
    step 9, FR-005) its cause, the chance the committing plan gave it and its flags."""
    out = 'lost %s (%s, turn %s, to %s)' % (who(d['charId']), d.get('faction'), d.get('turn'),
                                           who(d['killer']) if d.get('killer') is not None
                                           else 'nobody seen')
    cause = d.get('cause')
    if cause is None:
        return out
    causes, details = botrun_names()
    if cause not in causes or (d.get('detail') is not None and d['detail'] not in details):
        raise ValueError('montecarlo: a death cause botrun.lua does not name: %s/%s'
                         % (cause, d.get('detail')))
    out += ' %s' % cause
    if d.get('detail'):
        out += ' (%s: %s)' % (details[d['detail']], d['detail'])
    if d.get('predicted') is not None:
        out += ' at %.1f%%' % (100 * d['predicted'])
    flags = [f for f in ('boss',) if (d.get('flags') or {}).get(f)]
    if d.get('escort'):
        flags.append('escort')
    return out + ''.join(', %s' % f for f in flags)


def theft(t, who=hex_id):
    """One theft of a record's `thefts` (ADR 0379), in words."""
    return '%s stole item 0x%02X from %s (turn %s)' % (who(t['thief']), t['item'], who(t['from']),
                                                       t.get('turn'))


def spoiled(r, who=hex_id):
    """What kept record `r` from a clean clear (#510 step 9 design, part A), in words: each unit
    lost, each owed recruit missed, each village or chest not taken, each theft ranked above the
    stat boosters (ADR 0379); '' when nothing did."""
    c = r.get('clear') or {}
    out = [death(d, who) for d in c.get('lost') or []]
    missing = c.get('recruits_missing')
    if missing == 'unchecked':
        out.append('recruits unchecked')
    elif r.get('missed_recruits') is not None:   # graded: each with its reason (FR-006)
        out += ['missed %s (%s)' % (who(m['charId']), m['reason']) for m in r['missed_recruits']]
    else:
        out += ['missed %s' % who(m) for m in missing or []]
    graded = r.get('missed_rewards')
    for t in graded if graded is not None else c.get('rewards_missing') or []:
        # a graded one's reason (botrun.lua's REWARD_REASONS), else the explore log's word
        out.append('%s %s,%s %s%s' % ('village' if t['kind'] == 'visit' else 'chest', t['x'],
                                       t['y'], t.get('reason') or t['why'],
                                       ' by %s' % who(t['closed_by'])
                                       if t.get('closed_by') is not None else ''))
    out += [theft(t, who) for t in c.get('stolen') or []]
    return '; '.join(out)


def attempt_line(r, said):
    """The line `attempts` prints for record `r`, or None. `said` = the attempts already
    printed. A worker's CAMPAIGN end is printed only when no BOTRUN of its attempt was: a run
    that crashed before its bot reported (vanilla Ch3, 2026-10-29: a symbol table another run
    rewrote) would otherwise vanish from the listing."""
    if not is_bot(r):
        k = r.get('task_attempt')
        if k is None or k in said or (r.get('outcome') != 'crashed' and r.get('env_status') is None):
            return None
        said.add(k)
        if r.get('outcome') == 'crashed':
            return 'attempt %s: crashed before the bot reported (%s)' % (k, r.get('why'))
        return 'attempt %s: the bot left no record; the campaign ended %s (%s)' % (
            k, r.get('outcome'), r.get('why'))
    said.add(r.get('attempt'))
    cost = (r.get('costs') or {}).get('cpu_s')
    why = spoiled(r) if r.get('outcome') == 'won' and r.get('clean') is not True else ''
    # a theft at or below the boosters spoils nothing and is noted (ADR 0379)
    noted = '; '.join(theft(t) for t in r.get('thefts') or [] if not t.get('spoils'))
    # a run not won names its graded deaths too (a won one's are in `why`), labelled apart
    # from a crash's own reason
    graded = '; '.join(death(d) for d in r.get('deaths') or [] if d.get('cause'))
    if r.get('outcome') != 'won' and graded:
        why = 'deaths: ' + graded
    stalls = ', '.join('%s turn %s' % (e['kind'], e['turn']) for e in r.get('stall_events') or [])
    anomalies = ''.join('\n    anomaly: %s turn %s%s' % (
        a['kind'], a.get('turn'), ' -> %s' % a['narrate'] if a.get('narrate') else '')
        for a in r.get('anomalies') or [])
    return 'attempt %s: %s%s, turn %s, %d deaths%s%s%s%s%s%s' % (
        r.get('attempt'), r.get('outcome'), ' clean' if r.get('clean') is True else '',
        r.get('turns', '-'), len(r.get('deaths') or []),
        '' if r.get('frames') is None else ', %d frames' % r['frames'],
        '' if cost is None else ', %.1f CPU s' % cost,
        ' (%s)' % r.get('why') if r.get('outcome') == 'crashed' else '',
        ' (%s)' % why if why else '',
        ' [noted: %s]' % noted if noted else '',
        ' [stalls: %s]' % stalls if stalls else '') + anomalies


def first_clean(records):
    """The lowest attempt that cleared clean (the record's `clean`: all four parts), or None."""
    clean = [r['attempt'] for r in records if r.get('clean') is True and r.get('attempt')]
    return min(clean) if clean else None


# ---- the verdict (#510 step 9 PR-H; ADR 0385, spec FR-023 to FR-028) ----
# One endpoint, a protected unit's death anywhere in attempt 1, compared at planned looks with
# exact one-sided Clopper-Pearson bounds. Each bound takes an equal share of a familywise 0.05:
# four bounds a look, three looks, the frozen number of cells. That split is what lets every
# look be read without an early-stop bar, and the exact bounds need no rule for zero
# discordance: 0 of 50 is simply too wide to call equivalent, 0 of 200 is not.

LOOKS = (50, 100, 200)      # pairs (FR-026)
ALPHA = 0.05                # familywise, over every bound of every look of every cell
MARGIN = 0.10               # the equivalence margin, +-10 points (FR-028)
DECISIVE = ('EQUIVALENT', 'HARDER', 'EASIER')


def _binom_le(k, n, p):
    """P(X <= k) for X ~ Binomial(n, p), summed in logs so n = 200 never overflows."""
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 1.0 if k >= n else 0.0
    lp, lq, ln = math.log(p), math.log1p(-p), math.lgamma(n + 1)
    return min(1.0, sum(math.exp(ln - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                                 + i * lp + (n - i) * lq) for i in range(k + 1)))


def clopper_pearson(k, n, level):
    """The exact one-sided Clopper-Pearson bounds of k events in n, each at `level`: (lo, hi)
    with P(X >= k | lo) = level and P(X <= k | hi) = level; lo is 0 at k = 0 and hi is 1 at
    k = n. Found by bisection on the binomial tail (this repo has no scipy), each bound on
    the side that keeps its level at or under `level`."""
    if n <= 0 or not 0 <= k <= n:
        raise ValueError('montecarlo: %r events in %r is no proportion' % (k, n))

    def upper(j):
        if j >= n:
            return 1.0
        lo, hi = 0.0, 1.0
        for _ in range(60):   # P(X <= j | p) falls as p rises
            mid = (lo + hi) / 2
            if _binom_le(j, n, mid) > level:
                lo = mid
            else:
                hi = mid
        return hi
    return (1.0 - upper(n - k) if k > 0 else 0.0), upper(k)


def bound_level(cells, alpha=ALPHA):
    """Each one-sided bound's level (FR-026): alpha / (4 x 3 x N), N the frozen cell count."""
    if isinstance(cells, bool) or not isinstance(cells, int) or cells < 1:
        raise ValueError('montecarlo: the frozen cell count must be a positive int, not %r'
                         % (cells,))
    return alpha / (4 * len(LOOKS) * cells)


def table_of(pairs):
    """The paired 2x2 table (a, b, c, d) of resolved pairs (ours_died, twin_died): a both
    lost someone, b only Manchego Stars did, c only the twin did, d neither did."""
    a = sum(1 for x, y in pairs if x and y)
    b = sum(1 for x, y in pairs if x and not y)
    c = sum(1 for x, y in pairs if y and not x)
    return a, b, c, len(pairs) - a - b - c


def confirmatory_interval(table, cells, analysis, alpha=ALPHA):
    """(lo, hi) for ours' death rate minus the twin's, from table (a, b, c, d) (FR-026).
    Paired analysis bounds the two discordant proportions, b/n and c/n; marginal analysis
    bounds the two arms' rates, (a + b)/n and (a + c)/n. Both differences are the same point;
    the paired interval is the narrower one when the arms covary, which is what the pilot
    decides."""
    a, b, c, d = table
    n = a + b + c + d
    if analysis == 'paired':
        x, y = b, c
    elif analysis == 'marginal':
        x, y = a + b, a + c
    else:
        raise ValueError('montecarlo: analysis %r is neither paired nor marginal' % (analysis,))
    level = bound_level(cells, alpha)
    lx, ux = clopper_pearson(x, n, level)
    ly, uy = clopper_pearson(y, n, level)
    return lx - uy, ux - ly


def bound_unresolved(pairs):
    """The two worst-case tables (low, high) of `pairs` (ours_died, twin_died), None where an
    attempt has no game result even after its same-seed retry (FR-027): `low` reads each
    unresolved Manchego Stars run as everyone surviving and each unresolved twin as a death, `high`
    the reverse. The low table's lower bound and the high table's upper bound hold whatever the
    unresolved attempts would have done, so those attempts stay in the denominators."""
    def fill(ours, twin):
        return table_of([(ours if x is None else bool(x), twin if y is None else bool(y))
                         for x, y in pairs])
    return fill(False, True), fill(True, False)


def label(lo, hi, margin=MARGIN):
    """FR-028, in order: EQUIVALENT inside the margin, else HARDER or EASIER when the interval
    excludes zero (ours' deaths minus the twin's: above zero is harder), else INCONCLUSIVE."""
    if -margin <= lo and hi <= margin:
        return 'EQUIVALENT'
    if lo > 0:
        return 'HARDER'
    if hi < 0:
        return 'EASIER'
    return 'INCONCLUSIVE'


def paired_verdict(pairs, cells, analysis, looks=LOOKS, look=None):
    """Where a cell stands, from its pairs (ours_died, twin_died) in seed order: each True when
    a protected unit died anywhere in that arm's attempt 1, None when the attempt has no game
    result after its same-seed retry (ADR 0385). `cells` is the frozen cell count N and
    `analysis` the pilot's choice, 'paired' or 'marginal'.

    It is judged at the largest planned look its pairs reach, on that many pairs only: a pair
    past the look waits for the next one. `look`, one of `looks`, judges every pair given at
    that look instead: a campaign cell's look counts replicates, and the pairs it compares
    are only those both arms reached (run_cell). The interval is confirmatory_interval's, the
    unresolved pairs bounded adversarially (bound_unresolved), labelled at every look
    (`label`). A decisive label settles the cell; the last look settles it whatever it says.
    A look whose bounded interval decides nothing, with unresolved pairs in it, is WITHHELD
    rather than INCONCLUSIVE: resolving them could have decided it."""
    if look is None:
        reached = [k for k in looks if k <= len(pairs)]
        if not reached:
            return {'n': len(pairs), 'look': None, 'settled': False, 'verdict': None,
                    'reason': 'no look yet: the first is at %d pairs' % looks[0]}
        look = reached[-1]
        used = list(pairs[:look])
    elif look not in looks:
        raise ValueError('montecarlo: %r is not a planned look (%s)' % (look, looks))
    else:
        used = list(pairs)
    if not used:
        return {'n': 0, 'look': look, 'settled': False, 'verdict': 'WITHHELD',
                'reason': 'withheld at %d replicates: no replicate reached the chapter in '
                'both arms' % look}
    low, high = bound_unresolved(used)
    lo = confirmatory_interval(low, cells, analysis)[0]
    hi = confirmatory_interval(high, cells, analysis)[1]
    unresolved = sum(1 for x, y in used if x is None or y is None)
    verdict = label(lo, hi)
    if verdict == 'INCONCLUSIVE' and unresolved:
        verdict = 'WITHHELD'
    final = look == looks[-1]
    resolved = [(x, y) for x, y in used if x is not None and y is not None]
    a, b, c, d = table_of(resolved)
    m = len(resolved)
    out = {'n': len(pairs), 'look': look, 'verdict': verdict, 'lo': lo, 'hi': hi,
           'settled': final or verdict in DECISIVE, 'analysis': analysis, 'cells': cells,
           'table': (a, b, c, d), 'discordant': b + c, 'unresolved': unresolved,
           'diff': (b - c) / m if m else None,
           'ours': (a + b) / m if m else None, 'vanilla': (a + c) / m if m else None}
    held = ' (%d unresolved, bounded both ways)' % unresolved if unresolved else ''
    out['reason'] = '%s at %d %s: %+.1f to %+.1f points%s' % (
        verdict, look, 'pairs' if len(used) == look else 'replicates, %d pairs' % len(used),
        100 * lo, 100 * hi, held)
    if not out['settled']:
        out['reason'] += '; the next look is at %d' % looks[looks.index(look) + 1]
    return out


def pilot_summary(pairs, cells, cpu_s=0.0, reach=None, looks=LOOKS):
    """The one-cell pilot's report (FR-025, AS 1), from its pairs as paired_verdict reads them:
    the 2x2 table, the discordant counts each way, the difference, the correlation, the
    analysis it chooses (paired when the arms' outcomes covary positively, marginal
    otherwise), the reachability and the CPU. `half_width` is the interval the last look
    would give at this discordance (paired) or these death rates (marginal) with no
    difference, for the frozen N; `reachable` says whether it fits inside the margin. Pilot
    pairs are never confirmatory: this returns no verdict."""
    resolved = [(x, y) for x, y in pairs if x is not None and y is not None]
    a, b, c, d = table_of(resolved)
    n = len(resolved)
    if not n:
        raise ValueError('montecarlo: a pilot with no resolved pair has nothing to report')
    cov = (a * d - b * c) / n ** 2
    den = math.sqrt((a + b) * (c + d) * (a + c) * (b + d))
    analysis = 'paired' if cov > 0 else 'marginal'
    last = looks[-1]
    if analysis == 'paired':   # the measured discordance, split evenly: no difference
        m = round(last * (b + c) / n)
        table = (0, m // 2, m - m // 2, last - m)
    else:                      # both arms at the pooled death rate
        k = round(last * (2 * a + b + c) / (2 * n))
        table = (k, 0, 0, last - k)
    lo, hi = confirmatory_interval(table, cells, analysis)
    half = max(hi, -lo)
    return {'n': n, 'unresolved': len(pairs) - n, 'table': (a, b, c, d),
            'ours_only': b, 'twin_only': c, 'discordance': (b + c) / n,
            'diff': (b - c) / n, 'ours': (a + b) / n, 'vanilla': (a + c) / n,
            'cov': cov, 'corr': (a * d - b * c) / den if den else None, 'analysis': analysis,
            'half_width': half, 'reachable': label(-half, half) == 'EQUIVALENT',
            'cells': cells, 'reach': reach or {}, 'cpu_s': cpu_s}


# ---- one cell, played to its verdict (PR-H, T095: chapter cells and campaign cells) ----

UNUSABLE = ('crashed', 'no_style')   # no game result


def simdir(vanilla):
    """This game's store for the ROM built now: run.sh owns the path (`--simdir`)."""
    env = dict(os.environ, PT_VANILLA='1' if vanilla else '0')
    return subprocess.run([RUN_SH, '--simdir'], env=env, check=True, capture_output=True,
                          text=True).stdout.strip()


def bot_hash(root=HERE):
    """The bot code a run ran, hashed: the driver files the matrix keys on
    (matrix.driver_source: no generated symbol table, no test) and harness.lua. A change to
    any of them makes kept runs another cell's; rebuilding a ROM or editing a test does not."""
    import matrix
    files = matrix.driver_source(root)
    harness = os.path.join(root, 'harness.lua')
    if os.path.isfile(harness):
        files['harness.lua'] = matrix._read(harness)
    h = hashlib.sha1()
    for name in sorted(files):
        h.update(name.encode() + b'\0' + files[name].encode())
    return h.hexdigest()[:12]


def cell_stamp(env, mode, bot):
    """What makes two runs the same sweep's: the whole campaign env (claims, caps, shops, where
    it ends, the lead or route), the mode and the bot code."""
    key = json.dumps({'env': env, 'mode': mode}, sort_keys=True).encode()
    return {'cell': {'env': hashlib.sha1(key).hexdigest()[:12], 'bot': bot}}


def campaign_id(prefix, seed):
    """A New Game campaign's id: its sweep's prefix and its seed (its states folder's name)."""
    return '%s-s%d' % (prefix, seed)


def campaign_tasks(env, seeds, mode, stamp, vanilla=False, prefix=None):
    """Campaign s for each seed s: from New Game, the game seeded once with s and never again
    (a player's own save), every chapter to the env's last retried until it clears clean
    (campaign.lua). Its id is `<prefix>-s<seed>`, the prefix the sweep's (its stamp's env
    hash) unless given, so its chapter starts are its own."""
    if env.get('from') is not None or env.get('attempt') is not None:
        raise ValueError('montecarlo: a cell plays whole campaigns, each keeping its seed: '
                         'an env with `from` or `attempt` would cut one short')
    prefix = prefix or stamp['cell']['env'][:8]
    return [{'campaign': dict(env, id=campaign_id(prefix, s)), 'seed': s,
             'mode': mode, 'vanilla': vanilla, 'stamp': stamp} for s in seeds]


def kept(paths, keep, key):
    """{key(rec): [record]} of the runs kept in `paths` (runs files) that `keep(rec)` takes, in
    file order."""
    out = {}
    for path in paths:
        if not os.path.exists(path):
            continue
        with open(path) as fh:
            for line in fh:
                rec = json.loads(line)
                if keep(rec):
                    out.setdefault(key(rec), []).append(rec)
    return out


def kept_runs(path, stamp):
    """{seed: [record]} of the runs in `path` with this stamp, in file order."""
    return kept([path], lambda r: all(r.get(k) == v for k, v in stamp.items())
                and r.get('seed') is not None, lambda r: r['seed'])


def start_of(suite, start_id):
    """The suite's pinned start `start_id`; ValueError when it has none."""
    st = next((s for s in suite['starts'] if s['start_id'] == start_id), None)
    if st is None:
        raise ValueError('montecarlo: the suite has no start %s' % start_id)
    return st


def protected_deaths(rec):
    """The deaths in a played record that the bot answers for (ADR 0384, 0385): a blue unit's,
    or a green's whose death ends the game (its `escort`, botrun.grade's). A green whose
    death does not end the game is reported elsewhere, never counted here. A record from
    before deaths were graded (v1) carries no `escort`: its green deaths are not counted."""
    return [d for d in rec.get('deaths') or [] if d.get('escort', d.get('faction') != 'green')]


def chapter_result(recs, chapter, pinned=False):
    """What one replicate's records say of its FIRST attempt at `chapter`, as a dict whose
    `status` is:
    - 'played': `died` (the endpoint: a protected unit died anywhere in it, ADR 0385) and
      `clean` (reported, never the endpoint), from the first attempt-1 record there with a
      game result: a same-seed retry of a crashed attempt is still attempt 1;
    - 'unresolved': attempt 1 was reached and has no game result;
    - 'unreached': the campaign ended with a game result before the chapter (a campaign cell
      compares only the replicates both arms reach);
    - 'reach_unresolved': it crashed before the chapter, so whether it would have reached it
      is unknown (FR-027: that withholds the comparison);
    - 'unplayed': no record of it.
    `pinned` is a chapter cell's replicate: it starts at the chapter, so every play with no
    game result is attempt 1 unresolved (a worker that died before writing a chapter
    included), never 'reach_unresolved'. Every status but 'played' carries the run's own
    words for why (`why`), and `tries` counts the plays that stopped with no game result
    where this status says they stopped: at the chapter for 'unresolved', before it for
    'reach_unresolved'."""
    bots = bot_records(recs)
    here = [r for r in bots if (r.get('chapter') == chapter and r.get('attempt') == 1)
            or (pinned and r.get('chapter') is None)]
    for r in here:
        if r.get('outcome') not in UNUSABLE:
            return {'status': 'played', 'died': bool(protected_deaths(r)),
                    'clean': r.get('clean') is True, 'rec': r,
                    'tries': sum(1 for x in here if x.get('outcome') in UNUSABLE)}
    if here:
        return dict(here[-1], status='unresolved', tries=len(here), rec=here[-1])
    # an earlier attempt's crash, in its own words, before the campaign's summary of it
    crashed = [r for r in bots if r.get('outcome') in UNUSABLE]
    summaries = [r for r in recs if not is_bot(r)]
    ends = summaries or crashed
    if not ends:
        return {'status': 'unplayed', 'why': 'no record of this replicate', 'tries': 0}
    last = ends[-1]
    if last.get('outcome') in UNUSABLE or not summaries:
        status, said = 'reach_unresolved', crashed[-1] if crashed else last
        tries = sum(1 for r in summaries if r.get('outcome') in UNUSABLE) if summaries \
            else len(crashed)
    else:
        status, said, tries = 'unreached', last, 0
    where = ' (chapter %s, attempt %s)' % (said['chapter'], said.get('attempt')) \
        if is_bot(said) and said.get('chapter') is not None else ''
    return dict(said, status=status, tries=tries, rec=said,
                why='the campaign never played chapter %s: %s%s: %s' % (
                    chapter, said.get('outcome'), where, said.get('why')))


RETRIES = 1   # FR-027: an attempt with no game result is played once more on its own seed


def again(recs, chapter, pinned=False):
    """Whether a replicate is (re)played: never played, or with no game result where it
    stopped and at most RETRIES plays that stopped there behind it: the first play earns
    one retry, and once both are behind it, it is not played again."""
    if not recs:
        return True
    r = chapter_result(recs, chapter, pinned)
    return r['status'] in ('unresolved', 'reach_unresolved') and r['tries'] <= RETRIES


def pair_of(got):
    """A seed's pair from its {arm: chapter_result}: (ours_died, twin_died), None in an arm
    whose attempt is unresolved."""
    return tuple(got[n]['died'] if got[n]['status'] == 'played' else None
                 for n in ('ours', 'vanilla'))


def cell_pairs(sides, play, seeds, have=None):
    """Play `seeds` on both arms of a cell and pair their attempt-1 endpoints (seed order).
    `sides` = {'ours': side, 'vanilla': side}, each side a dict with `tasks(seeds) -> tasks`,
    `kept() -> {seed: [record]}` (its runs already played) and `chapter`; `play(side, tasks)
    -> records`. A seed whose attempt has no game result is played again on the same seed
    (RETRIES), then stays unresolved. `have`, {name: {seed: [record]}}, carries kept and
    played records between looks.

    Returns {'pairs', 'reach', 'problems', 'played', 'withheld', 'have', 'cpu_s',
    'results'}: a pair is (ours_died, twin_died), None where unresolved; a seed one arm did
    not reach is left out and counted in `reach`; `withheld` is set when an arm's
    reachability is unresolved; `results` is {seed: {arm: chapter_result}}. A side with
    `pinned` set is a chapter cell's (chapter_result's `pinned`)."""
    names = ('ours', 'vanilla')
    have = have if have is not None else {n: sides[n]['kept']() for n in names}
    played = {n: 0 for n in names}
    for n in names:
        side = sides[n]
        for _ in range(1 + RETRIES):
            todo = [s for s in seeds if again(have[n].get(s), side['chapter'],
                                              side.get('pinned', False))]
            if not todo:
                break
            for rec in play(side, side['tasks'](todo)):
                if rec.get('seed') is None:
                    raise RuntimeError('montecarlo: a run record without its seed: %r' % rec)
                have[n].setdefault(rec['seed'], []).append(rec)
            played[n] += len(todo)
    pairs, paired, problems, cpu, results = [], [], [], 0.0, {}
    reach = {n: {'reached': 0, 'unreached': 0, 'unresolved': 0} for n in names}
    for s in seeds:
        got = results[s] = {n: chapter_result(have[n].get(s, []), sides[n]['chapter'],
                                              sides[n].get('pinned', False)) for n in names}
        for n in names:
            r = got[n]
            st = r['status']
            reach[n]['reached' if st in ('played', 'unresolved') else
                     'unreached' if st == 'unreached' else 'unresolved'] += 1
            if st == 'played':
                cpu += (r['rec'].get('costs') or {}).get('cpu_s') or 0.0
            else:
                problems.append({'side': n, 'seed': s, 'status': st, 'why': r.get('why'),
                                 'outcome': r.get('outcome'), 'run_dir': r.get('run_dir'),
                                 'log': r.get('log'), 'log_tail': r.get('log_tail')})
        if any(got[n]['status'] == 'unreached' for n in names):
            continue
        pairs.append(pair_of(got))
        paired.append(s)
    withheld = any(reach[n]['unresolved'] for n in names)
    return {'pairs': pairs, 'reach': reach, 'problems': problems, 'played': played,
            'withheld': withheld, 'have': have, 'cpu_s': cpu, 'results': results,
            'paired': paired}


def run_cell(sides, play, cells, analysis, seeds=None, looks=LOOKS):
    """Play a cell to its verdict (ADR 0385): the confirmatory seeds (`seeds`, 1..the last
    look by default) look by look, cell_pairs' pairs judged by paired_verdict at each look,
    then by validity (FR-029: NOT READABLE or an outcome-dependent fault settles it),
    stopping at the first settled one. An arm's unresolved reachability (a campaign that
    crashed before the chapter, after its retry) withholds the comparison, and the cell
    stops there, each such run named with what it said."""
    seeds = list(seeds or range(1, looks[-1] + 1))
    if len(seeds) < looks[-1]:
        raise ValueError('montecarlo: %d confirmatory seeds, and the last look needs %d'
                         % (len(seeds), looks[-1]))
    have, played = None, {'ours': 0, 'vanilla': 0}
    for look in looks:
        got = cell_pairs(sides, play, seeds[:look], have)
        have = got['have']
        for n in played:
            played[n] += got['played'][n]
        if got['withheld']:
            verdict = {'n': len(got['pairs']), 'look': look, 'settled': False,
                       'verdict': 'WITHHELD',
                       'reason': 'withheld at %d replicates: an arm crashed before the chapter, '
                       'so whether it reaches it is unknown' % look}
            verdict = judged(verdict, validity(cell_results(got['results'], seeds[:look])))
            break
        verdict = paired_verdict(got['pairs'], cells, analysis, looks, look=look)
        # FR-029: both arms' first attempts at this look pass every invariant, or the cell is
        # NOT READABLE and stops: more pairs from an instrument that failed one read nothing
        verdict = judged(verdict, validity(cell_results(got['results'], seeds[:look])))
        if verdict['settled']:
            break
    return dict(verdict, played=played, reach=got['reach'], problems=got['problems'],
                cpu_s=got['cpu_s'], paired=got['paired'], results=got['results'],
                seeds=seeds[:look])


def campaign_side(env, chapter, mode, store, stamp, vanilla):
    """One arm of a campaign cell: whole campaigns from New Game (campaign_tasks), kept in
    `store` under `stamp`, compared at `chapter`."""
    return {'chapter': chapter, 'store': store, 'vanilla': vanilla,
            'tasks': lambda seeds: campaign_tasks(env, seeds, mode, stamp, vanilla),
            'kept': lambda: kept_runs(store, stamp)}


def bench_instrument(instrument, bench):
    """The instrument an experiment with `bench` (charIds) benched plays under: its own, so
    its runs are never kept, read or judged as the instrument's."""
    return instrument + ''.join('+bench%02x' % c for c in bench) if bench else instrument


def chapter_side(suite, envs, instrument, starts, kind, store, rom_hash, bench=None):
    """One arm of a chapter cell: attempt 1 under each seed of seed set `kind`, seed s on
    start `starts[(s - the set's first seed) % len(starts)]` (chapter_tasks), so a cell's
    pairs are spread over its starts the same way whichever seeds a look plays (T100e). Its
    records go to `store` (the game's runs file); a kept run counts when this instrument
    played it on the ROM built now (`rom_hash`) from the start its seed is dealt. `bench`
    (charIds, an experiment's): each only waits where it stands, under bench_instrument's."""
    game = starts[0]['game']
    instrument = bench_instrument(instrument, bench)
    mine = suite_run_of(instrument, {game: rom_hash})
    first = suite['seed_sets'][kind][0]

    def dealt(seed):
        return starts[(seed - first) % len(starts)]

    def tasks(seeds):
        out = []
        for st in starts:
            here = [seed for seed in seeds if dealt(seed) is st]
            if here:
                out += chapter_tasks(suite, envs, instrument, {game: store}, st, kind, here)
        for t in out:
            if bench:
                t['bench'] = list(bench)
        return out
    return {'chapter': starts[0]['chapter'], 'store': store, 'vanilla': game == 'vanilla',
            'starts': starts, 'pinned': True, 'dealt': dealt,
            'tasks': tasks,
            'kept': lambda: kept([store], lambda r: mine(r)
                                 and r['suite'].get('set') == kind
                                 and r.get('seed') is not None
                                 and r['suite'].get('start_id') == dealt(r['seed'])['start_id'],
                                 lambda r: r['seed'])}


def pool_play(jobs):
    """The real `play`: a Pool appending to the side's store."""
    def play(side, tasks):
        os.makedirs(os.path.dirname(side['store']), exist_ok=True)
        return list(Pool(jobs=jobs, out=side['store']).run(tasks))
    return play


def problem_lines(problems):
    """Each run a cell or pilot could not use, with what it said and the end of its log."""
    out = []
    for p in problems:
        out.append('  %s seed %s, %s: %s (%s)' % (
            p['side'], p['seed'], p['status'], p['why'],
            p.get('run_dir') or 'its run passed: no run dir kept'))
        out += ['      ' + line for line in (p.get('log_tail') or [])[-5:]]
    return out


def frozen_cells(args, suite):
    """The cell count N a run is judged on: `--cells` when given, else the manifest's,
    checked before anything plays (bound_level raises on a bad one)."""
    cells = suite['cells'] if args.cells is None else args.cells
    bound_level(cells)
    return cells


def games_line(sides, seeds):
    """How many games a chapter cell's pairs came from, arm by arm (T100e): the starts
    `seeds` (the seeds that made a pair, cell_pairs' `paired`) were dealt, so pairs that
    reach only some of the K say so. Each
    arm also says how many of its pinned campaigns reached the chapter at all: a start is a
    campaign that cleared every chapter before it clean, so an arm whose campaigns fell short
    more often plays the stronger parties (ADR 0385, T100e)."""
    def arm(n):
        side = sides[n]
        reached, pinned = side['reached']
        return '%d %s games (%d of %d pinned campaigns reached the chapter)' % (
            len({side['dealt'](s)['start_id'] for s in seeds}), GAME_NAMES[n], reached, pinned)
    return 'over %s and %s' % (arm('ours'), arm('vanilla'))


def chapter_sides(suite, simdirs, envs, inst, starts, kind, bench=None):
    """{arm: chapter_side} for `starts` ({arm: [cell start]}, cell_setup's) on seed set
    `kind`, each arm in its own game's store, `bench` ({arm: charIds}) benching an arm's
    units. Each side carries `reached`: (pinned campaigns that reached its chapter, pinned)."""
    sides = {}
    for arm in ('ours', 'vanilla'):
        sides[arm] = chapter_side(suite, envs, inst, starts[arm], kind,
                                  os.path.join(simdirs[arm], 'runs.jsonl'),
                                  os.path.basename(simdirs[arm]), (bench or {}).get(arm))
        pins = cell_pins(simdirs[arm])
        sides[arm]['reached'] = (sum(1 for c in pins if str(starts[arm][0]['chapter'])
                                     in c['chapters']), len(pins))
    return sides


def cell_main(args):
    """`cell`: one cell to its verdict, a chapter cell over K pinned starts an arm
    (cell_setup) or a campaign cell from two campaign envs, judged with the pilot's analysis
    and the frozen N."""
    chapter_cell = args.chapter is not None
    if chapter_cell:
        setup = cell_setup(args.chapter, args.starts)
        if isinstance(setup, str):
            print(setup)
            return 1
        suite, simdirs, envs, starts = setup
        try:
            cells = frozen_cells(args, suite)
            sides = chapter_sides(suite, simdirs, envs(), instrument_id(), starts,
                                  'confirmatory')
        except ValueError as err:
            print('refused: %s' % err)
            return 1
        lo, hi = suite['seed_sets']['confirmatory']
        seeds = range(lo, hi + 1)
        number, twin = args.chapter, starts['vanilla'][0]['chapter']
    else:
        try:
            cells = frozen_cells(args, load_suite())
        except ValueError as err:
            print('refused: %s' % err)
            return 1
        import campaign_env
        # the cell's sentence names our chapter by its number; an index no hosted chapter
        # stands at has none, and a sentence must never print an index as a chapter
        number = next((k for k, (host, _) in campaign_env.cell_chapters().items()
                       if host == args.ours_chapter), None)
        if number is None:
            print('refused: --ours-chapter %d is no written chapter\'s index (%s)' % (
                args.ours_chapter, ', '.join('ch%02d at %d' % (k, h) for k, (h, _)
                                             in sorted(campaign_env.cell_chapters().items()))))
            return 1
        twin = args.vanilla_chapter
        bot, sides, seeds = bot_hash(), {}, None
        for name, path, chapter in (('ours', args.ours, args.ours_chapter),
                                    ('vanilla', args.vanilla, args.vanilla_chapter)):
            with open(path) as fh:
                env = json.load(fh)
            vanilla = name == 'vanilla'
            sides[name] = campaign_side(env, chapter, args.mode,
                                        os.path.join(simdir(vanilla), 'runs.jsonl'),
                                        cell_stamp(env, args.mode, bot), vanilla)
    v = run_cell(sides, pool_play(args.jobs), cells, args.analysis, seeds)
    stores = {n: sides[n]['store'] for n in ('ours', 'vanilla')}
    print(v['reason'] + (' (%d pairs %s)' % (v['n'], games_line(sides, v['paired']))
                         if chapter_cell else ''))
    for line in problem_lines(v['problems']):
        print(line)
    if v.get('ours') is not None:   # some pair resolved in both arms
        a, b, c, d = v['table']
        print('a protected unit died: Manchego Stars %.0f%%, vanilla %.0f%%; only Manchego Stars '
              '%d, only the '
              'twin %d, both %d, neither %d (%s analysis, N = %d)' % (
                  100 * v['ours'], 100 * v['vanilla'], b, c, a, d, v['analysis'], cells))
    for n in ('ours', 'vanilla'):
        print('%s: %d replicates reached the chapter, %d did not, %d unknown' % (
            GAME_NAMES[n], v['reach'][n]['reached'], v['reach'][n]['unreached'],
            v['reach'][n]['unresolved']))
    print('played now: Manchego Stars %(ours)d, vanilla %(vanilla)d' % v['played'])
    print('\n'.join(validity_lines(v['validity'])))
    append_record(CELLS_FILE, cell_record(
        'chapter' if chapter_cell else 'campaign', number, twin, v, v['results'], v['paired'],
        stores, instrument_id(), games_line(sides, v['paired']) if chapter_cell else None))
    print('cell record: %s (`montecarlo.py report` reads it)' % CELLS_FILE)
    return 0


def pilot_lines(s, chapter, games):
    """pilot_summary's report in sentences (FR-025, AS 1); `games` says over how many games
    each arm's pairs were played (games_line)."""
    a, b, c, d = s['table']
    out = ['pilot: Manchego Stars ch%02d vs its twin, %d pairs %s%s' % (
               chapter, s['n'], games,
               ' (%d unresolved, left out)' % s['unresolved'] if s['unresolved'] else ''),
           '  a protected unit died: Manchego Stars %d of %d (%.0f%%), the twin %d of %d '
           '(%.0f%%)' % (
               a + b, s['n'], 100 * s['ours'], a + c, s['n'], 100 * s['vanilla']),
           '  both %d, only Manchego Stars %d, only the twin %d, neither %d: %d discordant '
           '(%.0f%%)' % (
               a, b, c, d, b + c, 100 * s['discordance']),
           '  difference %+.1f points; correlation %s; covariance %+.4f, so %s analysis' % (
               100 * s['diff'], '%.2f' % s['corr'] if s['corr'] is not None else 'undefined',
               s['cov'], s['analysis']),
           '  at 200 pairs and N = %d, no difference would read +-%.1f points: the +-%d margin '
           '%s' % (s['cells'], 100 * s['half_width'], round(100 * MARGIN),
                   'can be reached' if s['reachable'] else 'cannot be reached')]
    for n, r in sorted(s['reach'].items()):
        out.append('  %s: %d replicates reached the chapter, %d did not, %d unknown' % (
            GAME_NAMES.get(n, n), r['reached'], r['unreached'], r['unresolved']))
    out.append('  %.0f CPU s in all (%.2f CPU-hours)' % (s['cpu_s'], s['cpu_s'] / 3600))
    return out


def pilot_main(args):
    """`pilot`: the one-cell pilot (FR-025): each arm's cell starts on the 50 pilot seeds,
    estimated first and refused over SC-007's 8 wall-hours, then pilot_summary's report and
    each discordant pair's two traces, for `story`."""
    setup = cell_setup(args.chapter, args.starts)
    if isinstance(setup, str):
        print(setup)
        return 1
    suite, simdirs, envs, starts = setup
    inst = instrument_id()
    try:
        cells = frozen_cells(args, suite)
        sides = chapter_sides(suite, simdirs, envs(), inst, starts, 'pilot',
                              {'vanilla': args.bench_vanilla} if args.bench_vanilla else None)
    except ValueError as err:
        print('refused: %s' % err)
        return 1
    outs = [os.path.join(d, 'runs.jsonl') for d in simdirs.values()]
    hashes = {g: os.path.basename(d) for g, d in simdirs.items()}
    lo, hi = suite['seed_sets']['pilot']
    seeds = list(range(lo, hi + 1))
    # every seed cell_pairs will play now: unplayed, or kept with no game result and a retry
    # still owed (a play that crashes from here on adds its one retry to this)
    todo = []
    for n, side in sides.items():
        have = side['kept']()
        todo += side['tasks']([s for s in seeds
                               if again(have.get(s), side['chapter'], side['pinned'])])
    hours = suite_estimate(dict(suite, starts=starts['ours'] + starts['vanilla']), todo,
                           kept_walls(outs, inst, hashes), args.jobs)
    print('%d runs to play on %d workers: about %.2f wall-hours' % (len(todo), args.jobs, hours))
    if hours > MAX_WALL_H:
        print('refused: the estimate is over the %g wall-hours one job may take (SC-007); '
              'split it' % MAX_WALL_H)
        return 1
    got = cell_pairs(sides, pool_play(args.jobs), seeds)
    if not any(None not in p for p in got['pairs']):
        print('refused: no pilot pair has a game result in both arms; each run says why:')
        print('\n'.join(problem_lines(got['problems'])))
        return 1
    s = pilot_summary(got['pairs'], cells, got['cpu_s'], got['reach'])
    games = games_line(sides, got['paired'])
    # FR-029 on the pilot too: a pilot whose attempts fail an invariant is NOT READABLE, and
    # the analysis it chose must not be handed to `cell`, so it says so first and fails
    v = judged({'verdict': None, 'n': s['n'], 'diff': s['diff'], 'table': s['table'],
                'analysis': s['analysis'], 'cpu_s': s['cpu_s']},
               validity(cell_results(got['results'], seeds)))
    unreadable = v['verdict'] == NOT_READABLE
    if unreadable:
        print('NOT READABLE (%s): this pilot\'s analysis choice cannot be used for a cell'
              % ', '.join(v['failed_invariants']))
    for line in pilot_lines(s, args.chapter, games) + validity_lines(v['validity']) + \
            problem_lines(got['problems']):
        print(line)
    if args.bench_vanilla:
        # an experiment's runs are filed under their own instrument (bench_instrument); its
        # record would stand in for the instrument's real pilot in `report`
        print('no cell record: a benched experiment is not the instrument\'s pilot')
    else:
        append_record(CELLS_FILE, cell_record('pilot', args.chapter, sides['vanilla']['chapter'],
                                              v, got['results'], got['paired'],
                                              {n: sides[n]['store'] for n in sides}, inst,
                                              games))
        print('cell record: %s (`montecarlo.py report` reads it)' % CELLS_FILE)
    print('discordant pairs (story <trace> reads each):')
    for seed in seeds:
        res = got['results'][seed]
        pair = pair_of(res)
        if None not in pair and pair[0] != pair[1]:
            print('  seed %d (%s), only %s lost someone: Manchego Stars %s, vanilla %s' % (
                seed, ', '.join(res[n]['rec']['suite']['start_id'] for n in ('ours', 'vanilla')),
                'Manchego Stars' if pair[0] else 'the twin',
                *(os.path.join(simdirs[n], res[n]['rec'].get('trace') or '?')
                  for n in ('ours', 'vanilla'))))
    return 1 if unreadable else 0


# ---- read validity and the report (#510 step 9 PR-I; FR-029, FR-031, FR-032) ----
# A verdict is only as good as the attempts behind it. Before a cell gets one, both arms'
# first attempts pass FR-029's invariants, or the cell is NOT READABLE with each failed one
# named. There are no human playtests (ADR 0385, amended 2026-11-09): vanilla is the proxy for
# playtesters, so the bot is checked against vanilla (the validity bars and the canary) alone. `report` says it all in sentences, one per cell (FR-031), and
# reads a decision's own components only (FR-032).

ENV_CLEAN_MIN = 0.90       # FR-029: an arm's environment-clean share of its first attempts
BLIND_MAX = 0.10           # FR-029: blindspot plus unclassified attempts, under this
VANILLA_DEATH_MAX = 0.85   # FR-029: the twin losing someone this often reads nothing
VALIDITY = ('environment_clean', 'sandbox_fault', 'blindspot', 'unlabelled_over_cap',
            'unjustified_seize_skip', 'vanilla_deaths')
NOT_READABLE = 'NOT_READABLE'


def first_death(rec):
    """Record `rec`'s first protected death, or None: the earliest by turn, a death with no
    turn after every one with a turn, and same-turn deaths in the order the watch saw them."""
    deaths = protected_deaths(rec)
    if not deaths:
        return None
    return min(enumerate(deaths), key=lambda i_d: (i_d[1].get('turn') is None,
                                                   i_d[1].get('turn') or 0, i_d[0]))[1]


def death_rate(recs):
    """(attempts that lost a protected unit, attempts): the endpoint, counted."""
    return sum(1 for r in recs if protected_deaths(r)), len(recs)


def blind_or_unclassified(d):
    """Whether graded death `d` is one the plan could not see coming (botrun.lua's `blindspot`
    family) or one no cause in botrun.lua names its family (unclassified): an "other" death
    with no detail or an unknown one, or a death with no cause at all."""
    causes, details = botrun_names()
    cause = d.get('cause')
    if cause is None or cause not in causes:
        return True
    return cause == 'other' and details.get(d.get('detail')) in (None, 'blindspot')


def validity(results):
    """FR-029 on a cell's first attempts, `results` {arm: [chapter_result]} (the seeds of the
    look; a seed an arm never reached is left out). Returns {'failed': [(invariant, sentence)],
    'withheld': [sentence]}: a failed invariant makes the cell NOT READABLE, each named
    (VALIDITY); a played attempt whose environment did not hold, with play begun (an
    outcome-dependent fault), withholds the verdict, since which runs fail then can follow what
    happened in them. An attempt with no game result stays in the clean share's denominator;
    FR-027 already bounds its endpoint. The clean share is over every attempt that reached
    the chapter; every other rate is over the arm's played attempts. An arm with no attempt
    at all is listed in `unread`, never passed:
      - environment_clean: under ENV_CLEAN_MIN of the arm's attempts (played or not) clean;
      - sandbox_fault: any protected death the plan's own reads failed (botrun.lua's family);
      - blindspot: BLIND_MAX or more of the attempts with a blindspot or unclassified death;
      - unlabelled_over_cap: any death over the cap no fallback names (run_outcome's);
      - unjustified_seize_skip: any win put off with nothing left it would close;
      - vanilla_deaths: the twin lost someone in VANILLA_DEATH_MAX or more of its attempts."""
    failed, withheld, unread = [], [], []
    for arm in ('ours', 'vanilla'):
        name = GAME_NAMES[arm]
        got = [r for r in results.get(arm) or [] if r['status'] in ('played', 'unresolved')]
        if not got:
            unread.append(arm)
            continue
        clean = sum(1 for r in got if r['rec'].get('env_status') == 'clean')
        if clean < ENV_CLEAN_MIN * len(got):
            failed.append(('environment_clean', '%s: %d of %d attempts environment-clean '
                           '(%.0f%%), the bar is %.0f%%' % (name, clean, len(got),
                                                             100.0 * clean / len(got),
                                                             100 * ENV_CLEAN_MIN)))
        played = [r['rec'] for r in got if r['status'] == 'played']
        dep = [x for x in played if isinstance(x.get('env_status'), dict)
               and x['env_status'].get('outcome_dependent')]
        if dep:
            withheld.append('%s: %s with an outcome-dependent environment fault (%s)' % (
                name, plural(len(dep), 'played attempt'),
                ', '.join(sorted({x['env_status'].get('fault') or '?' for x in dep}))))
        if not played:
            continue
        deaths = [d for x in played for d in protected_deaths(x)]
        sandbox = [d for d in deaths if d.get('cause') == 'other'
                   and botrun_names()[1].get(d.get('detail')) == 'sandbox_fault']
        if sandbox:
            failed.append(('sandbox_fault', '%s: %s (%s)' % (
                name, plural(len(sandbox), 'sandbox-fault death'),
                ', '.join(sorted({d['detail'] for d in sandbox})))))
        blind = sum(1 for x in played if any(blind_or_unclassified(d)
                                             for d in protected_deaths(x)))
        if blind >= BLIND_MAX * len(played):
            failed.append(('blindspot', '%s: %d of %d attempts (%.0f%%) lost someone to a '
                           'blindspot or an unclassified death, the bar is under %.0f%%' % (
                               name, blind, len(played), 100.0 * blind / len(played),
                               100 * BLIND_MAX)))
        unlabelled = sum(run_outcome(x)['unlabelled'] for x in played)
        if unlabelled:
            failed.append(('unlabelled_over_cap', '%s: %s over the cap no fallback names' % (
                name, plural(unlabelled, 'death'))))
        skips = sum(1 for x in played for k in x.get('seize_skips') or []
                    if not k.get('justified'))
        if skips:
            failed.append(('unjustified_seize_skip', '%s: %s put off with nothing left to '
                           'close' % (name, plural(skips, 'win'))))
        if arm == 'vanilla':
            died = death_rate(played)[0]
            if died >= VANILLA_DEATH_MAX * len(played):
                failed.append(('vanilla_deaths', 'vanilla: lost someone in %d of %d attempts '
                               '(%.0f%%), the bar is under %.0f%%' % (
                                   died, len(played), 100.0 * died / len(played),
                                   100 * VANILLA_DEATH_MAX)))
    return {'failed': failed, 'withheld': withheld, 'unread': unread}


def validity_lines(valid):
    """validity's result in sentences: each failed invariant, by name, each withholding, and
    an arm with no attempt to read, which never reads as holding."""
    unread = valid.get('unread') or []
    if not valid['failed'] and not valid['withheld'] and not unread:
        return ['validity (FR-029): every invariant holds in both arms']
    if valid['failed']:
        out = ['validity (FR-029): NOT READABLE, %s' % ', '.join(n for n, _ in valid['failed'])]
    elif unread:
        out = ['validity (FR-029): not read, %s' % ', '.join(GAME_NAMES[a] for a in unread)]
    else:
        out = ['validity (FR-029): withheld']
    out += ['  %s: not read, no attempt reached the chapter' % GAME_NAMES[a] for a in unread]
    out += ['  %s: %s' % (n, said) for n, said in valid['failed']]
    out += ['  withheld: %s' % said for said in valid['withheld']]
    return out


def judged(verdict, valid):
    """paired_verdict's `verdict` with `valid` (validity's) applied: NOT READABLE, settled,
    naming every failed invariant, when one failed; else WITHHELD, settled, when an
    outcome-dependent fault withholds it, whatever it read (a pilot, verdict None, has nothing
    to withhold); else unchanged. Both settle the cell: the attempts behind the fault stay in
    every later look, so more pairs could never clear it. The interval stays on the record,
    for the report's descriptive line, never as a verdict."""
    out = dict(verdict, validity=valid)
    at = ' at %s' % verdict['look'] if verdict.get('look') is not None else ''
    if valid['failed']:
        names = [n for n, _ in valid['failed']]
        out.update(verdict=NOT_READABLE, settled=True, failed_invariants=names,
                   reason='NOT READABLE%s: %s' % (at, '; '.join(s for _, s in valid['failed'])))
    elif valid['withheld'] and verdict.get('verdict') is not None:
        faults = '; '.join(valid['withheld'])
        # a verdict already withheld (an arm's reach unknown) keeps its own reason too
        reason = '%s; %s' % (verdict['reason'], faults) \
            if verdict['verdict'] == 'WITHHELD' and verdict.get('reason') \
            else 'withheld%s: %s' % (at, faults)
        out.update(verdict='WITHHELD', settled=True, reason=reason)
    return out


def first_attempts(paths, instrument):
    """{(game, chapter): [played attempt-1 record]} of `instrument` in runs files `paths`,
    never a held-out run (those stay unseen until the verdict, FR-025)."""
    return kept(paths, lambda r: is_bot(r) and r.get('instrument') == instrument
                and r.get('attempt') == 1 and r.get('outcome') not in UNUSABLE
                and (r.get('suite') or {}).get('set') != 'held_out',
                lambda r: (r.get('game'), r.get('chapter')))


# ---- the canary (spec assumptions): on Normal, vanilla's first-attempt death rates order
# Ch1 below Ch5 and Ch2 below Ch6. An inversion is a banner and an audit, never a verdict.
CANARY = (('FE8 Ch1', 'FE8 Ch5'), ('FE8 Ch2', 'FE8 Ch6'))


def canary(vanilla):
    """The canary's lines and whether it inverted, from {chapter index: [vanilla played
    attempt-1 record]}. An order is read only when both chapters have attempts; one that
    cannot be read says so, never passes."""
    rows = vanilla_rows()
    pairs = [(lo, hi, 'expected') for lo, hi in CANARY]
    lines, inverted = [], False
    for lo, hi, why in pairs:
        (k1, n1), (k2, n2) = (death_rate(vanilla.get(rows[c]) or []) for c in (lo, hi))
        if not n1 or not n2:
            empty = [vanilla_name(c) for c, n in ((lo, n1), (hi, n2)) if not n]
            lines.append('canary %s below %s (%s): not read, %s %s no first attempts under '
                         'this instrument' % (vanilla_name(lo), vanilla_name(hi), why,
                                              ' and '.join(empty),
                                              'have' if len(empty) > 1 else 'has'))
            continue
        bad = k1 / n1 > k2 / n2
        inverted = inverted or bad
        lines.append('canary %s below %s (%s): %s %d of %d, %s %d of %d: %s' % (
            vanilla_name(lo), vanilla_name(hi), why, vanilla_name(lo), k1, n1, vanilla_name(hi),
            k2, n2,
            'INVERTED' if bad else 'holds'))
    if inverted:
        lines.insert(0, '!!! CANARY INVERSION: vanilla\'s own chapters read out of order; '
                        'audit the instrument (`montecarlo.py audit`) before reading any cell')
    return lines, inverted


# ---- the descriptive data (FR-031) and what each decision reads (FR-032) ----
SURVIVAL_TURNS = (1, 3, 5, 10, 15, 20)
COMPONENTS = ('survival', 'turn5', 'nonluck', 'causes', 'boss_causes', 'by_unit', 'rng_tail',
              'greens', 'missed', 'stalls', 'winner_turns')
DECISIONS = {'party': ('causes', 'by_unit'),
             'enemy': ('boss_causes', 'rng_tail', 'winner_turns')}


def describe(recs):
    """One arm's descriptive data from its played attempt-1 records, by component (COMPONENTS):
    the share alive by each turn, turn-5 deaths, deaths not down to a lost roll, deaths by
    cause (with the boss flag), the boss's deaths by cause leaving out over-cap ones (an enemy
    level decision's), deaths by unit, rng_tail deaths, greens lost, rewards and recruits
    missed, stalls and the turns the wins took. Counts are attempts' or deaths' as named."""
    n = len(recs)
    firsts = [first_death(r) for r in recs]
    first = [(d.get('turn') or 0) if d else None for d in firsts]
    deaths = [d for r in recs for d in protected_deaths(r)]
    causes = collections.Counter('%s%s' % (d.get('cause'), ', boss' if (d.get('flags') or {})
                                           .get('boss') else '') for d in deaths)
    boss = collections.Counter(d.get('cause') for d in deaths
                               if (d.get('flags') or {}).get('boss')
                               and d.get('cause') != 'over_cap')
    greens = [d for r in recs for d in r.get('deaths') or [] if d.get('faction') == 'green']
    missed = collections.Counter(t.get('reason') or '?' for r in recs
                                 for t in r.get('missed_rewards') or [])
    missed['recruits'] = sum(len(r.get('missed_recruits') or []) for r in recs)
    return {'n': n, 'died': death_rate(recs)[0],
            'survival': [(t, sum(1 for f in first if f is None or f > t)) for t in SURVIVAL_TURNS],
            'turn5': sum(1 for f in first if f is not None and f <= 5),
            'nonluck': sum(1 for d in deaths if d.get('cause') != 'rng_tail'),
            'causes': causes, 'boss_causes': boss,
            'by_unit': collections.Counter(d.get('charId') for d in deaths),
            'rng_tail': sum(1 for d in deaths if d.get('cause') == 'rng_tail'),
            'greens': (len(greens), sum(1 for d in greens if d.get('escort'))),
            'missed': +missed,
            'stalls': sum(len(r.get('stall_events') or []) for r in recs),
            'winner_turns': sorted(r['turns_to_win'] for r in recs
                                   if r.get('outcome') == 'won' and r.get('turns_to_win'))}


def component_line(comp, arms, who=None):
    """One component's line, the two arms side by side (FR-032: every result beside its twin);
    `arms` is {arm: describe()}, `who` {arm: charId -> name} (hex ids when None)."""
    who = who or {}
    def counts(c, fmt=str):
        order = lambda kv: (-kv[1], (0, kv[0], '') if isinstance(kv[0], int) else (1, 0,
                                                                               str(kv[0])))
        return ', '.join('%s %d' % (fmt(k), v) for k, v in sorted(c.items(), key=order)) \
            or 'none'

    def one(arm):
        d = arms[arm]
        n = d['n']
        if not n:
            return 'no attempts'
        if comp == 'survival':
            return ', '.join('t%d %.0f%%' % (t, 100.0 * k / n) for t, k in d['survival'])
        if comp == 'turn5':
            return '%d of %d attempts' % (d['turn5'], n)
        if comp in ('nonluck', 'rng_tail', 'stalls'):
            return '%d' % d[comp]
        if comp in ('causes', 'boss_causes', 'missed'):
            return counts(d[comp])
        if comp == 'by_unit':
            return counts(d['by_unit'], who.get(arm) or hex_id)
        if comp == 'greens':
            return '%d lost, %d of them escorts' % d['greens']
        if comp == 'winner_turns':
            w = d['winner_turns']
            return ('%d wins, turns %d to %d, median %d' % (len(w), w[0], w[-1],
                                                            w[len(w) // 2])) if w else 'no wins'
        raise ValueError('montecarlo: no component %r (%s)' % (comp, ', '.join(COMPONENTS)))
    words = {'survival': 'no protected death by turn', 'turn5': 'a protected death by turn 5',
             'nonluck': 'protected deaths not down to a lost roll',
             'causes': 'protected deaths by cause', 'boss_causes':
             'boss-flagged deaths by cause, over-cap left out', 'by_unit':
             'protected deaths by unit', 'rng_tail': 'rng_tail deaths', 'greens': 'greens',
             'missed': 'goals missed (rewards by reason, recruits)', 'stalls': 'stalls',
             'winner_turns': 'turns to win'}[comp]
    return '  %s: Manchego Stars %s; twin %s' % (words, one('ours'), one('vanilla'))


def drivers(arms, diff):
    """The components that drive a cell's difference, in words (FR-031): the two causes (boss
    flag kept) whose deaths an attempt differ most between the arms in the difference's
    direction, then escort greens when Manchego Stars lost more. [] when nothing differs."""
    o, v = arms['ours'], arms['vanilla']
    sign = 1 if (diff or 0) >= 0 else -1
    rate = lambda d, k: d['causes'].get(k, 0) / d['n'] if d['n'] else 0.0
    gaps = sorted((-sign * (rate(o, k) - rate(v, k)), k) for k in set(o['causes']) |
                  set(v['causes']))
    out = ['%s deaths (Manchego Stars %.2f an attempt, twin %.2f)' % (k, rate(o, k),
                                                                         rate(v, k))
           for g, k in gaps[:2] if g < 0]
    if o['greens'][1] > v['greens'][1] and sign > 0:
        out.append('%s (twin %d)' % (plural(o['greens'][1], 'escort-green death'),
                                     v['greens'][1]))
    return out


VERDICT_WORDS = {'EQUIVALENT': 'equivalent within the +-10 margin',
                 'HARDER': 'harder', 'EASIER': 'easier', 'INCONCLUSIVE': 'inconclusive',
                 'WITHHELD': 'withheld', NOT_READABLE: 'NOT READABLE'}


@functools.lru_cache(maxsize=None)
def vanilla_rows():
    """{'FE8 Prologue': 0, ..., 'FE8 Ch5': 6, ...}: each vanilla chapter's index, from
    inject.chapter_settings.twin_rows, the one owner of that mapping."""
    sys.path.insert(0, os.path.dirname(HERE))
    import inject.chapter_settings
    return inject.chapter_settings.twin_rows()


def vanilla_name(row):
    """A twin_rows name ('FE8 Ch3') as a reader says it ('vanilla Ch3'): the one formatter."""
    return 'vanilla ' + row.split()[-1]


def twin_name(index):
    """Vanilla chapter index `index` as a reader says it ('vanilla Ch3')."""
    for name, i in vanilla_rows().items():
        if i == index:
            return vanilla_name(name)
    return 'vanilla chapter %d' % index


def cell_sentence(cell, arms):
    """A cell in one plain sentence (FR-031): which chapters, how many pairs over how many
    games, its verdict with its uncertainty or NOT READABLE with the failed invariants, the two
    arms' death rates and what drives the difference."""
    o, v = arms['ours'], arms['vanilla']
    head = '%s ch%02d vs %s, %d pairs%s: ' % (
        GAME_NAMES['ours'], cell['chapter'], twin_name(cell['twin_index']), cell['pairs'],
        ' ' + cell['games'] if cell.get('games') else '')
    verdict = cell.get('verdict')
    if verdict == NOT_READABLE:
        what = 'NOT READABLE (%s)' % ', '.join(cell['failed_invariants'])
    elif verdict is None:
        what = 'a pilot, no verdict'
    elif verdict == 'WITHHELD':
        what = 'withheld (%s)' % cell.get('reason')
    else:
        what = '%s, %+.1f to %+.1f points' % (VERDICT_WORDS[verdict], 100 * cell['lo'],
                                             100 * cell['hi'])
    rates = 'a protected unit died in Manchego Stars %d of %d, the twin %d of %d' % (
        o['died'], o['n'], v['died'], v['n'])
    why = drivers(arms, cell.get('diff'))
    return head + what + ' on any protected death; ' + rates + (
        ', driven by ' + ' and '.join(why) if why else '')


# ---- cell records (plan: "Cell records"): what `pilot` and `cell` decided, one line a run
# of either, beside the stores; `report` reads them and the runs they name.
CELLS_FILE = os.path.join(REPO, 'references', 'sim', 'cells.jsonl')


def cell_record(kind, chapter, twin_index, verdict, results, seeds, stores, instrument,
                games=None):
    """The `kind: cell` record of one pilot or cell run: its verdict fields (None for a
    pilot), validity, its pairs, and each arm's played attempt-1 runs (run_ref) with the
    store's runs file, so `report` reads the very records judged. `seeds` are the seeds that
    made a pair (cell_pairs' `paired`), so the descriptive data counts what the verdict does."""
    runs = {arm: [run_ref(results[s][arm]['rec']) for s in seeds
                  if results[s][arm]['status'] == 'played'] for arm in ('ours', 'vanilla')}
    return {'kind': 'cell', 'cell_kind': kind, 'chapter': chapter, 'twin_index': twin_index,
            'instrument': instrument, 'verdict': verdict.get('verdict'),
            'reason': verdict.get('reason'), 'lo': verdict.get('lo'), 'hi': verdict.get('hi'),
            'look': verdict.get('look'), 'analysis': verdict.get('analysis'),
            'table': verdict.get('table'), 'diff': verdict.get('diff'),
            'pairs': verdict.get('n', len(seeds)), 'games': games,
            'failed_invariants': verdict.get('failed_invariants') or [],
            'validity': verdict.get('validity'), 'cpu_s': verdict.get('cpu_s') or 0.0,
            'stores': stores, 'runs': runs}


def cell_results(results, seeds):
    """{arm: [chapter_result]} of `seeds`, validity's input, from cell_pairs' `results`."""
    return {arm: [results[s][arm] for s in seeds if s in results]
            for arm in ('ours', 'vanilla')}


def report_cells(path, instrument=None):
    """The cell records in `path` of `instrument` (the newest in the file when None): one job's
    cells, the last record of each (kind, chapter) kept."""
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        recs = [json.loads(line) for line in fh if line.strip()]
    recs = [r for r in recs if r.get('kind') == 'cell']
    if not recs:
        return []
    instrument = instrument or recs[-1]['instrument']
    last = {}
    for r in recs:
        if r['instrument'] == instrument:
            last[(r['cell_kind'], r['chapter'])] = r
    return [last[k] for k in sorted(last, key=lambda k: (k[1], k[0]))]


def run_ref(rec):
    """A played run as a cell record names it: its name, its filed trace and its instrument.
    The trace alone is not enough: keep_trace drops it when the file is gone, and every
    trace-less record in a store would then share the one key None."""
    return [run_name(rec), run_key(rec), rec.get('instrument')]


def cell_arms(cell):
    """{arm: [played attempt-1 record]} a cell record names (run_ref), read from its stores,
    the newest record of each name. ValueError naming a run the store no longer holds."""
    out = {}
    for arm in ('ours', 'vanilla'):
        if any(not isinstance(w, (list, tuple)) for w in cell['runs'][arm]):
            raise ValueError('montecarlo: the ch%02d cell record predates run_ref (it names %s '
                             'runs by trace alone): rerun the pilot' % (cell['chapter'],
                                                                     GAME_NAMES[arm]))
        want = [tuple(w) for w in cell['runs'][arm]]
        wanted = set(want)
        have = kept([cell['stores'][arm]],
                    lambda r: is_bot(r) and tuple(run_ref(r)) in wanted,
                    lambda r: tuple(run_ref(r)))
        lost = [w for w in want if w not in have]
        if lost:
            raise ValueError('montecarlo: %s no longer holds %s of the ch%02d cell (first: %s)'
                             % (cell['stores'][arm], plural(len(lost), 'run'),
                                cell['chapter'], '/'.join(str(x) for x in lost[0])))
        out[arm] = [have[w][-1] for w in want]
    return out


def report(cells, arms_of, canary_out, decision=None, components=None, who=None):
    """FR-031's report, in order, as lines (it is not a table): the header (instrument,
    CPU-hours, pairs and the label counts), the canary with its banner, one sentence a cell,
    the anomalies with their `story` commands, the validity failures and the descriptive
    data. `decision` ('party', 'enemy' or 'chapter' with `components`)
    reads only that decision's components (FR-032), each beside the twin; None reads all.
    `arms_of(cell)` is {arm: [played attempt-1 record]} (cell_arms), `who` component_line's."""
    if decision is None:
        comps = COMPONENTS
    elif decision == 'chapter':
        if not components:
            raise ValueError('a chapter-change decision names the components it affected '
                             '(--components, of %s)' % ', '.join(COMPONENTS))
        comps = tuple(components)
    elif decision in DECISIONS:
        comps = DECISIONS[decision]
    else:
        raise ValueError('montecarlo: no decision %r (party, enemy, chapter)' % (decision,))
    for c in comps:
        if c not in COMPONENTS:
            raise ValueError('montecarlo: no component %r (%s)' % (c, ', '.join(COMPONENTS)))
    labels = collections.Counter(c['verdict'] or 'pilot' for c in cells)
    cpu = sum(c.get('cpu_s') or 0.0 for c in cells)
    lines = ['instrument %s: %s, %d pairs, %.2f CPU-hours; %s' % (
        cells[0]['instrument'] if cells else '?', plural(len(cells), 'cell'),
        sum(c['pairs'] for c in cells), cpu / 3600,
        ', '.join('%s %d' % (k, v) for k, v in sorted(labels.items())) or 'no cells')]
    lines += canary_out[0]
    described = []
    for c in cells:
        recs = arms_of(c)
        arms = {a: describe(recs[a]) for a in ('ours', 'vanilla')}
        described.append((c, recs, arms))
        lines.append(cell_sentence(c, arms))
    # one line a run, its anomalies by kind with their turns, and the story command at the
    # first one's turn: a cell of 100 runs can carry a hundred anomalies
    runs = [(c, arm, r) for c, recs, _ in described for arm in ('ours', 'vanilla')
            for r in recs[arm] if r.get('anomalies')]
    lines.append('anomalies: %d in %d runs' % (sum(len(r['anomalies']) for _, _, r in runs),
                                               len(runs)))
    for c, arm, r in runs:
        kinds = collections.OrderedDict()
        for a in r['anomalies']:
            kinds.setdefault(a.get('kind'), []).append(str(a.get('turn')))
        cmd = next((a['narrate'] for a in r['anomalies'] if a.get('narrate')), None)
        lines.append('  ch%02d %s seed %s: %s%s' % (
            c['chapter'], GAME_NAMES[arm], r.get('seed'),
            '; '.join('%s turn %s' % (k, ', '.join(t)) for k, t in kinds.items()),
            ' -> ' + cmd if cmd else ' (no trace kept)'))
    failures = [(c, s) for c in cells for _, s in (c.get('validity') or {}).get('failed', [])]
    lines.append('validity failures: %s' % (len(failures) or 'none'))
    lines += ['  ch%02d %s' % (c['chapter'], s) for c, s in failures]
    for c, _, arms in described:
        lines.append('ch%02d, %s:' % (c['chapter'], 'the components a %s decision reads'
                                      % decision if decision else 'descriptive data'))
        lines += [component_line(k, arms, who) for k in comps]
    return lines


def report_main(args):
    """`report`: FR-031's report of one instrument's cells, printed; with --post, written to a
    file and the `gh issue comment` that would post it printed, never run (T107)."""
    cells = report_cells(args.cells, args.instrument)
    if not cells:
        print('refused: no cell records in %s%s; `pilot` and `cell` write them' % (
            args.cells, ' for %s' % args.instrument if args.instrument else ''))
        return 1
    inst = cells[0]['instrument']
    paths = sorted({p for c in cells for p in c['stores'].values()})
    vanilla = {ch: recs for (game, ch), recs in first_attempts(paths, inst).items()
               if game == 'vanilla'}
    names = {g: _names(g) for g in ('ours', 'vanilla')}
    try:
        lines = report(cells, cell_arms, canary(vanilla), args.decision,
                       args.components.split(',') if args.components else None,
                       {g: namer(names[g]) for g in names})
    except ValueError as err:
        print('refused: %s' % err)
        return 1
    print('\n'.join(lines))
    if args.post:
        out = os.path.join(REPO, 'build', 'report-%s.md' % inst.replace('+', '-'))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, 'w') as fh:
            fh.write('\n'.join(lines) + '\n')
        print('\nto post it (only on Nicolas\'s go-ahead):\n  gh issue comment 510 '
              '--body-file %s' % os.path.relpath(out, REPO))
    return 0


# ---- the frozen suite (#510 step 9 plan, PR-A: T006, T010) ----
# The instrument's regression suite is a section of matrix.yaml (plan R-6: one manifest owns
# what a playtest needs, ADR 0074): pinned chapter starts, each played on attempt 1 from its
# saved state under fixed seeds. FR-021 says what an entry names; FR-025 that the tuning,
# held-out, pilot and confirmatory seeds never meet.

SUITE_TOP = ('version', 'route', 'emulator', 'seed_sets', 'cells', 'shops_from', 'starts')
SUITE_KEYS = ('start_id', 'game', 'chapter', 'rom_hash', 'state_path', 'state_sha1',
              'provenance', 'label', 'seeds', 'style', 'invariant', 'budgets', 'estimate_wall_s')
BUDGET_KEYS = ('beam', 'final', 'branch', 'lookahead_decision', 'lookahead_attempt')
LABELS = ('fixture', 'scout', 'snapshot')
STYLES = ('drawn',)       # attempt 1's own draw (campaign.lua drawStyle), what a cell plays
INVARIANTS = ('record',)  # the attempt leaves one BOTRUN record with a game result
# A failing decision's kept state (FR-021, T084): a fresh emulator's load of it holds the board
# its decision read
SNAPSHOT_KEYS = ('snapshot_id', 'start_id', 'state_path', 'state_sha1', 'board_path',
                 'board_sha1', 'provenance', 'invariant')
SNAPSHOT_PROVENANCE = ('seed', 'set', 'ref', 'mode', 'char', 'source')
SNAPSHOT_INVARIANTS = ('pinned_board',)


def instrument_section(path=None):
    """matrix.yaml's `instrument:` section as written, unchecked ({} when there is none)."""
    import yaml
    import matrix
    with open(path or matrix.MANIFEST) as fh:
        return (yaml.safe_load(fh) or {}).get('instrument') or {}


def load_suite(path=None):
    """matrix.yaml's `instrument:` section, every start with the defaults it does not name
    merged in (key by key, as matrix.yaml's rows take its defaults). Raises ManifestError on a
    start listed twice (its id or its state), a field missing, a seed in two sets, or other
    than two distinct tuning and two distinct held-out seeds a start (FR-021)."""
    from matrix import ManifestError
    inst = instrument_section(path)
    if not inst:
        raise ManifestError('matrix.yaml has no `instrument:` section')
    lacking = [k for k in SUITE_TOP if inst.get(k) is None]
    if lacking:
        raise ManifestError('the suite manifest has no %s' % ', '.join(lacking))
    if isinstance(inst['cells'], bool) or not isinstance(inst['cells'], int) or \
            inst['cells'] < 1:
        raise ManifestError('the suite manifest\'s cells %r is not a positive count (the frozen '
                            'N of ADR 0385)' % (inst['cells'],))
    defaults = inst.get('defaults') or {}
    sets = {name: set(range(lo, hi + 1)) for name, (lo, hi) in inst['seed_sets'].items()}
    names = sorted(sets)
    for i, one in enumerate(names):   # FR-025: the pilot never plays a confirmatory seed
        for other in names[i + 1:]:
            if sets[one] & sets[other]:
                raise ManifestError('the suite manifest\'s %s and %s seeds meet at %d (FR-025)'
                                    % (one, other, min(sets[one] & sets[other])))
    starts, ids, states = [], set(), set()
    used = {'tuning': {}, 'held_out': {}}   # seed -> the start that uses it
    for row in inst.get('starts') or []:
        s = dict(defaults, **row)
        sid = s.get('start_id')
        for k in ('seeds', 'budgets'):   # a table merges key by key too
            for got in (defaults.get(k), row.get(k)):
                if got is not None and not isinstance(got, dict):
                    raise ManifestError('suite start %s: %s %r is not a table' % (sid, k, got))
            s[k] = dict(defaults.get(k) or {}, **(row.get(k) or {}))
        missing = [k for k in SUITE_KEYS if s.get(k) is None] + \
            ['budgets.' + k for k in BUDGET_KEYS if s['budgets'].get(k) is None]
        if missing:
            raise ManifestError('suite start %s: no %s' % (sid, ', '.join(missing)))
        if sid in ids:
            raise ManifestError('suite start %s is listed twice' % sid)
        if s['state_path'] in states:
            raise ManifestError('suite start %s: its state %s is listed twice'
                                % (sid, s['state_path']))
        ids.add(sid)
        states.add(s['state_path'])
        for k, allowed in (('game', ('vanilla', 'ours')), ('label', LABELS), ('style', STYLES),
                           ('invariant', INVARIANTS)):
            if s[k] not in allowed:
                raise ManifestError('suite start %s: %s %r is not one of %s'
                                    % (sid, k, s[k], ', '.join(allowed)))
        for kind in ('tuning', 'held_out'):
            seeds = s['seeds'].get(kind) or []
            if len(set(seeds)) != 2 or len(seeds) != 2:
                raise ManifestError('suite start %s: %s seeds %r, not two distinct ones'
                                    % (sid, kind, seeds))
            other = 'held_out' if kind == 'tuning' else 'tuning'
            for seed in seeds:
                clash = [n for n, r in sets.items() if seed in r]
                if seed in used[other]:
                    clash.append('%s (%s)' % (other, used[other][seed]))
                if clash:
                    raise ManifestError('suite start %s: %s seed %d is also a %s seed (FR-025)'
                                        % (sid, kind, seed, ' and '.join(clash)))
                used[kind][seed] = sid
        starts.append(s)
    held = set(used['held_out'])
    by_id = {s['start_id']: s for s in starts}
    snaps, snap_ids = [], set()
    for row in inst.get('snapshots') or []:
        sid = row.get('snapshot_id')
        missing = [k for k in SNAPSHOT_KEYS if row.get(k) is None] + \
            ['provenance.' + k for k in SNAPSHOT_PROVENANCE
             if (row.get('provenance') or {}).get(k) is None]
        if missing:
            raise ManifestError('suite snapshot %s: no %s' % (sid, ', '.join(missing)))
        if sid in snap_ids:
            raise ManifestError('suite snapshot %s is listed twice' % sid)
        snap_ids.add(sid)
        if row['start_id'] not in by_id:
            raise ManifestError('suite snapshot %s: no start %s' % (sid, row['start_id']))
        if row['invariant'] not in SNAPSHOT_INVARIANTS:
            raise ManifestError('suite snapshot %s: invariant %r is not one of %s'
                                % (sid, row['invariant'], ', '.join(SNAPSHOT_INVARIANTS)))
        snaps.append(dict(row, game=by_id[row['start_id']]['game']))
    # AS 2: a fixture made from a held-out run's failure enters only once that seed is no
    # longer held out, its replacement frozen: until then it would tune the bot to it
    for kind, sid, prov in ([('start', s['start_id'], s['provenance']) for s in starts]
                            + [('snapshot', s['snapshot_id'], s['provenance']) for s in snaps]):
        if prov.get('set') == 'held_out' and not inst.get('held_out_frozen_at'):
            raise ManifestError('suite %s %s comes from a held-out run, and the manifest names '
                                'no commit that froze its held-out seeds (held_out_frozen_at)'
                                % (kind, sid))
        # by the seed, whatever the label says: a fixture mislabelled `tuning` is refused too
        if prov.get('seed') in held:
            raise ManifestError('suite %s %s comes from held-out seed %s, which is still held '
                                'out: freeze its replacement first (AS 2)'
                                % (kind, sid, prov.get('seed')))
    return dict(inst, starts=starts, snapshots=snaps)


MAX_WALL_H = 8    # SC-007: a planned job longer than this is split or narrowed, never run
# The frozen baseline (#510 step 9 PR-G, ADR 0395): what the instrument did when it was frozen,
# the comparator every later change is judged on. SC-003 / FR-022: a suite's AiDecideMain calls
# more than FROZEN_MARGIN over the frozen count are a regression.
FROZEN = os.path.join(HERE, 'suite-frozen.json')
FROZEN_MARGIN = 0.20
SEED_SETS = ('tuning', 'held_out')


def sha1_file(path):
    """A file's sha1, as `shasum` prints it (run.sh names a ROM's store by the same hash)."""
    h = hashlib.sha1()
    with open(path, 'rb') as fh:
        for block in iter(lambda: fh.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


@functools.lru_cache(maxsize=None)
def instrument_id(path=None):
    """The instrument a run is played under (the record's `instrument`): the bot code's hash
    and the suite manifest's version. Read alone, so a cell's runs never hang on the rest of
    the suite's validation (load_suite's); a manifest with no version raises, since every run
    would otherwise be stamped with nothing."""
    from matrix import ManifestError
    version = instrument_section(path).get('version')
    if not isinstance(version, int):
        raise ManifestError('the suite manifest has no integer `version` (%r)' % (version,))
    return '%s+v%d' % (bot_hash(), version)


def check_starts(suite, simdirs, emulator_sha1=None):
    """Why each pinned start cannot be played as pinned, one sentence each ([] = all can): the
    emulator is not the pinned build, the ROM built now is not the one that saved the state
    (`simdirs[game]` is its store, named by its hash), the state is not where the harness
    loads it from, or its file is gone or changed."""
    out = ['the shops store %s is gone' % p for p in suite['shops_from']
           if not os.path.isdir(os.path.join(REPO, p))]
    emu = suite['emulator']
    got = emulator_sha1 or sha1_file(os.path.join(REPO, emu['binary']))
    if got != emu['sha1']:
        out.append('the emulator %s is not the pinned build (sha1 %s, pinned %s)'
                   % (emu['binary'], got[:12], emu['sha1'][:12]))
    for st in suite['starts']:
        store = simdirs[st['game']]
        path = os.path.join(REPO, st['state_path'])
        want = os.path.join(store, 'states', st['provenance']['campaign'],
                            '%d.ss' % st['chapter'])
        if not os.path.basename(store):
            why = 'no %s ROM is built' % st['game']
        elif os.path.basename(store) != st['rom_hash']:
            why = 'pinned on ROM %s, but the %s ROM built now is %s' % (
                st['rom_hash'], st['game'], os.path.basename(store))
        elif os.path.abspath(path) != os.path.abspath(want):
            why = 'its state %s is not where the harness loads it (%s)' % (path, want)
        elif not os.path.exists(path):
            why = 'its state %s is gone' % path
        elif sha1_file(path) != st['state_sha1']:
            why = 'its state %s no longer hashes to %s' % (path, st['state_sha1'][:12])
        else:
            continue
        out.append('%s: %s' % (st['start_id'], why))
    for sn in suite.get('snapshots') or []:
        path = os.path.join(REPO, sn['state_path'])
        if not os.path.exists(path):
            why = 'its state %s is gone' % path
        elif sha1_file(path) != sn['state_sha1']:
            why = 'its state %s no longer hashes to %s' % (path, sn['state_sha1'][:12])
        elif not os.path.exists(os.path.join(REPO, sn['board_path'])):
            why = 'its board %s is gone' % sn['board_path']
        elif sha1_file(os.path.join(REPO, sn['board_path'])) != sn['board_sha1']:
            why = 'its board %s no longer hashes to %s' % (sn['board_path'], sn['board_sha1'][:12])
        else:
            continue
        out.append('%s: %s' % (sn['snapshot_id'], why))
    return out


def suite_tasks(suite, envs, instrument, outs, sets=SEED_SETS):
    """Attempt 1 of each pinned start under each of its seeds in `sets` (chapter_tasks')."""
    return [t for st in suite['starts'] for kind in sets
            for t in chapter_tasks(suite, envs, instrument, outs, st, kind)]


def chapter_tasks(suite, envs, instrument, outs, st, kind, seeds=None):
    """Attempt 1 of pinned start `st` (a suite start, or a cell start: cell_starts'), one
    task a seed: the game's campaign env
    (`envs[game]`) resumed at the start's chapter from the state its campaign saved, and
    ended there (campaign_env.pinned_env). The seeds are the start's own for a suite set
    (`tuning`, `held_out`), the manifest's range for a cell's (`pilot`, `confirmatory`),
    each an independent replicate on the same pinned start in both arms (FR-024); `seeds`
    picks some of them. An attempt-mode run saves no state, so the pinned file is never
    rewritten (campaign.lua)."""
    import campaign_env
    if kind in SEED_SETS:
        allowed = list(st['seeds'][kind])
    elif kind in suite['seed_sets']:
        lo, hi = suite['seed_sets'][kind]
        allowed = list(range(lo, hi + 1))
    else:
        raise ValueError('montecarlo: no seed set %r' % (kind,))
    if seeds is not None:
        stray = [s for s in seeds if s not in allowed]
        if stray:
            raise ValueError('montecarlo: seeds %s are not %s seeds (FR-025)' % (stray, kind))
        allowed = [s for s in allowed if s in set(seeds)]
    camp = campaign_env.pinned_env(envs[st['game']], st['provenance']['campaign'],
                                   st['chapter'])
    return [{'campaign': camp, 'seed': seed, 'vanilla': st['game'] == 'vanilla',
             'instrument': instrument, 'out': outs.get(st['game']),
             'stamp': {'task_attempt': 1, 'suite': {'start_id': st['start_id'], 'set': kind,
                                                    'version': suite['version']}}}
            for seed in allowed]


def suite_run_of(instrument, rom_hashes):
    """Whether a kept record is a suite run this instrument played on these ROMs ({game:
    hash}): what kept_walls and kept_play both read."""
    return lambda r: (bool(r.get('suite')) and is_bot(r) and r.get('instrument') == instrument
                      and r.get('rom_hash') == rom_hashes.get(r.get('game')))


def kept_walls(paths, instrument, rom_hashes):
    """{start_id: [wall_s]} of the suite runs kept in `paths` (each game's runs file) that this
    instrument played on these ROMs ({game: hash}) to a game result: a run of other code, or
    one that crashed at boot in seconds, says nothing about what the next will take."""
    mine = suite_run_of(instrument, rom_hashes)
    runs = kept(paths, lambda r: mine(r) and r.get('outcome') not in UNUSABLE
                and r.get('wall_s') is not None,
                lambda r: r['suite']['start_id'])
    return {sid: [r['wall_s'] for r in recs] for sid, recs in runs.items()}


def suite_estimate(suite, tasks, kept, jobs):
    """The wall-hours `tasks` would take on `jobs` workers: each start's mean measured wall
    time a run where a kept run has one (`kept`, kept_walls'), its manifest estimate where
    none has."""
    by_id = {st['start_id']: st for st in suite['starts']}
    total = 0.0
    for t in tasks:
        sid = t['stamp']['suite']['start_id']
        walls = kept.get(sid)
        total += sum(walls) / len(walls) if walls else by_id[sid]['estimate_wall_s']
    return total / max(1, min(jobs, len(tasks))) / 3600


def lookahead_line(look):
    """The lookahead's trigger rate, coverage, skipped extensions and CPU (SC-003), in words.
    `look` is a Counter of botrun's rec.lookahead fields (FR-018), summed: a field no record
    had reads 0."""
    return ('lookahead: %d of %d decisions triggered (%.1f%%), %d extended, %d skipped for '
            'budget, %d calls, %.1f CPU s' % (
                look['triggered'], look['decisions'],
                100.0 * look['triggered'] / max(1, look['decisions']), look['extended'],
                look['skipped_budget'], look['calls'], look['cpu_s']))


def held_out_tag(start_id, seed):
    """A held-out run's name as the frozen baseline keeps it: hashed, so reading the file does
    not tell whoever tunes the bot which held-out run lost (FR-025). It keeps the honest
    honest; it hides nothing from someone who hashes every start and seed on purpose."""
    return hashlib.sha1(('%s/%s' % (start_id, seed)).encode()).hexdigest()[:16]


def run_outcome(rec):
    """What a regression is judged on in one suite run, and the frozen baseline keeps of a
    tuning run: whether its invariant held (`record`: one BOTRUN record with a game result),
    which units it answers for died (blue, or an escort green: a green the bot does not escort
    is not its to keep alive), its stalls, whether it lost, and its unlabelled fallbacks: those
    deaths over the cap on a turn no fallback_sacrifice anomaly names (FR-022)."""
    held = is_bot(rec) and rec.get('outcome') not in UNUSABLE
    deaths = protected_deaths(rec) if held else []
    labelled = {a.get('turn') for a in rec.get('anomalies') or []
                if a.get('kind') == 'fallback_sacrifice'}
    return {'invariant': held,
            'deaths': sorted({d['charId'] for d in deaths if d.get('charId') is not None}),
            'stalls': len(rec.get('stall_events') or []) if held else 0,
            'lost': held and rec.get('outcome') == 'lost',
            'unlabelled': sum(1 for d in deaths if d.get('over_cap')
                              and d.get('turn') not in labelled)}


def regressions(frozen, now, explained=lambda key, char: None):
    """FR-022's regressions of the tuning runs `now` ({'<start>/<seed>': run_outcome}) on the
    frozen baseline's runs, as (sentence, blocking): an invariant that held when frozen and
    fails now, and more stalls than it had, each blocking; a death of a unit the frozen run
    kept alive, said with the witnessed replay's label when one explains it
    (`explained(key, charId)`: the audit's primary label, or None) and never blocking,
    explained or not (T107a, ADR 0395): one seed's death is a signal, and a bot change is
    judged by rates, crashes, stalls and cost. A stall always blocks: nothing witnesses a
    stall. A run the baseline lacks (a start added since) has nothing to regress from, and
    says so."""
    out = []
    for key in sorted(now):
        got, was = now[key], frozen.get(key)
        if was is None:
            out.append(('%s: not in the frozen baseline, nothing to compare it with' % key, False))
            continue
        if was['invariant'] and not got['invariant']:
            out.append(('%s: its invariant held when frozen and fails now' % key, True))
            continue
        for c in got['deaths']:
            if c not in was['deaths']:
                label = explained(key, c)
                out.append(('%s: %s dies, and lived when frozen; %s (a signal, not a '
                            'blocker)' % (key, hex_id(c), 'witnessed: %s' % label if label
                                          else 'unexplained'), False))
        if got['stalls'] > was['stalls']:
            out.append(('%s: %s, %d when frozen' % (key, plural(got['stalls'], 'stall'),
                                                    was['stalls']), True))
    return out


def promotion(regs, unlabelled, reproducible, complete):
    """(promoted, reasons): a candidate is promoted only with every run back with a game
    result, no blocking regression (each is deterministic: a seed plays the same every time),
    no unlabelled fallback and no reproducible held-out loss (FR-022)."""
    why = []
    if not complete:
        why.append('not every run came back with a game result')
    blocking = sum(1 for _, b in regs if b)
    for n, what in ((blocking, 'deterministic regression'), (unlabelled, 'unlabelled fallback'),
                    (reproducible, 'reproducible held-out loss')):
        if n:
            why.append(plural(n, what, what + 'es' if what.endswith('s') else None))
    return not why, why


def load_frozen(path=FROZEN):
    """The frozen baseline (ADR 0395), or None before the first freeze."""
    if not os.path.exists(path):
        return None
    with open(path) as fh:
        return json.load(fh)


def run_suite(suite, envs, simdirs, play, jobs, held_out, instrument, check=check_starts,
              kept=None, wall_limit_h=MAX_WALL_H, frozen=None, explain=None, snapshots=None,
              result=None, again=None):
    """Play the suite and say what it did, as lines to print. The tuning seeds always play,
    each run's line printed, and are judged on the frozen baseline (`frozen`, load_frozen's):
    regressions, unlabelled fallbacks and SC-003's calls on the same seeds frozen. With
    `held_out` the held-out seeds play too, said only as counts, never a start or seed: a
    held-out outcome is never shown to whoever is tuning the bot. A new held-out loss (one the
    frozen baseline did not have) is played again (`again`, `play` unless given), and one that
    loses again is reproducible. Only then is there a promotion result. `explain(rec, charId)`
    is a new death's witnessed label, or None. `snapshots(envs)` checks the snapshots
    (snapshot_check's lines and failures), handed the envs this run built. Refuses, with the
    reason, a start that no longer matches its pin or a
    job over `wall_limit_h` (SC-007), before anything runs. `envs()` builds {game: campaign
    env}. `result`, a dict, is filled with what a freeze keeps."""
    lines = []
    problems = check(suite, simdirs)
    if problems:
        return ['refused: %d pinned starts cannot be played as pinned:' % len(problems)] + \
            ['  ' + p for p in problems]
    try:
        envs = envs()   # built after the check: campaign_env raises on a missing twin
    except FileNotFoundError as err:
        return ['refused: a campaign env cannot be built: %s' % err]
    outs = {g: os.path.join(d, 'runs.jsonl') for g, d in simdirs.items()}
    sets = SEED_SETS if held_out else ('tuning',)
    tasks = suite_tasks(suite, envs, instrument, outs, sets)
    hours = suite_estimate(suite, tasks, kept or {}, jobs)
    lines.append('%d runs on %d workers: about %.2f wall-hours' % (len(tasks), jobs, hours))
    if hours > wall_limit_h:
        lines.append('refused: the estimate is over the %g wall-hours one job may take (SC-007); '
                     'split it or narrow it' % wall_limit_h)
        return lines
    per, seen, outcome, recs = {}, set(), {}, {}
    by_set = {k: {'n': 0, 'calls': 0, 'cpu': 0.0, 'wall': 0.0, 'unread': 0} for k in sets}
    for rec in play(tasks):
        st = rec.get('suite') or {}
        sid, kind = st.get('start_id'), st.get('set')
        # a worker's records come together, its bot's first: its campaign's end is the run
        # only when the bot left none (records_of)
        key = (sid, rec.get('seed'))
        if sid is None or kind not in by_set or (not is_bot(rec) and key in seen):
            continue
        seen.add(key)
        got = per.setdefault(sid, {'n': 0, 'cpu': 0.0, 'wall': 0.0, 'calls': 0, 'unread': 0,
                                   'look': collections.Counter()})
        costs = rec.get('costs') or {}
        got['look'].update(rec.get('lookahead') or {})
        o = run_outcome(rec)
        outcome[key], recs[key] = (kind, o), rec
        # SC-003's measure (ADR 0384, 2026-11-03): the AI decisions the bot asked the game for,
        # the same on every run of the same code that plays to a game result, which the clock
        # is not. A run cut short asked for fewer, so it is left out rather than read as a saving
        calls = (costs.get('game_calls') or {}).get('AiDecideMain') or 0 if o['invariant'] else 0
        for into in (got, by_set[kind]):
            into['n'] += 1
            into['cpu'] += costs.get('cpu_s') or 0.0
            into['wall'] += rec.get('wall_s') or 0.0
            into['unread'] += not o['invariant']
            into['calls'] += calls
        if kind == 'tuning':
            line = attempt_line(rec, set()) or 'attempt 1: %s (%s)' % (rec.get('outcome'),
                                                                    rec.get('why'))
            lines.append('%s seed %s: %s' % (sid, rec.get('seed'), line))
    total = {'n': 0, 'cpu': 0.0, 'wall': 0.0, 'calls': 0, 'unread': 0,
             'look': collections.Counter()}
    missing = 0
    for st in suite['starts']:
        got = per.get(st['start_id'])
        if not got:
            lines.append('%s: no run came back' % st['start_id'])
            missing += 1
            continue
        for k in total:
            total[k] += got[k]
        played = got['n'] - got['unread']
        lines.append('%s (%s chapter %d, %s): %d runs, %d AiDecideMain calls, %.1f CPU s and '
                     '%.1f wall s in all, %.1f calls and %.1f CPU s a run%s' % (
                         st['start_id'], st['game'], st['chapter'], st['label'], got['n'],
                         got['calls'], got['cpu'], got['wall'], got['calls'] / max(1, played),
                         got['cpu'] / got['n'],
                         '; %d without a game result' % got['unread'] if got['unread'] else ''))
        lines.append('  ' + lookahead_line(got['look']))
    lines.append('the suite: %d runs, %d AiDecideMain calls, %.1f CPU s and %.1f wall s of work, '
                 '%d without a game result' % (total['n'], total['calls'], total['cpu'],
                                               total['wall'], total['unread']))
    lines.append("the suite's " + lookahead_line(total['look']))
    complete = not missing and total['n'] == len(tasks) and not total['unread']

    # the tuning runs, judged on the frozen baseline (FR-022)
    tuning = {'%s/%s' % k: o for k, (kind, o) in outcome.items() if kind == 'tuning'}
    unlabelled = sum(o['unlabelled'] for _, o in outcome.values())
    regs = []
    if frozen is None:
        lines.append('regressions: none judged, there is no frozen baseline yet')
    else:
        named = {'%s/%s' % k: r for k, r in recs.items()}
        regs = regressions(frozen['tuning'], tuning,
                           lambda key, char: explain(named[key], char) if explain else None)
    for key in sorted(tuning):
        if tuning[key]['unlabelled']:
            lines.append('%s: %s (a death over the cap no fallback names)'
                         % (key, plural(tuning[key]['unlabelled'], 'unlabelled fallback')))
    held = sum(o['unlabelled'] for kind, o in outcome.values() if kind == 'held_out')
    if held:
        lines.append('the held-out runs: %s' % plural(held, 'unlabelled fallback'))
    # SC-003 on the seeds played: a run that never came back or played to no result would read
    # as a saving, so the calls are judged only on a whole set
    calls = sum(by_set[k]['calls'] for k in sets)
    over = False
    if frozen is None:
        lines.append('SC-003: not judged, there is no frozen baseline yet')
    elif missing or total['n'] != len(tasks):
        lines.append('SC-003: not judged, %d of %d runs came back' % (total['n'], len(tasks)))
    elif total['unread']:
        lines.append('SC-003: not judged, %s without a game result'
                     % plural(total['unread'], 'run'))
    else:
        base = sum(frozen['calls'][k] for k in sets)
        budget = int(base * (1 + FROZEN_MARGIN))
        over = calls > budget
        lines.append('SC-003 (%s seeds): %d AiDecideMain calls against a budget of %d (%+.1f%% '
                     'on the frozen %d): %s' % (
                         ' and '.join(k.replace('_', '-') for k in sets), calls, budget,
                         100.0 * (calls / max(1, base) - 1), base,
                         'OVER' if over else 'within'))
        if over:
            regs.append(('the suite asked for more than %d%% over the frozen calls'
                         % int(FROZEN_MARGIN * 100), True))
    # the snapshots: a fixture that loaded back to its board when it entered the manifest
    snaps_failed = []
    if snapshots is not None and suite.get('snapshots'):
        snap_lines, failed = snapshots(envs)
        lines.extend(snap_lines)
        snaps_failed = failed
        regs.extend(('snapshot %s: its invariant fails' % f, True) for f in failed)
    if frozen is not None:
        lines.append('regressions on the frozen baseline (instrument %s): %s' % (
            frozen.get('instrument'), '%d' % sum(1 for _, b in regs if b) if regs else 'none'))
        lines.extend('  ' + r for r, _ in regs)
    if not held_out:
        if result is not None:
            result.clear()
        return lines
    # held-out losses: counts only (FR-025)
    known = set((frozen or {}).get('held_out_losses') or [])
    losses = {k for k, (kind, o) in outcome.items() if kind == 'held_out' and o['lost']}
    new = [k for k in losses if held_out_tag(*k) not in known]
    reproducible = 0
    if new and frozen is not None:
        again_tasks = [t for t in tasks if t['stamp']['suite']['set'] == 'held_out'
                 and (t['stamp']['suite']['start_id'], t['seed']) in new]
        lost_again = set()
        for rec in (again or play)(again_tasks):
            if is_bot(rec) and run_outcome(rec)['lost']:
                lost_again.add((rec['suite']['start_id'], rec.get('seed')))
        reproducible = len(lost_again)
        lines.append('the held-out runs: %d of %d lost, %d of them new since the freeze; played '
                     'again, %d lost again (reproducible)%s' % (
                         len(losses), by_set['held_out']['n'], len(new), reproducible,
                         '' if reproducible == len(new) else
                         '; %d did not: the play is not deterministic' % (len(new) - reproducible)))
    else:
        lines.append('the held-out runs: %d of %d lost%s' % (
            len(losses), by_set['held_out']['n'],
            '' if frozen is None else ', none new since the freeze'))
    if frozen is not None:
        ok, why = promotion(regs, unlabelled, reproducible, complete)
        lines.append('promotion: %s' % ('PROMOTED' if ok else 'refused, ' + '; '.join(why)))
    if result is not None:
        result.clear()
        if complete:
            result.update({
                'tuning': tuning,
                'held_out_losses': sorted(held_out_tag(*k) for k in losses),
                'calls': {k: by_set[k]['calls'] for k in sets},
                'cpu_s': {k: round(by_set[k]['cpu'], 1) for k in sets},
                'wall_s': {k: round(by_set[k]['wall'], 1) for k in sets},
                'snapshots_failed': snaps_failed,
                # the first freeze has no regression to judge, but a fallback no label names
                # is still never frozen as the reference
                'promoted': promotion([] if frozen is None else regs, unlabelled,
                                      reproducible, complete)[0]})
    return lines


PINNED = 'PINNED'


def snapshot_check(suite, envs, instrument, launch=launch, run_root=None, jobs=8):
    """Each snapshot's invariant, `pinned_board`: its kept state, loaded in a fresh emulator
    (PT_PINNED, botrun.lua's check_pinned), holds the board its decision read, the board file
    kept beside it when the replay pinned it (ADR 0392's in-run reload, made from outside the
    run). Booted from its start's own task (start_task's); nothing is played. The checks run
    side by side, at most `jobs` emulators at once (the suite's own --jobs), and each run dir
    is settled on this thread, as Pool settles its own. (lines, failed snapshot ids), in
    manifest order."""
    snaps = suite.get('snapshots') or []

    def one(sn):
        task = start_task(suite, envs, instrument, sn['start_id'], 'tuning')
        task['pinned'] = os.path.join(REPO, sn['state_path'])
        text, where = launch_tagged(task, 'pinned', os.path.join(REPO, 'build', 'suite-workers'),
                                    launch)
        got = parse_lines(text, PINNED)
        with open(os.path.join(REPO, sn['board_path'])) as fh:
            want = json.load(fh)
        ok = bool(got) and got[-1].get('board') == want
        return ok, where, 'snapshot %s (%s, decision %s, %s): %s' % (
            sn['snapshot_id'], sn['start_id'], sn['provenance']['ref'], sn['provenance']['mode'],
            'loads back to its board' if ok else
            'printed no PINNED line' if not got else 'loads to a board other than its own')
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(jobs, len(snaps)))) as ex:
        done = list(ex.map(one, snaps))
    for ok, where, _ in done:
        settle_run_dir(where, ok, run_root)
    return ([line for _, _, line in done],
            [sn['snapshot_id'] for sn, (ok, _, _) in zip(snaps, done) if not ok])


def suite_setup():
    """(suite, simdirs, envs) to play suite starts from, or a refusal: each game plays from its
    own store, named by the ROM built now. `envs()` builds {game: campaign env}."""
    import campaign_env
    if os.environ.get('PT_SIMDIR'):
        return ('refused: PT_SIMDIR is set; the suite plays each game from its own store, named '
                "by the ROM built now (run.sh's simdir)")
    suite = load_suite()
    simdirs = {'vanilla': simdir(True), 'ours': simdir(False)}

    def envs():
        return {'vanilla': campaign_env.vanilla_env(suite['route']),
                'ours': campaign_env.ours_env([os.path.join(REPO, p)
                                               for p in suite['shops_from']])}
    return suite, simdirs, envs


def pinned_setup(start_ids, game):
    """suite_setup's (suite, simdirs, envs) with the named starts (a suite start, or a cell
    start: start_by_id) as the suite's `starts`, or the refusal to print: an unknown start, or
    `unplayable`'s. What `replay` checks before it plays."""
    setup = suite_setup()
    if isinstance(setup, str):
        return setup
    suite, simdirs, envs = setup
    try:
        starts = [start_by_id(suite, simdirs, sid, game) for sid in start_ids]
    except ValueError as err:
        return 'refused: %s' % err
    setup = (dict(suite, starts=starts), simdirs, envs)
    return unplayable(suite, simdirs, starts) or setup


def unplayable(suite, simdirs, starts):
    """The refusal to print when check_starts finds any of `starts` cannot be played as
    pinned (the shops store, the emulator, each start's ROM and state), else None. No snapshot
    is checked: a cell or a replay plays a start's state and loads none; `suite` checks them."""
    problems = check_starts(dict(suite, starts=starts, snapshots=[]), simdirs)
    if problems:
        return '\n'.join(['refused: %d pinned starts cannot be played as pinned:'
                          % len(problems)] + ['  ' + p for p in problems])
    return None


# ---- a chapter cell's starts (#510 step 9, T100e) ----
# A cell's pairs are spread over several chapter starts, each from its own New Game campaign
# (its own dice, its own party), so a verdict is not one save's. `starts` plays the campaigns
# and pins what each left in its game's store: a store is one ROM, so a Manchego Stars ROM
# change is a new store with no starts until they are remade, and the cell says how.
STARTS_FILE = 'cell-starts.json'
STARTS_PREFIX = 'cs'   # a starts campaign is cs-s<seed> in its game's store
GAME_NAMES = {'ours': 'Manchego Stars', 'vanilla': 'vanilla'}   # how a sentence names a game
CELL_STARTS = 10   # starts an arm for a verdict to trust; a cell being tried may ask fewer


def cell_pins(store):
    """The campaigns `starts` pinned in one game's store, by seed: [{campaign, seed, outcome,
    why, chapters: {chapter index: its start state's sha1}}]; [] when it has none."""
    path = os.path.join(store, STARTS_FILE)
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        return sorted(json.load(fh)['campaigns'], key=lambda c: c['seed'])


def write_pins(store, pins):
    """Write the store's pins whole (a rename, so a kill leaves the old file or the new)."""
    path = os.path.join(store, STARTS_FILE)
    with open(path + '.tmp', 'w') as fh:
        json.dump({'campaigns': sorted(pins, key=lambda c: c['seed'])}, fh, indent=1,
                  sort_keys=True)
    os.replace(path + '.tmp', path)


def pin_of(store, campaign, seed, end):
    """What campaign `campaign` (seed `seed`) left in `store`: each chapter-start state it
    saved, by its sha1, and how it ended (`end`, its CAMPAIGN or crash record)."""
    d = os.path.join(store, 'states', campaign)
    names = os.listdir(d) if os.path.isdir(d) else []
    return {'campaign': campaign, 'seed': seed, 'outcome': end.get('outcome'),
            'why': end.get('why'),
            'chapters': {n[:-3]: sha1_file(os.path.join(d, n)) for n in sorted(names)
                         if n.endswith('.ss') and n[:-3].isdigit()}}


def cell_start(suite, store, game, pin, chapter):
    """Pinned campaign `pin`'s start at chapter index `chapter` as a pinned start in the
    suite's shape (check_starts and chapter_tasks read it), or None when it never got there."""
    sha = pin['chapters'].get(str(chapter))
    if sha is None:
        return None
    return {'start_id': '%s/%d' % (pin['campaign'], chapter), 'game': game, 'chapter': chapter,
            'rom_hash': os.path.basename(store),
            'state_path': os.path.relpath(
                os.path.join(store, 'states', pin['campaign'], '%d.ss' % chapter), REPO),
            'state_sha1': sha, 'estimate_wall_s': suite['defaults']['estimate_wall_s'],
            'provenance': {'campaign': pin['campaign'], 'seed': pin['seed']}}


def start_by_id(suite, simdirs, start_id, game):
    """The suite's start `start_id`, or the cell start it names (`<campaign>/<chapter>`) in
    game `game`'s store: what a record's `suite.start_id` and `game` say it was played from.
    Both games name their starts campaigns alike, so the game picks the store. ValueError
    when there is no such start."""
    if '/' not in start_id:
        return start_of(suite, start_id)
    campaign, chapter = start_id.rsplit('/', 1)
    pin = next((c for c in cell_pins(simdirs[game]) if c['campaign'] == campaign), None)
    st = pin and chapter.isdigit() and cell_start(suite, simdirs[game], game, pin, int(chapter))
    if not st:
        raise ValueError('montecarlo: no suite start or pinned %s cell start %s'
                         % (game, start_id))
    return st


def cell_starts(suite, store, game, chapter, k):
    """The first `k` campaigns pinned in `store` (by seed) that reached chapter index
    `chapter`, each as a pinned start in the suite's shape (check_starts and chapter_tasks
    read it). ValueError, with the count and the command that makes more, when fewer did."""
    got = []
    for pin in cell_pins(store):
        st = cell_start(suite, store, game, pin, chapter)
        if st:
            got.append(st)
        if len(got) == k:
            return got
    raise ValueError('%d %s campaigns pinned in %s reached chapter index %d, and the cell asks '
                     'for %d: make more with `montecarlo.py starts --game %s --count N`'
                     % (len(got), game, store, chapter, k, game))


def cell_setup(number, k):
    """(suite, simdirs, envs, {arm: [cell start]}) for a chapter cell of Manchego Stars
    chapter `number` and its twin on `k` starts an arm, or the refusal to print: not a written
    chapter, fewer than `k` pinned campaigns reached it in an arm, or what check_starts finds
    wrong with the starts dealt (the shops store, the emulator, each start's ROM and state)."""
    import campaign_env
    if k < 1:
        return 'refused: --starts %d: a cell needs a start an arm' % k
    setup = suite_setup()
    if isinstance(setup, str):
        return setup
    suite, simdirs, envs = setup
    pair = campaign_env.cell_chapters().get(number)
    if pair is None:
        return 'refused: chapter %d is not a written chapter of Manchego Stars' % number
    try:
        starts = {arm: cell_starts(suite, simdirs[arm], arm, index, k)
                  for arm, index in zip(('ours', 'vanilla'), pair)}
    except ValueError as err:
        return 'refused: %s' % err
    return unplayable(suite, simdirs, starts['ours'] + starts['vanilla']) or \
        (suite, simdirs, envs, starts)


def starts_main(args, pool=None):
    """`starts`: play the campaigns a chapter cell's starts come from (T100e) on the first
    `--count` seeds of the `starts` set that this store has not pinned yet, and pin what each
    left as its worker ends, so a kill keeps every campaign already finished."""
    import campaign_env
    setup = suite_setup()
    if isinstance(setup, str):
        print(setup)
        return 1
    suite, simdirs, envs = setup
    store, vanilla = simdirs[args.game], args.game == 'vanilla'
    if not os.path.basename(store):
        print('refused: no %s ROM is built' % args.game)
        return 1
    lo, hi = suite['seed_sets']['starts']
    if args.count < 1 or lo + args.count - 1 > hi:
        print('refused: --count %d: the starts seed set holds %d' % (args.count, hi - lo + 1))
        return 1
    pins = {c['seed']: c for c in cell_pins(store)}
    todo = [s for s in range(lo, lo + args.count) if s not in pins]
    index = {n: pair[1 if vanilla else 0] for n, pair in campaign_env.cell_chapters().items()}
    last = max(index.values())
    print('%d %s campaigns pinned, %d to play to chapter index %d\'s start on %d workers'
          % (len(pins), args.game, len(todo), last, args.jobs), flush=True)
    # a seed played again starts clean: states an earlier, killed play left would be pinned
    # as starts this play never reached (api.save only overwrites)
    for s in todo:
        shutil.rmtree(os.path.join(store, 'states', campaign_id(STARTS_PREFIX, s)),
                      ignore_errors=True)
    os.makedirs(store, exist_ok=True)
    pool = pool or Pool(jobs=args.jobs, out=os.path.join(store, 'runs.jsonl'))
    # each campaign stops once the last chapter's start is saved: no cell plays past it
    env = dict(envs()[args.game], last=[last], start_only=last)
    crashed = 0
    for rec in pool.run(campaign_tasks(env, todo, None, {'cell_starts': True}, vanilla,
                                     STARTS_PREFIX)):
        if rec.get('chapter') is not None:
            continue   # an attempt; the record with no chapter says how the campaign ended
        seed = rec['seed']
        if rec.get('outcome') == 'crashed':
            # the harness failing, never the bot (campaign.lua): left unpinned, so the next
            # `starts` plays the seed again rather than spend it on a crash
            crashed += 1
            print('  %s: crashed, not pinned (%s; %s)' % (campaign_id(STARTS_PREFIX, seed),
                                                         rec.get('why'),
                                                             rec.get('run_dir') or rec.get('log')),
                  flush=True)
            continue
        pins[seed] = pin_of(store, campaign_id(STARTS_PREFIX, seed), seed, rec)
        write_pins(store, pins.values())
        print('  %s: %s (%s), %d chapter starts' % (campaign_id(STARTS_PREFIX, seed),
                                                   rec.get('outcome'),
                                                       rec.get('why'),
                                                       len(pins[seed]['chapters'])),
              flush=True)
    for number in sorted(index):
        n = sum(1 for c in pins.values() if str(index[number]) in c['chapters'])
        print('ch%02d (index %d): %d of %d pinned campaigns reached its start'
              % (number, index[number], n, len(pins)))
    if crashed:
        print('%d campaigns crashed: run `starts` again to play them' % crashed)
    return 1 if crashed else 0


def kept_play(paths, instrument, rom_hashes):
    """A `play` that plays nothing: each task's newest kept suite run of this instrument on
    these ROMs ({game: hash}), so a suite is judged again without playing it: after a replay
    witnessed why a new death happened, to say its label (its DIAG lines name that run's
    trace, and a fresh run's trace is new; the death never blocks either way, T107a), or to
    freeze the runs already judged."""
    runs = kept(paths, suite_run_of(instrument, rom_hashes),
                lambda r: (r['suite']['start_id'], r['suite']['set'], r.get('seed')))

    def play(tasks):
        for t in tasks:
            st = t['stamp']['suite']
            got = runs.get((st['start_id'], st['set'], t['seed']))
            if got:
                yield got[-1]
    return play


def store_explain(simdirs):
    """`explain(rec, charId)` for run_suite: the audit's primary label of that death, from the
    DIAG lines in the run's store (diag.jsonl, `replay`'s), or None."""
    diags = {game: load_diag(os.path.join(d, 'diag.jsonl'))
             if os.path.exists(os.path.join(d, 'diag.jsonl')) else []
             for game, d in simdirs.items()}

    def explain(rec, char):
        base = simdirs[rec.get('game')]
        for f in audit([rec], diags.get(rec.get('game')) or [],
                       lambda r: record_events(r, base)):
            if f['death'].get('charId') == char and f['primary']:
                return f['primary']
        return None
    return explain


def freeze_record(result, instrument, version, today=None, override=None):
    """What `suite --freeze` writes (FROZEN): the run's result stamped with its instrument,
    the manifest's version and the day. None, with why, when the run may not be frozen.
    `override`, Nicolas's reason, freezes a candidate the promotion refused, and is kept in the
    file whenever it is given, promoted or not, so a reason he gave is never dropped (ADR 0395):
    a refusal can be his call to accept, an incomplete run or a broken snapshot never."""
    if not result:
        return None, 'not every run came back with a game result'
    if result['snapshots_failed']:
        return None, 'snapshot %s fails its invariant' % ', '.join(result['snapshots_failed'])
    if not result['promoted'] and not override:
        return None, 'the candidate is not promoted'
    rec = {k: v for k, v in result.items() if k not in ('promoted', 'snapshots_failed')}
    if override:
        rec['override'] = override
    rec.update(instrument=instrument, manifest_version=version,
               frozen_on=today or time.strftime('%Y-%m-%d'))
    return rec, None


def suite_main(args):
    if args.override and not args.freeze:
        print('--override only goes with --freeze')
        return 2
    setup = suite_setup()
    if isinstance(setup, str):
        print(setup)
        return 1
    suite, simdirs, envs = setup
    outs = [os.path.join(d, 'runs.jsonl') for d in simdirs.values()]
    pool = Pool(jobs=args.jobs, out=outs[0])
    hashes = {g: os.path.basename(d) for g, d in simdirs.items()}
    inst = instrument_id()
    play = kept_play(outs, inst, hashes) if args.kept else pool.run
    result = {}
    lines = run_suite(suite, envs, simdirs, play, args.jobs, args.held_out or args.freeze, inst,
                      kept=kept_walls(outs, inst, hashes), frozen=load_frozen(),
                      explain=store_explain(simdirs), result=result, again=pool.run,
                      snapshots=lambda built: snapshot_check(suite, built, inst,
                                                             jobs=args.jobs))
    for line in lines:
        print(line, flush=True)
    if any(line.startswith('refused') for line in lines):
        return 1
    if args.freeze:
        rec, why = freeze_record(result, inst, suite['version'], override=args.override)
        if rec is None:
            print('not frozen: %s' % why)
            return 1
        with open(FROZEN, 'w') as fh:
            json.dump(rec, fh, indent=1, sort_keys=True)
            fh.write('\n')
        print('frozen: %s (instrument %s)%s' % (
            os.path.relpath(FROZEN, REPO), inst,
            ', override: %s' % rec['override'] if 'override' in rec else ''))
    return 0


# ---- a diagnostic replay of one death (#510 step 9 PR-F, T074; ADR 0392) ----

# A run, by the name a person types (`replay --record`), and by its identity: its filed trace
# (keep_trace's name is unique). The suite reruns a start under every instrument, so a name is
# never unique in a store and only the trace tells those runs apart.
RUN_NAME = ('campaign', 'seed', 'chapter', 'attempt')


def run_name(r):
    """Run `r`'s name, '<campaign>/<seed>/<chapter>/<attempt>'."""
    return '/'.join(str(r.get(k)) for k in RUN_NAME)


def run_key(r):
    """Run `r`'s identity (a record, or a DIAG line's `run`): its filed trace."""
    return r.get('trace')


def record_events(rec, base):
    """Record `rec`'s trace events, its trace filed relative to `base` (keep_trace's), or []
    when it has none."""
    path = rec.get('trace') and os.path.join(base, rec['trace'])
    return read_trace(path) if path and os.path.exists(path) else []


def find_record(records, spec, trace=None):
    """The BOTRUN record of `records` that `spec` names (run_name): the one whose filed trace
    is `trace`, else the newest (the last in the file)."""
    if len(spec.split('/')) != len(RUN_NAME):
        raise ValueError('a record is <campaign>/<seed>/<chapter>/<attempt>, not %r' % spec)
    got = [r for r in bot_records(records) if run_name(r) == spec
           and (trace is None or run_key(r) == trace)]
    if not got:
        raise ValueError('no record is %s%s' % (spec, ' with trace %s' % trace if trace else ''))
    return got[-1]


def moved_ref(events, d):
    """The last decision (a plan's `ref`) whose act moved death `d`'s unit before it fell, from
    the run's trace `events`, or None. A kept act is played under the plan that made it, so a
    plan event without a ref keeps the one before. The death's own `plan_ref` is the plan that
    committed to the phase it fell in, which need not move it at all."""
    cur = last = None
    for e in events:
        if any(f.get('charId') == d.get('charId') for f in e.get('fell') or []):
            break
        if e.get('t') == 'plan' and e.get('ref') is not None:
            cur = e['ref']
        elif (e.get('t') == 'act' and e.get('phase') == 'player'
              and e.get('unit') == d.get('charId')):
            last = cur
    return last


def replay_diag(rec, mode, force=None, char=None, ref=None, base='.', events=(),
                instrument=None):
    """PT_DIAG for one diagnostic replay of a death of suite run `rec` (whose trace is filed
    relative to `base`): the decision to pin, the mode, the forced plan, the death, the
    original trace and the run. Without `ref`, the decision is the last that moved the unit in
    the original trace `events` (moved_ref), else the death's plan_ref; `ref_from` says which
    ('asked', 'act' or 'plan_ref'). Raises ValueError, saying why, on a replay it cannot make:
    a run not of the suite (a campaign's chapter is reached through every chapter before it),
    a held-out run (FR-025: held-out play stays unseen while the bot is being tuned), a run of
    another instrument than `instrument` (the code playing now: a newer planner would play the
    diagnostic, and its witness count toward the old one), or a death, decision or plan it
    cannot name."""
    suite = rec.get('suite') or {}
    if not suite.get('start_id'):
        raise ValueError('not a suite run: only a pinned start replays to a decision')
    if suite.get('set') == 'held_out':
        raise ValueError('a held-out run is never replayed while the bot is tuned (FR-025)')
    if instrument is not None and rec.get('instrument') != instrument:
        raise ValueError('that run is of instrument %s, and the code now is %s'
                         % (rec.get('instrument'), instrument))
    deaths = [d for d in rec.get('deaths') or [] if char is None or d.get('charId') == char]
    if not deaths:
        raise ValueError('no death of %s in that run' % hex_id(char) if char is not None
                         else 'that run has no death')
    if len(deaths) > 1:
        raise ValueError('%d deaths in that run: name one with --char' % len(deaths))
    if (mode == 'force') != bool(force):
        raise ValueError('force needs --force' if mode == 'force'
                         else '--force goes only with force')
    if not rec.get('trace'):
        raise ValueError('that run has no kept trace to match the replay against')
    d = deaths[0]
    ref_from = 'asked'
    if ref is None:
        ref = moved_ref(events, d)
        ref_from = 'act'
    if ref is None:
        ref, ref_from = d.get('plan_ref'), 'plan_ref'
    if ref is None:   # a greedy phase's death: no plan committed to it, none moved the unit
        raise ValueError('no decision to pin: no plan moved %s or committed to its death'
                         % hex_id(d['charId']))
    return {'ref': ref, 'ref_from': ref_from, 'mode': mode,
            'force': list(force) if force else None,
            'failure': {'charId': d['charId'], 'turn': d.get('turn')},
            'original_trace': os.path.join(base, rec['trace']),
            'run': dict({k: rec.get(k) for k in RUN_NAME}, game=rec.get('game'),
                        trace=run_key(rec))}


def start_task(suite, envs, instrument, sid, kind, seed=None):
    """Start `sid`'s suite task (suite_tasks': its start, instrument and seed in set `kind`;
    the set's first when `seed` is None) without the runs file and stamp a record would take:
    a replay or a snapshot's check leaves none. None when the suite has no such start or seed."""
    one = dict(suite, starts=[s for s in suite['starts'] if s['start_id'] == sid])
    tasks = [t for t in suite_tasks(one, envs, instrument, {}, (kind,))
             if seed is None or t['seed'] == seed]
    if not tasks:
        return None
    task = tasks[0]
    for k in ('out', 'stamp'):
        task.pop(k, None)
    return task


def launch_tagged(task, prefix, log_dir, launch=launch):
    """One launch of `task` outside a Pool, under a tag of its own (unique_tag's), its log in
    `log_dir`. Returns launch's (stdout, run dir)."""
    os.makedirs(log_dir, exist_ok=True)
    tag = unique_tag(prefix)
    return launch(task, tag, os.path.join(log_dir, tag + '.log'))


def replay_task(rec, suite, envs, diag, instrument):
    """Suite run `rec`'s own task (start_task's) with `diag`. Raises ValueError when the
    suite no longer has that start or seed."""
    sid, kind = rec['suite']['start_id'], rec['suite']['set']
    task = start_task(suite, envs, instrument, sid, kind, rec.get('seed'))
    if task is None:
        raise ValueError('%s seed %s of %s is no longer in the suite'
                         % (kind, rec.get('seed'), sid))
    task['diag'] = diag
    return task


def replay_run(task, base, launch=launch, run_root=None):
    """Play one replay; append its DIAG lines to `base`/diag.jsonl, each replay trace filed
    beside the runs file (keep_trace) and named relative to it. Its BOTRUN line, if any, is
    dropped: a diagnostic feeds no record (FR-019). A replay that printed no DIAG line keeps
    its run dir as a failure."""
    out = os.path.join(base, 'diag.jsonl')
    text, where = launch_tagged(task, 'diag', os.path.join(base, 'workers'), launch)
    diags = parse_lines(text, DIAG)
    for g in diags:
        run = g.get('run') or {}
        kept = {'trace': g.get('trace'), 'run_dir': where, 'campaign': 'diag',
                'chapter': run.get('chapter'), 'seed': run.get('seed'),
                'attempt': '%s-%s' % (run.get('attempt'), g.get('mode'))}
        keep_trace(kept, out)
        g['trace'] = kept.get('trace')
        # the state at the pinned decision (harness.lua's api.pinned) is a board fixture
        # (T084): filed beside the trace before the run dir goes, and named in the line
        names = os.listdir(where) if where and os.path.isdir(where) else []
        pinned = [n for n in names if n.startswith('pinned-')
                  and n.endswith('-r%s.ss' % g.get('ref'))]
        for name in pinned[:1]:
            rel = os.path.join('traces', 'diag', '%s-%s' % (uuid.uuid4().hex[:8], name))
            os.makedirs(os.path.join(base, 'traces', 'diag'), exist_ok=True)
            shutil.copyfile(os.path.join(where, name), os.path.join(base, rel))
            g['pinned'] = rel
            # the board its decision read, kept beside it: a snapshot's check (PR-G T084)
            board = os.path.join(where, name[:-len('.ss')] + '.json')
            if os.path.exists(board):
                shutil.copyfile(board, os.path.join(base, rel[:-len('.ss')] + '.json'))
                g['pinned_board_file'] = rel[:-len('.ss')] + '.json'
        append_record(out, g, DIAG)
    settle_run_dir(where, bool(diags), run_root)
    return diags


def replay_main(args):
    base = os.path.dirname(os.path.abspath(args.runs))
    try:
        rec = find_record(read_trace(args.runs), args.record, args.trace)
        print('replaying the run filed as %s' % rec.get('trace'))
        diag = replay_diag(rec, args.mode, args.force,
                           None if args.char is None else int(args.char, 0), args.ref, base,
                           record_events(rec, base), instrument_id())
        print('pinned at decision %s (%s)' % (diag['ref'], {
            'asked': '--ref', 'act': 'the last that moved the unit',
            'plan_ref': "nothing moved the unit: the death's plan_ref"}[diag['ref_from']]))
    except ValueError as err:
        print('refused: %s' % err)
        return 1
    setup = pinned_setup([rec['suite']['start_id']], rec.get('game'))
    if isinstance(setup, str):
        print(setup)
        return 1
    suite, simdirs, envs = setup
    try:
        task = replay_task(rec, suite, envs(), diag, instrument_id())
    except ValueError as err:
        print('refused: %s' % err)
        return 1
    for g in replay_run(task, base) or [None]:
        print('DIAG %s' % json.dumps(g) if g else 'the replay printed no DIAG line')
    return 0


# ---- one run, told (PR F3) ----

@functools.lru_cache(maxsize=None)
def _names(game):
    """{character id: name}: every character by its decomp enum (vanilla's cast and the generic
    enemies); for Manchego Stars, then every pid the build renamed by the name the ROM prints for
    it (`inject.text.character_names` on the build tree: a chapter unit on a reused vanilla slot,
    which printed the vanilla name before; ch02's Rime Spark rode KLIMT and read "Klimt", #590);
    then the cast by its PCs' and guests' names, last, because a scene-only guest's slot keeps
    its vanilla nameplate (Duvessa rides SELENA) and the cast lookup is the one claims use."""
    sys.path.insert(0, os.path.dirname(HERE))
    import inject.decomp
    import inject.text
    from inject.scene_actors import cast_pids
    text = inject.decomp.vanilla_decomp_text('include/constants/characters.h')
    out = {v: k[len('CHARACTER_'):].replace('_', ' ').title()
           for k, v in inject.decomp.enum_values(text, 'CHARACTER_').items()}
    if game == 'ours':
        vanilla = inject.text.character_names(inject.decomp.vanilla_decomp_text)
        out.update((pid, name) for pid, name
                   in inject.text.character_names(inject.decomp.rom_text).items()
                   if name != vanilla.get(pid))
        for name, pid in cast_pids().items():
            out[pid] = name.replace('-', ' ').title()
    return out


def names_note(game, rom_hashes):
    """The line a story or audit prints when its Manchego Stars names may not be the run's: they
    come from the build tree's sources (`_names`), and the run played the ROM its record names.
    None only when every run names the ROM built now and the sources the names come from are no
    newer than it (an injection rewrites them before the ROM is rebuilt, and `git checkout`
    resets them to vanilla). A run with no `rom_hash` cannot be matched, so it counts as another."""
    if game != 'ours':
        return None
    import matrix
    rom = matrix.ROM_PATH
    built = sha1_file(rom) if os.path.isfile(rom) else None
    others = sorted({h or 'unrecorded' for h in rom_hashes
                     if not (built and h and built.startswith(h))})
    sources = [os.path.join(os.path.dirname(rom), rel) for rel in NAME_SOURCES]
    stale = built is not None and any(
        os.path.isfile(p) and os.path.getmtime(p) > os.path.getmtime(rom) for p in sources)
    if built and not others and not stale:
        return None
    where = ('vanilla (no ROM is built)' if not built else
             'the build tree, changed since its ROM %s was built' % built[:12] if stale else
             'the build tree (ROM %s)' % built[:12])
    return ('note: chapter-unit names are read from %s; the run played ROM %s, so a name may '
            'not be the one that ROM showed (build that ROM to read its names)'
            % (where, ', '.join(others) or built[:12]))


# The build-tree files `_names` reads through `inject.text.character_names`.
NAME_SOURCES = ('src/data_characters.c', 'texts/texts.txt', 'include/constants/characters.h')


@functools.lru_cache(maxsize=None)
def _items():
    sys.path.insert(0, os.path.dirname(HERE))
    import inject.decomp
    text = inject.decomp.vanilla_decomp_text('include/constants/items.h')
    return {v: k[len('ITEM_'):].replace('_', ' ').title()
            for k, v in inject.decomp.enum_values(text, 'ITEM_').items()}


@functools.lru_cache(maxsize=None)
def _classes(game='vanilla'):
    """{class id: name}: every vanilla class by FE8's name, and for Manchego Stars each enemy reskin
    by its own (campaign.yaml), on the slot it takes."""
    sys.path.insert(0, os.path.dirname(HERE))
    from inject import class_ids, reskins
    import campaign_env
    out = {v: class_ids.class_display_name(k[len('CLASS_'):])
           for k, v in class_ids.vanilla_class_values().items()}
    if game == 'ours':
        for rk in reskins.enemy_class_reskins(campaign_env.campaign_chapters.CAMPAIGN):
            out[reskins.reskin_class_id(rk)] = class_ids.class_display_name(rk['id'])
    return out


VERBS = {'attack': 'attacks', 'wait': 'waits', 'staff': 'uses a staff on', 'talk': 'talks to',
         'door': 'opens a door', 'seize': 'seizes', 'item': 'uses an item', 'moves': 'moves',
         'steal': 'steals from', 'visit': 'visits a village', 'chest': 'opens a chest',
         'pick': 'pillages', 'rescue': 'rescues', 'drop': 'drops'}


def read_trace(path):
    opener = gzip.open if path.endswith('.gz') else open
    with opener(path, 'rt') as fh:
        return [json.loads(line) for line in fh if line.strip()]


def story(events, names=None, items=None, classes=None):
    """One run's trace as plain lines. `names`/`items`/`classes`: {id: name}. A unit without a
    name of its own is named by its class (from the phase snapshots and battles), then by id."""
    names, items, classes = names or {}, items or {}, classes or {}
    cls = {}   # character id -> class id, as the trace saw it
    char = {}  # unit index -> character id, from the phase snapshots

    def who(cid):
        if cid is None:
            return 'someone'
        if cid in names:
            return names[cid]
        c = cls.get(cid)
        if c is not None:
            return 'the %s' % classes.get(c, 'class 0x%02X' % c)
        return 'unit %s' % hex_id(cid)

    def item(iid):
        return items.get(iid) or ('item 0x%02X' % iid)

    def blows(b):
        a, t = b['actor'], b['target']
        side = {'actor': a, 'target': t}
        other = {'actor': t, 'target': a}
        back = ('%s hit %d%% crit %d%%' % (who(t['charId']), t['hit'], max(t['crit'], 0))
                if t.get('canCounter', True) else '%s cannot strike back' % who(t['charId']))
        head = '    forecast: %s hit %d%% crit %d%% with %s; %s' % (
            who(a['charId']), a['hit'], max(a['crit'], 0), item(a['weapon']), back)
        out = [head]
        for h in b['hits']:
            by, on = side[h['by']], other[h['by']]
            if h['miss']:
                out.append('    %s misses' % who(by['charId']))
            else:
                out.append('    %s hits %s for %d%s' % (who(by['charId']), who(on['charId']),
                                                      h['dmg'], ', a critical' if h['crit'] else ''))
        out.append('    after: %s %d -> %d HP, %s %d -> %d HP' % (
            who(a['charId']), a['hpBefore'], a['hp'], who(t['charId']), t['hpBefore'], t['hp']))
        for s in (a, t):
            if s.get('levelUp'):
                out.append('    %s gains a level' % who(s['charId']))
            if s.get('broke'):
                out.append("    %s's weapon breaks" % who(s['charId']))
        return out

    lines = []
    for e in events:
        t = e.get('t')
        for u in e.get('units') or []:
            if u.get('id') is not None:
                char[u['id']] = u['charId']
            if u.get('classId') is not None:
                cls[u['charId']] = u['classId']
        for b in e.get('battles') or []:
            for side in (b or {}).get('actor'), (b or {}).get('target'):
                if side and side.get('classId') is not None:
                    cls.setdefault(side['charId'], side['classId'])
        if t == 'start':
            info, st = e.get('info') or {}, e.get('style') or {}
            lines.append('%s, chapter %s, %s, seed %s, attempt %s: plays %s, following %d claims'
                         % (info.get('game'), info.get('chapter'), info.get('mode'),
                            info.get('seed'), info.get('attempt') or 1, st.get('aggression'),
                            len(e.get('claims_played') or [])))
        elif t == 'phase':
            lines.append('Turn %s, %s phase.' % (e.get('turn'), e.get('phase')))
        elif t == 'plan' and (e.get('replan') or e.get('worth')):
            if e.get('replan'):
                lines.append('  (the board was not what the plan expected: %s; a new plan)'
                             % e['replan'])
            # what the plan does to each goal it moves (planner.lua's goalWorth)
            for g in e.get('worth') or []:
                if abs(g['after'] - g['before']) >= 0.005:
                    lines.append('  goal %s (worth %.0f): chance %.2f -> %.2f'
                                 % (g['id'], g['worth'], g['before'], g['after']))
        elif t == 'act':
            act = e.get('act') or ('attacks' if e.get('battles') else 'moves')
            act = VERBS.get(act, act)
            fr, to = e.get('from') or {}, e.get('to') or {}
            moved = ('from %s,%s to %s,%s' % (fr.get('x'), fr.get('y'), to.get('x'), to.get('y'))
                     if fr != to else 'at %s,%s' % (to.get('x'), to.get('y')))
            target = ''
            if e.get('target') is not None:
                target = ' %s' % who(e['target'])
            elif e.get('tile'):
                target = ' the tile at %s,%s' % (e['tile']['x'], e['tile']['y'])
            elif e.get('battles') and e['battles'][0]:
                target = ' %s' % who(e['battles'][0]['target']['charId'])
            elif e.get('targetId') in char:
                target = ' %s' % who(char[e['targetId']])
            lines.append('  %s %s%s, %s.' % (who(e.get('unit')), act, target, moved))
            for b in e.get('battles') or []:
                if b:
                    lines.extend(blows(b))
            for f in e.get('fell') or []:
                lines.append('  %s falls%s.' % (who(f.get('charId')), (' to %s' % who(f['killer']))
                                                if f.get('killer') is not None else ''))
        elif t == 'fell':
            for f in e.get('fell') or []:
                lines.append('  %s falls%s.' % (who(f.get('charId')), (' to %s' % who(f['killer']))
                                                if f.get('killer') is not None else ''))
        elif t == 'event':
            k = e.get('kind')
            if k == 'arrive':
                lines.append('  %s arrives at %s,%s (%s).' % (who(e.get('charId')), e.get('x'),
                                                             e.get('y'), e.get('faction')))
            elif k == 'recruit':
                lines.append('  %s joins (was %s).' % (who(e.get('charId')), e.get('from')))
            elif k == 'items':
                ch = ['gains %s' % item(i) for i in e.get('gained') or []] + \
                     ['loses %s' % item(i) for i in e.get('lost') or []]
                lines.append('  %s %s.' % (who(e.get('charId')), ', '.join(ch)))
        elif t == 'end':
            r = e.get('record') or {}
            why = spoiled(r, who)
            lines.append('Result: %s on turn %s%s.' % (
                r.get('outcome'), r.get('turns'), ', clean' if r.get('clean') is True
                else (', not clean: ' + why if why else '')))
    return lines


# ---- the failure audit (#510 step 9 PR-F, FR-019, FR-020, SC-004; ADR 0392) ----

DIAG = 'DIAG'
# The labels a witness can support, in the order the primary one is picked: a defect the bot
# owns (it never offered the plan, misjudged its risk, misranked it) before a limit of its
# search, and that before what it could not have known.
AUDIT_LABELS = ('missing_action', 'mis_predicted_safety', 'mis_scored', 'search_miss',
                'information_unavailable')
# planner.lua's rejection of a judged plan (the trace's `considered`), by what it says of a forced
# plan that then lived: judged too risky, or ranked below the one played. A `stalled` plan may
# not be played at all, so it places nothing.
REJECTED_LABEL = {'over_cap': 'mis_predicted_safety', 'outranked': 'mis_scored'}
SC004_BAR = 0.9


def diag_of(g, r, d):
    """Whether DIAG line `g` replays death `d` of record `r`."""
    f = g.get('failure') or {}
    key = run_key(g.get('run') or {})
    return (key is not None and key == run_key(r) and f.get('charId') == d.get('charId')
            and f.get('turn') == d.get('turn'))


def orphans(records, diags):
    """The DIAG lines that replay no death of `records`: a stale line whose run left the
    store, or whose death the run no longer has. Never dropped: a replay that answers nothing
    the audit reads must be seen, not lost."""
    return [g for g in diags if not any(diag_of(g, r, d) for r in records
                                        for d in r.get('deaths') or [])]


def witness_label(diag, plan):
    """(label, None) for a DIAG replay that witnesses one, else (None, why not). A witness is a
    replay that matched the original up to the decision (`matched`), played a DIFFERENT plan
    (`planned`) to the end (not `broken`, no error) and kept the unit alive with no one traded
    for it. Its label: a deep or full-information replay says what that diagnostic added. A
    forced plan with an act the game did not offer on the board it was played on (the replay's
    `unoffered`) is a missing action; otherwise it is placed by what the planner recorded at the
    pinned decision (`plan`, the trace's `plan` event: its `audit`, and `considered`, every plan
    it judged), and without that record nothing is claimed."""
    mode = diag.get('mode')
    if not diag.get('matched'):
        return None, 'UNMATCHED: the %s fork did not replay the original up to decision %s' % (
            mode, diag.get('ref'))
    if 'planned' not in diag:
        # written before the replay recorded its whole plan and where it broke off: a stop at
        # the pin then read avoided, and a full-information plan could use acts only the
        # fog-off board offered (ADR 0392)
        return None, '%s: a line from before `planned` was recorded; re-run it' % mode
    if diag.get('outcome') == 'crashed':
        # the replay stopped on an error of its own after it matched: the unit fell, if it
        # did, because the run stopped, which says nothing about the plan. Every replay that
        # reached its pin ends with a `why` (outcome "diag"); only a crash is a failure
        return None, 'REPLAY FAILED: %s: %s' % (mode, diag.get('why'))
    if diag.get('broken'):
        # the replay could not play its plan to the end (`broken`, the first act not played):
        # a plan cut short is no counterfactual of the one the bot would have played
        return None, '%s: broken (%s)' % (mode, diag['broken'])
    if not diag.get('differs') or diag.get('planned') == diag.get('baseline'):
        return None, '%s: chose the same plan' % mode
    if diag.get('traded'):
        # the unit lived and another protected unit died in its place (harness.lua's `traded`):
        # the failure moved, it was not avoided
        return None, '%s: traded it for %s' % (mode, ', '.join(hex_id(c)
                                                              for c in diag['traded']))
    if not diag.get('avoided'):
        return None, '%s: did not avoid it' % mode
    if mode == 'deep':
        return 'search_miss', None
    if mode == 'full_info':
        return 'information_unavailable', None
    if diag.get('unoffered') is None:
        return None, 'force: avoided it, but the replay did not check its acts were offered ' \
            '(no `unoffered`)'
    if diag['unoffered']:
        return 'missing_action', None
    if (plan or {}).get('audit') is None:
        return None, 'force: avoided it, but the trace has no plan audit at decision %s' % (
            diag.get('ref'))
    planned = list(diag.get('planned') or [])
    for c in plan.get('considered') or []:
        if list(c.get('acts') or []) == planned:
            label = REJECTED_LABEL.get(c.get('rejected'))
            if label is None:
                return None, 'force: avoided it, but the planner judged that plan %s' % (
                    c.get('rejected') or 'the one it played')
            return label, None
    # every act was offered, and the plan was never judged: the beam or the budget cut it
    return 'search_miss', None


def audit(records, diags, events_of):
    """One finding per blue or green death of `records` (BOTRUN records): every label a DIAG
    replay of that death witnesses, the primary one, each witness, and why each other replay is
    none. `events_of(record)`: that run's trace events (read_trace), [] when it has none."""
    findings = []
    for r in bot_records(records):
        plans = None
        for d in r.get('deaths') or []:
            mine = [g for g in diags if diag_of(g, r, d)]
            if mine and plans is None:   # a trace is read only for a run a replay names
                plans = {e.get('ref'): e for e in events_of(r) if e.get('t') == 'plan'
                         and e.get('ref') is not None}
            # a replay run again (its harness made stricter, say) appends a new line: the
            # newest line of each replay -- one decision, mode and plan -- is the one that counts
            newest = {}
            for g in mine:
                newest[(g.get('ref'), g.get('mode'),
                        json.dumps(g.get('planned', g.get('chosen'))))] = g
            mine = list(newest.values())
            labels, witnesses, notes = set(), [], []
            for g in mine:
                label, why = witness_label(g, (plans or {}).get(g.get('ref')))
                if label:
                    labels.add(label)
                    witnesses.append(dict(g, label=label))
                else:
                    notes.append(why)
            ordered = [x for x in AUDIT_LABELS if x in labels]
            findings.append({'record': r, 'death': d, 'labels': ordered,
                             'primary': ordered[0] if ordered else None,
                             'witnesses': witnesses, 'notes': notes})
    return findings


def audit_lines(findings, who=hex_id):
    """The findings in words. An unclassified failure shows the run's own grading of the death
    as proposed only (AS 2): it is what the bot thought, never a witnessed label."""
    lines = []
    for f in findings:
        r, d = f['record'], f['death']
        head = '%s chapter %s, seed %s, attempt %s: %s' % (
            r.get('game'), r.get('chapter'), r.get('seed'), r.get('attempt'), death(d, who))
        if f['primary']:
            lines.append('%s -> primary %s; supported: %s' % (head, f['primary'],
                                                              ', '.join(f['labels'])))
        else:
            lines.append('%s -> unclassified (proposed: %s, not witnessed)' % (
                head, d.get('cause') or 'nothing'))
        for w in f['witnesses']:
            lines.append('    witness (%s): %s at decision %s played %s instead of %s -> '
                         'python3 tools/playtest/montecarlo.py story %s' % (
                             w['label'], w.get('mode'), w.get('ref'), w.get('chosen'),
                             w.get('baseline'), w.get('trace')))
        for n in f['notes']:
            lines.append('    no witness: %s' % n)
    return lines


def coverage(findings, instrument=None, orphaned=0):
    """SC-004's sentence for one instrument's runs: how many audited failures have a witnessed
    label, against its bar, and the DIAG lines that matched no failure (`orphaned`)."""
    n = len(findings)
    head = 'SC-004 (instrument %s): ' % instrument
    tail = ' %d orphan DIAG lines (no record matches their run).' % orphaned if orphaned else ''
    if not n:
        return head + 'no failures to audit.' + tail
    k = sum(1 for f in findings if f['primary'])
    # an unclassified failure whose replay could not reach the original's decision, or stopped
    # on an error of its own, is a fault of the replay, not an answer about the bot: counted
    # apart so it is never read as one
    def faulty(word):
        return sum(1 for f in findings if not f['primary']
                   and any(n.startswith(word) for n in f['notes']))
    lost, failed = faulty('UNMATCHED'), faulty('REPLAY FAILED')
    faults = ', '.join(x for x in ('%d with an UNMATCHED replay' % lost if lost else '',
                                   '%d with a failed replay' % failed if failed else '') if x)
    return head + ('%d of %d audited failures (%.0f%%) have a witnessed label; '
                   '%d unclassified%s. The bar is %.0f%%: %s.' % (
                       k, n, 100.0 * k / n, n - k,
                       ' (%s)' % faults if faults else '',
                       100 * SC004_BAR, 'met' if k >= SC004_BAR * n else 'not met')) + tail


def load_diag(path):
    """The DIAG lines of a log or diag file, each witness's trace made absolute: `replay`
    files it relative to its diag file."""
    with open(path) as fh:
        got = parse_lines(fh.read(), DIAG)
    for g in got:
        if g.get('trace') and not os.path.isabs(g['trace']):
            g['trace'] = os.path.join(os.path.dirname(os.path.abspath(path)), g['trace'])
    return got


def audit_main(args):
    records = read_trace(args.runs)
    base = os.path.dirname(os.path.abspath(args.runs))
    diags = [g for path in args.diag or [] for g in load_diag(path)]
    # one instrument's runs: two instruments are two bots, and one sentence over both measures
    # neither. The newest run's, as `replay` picks the newest run, unless --instrument says
    runs = bot_records(records)
    inst = args.instrument if args.instrument is not None else (
        runs[-1].get('instrument') if runs else None)
    mine = [r for r in runs if r.get('instrument') == inst]
    # a line for another instrument's run belongs to that instrument's audit
    others = {run_key(r) for r in runs if r.get('instrument') != inst}
    diags = [g for g in diags if run_key(g.get('run') or {}) not in others]
    findings = audit(mine, diags, lambda r: record_events(r, base))
    lost = orphans(mine, diags)
    game = next((r.get('game') for r in mine if r.get('game')), None) or 'vanilla'
    names = _names(game)
    note = names_note(game, [r.get('rom_hash') for r in mine])
    if note:
        print(note)
    for line in audit_lines(findings, namer(names)):
        print(line)
    for g in lost:
        print('orphan (no record matches its run): %s, failure %s, %s at decision %s' % (
            g.get('run'), g.get('failure'), g.get('mode'), g.get('ref')))
    print(coverage(findings, inst, len(lost)))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('attempts', help="a chapter's attempts 1..N side by side")
    a.add_argument('--env', required=True, help='a campaign env .json with `from`')
    a.add_argument('--attempts', type=int, required=True)
    a.add_argument('--jobs', type=int, default=4)
    a.add_argument('--out', default='runs.jsonl')
    a.add_argument('--seed', type=int, default=1)
    a.add_argument('--vanilla', action='store_true')
    st = sub.add_parser('story', help="one run's trace as plain text")
    st.add_argument('trace', help='a trace .jsonl or .jsonl.gz')
    st.add_argument('--turn', type=int, help="only this turn and the one before (an anomaly's)")
    au = sub.add_parser('audit', help="each failure's witnessed labels, from DIAG replays")
    au.add_argument('runs', help='a runs .jsonl (its records name their kept traces)')
    au.add_argument('--instrument', help="the instrument whose runs to audit (default: the "
                    "newest run's)")
    au.add_argument('--diag', action='append', help='a log or file with DIAG lines (repeatable)')
    rp = sub.add_parser('replay', help="one diagnostic replay of a suite run's death")
    rp.add_argument('runs', help='the runs .jsonl the run is in')
    rp.add_argument('--record', required=True, help='<campaign>/<seed>/<chapter>/<attempt>')
    rp.add_argument('--mode', required=True, choices=('force', 'full_info', 'deep'))
    rp.add_argument('--force', action='append',
                    help='one act key of the plan to force (repeat it, in act order)')
    rp.add_argument('--trace', help="the run's filed trace (default: the newest run so named)")
    rp.add_argument('--char', help="the dead unit's character id (default: the run's one death)")
    rp.add_argument('--ref', type=int, help='the decision to pin (default: the last that moved '
                    "the dead unit, else the death's plan_ref)")
    c = sub.add_parser('cell',
                       help='one cell, Manchego Stars vs its twin, to its verdict (ADR 0385)')
    c.add_argument('--analysis', required=True, choices=('paired', 'marginal'),
                   help="the pilot's choice, frozen before any confirmatory seed plays")
    c.add_argument('--cells', type=int, help="the frozen cell count N (default: the manifest's)")
    c.add_argument('--chapter', type=int,
                   help='a chapter cell: the Manchego Stars chapter number (its twin is '
                        'its parity reference)')
    c.add_argument('--starts', type=int, default=CELL_STARTS,
                   help='a chapter cell: the pinned campaigns an arm (default %(default)s)')
    c.add_argument('--ours', help="a campaign cell: ours' campaign env .json")
    c.add_argument('--vanilla', help="a campaign cell: the twin's campaign env .json")
    c.add_argument('--ours-chapter', type=int, help="a campaign cell: ours' chapter index")
    c.add_argument('--vanilla-chapter', type=int, help="a campaign cell: the twin's index")
    c.add_argument('--mode', default='normal')
    c.add_argument('--jobs', type=int, default=4)
    pi = sub.add_parser('pilot', help='the one-cell pilot on the 50 pilot seeds (FR-025)')
    pi.add_argument('--chapter', type=int, required=True,
                    help='the Manchego Stars chapter number (its twin is its parity reference)')
    pi.add_argument('--starts', type=int, default=CELL_STARTS,
                    help='the pinned campaigns an arm (default %(default)s)')
    pi.add_argument('--cells', type=int, help="the frozen cell count N (default: the manifest's)")
    pi.add_argument('--jobs', type=int, default=8)
    pi.add_argument('--bench-vanilla', type=lambda s: int(s, 0), action='append',
                    help="an experiment: this charId of the twin's only waits where it stands "
                         '(repeat it); its runs are filed under their own instrument')
    sa = sub.add_parser('starts', help="play and pin the campaigns a chapter cell's starts "
                        'come from (T100e)')
    sa.add_argument('--game', required=True, choices=('ours', 'vanilla'))
    sa.add_argument('--count', type=int, default=CELL_STARTS,
                    help='campaigns pinned in all, on the first seeds of the starts set')
    sa.add_argument('--jobs', type=int, default=8)
    rr = sub.add_parser('report', help="one instrument's cells in sentences (FR-031)")
    rr.add_argument('cells', nargs='?', default=CELLS_FILE,
                    help='the cell records (default %(default)s)')
    rr.add_argument('--instrument', help="whose cells (default: the newest cell's)")
    rr.add_argument('--decision', choices=('party', 'enemy', 'chapter'),
                    help="read only this decision's components (FR-032)")
    rr.add_argument('--components', help='a chapter decision: the components it affected, '
                    'comma-separated (%s)' % ', '.join(COMPONENTS))
    rr.add_argument('--post', action='store_true', help='write it to build/ and print the '
                    '`gh issue comment 510` command; never runs it')
    su = sub.add_parser('suite', help="the frozen suite's pinned starts, attempt 1 each")
    su.add_argument('--held-out', action='store_true',
                    help='the held-out seeds too, as counts only, and the promotion result')
    su.add_argument('--freeze', action='store_true',
                    help='as --held-out, then write the frozen baseline if promoted')
    su.add_argument('--override', metavar='WHY',
                    help='with --freeze: freeze a refused candidate, WHY kept in the file '
                         '(Nicolas\'s call only, ADR 0395)')
    su.add_argument('--kept', action='store_true',
                    help="judge this instrument's kept runs instead of playing them again")
    su.add_argument('--jobs', type=int, default=8)
    args = ap.parse_args(argv)
    if args.cmd == 'cell':
        campaign = [args.ours, args.vanilla, args.ours_chapter, args.vanilla_chapter]
        given = [x is not None for x in [args.chapter] + campaign]
        if given not in ([True] + [False] * 4, [False] + [True] * 4):
            ap.error('cell takes either --chapter (a chapter cell) or --ours, --vanilla, '
                     '--ours-chapter and --vanilla-chapter (a campaign cell)')
        return cell_main(args)
    if args.cmd == 'pilot':
        return pilot_main(args)
    if args.cmd == 'suite':
        return suite_main(args)
    if args.cmd == 'starts':
        return starts_main(args)
    if args.cmd == 'replay':
        return replay_main(args)
    if args.cmd == 'audit':
        return audit_main(args)
    if args.cmd == 'report':
        return report_main(args)
    if args.cmd == 'story':
        events = read_trace(args.trace)
        if args.turn is not None:
            events = [e for e in events if e.get('t') in ('start', 'end')
                      or args.turn - 1 <= (e.get('turn') or 0) <= args.turn]
        info = (events[0].get('info') or {}) if events else {}
        game = info.get('game') or 'vanilla'
        note = names_note(game, [info.get('rom_hash')])
        if note:
            print(note)
        print('\n'.join(story(events, _names(game), _items(), _classes(game))))
        return 0
    with open(args.env) as fh:
        env = json.load(fh)
    pool = Pool(jobs=args.jobs, out=args.out)
    records, said = [], set()
    for r in pool.run(attempt_tasks(env, args.attempts, args.seed, args.vanilla)):
        records.append(r)
        line = attempt_line(r, said)
        if line:
            print(line, flush=True)
    k = first_clean(records)
    print('first clean attempt: %s' % (k if k is not None else 'none'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
