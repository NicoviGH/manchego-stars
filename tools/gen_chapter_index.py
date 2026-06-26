#!/usr/bin/env python3
"""Generate docs/CHAPTERS.md (the chapter overview table) from the per-chapter
YAML in campaigns/rime-of-the-frostmaiden/chapters/ch*.yaml.

The YAML is the single source of truth for per-chapter facts; this index is
DERIVED. Do not hand-edit docs/CHAPTERS.md -- edit the YAML and regenerate:

    python3 tools/gen_chapter_index.py

Freshness is enforced by tools/check.py (it imports generate() and diffs the
committed file). Stdlib + pyyaml only.
"""

import glob
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAPTERS = os.path.join(ROOT, 'campaigns/rime-of-the-frostmaiden/chapters')
OUT = os.path.join(ROOT, 'docs/CHAPTERS.md')

# cadence token (YAML) -> emoji + human label for the table + legend.
CADENCE = {
    'tutorial':           ('\U0001F7E6', 'tutorial'),
    'full_party_intro':   ('\U0001F7E6', 'full-party intro'),
    'breather_defend':    ('\U0001F7E6', 'breather / defend'),
    'gimmick_multilevel': ('\U0001F7E8', 'gimmick (multi-level)'),
    'big_battle_seize':   ('\U0001F7E5', 'big battle (seize)'),
    'monster_debut':      ('\U0001F7E8', 'monster debut (fog)'),
    'first_boss':         ('\U0001F7E5', 'first boss'),
    'marquee_setpiece':   ('\U0001F3AC', 'marquee set-piece'),
    'big_battle_gray':    ('\U0001F7E5', 'big battle (gray)'),
    'scripted_defeat':    ('\U0001F3AC', 'scripted defeat'),
}

# objective.type token -> FE-canonical label.
OBJECTIVE = {
    'defeat_boss':         'DefeatBoss',
    'defeat_all':          'DefeatAll',
    'seize':               'Seize',
    'survive':             'Survive',
    'defeat_boss_or_talk': 'DefeatBoss / Talk',
}


def squish(s):
    return re.sub(r'\s+', ' ', str(s if s is not None else '')).strip()


def chapter_label(num):
    return 'P' if int(num) == 0 else str(int(num))


def unlocks_label(target_id, known_numbers):
    """Resolve a chapter id (e.g. "ch05-the-elven-tomb" or "ch09-revels-end") to a
    short "Ch N" label, flagging targets that have no YAML yet (post-MVP)."""
    if target_id is None:
        return '—'
    m = re.match(r'ch0*(\d+)', target_id)
    if not m:
        return target_id
    n = int(m.group(1))
    return 'Ch %d' % n if n in known_numbers else 'Ch %d (post-MVP)' % n


def objective_label(obj):
    if not obj:
        return '—'
    t = obj.get('type')
    if t in OBJECTIVE:
        return OBJECTIVE[t]
    return ' '.join(w.capitalize() for w in str(t).split('_'))


def recruits_label(post):
    if not post:
        return '—'
    playable = [u['id'] for u in (post.get('units_available_to_recruit') or [])]
    npcs = [u['id'] for u in (post.get('caravan_npcs_added') or [])]
    parts = []
    if playable:
        parts.append(', '.join(playable))
    if npcs:
        parts.append('+npc: ' + ', '.join(npcs))
    return ' '.join(parts) if parts else '—'


def generate():
    files = sorted(glob.glob(os.path.join(CHAPTERS, 'ch*.yaml')))
    if not files:
        sys.exit('No chapter YAML found in %s' % CHAPTERS)

    chapters = [yaml.safe_load(open(f, encoding='utf-8')) for f in files]
    chapters.sort(key=lambda c: int(c['chapter_number']))
    known_numbers = {int(c['chapter_number']) for c in chapters}

    rows = []
    for c in chapters:
        emoji, label = CADENCE.get(c['cadence'], ('', str(c['cadence'])))
        cadence_cell = ' '.join(s for s in (emoji, label) if s)
        obj = c.get('objective')
        objective_cell = squish('%s — %s'
                                % (objective_label(obj), obj and obj.get('description')))
        rows.append([
            chapter_label(c['chapter_number']),
            squish(c['title']),
            cadence_cell,
            objective_cell,
            recruits_label(c.get('post_chapter')),
            unlocks_label((c.get('post_chapter') or {}).get('unlocks_chapter'),
                          known_numbers),
        ])

    # Build the legend from only the cadence tags actually present, grouped by emoji.
    legend_by_emoji = {}
    seen = []
    for c in chapters:
        if c['cadence'] not in seen:
            seen.append(c['cadence'])
    for tok in seen:
        if tok not in CADENCE:
            continue
        emoji, label = CADENCE[tok]
        labels = legend_by_emoji.setdefault(emoji, [])
        if label not in labels:
            labels.append(label)
    legend = ' · '.join('%s %s' % (emoji, ' / '.join(labels))
                             for emoji, labels in legend_by_emoji.items())

    first_num = int(chapters[0]['chapter_number'])
    last_num = int(chapters[-1]['chapter_number'])
    span = ('Prologue–Ch %d' % last_num if first_num == 0
            else 'Ch %d–%d' % (first_num, last_num))

    lines = []
    lines.append('# Manchego Stars — Chapter Index (MVP, %s)' % span)
    lines.append('')
    lines.append('<!-- GENERATED FILE — do not edit by hand.')
    lines.append('     Source:     campaigns/rime-of-the-frostmaiden/chapters/ch*.yaml')
    lines.append('     Regenerate: python3 tools/gen_chapter_index.py')
    lines.append('     Per-chapter facts live in the YAML; this table is derived from it. -->')
    lines.append('')
    lines.append('The per-chapter source of truth is the YAML in')
    lines.append('`campaigns/rime-of-the-frostmaiden/chapters/`. This table is generated from it.')
    lines.append('Forward-looking design (the promotion seam, the Act II–V scaffold, the cadence')
    lines.append('rules) lives in `docs/decisions.md` and `docs/fe8-pacing-reference.md`.')
    lines.append('')
    lines.append('**Cadence legend:** %s' % legend)
    lines.append('')
    lines.append('| # | Title | Cadence | Objective | Recruits | Unlocks |')
    lines.append('|---|---|---|---|---|---|')
    for r in rows:
        lines.append('| %s |' % ' | '.join(r))
    lines.append('')
    return '\n'.join(lines), len(chapters)


def main():
    content, n = generate()
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Wrote %s (%d chapters).' % (OUT, n), file=sys.stderr)


if __name__ == '__main__':
    main()
