#!/usr/bin/env python3
"""Fail loudly when the GitHub issue record drifts (#707, from the #706 tidy-up).

The tidy-up found four kinds of drift, each a skipped update rather than a missing tool. This
is the guard, the way `tools/check.py` is for code. Each finding names the issue or PR, what
is wrong, and the one-line fix:

  orphan   an OPEN bot issue (title rule: BOT_TITLE) with no parent issue. The one root, #510,
           is exempt (ROOTS).
  hold     an OPEN `on-hold` issue with no comment starting `**On hold` (the one why-comment).
  pr-link  an OPEN PR whose closing issue is a bot issue with no parent and is not itself in
           the open-issues list (an open one is already an orphan finding, so it is not
           reported twice).
  status   an issue with a status comment edited in place (STATUS_MARKER) that is older than
           the newest other comment on the issue.
  roadmap  an OPEN issue in the roadmap root's tree (ROADMAP_ROOT, #640, and every issue whose
           parent chain reaches it) that is not an item of the roadmap Project
           (ROADMAP_PROJECT) or has no Phase there (#747, Nicolas 2026-11-23: "build a roadmap
           and stick to it"). New work cannot pile up unranked. Reading Project items needs
           the token's read:project scope; without it the fetch fails and the run exits 2.

Run: python3 tools/gh_tidy.py     (or `make tidy`)
Exit: 0 clean, 1 any finding, 2 `gh` failed (a failed fetch is never reported as clean).

Scope: bot work is recognised by TITLE only (BOT_TITLE). A body rule was tried against the live
open issues and is not clean: a body mentioning #510 or #640 also sweeps in the content
backlog (#526, #543, #547 mention #510 and are roster/lord design, not bot work), and
"Part of #706" matches only #707. So bot issues with other titles (e.g. #651 "difficulty.py
resolves...", #707 "Tidy check: ...", both children of the #510 tree) are NOT checked for a
parent; name a bot issue with a BOT_TITLE prefix to have it guarded.

The fetch is two paginated GraphQL queries (open issues, open PRs), plus one follow-up query
for each issue with more than a page of comments, never a call per issue otherwise; the checks
are pure functions of the parsed data, unit-tested on tools/testdata/gh_tidy.json.
"""
import json
import re
import subprocess
import sys

# A bot issue is one whose title starts with one of these (step 9 of #510). Case-sensitive on
# purpose: `harness.lua audit` (#531) is the harness' code, not the bot's work.
BOT_TITLE = re.compile(r'^(Bot\b|#510\b|Harness\b|Lookahead\b|Campaign laps\b|Playtest\b)')
# The one issue that heads the tree, so having no parent is correct: #510 (parity model).
# #640 (step 9 of #510) is not a root: if it loses its parent #510 that is reported.
ROOTS = frozenset({510})
HOLD_LABEL = 'on-hold'
HOLD_COMMENT = re.compile(r'^\s*\*\*on hold', re.IGNORECASE)
STATUS_MARKER = re.compile(r'^### Status \(edited in place', re.MULTILINE)
# The roadmap (#747): the user Project every open issue under ROADMAP_ROOT sits on, ranked by
# its single-select ROADMAP_FIELD (Now, Next, Later, Parked, Epic).
ROADMAP_ROOT = 640
ROADMAP_PROJECT = 2
ROADMAP_FIELD = 'Phase'
ROADMAP_URL = 'https://github.com/users/NicoviGH/projects/%d' % ROADMAP_PROJECT
# How far up the parent chain the query reads: #510 > #640 > #699 > a fix is three levels; one
# more for headroom. An issue nested deeper is reported as outside the tree, so keep the tree
# within it.
PARENT_DEPTH = 4

REPO_OWNER, REPO_NAME = 'NicoviGH', 'manchego-stars'
REPO = '%s/%s' % (REPO_OWNER, REPO_NAME)
COMMENT_PAGE = 100
_COMMENT_FIELDS = 'pageInfo { hasNextPage endCursor } nodes { databaseId body createdAt updatedAt }'
_PARENTS = 'number'
for _ in range(PARENT_DEPTH - 1):
    _PARENTS = 'number parent { %s }' % _PARENTS
_PROJECT_ITEMS = ('projectItems(first: 20) { nodes { project { number } '
                  'fieldValueByName(name: "%s") { '
                  '... on ProjectV2ItemFieldSingleSelectValue { name } } } }' % ROADMAP_FIELD)
ISSUES_QUERY = '''query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
  issues(states: OPEN, first: 50, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes { number title
      labels(first: 30) { nodes { name } }
      parent { %s }
      %s
      comments(first: %d) { %s } } } } }''' % (_PARENTS, _PROJECT_ITEMS, COMMENT_PAGE,
                                              _COMMENT_FIELDS)
COMMENTS_QUERY = '''query($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) { issue(number: $number) {
    comments(first: %d, after: $after) { %s } } } }''' % (COMMENT_PAGE, _COMMENT_FIELDS)
PRS_QUERY = '''query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
  pullRequests(states: OPEN, first: 50, after: $after) {
    pageInfo { hasNextPage endCursor }
    nodes { number title
      closingIssuesReferences(first: 10) { nodes { number title parent { number } } } } } } }'''


class GhError(Exception):
    """`gh` could not answer; the check cannot say whether the record is clean."""


def _graphql(query, **variables):
    cmd = ['gh', 'api', 'graphql', '-f', 'query=' + query, '-f', 'owner=' + REPO_OWNER,
           '-f', 'name=' + REPO_NAME]
    for k, v in variables.items():
        if v is not None:  # -F types an int as Int; -f keeps a cursor a string
            cmd += ['-F' if isinstance(v, int) else '-f', '%s=%s' % (k, v)]
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


def _pages(query, get_conn, first=None, **variables):
    """All nodes of a connection; `first` is the page already read (so a follow-up resumes)."""
    nodes, conn = [], first
    while True:
        if conn is None:
            conn = get_conn(_graphql(query, **variables))
        nodes += conn['nodes']
        if not conn['pageInfo']['hasNextPage']:
            return nodes
        variables['after'] = conn['pageInfo']['endCursor']
        conn = None


def _all_comments(issue):
    """The issue's full comment list, in place of the first page the issues query read."""
    conn = issue['comments']
    nodes = _pages(COMMENTS_QUERY, lambda r: r['issue']['comments'], first=conn,
                   number=issue['number'])
    return {'nodes': nodes}


def fetch():
    issues = _pages(ISSUES_QUERY, lambda r: r['issues'])
    for i in issues:
        if i['comments']['pageInfo']['hasNextPage']:
            i['comments'] = _all_comments(i)
        else:
            i['comments'] = {'nodes': i['comments']['nodes']}
    return {'issues': issues,
            'pullRequests': _pages(PRS_QUERY, lambda r: r['pullRequests'])}


def is_bot(title):
    return bool(BOT_TITLE.match(title))


def _orphan_wanted(number, title, parent):
    return is_bot(title) and number not in ROOTS and not parent


def check_orphans(issues):
    return ['#%d (%s): bot issue with no parent. Fix: gh api -X POST '
            'repos/%s/issues/<parent>/sub_issues -F sub_issue_id=<id of #%d> '
            '(parent is #640 or the umbrella that owns it)'
            % (i['number'], i['title'], REPO, i['number'])
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


def check_pr_links(prs, open_numbers=frozenset()):
    """Only what check_orphans cannot see: a closing issue not in the open-issues list."""
    out = []
    for p in prs:
        for c in p['closingIssuesReferences']['nodes']:
            if c['number'] in open_numbers:
                continue
            if _orphan_wanted(c['number'], c['title'], c['parent']):
                out.append('PR #%d (%s): closes #%d (%s), a bot issue with no parent. Fix: link '
                           '#%d under #640 or its umbrella before merging'
                           % (p['number'], p['title'], c['number'], c['title'], c['number']))
    return out


def check_stale_status(issues):
    out = []
    for i in issues:
        comments = i['comments']['nodes']
        for s in (c for c in comments if STATUS_MARKER.search(c['body'])):
            newer = [c for c in comments if c is not s and c['createdAt'] > s['updatedAt']]
            if newer:
                y = max(newer, key=lambda c: c['createdAt'])
                out.append('#%d: status comment %d (updated %s) is older than comment %d '
                           '(created %s): fold %d\'s state into it, edited in place'
                           % (i['number'], s['databaseId'], s['updatedAt'], y['databaseId'],
                              y['createdAt'], y['databaseId']))
    return out


def _in_roadmap_tree(issue):
    """The issue is ROADMAP_ROOT or has it somewhere up its parent chain."""
    if issue['number'] == ROADMAP_ROOT:
        return True
    p = issue['parent']
    while p:
        if p['number'] == ROADMAP_ROOT:
            return True
        p = p.get('parent')
    return False


def check_roadmap(issues):
    out = []
    for i in issues:
        if not _in_roadmap_tree(i):
            continue
        items = [n for n in i['projectItems']['nodes']
                 if n['project']['number'] == ROADMAP_PROJECT]
        if not items:
            out.append('#%d (%s): not on the roadmap (%s). Fix: gh project item-add %d '
                       '--owner %s --url https://github.com/%s/issues/%d, then set its %s'
                       % (i['number'], i['title'], ROADMAP_URL, ROADMAP_PROJECT, REPO_OWNER,
                          REPO, i['number'], ROADMAP_FIELD))
        elif not any(n['fieldValueByName'] for n in items):
            out.append('#%d (%s): on the roadmap with no %s. Fix: set it on %s'
                       % (i['number'], i['title'], ROADMAP_FIELD, ROADMAP_URL))
    return out


def findings(data):
    """Every finding as (kind, message), in a stable order."""
    return ([('orphan', m) for m in check_orphans(data['issues'])]
            + [('hold', m) for m in check_holds(data['issues'])]
            + [('pr-link', m) for m in check_pr_links(
                data['pullRequests'], {i['number'] for i in data['issues']})]
            + [('status', m) for m in check_stale_status(data['issues'])]
            + [('roadmap', m) for m in check_roadmap(data['issues'])])


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
