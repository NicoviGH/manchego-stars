#!/usr/bin/env python3
"""Fail loudly when the GitHub issue record drifts (#707, from the #706 tidy-up).

The tidy-up found four kinds of drift, each a skipped update rather than a missing tool. This
is the guard, the way `tools/check.py` is for code. Each finding names the issue or PR, what
is wrong, and the one-line fix:

  orphan   an OPEN bot issue (title rule: BOT_TITLE) with no parent issue. Roots are exempt
           (ROOTS).
  hold     an OPEN `on-hold` issue with no comment starting `**On hold` (the one why-comment).
  pr-link  an OPEN PR whose closing issue is a bot issue with no parent.
  status   an issue with a status comment edited in place (STATUS_MARKER) that is older than
           the newest other comment on the issue.

Run: python3 tools/gh_tidy.py     (or `make tidy`)
Exit: 0 clean, 1 any finding, 2 `gh` failed (a failed fetch is never reported as clean).

The fetch is two paginated GraphQL queries (open issues, open PRs), not a call per issue; the
checks are pure functions of the parsed data, unit-tested on tools/testdata/gh_tidy.json.
"""
import json
import re
import subprocess
import sys

# A bot issue is one whose title starts with one of these (step 9 of #510). Case-sensitive on
# purpose: `harness.lua audit` (#531) is the harness' code, not the bot's work.
BOT_TITLE = re.compile(r'^(Bot\b|#510\b|Harness\b|Lookahead\b|Campaign laps\b|Playtest\b)')
# Issues that head a tree, so having no parent is correct: #510 (parity model) and #640
# (the bot plays vanilla clean, step 9 of #510, whose parent is #510 but which is declared a
# root so a lost link does not hide the whole tree).
ROOTS = frozenset({510, 640})
HOLD_LABEL = 'on-hold'
HOLD_COMMENT = re.compile(r'^\s*\*\*on hold', re.IGNORECASE)
STATUS_MARKER = '### Status (edited in place'

_ISSUE_FIELDS = '''number title url
  labels(first: 30) { nodes { name } }
  parent { number }
  subIssues(first: 1) { totalCount }
  comments(last: 100) { nodes { databaseId url body createdAt updatedAt } }'''
ISSUES_QUERY = '''query($after: String) { repository(owner: "NicoviGH", name: "manchego-stars") {
  issues(states: OPEN, first: 50, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes { %s } } } }''' % _ISSUE_FIELDS
PRS_QUERY = '''query($after: String) { repository(owner: "NicoviGH", name: "manchego-stars") {
  pullRequests(states: OPEN, first: 50, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes { number title url
      closingIssuesReferences(first: 10) { nodes { number title parent { number } } } } } } }'''


class GhError(Exception):
    """`gh` could not answer; the check cannot say whether the record is clean."""


def _graphql(query, after=None):
    cmd = ['gh', 'api', 'graphql', '-f', 'query=' + query]
    if after:
        cmd += ['-f', 'after=' + after]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise GhError('`gh` is not installed')
    if out.returncode != 0:
        raise GhError('`gh api graphql` failed: ' + (out.stderr.strip() or out.stdout.strip()))
    try:
        data = json.loads(out.stdout)
    except ValueError:
        raise GhError('`gh api graphql` returned non-JSON: ' + out.stdout[:200])
    if data.get('errors'):
        raise GhError('GraphQL errors: ' + json.dumps(data['errors'])[:300])
    return data['data']['repository']


def _pages(query, key):
    nodes, after = [], None
    while True:
        conn = _graphql(query, after)[key]
        nodes += conn['nodes']
        if not conn['pageInfo']['hasNextPage']:
            return nodes
        after = conn['pageInfo']['endCursor']


def fetch():
    return {'issues': _pages(ISSUES_QUERY, 'issues'),
            'pullRequests': _pages(PRS_QUERY, 'pullRequests')}


def is_bot(title):
    return bool(BOT_TITLE.match(title))


def _orphan_wanted(number, title, parent):
    return is_bot(title) and number not in ROOTS and not parent


def check_orphans(issues):
    return ['#%d (%s): bot issue with no parent. Fix: gh api -X POST '
            'repos/NicoviGH/manchego-stars/issues/<parent>/sub_issues -F sub_issue_id=<id of #%d> '
            '(parent is #640 or the umbrella that owns it)' % (i['number'], i['title'], i['number'])
            for i in issues if _orphan_wanted(i['number'], i['title'], i['parent'])]


def check_holds(issues):
    out = []
    for i in issues:
        if HOLD_LABEL not in [l['name'] for l in i['labels']['nodes']]:
            continue
        if not any(HOLD_COMMENT.match(c['body']) for c in i['comments']['nodes']):
            out.append('#%d (%s): labelled %s but has no comment starting "**On hold". Fix: '
                       'gh issue comment %d with one "**On hold (Nicolas, <date>).** why, and '
                       'what reopens it", or remove the label' % (i['number'], i['title'],
                                                                   HOLD_LABEL, i['number']))
    return out


def check_pr_links(prs):
    out = []
    for p in prs:
        for c in p['closingIssuesReferences']['nodes']:
            if _orphan_wanted(c['number'], c['title'], c['parent']):
                out.append('PR #%d (%s): closes #%d (%s), a bot issue with no parent. Fix: link '
                           '#%d under #640 or its umbrella before merging'
                           % (p['number'], p['title'], c['number'], c['title'], c['number']))
    return out


def check_stale_status(issues):
    out = []
    for i in issues:
        comments = i['comments']['nodes']
        for s in (c for c in comments if STATUS_MARKER in c['body']):
            newer = [c for c in comments if c is not s and c['createdAt'] > s['updatedAt']]
            if newer:
                y = max(newer, key=lambda c: c['createdAt'])
                out.append('#%d: status comment %d (updated %s) is older than comment %d '
                           '(created %s): fold %d\'s state into it, edited in place'
                           % (i['number'], s['databaseId'], s['updatedAt'], y['databaseId'],
                              y['createdAt'], y['databaseId']))
    return out


def findings(data):
    """Every finding as (kind, message), in a stable order."""
    return ([('orphan', m) for m in check_orphans(data['issues'])]
            + [('hold', m) for m in check_holds(data['issues'])]
            + [('pr-link', m) for m in check_pr_links(data['pullRequests'])]
            + [('status', m) for m in check_stale_status(data['issues'])])


def main(argv):
    try:
        data = fetch()
    except GhError as e:
        print('gh_tidy: could not read GitHub, so the record is UNCHECKED: %s' % e,
              file=sys.stderr)
        return 2
    found = findings(data)
    for kind, msg in found:
        print('[%s] %s' % (kind, msg))
    if found:
        print('gh_tidy: %d finding(s)' % len(found))
        return 1
    print('gh_tidy: clean (%d open issues, %d open PRs)'
          % (len(data['issues']), len(data['pullRequests'])))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
