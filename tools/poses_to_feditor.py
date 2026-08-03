#!/usr/bin/env python3
"""Hi-res poses -> FEditor "For Each Frame" battle-anim frames (imported-PC-anim path).

Where `descale_battleframe.py` (the faked 3-pose path, #65) PINS the feet so the body never
moves between beats, an imported anim (feditor_to_banim, #90) wants the OPPOSITE: each pose
sits at its own spot on a shared canvas so the per-frame shift BECOMES the on-screen motion.
This tool is that bridge -- it turns a page of hi-res poses + an arc manifest into the
248x160 indexed FEditor frames the #90 importer consumes (Pinky, the flier, is the first PC
to ride it; his swoop can't be faked from 3 static poses).

Reads `<dir>/poses.yaml` (canvas / home / target_h / abbr / poses[name,src,dx,dy]) and writes
`<dir>/<Abbr>_000.png ..` -- one uniform downscale for EVERY pose (the ears grow, the body
scale stays constant), one shared <=15-colour palette (index 0 = a keyed-out backdrop, so the
importer's corner-key drops it), each sprite composited at its arc offset from the idle home.

    python3 tools/poses_to_feditor.py campaigns/rime-of-the-frostmaiden/battle_anims/pinky

Two OPT-IN manifest keys, both added for Lupin's wolf pounce (#206); omit them and the output
is byte-identical to what shipped for Pinky:
  * `outline: true` -- re-stroke the silhouette in the palette's ink after the shrink. The
    faked 3-pose path has always done this (descale_battleframe's `_outline`): an area-average
    downscale eats a drawn outline, and an FE8 battle sprite without one reads as a blob.
  * `sharpen: <amount>` -- pre-unsharp before the area shrink, exactly as `descale --sharpen`
    does for the faked path (the cast runs 0-2.0). It rescues EDGES; it does NOT rescue detail
    finer than one shrink cell, which comes out slightly worse (measured, test_poses_to_feditor)
    -- that detail gets PAINTED at final size instead (`hand_painted:`, tools/banim_paint.py).
  * `reserve: [[r,g,b], ..]` -- force a colour into the <=15-colour palette that no source
    pixel carries. Same seam as `descale --reserve` (which rescued Rootis's carrot nose from
    the median-cut). Its other use is the one Lupin needs: a colour to HAND-PAINT with that
    the art itself does not contain.

Review the frames, then wire the unit YAML `battle_anim.import` block + author the `.txt`.
"""
import os
import sys

import yaml
from PIL import Image

import descale_battleframe as db

BACKDROP = (0, 255, 0)     # canvas index 0: a colour the sprite never uses (keyed out on import)


def _downscaled(poses, src_dir, target_h, flip=True, sharpen=0.0):
    """Every pose BOX-downscaled by ONE factor (idle height -> target_h) then alpha-cropped.

    `flip` mirrors each source to FE8-canonical SCREEN-LEFT facing (the whole cast's convention;
    descale_battleframe flips by default too). The arc dx signs in poses.yaml must match: a
    left-facing unit dives toward the foe with NEGATIVE dx (like ref_to_battleframe's melee lunge).
    `sharpen` pre-unsharps before the area shrink, the same way `descale --sharpen` does for the
    faked path -- without it, detail finer than the shrink factor averages into the body colour."""
    idle = Image.open(os.path.join(src_dir, poses[0]['src'])).convert('RGBA')
    bb = db._alpha_bbox(idle)
    factor = target_h / (bb[3] - bb[1])
    outs = []
    for p in poses:
        im = Image.open(os.path.join(src_dir, p['src'])).convert('RGBA')
        if flip:
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        im = db._presharpen(im, sharpen)
        im = im.resize((max(1, round(im.width * factor)),
                        max(1, round(im.height * factor))), Image.BOX)
        a = im.getchannel('A').point(lambda v: 255 if v >= db.ALPHA_CUT else 0)
        im.putalpha(a)
        outs.append(im.crop(im.getchannel('A').getbbox()))
    return outs, factor


def _stroke_outline(canvas, ink_index):
    """Paint a 1px 4-connected ring of `ink_index` around everything already drawn.

    Done on the COMPOSITED canvas rather than on the loose pose: the frame holds exactly one
    sprite either way, and stroking here needs no padding -- an alpha-cropped pose has no room
    inside its own bounds for a ring, and padding it would shift the placement arithmetic."""
    c = canvas.load()
    cw, ch = canvas.size
    ring = [(x, y) for y in range(ch) for x in range(cw) if c[x, y] == 0
            and any(0 <= x + dx < cw and 0 <= y + dy < ch and c[x + dx, y + dy] not in (0,)
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))]
    for x, y in ring:
        c[x, y] = ink_index


def build_frames(spec, src_dir):
    """spec: the parsed poses.yaml. Returns [(name, P-image)] -- FEditor 248x160 frames."""
    poses = spec['poses']
    cw, ch = spec['canvas']
    hx, hy = spec['home']
    downs, _ = _downscaled(poses, src_dir, spec['target_h'], spec.get('flip', True),
                           spec.get('sharpen', 0.0))

    reserve = [tuple(c) for c in spec.get('reserve', ())]
    pal15, ink = db._shared_palette(downs, reserve)               # 15 sprite colours
    final_pal = list(BACKDROP) + pal15.getpalette()[:db.MAX_COLOURS * 3]
    final_pal += [0] * (768 - len(final_pal))
    entries = [tuple(final_pal[i:i + 3]) for i in range(0, 16 * 3, 3)]
    ink_index = entries.index(ink)               # _shared_palette RESERVES ink, so it is present

    frames = []
    for p, im in zip(poses, downs):
        idx = im.convert('RGB').quantize(palette=pal15, dither=Image.NONE)  # 0..14
        canvas = Image.new('P', (cw, ch), 0)
        canvas.putpalette(final_pal)
        a, q, c = im.getchannel('A'), idx.load(), canvas.load()
        ox = round(hx + p['dx'] - im.width / 2)
        oy = round(hy - p['dy'] - im.height / 2)                 # dy is UP; screen y grows down
        for y in range(im.height):
            for x in range(im.width):
                if a.getpixel((x, y)) >= db.ALPHA_CUT:
                    px, py = ox + x, oy + y
                    if 0 <= px < cw and 0 <= py < ch:
                        c[px, py] = q[x, y] + 1                  # +1: leave index 0 for backdrop
        if spec.get('outline'):
            _stroke_outline(canvas, ink_index)
        frames.append((p['name'], canvas))
    return frames


def write_frames(spec, anim_dir, force=False):
    """Render the manifest to `<Abbr>_000.png ..` beside it.

    A manifest marked `hand_painted: true` REFUSES to be re-rendered: detail that had to be
    drawn at final size (Lupin's glasses -- see banim_paint.py) lives only in those PNGs, and
    a regeneration would throw it away silently. `--force` is the deliberate override, and
    means the paint has to be redone."""
    if spec.get('hand_painted') and not force:
        sys.exit('ERROR: %s is marked hand_painted -- re-rendering would discard the paint '
                 'in its frames. Pass --force if that is really what you want (then repaint '
                 'via tools/banim_paint.py).' % os.path.join(anim_dir, 'poses.yaml'))
    abbr = spec['abbr'].capitalize()
    for i, (name, img) in enumerate(build_frames(spec, anim_dir)):
        out = os.path.join(anim_dir, '%s_%03d.png' % (abbr, i))
        img.save(out)
        print('  %-8s -> %s' % (name, os.path.basename(out)))


def main():
    args = [a for a in sys.argv[1:] if a != '--force']
    if len(args) != 1:
        sys.exit('usage: poses_to_feditor.py [--force] <anim_dir with poses.yaml>')
    anim_dir = args[0]
    with open(os.path.join(anim_dir, 'poses.yaml'), encoding='utf-8') as f:
        spec = yaml.safe_load(f)
    write_frames(spec, anim_dir, force='--force' in sys.argv)


if __name__ == '__main__':
    main()
