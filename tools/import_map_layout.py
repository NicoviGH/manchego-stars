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
import sys


ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root (worktree-aware)
sys.path.insert(0, os.path.join(ROOT,'tools'))
from map_tileset_tool import (_tileset_from_dir, compile_layout,
                              preserved_terrain_targets, render_grid,
                              vanilla_layout_data)


def validate_vanilla_retile(export_data, decomp_root, maps_root):
    """Reject Snowy Bern exports that alter protected vanilla terrain sequences."""
    if export_data.get('tileset', 'snowy-bern') != 'snowy-bern':
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
    target_tileset = _tileset_from_dir(
        os.path.join(maps_root, 'tilesets/snowy-bern'))
    expected_targets = preserved_terrain_targets(
        source_cells, source_terrain, target_tileset, rules, width)

    errors = []
    for cell, expected in expected_targets.items():
        actual = grid[cell]
        if actual != expected:
            errors.append('forest sequence at (%d, %d) is tile %d; expected tile %d' %
                          (cell % width, cell // width, actual, expected))
    if errors:
        raise ValueError('; '.join(errors))


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
    try:
        validate_vanilla_retile(export_data, os.path.join(ROOT, 'fireemblem8u'),
                                os.path.join(ROOT, 'campaigns/rime-of-the-frostmaiden/maps'))
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
