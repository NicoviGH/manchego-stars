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
"""
import argparse
import concurrent.futures
import json
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
