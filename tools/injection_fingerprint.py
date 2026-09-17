#!/usr/bin/env python3
"""What the injector WROTE, as a hash manifest -- the gate for refactoring it (#389).

Decomposing `build_campaign.py` is pure code movement, so the invariant is exact: the
injected decomp tree must be byte-for-byte what it was before. A rebuilt ROM would prove the
same thing, but `make` legitimately skips work it thinks is done, and a gate that can be
satisfied by doing nothing is not a gate -- the first attempt at this "passed" in 1.1 seconds
because the decomp's make found the ROM up to date.

So this measures the injector's actual output instead:

    python3 tools/injection_fingerprint.py --write before.json
    ...refactor...
    python3 tools/injection_fingerprint.py --check before.json

Each run restores the decomp to HEAD, runs a full injection, and hashes every file the
injection changed. Identical manifests mean identical ROM input.

Restoring first matters: injection is idempotent and skips files that already hold the right
bytes, so fingerprinting a tree that is already injected measures the cache rather than the
injector.

WHAT COUNTS AS INJECTED OUTPUT, and why it is not just `git status`: the injector also writes
files the decomp GITIGNORES -- `MontageMural.gbapal`, the world-map `.4bpp`/`.tsa`/`.gbapal`
copies -- and deletes stale ones so `make` regenerates them. `git status` never lists an ignored
path, and `git clean` without `-x` never removes one, so a manifest built from status alone
would print `IDENTICAL` for a refactor that stopped writing them entirely. Extension is no help
either: `make` produces 3,431 `.lz` and 2,424 `.4bpp` files of its own in the same directories.

So the manifest is the union of three things, and the third is what makes the second safe:
  * every TRACKED file the injection changed or added (content, via `git status`);
  * every ignored/untracked file under the injected directories whose mtime says THIS run
    wrote it -- which cannot pick up a `make` artifact, because nothing built one meanwhile;
  * a `DELETED` marker for every ignored/untracked path that existed before the run and does
    not after, so dropping a stale-artifact removal is a difference too.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject.decomp import git_env                                     # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECOMP = os.path.join(REPO, 'fireemblem8u')
CAMPAIGN = 'rime-of-the-frostmaiden'

# Injection rewrites these; the caches below make a second run skip work, which is exactly
# what must NOT happen while fingerprinting. `.build-config.json` is not a cache -- it is the
# stamp `playtest/matrix.py` reads to know WHICH ROM is in the tree -- but injection rewrites
# it, so a fingerprint run would relabel a ROM it never built and defeat `matrix.check_rom`.
# It is stashed and restored for that reason, not for speed.
CACHES = ('.injectcache', '.build-scopes.json', '.build-config.json')

# The directories injection writes into. Everything outside them is the decomp's own business.
INJECTED_DIRS = ('src', 'data', 'include', 'graphics', 'texts')

# A filesystem timestamp can sit marginally behind the clock we sampled, and nothing else is
# writing this tree while we inject, so a couple of seconds of slack costs nothing.
MTIME_SLACK = 2.0


def restore_decomp():
    """Put the decomp back to HEAD so the injector has to do all of its work."""
    # `HEAD --`, never `-- .`: `git checkout -- <path>` restores from the INDEX, so anything
    # staged in the decomp survives the restore and the injector never has to rewrite it.
    # `build_campaign.restore_vanilla_sources` documents the same trap.
    subprocess.run(['git', '-C', DECOMP, 'checkout', 'HEAD', '--', '.'], env=git_env(), check=True)
    subprocess.run(['git', '-C', DECOMP, 'clean', '-fdq', '--'] + list(INJECTED_DIRS),
                   env=git_env(), check=True)


def inject():
    env = dict(os.environ)
    subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'build_campaign.py'),
                    '--campaign', CAMPAIGN],
                   cwd=REPO, env=env, check=True, stdout=subprocess.DEVNULL)


def _status(*extra):
    """Paths from `git status --porcelain -z`, rename records parsed rather than mis-sliced.

    With `-z` a rename is TWO records -- `R  <new>\0<old>\0` -- so a loop that slices `[3:]`
    off every record turns the old path into garbage and drops it. Both halves matter here:
    the new path is output, and the old one is a path that stopped existing.
    """
    cmd = ['git', '-C', DECOMP, 'status', '--porcelain', '-z', '-uall']
    out = subprocess.run(cmd + list(extra), env=git_env(),
                         capture_output=True, text=True, check=True).stdout
    records = iter([r for r in out.split('\0') if r])
    paths = []
    for rec in records:
        status, rel = rec[:2], rec[3:]
        paths.append(rel)
        if 'R' in status or 'C' in status:
            paths.append(next(records, ''))     # the source half of the rename/copy
    return [p for p in paths if p]


def _ignored_paths():
    """Every ignored/untracked path under the injected directories.

    `--ignored=matching` is what makes the injector's `.gbapal`/`.4bpp` output visible at all;
    `git status` alone never lists an ignored path.
    """
    return set(_status('--ignored=matching', '--', *INJECTED_DIRS))


def fingerprint(started, ignored_before):
    """{relpath: sha1} for every decomp file THIS injection wrote, plus deletion markers.

    `started` is the clock reading from immediately before the injection ran; an ignored file
    is counted as ours when its mtime is at or after it. Tracked files are judged by CONTENT
    (git status), which is stronger, so mtime never gets a say in those.
    """
    manifest = {}
    for rel in _status():
        path = os.path.join(DECOMP, rel)
        if not os.path.isfile(path):
            continue
        with open(path, 'rb') as fh:
            manifest[rel] = hashlib.sha1(fh.read()).hexdigest()

    ignored_after = _ignored_paths()
    cutoff = started - MTIME_SLACK
    for rel in ignored_after:
        if rel in manifest:
            continue
        path = os.path.join(DECOMP, rel)
        try:
            if not os.path.isfile(path) or os.stat(path).st_mtime < cutoff:
                continue
            with open(path, 'rb') as fh:
                manifest[rel] = hashlib.sha1(fh.read()).hexdigest()
        except OSError:
            continue

    # A stale artifact the injector REMOVES is output too -- a refactor that stops removing it
    # leaves `make` compiling last build's bytes, and no hash of a written file would say so.
    for rel in ignored_before - ignored_after:
        manifest.setdefault(rel, 'DELETED')
    return manifest


def build(stash_caches=True):
    saved = []
    if stash_caches:
        for name in CACHES:
            src = os.path.join(REPO, name)
            if os.path.exists(src):
                dst = src + '.fingerprint-bak'
                os.rename(src, dst)
                saved.append((src, dst))
    try:
        restore_decomp()
        ignored_before = _ignored_paths()
        started = time.time()
        inject()
        return fingerprint(started, ignored_before)
    finally:
        for src, dst in saved:
            if os.path.exists(src):
                subprocess.run(['rm', '-rf', src], check=False)
            os.rename(dst, src)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument('--write', metavar='PATH', help='record a manifest')
    mode.add_argument('--check', metavar='PATH', help='compare against a recorded manifest')
    ap.add_argument('--keep-caches', action='store_true',
                    help='do not hide .injectcache (faster, but measures the cache)')
    args = ap.parse_args()

    manifest = build(stash_caches=not args.keep_caches)

    if args.write:
        with open(args.write, 'w') as fh:
            json.dump(manifest, fh, indent=1, sort_keys=True)
        print('wrote %s: %d injected files' % (args.write, len(manifest)))
        return 0

    with open(args.check) as fh:
        before = json.load(fh)
    added = sorted(set(manifest) - set(before))
    removed = sorted(set(before) - set(manifest))
    changed = sorted(k for k in set(before) & set(manifest) if before[k] != manifest[k])
    if not (added or removed or changed):
        print('IDENTICAL: %d injected files, byte for byte' % len(manifest))
        return 0
    print('INJECTION OUTPUT CHANGED')
    for label, rows in (('only after', added), ('only before', removed), ('differs', changed)):
        for rel in rows[:25]:
            print('  %-12s %s' % (label, rel))
        if len(rows) > 25:
            print('  %-12s ... and %d more' % (label, len(rows) - 25))
    return 1


if __name__ == '__main__':
    sys.exit(main())
