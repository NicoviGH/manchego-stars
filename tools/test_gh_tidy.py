#!/usr/bin/env python3
"""Tests for tools/gh_tidy.py (#707): each check on recorded GitHub data, plus the exit codes.

The fixture tools/testdata/gh_tidy.json has the same shape the GraphQL queries return, with
one deliberate drift per check and a clean twin beside it.

Run: python3 tools/test_gh_tidy.py
"""
import json
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gh_tidy

with open(os.path.join(HERE, 'testdata', 'gh_tidy.json')) as _f:
    DATA = json.load(_f)


class OrphanTest(unittest.TestCase):
    def test_only_the_parentless_bot_issue_is_reported(self):
        msgs = gh_tidy.check_orphans(DATA['issues'])
        self.assertEqual(len(msgs), 1, msgs)
        self.assertTrue(msgs[0].startswith('#900 '), msgs)

    def test_roots_and_non_bot_titles_are_exempt(self):
        self.assertFalse(any(m.startswith(p) for m in gh_tidy.check_orphans(DATA['issues'])
                             for p in ('#510 ', '#640 ', '#902 ', '#903 ')))


class HoldTest(unittest.TestCase):
    def test_hold_without_a_bold_why_comment(self):
        msgs = gh_tidy.check_holds(DATA['issues'])
        self.assertEqual(len(msgs), 1, msgs)
        self.assertTrue(msgs[0].startswith('#910 '), msgs)

    def test_the_why_comment_matches_case_insensitively(self):
        self.assertFalse(any(m.startswith('#911 ') for m in gh_tidy.check_holds(DATA['issues'])))


class PrLinkTest(unittest.TestCase):
    def test_pr_closing_an_orphan_bot_issue(self):
        msgs = gh_tidy.check_pr_links(DATA['pullRequests'])
        self.assertEqual(len(msgs), 1, msgs)
        self.assertTrue(msgs[0].startswith('PR #950 '), msgs)


class StatusTest(unittest.TestCase):
    def test_status_older_than_a_newer_comment_names_the_newest(self):
        msgs = gh_tidy.check_stale_status(DATA['issues'])
        self.assertEqual(len(msgs), 1, msgs)
        self.assertTrue(msgs[0].startswith('#920: status comment 10 '), msgs)
        self.assertIn('comment 12 ', msgs[0])

    def test_status_edited_after_the_last_comment_is_fresh(self):
        self.assertFalse(any(m.startswith('#921') for m in gh_tidy.check_stale_status(DATA['issues'])))


class MainTest(unittest.TestCase):
    def _run(self, fetch):
        with mock.patch.object(gh_tidy, 'fetch', fetch), \
                mock.patch('sys.stdout'), mock.patch('sys.stderr'):
            return gh_tidy.main([])

    def test_exit_1_on_findings(self):
        self.assertEqual(self._run(lambda: DATA), 1)

    def test_exit_0_when_clean(self):
        self.assertEqual(self._run(lambda: {'issues': [], 'pullRequests': []}), 0)

    def test_exit_2_when_gh_fails_never_clean(self):
        def boom():
            raise gh_tidy.GhError('no network')
        self.assertEqual(self._run(boom), 2)

    def test_gh_nonzero_exit_raises(self):
        done = mock.Mock(returncode=1, stderr='HTTP 401', stdout='')
        with mock.patch('subprocess.run', return_value=done):
            with self.assertRaises(gh_tidy.GhError):
                gh_tidy.fetch()


if __name__ == '__main__':
    unittest.main()
