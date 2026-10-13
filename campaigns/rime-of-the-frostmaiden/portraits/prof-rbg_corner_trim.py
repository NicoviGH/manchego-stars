#!/usr/bin/env python3
"""Prof RBG post-pipeline hand pass: clear a stray nub at the lower-left corner.

Reproduce the shipped bust from the ref (render params live in pcs/prof-rbg.yaml's
`art.render:` block):

  python3 tools/ref_to_bust.py "<References>/PCs/RBG3:4_Flat.png" /tmp/rbg.png \
      --crop 60,40,2240,1856 --zoom 0.88 --flip-h --matte 190f17
  python3 campaigns/rime-of-the-frostmaiden/portraits/prof-rbg_corner_trim.py /tmp/rbg.png \
      campaigns/rime-of-the-frostmaiden/portraits/prof-rbg.png

The ref's edge leaves a 2x2 green/pale speck hanging off the coat outline at x 8-9,
y 76-77 (Nicolas, 2026-10-13). It touches the outline, so ref_to_bust's stray-blob
cleanup keeps it; this erases it to transparent.
"""
import sys

import numpy as np
from PIL import Image

im = Image.open(sys.argv[1])
a = np.asarray(im).copy()
a[76:78, 8:10] = 0
out = Image.fromarray(a, 'P')
out.putpalette(im.getpalette())
out.save(sys.argv[2])
