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
"""
import argparse
import concurrent.futures
import json
import math
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RUN_SH = os.path.join(HERE, 'run.sh')

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
    with open(log_path, 'w') as log:
        subprocess.run([RUN_SH, scenario], env=env, stdout=log, stderr=subprocess.STDOUT,
                       check=False)
    where = run_dir(scenario, tag)
    try:
        with open(os.path.join(where, 'mgba-stdout.log'), errors='replace') as fh:
            return fh.read(), where
    except FileNotFoundError:
        return '', where


def records_of(task, text, where, log_path):
    """A worker's records: its BOTRUN lines, each naming its run dir; else one stand-in
    saying why there is none."""
    recs = parse_lines(text, BOTRUN)
    for r in recs:
        r['run_dir'] = where
    if recs:
        return recs
    attempt = (task.get('campaign') or {}).get('attempt')
    for c in parse_lines(text, CAMPAIGN):
        if c.get('outcome') == 'no_style':
            return [{'outcome': 'no_style', 'attempt': attempt, 'chapter': c.get('chapter'),
                     'run_dir': where}]
    return [{'outcome': 'crashed', 'attempt': attempt, 'run_dir': where, 'log': log_path,
             'why': 'the worker left no BOTRUN record'}]


class Pool:
    """`jobs` workers at once. `launch(task, tag, log_path) -> (stdout text, run dir)` runs one
    task (the real one drives run.sh; tests pass a fake)."""

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
            try:
                text, where = self.launch(task, tag, log_path)
            except Exception as err:   # a worker that dies is a record, never a lost run
                attempt = (task.get('campaign') or {}).get('attempt')
                return [{'outcome': 'crashed', 'attempt': attempt, 'log': log_path,
                         'run_dir': run_dir(task.get('scenario', 'campaign'), tag),
                         'why': '%s: %s' % (type(err).__name__, err)}]
            return records_of(task, text, where, log_path)

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.jobs) as ex:
            futures = [ex.submit(one, i, t) for i, t in enumerate(tasks)]
            for f in concurrent.futures.as_completed(futures):
                for rec in f.result():
                    append_record(self.out, rec)
                    yield rec


def attempt_tasks(env, n, seed=1, vanilla=False):
    """Attempts 1..n of the chapter at `env`'s `from` start, one task each."""
    if env.get('from') is None:
        raise ValueError('montecarlo: attempts need an env with `from` (a saved chapter start)')
    return [{'campaign': dict(env, attempt=k), 'seed': seed, 'vanilla': vanilla}
            for k in range(1, n + 1)]


def first_clean(records):
    """The lowest attempt that cleared with everyone alive, or None."""
    clean = [r['attempt'] for r in records if r.get('all_alive') and r.get('attempt')]
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
    """Where a cell stands, from its pairs (ours_all_alive, vanilla_all_alive) in run order.

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
    args = ap.parse_args(argv)
    with open(args.env) as fh:
        env = json.load(fh)
    pool = Pool(jobs=args.jobs, out=args.out)
    records = []
    for r in pool.run(attempt_tasks(env, args.attempts, args.seed, args.vanilla)):
        records.append(r)
        cost = (r.get('costs') or {}).get('cpu_s')
        print('attempt %s: %s%s, turn %s, %d deaths%s' % (
            r.get('attempt'), r.get('outcome'), ' all alive' if r.get('all_alive') else '',
            r.get('turns', '-'), len(r.get('deaths') or []),
            '' if cost is None else ', %.1f CPU s' % cost), flush=True)
    k = first_clean(records)
    print('first clean attempt: %s' % (k if k is not None else 'none'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
