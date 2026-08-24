#!/usr/bin/env python3
"""Which vanilla layout did one of our chapter maps come from?

A retile PRESERVES GEOMETRY, so the donor is recoverable from the artifact rather than
read off a label. `fe8_base_map` in a chapter YAML is prose that nothing consumes, and
ch01's was wrong for months (docs/decisions.md -> "A base-map LABEL is prose -- the donor
is DERIVED"). This is the derivation, committed so the answer is reproducible instead of
hand-transcribed from somebody's scratch script.

Method: take our `.mar`, take every VANILLA layout of the SAME DIMENSIONS, and compare the
blocked-cell pattern -- for each cell, whether its metatile's terrain is impassable under
that layout's OWN tile config. Dimensions eliminate most candidates before any comparison
runs; the real donor then scores far above whatever is left.

Three things this gets right that an ad-hoc version does not:

  * IMPASSABLE is DECLARED here, below. The score is meaningless without it and the set is
    a judgement call (does a river block? a snag?), so it is written down rather than
    reinvented per run. Change it and every number in the ADR changes with it.
  * OUR OWN injected layouts are EXCLUDED. The build copies each of our maps into the
    decomp's `graphics/map/layout/`, so a naive scan of that directory finds ch01's own
    artifact and reports it as ch01's donor at ~100%. Worse, `_vanilla_tileconfig_path`
    cannot resolve a tile config for them: it WARNs and falls back to TileConfiguration1,
    which silently scores against the wrong terrain table. The exclusion list is READ from
    build_campaign's `CHNN_LAYOUT` constants, not matched on a name prefix -- registering a
    new chapter map excludes it automatically.
  * TIES ARE REPORTED. `Ch5Map.mar` and `Ch5TownMapPast.mar` are BYTE-IDENTICAL, so ch05
    scores 100% against both and no amount of geometry will separate them. A tool that
    printed the first one would be inventing a certainty it does not have.

Stdlib + our own map_tileset_tool only, like hosts.py next to it.

Usage:
    python3 tools/map_donor.py                 # every chapter map we ship
    python3 tools/map_donor.py ch01            # one of them, with runners-up
"""
import json
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import map_tileset_tool as mt                                   # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECOMP = os.path.join(REPO, 'fireemblem8u')
MAPS = os.path.join(REPO, 'campaigns/rime-of-the-frostmaiden/maps')
LAYOUT_DIR = os.path.join(DECOMP, 'graphics/map/layout')
BUILD_CAMPAIGN = os.path.join(REPO, 'tools', 'build_campaign.py')

# The blocked set: terrain a foot unit cannot enter. Declared, not derived -- see the
# docstring. Ids are terrains.h, named as gen_map_editor's palette names them.
IMPASSABLE = {
    0x0f,      # (unnamed solid)
    0x12,      # Peak
    0x19,      # Fence
    0x1a,      # Wall
    0x1d,      # Pillar
    0x26,      # Cliff
    0x2c,      # Building edge
    0x2e,      # Building / roof
    0x32,      # Fence
}
# NOT blocked, on purpose: water (0x15 sea, 0x36 deep, 0x3c) and rivers (0x10). They stop
# foot units but they are exactly what a retile REPAINTS -- ch06 turns sea into walkable
# ice. Counting them as walls would score a coast map against its own future.

_LAYOUT_CONST = re.compile(r"^(?:CH\d+|PROLOGUE)_LAYOUT\s*=\s*\(\s*'([A-Za-z0-9_]+)'")


def our_layout_labels(path=BUILD_CAMPAIGN):
    """The asset labels our build writes into the decomp's layout directory.

    Read from build_campaign's SOURCE so a newly registered chapter is excluded the moment
    its constant exists -- there is no second list to remember.
    """
    labels = set()
    with open(path, encoding='utf-8') as source:
        for line in source:
            match = _LAYOUT_CONST.match(line)
            if match:
                labels.add(match.group(1))
    return labels


def vanilla_layouts(exclude=None):
    """Every layout in the decomp that is actually VANILLA, by name."""
    exclude = our_layout_labels() if exclude is None else exclude
    found = []
    for entry in sorted(os.listdir(LAYOUT_DIR)):
        if not entry.endswith('.mar'):
            continue
        name = entry[:-4]
        if name in exclude or name.startswith('ChTest'):
            continue
        found.append(name)
    return found


def blocked_grid(cells, terrain):
    return [1 if terrain[m] in IMPASSABLE else 0 for m in cells]


def our_map(stem):
    """(width, height, blocked_grid) for one of our painted maps."""
    with open(os.path.join(MAPS, stem + '.json'), encoding='utf-8') as source:
        info = json.load(source)
    width, height = info['width'], info['height']
    tileset = mt._tileset_from_dir(
        os.path.join(MAPS, 'tilesets', info.get('tileset', 'snowy-bern')))
    with open(os.path.join(MAPS, stem + '.mar'), 'rb') as source:
        raw = source.read()
    cells = [struct.unpack_from('<H', raw, i * 2)[0] >> 5 for i in range(width * height)]
    return width, height, [1 if tileset.terrain(m) in IMPASSABLE else 0 for m in cells]


def candidates(stem):
    """[(score, layout)] for every vanilla layout of our map's dimensions, best first."""
    width, height, ours = our_map(stem)
    scored = []
    for name in vanilla_layouts():
        try:
            vw, vh, cells, terrain = mt.vanilla_layout_data(DECOMP, name)
        except Exception:
            continue
        if (vw, vh) != (width, height):
            continue
        theirs = blocked_grid(cells, terrain)
        agree = sum(1 for a, b in zip(ours, theirs) if a == b) / float(len(ours))
        scored.append((agree, name))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return width, height, scored


def identical_to(name, others):
    """Layouts whose .mar is byte-identical to `name` -- an unbreakable tie."""
    def blob(n):
        with open(os.path.join(LAYOUT_DIR, n + '.mar'), 'rb') as source:
            return source.read()
    mine = blob(name)
    return [n for n in others if n != name and blob(n) == mine]


def report(stems, verbose=False):
    for stem in stems:
        width, height, scored = candidates(stem)
        head = '%-26s %-7s' % (stem, '%dx%d' % (width, height))
        if not scored:
            print('%s  no vanilla layout of these dimensions' % head)
            continue
        best, name = scored[0]
        tied = [n for score, n in scored if abs(score - best) < 1e-9 and n != name]
        byte_tied = identical_to(name, tied)
        note = ''
        if byte_tied:
            note = '  TIE with %s (byte-identical .mar -- geometry cannot separate them)' % (
                ', '.join(byte_tied))
        elif tied:
            note = '  TIE with %s' % ', '.join(tied)
        print('%s %-22s %5.1f%%%s' % (head, name, best * 100, note))
        if verbose:
            for score, other in scored[1:4]:
                print('%-34s   runner-up %-20s %5.1f%%' % ('', other, score * 100))


def main(argv):
    stems = [a for a in argv[1:] if not a.startswith('-')]
    known = sorted(f[:-4] for f in os.listdir(MAPS) if f.endswith('.mar'))
    if stems:
        chosen = [s for s in known if any(s.startswith(a) for a in stems)]
        if not chosen:
            sys.exit('no map matching %s in %s (have: %s)'
                     % (', '.join(stems), MAPS, ', '.join(known)))
    else:
        chosen = known
    report(chosen, verbose=bool(stems))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
