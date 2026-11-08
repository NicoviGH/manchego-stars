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

    def test_an_import_served_from_bytecode_records_its_source(self):
        # The module is popped before exit, so only the open() of its .pyc saw it (#579).
        mod = os.path.join(self.tmp, 'probe_mod.py')
        with open(mod, 'w') as fh:
            fh.write('X = 1\n')
        self.run_test_file('''
            import py_compile
            py_compile.compile(%r)
        ''' % mod)                                    # writes the .pyc (reading the source)
        rel, out = self.run_test_file('''
            import sys
            import probe_mod
            sys.modules.pop('probe_mod')
        ''')                                          # imports from it, never opening the .py
        self.assertIsNone(out)
        reads = self.record(rel)['reads']
        self.assertIn(os.path.relpath(mod, REPO), reads)
        self.assertFalse([r for r in reads if '__pycache__' in r])

    def test_git_apply_on_the_decomp_is_opaque_but_a_read_is_not(self):
        decomp = os.path.join(REPO, 'fireemblem8u')
        patch = os.path.join(REPO, 'AGENTS.md')
        for argv, opaque in ((['git', '-C', decomp, 'apply', '--check', patch], True),
                             (['git', '-C', decomp, '-c', 'a.b=c', 'show', 'HEAD:Makefile'], False),
                             (['git', '-C', decomp, 'diff', '--', patch], True),
                             (['git', '-C', decomp, 'diff', '--no-index', '../AGENTS.md',
                               'CONTRIBUTING.md'], True)):
            rel, out = self.run_test_file('''
                import subprocess
                subprocess.run(%r, capture_output=True)
            ''' % (argv,))
            self.assertEqual(bool(self.record(rel)['opaque']), opaque, argv)

    def test_a_multiprocessing_worker_makes_it_opaque(self):
        rel, out = self.run_test_file('''
            import multiprocessing
            if __name__ == '__main__':
                p = multiprocessing.get_context('spawn').Process(target=print)
                p.start(); p.join()
        ''')
        self.assertIsNone(out)
        self.assertTrue(self.record(rel)['opaque'])

    def test_listing_the_repo_root_with_no_argument_is_recorded(self):
        rel, out = self.run_test_file('''
            import os
            os.chdir(%r)
            os.listdir()
        ''' % REPO)
        self.assertIsNone(out)
        self.assertIn('.', self.record(rel)['dirs'])

    @unittest.skipIf(sys.version_info < (3, 10), 'glob has root_dir from 3.10')
    def test_a_glob_under_root_dir_is_recorded_against_it(self):
        rel, out = self.run_test_file('''
            import glob
            glob.glob('*.md', root_dir=%r)
        ''' % os.path.join(REPO, 'docs'))
        self.assertIsNone(out)
        self.assertIn(os.path.join('docs', '*.md'), self.record(rel)['globs'])

    def test_a_checkout_reached_through_a_symlink_still_records(self):
        link = os.path.join(tempfile.mkdtemp(), 'repo')
        self.addCleanup(shutil.rmtree, os.path.dirname(link))
        os.symlink(REPO, link)
        with mock.patch.object(run_tests, 'REPO', link):
            root = run_tests._real_root()
        self.assertEqual(run_tests._inside(os.path.join(link, 'AGENTS.md'), root), 'AGENTS.md')

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
        full.setdefault('stamps', [run_tests._stamp(r, REPO) for r in full['reads']])
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

    def test_the_repo_root_listed_reaches_top_level_files_only(self):
        root = self.put('tools/test_r.py', dirs=['.'])
        self.assertEqual(run_tests.affected([root], ['HANDOFF.md']), [root])
        self.assertEqual(run_tests.affected([root], ['docs/roadmap.md']), [])

    def test_a_record_whose_reads_moved_since_counts_as_none(self):
        # A pull or branch switch can change what a test reads without any run (#579).
        ok = self.put('tools/test_s.py', reads=['AGENTS.md'])
        self.assertEqual(run_tests.affected([ok], ['HANDOFF.md']), [])
        moved = self.put('tools/test_t.py', reads=['AGENTS.md'], stamps=[[1, 2]])
        self.assertEqual(run_tests.affected([moved], ['HANDOFF.md']), [moved])
        old = self.put('tools/test_u.py', reads=['AGENTS.md'], stamps=[])
        self.assertEqual(run_tests.affected([old], ['HANDOFF.md']), [old])


if __name__ == '__main__':
    unittest.main()
