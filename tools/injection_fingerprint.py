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
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject.decomp import git_env                                     # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECOMP = os.path.join(REPO, 'fireemblem8u')
CAMPAIGN = 'rime-of-the-frostmaiden'

# Injection rewrites these; the caches below make a second run skip work, which is exactly
# what must NOT happen while fingerprinting.
CACHES = ('.injectcache', '.build-scopes.json')


def restore_decomp():
    """Put the decomp back to HEAD so the injector has to do all of its work."""
    subprocess.run(['git', '-C', DECOMP, 'checkout', '--', '.'], env=git_env(), check=True)
    subprocess.run(['git', '-C', DECOMP, 'clean', '-fdq', '--',
                    'src', 'data', 'include', 'graphics', 'texts'],
                   env=git_env(), check=True)


def inject():
    env = dict(os.environ)
    subprocess.run([sys.executable, os.path.join(REPO, 'tools', 'build_campaign.py'),
                    '--campaign', CAMPAIGN],
                   cwd=REPO, env=env, check=True, stdout=subprocess.DEVNULL)


def fingerprint():
    """{relpath: sha1} for every decomp file the injection changed or added."""
    out = subprocess.run(['git', '-C', DECOMP, 'status', '--porcelain', '-z', '-uall'],
                         env=git_env(), capture_output=True, text=True, check=True).stdout
    manifest = {}
    for entry in out.split('\0'):
        if not entry.strip():
            continue
        rel = entry[3:]
        path = os.path.join(DECOMP, rel)
        if not os.path.isfile(path):
            continue
        with open(path, 'rb') as fh:
            manifest[rel] = hashlib.sha1(fh.read()).hexdigest()
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
        inject()
        return fingerprint()
    finally:
        for src, dst in saved:
            if os.path.exists(src):
                subprocess.run(['rm', '-rf', src], check=False)
            os.rename(dst, src)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--write', metavar='PATH', help='record a manifest')
    ap.add_argument('--check', metavar='PATH', help='compare against a recorded manifest')
    ap.add_argument('--keep-caches', action='store_true',
                    help='do not hide .injectcache (faster, but measures the cache)')
    args = ap.parse_args()
    if not (args.write or args.check):
        ap.error('one of --write or --check is required')

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
