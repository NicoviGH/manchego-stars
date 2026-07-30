"""Regression tests for check_handoff_only_on_main -- the HANDOFF branch guard.

Guards the failure it was written for (2026-07-30): HANDOFF.md describes GLOBAL live
state but is a tracked repo-root file, so every branch gets a private copy. The ch05
merge carried its branch's stale copy onto main and put ch04 back to a "WIP checkpoint"
four committed stages out of date. It had already been caught once on 2026-07-21 and
"mitigated" with a note telling us to sync manually; that failed nine days later.

The interesting cases are not the happy path -- they are the two states that MUST NOT
fail, because a guard that cries wolf gets bypassed:
  * a branch that never touched HANDOFF while main moved on (git's 3-way merge keeps
    main's version, so there is nothing to warn about);
  * a branch whose copy is byte-identical to main's tip (the ideal worktree state).
"""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


# A git subprocess started INSIDE a git hook resolves against the OUTER repo: git exports
# GIT_DIR / GIT_INDEX_FILE / GIT_WORK_TREE while pre-commit runs, and those override cwd.
# Without this, the throwaway fixtures below ran `init` / `config` / `add` / `commit`
# against the REAL repo -- on 2026-07-30 that flipped core.bare=true, overwrote user.name /
# user.email with the fixture's, and left HANDOFF.md staged mid-commit. Exactly the failure
# docs/decisions.md "Operational Gotchas" already records from 2026-07-21. Strip the ambient
# GIT_* vars, target the repo with -C (not cwd), and disable hooks so a fixture commit can
# never re-enter the outer pre-commit.
_GIT_ENV = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}


def _run(repo, *args):
    subprocess.run(['git', '-C', repo, '-c', 'core.hooksPath=/dev/null'] + list(args),
                   check=True, capture_output=True, env=_GIT_ENV)


def _commit(repo, path, body, msg):
    with open(os.path.join(repo, path), 'w') as f:
        f.write(body)
    _run(repo, 'add', path)
    _run(repo, 'commit', '-m', msg)


class HandoffBranchGuard(unittest.TestCase):
    """Exercised against throwaway repos, so the real one's state never leaks in."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        _run(self.tmp, 'init', '-q', '-b', 'main')
        _run(self.tmp, 'config', 'user.email', 't@t')
        _run(self.tmp, 'config', 'user.name', 't')
        _commit(self.tmp, 'HANDOFF.md', 'state v1\n', 'init')
        _commit(self.tmp, 'other.txt', 'x\n', 'other')
        import check
        self.check = check
        self._real_repo = check.REPO
        check.REPO = self.tmp
        # GITHUB_* would otherwise redirect the guard at a CI PR base that isn't here.
        self._env = {k: os.environ.pop(k, None) for k in ('GITHUB_HEAD_REF', 'GITHUB_BASE_REF')}

    def tearDown(self):
        self.check.REPO = self._real_repo
        for k, v in self._env.items():
            if v is not None:
                os.environ[k] = v

    def _state(self):
        return self.check._handoff_branch_state()[0]

    def _fails(self):
        """Captures stdout: the guard prints a 'skipped' note, and `make check` runs these
        tests as subprocesses and surfaces their output -- an escaped note reads as the guard
        misfiring on main."""
        fail, buf = [], io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.check.check_handoff_only_on_main(fail)
        return fail

    def test_main_is_always_allowed_to_write_handoff(self):
        _commit(self.tmp, 'HANDOFF.md', 'state v2\n', 'refresh on main')
        self.assertEqual(self._state(), 'ok')
        self.assertEqual(self._fails(), [])

    def test_branch_that_never_touched_handoff_passes(self):
        _run(self.tmp, 'checkout', '-q', '-b', 'feat/x')
        _commit(self.tmp, 'other.txt', 'y\n', 'unrelated work')
        self.assertEqual(self._state(), 'ok')

    def test_branch_untouched_while_main_moved_on_still_passes(self):
        """The false positive that would get the guard bypassed.

        The branch is behind main's HANDOFF but never edited it, so a 3-way merge keeps
        main's version. Nothing is at risk and nothing may be reported.
        """
        _run(self.tmp, 'checkout', '-q', '-b', 'feat/x')
        _commit(self.tmp, 'other.txt', 'y\n', 'unrelated work')
        _run(self.tmp, 'checkout', '-q', 'main')
        _commit(self.tmp, 'HANDOFF.md', 'state v2 -- main moved\n', 'refresh on main')
        _run(self.tmp, 'checkout', '-q', 'feat/x')
        self.assertEqual(self._state(), 'ok')
        self.assertEqual(self._fails(), [])

    def test_branch_that_edits_handoff_is_rejected(self):
        """The actual ch05 failure: a branch authoring its own live state."""
        _run(self.tmp, 'checkout', '-q', '-b', 'feat/x')
        _commit(self.tmp, 'HANDOFF.md', 'branch-local state\n', 'refresh on the branch')
        self.assertEqual(self._state(), 'diverged')
        fail = self._fails()
        self.assertEqual(len(fail), 1)
        self.assertIn('HANDOFF.md', fail[0])
        self.assertIn('git checkout main -- HANDOFF.md', fail[0])

    def test_branch_synced_to_mains_tip_passes(self):
        """The ideal worktree state, and the reason the rule is livable.

        The branch edited HANDOFF, but only to match main exactly -- merging it is a no-op,
        and people reading HANDOFF in their worktree see true live state.
        """
        _run(self.tmp, 'checkout', '-q', '-b', 'feat/x')
        _commit(self.tmp, 'HANDOFF.md', 'branch-local state\n', 'drifted')
        _run(self.tmp, 'checkout', '-q', 'main')
        _commit(self.tmp, 'HANDOFF.md', 'state v2\n', 'refresh on main')
        _run(self.tmp, 'checkout', '-q', 'feat/x')
        _run(self.tmp, 'checkout', 'main', '--', 'HANDOFF.md')
        _run(self.tmp, 'commit', '-am', 'sync HANDOFF to main')
        self.assertEqual(self._state(), 'ok')
        self.assertEqual(self._fails(), [])

    def test_staged_edit_is_caught_before_it_becomes_a_commit(self):
        """Pre-commit runs `check.py`, so the guard has to see the index, not just history."""
        _run(self.tmp, 'checkout', '-q', '-b', 'feat/x')
        with open(os.path.join(self.tmp, 'HANDOFF.md'), 'w') as f:
            f.write('about to drift\n')
        _run(self.tmp, 'add', 'HANDOFF.md')
        self.assertEqual(self._state(), 'diverged')
        self.assertIn('staged', self._fails()[0])

    def test_missing_base_is_skipped_not_failed(self):
        """A guard that cannot see the base must not invent a violation."""
        _run(self.tmp, 'checkout', '-q', '-b', 'feat/x')
        _commit(self.tmp, 'HANDOFF.md', 'branch-local\n', 'drifted')
        _run(self.tmp, 'branch', '-D', 'main')
        state, reason = self.check._handoff_branch_state()
        self.assertEqual(state, 'unknown')
        self.assertTrue(reason)
        self.assertEqual(self._fails(), [])


if __name__ == '__main__':
    unittest.main()
