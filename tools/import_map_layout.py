#!/usr/bin/env python3
"""Import an editor-exported layout JSON -> compile to the decomp .mar/.json pair in
campaigns/.../maps/ and render a confirmation preview under /tmp/.

Usage: import_map_layout.py <map-stem> [src-json]
e.g.   import_map_layout.py ch01-the-iron-trail ~/Downloads/ch01-layout.json
       (src defaults to ~/Downloads/<map-stem>-layout.json; ch00/prologue stems also try
        ~/Downloads/prologue-layout.json and ch01 stems ~/Downloads/ch01-layout.json --
        any other stem has no second fallback)"""
import json
import os
import re
import sys


ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root (worktree-aware)
sys.path.insert(0, os.path.join(ROOT,'tools'))
from map_tileset_tool import (_tileset_from_dir, compile_layout,
                              preserved_terrain_targets, render_grid,
                              tilesets_are_compatible_variants,
                              vanilla_layout_data)


TERRAIN_BY_NAME = {}
for _line in open(os.path.join(ROOT, 'fireemblem8u/include/constants/terrains.h')):
    _m = re.match(r'\s*(TERRAIN_\w+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)', _line)
    if _m:
        TERRAIN_BY_NAME[_m.group(1)] = int(_m.group(2), 0)


def validate_terrain_matches_vanilla(export_data, decomp_root, maps_root, declared=None):
    """A retile inherits vanilla's terrain, whatever tileset it is painted on.

    Runs for EVERY tileset, unlike validate_vanilla_retile below, which only ever covered
    snowy-bern. That gap is why ch05's fence->wall drift had to be caught by hand: eleven
    cells changed role while looking right, and FENCE vs WALL differ in exactly one place
    (TerrainTable_MovCost_Fly*), so the map would have quietly stopped our one Pegasus
    Knight crossing the wall he is meant to fly over. Same failure class as ch04's
    unobtainable village.

    The fix for a violation is to author the TERRAIN BYTE of the offending metatile in our
    vendored copy of the tileset -- never to swap the painted tile.

    `declared` is the ONE escape hatch: a chapter that deliberately departs from vanilla's
    terrain (ch06 seals a corner with cliff, and turns a snag into a lowered bridge) lists
    those cells in its YAML under `terrain_divergence`. It is a cell-by-cell allowlist on
    purpose -- naming the exact coordinate and the exact before/after keeps the guard live
    everywhere else, so the ch05 fence->wall class of accident still fails loudly. An
    undeclared drift is a bug; a declared one is a decision with an ADR behind it.
    """
    layout = export_data.get('vanilla_layout')
    if not layout:
        return                        # a genuine from-scratch canvas has no vanilla to match
    width, height, source_cells, source_terrain = vanilla_layout_data(decomp_root, layout)
    grid = export_data.get('grid') or []
    if len(grid) != width * height:
        return                        # dimension mismatch is reported by the checks below
    tileset = _tileset_from_dir(os.path.join(
        maps_root, 'tilesets', export_data.get('tileset', 'snowy-bern')))
    errors = []
    for cell, (painted, vanilla_metatile) in enumerate(zip(grid, source_cells)):
        want = source_terrain[vanilla_metatile]
        got = tileset.terrain(painted)
        if (cell % width, cell // width) in (declared or {}):
            expected = (declared or {})[(cell % width, cell // width)]
            if got == expected:
                continue
            errors.append('(%d, %d) declares a divergence to 0x%02x but is painted 0x%02x'
                          % (cell % width, cell // width, expected, got))
            continue
        if got != want:
            errors.append('(%d, %d) is terrain 0x%02x; vanilla %s has 0x%02x '
                          '(metatile %d)' % (cell % width, cell // width, got,
                                             layout, want, painted))
    if errors:
        raise ValueError(
            'retile changed terrain on %d cell(s) -- re-author the metatile terrain byte '
            'in maps/tilesets/%s/, do not swap the tile: %s'
            % (len(errors), export_data.get('tileset'), '; '.join(errors[:8])
               + (' ...' if len(errors) > 8 else '')))


def validate_vanilla_retile(export_data, decomp_root, maps_root, declared=None, stem=None):
    """Reject Snowy Bern exports that alter protected vanilla terrain sequences.

    Runs for snowy-bern AND for any compatible variant of it (identical .4bpp, .bin differing
    only at slots the base declares unused). An exact name compare used to skip the whole
    invariant for `snowy-bern-ice`, which is how ch06 could violate all 25 protected cells and
    still import clean -- the generator was taught about variants in the same change and the
    importer was not.

    `declared` exempts cells the chapter lists under `terrain_divergence:`. That is the
    sanctioned form of the #193 escape clause ("a deliberate forest-composition departure is a
    new map-design decision, not a quiet override"): ch06 is a frozen lake with no trees, so
    its 23 forest cells become snow drifts. The exemption is per-coordinate, so a chapter that
    merely retiles a forest is still held to the sequence, cell for cell.
    """
    tileset = export_data.get('tileset', 'snowy-bern')
    if not tilesets_are_compatible_variants(maps_root, 'snowy-bern', tileset):
        return

    mode = export_data.get('retile_mode')
    layout = export_data.get('vanilla_layout')
    if mode == 'custom':
        return
    if mode not in (None, 'vanilla'):
        raise ValueError('unknown retile_mode %r; regenerate this export with '
                         'tools/gen_map_editor.py' % mode)
    if not layout:
        raise ValueError('Snowy Bern export is missing retile metadata; regenerate it '
                         'with tools/gen_map_editor.py (custom canvases must explicitly '
                         'use retile_mode "custom")')

    width, height, source_cells, source_terrain = vanilla_layout_data(
        decomp_root, layout)
    if (export_data.get('width'), export_data.get('height')) != (width, height):
        raise ValueError('vanilla layout %s is %dx%d; export is %sx%s' %
                         (layout, width, height, export_data.get('width'),
                          export_data.get('height')))
    grid = export_data.get('grid') or []
    if len(grid) != width * height:
        raise ValueError('grid has %d cells; expected %d for vanilla layout %s' %
                         (len(grid), width * height, layout))

    with open(os.path.join(maps_root, 'reskin-learned.json'),
              encoding='utf-8') as source:
        rules = json.load(source)
    target_tileset = _tileset_from_dir(os.path.join(maps_root, 'tilesets', tileset))
    expected_targets = preserved_terrain_targets(
        source_cells, source_terrain, target_tileset, rules, width)

    replaced = (_chapter_for_map(stem) or {}).get('forest_composition') == 'replaced'
    errors = []
    for cell, expected in expected_targets.items():
        if (cell % width, cell // width) in (declared or {}):
            continue                      # a declared terrain divergence, with an ADR behind it
        if replaced and source_terrain[source_cells[cell]] == TERRAIN_BY_NAME['TERRAIN_FOREST']:
            continue                      # the chapter declared it has no forest to translate
        actual = grid[cell]
        if actual != expected:
            errors.append('forest sequence at (%d, %d) is tile %d; expected tile %d' %
                          (cell % width, cell // width, actual, expected))
    if errors:
        raise ValueError('; '.join(errors))


def _terrain_byte(value):
    """A `to:` entry -> terrain byte. Accepts '0x0C', '0x0c', 12 and 'TERRAIN_FOREST'.

    Quoting hex in YAML is easy to forget, and `yaml.safe_load` turns an unquoted 0x0C into
    the int 12 -- which used to reach int(value, 0) and raise a bare TypeError naming neither
    the chapter nor the cell.
    """
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.upper().startswith('TERRAIN_'):
        return TERRAIN_BY_NAME[text.upper()]
    return int(text, 0)


def _chapter_for_map(stem):
    """The chapter YAML whose `map.file` names `stem`, or None.

    Matched on the map file's BASENAME. An earlier version compared the chapter `id`
    (ch06-the-maer-monster) against the map stem (ch06-maer-monster) and prefix-matched
    `map.file` -- which is always 'maps/<stem>.<ext>' and so never starts with the stem.
    Both tests failed for every chapter, silently returning "nothing declared" and taking
    the guard's escape hatch with it.
    """
    path = os.path.join(ROOT, 'campaigns/rime-of-the-frostmaiden/chapters')
    if not os.path.isdir(path):
        return None
    import yaml
    for name in sorted(os.listdir(path)):
        if not name.endswith(('.yaml', '.yml')):
            continue
        with open(os.path.join(path, name), encoding='utf-8') as handle:
            data = yaml.safe_load(handle) or {}
        declared = (data.get('map') or {}).get('file') or ''
        if os.path.splitext(os.path.basename(declared))[0] == stem:
            return data
    return None


def _declared_divergence(stem):
    """A chapter's `terrain_divergence:` allowlist -> {(x, y): terrain_byte}.

    Lives in the chapter YAML because that is where the campaign's facts live and where the
    ADR can point; no chapter, or no block, means "nothing declared", which is the right
    default for every chapter that simply inherits vanilla terrain.
    """
    data = _chapter_for_map(stem)
    if not data:
        return {}
    return {(row['tile'][0], row['tile'][1]): _terrain_byte(row['to'])
            for row in data.get('terrain_divergence') or []}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        sys.exit('usage: import_map_layout.py <map-stem> [src-json]')
    stem = argv[0]
    if len(argv) > 1:
        src = os.path.expanduser(argv[1])
    else:
        # Legacy fallbacks apply ONLY to their own chapters -- a stale prologue export
        # must never silently compile as some other chapter's map (#40 review).
        cands = [os.path.expanduser('~/Downloads/%s-layout.json' % stem),
                 os.path.expanduser('~/Downloads/ch01-layout.json')
                 if stem.startswith('ch01') else None,
                 os.path.expanduser('~/Downloads/prologue-layout.json')
                 if stem.startswith(('ch00', 'prologue')) else None]
        src = next((candidate for candidate in cands
                    if candidate and os.path.exists(candidate)), None)
        if not src:
            sys.exit('no exported layout JSON found '
                     '(looked for ~/Downloads/%s-layout.json)' % stem)

    with open(src, encoding='utf-8') as source:
        export_data = json.load(source)
    decomp = os.path.join(ROOT, 'fireemblem8u')
    maps_root = os.path.join(ROOT, 'campaigns/rime-of-the-frostmaiden/maps')
    try:
        validate_terrain_matches_vanilla(export_data, decomp, maps_root,
                                         declared=_declared_divergence(stem))
        validate_vanilla_retile(export_data, decomp, maps_root,
                                declared=_declared_divergence(stem), stem=stem)
    except ValueError as error:
        sys.exit('ERROR: %s' % error)

    width, height, flat = (export_data['width'], export_data['height'],
                           export_data['grid'])
    if len(flat) != width * height:
        sys.exit('ERROR: grid size mismatch')
    grid = [flat[row * width:(row + 1) * width] for row in range(height)]

    tileset = export_data.get('tileset', 'snowy-bern')
    mapdir = os.path.join(ROOT, 'campaigns/rime-of-the-frostmaiden/maps')
    out_bin = os.path.join(mapdir, '%s.mar' % stem)
    compile_layout(grid, out_bin, stem, tileset=tileset)
    print('compiled', out_bin, '(%dx%d, tileset %s)' % (width, height, tileset))

    target_tileset = _tileset_from_dir(os.path.join(mapdir, 'tilesets/%s' % tileset))
    scratch = os.path.join('/tmp', 'manchego-stars-review')
    os.makedirs(scratch, exist_ok=True)
    preview = render_grid(target_tileset, grid,
                          os.path.join(scratch, '%s-painted.png' % stem), zoom=4)
    print('rendered preview', preview, '; imported from', src)


if __name__ == '__main__':
    main()
