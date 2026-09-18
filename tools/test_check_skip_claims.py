#!/usr/bin/env python3
"""Tests that a guard which SKIPS cannot lie about who covers it (#379).

Four guards in `tools/check.py` cannot run on the CI job that runs `tools/check.py` -- the
`checks` job installs pyyaml, checks out no submodule, and these four import `build_campaign`,
`difficulty`, `map_placement_preview` or `chapter_status`. Each printed a reassuring sentence
and returned:

    check_documented_tileset: skipping (No module named 'PIL'; the `tests` job's `make test`
    covers it)

The sentence was true when it was written and nothing held it there. Fixture-ify or delete the
test it means, and the guard covers nothing on either job while still printing the reassurance.
This repo has shipped that exact shape before: `check_tile_changes_outlive_the_retarget` ran
only through its own test file's subprocess, which no-ops when `fireemblem8u/src` is absent --
the lightweight job it existed to protect.

So the claim is a DECLARATION now (`SKIP_COVERAGE`), and these tests are what make it a gate:
the named test must exist, live in a file `run_tests.py` actually collects, and **call the guard
it claims to cover**. Renaming it, deleting it, or quietly turning it into a fixture-only test
breaks the build instead of the coverage.

The second half is the skip PATH itself. #373's review caught a guard whose skip clause caught
`ImportError` while the real failure was `FileNotFoundError` -- `map_placement_preview` opens
the decomp's `terrains.h` at module scope -- so on the very job it was written for it would have
raised instead of skipped, reddening every PR while never running. Every one of these four had
the same three lines, and no test exercised any of them: they only ever ran where the import
succeeds. Here they are driven with the module genuinely unimportable.

Run: python3 tools/test_check_skip_claims.py
"""
import ast
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check

TOOLS = os.path.dirname(os.path.abspath(__file__))
CHECK_SRC = os.path.join(TOOLS, 'check.py')


def _function_source(path, name):
    """The source of a top-level or method `def name`, or None."""
    with open(path, encoding='utf-8') as fh:
        text = fh.read()
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name:
            return ast.get_source_segment(text, node)
    return None


class TheClaimIsDeclared(unittest.TestCase):

    def test_the_four_known_skippers_declare_a_covering_test(self):
        for guard in ('check_documented_tileset', 'check_personal_line_injection_routes',
                      'check_rescue_targets', 'check_rescue_fuse_forecast'):
            self.assertIn(guard, check.SKIP_COVERAGE)

    def test_no_guard_hand_rolls_a_coverage_claim(self):
        """The registry is only the truth if it is the ONLY way to make the claim.

        A guard that prints its own "the tests job covers it" is back to a sentence nothing
        checks, which is the whole bug.

        The registry's own two functions are exempt, the same way `check.py` is exempt from
        the `DEAD_CONCEPTS` scan it hosts: the helper emits the phrase by construction and the
        gate's docstring QUOTES the message it exists to replace. A guard that rejects its own
        warning is worse than none -- this file's own first run proved it by flagging them.
        """
        with open(CHECK_SRC, encoding='utf-8') as fh:
            rest = fh.read()
        for own in ('_skip_covered_elsewhere', 'check_skip_claims_name_a_live_test'):
            rest = rest.replace(_function_source(CHECK_SRC, own) or '\0', '')
        offenders = [line.strip() for line in rest.split('\n')
                     if re.search(r'covers (it|this gate)', line)
                     and 'SKIP_COVERAGE' not in line and not line.strip().startswith('#')]
        self.assertEqual([], offenders)


class TheNamedTestMustReallyCoverIt(unittest.TestCase):

    def test_every_claim_names_a_test_that_exists(self):
        for guard, (rel, name) in check.SKIP_COVERAGE.items():
            path = os.path.join(check.REPO, rel)
            self.assertTrue(os.path.isfile(path), '%s -> %s' % (guard, rel))
            self.assertIsNotNone(_function_source(path, name),
                                 '%s claims %s::%s, which does not exist' % (guard, rel, name))

    def test_every_claimed_test_actually_calls_the_guard(self):
        """The tie that makes fixture-ifying it a build failure rather than a silent hole."""
        for guard, (rel, name) in check.SKIP_COVERAGE.items():
            src = _function_source(os.path.join(check.REPO, rel), name)
            self.assertIn(guard, src or '',
                          '%s::%s does not call %s' % (rel, name, guard))

    def test_every_claimed_test_lives_in_a_file_run_tests_collects(self):
        import run_tests
        collected = {os.path.relpath(p, check.REPO) for p in run_tests.test_files()}
        for guard, (rel, _name) in check.SKIP_COVERAGE.items():
            self.assertIn(rel, collected, '%s claims an uncollected file' % guard)


class TheGateCatchesABrokenClaim(unittest.TestCase):
    """Rule out the failure mode of a gate that only ever passes."""

    def _run_with(self, table):
        original = check.SKIP_COVERAGE
        try:
            check.SKIP_COVERAGE = table
            fail = []
            check.check_skip_claims_name_a_live_test(fail)
            return fail
        finally:
            check.SKIP_COVERAGE = original

    def test_a_claim_naming_a_deleted_test_is_reported(self):
        fail = self._run_with({'check_documented_tileset':
                               ('tools/test_check_chapter_schema.py', 'test_deleted_ages_ago')})
        self.assertTrue(fail)

    def test_a_claim_naming_a_missing_file_is_reported(self):
        fail = self._run_with({'check_documented_tileset':
                               ('tools/test_not_a_file.py', 'test_x')})
        self.assertTrue(fail)

    def test_a_test_that_stopped_calling_the_guard_is_reported(self):
        """Fixture-ified: the test still exists and no longer exercises the gate."""
        fail = self._run_with({'check_documented_tileset':
                               ('tools/test_check_chapter_schema.py',
                                'test_personal_line_routes_gate_passes')})
        self.assertTrue(fail)

    def test_a_test_decorated_to_SKIP_is_reported(self):
        """Coverage that never runs is not coverage, and it stays green forever."""
        import tempfile
        d = tempfile.mkdtemp(dir=os.path.join(check.REPO, 'tools'))
        rel = os.path.join('tools', os.path.basename(d), 'test_fixture.py')
        with open(os.path.join(check.REPO, rel), 'w') as fh:
            fh.write('import unittest\n@unittest.skip("x")\n'
                     'def test_it():\n    check.check_documented_tileset([])\n')
        try:
            original = check.SKIP_COVERAGE
            collected = __import__('run_tests').test_files
            check.SKIP_COVERAGE = {'check_documented_tileset': (rel, 'test_it')}
            __import__('run_tests').test_files = lambda: [os.path.join(check.REPO, rel)]
            fail = []
            check.check_skip_claims_name_a_live_test(fail)
            self.assertTrue(any('SKIP' in f for f in fail), fail)
        finally:
            check.SKIP_COVERAGE = original
            __import__('run_tests').test_files = collected
            import shutil
            shutil.rmtree(d, ignore_errors=True)

    def test_a_guard_name_surviving_only_in_a_COMMENT_is_not_a_call(self):
        """The substring hole: fixture-ify the body, leave the name in a docstring."""
        node = ast.parse('def t():\n    """calls check_documented_tileset"""\n    pass\n')
        fn = node.body[0]
        self.assertFalse(check._calls_guard(fn, 'check_documented_tileset'))

    def test_a_real_call_is_recognised_through_the_module_attribute(self):
        node = ast.parse('def t():\n    check.check_documented_tileset([])\n')
        self.assertTrue(check._calls_guard(node.body[0], 'check_documented_tileset'))

    def test_every_call_site_of_the_helper_is_registered(self):
        """A fifth guard copying the pattern without a table entry used to be green
        locally and on `tests`, and raise KeyError only on `checks`."""
        for guard, claimed in check._helper_call_sites():
            self.assertEqual(guard, claimed)
            self.assertIn(claimed, check.SKIP_COVERAGE)

    def test_an_unregistered_guard_does_not_raise_on_the_lightweight_job(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            check._skip_covered_elsewhere('check_not_registered', ImportError('x'))
        self.assertIn('NO COVERAGE DECLARED', buf.getvalue())

    def test_the_exception_set_is_the_two_that_really_happen(self):
        """OSError was too wide: a permission error or a path broken by a refactor must
        ESCAPE and be reported as a guard that could not run, not printed as a delegation."""
        self.assertEqual((ImportError, FileNotFoundError), check.SKIP_IMPORT_ERRORS)

    def test_a_covering_test_that_cannot_prove_the_guard_RAN_is_reported(self):
        """The vacuity hole: `assertEqual([], fail)` passes on a run that checked nothing."""
        fail = self._run_with({'check_rescue_targets':
                               ('tools/test_check_skip_claims.py',
                                'test_a_real_call_is_recognised_through_the_module_attribute')})
        self.assertTrue(fail)

    def test_the_live_table_passes(self):
        fail = []
        check.check_skip_claims_name_a_live_test(fail)
        self.assertEqual([], fail)


class TheSkipPathItself(unittest.TestCase):
    """Driven with the module genuinely unavailable, not by reading the `except` clause."""

    def _guard_with_broken_import(self, guard, module, exc):
        """Run `guard` with `module` genuinely unimportable, and report what it printed.

        `find_spec` raises rather than returning None, which is how a module that blows up
        while being located behaves; the legacy `find_module`/`load_module` pair is gone in
        3.12 and would make this test rot silently.

        The printed output is returned because it is the only evidence the SKIP PATH was
        taken at all. Asserting `fail == []` alone passes just as happily when the import
        succeeded and the guard ran clean, which would make this test prove nothing.
        """
        import io
        from contextlib import redirect_stdout

        saved = sys.modules.pop(module, None)

        class Raiser:
            def find_spec(self, name, path=None, target=None):
                if name == module:
                    raise exc
                return None

        hook = Raiser()
        sys.meta_path.insert(0, hook)
        buf = io.StringIO()
        try:
            fail = []
            with redirect_stdout(buf):
                getattr(check, guard)(fail)
            return fail, buf.getvalue()
        finally:
            sys.meta_path.remove(hook)
            sys.modules.pop(module, None)
            if saved is not None:
                sys.modules[module] = saved

    def test_a_missing_dependency_skips_rather_than_raising(self):
        fail, out = self._guard_with_broken_import(
            'check_documented_tileset', 'build_campaign', ImportError("No module named 'PIL'"))
        self.assertEqual([], fail)
        self.assertIn('check_documented_tileset: skipping', out)

    def test_the_skip_message_names_the_test_that_covers_it(self):
        """So the reader of a CI log can go and read the coverage, not just be told it exists."""
        _fail, out = self._guard_with_broken_import(
            'check_documented_tileset', 'build_campaign', ImportError("No module named 'PIL'"))
        rel, name = check.SKIP_COVERAGE['check_documented_tileset']
        self.assertIn(rel, out)
        self.assertIn(name, out)

    def test_a_missing_DECOMP_FILE_skips_too_and_does_not_escape(self):
        """#373's bug, in the shape it really happens: a module that OPENS the decomp at
        import time raises FileNotFoundError, not ImportError, when the submodule is absent --
        so a clause catching only ImportError reddens the job it was written to protect."""
        fail, out = self._guard_with_broken_import(
            'check_documented_tileset', 'build_campaign',
            FileNotFoundError(2, 'No such file or directory',
                              'fireemblem8u/include/constants/terrains.h'))
        self.assertEqual([], fail)
        self.assertIn('check_documented_tileset: skipping', out)

    def test_every_registered_guard_survives_an_unimportable_dependency(self):
        """All four, not just the one -- they shared the bug because they shared the shape."""
        modules = {'check_documented_tileset': 'build_campaign',
                   'check_personal_line_injection_routes': 'build_campaign',
                   'check_rescue_targets': 'difficulty',
                   'check_rescue_fuse_forecast': 'rescue_forecast'}
        for guard, module in modules.items():
            fail, out = self._guard_with_broken_import(
                guard, module, FileNotFoundError(2, 'No such file or directory', 'terrains.h'))
            self.assertEqual([], fail, guard)
            self.assertIn('%s: skipping' % guard, out)


if __name__ == '__main__':
    unittest.main(verbosity=2)
