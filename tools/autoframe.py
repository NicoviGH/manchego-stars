#!/usr/bin/env python3
"""Bottom-anchor + pad a character reference so it converts to a properly
framed FE8 bust.

FE8 talking busts are **bottom-anchored**: the subject fills to the bottom row
with transparent headroom on top and small side margins (verified against
vanilla Eirika: opaque rows 11-79, cols 21-88). A reference where the subject
fills its own frame edge-to-edge therefore reads "zoomed in" when converted
directly. This tool detects the subject, then composites it onto a flat-bg
canvas at ~1.2 aspect — bottom-anchored, ~10% headroom, ~5% side margins (SUBJ_H_FRAC/SUBJ_W_FRAC = 0.90) — so
`ref_to_bust.py` produces Braulo-style framing.

Usage:
    autoframe.py <ref.png> <framed.png>
    # then: ref_to_bust.py <framed.png> <bust.png> --crop 0,0,<W>,<H> --preview ...
    # (prints the exact ref_to_bust command to run)
"""

import argparse
import numpy as np
from PIL import Image

SUBJ_H_FRAC = 0.90   # subject height as fraction of canvas height (-> ~10% headroom)
SUBJ_W_FRAC = 0.90   # subject width  as fraction of canvas width  (-> ~5% each side)
COVER = 0.06         # row/col foreground coverage to count as "subject" (ignores thin wisps)


def autoframe(ref_path, out_path, subj_h=SUBJ_H_FRAC, subj_w=SUBJ_W_FRAC):
    src = Image.open(ref_path).convert('RGB')
    W, H = src.size
    rgb = np.asarray(src).astype(np.float32)
    edge = np.concatenate([rgb[0:8].reshape(-1, 3), rgb[:, 0:8].reshape(-1, 3), rgb[:, -8:].reshape(-1, 3)])
    bg = np.median(edge, 0)
    fg = np.sqrt(((rgb - bg) ** 2).sum(2)) >= 45

    xs = np.where(fg.sum(0) > H * COVER)[0]
    ys = np.where(fg.sum(1) > W * COVER)[0]
    sx0, sx1, sy0, sy1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    w_s, h_s = sx1 - sx0 + 1, sy1 - sy0 + 1

    canvas_h = int(round(max(h_s / subj_h, (w_s / subj_w) / 1.2)))
    canvas_w = int(round(canvas_h * 1.2))
    canvas = Image.new('RGB', (canvas_w, canvas_h), tuple(int(v) for v in bg))
    canvas.paste(src.crop((sx0, sy0, sx1 + 1, sy1 + 1)),
                 ((canvas_w - w_s) // 2, canvas_h - h_s))  # bottom-anchored
    canvas.save(out_path)
    return canvas_w, canvas_h


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ref')
    ap.add_argument('framed')
    ap.add_argument('--subj-h', type=float, default=SUBJ_H_FRAC,
                    help='subject height as fraction of canvas height (higher = bigger / less headroom)')
    ap.add_argument('--subj-w', type=float, default=SUBJ_W_FRAC,
                    help='subject width as fraction of canvas width (higher = bigger / less side margin)')
    a = ap.parse_args()
    w, h = autoframe(a.ref, a.framed, a.subj_h, a.subj_w)
    print("framed canvas %dx%d -> %s" % (w, h, a.framed))
    print("next: python3 tools/ref_to_bust.py %s <bust.png> --crop 0,0,%d,%d --preview <preview.png>"
          % (a.framed, w, h))


if __name__ == '__main__':
    main()
