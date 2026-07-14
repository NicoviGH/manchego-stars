#!/usr/bin/env python3
"""Assemble playtest motion frames into a review GIF (and open it for Nicolas).

The headed mGBA harness (tools/playtest/harness.lua) drops PNG frames named
`NN-<tag>.png` into /tmp/playtest-<scenario>/ during a `record*` scenario. This
turns those frames into a single GIF for motion review.

Standard workflow (the recording capability, so it isn't re-derived each time):

    tools/playtest/run.sh recordending                 # capture frames -> /tmp/playtest-recordending/
    tools/playtest/make_gif.py recordending end \\      # frames tagged "end" -> a GIF
        --name ch01-ending-rolling-cheddar --open

By default, the GIF is written under docs/demo/ so it can be committed on the
current feature branch and reviewed in the GitHub PR.

Args:
  scenario   the run.sh scenario name (its frames live in /tmp/playtest-<scenario>/)
  tag        frame tag to assemble (e.g. "end", "trail", "op"); default: all frames
Options:
  --name N   output basename (default: <scenario>-<tag>)
  --fps F    playback frames/sec (default 12)
  --scale S  integer upscale of the 240x160 GBA frame (default 2)
  --out DIR  output dir (default: <repo>/docs/demo)
  --mp4      encode an H.264 .mp4 via ffmpeg instead of a .gif (smaller, no
             quantization artifacts; good for LOCAL viewing). NOTE: a committed
             .mp4 does NOT render inline on GitHub (web or mobile) -- it is a
             binary download -- so for repo-committed review use the default GIF
             (GitHub renders GIFs inline). See [[feedback_remote_file_delivery]].
  --open     open the finished GIF/MP4

Requires ffmpeg on PATH for --mp4 (brew install ffmpeg).
"""
import argparse
import glob
import os
import subprocess
import sys

from PIL import Image

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
DEFAULT_OUT = os.path.join(REPO, 'docs', 'demo')


def collect_frames(shotdir, tag):
    """Frames are `NN-<tag>.png`; NN is the harness's global shot counter. Sort
    NUMERICALLY on it -- the counter's zero padding (%02d) runs out at 99 while a
    record run shoots hundreds of frames, so a lexical sort would splice '100-'
    before '99-' and scramble the capture order mid-scene."""

    def shot_no(path):
        head = os.path.basename(path).split('-', 1)[0]
        return int(head) if head.isdigit() else -1

    return sorted((f for f in glob.glob(os.path.join(shotdir, '*.png'))
                   if tag in os.path.basename(f).split('-', 1)[-1]), key=shot_no)


def mp4_cmd(in_pattern, out, fps, scale):
    """ffmpeg arg list: encode a zero-padded frame sequence to faststart H.264.
    Nearest-neighbor upscale keeps the pixels crisp; yuv420p is the broadly
    playable pixel format (GBA 240x160 stays even at any integer scale)."""
    cmd = ['ffmpeg', '-y', '-framerate', '%g' % fps, '-i', in_pattern]
    if scale != 1:
        cmd += ['-vf', 'scale=iw*%d:ih*%d:flags=neighbor' % (scale, scale)]
    cmd += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18',
            '-movflags', '+faststart', out]
    return cmd


def write_mp4(frames, out, fps, scale):
    """Encode `frames` (capture-order paths) to `out` via ffmpeg. ffmpeg's image2
    demuxer needs a contiguous %04d sequence, so symlink the (possibly sparse-
    numbered, tag-filtered) frames into a temp dir first."""
    import shutil
    import tempfile
    seqdir = tempfile.mkdtemp(prefix='makegif-seq-')
    try:
        for i, f in enumerate(frames):
            os.symlink(os.path.abspath(f), os.path.join(seqdir, '%04d.png' % i))
        subprocess.run(mp4_cmd(os.path.join(seqdir, '%04d.png'), out, fps, scale),
                       check=True)
    finally:
        shutil.rmtree(seqdir, ignore_errors=True)


def write_gif_ffmpeg(frames, out, fps, scale):
    """Fast, high-quality GIF via ffmpeg palettegen/paletteuse (one shared palette,
    no dither -- clean for pixel art). PIL's save_all delta+full double-encode plus
    the decode-back self-check is O(frames^2)-ish and stalls for MINUTES past a few
    hundred frames; ffmpeg does the same clip in seconds. Frames are sparse-numbered
    (tag-filtered), so symlink them into a contiguous %04d seq first (cf. write_mp4)."""
    import shutil
    import tempfile
    seqdir = tempfile.mkdtemp(prefix='makegif-seq-')
    try:
        for i, f in enumerate(frames):
            os.symlink(os.path.abspath(f), os.path.join(seqdir, '%04d.png' % i))
        vf = ('scale=iw*%d:ih*%d:flags=neighbor,split[a][b];'
              '[a]palettegen=stats_mode=full[p];[b][p]paletteuse=dither=none'
              % (scale, scale))
        cmd = ['ffmpeg', '-y', '-framerate', '%g' % fps,
               '-i', os.path.join(seqdir, '%04d.png'), '-vf', vf, out]
        subprocess.run(cmd, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    finally:
        shutil.rmtree(seqdir, ignore_errors=True)


def _have_ffmpeg():
    from shutil import which
    return which('ffmpeg') is not None


def _shared_palette(imgs):
    """One palette for the whole clip. A GBA clip usually has <=256 unique colors
    total, so the palette is exact (lossless); busier clips get a mediancut over a
    sheet of EVERY frame (so one-frame colors like crit flashes still land a
    palette slot). No dither either way -- pixel art quantizes clean."""
    colors = set()
    for im in imgs:
        got = im.getcolors(maxcolors=257)
        if got is None:
            colors = None
            break
        colors.update(c for _, c in got)
        if len(colors) > 256:
            colors = None
            break
    if colors is not None:
        pal = Image.new('P', (1, 1))
        pal.putpalette([v for c in sorted(colors) for v in c])
        return pal
    sheet = Image.new('RGB', (imgs[0].width, imgs[0].height * len(imgs)))
    for i, im in enumerate(imgs):
        sheet.paste(im, (0, i * imgs[0].height))
    return sheet.quantize(colors=256, method=Image.MEDIANCUT)


def _decoded_frames(data):
    import io
    from PIL import ImageSequence
    return [f.convert('RGB').tobytes()
            for f in ImageSequence.Iterator(Image.open(io.BytesIO(data)))]


def encode_gif(imgs, duration):
    """RGB frames -> (gif bytes, 'delta'|'full'). The delta path -- one shared
    palette + disposal=1 -- lets PIL store dirty-rect diffs instead of full
    frames (5-6x smaller on battle-anim clips whose background never moves;
    audit 2.7 -- committed docs/demo GIFs live in git history forever). NO
    optimize=True there: it re-maps palette indices per frame, which corrupts
    cross-frame deltas (verified: menu-transition clips decode garbled). The
    result is self-checked by decoding it back; if the delta encode is bigger OR
    decodes off by more than the quantizer itself, ship the legacy full-frame
    form (disposal=2) instead."""
    import io
    q = [im.quantize(palette=_shared_palette(imgs), dither=Image.Dither.NONE)
         for im in imgs]
    delta, full = io.BytesIO(), io.BytesIO()
    q[0].save(delta, 'GIF', save_all=True, append_images=q[1:], loop=0,
              duration=duration, disposal=1)
    q[0].save(full, 'GIF', save_all=True, append_images=q[1:], loop=0,
              duration=duration, disposal=2)
    delta, full = delta.getvalue(), full.getvalue()
    if len(delta) < len(full) and _decoded_frames(delta) == _decoded_frames(full):
        return delta, 'delta'
    return full, 'full'


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('scenario')
    ap.add_argument('tag', nargs='?', default='')
    ap.add_argument('--name')
    ap.add_argument('--fps', type=float, default=12.0)
    ap.add_argument('--scale', type=int, default=2)
    ap.add_argument('--out', default=DEFAULT_OUT)
    ap.add_argument('--mp4', action='store_true',
                    help='encode an H.264 .mp4 via ffmpeg instead of a .gif '
                         '(smaller, no quantization artifacts)')
    ap.add_argument('--ffmpeg', action='store_true',
                    help='force the fast ffmpeg palettegen GIF path (default for >300 frames)')
    ap.add_argument('--pil', action='store_true',
                    help='force the PIL delta-encode GIF path (small, but slow past a few hundred frames)')
    ap.add_argument('--open', action='store_true', dest='do_open')
    a = ap.parse_args(argv)

    shotdir = '/tmp/playtest-%s' % a.scenario
    if not os.path.isdir(shotdir):
        sys.exit('ERROR: no frames dir %s -- run `tools/playtest/run.sh %s` first'
                 % (shotdir, a.scenario))
    frames = collect_frames(shotdir, a.tag)
    if not frames:
        sys.exit('ERROR: no frames matching tag %r in %s' % (a.tag, shotdir))

    name = a.name or ('%s-%s' % (a.scenario, a.tag or 'all'))
    os.makedirs(a.out, exist_ok=True)

    if a.mp4:
        out = os.path.join(a.out, name + '.mp4')
        write_mp4(frames, out, a.fps, a.scale)
        print('wrote %s (%d frames, %.0f fps, %dx scale)'
              % (out, len(frames), a.fps, a.scale))
        if a.do_open:
            subprocess.run(['open', out], check=False)
            print('opened')
        return 0

    imgs = []
    for f in frames:
        im = Image.open(f).convert('RGB')
        if a.scale != 1:
            im = im.resize((im.width * a.scale, im.height * a.scale), Image.NEAREST)
        imgs.append(im)

    out = os.path.join(a.out, name + '.gif')
    # ffmpeg palettegen is seconds; PIL's delta+full+decode-check stalls for minutes
    # past a few hundred frames. Default to ffmpeg for big clips (falls back to PIL if
    # ffmpeg is missing); --pil forces the PIL delta path, --ffmpeg forces ffmpeg.
    use_ffmpeg = a.ffmpeg or (not a.pil and len(frames) > 300)
    if use_ffmpeg and _have_ffmpeg():
        write_gif_ffmpeg(frames, out, a.fps, a.scale)
        print('wrote %s (%d frames, %.0f fps, %dx scale, ffmpeg palettegen, %d KB)'
              % (out, len(frames), a.fps, a.scale, os.path.getsize(out) // 1024))
    else:
        data, how = encode_gif(imgs, int(1000 / a.fps))
        with open(out, 'wb') as f:
            f.write(data)
        print('wrote %s (%d frames, %.0f fps, %dx scale, %s encoding, %d KB)'
              % (out, len(imgs), a.fps, a.scale, how, len(data) // 1024))

    if a.do_open:
        subprocess.run(['open', '-a', 'Safari', out], check=False)
        print('opened in Safari')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
