#!/usr/bin/env python3
"""Tests for tools/build_tree.py -- the tree the injector writes and `make` compiles (#408).

Run:  python3 tools/test_build_tree.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_tree  # noqa: E402
from inject.decomp import git_env  # noqa: E402


def git(cwd, *args):
    return subprocess.run(['git', '-C', cwd] + list(args), env=git_env(), check=True,
                          capture_output=True, text=True).stdout.strip()


class TheBuildTree(unittest.TestCase):
    """A throwaway repo stands in for the submodule; the tree is a worktree of it."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.sub = os.path.join(self.tmp, 'fireemblem8u')
        self.tree = os.path.join(self.tmp, 'build', 'fireemblem8u')
        os.makedirs(os.path.join(self.sub, 'src'))
        git(self.sub, 'init', '-q')
        with open(os.path.join(self.sub, '.gitignore'), 'w') as fh:
            fh.write('baserom.gba\n')
        self._commit('src/a.c', 'vanilla\n')
        with open(os.path.join(self.sub, 'baserom.gba'), 'wb') as fh:
            fh.write(b'rom')
        for name, value in (('SUBMODULE', self.sub), ('DECOMP', self.tree)):
            patcher = mock.patch.object(build_tree, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def _commit(self, rel, text):
        with open(os.path.join(self.sub, rel), 'w') as fh:
            fh.write(text)
        git(self.sub, 'add', '-A')
        git(self.sub, '-c', 'user.name=t', '-c', 'user.email=t@t', 'commit', '-qm', rel)
        return git(self.sub, 'rev-parse', 'HEAD')

    def test_it_is_a_checkout_of_the_submodule_that_leaves_the_submodule_clean(self):
        build_tree.ensure(verbose=False)
        self.assertEqual(git(self.tree, 'rev-parse', 'HEAD'), git(self.sub, 'rev-parse', 'HEAD'))
        with open(os.path.join(self.tree, 'src', 'a.c'), 'w') as fh:
            fh.write('injected\n')                        # what a build does to the tree
        self.assertEqual(git(self.sub, 'status', '--porcelain'), '')

    def test_it_follows_a_submodule_bump_over_an_injected_tree(self):
        build_tree.ensure(verbose=False)
        with open(os.path.join(self.tree, 'src', 'a.c'), 'w') as fh:
            fh.write('injected\n')
        with open(os.path.join(self.tree, 'src', 'ours.c'), 'w') as fh:
            fh.write('an injected new file\n')
        bumped = self._commit('src/a.c', 'vanilla, newer\n')
        build_tree.ensure(verbose=False)
        self.assertEqual(git(self.tree, 'rev-parse', 'HEAD'), bumped)
        with open(os.path.join(self.tree, 'src', 'a.c')) as fh:
            self.assertEqual(fh.read(), 'vanilla, newer\n')
        self.assertFalse(os.path.exists(os.path.join(self.tree, 'src', 'ours.c')))

    def test_the_toolchain_is_linked_from_the_submodule(self):
        build_tree.ensure(verbose=False)
        link = os.path.join(self.tree, 'baserom.gba')
        self.assertTrue(os.path.islink(link))
        self.assertEqual(os.path.realpath(link),
                         os.path.realpath(os.path.join(self.sub, 'baserom.gba')))
        build_tree.ensure(verbose=False)                   # idempotent
        self.assertTrue(os.path.islink(link))

    def test_its_outputs_are_what_git_ignores_minus_links_and_injected_files(self):
        # What CI caches (#408): the compile's outputs, never the injector's writes (the next
        # build injects those afresh) and never the toolchain links.
        build_tree.ensure(verbose=False)
        ours, obj = (os.path.join(self.tree, 'src', n) for n in ('ours.c', 'ours.o'))
        for path in (ours, obj):
            with open(path, 'w') as fh:
                fh.write('x')
        with mock.patch('inject.warm.load_compiled', lambda: {ours: (0, b'')}):
            self.assertEqual(sorted(build_tree.outputs()), ['src/ours.o'])

    def test_a_deleted_tree_is_recreated(self):
        build_tree.ensure(verbose=False)
        shutil.rmtree(os.path.dirname(self.tree))
        build_tree.ensure(verbose=False)                   # the stale worktree entry is pruned
        self.assertTrue(os.path.exists(os.path.join(self.tree, 'src', 'a.c')))


    def test_a_moved_checkout_is_repaired(self):
        # The tree's .git file and its admin entry hold absolute paths: moving or renaming
        # the checkout broke every `make` and the pre-commit hook with a traceback (review).
        build_tree.ensure(verbose=False)
        with open(os.path.join(self.tree, 'src', 'a.c'), 'w') as fh:
            fh.write('injected\n')
        moved = self.tmp + '-moved'
        os.rename(self.tmp, moved)
        self.addCleanup(shutil.rmtree, moved, True)
        sub, tree = (os.path.join(moved, os.path.relpath(p, self.tmp))
                     for p in (self.sub, self.tree))
        with mock.patch.object(build_tree, 'SUBMODULE', sub), \
                mock.patch.object(build_tree, 'DECOMP', tree):
            build_tree.ensure(verbose=False)
        self.assertEqual(git(tree, 'rev-parse', 'HEAD'), git(sub, 'rev-parse', 'HEAD'))
        with open(os.path.join(tree, 'src', 'a.c')) as fh:
            self.assertEqual(fh.read(), 'injected\n', 'repaired in place, not recreated')

if __name__ == '__main__':
    unittest.main()
