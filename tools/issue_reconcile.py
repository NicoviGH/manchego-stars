#!/usr/bin/env python3
"""Reconcile open chapter/vertical-slice issues against shipped repo state.

Backstop for the Definition-of-Done rule "the commit says `Closes #N`"
(docs/decisions.md -> Working Conventions). That rule is the ONLY lever that
moves a GitHub issue open->closed, it is manual, and issue state lives OUTSIDE
the repo -- so check.py / make can never catch "work shipped but the issue is
still open." That is exactly how #20 (Prologue) sat closed-in-fact / open-on-
GitHub for eleven days: the completing dialogue landed in a Ch2-focused commit
that never said `Closes #20`.

This advisory flags open chapter issues whose chapter is ALREADY shipped --
its YAML dialogue is LOCKED *and* it has a host/inject function in
build_campaign.py -- yet no commit ever referenced it with a closing keyword.
It does not close anything; it surfaces candidates so the agent (or Nicolas)
reconciles them. The discriminating signal (locked AND hosted) is deliberate:
a chapter with locked dialogue but no host yet (e.g. ch02/#22) is genuinely
unfinished and must NOT be flagged.

Stdlib only, so the SessionStart hook can run it anywhere. GitHub is read via
the `gh` CLI when present; with no `gh` (e.g. Claude Code on the web) the
fetch degrades to nothing and the hook falls back to its standing reminder.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAPTERS_DIR = os.path.join(
    REPO, 'campaigns', 'rime-of-the-frostmaiden', 'chapters')
BUILD_CAMPAIGN = os.path.join(REPO, 'tools', 'build_campaign.py')

# Closing keywords GitHub itself honours (close/closes/closed, fix.., resolve..).
_CLOSING_RE = re.compile(
    r'\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)\b', re.IGNORECASE)


# ---- pure cores (unit-tested in tools/test_issue_reconcile.py) -------------

def closing_ref_numbers(git_log_text):
    """Issue numbers any commit closed via a GitHub closing keyword."""
    return {int(n) for n in _CLOSING_RE.findall(git_log_text)}


def chapter_stem_for_title(title):
    """Map an issue title to its chapter stem ('ch00'..'ch08'), or None.

    'Prologue ...' -> ch00; 'Ch1 ...' / 'Chapter 1 ...' -> ch01; etc.
    """
    if re.search(r'\bprologue\b', title, re.IGNORECASE):
        return 'ch00'
    m = re.search(r'\bch(?:apter)?\s*0*(\d+)\b', title, re.IGNORECASE)
    if m:
        return 'ch%02d' % int(m.group(1))
    return None


def inject_fn_for_stem(stem):
    """The build_campaign.py host function that proves a chapter is wired."""
    return 'inject_prologue' if stem == 'ch00' else 'inject_%s' % stem


def shipped_stems(chapter_sources, build_src):
    """Stems that are SHIPPED: locked dialogue AND a host/inject function.

    `chapter_sources`: {stem: yaml_text}. `build_src`: build_campaign.py text.
    """
    out = set()
    for stem, text in chapter_sources.items():
        if 'LOCKED' in text and ('def %s' % inject_fn_for_stem(stem)) in build_src:
            out.add(stem)
    return out


def likely_closeable(issues, shipped, closing_refs):
    """[(number, title, reason)] for open chapter issues that look done.

    An issue is a candidate when its title maps to a SHIPPED chapter and no
    commit ever closed it. `issues`: [{'number', 'title'}, ...].
    """
    out = []
    for iss in issues:
        num, title = iss['number'], iss['title']
        stem = chapter_stem_for_title(title)
        if stem in shipped and num not in closing_refs:
            out.append((num, title,
                        'chapter %s is shipped (locked dialogue + host fn) but '
                        'no commit said "Closes #%d"' % (stem, num)))
    return out


# ---- thin I/O shell (not unit-tested; degrades when tools are absent) ------

def _read_chapter_sources():
    sources = {}
    if not os.path.isdir(CHAPTERS_DIR):
        return sources
    for name in os.listdir(CHAPTERS_DIR):
        m = re.match(r'(ch\d\d)', name)
        if m and name.endswith(('.yaml', '.yml')):
            with open(os.path.join(CHAPTERS_DIR, name), encoding='utf-8') as f:
                sources[m.group(1)] = f.read()
    return sources


def _read_text(path):
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except OSError:
        return ''


def _git_log():
    try:
        return subprocess.run(
            ['git', '-C', REPO, 'log', '--all', '--format=%B'],
            capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return ''


def _gh_open_issues():
    """Open issues via `gh`, or None if gh is unavailable/unauthed."""
    try:
        res = subprocess.run(
            ['gh', 'issue', 'list', '--state', 'open',
             '--json', 'number,title', '--limit', '200'],
            cwd=REPO, capture_output=True, text=True, check=True)
        return json.loads(res.stdout)
    except (OSError, subprocess.CalledProcessError, ValueError):
        return None


def find_candidates():
    """(candidates, issues_available). Empty list + False when gh is absent."""
    issues = _gh_open_issues()
    if issues is None:
        return [], False
    shipped = shipped_stems(_read_chapter_sources(), _read_text(BUILD_CAMPAIGN))
    return likely_closeable(issues, shipped, closing_ref_numbers(_git_log())), True


def main(argv):
    session_start = '--session-start' in argv
    candidates, available = find_candidates()
    if candidates:
        print('Issue reconciliation -- these open issues look already shipped '
              '(verify, then `Closes #N` or explain why still open):')
        for num, title, reason in candidates:
            print('  #%d  %s' % (num, title))
            print('       -> %s' % reason)
        return 0
    if session_start:
        # Silent when clean (or gh unavailable) so the hook never spams; the
        # hook's standing reminder covers the no-gh case.
        return 0
    if not available:
        print('issue_reconcile: gh unavailable -- reconcile open issues '
              'manually (see docs/decisions.md -> Working Conventions).')
    else:
        print('issue_reconcile: no shipped-but-open chapter issues found.')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
