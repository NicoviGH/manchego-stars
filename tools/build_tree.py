#!/usr/bin/env python3
"""build_tree.py ensure|toolchain -- the tree the injector writes and `make` compiles (#408).

`build/fireemblem8u` is a git worktree of the `fireemblem8u` submodule, detached at the
submodule's commit. The injector writes there and the ROM is compiled there, so the
submodule's own working tree stays vanilla. Because it is a real checkout of the same
commit, `git status` / `git checkout HEAD --` / `git show HEAD:` work in it exactly as they
did in the submodule; the worktree's metadata lives in the submodule's gitdir, not in its
working tree, so `git -C fireemblem8u status` stays clean.

  ensure      create the tree, follow a submodule bump, link the toolchain (every build)
  toolchain   print the gitignored toolchain paths, one per line (tools/worktree-setup.sh)
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inject.decomp import DECOMP, git_env, SUBMODULE  # noqa: E402

# Gitignored, so absent from any fresh checkout: built once by tools/setup-toolchain.sh in the
# submodule. Static native binaries that a build only reads (the decomp's Makefile has no rule
# that rebuilds one), so the tree links them rather than copying them.
TOOLCHAIN = (
    'tools/agbcc',
    'tools/aif2pcm/aif2pcm',
    'tools/bin2c/bin2c',
    'tools/gbagfx/gbagfx',
    'tools/jsonproc/jsonproc',
    'tools/mid2agb/mid2agb',
    'tools/scaninc/scaninc',
    'tools/textencode/textencode',
    'baserom.gba',
)


def _git(cwd, *args, capture=False):
    run = subprocess.run(['git', '-C', cwd] + list(args), env=git_env(), check=True,
                         capture_output=capture, text=True)
    return run.stdout.strip() if capture else None


def _link_toolchain(verbose):
    for rel in TOOLCHAIN:
        src, dst = os.path.join(SUBMODULE, rel), os.path.join(DECOMP, rel)
        if not os.path.lexists(src):
            if verbose:
                print('  build tree: no %s in the submodule (tools/setup-toolchain.sh)' % rel)
            continue
        target = os.path.relpath(src, os.path.dirname(dst))
        if os.path.islink(dst) and os.readlink(dst) == target:
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.lexists(dst):
            os.remove(dst)
        os.symlink(target, dst)


def _tree_head():
    """The tree's commit, repairing its link first if the checkout was moved: the worktree's
    `.git` file and its entry in the submodule's gitdir both hold absolute paths."""
    try:
        return _git(DECOMP, 'rev-parse', 'HEAD', capture=True)
    except subprocess.CalledProcessError:
        pass
    try:
        _git(SUBMODULE, 'worktree', 'repair', DECOMP, capture=True)
        return _git(DECOMP, 'rev-parse', 'HEAD', capture=True)
    except subprocess.CalledProcessError:
        sys.exit('ERROR: %s is not a working git worktree of %s, and `git worktree repair` '
                 'could not fix it. Delete %s and build again; it is recreated from the '
                 'submodule.' % (DECOMP, SUBMODULE, os.path.dirname(DECOMP)))


def ensure(verbose=True):
    """Make the build tree exist at the submodule's commit, with the toolchain linked."""
    head = _git(SUBMODULE, 'rev-parse', 'HEAD', capture=True)
    if not os.path.exists(os.path.join(DECOMP, '.git')):
        os.makedirs(os.path.dirname(DECOMP), exist_ok=True)
        _git(SUBMODULE, 'worktree', 'prune')     # a deleted build/ leaves a stale entry
        _git(SUBMODULE, 'worktree', 'add', '--detach', '--quiet', DECOMP, head)
        if verbose:
            print('  build tree: created %s at %s' % (os.path.relpath(DECOMP), head[:12]))
    elif _tree_head() != head:
        # A submodule bump. Drop the last injection first -- a checkout refuses to move over
        # modified files -- then follow; the next injection rewrites everything anyway.
        _git(DECOMP, 'checkout', '--quiet', 'HEAD', '--', '.')
        _git(DECOMP, 'clean', '-fdq')
        _git(DECOMP, 'checkout', '--quiet', '--detach', head)
        if verbose:
            print('  build tree: followed the submodule to %s' % head[:12])
    _link_toolchain(verbose)


def main(argv):
    if argv == ['ensure']:
        ensure()
    elif argv == ['toolchain']:
        print('\n'.join(TOOLCHAIN))
    else:
        sys.exit('usage: build_tree.py ensure|toolchain')


if __name__ == '__main__':
    main(sys.argv[1:])
