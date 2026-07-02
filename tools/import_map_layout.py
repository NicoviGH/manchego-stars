#!/usr/bin/env python3
"""Import an editor-exported layout JSON -> compile to the decomp .mar/.json pair in
campaigns/.../maps/ and render a confirmation preview to map-review/.

Usage: import_map_layout.py <map-stem> [src-json]
e.g.   import_map_layout.py ch01-the-iron-trail ~/Downloads/ch01-layout.json
       (src defaults to ~/Downloads/<map-stem>-layout.json; ch00/prologue stems also try
        ~/Downloads/prologue-layout.json and ch01 stems ~/Downloads/ch01-layout.json --
        any other stem has no second fallback)"""
import sys, os, json
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root (worktree-aware)
sys.path.insert(0, os.path.join(ROOT,'tools'))
from map_tileset_tool import _tileset_from_dir, compile_layout, render_grid

if len(sys.argv)<2:
    sys.exit('usage: import_map_layout.py <map-stem> [src-json]')
stem=sys.argv[1]
if len(sys.argv)>2:
    src=os.path.expanduser(sys.argv[2])
else:
    # Legacy fallbacks apply ONLY to their own chapters -- a stale prologue export
    # must never silently compile as some other chapter's map (#40 review).
    cands=[os.path.expanduser(f'~/Downloads/{stem}-layout.json'),
           os.path.expanduser('~/Downloads/ch01-layout.json') if stem.startswith('ch01') else None,
           os.path.expanduser('~/Downloads/prologue-layout.json')
           if stem.startswith(('ch00','prologue')) else None]
    src=next((c for c in cands if c and os.path.exists(c)), None)
    if not src:
        sys.exit(f'no exported layout JSON found (looked for ~/Downloads/{stem}-layout.json)')
d=json.load(open(src))
W,H,flat=d['width'],d['height'],d['grid']
assert len(flat)==W*H, 'grid size mismatch'
grid=[flat[r*W:(r+1)*W] for r in range(H)]

tileset=d.get('tileset','snowy-bern')     # editor exports stamp their tileset (#40)
mapdir=os.path.join(ROOT,'campaigns/rime-of-the-frostmaiden/maps')
out_bin=os.path.join(mapdir,f'{stem}.mar')
compile_layout(grid, out_bin, stem, tileset=tileset)
print('compiled', out_bin, f'({W}x{H}, tileset {tileset})')

win=_tileset_from_dir(os.path.join(mapdir,f'tilesets/{tileset}'))
prev=render_grid(win, grid, os.path.join(ROOT,f'map-review/{stem}-painted.png'), zoom=4)
print('rendered preview', prev, '; imported from', src)
