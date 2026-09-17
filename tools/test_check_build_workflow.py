#!/usr/bin/env python3
"""Tests for check_build_workflow_filters_agree (#382).

A gate that only ever runs against a passing tree has never demonstrated it can fail. This
one guards a filter whose failure mode is silent and backwards: if `pull_request` ignored a
path that `push` did not, a PR would skip the ROM build while the merge to main ran it --
so main breaks having been green on the PR. The guard is worth exactly as much as its
ability to say so, which is what these tests pin.

The tree's real build.yml is the passing oracle; every failing case is a synthetic workflow
written to a temp file, because the point is to see the guard go red.

Run: python3 tools/test_check_build_workflow.py
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check                                                          # noqa: E402

WORKFLOW = os.path.join(check.REPO, '.github', 'workflows', 'build.yml')


class TheRealWorkflowPasses(unittest.TestCase):

    def test_the_tree_is_clean(self):
        fail = []
        check.check_build_workflow_filters_agree(fail)
        self.assertEqual([], fail)

    def test_the_workflow_it_guards_actually_exists(self):
        """The guard reports a missing file rather than passing vacuously, but the tree
        should never be in that state."""
        self.assertTrue(os.path.exists(WORKFLOW), WORKFLOW)


class ItCatchesWhatItIsFor(unittest.TestCase):
    """Each case swaps in a synthetic build.yml and asserts the guard goes red."""

    def _run(self, body):
        with tempfile.TemporaryDirectory() as tmp:
            wf_dir = os.path.join(tmp, '.github', 'workflows')
            os.makedirs(wf_dir)
            with open(os.path.join(wf_dir, 'build.yml'), 'w', encoding='utf-8') as fh:
                fh.write(body)
            real = check.REPO
            check.REPO = tmp
            try:
                fail = []
                check.check_build_workflow_filters_agree(fail)
                return fail
            finally:
                check.REPO = real

    def test_disagreeing_lists_fail(self):
        fail = self._run(
            "on:\n"
            "  push:\n    branches: [main]\n    paths-ignore:\n      - 'HANDOFF.md'\n"
            "  pull_request:\n    paths-ignore:\n      - 'HANDOFF.md'\n      - 'docs/PRD.md'\n"
            "jobs: {}\n")
        self.assertEqual(1, len(fail), fail)
        self.assertIn('disagree', fail[0])
        self.assertIn('docs/PRD.md', fail[0])

    def test_a_broad_glob_fails(self):
        fail = self._run(
            "on:\n"
            "  push:\n    branches: [main]\n    paths-ignore:\n      - '**.md'\n"
            "  pull_request:\n    paths-ignore:\n      - '**.md'\n"
            "jobs: {}\n")
        self.assertEqual(1, len(fail), fail)
        self.assertIn('inert files, not globs', fail[0])

    def test_a_missing_side_fails(self):
        """push filtered, pull_request not -- main and PRs would build different things."""
        fail = self._run(
            "on:\n"
            "  push:\n    branches: [main]\n    paths-ignore:\n      - 'HANDOFF.md'\n"
            "  pull_request:\n"
            "jobs: {}\n")
        self.assertEqual(1, len(fail), fail)
        self.assertIn('both push and pull_request', fail[0])

    def test_a_missing_workflow_fails_rather_than_passing_quietly(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = check.REPO
            check.REPO = tmp
            try:
                fail = []
                check.check_build_workflow_filters_agree(fail)
            finally:
                check.REPO = real
        self.assertEqual(1, len(fail), fail)
        self.assertIn('missing', fail[0])


class TheFilterStaysSafe(unittest.TestCase):
    """The allowlist is only safe while it names files nothing derives from."""

    def test_generated_docs_are_not_ignored(self):
        import yaml
        with open(WORKFLOW, encoding='utf-8') as fh:
            wf = yaml.safe_load(fh)
        ignored = (wf.get(True) or wf.get('on'))['push']['paths-ignore']
        for derived in ('docs/scenes/ch05.md', 'AGENTS.md', 'docs/CHAPTERS.md',
                        'docs/CLASSES.md'):
            self.assertNotIn(derived, ignored,
                             '%s is derived or linted -- ignoring it skips the job whose '
                             'tests police it' % derived)


if __name__ == '__main__':
    unittest.main()
