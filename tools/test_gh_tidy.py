#!/usr/bin/env python3
"""Tests for tools/gh_tidy.py (#707): each check on recorded GitHub data, plus the exit codes.

The fixture tools/testdata/gh_tidy.json has the same shape the GraphQL queries return, with
one deliberate drift per check and a clean twin beside it.

Run: python3 tools/test_gh_tidy.py
"""
import copy
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

    def test_the_root_and_non_bot_titles_are_exempt(self):
        self.assertFalse(any(m.startswith(p) for m in gh_tidy.check_orphans(DATA['issues'])
                             for p in ('#510 ', '#640 ', '#902 ', '#903 ')))

    def test_640_losing_its_parent_is_reported(self):
        data = copy.deepcopy(DATA)
        next(i for i in data['issues'] if i['number'] == 640)['parent'] = None
        msgs = gh_tidy.check_orphans(data['issues'])
        self.assertEqual(sorted(m[:5] for m in msgs), ['#640 ', '#900 '], msgs)


class HoldTest(unittest.TestCase):
    def test_hold_without_a_bold_why_comment(self):
        msgs = gh_tidy.check_holds(DATA['issues'])
        self.assertEqual(len(msgs), 1, msgs)
        self.assertTrue(msgs[0].startswith('#910 '), msgs)

    def test_the_why_comment_matches_case_insensitively(self):
        self.assertFalse(any(m.startswith('#911 ') for m in gh_tidy.check_holds(DATA['issues'])))


class PrLinkTest(unittest.TestCase):
    OPEN = {i['number'] for i in DATA['issues']}

    def test_pr_closing_an_orphan_not_in_the_open_list(self):
        msgs = gh_tidy.check_pr_links(DATA['pullRequests'], self.OPEN)
        self.assertEqual(len(msgs), 1, msgs)
        self.assertTrue(msgs[0].startswith('PR #953 '), msgs)

    def test_open_orphan_is_reported_once_not_twice(self):
        # PR #950 closes open orphan #900: the orphan check owns it, the pr-link check skips it.
        found = gh_tidy.findings(DATA)
        self.assertEqual([k for k, m in found if '#900' in m], ['orphan'], found)


class StatusTest(unittest.TestCase):
    def test_status_older_than_a_newer_comment_names_the_newest(self):
        msgs = gh_tidy.check_stale_status(DATA['issues'])
        self.assertEqual(len(msgs), 1, msgs)
        self.assertTrue(msgs[0].startswith('#920: status comment 10 '), msgs)
        self.assertIn('comment 12 ', msgs[0])

    def test_a_quoted_marker_mid_line_is_not_a_status_comment(self):
        msgs = gh_tidy.check_stale_status(DATA['issues'])
        self.assertFalse(any(m.startswith('#922') for m in msgs))

    def test_status_edited_after_the_last_comment_is_fresh(self):
        msgs = gh_tidy.check_stale_status(DATA['issues'])
        self.assertFalse(any(m.startswith('#921') for m in msgs))


class RoadmapTest(unittest.TestCase):
    def test_off_board_and_phaseless_issues_in_the_tree_are_reported(self):
        # #930 sits on another Project only; #931 is on the roadmap with no Phase; #932 is a
        # grandchild of #640 (through #699) with no board item at all
        msgs = gh_tidy.check_roadmap(DATA['issues'])
        self.assertEqual(sorted(m.split(' ')[0] for m in msgs), ['#930', '#931', '#932'], msgs)
        self.assertIn('no Phase', next(m for m in msgs if m.startswith('#931')))

    def test_issues_outside_the_tree_are_not_checked(self):
        # #900 (no parent), #902 and #903 (other work) have no board item and are not reported
        msgs = gh_tidy.check_roadmap(DATA['issues'])
        self.assertFalse(any(m.startswith(p) for m in msgs for p in ('#900 ', '#902 ', '#903 ')))

    def test_the_root_itself_must_be_on_the_board(self):
        data = copy.deepcopy(DATA)
        next(i for i in data['issues'] if i['number'] == 640)['projectItems'] = {'nodes': []}
        self.assertTrue(any(m.startswith('#640 ') for m in gh_tidy.check_roadmap(data['issues'])))

    def test_the_query_reads_the_parent_chain_and_the_phase(self):
        q = gh_tidy.ISSUES_QUERY
        self.assertEqual(q.count('parent {'), gh_tidy.PARENT_DEPTH)
        self.assertIn('fieldValueByName(name: "Phase")', q)


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

    def test_comments_past_the_first_page_are_all_read(self):
        # #911's why-comment sits on the second page: a first-page-only read would call the
        # hold unexplained, and miss an old status comment the same way.
        issue = {'number': 911, 'title': 'Bot: held', 'parent': {'number': 640},
                 'labels': {'nodes': [{'name': 'on-hold'}]},
                 'comments': {'pageInfo': {'hasNextPage': True, 'endCursor': 'c1'},
                              'nodes': [{'databaseId': 1, 'body': 'x', 'createdAt': 'a',
                                         'updatedAt': 'a'}]}}
        page2 = {'pageInfo': {'hasNextPage': False, 'endCursor': None},
                 'nodes': [{'databaseId': 2, 'body': '**On hold (Nicolas).** why',
                            'createdAt': 'b', 'updatedAt': 'b'}]}
        seen = []

        def graphql(query, **variables):
            seen.append((query, variables))
            if query is gh_tidy.ISSUES_QUERY:
                return {'issues': {'pageInfo': {'hasNextPage': False}, 'nodes': [issue]}}
            if query is gh_tidy.COMMENTS_QUERY:
                return {'issue': {'comments': page2}}
            return {'pullRequests': {'pageInfo': {'hasNextPage': False}, 'nodes': []}}
        with mock.patch.object(gh_tidy, '_graphql', graphql):
            data = gh_tidy.fetch()
        self.assertEqual([c['databaseId'] for c in data['issues'][0]['comments']['nodes']], [1, 2])
        self.assertEqual(gh_tidy.check_holds(data['issues']), [])
        follow = [v for q, v in seen if q is gh_tidy.COMMENTS_QUERY]
        self.assertEqual(follow, [{'number': 911, 'after': 'c1'}], seen)

    def test_gh_nonzero_exit_raises(self):
        done = mock.Mock(returncode=1, stderr='HTTP 401', stdout='')
        with mock.patch('subprocess.run', return_value=done):
            with self.assertRaises(gh_tidy.GhError):
                gh_tidy.fetch()


if __name__ == '__main__':
    unittest.main()
