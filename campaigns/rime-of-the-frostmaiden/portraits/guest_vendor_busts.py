#!/usr/bin/env python3
"""Regenerate the guest vendor busts from the vendored FE-Repo sheets.

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
* dorbulgruf <- vendor/Fargus (FE8 Colours) {Eldritch Abomination} [F2E].png
    - 96x80 main-mug crop
    - royal-purple coat -> muted plum (Nicolas's pick of four, 2026-10-08). Speaker
      Dorbulgruf Shalescar of Bremen, an old shield-dwarf: the grey beard is what
      reads as a dwarf at bust size. Hires the party in ch06, ch07's boss.
* nerra <- vendor/Serra (Goth) {Freefall}.png
    - 96x80 main-mug crop
    - repainted in the merfolk's own battle-anim palette (vendored mermaid, `dark/Magic_000`):
      rust hair, pale green skin, gold eyes, and the top in the pink of the band they wear at
      the waist (Nicolas's pick, 2026-10-10: twin tails, as the merfolk wear them). Hair and
      top share the sheet's three greys, so the recolour is by REGION: the top is the rows from
      65 between the pigtails, and the face shading that borrows the hair greys goes to skin.
      Eight skin tones fold into the anim's five, which keeps the bust at 16 colours. Freefall's
      mugs are F2U and F2E with credit (FEUniverse t/19163, post 1).

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

DORBULGRUF_RECOLOR = {
    # royal-purple coat -> muted plum; the purple-black outline is kept
    (132, 82, 173): (122, 98, 140),
    (99, 41, 148):  (88, 64, 108),
}

NERRA_SKIN = {
    (246, 246, 223): (232, 244, 184), (247, 216, 160): (208, 232, 152),
    (246, 199, 137): (208, 232, 152), (231, 168, 96): (176, 192, 112),
    (226, 139, 81): (176, 192, 112), (199, 120, 56): (120, 168, 104),
    (156, 112, 73): (88, 128, 80), (112, 87, 86): (88, 128, 80),
}
NERRA_HAIR = {(79, 77, 80): (192, 112, 16), (73, 73, 73): (136, 64, 8), (66, 65, 66): (96, 24, 0)}
NERRA_TOP = {(79, 77, 80): (240, 176, 184), (73, 73, 73): (208, 128, 144),
             (66, 65, 66): (160, 80, 104)}
NERRA_LACE = (88, 80, 135)          # the top's mesh highlights; elsewhere the eye/clasp purple
NERRA_EYE_LIGHT = {(144, 168, 192): (232, 200, 80)}
NERRA_OUTLINE = (56, 32, 63)


def nerra_recolor(mug):
    """Serra (Goth) -> Nerra, by region (see the module docstring)."""
    out = mug.copy()
    for y in range(80):
        for x in range(96):
            c = tuple(int(v) for v in mug[y, x])
            top = y >= 65 and 30 <= x <= 65
            if c in NERRA_SKIN:
                new = NERRA_SKIN[c]
            elif c in NERRA_HAIR:
                new = (NERRA_TOP[c] if top
                       else (88, 128, 80) if 46 <= y < 65 and 34 <= x <= 62   # face shading
                       else NERRA_HAIR[c])
            elif c == NERRA_LACE:
                new = (240, 176, 184) if top else (160, 104, 8)
            elif c in NERRA_EYE_LIGHT:
                new = NERRA_EYE_LIGHT[c]
            elif c == NERRA_OUTLINE and 66 <= y <= 71 and 31 <= x <= 58:
                new = (160, 80, 104)                                       # the dark lace
            else:
                continue
            out[y, x] = new
    return out


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

    sheet = Image.open(os.path.join(
        VENDOR, 'Fargus (FE8 Colours) {Eldritch Abomination} [F2E].png')).convert('RGB')
    mug = np.array(sheet.crop((0, 0, 96, 80)))
    for src, dst in DORBULGRUF_RECOLOR.items():
        mug[(mug == src).all(axis=-1)] = dst
    out = os.path.join(HERE, 'dorbulgruf.png')
    to_indexed(Image.fromarray(mug), (160, 200, 152)).save(out)
    print('-> %s' % out)

    sheet = Image.open(os.path.join(VENDOR, 'Serra (Goth) {Freefall}.png')).convert('RGB')
    mug = np.array(sheet.crop((0, 0, 96, 80)))
    bg = tuple(int(v) for v in mug[0, 0])
    out = os.path.join(HERE, 'nerra.png')
    to_indexed(Image.fromarray(nerra_recolor(mug)), bg).save(out)
    print('-> %s' % out)


if __name__ == '__main__':
    main()
