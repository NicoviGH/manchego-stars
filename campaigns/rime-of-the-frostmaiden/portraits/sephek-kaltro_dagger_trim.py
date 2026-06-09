#!/usr/bin/env python3
"""Sephek post-pipeline hand pass: dagger halo trim + dead-corner clear.

Reproduce the shipped bust from the ref (render params live in the chapter
YAML's sephek-kaltro `art.render:` block):

  python3 tools/ref_to_bust.py "<References>/NPCs/Sephak Bust Dagger.png" \
      /tmp/sephek-raw.png --crop 260,610,1280,1460 --zoom 0.94 --bg-thresh 25
  python3 campaigns/rime-of-the-frostmaiden/portraits/sephek-kaltro_dagger_trim.py \
      /tmp/sephek-raw.png campaigns/rime-of-the-frostmaiden/portraits/sephek-kaltro.png

Two passes, both pixel-count-tiny but look-bearing (Nicolas's notes, 2026-06-09):
  1. Zero every painted pixel FE8 never draws (the OAM dead corners), so the
     authored bust IS what ships and `portrait_tool.py preview` reads clean.
  2. Trim the ice dagger's pale glow halo: the ref's soft outer glow survives
     the downscale as a 1px white fringe. Halo pixels bordering transparency
     are erased; halo pixels bordering the dark vest are recolored to the mid
     blade tone, so the blade edge stays solid instead of ringed white.
     Restricted to the dagger region (x >= 50, y < 70 for the vest side) so the
     white shirt/collar keep their true edges.
"""
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'tools'))
import portrait_tool


def main(inp, outp):
    bust = Image.open(inp)
    portrait_tool._check_indexed(bust, inp)

    # pass 1: clear the OAM dead corners
    mask = portrait_tool.clipped_mask(bust)
    data = [0 if m else p for p, m in zip(bust.getdata(), mask)]
    bust.putdata(data)

    idx = np.array(bust)
    pal = bust.getpalette()
    rgb = np.array([pal[i * 3:i * 3 + 3] for i in range(16)])
    sums = rgb.sum(axis=1)
    is_light = (sums > 580)[idx] & (idx != 0)
    xx = np.arange(idx.shape[1])[None, :]
    yy = np.arange(idx.shape[0])[:, None]

    def neighbors(cond):
        nb = np.zeros_like(cond)
        nb[1:, :] |= cond[:-1, :]; nb[:-1, :] |= cond[1:, :]
        nb[:, 1:] |= cond[:, :-1]; nb[:, :-1] |= cond[:, 1:]
        return nb

    # pass 2a: halo vs background -> erase
    trim_bg = is_light & neighbors(idx == 0) & (xx >= 50)
    idx[trim_bg] = 0
    # pass 2b: halo vs dark vest -> mid blade tone
    is_light = (sums > 580)[idx] & (idx != 0)
    trim_dark = is_light & neighbors((sums < 200)[idx]) & (xx >= 50) & (yy < 70)
    mid = np.where((sums > 350) & (sums <= 580) & (rgb[:, 2] > rgb[:, 0]))[0][0]
    idx[trim_dark] = mid

    out = Image.fromarray(idx)
    out.putpalette(pal)
    out.save(outp)
    print('%s -> %s (dead-corner clear + %d/%d halo px)'
          % (inp, outp, int(trim_bg.sum()), int(trim_dark.sum())))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
