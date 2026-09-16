"""Regression tests for check.py's per-check isolation (#372).

`main()` ran ~30 checks in a bare loop, so ONE raising check took down the whole drift
guard and every check queued after it -- a raw traceback, a non-zero exit naming nothing,
and ~29 gates that silently never ran. That is why five review rounds on #371 each found a
defect in code written to make a single guard defensive: with no isolation every guard is
load-bearing for the entire gate, so any wrong assumption about an input's shape becomes a
total crash rather than one line of output.

The design call this file pins down (#372, Nicolas's recommendation on the issue):

  * an errored check GOES IN `fail`, because a check that could not run is not a check that
    passed -- the alternative (print and continue) is the silently-green gate that #371 kept
    hitting;
  * `fail` gets ONE readable line, the full traceback goes to stderr, so CI output stays
    scannable without losing the detail that makes the crash fixable;
  * every other check still runs;
  * a clean run is byte-identical to the old bare loop -- isolation may not change what a
    passing gate says.
"""
import io
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import check


def _quietly(checks):
    """run_checks with stderr captured -- returns (fail, stderr)."""
    buf = io.StringIO()
    with redirect_stderr(buf):
        fail = check.run_checks(checks)
    return fail, buf.getvalue()


class PerCheckIsolation(unittest.TestCase):

    def test_a_raising_check_does_not_stop_the_ones_after_it(self):
        """The outage itself: ~29 gates behind the raiser never ran."""
        ran = []

        def check_before(fail):
            ran.append('before')

        def check_boom(fail):
            ran.append('boom')
            raise TypeError("'<' not supported between 'NoneType' and 'str'")

        def check_after(fail):
            ran.append('after')

        fail, _ = _quietly([check_before, check_boom, check_after])
        self.assertEqual(ran, ['before', 'boom', 'after'])

    def test_a_raising_check_reds_the_build_and_names_itself(self):
        """A check that cannot run is not a check that passed."""
        def check_boom(fail):
            raise AttributeError("'list' object has no attribute 'get'")

        fail, _ = _quietly([check_boom])
        self.assertEqual(len(fail), 1)
        self.assertIn('check_boom', fail[0])
        self.assertIn('AttributeError', fail[0])
        self.assertIn("'list' object has no attribute 'get'", fail[0])

    def test_the_error_is_one_line_and_the_traceback_goes_to_stderr(self):
        """CI prints `fail` as a bullet list; a pasted traceback there is unreadable."""
        def check_boom(fail):
            raise ValueError('bad shape')

        fail, err = _quietly([check_boom])
        self.assertNotIn('\n', fail[0])
        self.assertIn('Traceback', err)
        self.assertIn('check_boom', err)

    def test_findings_a_check_reported_before_raising_are_kept(self):
        """Half a check's answer is still evidence; it must not be dropped on the floor."""
        def check_boom(fail):
            fail.append('a real finding')
            raise RuntimeError('then it died')

        fail, _ = _quietly([check_boom])
        self.assertEqual(len(fail), 2)
        self.assertEqual(fail[0], 'a real finding')

    def test_a_clean_run_reports_exactly_what_the_checks_appended(self):
        """Isolation may not change what a passing -- or plainly-failing -- gate says."""
        def check_clean(fail):
            pass

        def check_drifted(fail):
            fail.append('docs/x.md cites a tool that does not exist')

        fail, err = _quietly([check_clean, check_drifted])
        self.assertEqual(fail, ['docs/x.md cites a tool that does not exist'])
        self.assertEqual(err, '')

    def test_an_interrupt_still_aborts_the_whole_run(self):
        """Ctrl-C is the operator talking, not a check failing."""
        ran = []

        def check_interrupted(fail):
            raise KeyboardInterrupt

        def check_after(fail):
            ran.append('after')

        with self.assertRaises(KeyboardInterrupt):
            _quietly([check_interrupted, check_after])
        self.assertEqual(ran, [])

    def test_main_runs_the_authoritative_list_through_run_checks(self):
        """`CHECKS` is only authoritative if `main()` is what runs it.

        Asserting the tuple's shape proves nothing about the gate: a bare loop reintroduced
        in `main()` would pass every other test in this file. So this pins the call.
        """
        seen = []
        real = check.run_checks
        check.run_checks = lambda checks, fail=None: seen.append(checks) or []
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = check.main()
        finally:
            check.run_checks = real
        self.assertEqual(seen, [check.CHECKS])
        self.assertEqual(rc, 0)
        self.assertIn('drift check: clean', buf.getvalue())

    def test_main_reds_and_lists_every_finding_it_was_handed(self):
        """The other half of `main()`'s contract, unchanged by isolation."""
        real = check.run_checks
        check.run_checks = lambda checks, fail=None: ['first drift', 'second drift']
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = check.main()
        finally:
            check.run_checks = real
        self.assertEqual(rc, 1)
        self.assertIn('DRIFT (2)', buf.getvalue())
        self.assertIn('first drift', buf.getvalue())
        self.assertIn('second drift', buf.getvalue())


class EveryGateIsRegistered(unittest.TestCase):
    """A check defined but left out of `CHECKS` never runs, and nothing says so.

    That is how `check_tile_changes_outlive_the_retarget` shipped: it executed only as a side
    effect of `check_tests_pass` re-invoking its test file, which no-ops when
    `fireemblem8u/src` is absent -- exactly the lightweight CI job it existed to protect.
    Four checks carry their own hand-written registration test; the other 35 carried nothing,
    and hoisting the list to a module-level `CHECKS` is what makes the question answerable in
    one place for all of them.
    """

    def test_the_live_gate_registers_every_check_it_defines(self):
        fail = []
        check.check_every_gate_is_registered(fail)
        self.assertEqual(fail, [])

    def test_the_guard_registers_itself(self):
        self.assertIn(check.check_every_gate_is_registered, check.CHECKS)

    def test_a_defined_but_unregistered_gate_is_reported(self):
        def check_zzz_probe(fail):
            pass

        # `__module__` is what the guard reads to mean "defined in check.py" -- so an
        # imported `check_*` from elsewhere is not demanded of the tuple. The probe has to
        # carry check.py's attribution to stand in for a check defined there.
        check_zzz_probe.__module__ = check.__name__
        check.check_zzz_probe = check_zzz_probe
        try:
            fail = []
            check.check_every_gate_is_registered(fail)
        finally:
            del check.check_zzz_probe
        self.assertEqual(len(fail), 1, fail)
        self.assertIn('check_zzz_probe', fail[0])
        self.assertIn('CHECKS', fail[0])


if __name__ == '__main__':
    unittest.main()
