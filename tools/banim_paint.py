#!/usr/bin/env python3
"""Hand-paint an imported battle anim's frames in the browser pixel editor (#206).

Some detail cannot be GENERATED at FE8 scale. Lupin's spectacles are ~4x3 px after the
shrink with a half-pixel frame stroke, and no palette reservation or `sharpen` setting
brings them back (measured -- sub-cell detail comes out slightly worse sharpened,
`test_poses_to_feditor`). They get drawn at final size, by hand, exactly as his MAP sprite
already did.

This is the plumbing for that: `poses_to_feditor`'s numbered frames become one vertical
sheet, `map_sprite_editor` opens it at the frames' own geometry and palette, and the saved
sheet becomes the numbered frames again. The painted frames ARE the deliverable -- there is
no re-render afterwards, so `poses.yaml` is marked `hand_painted: true` and
`poses_to_feditor` then refuses to overwrite them without `--force`.

    python3 tools/banim_paint.py edit  campaigns/.../battle_anims/lupin    # paint
    python3 tools/banim_paint.py apply campaigns/.../battle_anims/lupin    # save back
    python3 tools/banim_paint.py edit  <dir> --reset   # discard the paint, start from the frames

What is handed over is ONE shared window of the 248x160 canvas -- lossless, recorded, and
pasted straight back, so nothing is re-derived and nothing outside it is touched. Indices are
preserved end to end: it is the INDICES, not the embedded colours, that gbagfx packs to 4bpp
(decisions.md Art & Audio).
"""
import json
import os
import subprocess
import sys

import yaml
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
PAINT_DIR = '.paint'          # scratch the editor works in, beside the frames
PAD = 3                       # window margin, so paint can go just outside the silhouette


def frame_paths(anim_dir, abbr):
    """The numbered FEditor frames for `abbr`, in order."""
    stem = abbr.capitalize()
    out, i = [], 0
    while os.path.isfile(os.path.join(anim_dir, '%s_%03d.png' % (stem, i))):
        out.append(os.path.join(anim_dir, '%s_%03d.png' % (stem, i)))
        i += 1
    return out


def crop_window(frames, pad=PAD):
    """ONE window (PIL box) covering every frame's art, padded and clamped to the canvas.

    The FEditor canvas is 248x160 and the art occupies ~60x45 of it, in a different place
    each frame (the arc IS the motion). Handing the editor the raw canvas would mean
    hunting for the sprite in a field of backdrop and waiting on its per-row motion fit,
    which is O(canvas). One shared window keeps every frame ALIGNED, so onion-skin and the
    frame timeline still mean what they mean."""
    w, h = frames[0].size
    xs, ys = [], []
    for f in frames:
        for i, v in enumerate(f.getdata()):
            if v:
                xs.append(i % w)
                ys.append(i // w)
    if not xs:
        return (0, 0, w, h)
    return (max(0, min(xs) - pad), max(0, min(ys) - pad),
            min(w, max(xs) + 1 + pad), min(h, max(ys) + 1 + pad))


def build_sheet(frames, window=None):
    """Stack the frames' windows into one vertical strip, palette kept."""
    window = window or (0, 0) + frames[0].size
    w, h = window[2] - window[0], window[3] - window[1]
    sheet = Image.new('P', (w, h * len(frames)), 0)
    sheet.putpalette(frames[0].getpalette())
    for i, f in enumerate(frames):
        sheet.paste(f.crop(window), (0, i * h))
    return sheet


def split_sheet(sheet, n):
    """The inverse of build_sheet: one strip -> n equal tiles, indices untouched."""
    w, h = sheet.size
    fh = h // n
    out = []
    for i in range(n):
        tile = sheet.crop((0, i * fh, w, (i + 1) * fh))
        tile.putpalette(sheet.getpalette())
        out.append(tile)
    return out


def write_frames(sheet, anim_dir, abbr, n, window=None):
    """Paste a saved sheet's tiles back into the numbered frames at `window`.

    Only the window is touched -- everything outside it is whatever the frame already
    held, so the paste cannot quietly crop the canvas down to the painting surface."""
    stem = abbr.capitalize()
    for i, tile in enumerate(split_sheet(sheet, n)):
        path = os.path.join(anim_dir, '%s_%03d.png' % (stem, i))
        if window is None:
            tile.save(path)
            continue
        canvas = Image.open(path)
        canvas.paste(tile, (window[0], window[1]))
        canvas.save(path)
    return n


def _spec(anim_dir):
    with open(os.path.join(anim_dir, 'poses.yaml'), encoding='utf-8') as f:
        return yaml.safe_load(f)


def _paint_paths(anim_dir):
    d = os.path.join(anim_dir, PAINT_DIR)
    return d, os.path.join(d, 'sheet.png'), os.path.join(d, 'palette.png')


def prepare_sheet(anim_dir, reset=False):
    """Make sure `.paint/` holds a sheet + palette for the current frames; return its path.

    An EXISTING sheet of the right shape is KEPT, never rebuilt. The sheet is scratch derived
    from the frames, so rebuilding on every open would silently discard a painting session
    that had not been `apply`d yet -- which is exactly the accident that nearly lost Lupin's
    glasses. It is only rebuilt when its shape no longer matches (the window moved, so the
    old paint would not line up anyway) or on an explicit `reset`."""
    spec = _spec(anim_dir)
    paths = frame_paths(anim_dir, spec['abbr'])
    if not paths:
        sys.exit('ERROR: no frames in %s -- run poses_to_feditor first' % anim_dir)
    frames = [Image.open(p) for p in paths]
    d, sheet_path, pal_path = _paint_paths(anim_dir)
    os.makedirs(d, exist_ok=True)
    window = crop_window(frames)
    fresh = build_sheet(frames, window)
    keep = (not reset and os.path.isfile(sheet_path)
            and Image.open(sheet_path).size == fresh.size)
    if not keep:
        fresh.save(sheet_path)
    with open(os.path.join(d, 'window.json'), 'w', encoding='utf-8') as f:
        json.dump(list(window), f)
    # The editor reads its palette from a 16px-wide swatch strip (map_sprite_tool.read_palette).
    pal = Image.new('P', (16, 1), 0)
    pal.putpalette(fresh.getpalette())
    pal.putdata(list(range(16)))
    pal.save(pal_path)
    return sheet_path


def cmd_edit(anim_dir, port, reset=False):
    sheet_path = prepare_sheet(anim_dir, reset)
    _d, _s, pal_path = _paint_paths(anim_dir)
    with open(os.path.join(os.path.dirname(sheet_path), 'window.json'), encoding='utf-8') as f:
        window = tuple(json.load(f))
    w, h = window[2] - window[0], window[3] - window[1]
    n = Image.open(sheet_path).height // h
    print('painting %d frame(s) of %dx%d (window %s of the canvas) from %s'
          % (n, w, h, list(window), anim_dir))
    print('when you are done: python3 tools/banim_paint.py apply %s' % anim_dir)
    subprocess.call([sys.executable, os.path.join(HERE, 'map_sprite_editor.py'),
                     sheet_path, pal_path, '--frame', '%dx%d' % (w, h),
                     '--port', str(port)])


def cmd_apply(anim_dir):
    spec = _spec(anim_dir)
    d, sheet_path, _pal = _paint_paths(anim_dir)
    if not os.path.isfile(sheet_path):
        sys.exit('ERROR: nothing painted yet (%s missing)' % sheet_path)
    n = len(frame_paths(anim_dir, spec['abbr']))
    with open(os.path.join(d, 'window.json'), encoding='utf-8') as f:
        window = tuple(json.load(f))
    write_frames(Image.open(sheet_path), anim_dir, spec['abbr'], n, window)
    print('  %d frame(s) updated from %s' % (n, sheet_path))
    if not spec.get('hand_painted'):
        print('  NOTE: add `hand_painted: true` to poses.yaml so a re-render cannot '
              'silently overwrite this.')


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ('edit', 'apply'):
        sys.exit('usage: banim_paint.py edit|apply <anim_dir> [--port N] [--reset]')
    cmd, anim_dir = sys.argv[1], sys.argv[2]
    port = int(sys.argv[sys.argv.index('--port') + 1]) if '--port' in sys.argv else 8765
    (cmd_edit(anim_dir, port, '--reset' in sys.argv) if cmd == 'edit'
     else cmd_apply(anim_dir))


if __name__ == '__main__':
    main()
