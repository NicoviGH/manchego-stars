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
    MSGS = gh_tidy.check_roadmap(DATA['issues'])

    def _of(self, n):
        return [m for m in self.MSGS if m.startswith('#%d ' % n)]

    def test_each_drift_is_reported_once(self):
        # #930 on another Project only; #931 no Status; #932 a grandchild (through #699) off the
        # board; #933 Parked without on-hold; #934 cut off by PARENT_DEPTH; #935 on another
        # owner's Project 2; #936 on more Projects than one page reads
        self.assertEqual(sorted(m.split(' ')[0] for m in self.MSGS),
                         ['#930', '#931', '#932', '#933', '#934', '#935', '#936'], self.MSGS)

    def test_each_message_names_its_drift(self):
        self.assertIn('no Status', self._of(931)[0])
        self.assertIn('without the on-hold label', self._of(933)[0])
        self.assertIn('levels deep', self._of(934)[0])
        self.assertIn('not on the roadmap', self._of(935)[0])
        self.assertIn('more than %d Projects' % gh_tidy.PROJECT_PAGE, self._of(936)[0])

    def test_issues_outside_the_tree_and_a_labelled_parked_one_pass(self):
        for n in (900, 902, 903, 911):
            self.assertEqual(self._of(n), [], n)

    def test_the_root_itself_must_be_on_the_board(self):
        data = copy.deepcopy(DATA)
        next(i for i in data['issues'] if i['number'] == 640)['projectItems']['nodes'] = []
        self.assertTrue(any(m.startswith('#640 ') for m in gh_tidy.check_roadmap(data['issues'])))

    def test_the_queries_read_the_parent_chain_and_the_status_apart(self):
        self.assertEqual(gh_tidy.ISSUES_QUERY.count('parent {'), gh_tidy.PARENT_DEPTH)
        self.assertNotIn('projectItems', gh_tidy.ISSUES_QUERY)
        self.assertIn('fieldValueByName(name: "Status")', gh_tidy.ROADMAP_QUERY)
        self.assertIn('owner {', gh_tidy.ROADMAP_QUERY)


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

    def test_a_roadmap_read_failure_still_runs_the_other_checks_and_exits_2(self):
        # a token without read:project: orphans and holds still print, the roadmap is UNCHECKED
        issue = {'number': 900, 'title': 'Bot: orphaned crash', 'parent': None,
                 'labels': {'nodes': []},
                 'comments': {'pageInfo': {'hasNextPage': False}, 'nodes': []}}

        def graphql(query, **variables):
            if query is gh_tidy.ROADMAP_QUERY:
                raise gh_tidy.GhError('INSUFFICIENT_SCOPES')
            if query is gh_tidy.ISSUES_QUERY:
                return {'issues': {'pageInfo': {'hasNextPage': False}, 'nodes': [issue]}}
            return {'pullRequests': {'pageInfo': {'hasNextPage': False}, 'nodes': []}}
        with mock.patch.object(gh_tidy, '_graphql', graphql):
            data = gh_tidy.fetch()
        self.assertIn('roadmapError', data)
        self.assertEqual([k for k, _ in gh_tidy.findings(data)], ['orphan'])
        out = []
        with mock.patch.object(gh_tidy, 'fetch', lambda: data), \
                mock.patch('builtins.print', lambda *a, **k: out.append(a[0])):
            self.assertEqual(gh_tidy.main([]), 2)
        self.assertTrue(any(o.startswith('[orphan] #900') for o in out), out)
        self.assertTrue(any('UNCHECKED' in o for o in out), out)

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
            if query is gh_tidy.ROADMAP_QUERY:
                return {'issues': {'pageInfo': {'hasNextPage': False}, 'nodes': []}}
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
