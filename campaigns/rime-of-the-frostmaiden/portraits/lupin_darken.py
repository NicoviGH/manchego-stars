#!/usr/bin/env python3
"""Lupin hand pass: deepen the near-blacks (outline, eyes, glasses frame).

The ref's line work is warm charcoal-brown; at 96x80 it reads muddy against FE8's
dark textbox. Darken by LUMINANCE, not palette index (pngquant's slot order isn't
contract): entries under lum 70 scale x0.35 (the outline/glasses/eyes ink), entries
under lum 90 scale x0.72 (the ink's anti-aliased shoulder), everything else is
untouched. Reproduce: python3 lupin_darken.py <in.png> <out.png>
"""
import sys
from PIL import Image

def darken(src, dst):
    im = Image.open(src)
    assert im.mode == 'P'
    pal = im.getpalette()
    for i in range(16):
        r, g, b = pal[i*3:i*3+3]
        if i == 0:                      # index 0 = transparent key, leave alone
            continue
        lum = 0.3*r + 0.6*g + 0.1*b
        if lum < 70:
            f = 0.35
        elif lum < 90:
            f = 0.72
        else:
            continue
        pal[i*3:i*3+3] = [int(v*f) for v in (r, g, b)]
    im.putpalette(pal)
    im.save(dst, optimize=False)
    print(f'{src} -> {dst} (near-blacks deepened)')

if __name__ == '__main__':
    darken(sys.argv[1], sys.argv[2])
