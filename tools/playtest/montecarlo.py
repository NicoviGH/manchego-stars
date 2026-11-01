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

`paired_verdict` says where one chapter-and-mode cell stands from its ours/vanilla pairs: looked
at only at planned sizes, tested on the pairs that disagree, with score intervals (research
record 0022; the #510 plan's Task 12, amended 2026-10-27).

    python3 tools/playtest/montecarlo.py cell --ours <env .json> --vanilla <env .json> \
        [--mode normal] [--jobs 4]

    python3 tools/playtest/montecarlo.py story <trace .jsonl[.gz]>

`story` reads one run's trace (botrun.lua) as plain text, turn by turn, with the game's own
forecast and every blow.

    python3 tools/playtest/montecarlo.py suite [--baseline] [--jobs 8]

`suite` plays the difficulty instrument's frozen suite (#510 step 9; matrix.yaml's
`instrument:` section, ADR 0387): attempt 1 of each pinned chapter start, from its saved state,
under each of its seeds. Without --baseline it plays the tuning seeds and prints each run;
--baseline plays the held-out seeds too and prints only what each start cost. It refuses a start
that no longer matches its pin, and any job over 8 wall-hours (SC-007), before anything runs.

`cell` plays one chapter-and-mode cell to its verdict. Pair s is campaign s of each game: from
New Game, the game seeded once with s and never again, as a player's own save; each chapter is
retried until it clears clean (campaign.lua), and the pair's result is the campaign's FIRST
attempt at the cell's chapter. One sweep's campaigns serve every chapter's cell. Runs are kept in
each game's store (`run.sh --simdir`/runs.jsonl), stamped with a hash of the whole campaign env,
the mode and the bot code; a kept campaign with the same stamp is read, never played again. A
run without a game result (a crash, a campaign that never reached the chapter) is never guessed
at: the cell stops and reports what that run said.
"""
import argparse
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
sys.path.insert(0, HERE)

BOTRUN, CAMPAIGN = 'BOTRUN', 'CAMPAIGN'


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


def append_record(path, rec):
    """Append `rec` to `path` as ONE line, in one write on an O_APPEND descriptor: two
    workers' records never interleave, and a reader never sees half of one."""
    data = (json.dumps(rec, sort_keys=True) + '\n').encode('utf-8')
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        if os.write(fd, data) != len(data):
            raise OSError('montecarlo: a short write to %s' % path)
    finally:
        os.close(fd)


def run_dir(scenario, tag):
    """Where run.sh keeps a tagged run (its PT_RUN_TAG)."""
    return '/tmp/playtest-%s@%s' % (scenario, tag)


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
    bot = any(r.get('kind') != 'campaign' for r in recs)
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
        for a in rec.get('anomalies') or []:
            a.pop('narrate', None)
        return
    rel = os.path.join('traces', str(rec.get('campaign') or 'run'), '%s-s%s-a%s-%s.jsonl.gz' % (
        rec.get('chapter'), rec.get('seed'), rec.get('attempt'), uuid.uuid4().hex[:8]))
    dest = os.path.join(os.path.dirname(os.path.abspath(out)), rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(src, 'rb') as fin, gzip.open(dest, 'wb') as fout:
        shutil.copyfileobj(fin, fout)
    rec['trace'] = rel
    # each anomaly's story command names the trace where it is kept now, not the run dir
    for a in rec.get('anomalies') or []:
        a['narrate'] = narrate(dest, a.get('turn'))


class Pool:
    """`jobs` workers at once. `launch(task, tag, log_path) -> (stdout text, run dir)` runs one
    task (the real one drives run.sh; tests pass a fake). A task's `stamp` is written into
    each of its records, and its records go to its own `out` when it names one (the suite
    files each game's in that game's store). Each record carries `wall_s`, its worker's
    wall time."""

    def __init__(self, jobs=8, out='runs.jsonl', log_dir=None, launch=launch):
        self.jobs, self.out, self.launch = jobs, out, launch
        self.log_dir = log_dir or os.path.join(os.path.dirname(os.path.abspath(out)), 'workers')

    def run(self, tasks):
        """Yield every record as its worker finishes, each appended to `out` first."""
        os.makedirs(self.log_dir, exist_ok=True)
        base = '%d-%d' % (os.getpid(), id(self) % 10000)

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
                         'run_dir': run_dir(task.get('scenario', 'campaign'), tag),
                         'why': '%s: %s' % (type(err).__name__, err)}]
            else:
                recs = records_of(task, text, where, log_path)
            wall = time.monotonic() - began
            for r in recs:
                r.update(task.get('stamp') or {})
                r['wall_s'] = wall
                keep_trace(r, out)
            return out, recs

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.jobs) as ex:
            futures = [ex.submit(one, i, t) for i, t in enumerate(tasks)]
            for f in concurrent.futures.as_completed(futures):
                out, recs = f.result()
                for rec in recs:
                    append_record(out, rec)
                    yield rec


def attempt_tasks(env, n, seed=1, vanilla=False):
    """Attempts 1..n of the chapter at `env`'s `from` start, one task each."""
    if env.get('from') is None:
        raise ValueError('montecarlo: attempts need an env with `from` (a saved chapter start)')
    return [{'campaign': dict(env, attempt=k), 'seed': seed, 'vanilla': vanilla,
             'stamp': {'task_attempt': k}} for k in range(1, n + 1)]


def narrate(trace, turn):
    """The command that tells an anomaly's turns from its run's trace (botrun.lua writes the
    same shape with the run dir's name; keep_trace points it at the kept file)."""
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


def death(d, who=lambda c: '0x%02X' % c):
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


def theft(t, who=lambda c: '0x%02X' % c):
    """One theft of a record's `thefts` (ADR 0379), in words."""
    return '%s stole item 0x%02X from %s (turn %s)' % (who(t['thief']), t['item'], who(t['from']),
                                                       t.get('turn'))


def spoiled(r, who=lambda c: '0x%02X' % c):
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
        why = t.get('status', t.get('why'))
        out.append('%s %s,%s %s%s%s' % ('village' if t['kind'] == 'visit' else 'chest', t['x'],
                                         t['y'], why, ' by %s' % who(t['closed_by'])
                                         if t.get('closed_by') is not None else '',
                                         ' (%s)' % t['reason'] if t.get('reason') else ''))
    out += [theft(t, who) for t in c.get('stolen') or []]
    return '; '.join(out)


def attempt_line(r, said):
    """The line `attempts` prints for record `r`, or None. `said` = the attempts already
    printed. A worker's CAMPAIGN end is printed only when no BOTRUN of its attempt was: a run
    that crashed before its bot reported (vanilla Ch3, 2026-10-29: a symbol table another run
    rewrote) would otherwise vanish from the listing."""
    if r.get('kind') == 'campaign':
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
    # a lost run's deaths, graded, are what it says about the plan (a won one's are in `why`)
    if r.get('outcome') != 'won' and any(d.get('cause') for d in r.get('deaths') or []):
        why = '; '.join(death(d) for d in r['deaths'])
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


# ---- the paired verdict (PR F2; the #510 plan comment's Task 12, amended 2026-10-27) ----
# Research record 0022: a cell is looked at only at planned sizes (Haybittle-Peto), never
# after every run; the difference is tested on the discordant pairs (exact McNemar); rates
# and the difference carry score intervals, never a normal one.

LOOKS = (50, 100, 200)      # pairs; the last look always settles
EARLY_P = 0.001             # an early look settles only on a gap this clear
FINAL_P = 0.05
Z95 = 1.959963984540054     # the two-sided 95% normal quantile


def wilson(k, n, z=Z95):
    """Wilson's score interval for k successes in n: (lo, hi), inside [0, 1] even at 0/n."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p: the discordant pairs split as a fair coin would."""
    m = b + c
    if m == 0:
        return 1.0
    tail = sum(math.comb(m, i) for i in range(min(b, c) + 1)) / 2 ** m
    return min(1.0, 2 * tail)


def square_and_add(k1, n1, k2, n2, phi=0.0, z=Z95):
    """Newcombe's interval for p1 - p2: each rate's Wilson interval, combined. phi = 0 is
    two independent rates (Newcombe 1998a, method 10); the paired form passes the pairs'
    correlation (1998b, method 10)."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson(k1, n1, z)
    l2, u2 = wilson(k2, n2, z)
    delta = p1 - p2
    lo = delta - math.sqrt(max(0.0, (p1 - l1) ** 2 - 2 * phi * (p1 - l1) * (u2 - p2) + (u2 - p2) ** 2))
    hi = delta + math.sqrt(max(0.0, (u1 - p1) ** 2 - 2 * phi * (u1 - p1) * (p2 - l2) + (p2 - l2) ** 2))
    return max(-1.0, lo), min(1.0, hi)


def newcombe_paired(a, b, c, d, z=Z95):
    """The paired score interval for p1 - p2 from the cells -- a both clean, b only the first,
    c only the second, d neither (Newcombe 1998b, method 10)."""
    n = a + b + c + d
    if n == 0:
        return -1.0, 1.0
    den = math.sqrt((a + b) * (c + d) * (a + c) * (b + d))
    return square_and_add(a + b, n, a + c, n, (a * d - b * c) / den if den else 0.0, z)


def paired_verdict(pairs):
    """Where a cell stands, from its pairs (ours_clean, vanilla_clean) in run order.

    It is judged at the largest planned look its pairs reach, on that many pairs only: a pair
    past the look waits for the next one. Settled at an early look when exact McNemar p <
    EARLY_P, and always at the last. `differs` only when settled at p < its look's bar.
    """
    reached = [k for k in LOOKS if k <= len(pairs)]
    if not reached:
        return {'n': len(pairs), 'look': None, 'settled': False, 'differs': False,
                'reason': 'no look yet: the first is at %d pairs' % LOOKS[0]}
    look = reached[-1]
    used = [(bool(x), bool(y)) for x, y in pairs[:look]]
    a = sum(1 for x, y in used if x and y)
    b = sum(1 for x, y in used if x and not y)
    c = sum(1 for x, y in used if y and not x)
    d = look - a - b - c
    p = mcnemar_exact(b, c)
    final = look == LOOKS[-1]
    bar = FINAL_P if final else EARLY_P
    den = math.sqrt((a + b) * (c + d) * (a + c) * (b + d))
    lo, hi = newcombe_paired(a, b, c, d)
    out = {'n': len(pairs), 'look': look, 'p': p, 'diff': (b - c) / look, 'lo': lo, 'hi': hi,
           'ours': (a + b) / look, 'ours_ci': wilson(a + b, look),
           'vanilla': (a + c) / look, 'vanilla_ci': wilson(a + c, look),
           'discordant': b + c, 'corr': (a * d - b * c) / den if den else None,
           'differs': p < bar, 'settled': final or p < bar}
    if final:
        out['reason'] = 'the last look (%d pairs): %s' % (
            look, 'differs, p = %.3g' % p if p < bar else 'no clear difference, p = %.3g' % p)
    elif p < bar:
        out['reason'] = 'settled early at %d pairs: a clear gap, p = %.3g' % (look, p)
    else:
        out['reason'] = 'not settled at %d pairs (p = %.3g); the next look is at %d' % (
            look, p, LOOKS[LOOKS.index(look) + 1])
    return out


# ---- one cell, played to its verdict (PR F2) ----

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


def campaign_tasks(env, seeds, mode, stamp, vanilla=False):
    """Campaign s for each seed s: from New Game, the game seeded once with s and never again
    (a player's own save), every chapter to the env's last retried until it clears clean
    (campaign.lua). Its id is the sweep's and the seed, so its chapter starts are its own."""
    if env.get('from') is not None or env.get('attempt') is not None:
        raise ValueError('montecarlo: a cell plays whole campaigns, each keeping its seed: '
                         'an env with `from` or `attempt` would cut one short')
    return [{'campaign': dict(env, id='%s-s%d' % (stamp['cell']['env'][:8], s)), 'seed': s,
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


def chapter_result(recs, chapter):
    """(clean, None) for a campaign's FIRST attempt at `chapter`; (None, why) when it has no game
    result there -- that attempt crashed, or the campaign ended before reaching it -- with the
    run's own words for why; (None, None) when the campaign has not been played."""
    for r in recs:
        if r.get('kind') != 'campaign' and r.get('chapter') == chapter and r.get('attempt') == 1:
            if r.get('outcome') in UNUSABLE:
                return None, r
            return r.get('clean') is True, None
    # an earlier attempt's crash, in its own words, before the campaign's summary of it
    crashed = [r for r in recs if r.get('kind') != 'campaign' and r.get('outcome') in UNUSABLE]
    ends = crashed or [r for r in recs if r.get('kind') == 'campaign']
    if ends:
        last = ends[-1]
        where = ' (chapter %s, attempt %s)' % (last['chapter'], last.get('attempt')) \
            if last.get('chapter') is not None else ''
        return None, dict(last, why='the campaign never played chapter %s: %s%s: %s' % (
            chapter, last.get('outcome'), where, last.get('why')))
    return None, None


def run_cell(sides, play, looks=LOOKS):
    """Play a cell to its verdict. `sides` = {'ours': side, 'vanilla': side}, each side
    {'env', 'chapter', 'store', 'stamp', 'mode', 'vanilla'}; `play(side, tasks) -> records` runs
    campaigns and keeps their records in the side's store. Pair s is campaign s of each side.

    A pair without a game result on either side is never guessed at: the cell stops, unsettled,
    and `problems` lists each such run with what it said (why, log tail, run dir)."""
    names = ('ours', 'vanilla')
    have = {n: kept_runs(sides[n]['store'], sides[n]['stamp']) for n in names}
    played = {n: 0 for n in names}
    verdict = paired_verdict([])
    for look in looks:
        seeds = range(1, look + 1)
        for n in names:
            side = sides[n]
            missing = [s for s in seeds if s not in have[n]]
            if missing:
                for rec in play(side, campaign_tasks(side['env'], missing, side['mode'],
                                                     side['stamp'], side['vanilla'])):
                    if rec.get('seed') is None:
                        raise RuntimeError('montecarlo: a run record without its seed: %r' % rec)
                    have[n].setdefault(rec['seed'], []).append(rec)
                played[n] += len(missing)
        pairs, problems = [], []
        for s in seeds:
            got = {}
            for n in names:
                clean, bad = chapter_result(have[n].get(s, []), sides[n]['chapter'])
                if bad is not None or clean is None:
                    bad = bad or {'why': 'no record of this campaign'}
                    problems.append({'side': n, 'seed': s, 'why': bad.get('why'),
                                     'outcome': bad.get('outcome'), 'run_dir': bad.get('run_dir'),
                                     'log': bad.get('log'), 'log_tail': bad.get('log_tail')})
                got[n] = clean
            pairs.append((got['ours'], got['vanilla']))
        if problems:
            verdict = dict(paired_verdict([]), settled=False, problems=problems,
                           reason='stopped at %d pairs: %d runs have no game result; each says why'
                           % (look, len(problems)))
            break
        verdict = paired_verdict(pairs)
        if verdict['settled']:
            break
    return dict(verdict, played=played)


def pool_play(jobs):
    """The real `play`: a Pool appending to the side's store."""
    def play(side, tasks):
        os.makedirs(os.path.dirname(side['store']), exist_ok=True)
        return list(Pool(jobs=jobs, out=side['store']).run(tasks))
    return play


def cell_main(args):
    bot = bot_hash()
    sides = {}
    for name, path, chapter in (('ours', args.ours, args.ours_chapter),
                                ('vanilla', args.vanilla, args.vanilla_chapter)):
        with open(path) as fh:
            env = json.load(fh)
        sides[name] = {'env': env, 'chapter': chapter, 'mode': args.mode,
                       'vanilla': name == 'vanilla',
                       'store': os.path.join(simdir(name == 'vanilla'), 'runs.jsonl'),
                       'stamp': cell_stamp(env, args.mode, bot)}
    v = run_cell(sides, pool_play(args.jobs))
    print(v['reason'])
    for p in v.get('problems') or []:
        print('  %s seed %s: %s (%s)' % (p['side'], p['seed'], p['why'], p.get('run_dir')))
        for line in (p.get('log_tail') or [])[-5:]:
            print('      ' + line)
    if v.get('look') and not v.get('problems'):
        print('clean clears: ours %.0f%%, vanilla %.0f%%; gap %+.0f points (%+.0f to %+.0f)' % (
            100 * v['ours'], 100 * v['vanilla'], 100 * v['diff'], 100 * v['lo'], 100 * v['hi']))
    print('campaigns played now: ours %(ours)d, vanilla %(vanilla)d' % v['played'])
    return 0


# ---- the frozen suite (#510 step 9 plan, PR-A: T006, T010) ----
# The instrument's regression suite is a section of matrix.yaml (plan R-6: one manifest owns
# what a playtest needs, ADR 0074): pinned chapter starts, each played on attempt 1 from its
# saved state under fixed seeds. FR-021 says what an entry names; FR-025 that the tuning,
# held-out, pilot and confirmatory seeds never meet.

SUITE_TOP = ('version', 'route', 'emulator', 'seed_sets', 'shops_from', 'starts')
SUITE_KEYS = ('start_id', 'game', 'chapter', 'rom_hash', 'state_path', 'state_sha1',
              'provenance', 'label', 'seeds', 'style', 'invariant', 'budgets', 'estimate_wall_s')
BUDGET_KEYS = ('beam', 'final', 'branch', 'lookahead_decision', 'lookahead_attempt')
LABELS = ('fixture', 'scout', 'snapshot')
STYLES = ('drawn',)       # attempt 1's own draw (campaign.lua drawStyle), what a cell plays
INVARIANTS = ('record',)  # the attempt leaves one BOTRUN record with a game result


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
    defaults = inst.get('defaults') or {}
    sets = {name: set(range(lo, hi + 1)) for name, (lo, hi) in inst['seed_sets'].items()}
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
    return dict(inst, starts=starts)


REPO = os.path.dirname(os.path.dirname(HERE))
MAX_WALL_H = 8    # SC-007: a planned job longer than this is split or narrowed, never run
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
    return out


def suite_tasks(suite, envs, instrument, outs, sets=SEED_SETS):
    """Attempt 1 of each pinned start under each of its seeds in `sets`: the game's campaign env
    (`envs[game]`, campaign_env's) resumed at the start's chapter from the state its campaign
    saved, and ended there. An attempt-mode run saves no state, so the pinned file is never
    rewritten (campaign.lua)."""
    tasks = []
    for st in suite['starts']:
        camp = dict(envs[st['game']], id=st['provenance']['campaign'], attempt=1,
                    last=[st['chapter']])
        camp['from'] = st['chapter']
        for kind in sets:
            for seed in st['seeds'][kind]:
                tasks.append({'campaign': camp, 'seed': seed, 'vanilla': st['game'] == 'vanilla',
                              'instrument': instrument, 'out': outs.get(st['game']),
                              'stamp': {'task_attempt': 1,
                                        'suite': {'start_id': st['start_id'], 'set': kind,
                                                  'version': suite['version']}}})
    return tasks


def kept_walls(paths, instrument, rom_hashes):
    """{start_id: [wall_s]} of the suite runs kept in `paths` (each game's runs file) that this
    instrument played on these ROMs ({game: hash}) to a game result: a run of other code, or
    one that crashed at boot in seconds, says nothing about what the next will take."""
    runs = kept(paths, lambda r: r.get('suite') and r.get('kind') != 'campaign'
                and r.get('instrument') == instrument
                and r.get('rom_hash') == rom_hashes.get(r.get('game'))
                and r.get('outcome') not in UNUSABLE and r.get('wall_s') is not None,
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


def run_suite(suite, envs, simdirs, play, jobs, baseline, instrument, check=check_starts,
              kept=None, wall_limit_h=MAX_WALL_H):
    """Play the suite and say what it cost, as lines to print. `baseline` plays every seed,
    tuning and held-out, and reports only cost: a held-out outcome is never shown to whoever
    is tuning the bot. Without it, the tuning seeds play and each run's line is printed too.
    Refuses, with the reason, a start that no longer matches its pin or a job over
    `wall_limit_h` (SC-007), before anything runs. `envs()` builds {game: campaign env}."""
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
    tasks = suite_tasks(suite, envs, instrument, outs, SEED_SETS if baseline else ('tuning',))
    hours = suite_estimate(suite, tasks, kept or {}, jobs)
    lines.append('%d runs on %d workers: about %.2f wall-hours' % (len(tasks), jobs, hours))
    if hours > wall_limit_h:
        lines.append('refused: the estimate is over the %g wall-hours one job may take (SC-007); '
                     'split it or narrow it' % wall_limit_h)
        return lines
    per, seen = {}, set()
    for rec in play(tasks):
        sid = (rec.get('suite') or {}).get('start_id')
        # a worker's records come together, its bot's first: its campaign's end is the run
        # only when the bot left none (records_of)
        key = (sid, rec.get('seed'))
        if sid is None or (rec.get('kind') == 'campaign' and key in seen):
            continue
        seen.add(key)
        got = per.setdefault(sid, {'n': 0, 'cpu': 0.0, 'wall': 0.0, 'unread': 0})
        got['n'] += 1
        got['cpu'] += (rec.get('costs') or {}).get('cpu_s') or 0.0
        got['wall'] += rec.get('wall_s') or 0.0
        # the invariant `record`: one BOTRUN record with a game result; a campaign's end
        # standing in for it is never one
        got['unread'] += rec.get('kind') == 'campaign' or rec.get('outcome') in UNUSABLE
        if not baseline:
            line = attempt_line(rec, set()) or 'attempt 1: %s (%s)' % (rec.get('outcome'),
                                                                    rec.get('why'))
            lines.append('%s seed %s: %s' % (sid, rec.get('seed'), line))
    total = {'n': 0, 'cpu': 0.0, 'wall': 0.0, 'unread': 0}
    for st in suite['starts']:
        got = per.get(st['start_id'])
        if not got:
            lines.append('%s: no run came back' % st['start_id'])
            continue
        for k in total:
            total[k] += got[k]
        lines.append('%s (%s chapter %d, %s): %d runs, %.1f CPU s and %.1f wall s in all, '
                     '%.1f CPU s a run%s' % (
                         st['start_id'], st['game'], st['chapter'], st['label'], got['n'],
                         got['cpu'], got['wall'], got['cpu'] / got['n'],
                         '; %d without a game result' % got['unread'] if got['unread'] else ''))
    lines.append('the suite: %d runs, %.1f CPU s and %.1f wall s of work, %d without a game '
                 'result' % (total['n'], total['cpu'], total['wall'], total['unread']))
    return lines


def suite_main(args):
    import campaign_env
    if os.environ.get('PT_SIMDIR'):
        print('refused: PT_SIMDIR is set; the suite plays each game from its own store, named '
              "by the ROM built now (run.sh's simdir)")
        return 1
    suite = load_suite()
    simdirs = {'vanilla': simdir(True), 'ours': simdir(False)}

    def envs():
        return {'vanilla': campaign_env.vanilla_env(suite['route']),
                'ours': campaign_env.ours_env([os.path.join(REPO, p)
                                               for p in suite['shops_from']])}
    outs = [os.path.join(d, 'runs.jsonl') for d in simdirs.values()]
    pool = Pool(jobs=args.jobs, out=outs[0])
    hashes = {g: os.path.basename(d) for g, d in simdirs.items()}
    lines = run_suite(suite, envs, simdirs, pool.run, args.jobs, args.baseline,
                      instrument_id(), kept=kept_walls(outs, instrument_id(), hashes))
    for line in lines:
        print(line, flush=True)
    return 1 if any(line.startswith('refused') for line in lines) else 0


# ---- one run, told (PR F3) ----

@functools.lru_cache(maxsize=None)
def _names(game):
    """{character id: name}: ours' cast by its PCs' and guests' names, then every character
    the decomp names (vanilla's cast and the generic enemies both games share)."""
    sys.path.insert(0, os.path.dirname(HERE))
    import inject.decomp
    from inject.scene_actors import cast_pids
    text = inject.decomp.vanilla_decomp_text('include/constants/characters.h')
    out = {v: k[len('CHARACTER_'):].replace('_', ' ').title()
           for k, v in inject.decomp.enum_values(text, 'CHARACTER_').items()}
    if game == 'ours':
        for name, pid in cast_pids().items():
            out[pid] = name.replace('-', ' ').title()
    return out


@functools.lru_cache(maxsize=None)
def _items():
    sys.path.insert(0, os.path.dirname(HERE))
    import inject.decomp
    text = inject.decomp.vanilla_decomp_text('include/constants/items.h')
    return {v: k[len('ITEM_'):].replace('_', ' ').title()
            for k, v in inject.decomp.enum_values(text, 'ITEM_').items()}


@functools.lru_cache(maxsize=None)
def _classes(game='vanilla'):
    """{class id: name}: every vanilla class by FE8's name, and for ours each enemy reskin by
    its own (campaign.yaml), on the slot it takes."""
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
        return 'unit 0x%02X' % cid

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
    c = sub.add_parser('cell', help='one chapter-and-mode cell, ours vs vanilla, to its verdict')
    c.add_argument('--ours', required=True, help="ours' campaign env .json")
    c.add_argument('--vanilla', required=True, help="the twin's campaign env .json")
    c.add_argument('--ours-chapter', type=int, required=True, help="ours' chapter index")
    c.add_argument('--vanilla-chapter', type=int, required=True, help="the twin's chapter index")
    c.add_argument('--mode', default='normal')
    c.add_argument('--jobs', type=int, default=4)
    su = sub.add_parser('suite', help="the frozen suite's pinned starts, attempt 1 each")
    su.add_argument('--baseline', action='store_true',
                    help='every seed, tuning and held-out; report cost only')
    su.add_argument('--jobs', type=int, default=8)
    args = ap.parse_args(argv)
    if args.cmd == 'cell':
        return cell_main(args)
    if args.cmd == 'suite':
        return suite_main(args)
    if args.cmd == 'story':
        events = read_trace(args.trace)
        if args.turn is not None:
            events = [e for e in events if e.get('t') in ('start', 'end')
                      or args.turn - 1 <= (e.get('turn') or 0) <= args.turn]
        game = ((events[0].get('info') or {}).get('game') if events else None) or 'vanilla'
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
