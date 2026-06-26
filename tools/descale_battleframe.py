#!/usr/bin/env python3
"""Hi-res battle poses -> FE8-scale banim source frames (#65 Milestone B).

The faked-anim injector (`inject_battle_anims`) consumes small transparent frames sharing
ONE <=15-colour palette and a COMMON feet anchor (so the body doesn't jump between beats).
The RBG set (Milestone A) was hand-prepared; this tool does it repeatably for every PC:

  flip (match RBG's left facing) -> alpha-crop -> ONE uniform downscale (Ready height ->
  ~FE infantry body) so poses keep a consistent size -> place each on a shared canvas at a
  common feet baseline + foot-centre -> crisp the alpha (BOX-descale haloes -> hard edge) ->
  snap all frames to one shared adaptive <=15-colour palette.

  python3 tools/descale_battleframe.py OUT_DIR ready=READY.png windup=WIND.png peak=PEAK.png

Writes OUT_DIR/{ready,windup,peak}.png. Frames the build reads via the unit's `battle_anim:`
`frames:` list. Tune --body / --noflip per unit; review the PNGs before wiring the YAML.
"""
import argparse
import colorsys
import os
from collections import Counter, defaultdict

from PIL import Image, ImageChops, ImageFilter

ALPHA_CUT = 128       # BOX-descale leaves a soft halo; below this -> fully transparent
MAX_COLOURS = 15      # + index 0 (transparent) = the 16-colour banim palette


def _alpha_bbox(im):
    return im.getchannel("A").point(lambda a: 255 if a >= ALPHA_CUT else 0).getbbox()


def _foot_centre_x(im, bbox):
    """Horizontal centre of the bottom 12% of the silhouette (the feet), in im coords."""
    x0, y0, x1, y1 = bbox
    band = max(1, (y1 - y0) * 12 // 100)
    a = im.getchannel("A")
    xs = [x for y in range(y1 - band, y1) for x in range(x0, x1)
          if a.getpixel((x, y)) >= ALPHA_CUT]
    return sum(xs) / len(xs) if xs else (x0 + x1) / 2


def _crisp(im):
    """Hard-threshold the alpha so descaled edges read like a drawn FE sprite."""
    a = im.getchannel("A").point(lambda v: 255 if v >= ALPHA_CUT else 0)
    im.putalpha(a)
    return im


def _opaque_pixels(frames):
    out = []
    for f in frames:
        a = f.getchannel("A")
        for (x, y), px in zip(((x, y) for y in range(f.height) for x in range(f.width)),
                              f.convert("RGB").getdata()):
            if a.getpixel((x, y)) >= ALPHA_CUT:
                out.append(px)
    return out


def _shared_palette(frames):
    """One <=MAX_COLOURS palette over every frame's opaque pixels, with a true outline
    black RESERVED as entry 0 so the silhouette edge snaps to a clean dark line (the
    adaptive-only palette dropped black, washing the outline out). Returns (pal_img, ink)."""
    px = _opaque_pixels(frames)
    ink = min(px, key=lambda c: c[0] * 0.299 + c[1] * 0.587 + c[2] * 0.114)  # darkest tone
    strip = Image.new("RGB", (sum(f.width for f in frames), max(f.height for f in frames)))
    x = 0
    for f in frames:
        strip.paste(f.convert("RGB"), (x, 0), f.getchannel("A").point(
            lambda v: 255 if v >= ALPHA_CUT else 0))
        x += f.width
    adaptive = strip.quantize(colors=MAX_COLOURS - 1, method=Image.MEDIANCUT)
    cols = [ink]
    for i in range(0, len(adaptive.getpalette()), 3):
        c = tuple(adaptive.getpalette()[i:i + 3])
        if c not in cols and len(cols) <= MAX_COLOURS:
            cols.append(c)
    pal = Image.new("P", (1, 1))
    flat = [v for c in cols for v in c]
    pal.putpalette(flat + [0] * (768 - len(flat)))
    return pal, ink


def _dilate4(a):
    """1px 4-connected dilation (no diagonal corners) -> a thinner outline than MaxFilter."""
    out = a.copy()
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        sh = Image.new("L", a.size, 0)
        sh.paste(a, (dx, dy))
        out = ImageChops.lighter(out, sh)
    return out


FLAT_SPEC = (("red", 2), ("orange", 2), ("grey", 2), ("brown", 2))  # + black + white = 10


def _family(rgb):
    """Bucket an RGB into a hue family (HSV thresholds tuned for a warm crab palette)."""
    h, s, v = colorsys.rgb_to_hsv(*[c / 255 for c in rgb])
    H = h * 360
    if v < 0.20:
        return "black"
    if s < 0.16 and v > 0.82:
        return "white"
    if s < 0.18:
        return "grey"
    if H <= 16 or H >= 343:
        return "red"
    if H <= 50:
        return "orange" if s >= 0.50 else "brown"   # saturated = orange, muted = tan/brown
    return "brown"                                    # yellow-tan tail


def _lum(c):
    return c[0] * 0.299 + c[1] * 0.587 + c[2] * 0.114


def _centroid(group):
    t = sum(c for _, c in group)
    return tuple(round(sum(p[i] * c for p, c in group) / t) for i in range(3))


def _split_shades(px, n):
    """Population-split a family's pixels by luminance into n shade clusters -> centroids."""
    px = sorted(px, key=lambda pc: _lum(pc[0]))
    target = sum(c for _, c in px) / n
    groups, gi, acc = [[] for _ in range(n)], 0, 0
    for pc in px:
        groups[gi].append(pc)
        acc += pc[1]
        if acc >= target and gi < n - 1:
            gi, acc = gi + 1, 0
    return [_centroid(g) for g in groups if g]


def _flat_palette(frames, spec=FLAT_SPEC):
    """A curated 'family' palette: ~2 deliberate shades per hue + black + white, instead of
    the busy adaptive median-cut. Flattens the AI gradient shading into clean cel bands.
    Returns (pal_img, ink)."""
    fam = defaultdict(list)
    for rgb, c in Counter(_opaque_pixels(frames)).items():
        fam[_family(rgb)].append((rgb, c))
    cols = []
    ink = _centroid(fam["black"]) if fam.get("black") else (20, 16, 16)
    cols.append(ink)
    if fam.get("white"):
        cols.append(_centroid(fam["white"]))
    for name, n in spec:
        if fam.get(name):
            cols += _split_shades(fam[name], n)
    seen, uniq = set(), []
    for c in cols:
        if c not in seen and len(uniq) < MAX_COLOURS + 1:
            seen.add(c)
            uniq.append(c)
    pal = Image.new("P", (1, 1))
    flat = [v for c in uniq for v in c]
    pal.putpalette(flat + [0] * (768 - len(flat)))
    return pal, ink


def _outline(im, ink, thin=False):
    """Re-stroke a 1px outline in `ink` around the silhouette (lost in the area shrink).
    `thin` uses a 4-connected ring (no diagonal corner pixels) for a lighter stroke."""
    a = im.getchannel("A").point(lambda v: 255 if v >= ALPHA_CUT else 0)
    grown = _dilate4(a) if thin else a.filter(ImageFilter.MaxFilter(3))
    ring = ImageChops.subtract(grown, a)  # the new 1px edge
    out = im.copy()
    out.paste(Image.new("RGBA", im.size, ink + (255,)), (0, 0), ring)
    return out


def _snap(im, pal):
    """Map opaque pixels to the shared palette; keep transparency."""
    a = im.getchannel("A").point(lambda v: 255 if v >= ALPHA_CUT else 0)
    rgb = im.convert("RGB").quantize(palette=pal, dither=Image.NONE).convert("RGB")
    out = rgb.convert("RGBA")
    out.putalpha(a)
    return out


def _presharpen(im, amount):
    """Unsharp the hi-res RGB before the area-average shrink, so fine features (face,
    eyes, claw edges) survive the big reduction. Alpha is left untouched."""
    if amount <= 0:
        return im
    a = im.getchannel("A")
    rgb = im.convert("RGB").filter(
        ImageFilter.UnsharpMask(radius=3, percent=int(amount * 100), threshold=0))
    out = rgb.convert("RGBA")
    out.putalpha(a)
    return out


def descale(srcs, body_h, flip, sharpen=0.0, outline=True, thin_outline=False, flat=False):
    """srcs: {beat: path}. Returns {beat: RGBA frame} on a shared canvas + palette."""
    raws = {}
    for beat, path in srcs.items():
        im = Image.open(path).convert("RGBA")
        if flip:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        raws[beat] = _presharpen(im, sharpen)

    # ONE scale factor for every pose (consistent body size), keyed off Ready's height.
    rb = _alpha_bbox(raws["ready"])
    factor = body_h / (rb[3] - rb[1])

    placed, feet = {}, {}
    for beat, im in raws.items():
        bb = _alpha_bbox(im)
        crop = im.crop(bb)
        w, h = max(1, round(crop.width * factor)), max(1, round(crop.height * factor))
        crop = crop.resize((w, h), Image.BOX)
        fx = (_foot_centre_x(im, bb) - bb[0]) * factor      # feet x within the crop
        placed[beat] = crop
        feet[beat] = (fx, h)                                # (foot x, bottom y) in crop

    # Shared canvas: every frame's feet land on one baseline + foot-centre.
    pad = 4
    left = max(feet[b][0] for b in placed) + pad
    right = max(placed[b].width - feet[b][0] for b in placed) + pad
    top = max(placed[b].height for b in placed) + pad
    cw = int((left + right + 7) // 8 * 8)
    ch = int((top + pad + 7) // 8 * 8)
    base_x, base_y = left, ch - pad                          # common foot anchor

    canvases = {}
    for beat, crop in placed.items():
        fx, fb = feet[beat]
        cv = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        cv.alpha_composite(crop, (int(round(base_x - fx)), int(round(base_y - fb))))
        canvases[beat] = _crisp(cv)

    cvs = list(canvases.values())
    if flat:
        pal, ink = _flat_palette(cvs, flat if isinstance(flat, tuple) else FLAT_SPEC)
    else:
        pal, ink = _shared_palette(cvs)
    snapped = {beat: _snap(cv, pal) for beat, cv in canvases.items()}
    if outline:
        snapped = {beat: _outline(im, ink, thin_outline) for beat, im in snapped.items()}
    return snapped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("frames", nargs="+", help="beat=path (ready=, windup=, peak=)")
    ap.add_argument("--body", type=int, default=56, help="Ready-pose body height in px")
    ap.add_argument("--sharpen", type=float, default=0.0,
                    help="pre-downscale unsharp amount (e.g. 1.5); 0 = off")
    ap.add_argument("--noflip", action="store_true", help="source already faces left")
    ap.add_argument("--no-outline", dest="outline", action="store_false",
                    help="skip the re-stroked silhouette outline")
    ap.add_argument("--thin-outline", action="store_true",
                    help="4-connected (lighter) outline instead of the 8-connected ring")
    ap.add_argument("--flat", nargs="?", const="", default=None,
                    help="curated family palette; optional spec 'red:3,orange:3,grey:2,brown:3'"
                         " (default = 2 shades per family)")
    a = ap.parse_args()
    srcs = dict(kv.split("=", 1) for kv in a.frames)
    os.makedirs(a.out_dir, exist_ok=True)
    flat = False
    if a.flat is not None:
        flat = (tuple((n, int(k)) for n, k in (p.split(":") for p in a.flat.split(",")))
                if a.flat else True)
    out = descale(srcs, a.body, not a.noflip, a.sharpen, a.outline, a.thin_outline, flat)
    for beat, im in out.items():
        p = os.path.join(a.out_dir, beat + ".png")
        im.save(p)
        print("wrote", p, im.size, "opaque colours:",
              len({c for c in im.getdata() if c[3] != 0}))


if __name__ == "__main__":
    main()
