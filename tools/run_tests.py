#!/usr/bin/env python3
"""Run the Python unit tests, in parallel, for everything that needs them run.

`make test` and `tools/check.py check_tests_pass` both run "every test file", and before
#382 each had its own serial loop -- a shell `for` in the Makefile and a `for` in check.py.
Two implementations of one decision, and both were the slowest thing in a commit: 57 files,
one at a time, is what made the pre-commit hook 6-10 minutes before #380 and 199s after it.

So the loop lives here, once, and both callers import or invoke it.

Parallel by threads rather than processes: every unit of work is itself a subprocess, so the
pool waits on `git show` and the OS scheduler instead of contending for the GIL. Failures
are reported in DISCOVERY order, never completion order, so the report does not depend on
which worker happened to finish first.

Stdlib only -- check.py imports this in the lightweight CI job, which has pyyaml and nothing
else.

Run: python3 tools/run_tests.py [-jN]
"""
import argparse
import concurrent.futures
import glob
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# One worker per core, capped. Past the core count these are just more processes competing
# for the same `git show` I/O, and an unbounded pool over a 57-file glob is a fork bomb on a
# small runner. os.cpu_count() can return None on exotic hosts.
DEFAULT_WORKERS = min(8, (os.cpu_count() or 4))


def test_files():
    """Every Python test file, in a stable order.

    `tools/playtest/` was outside this glob until 2026-08-06 (#236), so its tests -- the
    pure formatting/diff logic that keeps the emulator out of the loop -- ran only when
    someone invoked them by hand. `unittest discover -s tools` does not reach them either
    (the directory is not an importable package), so this glob is the only gate. Coverage
    nothing runs is not coverage.
    """
    return sorted(glob.glob(os.path.join(REPO, 'tools', 'test_*.py'))
                  + glob.glob(os.path.join(REPO, 'tools', 'playtest', 'test_*.py')))


def run_one(path):
    """(relpath, None) when it passes, (relpath, combined_output) when it does not."""
    proc = subprocess.run([sys.executable, path], capture_output=True, text=True)
    rel = os.path.relpath(path, REPO)
    if proc.returncode == 0:
        return rel, None
    return rel, (proc.stderr or proc.stdout).strip()


def run(paths=None, workers=DEFAULT_WORKERS, report=None):
    """Run every test file; return [(relpath, output), ...] for the ones that failed.

    `report` is called with each (relpath, output) as it completes, for callers that want
    live progress; the RETURNED list is always in discovery order.
    """
    paths = test_files() if paths is None else paths
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for rel, output in pool.map(run_one, paths):
            results[rel] = output
            if report:
                report(rel, output)
    order = [os.path.relpath(p, REPO) for p in paths]
    return [(rel, results[rel]) for rel in order if results.get(rel) is not None]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('-j', '--jobs', type=int, default=DEFAULT_WORKERS,
                    help='parallel workers (default: one per core, capped at 8)')
    ap.add_argument('-q', '--quiet', action='store_true', help='only report failures')
    args = ap.parse_args()

    paths = test_files()
    print('== %d test files, %d at a time ==' % (len(paths), args.jobs))

    def progress(rel, output):
        if output is None:
            if not args.quiet:
                print('ok   %s' % rel)
        else:
            print('FAIL %s' % rel)

    failures = run(paths, workers=args.jobs, report=progress)
    if not failures:
        print('== all %d test files pass ==' % len(paths))
        return 0

    # Full output for the failures only, after the run, so it is readable instead of
    # interleaved with seven other workers.
    for rel, output in failures:
        print('\n' + '=' * 70)
        print('FAIL %s' % rel)
        print('=' * 70)
        print(output)
    print('\n== %d of %d test files FAILED: %s ==' % (
        len(failures), len(paths), ', '.join(rel for rel, _ in failures)))
    return 1


if __name__ == '__main__':
    sys.exit(main())
