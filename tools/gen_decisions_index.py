#!/usr/bin/env python3
"""Generate docs/decisions.md -- the INDEX over docs/decisions/*.md.

The ADR files are the single source of truth; this index is DERIVED. Do not hand-edit
docs/decisions.md -- add or edit a file under docs/decisions/ and regenerate:

    python3 tools/gen_decisions_index.py

Freshness is enforced by tools/check.py (it imports generate() and diffs the committed
file), the same way docs/CHAPTERS.md and docs/CLASSES.md are held.

Why the split (#384): decisions.md was 728 KB -- about 197,000 tokens -- and AGENTS.md's
session-start checklist told every session to read it before touching code. That is a whole
context window spent before any work starts, so in practice nobody read it and the
checklist's most load-bearing line was quietly ignored. An instruction no one can follow is
worse than none. The index is a few thousand tokens; a session reads it and then opens the
two or three ADRs its task actually needs.

Stdlib + pyyaml only, so the lightweight CI `checks` job can import it.
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from yaml_loader import yaml_load                                     # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADR_DIR = os.path.join(REPO, 'docs', 'decisions')
OUT = os.path.join(REPO, 'docs', 'decisions.md')

# The section order of the original document, preserved so the index reads the way the file
# always did. A section with no ADRs simply does not appear.
SECTION_ORDER = [
    'Engine & Tech Stack',
    'Documentation Model',
    'Working Conventions (Definition of Done)',
    'Combat System',
    'Weapon & Magic Systems',
    'Economy',
    'Distribution & Scope',
    'Art & Audio',
    'Class Mapping & Promotions',
    'Story & Dialogue',
    'Operational Gotchas (durable)',
    'Open Questions (not yet decided)',
]

FRONT_MATTER = re.compile(r'\A---\n(.*?)\n---\n', re.S)


def parse(path):
    """One ADR file -> its front matter plus the first prose line, for the index blurb."""
    with open(path, encoding='utf-8') as fh:
        text = fh.read()
    m = FRONT_MATTER.match(text)
    if not m:
        raise ValueError('%s has no front matter' % os.path.relpath(path, REPO))
    meta = yaml_load(m.group(1)) or {}
    body = text[m.end():]
    # Skip the `# Title` line the file repeats for standalone readability.
    body = re.sub(r'\A\s*#[^\n]*\n', '', body)
    blurb = ''
    for line in body.split('\n'):
        line = line.strip()
        if line and not line.startswith(('|', '#', '```', '---', '>')):
            blurb = line
            break
    meta['path'] = 'decisions/' + os.path.basename(path)
    meta['blurb'] = blurb
    return meta


def adrs():
    return [parse(p) for p in sorted(glob.glob(os.path.join(ADR_DIR, '[0-9]*.md')))]


def section_notes():
    """`_<slug>.md` files: prose that belongs to a SECTION rather than to any one decision.

    These carried the section's framing in the original document -- including the whole of
    "Open Questions", which has no decisions in it at all and would otherwise vanish from a
    decisions-only index. Underscore-prefixed so the ADR glob above skips them.
    """
    notes = {}
    for path in sorted(glob.glob(os.path.join(ADR_DIR, '_*.md'))):
        with open(path, encoding='utf-8') as fh:
            text = fh.read()
        m = FRONT_MATTER.match(text)
        if not m:
            raise ValueError('%s has no front matter' % os.path.relpath(path, REPO))
        meta = yaml_load(m.group(1)) or {}
        notes[meta.get('section')] = text[m.end():].strip('\n')
    return notes


def squish(text, limit=150):
    """One line, no markdown emphasis, trimmed on a word boundary.

    Backticks and asterisks only. Stripping `_` as well turned `rom_bg_preview.py` into
    `rombgpreview.py` in the index, which `check_tool_refs_exist` then correctly reported as
    a dangling pointer -- an index is not allowed to corrupt the identifiers it cites (#384).
    """
    text = re.sub(r'\s+', ' ', re.sub(r'[`*]', '', text or '')).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(' ', 1)[0] + '...'


def generate():
    """Return (index_text, adr_list). check.py diffs [0] against the committed file."""
    found = adrs()
    notes = section_notes()
    by_section = {}
    for a in found:
        by_section.setdefault(a.get('section') or 'Uncategorised', []).append(a)
    for section in notes:                    # a prose-only section still gets a heading
        by_section.setdefault(section, [])

    order = [s for s in SECTION_ORDER if s in by_section]
    order += sorted(s for s in by_section if s not in SECTION_ORDER)

    out = []
    out.append('# Design Decisions — Manchego Stars')
    out.append('')
    out.append('> These decisions are **settled**. Do not re-open them without a strong reason.')
    out.append('>')
    out.append('> **This file is GENERATED.** Each decision is one file under `docs/decisions/`;')
    out.append('> this is the index. Add or edit the ADR, then regenerate:')
    out.append('> `python3 tools/gen_decisions_index.py`. `tools/check.py` fails if it is stale.')
    out.append('')
    out.append('%d decisions. Read this index, then open the two or three you need — the whole'
               % len(found))
    out.append('set is ~197,000 tokens and no session has ever needed all of it at once.')
    out.append('')
    out.append('**Contents:** ' + ' · '.join(
        '[%s](#%s)' % (s, anchor(s)) for s in order))
    out.append('')

    for section in order:
        out.append('---')
        out.append('')
        out.append('## ' + section)
        out.append('')
        if section in notes:
            out.append(notes[section])
            out.append('')
        rows = sorted(by_section[section], key=lambda a: a.get('id') or 0)
        if not rows:
            continue
        # Title only. These titles are full sentences that state the decision -- "A read that
        # never changes is read ONCE" -- so a separate blurb column doubled the index's size
        # to say the same thing twice.
        out.append('| | decision | date | issues |')
        out.append('|---|---|---|---|')
        for a in rows:
            issues = ' '.join('#%s' % i for i in (a.get('issues') or [])) or '—'
            out.append('| `%04d` | [%s](%s) | %s | %s |' % (
                a.get('id') or 0, squish(a.get('title'), 120), a['path'],
                a.get('date') or '—', issues))
        out.append('')

    text = '\n'.join(out)
    return text.rstrip('\n') + '\n', found


def anchor(heading):
    """GitHub's heading-anchor rules, for the Contents line."""
    a = heading.lower()
    a = re.sub(r'[^\w\s-]', '', a)
    return re.sub(r'\s+', '-', a).strip('-')


def main():
    text, found = generate()
    with open(OUT, 'w', encoding='utf-8') as fh:
        fh.write(text)
    print('docs/decisions.md: %d decisions indexed (%.0f KB)' % (len(found), len(text) / 1024))
    return 0


if __name__ == '__main__':
    sys.exit(main())
