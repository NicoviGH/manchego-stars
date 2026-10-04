#!/usr/bin/env python3
"""Vendor an FE-Repo asset in one command, and prove every vendored asset still matches its source.

    python3 tools/fe_repo_vendor.py anim <name> <mode> "<FE-Repo mode folder>" [--script FILE]
    python3 tools/fe_repo_vendor.py sms  <stem> "<FE-Repo sheet path, without -stand/-walk.png>"
    python3 tools/fe_repo_vendor.py verify            # re-fetch everything in both manifests

Each command records where the asset came from in the manifest beside it:
`engine/battle_anims/_vendored/fe-repo.yaml` and `campaigns/<c>/map_sprites/fe-repo.yaml`.
Nothing used to record this, so every reskin was re-scouted and cleaned up by hand -- ch05's
commit lists three sheets that each failed a different guard first (#26).

What a vendored asset IS, measured over every one in the tree on 2026-10-04:

  * A BATTLE ANIM is the mode folder's FEditor script plus its numbered frames
    (`<Mode>.txt`, `<Mode>_NNN.png`), byte for byte. All 402 vendored files were verbatim
    copies. The folder's sheets, .gif, .bin, .dmp and README are not taken. The one exception
    is a folder that ships only `<Mode> with comments.txt`, which is taken under the
    `<Mode>.txt` name feditor_to_banim reads (`--script`).
  * A MAP SPRITE is the source's stand/walk pair, PIXEL-identical but re-encoded: indexed,
    one palette index per colour, the green key at index 0. The build re-maps every sheet
    onto its base class's palette anyway (remap_sms_palette), so `verify` compares pictures
    for these, not bytes. All six enemy pairs were pixel-identical to their sources.

A cast sheet recoloured onto the cast palette (Ravisin, Sahnar, Trex...) is DERIVED, not
vendored: its recipe lives in its unit YAML, and it has no entry here.

Network: GitHub's API through `gh` (the listing) and raw.githubusercontent.com (the bytes).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

from PIL import Image

import map_sprite_tool as mst
from yaml_loader import yaml_load

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMPAIGN = 'rime-of-the-frostmaiden'
FE_REPO = 'Klokinator/FE-Repo'
RAW = 'https://raw.githubusercontent.com/%s/main/' % FE_REPO
ANIM_DIR = os.path.join(REPO, 'engine', 'battle_anims', '_vendored')
SMS_DIR = os.path.join(REPO, 'campaigns', CAMPAIGN, 'map_sprites')
MANIFEST = 'fe-repo.yaml'
MANIFEST_HEADER = {
    ANIM_DIR: '# FE-Repo source of every vendored battle anim: name -> mode -> folder (+ script).\n'
              '# Written by tools/fe_repo_vendor.py; `verify` re-fetches each one byte for byte.\n',
    SMS_DIR: '# FE-Repo source of every VENDORED map sprite: stem -> sheet path without '
             '-stand/-walk.png.\n# Derived cast recolours are not here. Written by '
             'tools/fe_repo_vendor.py; `verify` checks pixels.\n',
}


def fetch(path):
    """The bytes of one FE-Repo file."""
    with urllib.request.urlopen(RAW + urllib.parse.quote(path), timeout=60) as r:
        return r.read()


def list_folder(path):
    """File names in one FE-Repo folder (the contents API, through gh for its auth)."""
    out = subprocess.run(['gh', 'api', 'repos/%s/contents/%s' % (FE_REPO, urllib.parse.quote(path))],
                         capture_output=True, text=True)
    if out.returncode:
        sys.exit('ERROR: cannot list %r: %s' % (path, out.stderr.strip()))
    return sorted(e['name'] for e in json.loads(out.stdout) if e['type'] == 'file')


def anim_files(names, script=None):
    """(source name, vendored name) pairs a battle-anim mode folder contributes."""
    frames = [n for n in names if re.fullmatch(r'.+_\d{3}\.png', n)]
    if not frames:
        raise ValueError('no numbered frames (<Mode>_NNN.png) in this folder')
    mode = frames[0].rsplit('_', 1)[0]
    script = script or mode + '.txt'
    if script not in names:
        raise ValueError('no %s here; pass --script (it ships %s)'
                         % (script, ', '.join(n for n in names if n.endswith('.txt'))))
    return [(script, mode + '.txt')] + [(n, n) for n in frames]


def _pixels(im):
    """A sheet as what it SHOWS: RGB per pixel, None where transparent.

    Transparency is read from evidence, in this order, and never guessed from a pixel:
      1. the green key (#80a080 and kin) -- community sheets ship on it, and it is never art;
         judged by COLOUR, because a sheet may spend several indices on it (ch05's
         Bonewalker Axe walk sheet spent 20 indices on 14 colours);
      2. alpha 0, for a sheet that carries an alpha channel or a tRNS chunk;
      3. palette index 0, the decomp's own convention for an indexed sheet.
    A sheet with none of the three has no transparency marker at all and is refused: taking
    the corner pixel's colour instead would erase every real pixel that shares it."""
    rgba = list(im.convert('RGBA').getdata())
    keys = {p[:3] for p in rgba} & set(mst.GREEN_KEYS)
    if keys:
        return [None if p[3] == 0 or p[:3] in keys else p[:3] for p in rgba]
    if any(p[3] == 0 for p in rgba):
        return [None if p[3] == 0 else p[:3] for p in rgba]
    if im.mode == 'P':
        return [None if i == 0 else p[:3] for i, p in zip(im.getdata(), rgba)]
    raise ValueError('no transparency marker: no green key, no alpha, and not indexed')


def normalise_sheet(im):
    """A community sheet re-encoded the way the build's guards want it: indexed, one index per
    distinct colour, transparency on index 0 (painted the green key, which no art uses)."""
    px = _pixels(im)
    colours = [None]
    for c in px:
        if c not in colours:
            colours.append(c)
    if len(colours) > mst.MAX_COLORS:
        raise ValueError('%d colours; a map sprite allows %d' % (len(colours), mst.MAX_COLORS))
    index = {c: i for i, c in enumerate(colours)}
    rgb = [mst.GREEN_KEYS[0]] + colours[1:]
    out = Image.new('P', im.size)
    out.putpalette([v for c in rgb for v in c] + [0, 0, 0] * (16 - len(rgb)))
    out.putdata([index[c] for c in px])
    return out


def picture(im):
    """(size, pixels) -- what `verify` compares for a map sprite."""
    return im.size, _pixels(im)


def load_manifest(directory):
    path = os.path.join(directory, MANIFEST)
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as f:
        return yaml_load(f) or {}


def save_manifest(directory, data):
    import yaml
    with open(os.path.join(directory, MANIFEST), 'w', encoding='utf-8') as f:
        f.write(MANIFEST_HEADER[directory])
        yaml.safe_dump(data, f, sort_keys=True, allow_unicode=True, width=200)


def vendor_anim(name, mode, folder, script=None):
    pairs = anim_files(list_folder(folder), script)
    dest = os.path.join(ANIM_DIR, name, mode)
    os.makedirs(dest, exist_ok=True)
    for src, out in pairs:
        with open(os.path.join(dest, out), 'wb') as f:
            f.write(fetch(folder + '/' + src))
    data = load_manifest(ANIM_DIR)
    entry = {'folder': folder}
    if script:
        entry['script'] = script
    data.setdefault(name, {})[mode] = entry
    save_manifest(ANIM_DIR, data)
    print('vendored %d files -> %s' % (len(pairs), os.path.relpath(dest, REPO)))


def _sheet_pair(prefix):
    import io
    return [Image.open(io.BytesIO(fetch(prefix + suffix))) for suffix in ('-stand.png', '-walk.png')]


def vendor_sms(stem, prefix):
    idle, walk = _sheet_pair(prefix)
    for im, suffix in ((idle, '.png'), (walk, '_mu.png')):
        path = os.path.join(SMS_DIR, stem + suffix)
        normalise_sheet(im).save(path)
    mst.sheet_info(os.path.join(SMS_DIR, stem + '.png'))
    mst.validate_mu_sheet(os.path.join(SMS_DIR, stem + '_mu.png'))
    data = load_manifest(SMS_DIR)
    data[stem] = prefix
    save_manifest(SMS_DIR, data)
    print('vendored %s{,_mu}.png <- %s' % (stem, prefix))


def verify():
    """Every manifest entry re-fetched and compared. Returns the list of mismatches."""
    bad = []
    for name, modes in sorted(load_manifest(ANIM_DIR).items()):
        for mode, entry in sorted(modes.items()):
            dest = os.path.join(ANIM_DIR, name, mode)
            pairs = anim_files(list_folder(entry['folder']), entry.get('script'))
            want = {out for _, out in pairs}
            have = set(os.listdir(dest)) - {'CREDITS.md'}
            if want != have:
                bad.append('%s/%s: files differ (extra %s, missing %s)'
                           % (name, mode, sorted(have - want), sorted(want - have)))
                continue
            for src, out in pairs:
                with open(os.path.join(dest, out), 'rb') as f:
                    if f.read() != fetch(entry['folder'] + '/' + src):
                        bad.append('%s/%s/%s: bytes differ from the FE-Repo' % (name, mode, out))
    for stem, prefix in sorted(load_manifest(SMS_DIR).items()):
        for im, suffix in zip(_sheet_pair(prefix), ('.png', '_mu.png')):
            if picture(im) != picture(Image.open(os.path.join(SMS_DIR, stem + suffix))):
                bad.append('%s%s: picture differs from the FE-Repo' % (stem, suffix))
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    a = sub.add_parser('anim')
    a.add_argument('name')
    a.add_argument('mode')
    a.add_argument('folder')
    a.add_argument('--script')
    s = sub.add_parser('sms')
    s.add_argument('stem')
    s.add_argument('prefix')
    sub.add_parser('verify')
    args = ap.parse_args()
    if args.cmd == 'anim':
        vendor_anim(args.name, args.mode, args.folder, args.script)
    elif args.cmd == 'sms':
        vendor_sms(args.stem, args.prefix)
    else:
        bad = verify()
        for line in bad:
            print('MISMATCH', line)
        print('verify: %s' % ('%d mismatch(es)' % len(bad) if bad else 'every vendored asset matches its source'))
        sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
