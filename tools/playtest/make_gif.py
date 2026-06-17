#!/usr/bin/env python3
"""Assemble playtest motion frames into a review GIF (and open it for Nicolas).

The headed mGBA harness (tools/playtest/harness.lua) drops PNG frames named
`NN-<tag>.png` into /tmp/playtest-<scenario>/ during a `record*` scenario. This
turns those frames into a single GIF for motion review.

Standard workflow (the recording capability, so it isn't re-derived each time):

    tools/playtest/run.sh recordending                 # capture frames -> /tmp/playtest-recordending/
    tools/playtest/make_gif.py recordending end \\      # frames tagged "end" -> a GIF
        --name ch01-ending-rolling-cheddar --open

`--open` saves under map-review/ and opens in Safari (Preview paginates GIFs; Safari
plays them -- Nicolas can't see inline renders, see [[feedback_sharing_visual_drafts]]).

Args:
  scenario   the run.sh scenario name (its frames live in /tmp/playtest-<scenario>/)
  tag        frame tag to assemble (e.g. "end", "trail", "op"); default: all frames
Options:
  --name N   output basename (default: <scenario>-<tag>)
  --fps F    playback frames/sec (default 12)
  --scale S  integer upscale of the 240x160 GBA frame (default 2)
  --out DIR  output dir (default: <repo>/map-review)
  --open     open the finished GIF in Safari
"""
import argparse
import glob
import os
import subprocess
import sys

from PIL import Image

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('scenario')
    ap.add_argument('tag', nargs='?', default='')
    ap.add_argument('--name')
    ap.add_argument('--fps', type=float, default=12.0)
    ap.add_argument('--scale', type=int, default=2)
    ap.add_argument('--out', default=os.path.join(REPO, 'map-review'))
    ap.add_argument('--open', action='store_true', dest='do_open')
    a = ap.parse_args(argv)

    shotdir = '/tmp/playtest-%s' % a.scenario
    if not os.path.isdir(shotdir):
        sys.exit('ERROR: no frames dir %s -- run `tools/playtest/run.sh %s` first'
                 % (shotdir, a.scenario))
    # Frames are `NN-<tag>.png`; NN is a zero-padded global counter, so lexical sort
    # == capture order. Filter to the tag (substring after the NN- prefix).
    frames = sorted(f for f in glob.glob(os.path.join(shotdir, '*.png'))
                    if a.tag in os.path.basename(f).split('-', 1)[-1])
    if not frames:
        sys.exit('ERROR: no frames matching tag %r in %s' % (a.tag, shotdir))

    imgs = []
    for f in frames:
        im = Image.open(f).convert('RGB')
        if a.scale != 1:
            im = im.resize((im.width * a.scale, im.height * a.scale), Image.NEAREST)
        imgs.append(im)

    name = a.name or ('%s-%s' % (a.scenario, a.tag or 'all'))
    os.makedirs(a.out, exist_ok=True)
    out = os.path.join(a.out, name + '.gif')
    imgs[0].save(out, save_all=True, append_images=imgs[1:], loop=0,
                 duration=int(1000 / a.fps), disposal=2)
    print('wrote %s (%d frames, %.0f fps, %dx scale)'
          % (out, len(imgs), a.fps, a.scale))

    if a.do_open:
        subprocess.run(['open', '-a', 'Safari', out], check=False)
        print('opened in Safari')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
