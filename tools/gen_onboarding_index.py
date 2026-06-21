#!/usr/bin/env python3
"""Generate docs/ONBOARDING.md -- the FE8 tutorial-parity coverage dashboard.

Combats is vanilla-strict, but rewriting cutscenes / reordering content can silently
strip the onboarding a vanilla player gets. This rolls up two sources of truth:

  * the STABLE catalog -- campaigns/.../onboarding-catalog.yaml: what vanilla teaches,
    the channel (tutorial box vs mandatory dialogue), and the decomp citation;
  * the LIVING ledger -- each chapter YAML's `introduces:` list: which concept first
    appears in OUR chapter order and how we cover it.

into a coverage table + a Pending list of concepts no chapter covers yet, so a dropped
lesson is visible. Integrity (orphan / double-debut concepts) is checked by
tools/test_onboarding.py. Do not hand-edit docs/ONBOARDING.md -- edit the YAML and
regenerate:  python3 tools/gen_onboarding_index.py

Stdlib + pyyaml only.
"""

import glob
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMPAIGN = os.path.join(ROOT, 'campaigns/rime-of-the-frostmaiden')
CATALOG = os.path.join(CAMPAIGN, 'onboarding-catalog.yaml')
CHAPTERS = os.path.join(CAMPAIGN, 'chapters')
OUT = os.path.join(ROOT, 'docs/ONBOARDING.md')


def squish(s):
    return re.sub(r'\s+', ' ', str(s if s is not None else '')).strip()


def chapter_label(num):
    return 'P' if int(num) == 0 else 'Ch %d' % int(num)


def load_catalog():
    """The vanilla onboarding concepts, in file order."""
    data = yaml.safe_load(open(CATALOG, encoding='utf-8')) or {}
    return data.get('concepts') or []


def _chapters():
    files = sorted(glob.glob(os.path.join(CHAPTERS, 'ch*.yaml')))
    chapters = [yaml.safe_load(open(f, encoding='utf-8')) for f in files]
    chapters.sort(key=lambda c: int(c['chapter_number']))
    return chapters


def load_chapter_coverage():
    """[(chapter_label, intro_entry)] across all chapters, in chapter order. Each
    intro_entry is a chapter `introduces:` item ({concept, coverage, where, status})."""
    out = []
    for c in _chapters():
        for entry in (c.get('introduces') or []):
            out.append((chapter_label(c['chapter_number']), entry))
    return out


def load_chapter_introductions():
    """{concept_id: [chapter_label, ...]} -- which chapter(s) debut each concept."""
    out = {}
    for label, entry in load_chapter_coverage():
        out.setdefault(entry.get('concept'), []).append(label)
    return out


def integrity_errors(catalog=None, intros=None):
    """Drift the guardrail must block: a chapter introduces a concept absent from the
    catalog (typo / orphan), or a concept debuts in more than one chapter. Reads the real
    files by default; pass `catalog`/`intros` to check synthetic data (tests)."""
    errors = []
    ids = {c.get('id') for c in (load_catalog() if catalog is None else catalog)}
    intros = load_chapter_introductions() if intros is None else intros
    for cid, chapters in intros.items():
        if cid not in ids:
            errors.append('chapter(s) %s introduce %r, which is not in the catalog'
                          % (', '.join(chapters), cid))
        if len(chapters) > 1:
            errors.append('concept %r debuts in multiple chapters (%s) -- it should debut once'
                          % (cid, ', '.join(chapters)))
    return errors


def generate():
    catalog = load_catalog()
    coverage = {}  # concept_id -> (chapter_label, entry)
    for label, entry in load_chapter_coverage():
        coverage.setdefault(entry.get('concept'), (label, entry))

    lines = []
    lines.append('# Manchego Stars — FE8 Onboarding Parity')
    lines.append('')
    lines.append('<!-- GENERATED FILE — do not edit by hand.')
    lines.append('     Source:     campaigns/rime-of-the-frostmaiden/onboarding-catalog.yaml')
    lines.append('                 + each chapters/ch*.yaml `introduces:` list')
    lines.append('     Regenerate: python3 tools/gen_onboarding_index.py')
    lines.append('     Integrity:  tools/test_onboarding.py (orphan / double-debut guard) -->')
    lines.append('')
    lines.append('Combat is vanilla-strict, so this is not about new mechanics — it is about')
    lines.append('**timing**: whenever a concept first becomes relevant in *our* chapter order, our')
    lines.append('players should get the same heads-up a vanilla player gets, via the same kind of')
    lines.append('channel. The catalog is what vanilla teaches; `introduces:` is where we cover it.')
    lines.append('The dialogue-pass skill cross-checks both at beat-planning time.')
    lines.append('')
    lines.append('**channel:** `tutorial` = `PLAY_FLAG_TUTORIAL`-gated box (a veteran who declines')
    lines.append('the tutorial never sees it) · `dialogue` = mandatory story line, shown to everyone')
    lines.append('· `both` = vanilla uses each.')
    lines.append('')
    lines.append('| Concept | Vanilla channel | Our coverage |')
    lines.append('|---|---|---|')
    pending = []
    for c in catalog:
        cid = c.get('id')
        cov = coverage.get(cid)
        if cov:
            label, entry = cov
            cover_cell = '%s — %s (%s)' % (label, squish(entry.get('coverage') or '—'),
                                           squish(entry.get('status') or 'planned'))
        else:
            cover_cell = '— *(pending)*'
            pending.append(c)
        lines.append('| %s — %s | %s | %s |'
                     % (cid, squish(c.get('concept')), squish(c.get('vanilla_channel')),
                        cover_cell))
    lines.append('')
    if pending:
        lines.append('## Pending coverage')
        lines.append('')
        lines.append('Concepts vanilla teaches that no chapter covers yet. As each chapter is')
        lines.append('authored, the dialogue-pass parity step should claim the ones debuting there')
        lines.append('(add an `introduces:` entry) or confirm they belong later.')
        lines.append('')
        for c in pending:
            lines.append('- **%s** — %s _(vanilla: %s; %s)_'
                         % (c.get('id'), squish(c.get('concept')),
                            squish(c.get('vanilla_channel')), squish(c.get('citation') or '—')))
        lines.append('')
    return '\n'.join(lines), (len(catalog), len(catalog) - len(pending))


def main():
    errs = integrity_errors()
    if errs:
        print('ONBOARDING INTEGRITY (%d):' % len(errs), file=sys.stderr)
        for e in errs:
            print('  - ' + e, file=sys.stderr)
        return 1
    content, (total, covered) = generate()
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Wrote %s (%d/%d concepts covered).' % (OUT, covered, total), file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
