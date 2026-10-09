#!/usr/bin/env python3
"""Regenerate Messie's two busts from Nicolas's refs.

  python3 campaigns/rime-of-the-frostmaiden/portraits/messie.py

  messie.png        -- ch06, no hat (he is given the hat at the end of ch07)
  messie-mayor.png  -- ch07 on, the mayor in his top hat

THE CH06 BUST comes from References/NPCs/Messie/MessieLongThick.jpeg (Gemini, Nicolas's pick on
2026-10-09): flat cel art, long thick neck, wearing the top hat he has not been given yet.

  * no-hat -- the hat is flood-filled from three seeds on it (stopping at his blue and at the
    background), and the top of his head is redrawn as a cubic curve from his own left outline
    to the top of his snout, in his own blue and outline. Hat pixels inside the curve become
    head, outside it background, and the band the brim shadowed is repainted, the eye spared.
  * bust -- the head centred and as HIGH as the frame allows ("raise him as high as possible"),
    the neck running off the bottom: the largest framing that leaves FE8's dead corners empty
    (portrait_tool.clipped_mask). Downscaled with ref_to_bust's cel mode, flipped to face
    screen-left.
  * retint -- AFTER the downscale, on the finished palette: his blues onto his map sprite's
    slate (cast idx 10) and his belly onto the cast light grey (idx 11), each at its own
    brightness. Done to the source instead, the darker slates come close enough to the teal
    background that the keyer eats them.

THE CH07 MAYOR BUST still comes from the earlier pixel-art ref (2DMessieMayor.jpeg) on the
native-grid path below; it moves to the new ref when ch07's scenes are written.
"""
import os
import sys
from collections import deque

import numpy as np
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'tools'))
import portrait_tool  # noqa: E402
import ref_to_bust  # noqa: E402

REFS = os.path.join(REPO, 'references', 'References', 'NPCs', 'Messie')
MATTE = (0x16, 0x13, 0x1f)                 # cast outline (idx 1)
SKIN, BELLY = (0x5f, 0x6f, 0x90), (0xb4, 0xb8, 0xbe)   # cast idx 10 / 11, his map sprite

# ── ch06: the hatless bust ───────────────────────────────────────────────────────────────
REF_CH06 = os.path.join(REFS, 'MessieLongThick.jpeg')
CH06_BG = (55, 95, 87)                     # the ref's flat backdrop
CH06_HEAD = (63, 117, 226)                 # his mid blue
CH06_BELLY = (213, 212, 226)               # his belly
CH06_INK = (32, 34, 49)                    # his outline
HAT_SEEDS = ((1150, 300), (1250, 300), (1400, 300))
HAT_FLOOR = 640                            # the hat never reaches below this row
# The new crown: from his left outline, over where the brim sat, onto the top of his snout.
CROWN = ((1058, 600), (1045, 360), (1330, 290), (1512, 424))
CROWN_INK_W = 16
BRIM_SHADOW = 110                          # rows under the crown the brim had darkened
EYE = (1246, 430, 1314, 526)               # never repainted
CH06_CROP = (795, 280, 2035, 1313)         # head centred, crown at the top edge (1.2 aspect)


def _bezier(p0, p1, p2, p3, n=80):
    p0, p1, p2, p3 = (np.array(p, float) for p in (p0, p1, p2, p3))
    return [tuple((1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t * t * p2
                  + t ** 3 * p3) for t in np.linspace(0, 1, n)]


def remove_hat_ch06(img):
    a = np.asarray(img.convert('RGB')).astype(int)
    H, W = a.shape[:2]
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    blue = (b > 150) & (b > r + 70)
    bg = np.all(np.abs(a - np.array(CH06_BG)) < 22, axis=2)
    hat = np.zeros((H, W), bool)
    todo = deque(HAT_SEEDS)
    for x, y in HAT_SEEDS:
        hat[y, x] = True
    while todo:
        x, y = todo.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if (0 <= nx < W and 0 <= ny < HAT_FLOOR and not hat[ny, nx]
                    and not blue[ny, nx] and not bg[ny, nx]):
                hat[ny, nx] = True
                todo.append((nx, ny))
    curve = _bezier(*CROWN)
    poly = Image.new('L', (W, H), 0)
    ImageDraw.Draw(poly).polygon(curve + [(CROWN[3][0], HAT_FLOOR + 60),
                                          (CROWN[0][0], HAT_FLOOR + 60)], fill=1)
    inside = np.asarray(poly).astype(bool)
    out = a.copy()
    out[hat & inside] = CH06_HEAD
    out[hat & ~inside] = CH06_BG
    yy, xx = np.mgrid[0:H, 0:W]
    crown_y = np.interp(np.arange(W), [c[0] for c in curve], [c[1] for c in curve])
    band = (inside & (yy < crown_y[None, :] + BRIM_SHADOW)
            & (xx >= CROWN[0][0] + CROWN_INK_W) & (xx <= CROWN[3][0]))
    x0, y0, x1, y1 = EYE
    band &= ~((xx >= x0) & (xx <= x1) & (yy >= y0) & (yy <= y1))
    out[band & ((a.sum(2) < sum(CH06_HEAD) - 40) | ~blue)] = CH06_HEAD
    res = Image.fromarray(out.astype('uint8'))
    ImageDraw.Draw(res).line(curve, fill=CH06_INK, width=CROWN_INK_W, joint='curve')
    return res


def _his_blues(a):
    """His blue family on the finished palette; not the near-black ink, which is blue-ish too."""
    lum = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    return _blue(a) & (lum > 0.15)


def retint_palette(bust):
    pal = bust.getpalette()[:48]
    swatch = Image.new('RGB', (16, 1))
    swatch.putdata([tuple(pal[i * 3:i * 3 + 3]) for i in range(16)])
    swatch = ref_to_bust.retint_ramp(swatch, (CH06_HEAD, SKIN), (CH06_BELLY, BELLY), _his_blues)
    new = [c for px in swatch.getdata() for c in px]
    new[0:3] = pal[0:3]                    # index 0 stays the transparent key
    out = bust.copy()
    out.putpalette(new + [0] * (768 - len(new)))
    return out


def bust_ch06():
    tmp = os.path.join(HERE, '.messie-nohat.png')
    remove_hat_ch06(Image.open(REF_CH06)).save(tmp)
    try:
        out = ref_to_bust.convert(tmp, CH06_CROP, matte=MATTE, cel=True)
    finally:
        os.unlink(tmp)
    out = retint_palette(out.transpose(Image.FLIP_LEFT_RIGHT))
    clipped = sum(portrait_tool.clipped_mask(out))
    if clipped:
        sys.exit('messie: %d px fall in FE8\'s dead corners -- re-fit CH06_CROP' % clipped)
    return out


# ── ch07: the mayor, from the earlier pixel-art ref ────────────────────────────────────────
# Pixel art saved as a 2048px JPEG: a 49x49 grid of 41px cells, sampled at cell centres so JPEG
# noise never reaches the bust; blue retinted to slate on the native grid.
REF_MAYOR = os.path.join(REFS, '2DMessieMayor.jpeg')
CELL, ORIGIN = 41, -1                      # the art's pixel size and grid offset in the JPEG
MAYOR_CROP = (656, -29, 2146, 1212)        # in upscaled-native pixels (JPEG crop + 1)
SKIN_FROM, BELLY_FROM = (0x33, 0x94, 0xea), (0xd4, 0xec, 0xf1)   # the ref's own anchors


def _blue(a):
    r, b = a[..., 0], a[..., 2]
    mx, mn = a.max(2), a.min(2)
    return (b >= r + 0.03) & ((mx - mn) / np.maximum(mx, 1e-6) > 0.05)


def bust_mayor():
    grid = ref_to_bust.sample_pixel_grid(Image.open(REF_MAYOR), CELL, ORIGIN)
    grid = ref_to_bust.retint_ramp(grid, (SKIN_FROM, SKIN), (BELLY_FROM, BELLY), _blue,
                                   blend=(0.62, 0.82))
    big = grid.resize((grid.width * CELL, grid.height * CELL), Image.NEAREST)
    tmp = os.path.join(HERE, '.messie-ref.png')
    big.save(tmp)
    try:
        out = ref_to_bust.convert(tmp, MAYOR_CROP, matte=MATTE).transpose(Image.FLIP_LEFT_RIGHT)
    finally:
        os.unlink(tmp)
    clipped = sum(portrait_tool.clipped_mask(out))
    if clipped:
        sys.exit('messie-mayor: %d px fall in FE8\'s dead corners -- re-fit MAYOR_CROP' % clipped)
    return out


def main():
    for name, build in (('messie', bust_ch06), ('messie-mayor', bust_mayor)):
        path = os.path.join(HERE, name + '.png')
        build().save(path)
        print('wrote', os.path.relpath(path, REPO))


if __name__ == '__main__':
    main()
