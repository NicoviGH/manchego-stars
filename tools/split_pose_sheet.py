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
POSE_SHARE = 0.1               # a blob >= this share of the biggest one IS another pose


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


def _blobs(mask):
    """[(label, x0, y0, x1, y1, area)] -- the 8-connected blobs of `mask`, biggest first.

    Scanline union-find over row RUNS rather than pixels: a sheet is a couple of million
    pixels and only a few thousand runs, and two runs belong together exactly when they
    touch on adjacent rows (diagonals included, so a one-pixel stair does not sever a leg).
    Also returns `labels`, the per-pixel root, which `_cascade` measures distances against."""
    h, w = mask.shape
    parent = []

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    rows, prev = [], []
    for y in range(h):
        row = mask[y]
        edges = np.flatnonzero(np.diff(np.concatenate(([0], row.view(np.int8), [0]))))
        cur = []
        for x0, x1 in zip(edges[::2], edges[1::2]):
            label = len(parent)
            parent.append(label)
            for px0, px1, plabel in prev:
                if px0 <= x1 and x0 <= px1:        # touching, corners included
                    union(label, plabel)
            cur.append((int(x0), int(x1), label))
        rows.append((y, cur))
        prev = cur

    labels = np.zeros((h, w), np.int32) - 1
    found = {}
    for y, cur in rows:
        for x0, x1, label in cur:
            root = find(label)
            labels[y, x0:x1] = root
            b = found.get(root)
            if b is None:
                found[root] = [x0, y, x1, y + 1, x1 - x0]
            else:
                b[0] = min(b[0], x0); b[2] = max(b[2], x1)
                b[3] = y + 1; b[4] += x1 - x0
    blobs = [(root, b[0], b[1], b[2], b[3], b[4]) for root, b in found.items()]
    blobs.sort(key=lambda b: -b[5])
    return blobs, labels


def _cascade(mask, gap=GAP, pose_share=POSE_SHARE):
    """The pose boxes inside ONE gutter cell, left to right by leading edge.

    A generated sheet may CASCADE its poses diagonally -- overlapping their bounding boxes
    on both axes with no transparent column or row anywhere between them (Baxby's, #206).
    The gutter split cannot see that, but connectivity can: the poses never share ink.

    Connectivity alone over-splits, though, because plenty of ONE pose's parts are separate
    blobs -- a raised paw across an empty column, the ground shadow under the feet. Two
    rules keep them whole, and between them they say what a pose IS:
      * a blob under `pose_share` of the biggest is that pose's own DETACHED art (an impact
        spark's outer rays, a motion streak): merged into the nearest pose by real ink
        distance, never dropped, because it is drawn art the frame needs;
      * two pose-sized blobs that are merely NEAR each other (`gap`, the same promise the
        gutter split makes) are one pose. Only blobs that OVERLAP -- which no two parts of
        one drawing do, and which is exactly what a cascade produces -- stay separate.
    One pose in, one box out, equal to the cell's own bbox: a gutter-separated sheet is
    unaffected."""
    blobs, labels = _blobs(mask)
    if not blobs:
        return []
    cutoff = blobs[0][5] * pose_share
    big = [b for b in blobs if b[5] >= cutoff]
    small = blobs[len(big):]
    poses = [{'roots': [b[0]], 'box': [b[1], b[2], b[3], b[4]]} for b in big]

    def _absorb(p, box):
        p['box'] = [min(p['box'][0], box[0]), min(p['box'][1], box[1]),
                    max(p['box'][2], box[2]), max(p['box'][3], box[3])]

    merging = True
    while merging and len(poses) > 1:
        merging = False
        for i, a in enumerate(poses):
            for j, b in list(enumerate(poses))[i + 1:]:
                dx = max(0, max(a['box'][0], b['box'][0]) - min(a['box'][2], b['box'][2]))
                dy = max(0, max(a['box'][1], b['box'][1]) - min(a['box'][3], b['box'][3]))
                if (dx or dy) and dx < gap and dy < gap:
                    _absorb(a, b['box'])
                    a['roots'] += b['roots']
                    poses.pop(j)
                    merging = True
                    break
            if merging:
                break

    ink = [np.nonzero(np.isin(labels, p['roots'])) for p in poses]
    for root, x0, y0, x1, y1, _area in small:
        cx, cy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        best = min(range(len(poses)),
                   key=lambda k: np.min((ink[k][1] - cx) ** 2 + (ink[k][0] - cy) ** 2))
        _absorb(poses[best], (x0, y0, x1, y1))
        poses[best]['roots'].append(root)
    poses.sort(key=lambda p: p['box'][0])
    return [(tuple(p['box']), np.isin(labels, p['roots'])) for p in poses]


def pose_masks(im, gap=GAP, min_area=MIN_AREA):
    """[(box, ink)] per pose in READING order -- its alpha bbox (PIL-exclusive) and a mask,
    box-sized, of the pixels that are ITS OWN.

    Rows first, then columns within a row -- a sheet may lay its poses out as a grid rather
    than a strip, and the names it is split with follow the reading order. A single-row sheet
    yields one band, so a strip behaves exactly as it did before grids were handled. Within
    a cell, poses that OVERLAP (a diagonal cascade, no gutter to find) are split on ink
    connectivity -- see `_cascade`. The mask is what makes an overlap survivable: cascaded
    boxes intersect, so a pose's box holds a slice of the NEXT pose's art, and cropping the
    box alone would tow a neighbour's feathers into the frame."""
    a = np.array(im.convert("RGBA").getchannel("A"))
    drawn = a > ALPHA_ON
    out = []
    for y0, y1 in _runs(drawn.any(axis=1), gap):
        strip = drawn[y0:y1, :]
        for x0, x1 in _runs(strip.any(axis=0), gap):
            cell = strip[:, x0:x1]
            if cell.sum() < min_area:
                continue                   # a speck the generator left between poses
            for (bx0, by0, bx1, by1), own in _cascade(cell, gap):
                out.append(((x0 + bx0, y0 + by0, x0 + bx1, y0 + by1),
                            own[by0:by1, bx0:bx1]))
    return out


def pose_boxes(im, gap=GAP, min_area=MIN_AREA):
    """The alpha bbox of each pose, in READING order (see `pose_masks`)."""
    return [box for box, _ink in pose_masks(im, gap, min_area)]


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
    found = pose_masks(im, gap=gap, min_area=min_area)
    if len(found) != len(names):
        raise ValueError("sheet holds %d poses but %d name(s) were given: %s"
                         % (len(found), len(names), ", ".join(names)))
    out = []
    for name, (b, ink) in zip(names, found):
        cell = np.array(im.convert("RGBA").crop(b))
        # Drop a cascaded NEIGHBOUR's overlapping art -- only ink that is another pose's.
        # Pixels below ALPHA_ON belong to no pose and are left exactly as they lie, so a
        # gutter-separated sheet still splits byte-identically to before cascades existed.
        cell[(cell[:, :, 3] > ALPHA_ON) & ~ink] = (0, 0, 0, 0)
        pose = key_shadow(Image.fromarray(cell), shadow, feather=feather)
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
