#!/usr/bin/env python3
"""One generated pose sheet -> the per-pose PNGs the banim pipelines consume (#206).

The battle-anim reference art arrives as ONE wide image with every pose standing side by
side on a baked teal ground shadow. Both facts are wrong for FE8: the downstream tools
(`poses_to_feditor` for an arc, `descale_battleframe` for the faked 3-pose path) want one
alpha-cropped file per pose, and the battle screen draws its OWN platform -- a baked
ellipse would either double it or, on an airborne pose, tow a floating blob.

    python3 tools/split_pose_sheet.py SHEET.png OUT_DIR idle windup lunge hit

Two decisions worth keeping:
  * poses are split on the TRANSPARENT GUTTER between them, not a fixed grid -- generated
    sheets do not space their poses evenly, and a raised paw leaves empty columns INSIDE
    a pose that a naive column split would tear in half (hence `gap`).
  * the shadow is keyed by MORPHOLOGICAL RECONSTRUCTION, not a flat colour match: grow
    outward from tight-matching seed pixels through loosely-matching neighbours. Fur
    shading lands within ~40 of the teal in RGB, so a flat key at any tolerance wide
    enough to catch the ellipse's own gradient also eats the wolf; only the connected
    blob is the shadow.
"""
import os
import sys

import numpy as np
from PIL import Image

SHADOW_TEAL = (48, 108, 108)   # the generated sheets' baked ground ellipse
ALPHA_ON = 20                  # above this an alpha byte counts as drawn art
GAP = 30                       # empty columns that separate two POSES (fewer = one pose)
MIN_AREA = 64                  # a run smaller than this is a stray artifact, not a pose
SEED_TOL = 12                  # RGB distance that seeds the shadow (its flat interior)
SPREAD_TOL = 55                # ...and that the seed may grow through (its gradient/edge)
FEATHER = 2                    # rings dropped past the keyed blob (its washed AA fringe)


def _dilate(mask):
    out = mask.copy()
    out[1:, :] |= mask[:-1, :]
    out[:-1, :] |= mask[1:, :]
    out[:, 1:] |= mask[:, :-1]
    out[:, :-1] |= mask[:, 1:]
    return out


def _runs(occupied, gap):
    """Spans of True in `occupied`, merging any two closer together than `gap`."""
    runs, start = [], None
    for i, on in enumerate(occupied):
        if on and start is None:
            start = i
        elif not on and start is not None:
            runs.append([start, i])
            start = None
    if start is not None:
        runs.append([start, len(occupied)])
    merged = []
    for r in runs:
        if merged and r[0] - merged[-1][1] < gap:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    return merged


def pose_boxes(im, gap=GAP, min_area=MIN_AREA):
    """The alpha bbox of each pose, in READING order (PIL-exclusive coords).

    Rows first, then columns within a row -- a sheet may lay its poses out as a grid rather
    than a strip, and the names it is split with follow the reading order. A single-row sheet
    yields one band, so a strip behaves exactly as it did before grids were handled."""
    a = np.array(im.convert("RGBA").getchannel("A"))
    drawn = a > ALPHA_ON
    boxes = []
    for y0, y1 in _runs(drawn.any(axis=1), gap):
        strip = drawn[y0:y1, :]
        for x0, x1 in _runs(strip.any(axis=0), gap):
            cell = strip[:, x0:x1]
            if cell.sum() < min_area:
                continue                   # a speck the generator left between poses
            xs = np.where(cell.any(axis=0))[0]
            ys = np.where(cell.any(axis=1))[0]
            boxes.append((x0 + int(xs.min()), y0 + int(ys.min()),
                          x0 + int(xs.max()) + 1, y0 + int(ys.max()) + 1))
    return boxes


def key_shadow(im, colour=SHADOW_TEAL, seed_tol=SEED_TOL, spread_tol=SPREAD_TOL,
               feather=FEATHER):
    """A copy of `im` with the baked ground shadow keyed out (see the module docstring)."""
    im = im.convert("RGBA")
    a = np.array(im)
    rgb = a[:, :, :3].astype(float)
    dist = np.sqrt(((rgb - np.array(colour, dtype=float)) ** 2).sum(axis=2))
    opaque = a[:, :, 3] > ALPHA_ON
    shadow = (dist < seed_tol) & opaque
    loose = (dist < spread_tol) & opaque
    while True:
        grown = _dilate(shadow) & loose
        if grown.sum() == shadow.sum():
            break
        shadow = grown
    if shadow.any():
        for _ in range(feather):
            shadow = _dilate(shadow)
    a[shadow] = (0, 0, 0, 0)
    return Image.fromarray(a)


def split_sheet(im, names, shadow=SHADOW_TEAL, gap=GAP, min_area=MIN_AREA,
                feather=FEATHER):
    """[(name, pose)] -- one shadow-free, alpha-cropped RGBA image per name, left to right."""
    boxes = pose_boxes(im, gap=gap, min_area=min_area)
    if len(boxes) != len(names):
        raise ValueError("sheet holds %d poses but %d name(s) were given: %s"
                         % (len(boxes), len(names), ", ".join(names)))
    out = []
    for name, b in zip(names, boxes):
        pose = key_shadow(im.convert("RGBA").crop(b), shadow, feather=feather)
        bb = pose.getchannel("A").point(lambda v: 255 if v > ALPHA_ON else 0).getbbox()
        out.append((name, pose.crop(bb) if bb else pose))
    return out


def main():
    if len(sys.argv) < 4:
        sys.exit("usage: split_pose_sheet.py SHEET.png OUT_DIR name [name ...]")
    src, out_dir, names = sys.argv[1], sys.argv[2], sys.argv[3:]
    os.makedirs(out_dir, exist_ok=True)
    for i, (name, pose) in enumerate(split_sheet(Image.open(src), names)):
        path = os.path.join(out_dir, "%d_%s.png" % (i + 1, name))
        pose.save(path)
        print("  %-8s -> %s  %dx%d" % (name, path, pose.width, pose.height))


if __name__ == "__main__":
    main()
