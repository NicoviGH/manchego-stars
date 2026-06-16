#!/usr/bin/env python3
"""Regenerate the ch00 guest vendor busts from the vendored FE-Repo sheets.

  python3 campaigns/rime-of-the-frostmaiden/portraits/guest_vendor_busts.py

Both community mugs keep their original art; the transforms are mechanical:

* hlin-trollbane <- vendor/Pirate Lady (Version 3) {Cygnus} [F2E].png
    - 96x80 main-mug crop
    - merge 3 near-duplicate/speck colors (sheet has 18; FE8's ceiling is 16)
    - silver-hair age recolor (blonde ramp -> gray ramp): Hlin is "an elderly
      shield dwarf ... past her prime" (book p.22); look picked 2026-06-09
* scramsax <- vendor/Hero {LaurentLacroix, UltraFenix, monk-han}.png
    - 96x80 main-mug crop, used as-is
* hruna <- vendor/Generic Villager {Cynon} [F2E].png
    - 96x80 main-mug crop
    - periwinkle shirt -> olive wool cold-weather coat (Icewind Dale frost-dwarf
      quest-giver; book p.34 Foaming Mugs). Sympathetic "please help us" read
      picked over the canon scarf-wrapped look on 2026-06-16 (Nicolas's call for
      a one-chapter NPC); auburn hair reads as a dwarf. Cynon's mug is [F2E].

Output format is the bust-pipeline contract: 96x80 indexed PNG, <=16 colors,
index 0 = the transparent background.
"""
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(HERE, 'vendor')

HRUNA_RECOLOR = {
    # periwinkle shirt -> olive wool coat
    (112, 120, 192): (124, 144, 96),
    (80, 88, 144):   (88, 106, 66),
    (56, 64, 80):    (54, 68, 44),
    (40, 80, 104):   (54, 68, 44),   # merge teal accent into the deep coat shadow
}

HLIN_RECOLOR = {
    # merges (color budget 18 -> 16)
    (61, 38, 31): (58, 36, 37),
    (89, 56, 45): (58, 36, 37),
    (248, 248, 248): (248, 240, 216),
    # blonde -> silver (aging)
    (255, 238, 89): (214, 214, 218),
    (232, 216, 8): (196, 196, 202),
    (200, 176, 8): (156, 156, 164),
    (152, 120, 40): (104, 104, 114),
}


def to_indexed(rgb_img, bg):
    """RGB 96x80 -> P-mode, index 0 = bg, <=16 colors."""
    a = np.array(rgb_img)
    colors = sorted({tuple(int(v) for v in p) for p in a.reshape(-1, 3)})
    if len(colors) > 16:
        raise SystemExit('ERROR: %d colors (>16)' % len(colors))
    colors = [bg] + [c for c in colors if c != bg]
    idx = np.zeros(a.shape[:2], dtype=np.uint8)
    for i, c in enumerate(colors):
        idx[(a == c).all(axis=-1)] = i
    out = Image.fromarray(idx)
    out.putpalette(sum([list(c) for c in colors], []) + [0] * (48 - 3 * len(colors)))
    return out


def main():
    sheet = Image.open(os.path.join(
        VENDOR, 'Pirate Lady (Version 3) {Cygnus} [F2E].png')).convert('RGB')
    mug = np.array(sheet.crop((0, 0, 96, 80)))
    for src, dst in HLIN_RECOLOR.items():
        mug[(mug == src).all(axis=-1)] = dst
    out = os.path.join(HERE, 'hlin-trollbane.png')
    to_indexed(Image.fromarray(mug), (160, 200, 152)).save(out)
    print('-> %s' % out)

    sheet = Image.open(os.path.join(
        VENDOR, 'Hero {LaurentLacroix, UltraFenix, monk-han}.png')).convert('RGB')
    mug = sheet.crop((0, 0, 96, 80))
    bg = tuple(int(v) for v in np.array(mug)[0, 0])
    out = os.path.join(HERE, 'scramsax.png')
    to_indexed(mug, bg).save(out)
    print('-> %s' % out)

    sheet = Image.open(os.path.join(
        VENDOR, 'Generic Villager {Cynon} [F2E].png')).convert('RGB')
    mug = np.array(sheet.crop((0, 0, 96, 80)))
    for src, dst in HRUNA_RECOLOR.items():
        mug[(mug == src).all(axis=-1)] = dst
    out = os.path.join(HERE, 'hruna.png')
    to_indexed(Image.fromarray(mug), (160, 192, 144)).save(out)
    print('-> %s' % out)


if __name__ == '__main__':
    main()
