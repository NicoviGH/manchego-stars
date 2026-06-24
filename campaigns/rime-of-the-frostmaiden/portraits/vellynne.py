#!/usr/bin/env python3
"""Regenerate Vellynne Harpell's cutscene bust from the vendored FE-Repo Sonya mug.

  python3 campaigns/rime-of-the-frostmaiden/portraits/vellynne.py

Vellynne (recurring Arcane Brotherhood necromancer; the book describes her as
"aristocratic ... sharp features and snow white hair") is the FE2/15 **Sonya (Witch)**
mug -- {JeyTheCount}, FE8 colours, [F2E] -- with one mechanical recolor: Sonya's
magenta hair ramp -> snow-white / cool silver, the rest of the elegant-sorceress bust
kept as-is. Base + recolor picked by Nicolas 2026-06-24 (avoid the custom-art path; a
hair palette swap, the same minimal move as Duvessa <- Selena). She dresses FID_Ismaire
(a regal vanilla woman absent from our ch00-08 chapters -- collision-free).

Output: 96x80 indexed PNG, <=16 colors, index 0 = transparent bg -- the bust-pipeline
contract consumed by tools/build_campaign.py inject_portraits (GUEST_PORTRAIT_MAP).
"""
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(HERE, 'vendor')
SONYA = 'Sonya (Witch, FE8 colours) {JeyTheCount} [F2E].png'
SONYA_BG = (160, 200, 152)        # Sonya sheet background (palette index 0)

# Sonya's magenta hair ramp -> snow-white / cool silver. The two near-identical darkest
# purples both fold to one cool grey, which also trims the 96x80 crop from 17 colours to
# FE8's 16-colour ceiling. Skin / red robe / teal gem / gold trim untouched.
RECOLOR = {
    (188, 67, 153): (226, 227, 236),   # main hair -> near-white
    (132, 61, 109): (176, 181, 197),   # hair mid -> silver
    (91, 42, 75):   (120, 126, 145),   # hair deep shadow -> dark cool silver
    (57, 33, 66):   (78, 82, 100),     # darkest strand/outline -> cool grey
    (56, 32, 64):   (78, 82, 100),     # near-dup of the above (merge: 17 -> 16 colours)
}


def to_indexed(rgb_img, bg):
    """RGB 96x80 -> P-mode, index 0 = bg, <=16 colors (the bust-pipeline contract)."""
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
    sheet = Image.open(os.path.join(VENDOR, SONYA)).convert('RGB')
    mug = np.array(sheet.crop((0, 0, 96, 80)))
    for src, dst in RECOLOR.items():
        mug[(mug == src).all(axis=-1)] = dst
    out = os.path.join(HERE, 'vellynne.png')
    to_indexed(Image.fromarray(mug), SONYA_BG).save(out)
    print('-> %s' % out)


if __name__ == '__main__':
    main()
