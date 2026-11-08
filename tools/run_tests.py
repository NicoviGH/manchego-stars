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
import fnmatch
import glob
import json
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


# What each test file READ the last time it ran (#579): the repo files it opened or imported,
# the directories it listed, the globs it matched, and whether it ran a subprocess this cannot
# see into. The pre-commit hook runs only the tests a staged path can reach (`affected`);
# `make test`, `make check` and CI still run all of them. Kept under build/ (gitignored), one
# JSON per test, rewritten by every run, so a record is never older than the test's last run.
TRACE_DIR = os.path.join(REPO, 'build', 'test-reads')

# A subprocess the tracer cannot follow makes the test OPAQUE (it always runs), except git
# reading a commit of the decomp submodule or its build tree: neither is ever staged here
# (AGENTS.md: never commit the submodule pointer; build/ is gitignored).
_INERT_GIT = ('fireemblem8u', os.path.join('build', 'fireemblem8u'))


def trace_path(rel):
    return os.path.join(TRACE_DIR, rel.replace(os.sep, '__') + '.json')


def _trace_run(path, out):
    """Run test `path` as `python path` would, recording what it reads (sys.addaudithook)."""
    reads, dirs, globs, opaque = set(), set(), set(), []
    root = REPO + os.sep

    def inside(p):
        try:
            p = os.path.realpath(os.fspath(p))
        except (TypeError, ValueError):
            return None
        return os.path.relpath(p, REPO) if p.startswith(root) else None

    def hook(event, args):
        if event == 'open' and args and isinstance(args[0], (str, bytes, os.PathLike)):
            rel = inside(args[0] if not isinstance(args[0], bytes) else args[0].decode())
            if rel:
                reads.add(rel)
        elif event in ('os.listdir', 'os.scandir') and args and args[0] is not None:
            rel = inside(args[0])
            if rel:
                dirs.add(rel)
        elif event == 'glob.glob' and args:
            pat = os.path.join(os.getcwd(), args[0]) if not os.path.isabs(args[0]) else args[0]
            if pat.startswith(root):
                globs.add(os.path.relpath(pat, REPO))
        elif event in ('subprocess.Popen', 'os.system', 'os.posix_spawn', 'os.exec'):
            argv = args[1] if event == 'subprocess.Popen' else args[0]
            argv = [os.fspath(a) for a in argv] if isinstance(argv, (list, tuple)) else [argv]
            text = ' '.join(str(a) for a in argv)
            inert = (os.path.basename(str(argv[0])) == 'git'
                     and any(('-C' == a and k + 1 < len(argv)
                              and str(argv[k + 1]).rstrip('/').endswith(_INERT_GIT))
                             for k, a in enumerate(argv)))
            if not inert:
                opaque.append(text[:200])

    def write():
        for mod in list(sys.modules.values()):
            rel = inside(getattr(mod, '__file__', None) or '')
            if rel:
                reads.add(rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out + '.tmp', 'w') as fh:
            json.dump({'reads': sorted(r for r in reads if '__pycache__' not in r),
                       'dirs': sorted(dirs), 'globs': sorted(globs),
                       'opaque': opaque[:5]}, fh)
        os.replace(out + '.tmp', out)

    import atexit
    import runpy
    atexit.register(write)
    sys.argv = [path]
    sys.path[0] = os.path.dirname(path)
    sys.addaudithook(hook)
    runpy.run_path(path, run_name='__main__')


def affected(paths, staged):
    """The test files among `paths` that a staged path can reach (#579): a test with no
    record, an opaque one, or one that read, listed or globbed a staged path. Anything this
    cannot know runs."""
    out = []
    for path in paths:
        rel = os.path.relpath(path, REPO)
        try:
            with open(trace_path(rel)) as fh:
                rec = json.load(fh)
        except (OSError, ValueError):
            out.append(path)
            continue
        reads = set(rec.get('reads', ())) | {rel}
        dirs = rec.get('dirs', ())
        globs = rec.get('globs', ())
        if rec.get('opaque') or any(
                s in reads
                or any(os.path.dirname(s) == d or s.startswith(d.rstrip(os.sep) + os.sep)
                       for d in dirs if d not in ('.', ''))
                or any(fnmatch.fnmatch(s, g) for g in globs)
                for s in staged):
            out.append(path)
    return out


def run_one(path):
    """(relpath, None) when it passes, (relpath, combined_output) when it does not. Every run
    rewrites the test's read record (TRACE_DIR)."""
    rel = os.path.relpath(path, REPO)
    proc = subprocess.run([sys.executable, os.path.abspath(__file__), '--trace-run', path,
                           trace_path(rel)], capture_output=True, text=True)
    if proc.returncode == 0:
        return rel, None
    # A failing test keeps no record, so the hook runs it until it passes again, whatever
    # is staged.
    try:
        os.remove(trace_path(rel))
    except OSError:
        pass
    return rel, (proc.stderr or proc.stdout).strip()


def _ensure_build_tree():
    """The census and scene-actor tests read the LIVE tree the injector writes (#408). It used
    to be the submodule's working tree, so it always existed -- vanilla on CI, injected after
    a local build. Keep that: make the build tree where the submodule is checked out."""
    if os.path.isdir(os.path.join(REPO, 'fireemblem8u', 'src')):
        sys.path.insert(0, os.path.join(REPO, 'tools'))
        import build_tree
        build_tree.ensure(verbose=False)


def run(paths=None, workers=DEFAULT_WORKERS, report=None):
    """Run every test file; return [(relpath, output), ...] for the ones that failed.

    `report` is called with each (relpath, output) as it completes, for callers that want
    live progress; the RETURNED list is always in discovery order.
    """
    paths = test_files() if paths is None else paths
    _ensure_build_tree()
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for rel, output in pool.map(run_one, paths):
            results[rel] = output
            if report:
                report(rel, output)
    order = [os.path.relpath(p, REPO) for p in paths]
    return [(rel, results[rel]) for rel in order if results.get(rel) is not None]


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--trace-run':
        return _trace_run(sys.argv[2], sys.argv[3])
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
