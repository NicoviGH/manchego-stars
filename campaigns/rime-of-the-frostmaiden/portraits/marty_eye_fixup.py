#!/usr/bin/env python3
"""Marty's eyes are ~2px each -- below what the crisp downscale renders
consistently (one came out oval, one square). This deterministic touch-up clears
the messy eye-band pixels and stamps two identical rounded eyes (catchlight at
upper-left, matching the Marty 3 ref), symmetric about the mouth. Re-apply after
re-rendering marty.png with: ref_to_bust.py "Marty 3.png" marty.png
--crop 0,35,2222,1887 --downscale crisp.  (Mouth/scarf are already correct.)"""
import numpy as np
from PIL import Image
import sys
p = sys.argv[1] if len(sys.argv) > 1 else "marty.png"
im = Image.open(p); idx = np.asarray(im).copy()
FACE, DARK, SHINE = 1, 15, 13          # face flat / black / catchlight indices
for y in range(42, 47):                 # clear messy eye-band blacks (mouth is y47+)
    for x in range(40, 56):
        if idx[y, x] == DARK:
            idx[y, x] = FACE
def eye(cx, cy):                        # rounded eye, catchlight upper-left
    idx[cy, cx] = SHINE;     idx[cy, cx + 1] = DARK
    idx[cy + 1, cx] = DARK;  idx[cy + 1, cx + 1] = DARK
eye(43, 44); eye(52, 44)
out = Image.new('P', im.size); out.putpalette(im.getpalette()); out.putdata(idx.flatten().tolist())
out.save(p)
out.convert('RGB').resize((288, 240), Image.NEAREST).save(p.replace('.png', '_preview.png'))
print("applied Marty eye touch-up to", p)
