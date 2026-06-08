#!/usr/bin/env python3
"""Import the editor's exported layout JSON -> compile to the decomp .mar/.json and
render a confirmation preview. Default input: ~/Downloads/prologue-layout.json."""
import sys, os, json
ROOT='/Users/Yonick/Projects/manchego-stars'
sys.path.insert(0, os.path.join(ROOT,'tools'))
from map_tileset_tool import _tileset_from_dir, compile_layout
from PIL import Image

src=sys.argv[1] if len(sys.argv)>1 else os.path.expanduser('~/Downloads/prologue-layout.json')
d=json.load(open(src))
W,H,flat=d['width'],d['height'],d['grid']
assert len(flat)==W*H, 'grid size mismatch'
grid=[flat[r*W:(r+1)*W] for r in range(H)]

out_bin=os.path.join(ROOT,'campaigns/rime-of-the-frostmaiden/maps/ch00-prologue.mar')
compile_layout(grid, out_bin, 'ch00-prologue')
print('compiled', out_bin)

win=_tileset_from_dir(os.path.join(ROOT,'campaigns/rime-of-the-frostmaiden/maps/tilesets/snowy-bern'))
Z=4*16
img=Image.new('RGB',(W*Z,H*Z))
for i,m in enumerate(flat):
    img.paste(win.metatile_image(m).resize((Z,Z),Image.NEAREST),((i%W)*Z,(i//W)*Z))
img.save(os.path.join(ROOT,'map-review/prologue-winter-reskin-clean.png'))
print('rendered preview; imported from', src)
