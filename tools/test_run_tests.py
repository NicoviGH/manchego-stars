#!/usr/bin/env python3
"""Tests for tools/run_tests.py's read records (#579): the pre-commit hook runs only the tests
a staged path can reach, so what a test read must be recorded faithfully and an unknown must
always run.

Run:  python3 tools/test_run_tests.py
"""
import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_tests                                                       # noqa: E402

REPO = run_tests.REPO


class Records(unittest.TestCase):
    """A test file run through run_one leaves a record of what it read, listed and globbed."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(dir=os.path.join(REPO, 'build'))
        self.addCleanup(shutil.rmtree, self.tmp)
        self.traces = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.traces)
        patcher = mock.patch.object(run_tests, 'TRACE_DIR', self.traces)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_test_file(self, body):
        path = os.path.join(self.tmp, 'test_probe.py')
        with open(path, 'w') as fh:
            fh.write(textwrap.dedent(body))
        rel, out = run_tests.run_one(path)
        return rel, out

    def record(self, rel):
        with open(run_tests.trace_path(rel)) as fh:
            return json.load(fh)

    def test_reads_lists_and_globs_are_recorded(self):
        rel, out = self.run_test_file('''
            import glob, os
            open(os.path.join(%r, 'AGENTS.md')).read()
            os.listdir(os.path.join(%r, 'docs'))
            glob.glob(os.path.join(%r, 'campaigns', '*', 'campaign.yaml'))
        ''' % (REPO, REPO, REPO))
        self.assertIsNone(out)
        rec = self.record(rel)
        self.assertIn('AGENTS.md', rec['reads'])
        self.assertIn('docs', rec['dirs'])
        self.assertIn(os.path.join('campaigns', '*', 'campaign.yaml'), rec['globs'])
        self.assertEqual(rec['opaque'], [])

    def test_a_subprocess_makes_it_opaque_but_decomp_git_does_not(self):
        rel, out = self.run_test_file('''
            import subprocess
            subprocess.run(['git', '-C', %r, 'rev-parse', 'HEAD'], capture_output=True)
        ''' % os.path.join(REPO, 'fireemblem8u'))
        self.assertIsNone(out)
        self.assertEqual(self.record(rel)['opaque'], [])
        rel, out = self.run_test_file('''
            import subprocess
            subprocess.run(['true'])
        ''')
        self.assertTrue(self.record(rel)['opaque'])

    def test_a_failing_test_keeps_no_record(self):
        rel, out = self.run_test_file('''
            import sys
            sys.exit(1)
        ''')
        self.assertIsNotNone(out)
        self.assertFalse(os.path.exists(run_tests.trace_path(rel)))


class Affected(unittest.TestCase):
    """Which tests a staged path reaches; anything unknown runs."""

    def setUp(self):
        self.traces = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.traces)
        patcher = mock.patch.object(run_tests, 'TRACE_DIR', self.traces)
        patcher.start()
        self.addCleanup(patcher.stop)

    def put(self, rel, **rec):
        full = {'reads': [], 'dirs': [], 'globs': [], 'opaque': []}
        full.update(rec)
        os.makedirs(self.traces, exist_ok=True)
        with open(run_tests.trace_path(rel), 'w') as fh:
            json.dump(full, fh)
        return os.path.join(REPO, rel)

    def test_selection(self):
        reads = self.put('tools/test_a.py', reads=['tools/a.py'])
        lists = self.put('tools/test_b.py', dirs=['docs'])
        globs = self.put('tools/test_c.py', globs=['campaigns/*/chapters/*.yaml'])
        opaque = self.put('tools/test_d.py', opaque=['lua -e ...'])
        self_ = self.put('tools/test_e.py')
        unknown = os.path.join(REPO, 'tools', 'test_never_ran.py')
        paths = [reads, lists, globs, opaque, self_, unknown]
        pick = lambda staged: {os.path.basename(p) for p in run_tests.affected(paths, staged)}
        always = {'test_d.py', 'test_never_ran.py'}
        self.assertEqual(pick(['HANDOFF.md']), always)
        self.assertEqual(pick(['tools/a.py']), always | {'test_a.py'})
        self.assertEqual(pick(['docs/decisions/0001-x.md']), always | {'test_b.py'})
        self.assertEqual(pick(['campaigns/r/chapters/ch03.yaml']), always | {'test_c.py'})
        self.assertEqual(pick(['tools/test_e.py']), always | {'test_e.py'})


if __name__ == '__main__':
    unittest.main()
