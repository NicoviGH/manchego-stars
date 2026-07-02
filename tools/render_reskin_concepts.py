#!/usr/bin/env python3
"""Render vanilla FE8 fields-tileset layouts through snowy-bern as winter-reskin
concept previews (map-review/). Divergent metatiles (terrain mismatch between the
two tilesets) are ironed out with the same neighbor/mode substitution the layout
editor uses, so the preview reads as a finished winter map, not a glitch sheet."""
import sys, os, struct, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEC = os.path.join(ROOT, 'fireemblem8u')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
from map_tileset_tool import _tileset_from_dir, Tileset
from PIL import Image

win = _tileset_from_dir(os.path.join(ROOT, 'campaigns/rime-of-the-frostmaiden/maps/tilesets/snowy-bern'))
van = Tileset(os.path.join(DEC, 'graphics/map/ObjectType1.4bpp'),
              os.path.join(DEC, 'graphics/map/MapPalette1.gbapal'),
              os.path.join(DEC, 'graphics/map/TileConfiguration1.bin'))

def divergent(m): return win.terrain(m) != van.terrain(m)

def resolve(cells, W, H):
    modec = collections.defaultdict(collections.Counter)
    for m in cells:
        if not divergent(m): modec[van.terrain(m)][m] += 1
    MODE = {t: c.most_common(1)[0][0] for t, c in modec.items()}
    FB = {0x01: 6, 0x0c: 192, 0x10: 568, 0x12: 418, 0x13: 2}
    out = [0]*(W*H)
    for y in range(H):
        for x in range(W):
            m = cells[y*W+x]
            if not divergent(m):
                out[y*W+x] = m; continue
            vt = van.terrain(m); nb = collections.Counter()
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    if dx == 0 and dy == 0: continue
                    nx, ny = x+dx, y+dy
                    if 0 <= nx < W and 0 <= ny < H:
                        nm = cells[ny*W+nx]
                        if not divergent(nm) and van.terrain(nm) == vt: nb[nm] += 1
            out[y*W+x] = nb.most_common(1)[0][0] if nb else MODE.get(vt, FB.get(vt, m))
    return out

def render(layout_name, out_png, zoom=4):
    lay = open(os.path.join(DEC, f'graphics/map/layout/{layout_name}.bin'), 'rb').read()
    W, H = lay[0], lay[1]
    cells = [struct.unpack_from('<H', lay, 2+i*2)[0]//4 for i in range(W*H)]
    cells = resolve(cells, W, H)
    Z = zoom*16
    img = Image.new('RGB', (W*Z, H*Z))
    for i, m in enumerate(cells):
        img.paste(win.metatile_image(m).resize((Z, Z), Image.NEAREST), ((i % W)*Z, (i//W)*Z))
    img.save(out_png)
    print(f'{layout_name}: {W}x{H} -> {out_png}')

if __name__ == '__main__':
    outdir = os.path.join(ROOT, 'map-review/21-iron-trail')
    os.makedirs(outdir, exist_ok=True)
    for name, slug in [('Ch1Map', 'a-vanilla-ch1-escape'),
                       ('Ch13EirikaMap', 'b-ch13-fluorspar-wide-trail'),
                       ('Ch2Map', 'c-ch2-the-protected')]:
        render(name, os.path.join(outdir, f'{slug}.png'))

def render_pair(layout_name, out_png, zoom=3):
    """Vanilla render (top) stacked over the winter reskin (bottom)."""
    lay = open(os.path.join(DEC, f'graphics/map/layout/{layout_name}.bin'), 'rb').read()
    W, H = lay[0], lay[1]
    cells = [struct.unpack_from('<H', lay, 2+i*2)[0]//4 for i in range(W*H)]
    Z = zoom*16
    GAP = 8
    img = Image.new('RGB', (W*Z, H*Z*2+GAP), (32, 32, 32))
    for i, m in enumerate(cells):
        img.paste(van.metatile_image(m).resize((Z, Z), Image.NEAREST), ((i % W)*Z, (i//W)*Z))
    for i, m in enumerate(resolve(cells, W, H)):
        img.paste(win.metatile_image(m).resize((Z, Z), Image.NEAREST), ((i % W)*Z, H*Z+GAP+(i//W)*Z))
    img.save(out_png)
    print(f'{layout_name}: {W}x{H} pair -> {out_png}')
