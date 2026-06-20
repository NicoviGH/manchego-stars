#!/usr/bin/env python3
"""Import an editor-exported layout JSON -> compile to the decomp .mar/.json pair in
campaigns/.../maps/ and render a confirmation preview to map-review/.

Usage: import_map_layout.py <map-stem> [src-json]
e.g.   import_map_layout.py ch01-the-iron-trail ~/Downloads/ch01-layout.json
       (src defaults to ~/Downloads/<map-stem>-layout.json, then ~/Downloads/prologue-layout.json)"""
import sys, os, json
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repo root (worktree-aware)
sys.path.insert(0, os.path.join(ROOT,'tools'))
from map_tileset_tool import _tileset_from_dir, compile_layout
from PIL import Image

if len(sys.argv)<2:
    sys.exit('usage: import_map_layout.py <map-stem> [src-json]')
stem=sys.argv[1]
if len(sys.argv)>2:
    src=os.path.expanduser(sys.argv[2])
else:
    cands=[os.path.expanduser(f'~/Downloads/{stem}-layout.json'),
           os.path.expanduser('~/Downloads/ch01-layout.json') if stem.startswith('ch01') else None,
           os.path.expanduser('~/Downloads/prologue-layout.json')]
    src=next((c for c in cands if c and os.path.exists(c)), None)
    if not src: sys.exit('no exported layout JSON found in ~/Downloads')
d=json.load(open(src))
W,H,flat=d['width'],d['height'],d['grid']
assert len(flat)==W*H, 'grid size mismatch'
grid=[flat[r*W:(r+1)*W] for r in range(H)]

mapdir=os.path.join(ROOT,'campaigns/rime-of-the-frostmaiden/maps')
out_bin=os.path.join(mapdir,f'{stem}.mar')
compile_layout(grid, out_bin, stem)
json.dump({'id': stem, 'width': W, 'height': H}, open(os.path.join(mapdir,f'{stem}.json'),'w'))
print('compiled', out_bin, f'({W}x{H})')

win=_tileset_from_dir(os.path.join(mapdir,'tilesets/snowy-bern'))
Z=4*16
img=Image.new('RGB',(W*Z,H*Z))
for i,m in enumerate(flat):
    img.paste(win.metatile_image(m).resize((Z,Z),Image.NEAREST),((i%W)*Z,(i//W)*Z))
prev=os.path.join(ROOT,f'map-review/{stem}-painted.png')
img.save(prev)
print('rendered preview', prev, '; imported from', src)
