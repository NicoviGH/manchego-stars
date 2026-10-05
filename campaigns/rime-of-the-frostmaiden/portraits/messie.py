#!/usr/bin/env python3
"""Regenerate Messie's two busts from Nicolas's 2D pixel-art ref.

  python3 campaigns/rime-of-the-frostmaiden/portraits/messie.py

  messie.png        -- ch06, no hat (he is given the hat at the end of ch07)
  messie-mayor.png  -- ch07 on, the mayor in his top hat

The ref (References/NPCs/Messie/2DMessieMayor.jpeg, Nicolas's pick of three on 2026-10-05) is
pixel art saved as a 2048px JPEG: a 49x49 grid of 41px cells. Every step runs on that NATIVE
grid, sampled at cell centres, so JPEG noise never reaches the bust:

  * retint -- the ref is blue; his map sprite (map_sprites/messie-mayor.png, painted by Nicolas)
    is cast-palette SLATE. The art's mid skin blue lands exactly on the sprite's slate (cast idx
    10) and its pale belly on the cast light grey (idx 11), each at the art's own brightness, so
    the ramp survives. Gold goggles, black outline/hat and white eyes are not blue and stay.
  * no-hat -- the hat's cells are erased to background, and any erased cell touching exposed
    skin or goggle is re-inked as outline. Nothing is repainted (Nicolas: "just crop it out").
  * bust -- ref_to_bust at ONE crop for both, the largest that leaves FE8's dead corners empty
    with the hat on (0 clipped px, portrait_tool.clipped_mask), flipped to face screen-left and
    matted black so the white background cannot halo the outline. Same crop = same scale: in
    ch07 he puts a hat on, he does not change size.
"""
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'tools'))
import portrait_tool  # noqa: E402
import ref_to_bust  # noqa: E402

REF = os.path.join(REPO, 'references', 'References', 'NPCs', 'Messie', '2DMessieMayor.jpeg')
CELL, ORIGIN = 41, -1                      # the art's pixel size and grid offset in the JPEG
CROP = (656, -29, 2146, 1212)              # in upscaled-native pixels (JPEG crop + 1)
MATTE = (0x16, 0x13, 0x1f)                 # cast outline (idx 1)
SKIN, BELLY = (0x5f, 0x6f, 0x90), (0xb4, 0xb8, 0xbe)   # cast idx 10 / 11, his map sprite
SKIN_FROM, BELLY_FROM = (0x33, 0x94, 0xea), (0xd4, 0xec, 0xf1)   # the ref's own anchors
HAT_ROWS = 8                               # rows 0..8 are hat entirely
HAT_BRIM = (9, 13, 28)                     # rows 9..13, columns <= 28: the brim behind the head


def native(path=REF):
    src = Image.open(path).convert('RGB')
    n = (src.width - ORIGIN) // CELL
    out = Image.new('RGB', (n, n), (255, 255, 255))
    for j in range(n):
        for i in range(n):
            x, y = ORIGIN + i * CELL + CELL // 2, ORIGIN + j * CELL + CELL // 2
            if 0 <= x < src.width and 0 <= y < src.height:
                out.putpixel((i, j), src.getpixel((x, y)))
    return out


def _lum(a):
    return 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]


def retint(img):
    a = np.asarray(img).astype(np.float32) / 255
    r, b = a[..., 0], a[..., 2]
    mx, mn = a.max(2), a.min(2)
    sat = (mx - mn) / np.maximum(mx, 1e-6)
    blue = (b >= r + 0.03) & (sat > 0.05)
    L = _lum(a)
    f = lambda c: np.array(c, np.float32) / 255
    ls, lb = _lum(f(SKIN_FROM)), _lum(f(BELLY_FROM))
    w = np.clip((L - 0.62) / 0.2, 0, 1)[..., None]          # 0 = skin ramp, 1 = belly ramp
    new = np.clip(f(SKIN) * (L / ls)[..., None] * (1 - w) + f(BELLY) * (L / lb)[..., None] * w, 0, 1)
    a[blue] = new[blue]
    return Image.fromarray((a * 255).round().astype('uint8'))


def _is_bg(c):
    return min(c) > 230


def remove_hat(img):
    img = img.copy()
    dark = lambda c: sum(c) < 3 * 90
    hat = set()
    for j in range(HAT_BRIM[1] + 1):
        for i in range(img.width):
            c = img.getpixel((i, j))
            if _is_bg(c):
                continue
            if j <= HAT_ROWS or (HAT_BRIM[0] <= j and i <= HAT_BRIM[2] and dark(c)):
                hat.add((i, j))
    ink = {p for p in hat
           if any(q not in hat and not _is_bg(img.getpixel(q)) and not dark(img.getpixel(q))
                  for q in ((p[0] + 1, p[1]), (p[0] - 1, p[1]), (p[0], p[1] + 1), (p[0], p[1] - 1)))}
    for p in hat:
        img.putpixel(p, (0, 0, 0) if p in ink else (255, 255, 255))
    return img


def bust(grid):
    big = grid.resize((grid.width * CELL, grid.height * CELL), Image.NEAREST)
    tmp = os.path.join(HERE, '.messie-ref.png')
    big.save(tmp)
    try:
        out = ref_to_bust.convert(tmp, CROP, matte=MATTE).transpose(Image.FLIP_LEFT_RIGHT)
    finally:
        os.unlink(tmp)
    clipped = sum(portrait_tool.clipped_mask(out))
    if clipped:
        sys.exit('messie: %d px fall in FE8\'s dead corners -- re-fit CROP' % clipped)
    return out


def main():
    grey = retint(native())
    for name, grid in (('messie-mayor', grey), ('messie', remove_hat(grey))):
        path = os.path.join(HERE, name + '.png')
        bust(grid).save(path)
        print('wrote', os.path.relpath(path, REPO))


if __name__ == '__main__':
    main()
