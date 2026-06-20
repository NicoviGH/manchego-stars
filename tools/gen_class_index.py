#!/usr/bin/env python3
"""Generate docs/CLASSES.md (the unit roster + class/promotion index) from the
per-unit YAML in campaigns/rime-of-the-frostmaiden/{pcs,npcs}/*.yaml.

The unit YAML is the single source of truth for FE class + promotion; this index
is DERIVED. Do not hand-edit docs/CLASSES.md -- edit the YAML and regenerate:

    python3 tools/gen_class_index.py

The *rationale* (why each PC maps to its FE class, the promotion seam) lives in
docs/decisions.md, not here. Freshness is enforced by tools/check.py (it imports
generate() and diffs the committed file). Stdlib + pyyaml only.
"""

import glob
import os
import re
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PCS = os.path.join(ROOT, 'campaigns/rime-of-the-frostmaiden/pcs')
NPCS = os.path.join(ROOT, 'campaigns/rime-of-the-frostmaiden/npcs')
OUT = os.path.join(ROOT, 'docs/CLASSES.md')


def squish(s):
    return re.sub(r'\s+', ' ', str(s if s is not None else '')).strip()


def promotion_cell(promo):
    """"**Default** / Other / Other" from promotion.branch + promotion.default."""
    if not promo:
        return '—'
    branch = promo.get('branch') or []
    if not branch:
        return '—'
    default = promo.get('default')
    ordered = []
    for c in [default] + list(branch):
        if c is not None and c not in ordered:
            ordered.append(c)
    return ' / '.join('**%s**' % c if i == 0 and default else c
                      for i, c in enumerate(ordered))


def fe_base(unit):
    cls = (unit.get('fe_stats') or {}).get('class')
    return 'TBD (post-MVP)' if cls is None or not str(cls).strip() else cls


def dnd_source(unit):
    d = unit.get('dnd')
    if not d:
        return '—'
    src = squish(d.get('class'))
    race = squish(d.get('race'))
    return src if not race else '%s — %s' % (src, race)


def load_dir(d):
    return [yaml.safe_load(open(f, encoding='utf-8'))
            for f in sorted(glob.glob(os.path.join(d, '*.yaml')))]


def generate():
    pcs = sorted(load_dir(PCS), key=lambda u: str(u['id']))
    npcs = sorted(load_dir(NPCS), key=lambda u: str(u['id']))
    if not pcs:
        sys.exit('No PC YAML found in %s' % PCS)

    lines = []
    lines.append('# Manchego Stars — Unit Roster & Class Index')
    lines.append('')
    lines.append('<!-- GENERATED FILE — do not edit by hand.')
    lines.append('     Source:     campaigns/rime-of-the-frostmaiden/{pcs,npcs}/*.yaml')
    lines.append('     Regenerate: python3 tools/gen_class_index.py')
    lines.append('     Class/promotion facts live in the unit YAML; this table is derived from it. -->')
    lines.append('')
    lines.append('Every unit is a **stock vanilla FE8 class** (bases/growths/caps verbatim from')
    lines.append('`fireemblem8u/src/data_classes.c`); D&D is flavor only. The *rationale* for each')
    lines.append('mapping and the promotion seam live in `docs/decisions.md` — this is just the')
    lines.append('roster derived from the unit YAML.')
    lines.append('')
    lines.append('## Player characters')
    lines.append('')
    lines.append('| PC | D&D source | FE base | Promotion (player picks; **default** bold) |')
    lines.append('|---|---|---|---|')
    for u in pcs:
        lines.append('| %s | %s | %s | %s |'
                     % (squish(u['name']), dnd_source(u), fe_base(u),
                        promotion_cell(u.get('promotion'))))
    lines.append('')
    lines.append('## Recruits & NPCs')
    lines.append('')
    lines.append('| Unit | FE base | Promotion | Joins via |')
    lines.append('|---|---|---|---|')
    for u in npcs:
        joins = squish(u.get('recruited_via')) or '—'
        lines.append('| %s | %s | %s | %s |'
                     % (squish(u['name']), fe_base(u),
                        promotion_cell(u.get('promotion')), joins))
    lines.append('')
    lines.append('> **Note.** `pepperjack`/`brie` carry `fe_stats.class: null` because they are NOT')
    lines.append('> roster recruits — they are vanilla FE8 **map ballistae** (siege emplacements the')
    lines.append('> party mans), flavored as RBG\'s cannon-constructs, appearing from the vanilla')
    lines.append('> ballista era (~Ch10). Recruit class/role for Trex, Sahnar, Lupin, Basil is LOCKED')
    lines.append('> in their unit YAML (full bases/growths authored at wiring); `docs/CHAPTERS.md`')
    lines.append('> shows where each joins.')
    lines.append('')
    return '\n'.join(lines), (len(pcs), len(npcs))


def main():
    content, (npc, nnpc) = generate()
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Wrote %s (%d PCs, %d NPCs).' % (OUT, npc, nnpc), file=sys.stderr)


if __name__ == '__main__':
    main()
