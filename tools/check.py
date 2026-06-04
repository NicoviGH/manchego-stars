#!/usr/bin/env python3
"""Repo drift guard. ONE source of check logic, run by CI, the git pre-commit hook,
and `make check`. Keeps doc/plan drift from landing.

Catches:
  1. Python tooling that doesn't compile.
  2. Campaign YAML that doesn't parse.
  3. Docs referencing a tools/<x>.py|rb that doesn't exist.
  4. Resurrected "dead concepts" -- abandoned tool names, dead code symbols, retired
     implementation phrases -- in any doc except decisions.md (the ADR log that is
     *supposed* to record what we dropped).

What it does NOT catch: arbitrary prose that contradicts the code without using a
known-dead term. The defense there is single source of truth (link, don't restate)
and the Definition of Done -- see docs/decisions.md Working Conventions.

Exit 0 = clean, 1 = drift found. Run from the repo root.
"""

import glob
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Docs that carry prose facts (decisions.md is handled specially per-check).
DOC_GLOBS = ['docs/**/*.md', 'CLAUDE.md', 'README.md', 'HANDOFF.md']

# Terms that are NEVER legitimate in vision/ops docs: abandoned tools, dead code
# symbols, retired implementation phrases. decisions.md is EXEMPT (its ADRs record
# what we abandoned, e.g. "supersedes the flat-E placeholder"). Context-dependent
# terms (Event Assembler / devkitARM / "damage-type") are intentionally NOT here --
# they appear legitimately in negation ("no Event Assembler").
DEAD_CONCEPTS = [
    r'build-campaign\.ts', r'build-events\.ts', r'pull-srd', r'map-class\.ts',
    r'srd-snapshot', r'open5e-snapshot', r'CLASS_WEAPON', r'WPN_EXP_E',
    r'zeroed.{0,3}growth', r'flat-?E rank', r'pure[- ]class growth',
]


def _docs():
    out = []
    for g in DOC_GLOBS:
        out += glob.glob(os.path.join(REPO, g), recursive=True)
    return [d for d in out if os.path.isfile(d)]


def check_python_compiles(fail):
    import compileall
    if not compileall.compile_dir(os.path.join(REPO, 'tools'), quiet=1):
        fail.append('tools/ has a Python file that does not compile')


def check_yaml_parses(fail):
    import yaml
    for f in glob.glob(os.path.join(REPO, 'campaigns/**/*.yaml'), recursive=True):
        try:
            yaml.safe_load(open(f, encoding='utf-8'))
        except Exception as e:
            fail.append('YAML does not parse: %s (%s)' % (os.path.relpath(f, REPO), e))


def check_tool_refs_exist(fail):
    pat = re.compile(r'tools/([\w-]+\.(?:py|rb))')
    for d in _docs():
        for m in pat.findall(open(d, encoding='utf-8').read()):
            if not os.path.isfile(os.path.join(REPO, 'tools', m)):
                fail.append('%s references tools/%s which does not exist'
                            % (os.path.relpath(d, REPO), m))


def check_no_dead_concepts(fail):
    pat = re.compile('|'.join(DEAD_CONCEPTS), re.I)
    for d in _docs():
        if os.path.basename(d) == 'decisions.md':
            continue
        for i, line in enumerate(open(d, encoding='utf-8'), 1):
            m = pat.search(line)
            if m:
                fail.append('dead concept %r in %s:%d'
                            % (m.group(0), os.path.relpath(d, REPO), i))


def main():
    fail = []
    for check in (check_python_compiles, check_yaml_parses,
                  check_tool_refs_exist, check_no_dead_concepts):
        check(fail)
    if fail:
        print('DRIFT (%d):' % len(fail))
        for f in fail:
            print('  - ' + f)
        return 1
    print('drift check: clean')
    return 0


if __name__ == '__main__':
    sys.exit(main())
