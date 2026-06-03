#!/usr/bin/env python3
"""build_campaign.py -- inject campaign content into the fireemblem8u decomp build.

Reads campaign data (YAML + authored busts) and writes decomp-native source/asset
files into the fireemblem8u submodule working tree, so a plain `make` compiles a
ROM carrying our content. The generated files are reproducible build artifacts --
restore vanilla with `git -C fireemblem8u checkout <path>`.

Engine/Content boundary (CLAUDE.md): the GENERATOR knows character/chapter names;
the C/asm it EMITS is just data. No campaign name is ever hardcoded in engine C.

--- Milestone A (current): PORTRAITS ---------------------------------------------
For each named cast member, run the bust through portrait_tool.generate (4 decomp
assets) and overwrite a vanilla portrait slot's source files in
graphics/portrait/. The decomp's generic gbagfx pattern rules rebuild the
.4bpp/.4bpp.fk/.4bpp.lz on the next `make`; data_portrait[] is untouched, so the
mapped vanilla character simply wears our face. Zero C changes, fully reversible.

Milestones B+ (characters, chapter, dialogue codegen) hang off the same CLI.
"""

import argparse
import os
import sys

# portrait_tool lives next to us in tools/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import portrait_tool  # noqa: E402
import yaml  # noqa: E402
from PIL import Image  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECOMP = os.path.join(REPO, 'fireemblem8u')
PORTRAIT_DIR = os.path.join(DECOMP, 'graphics', 'portrait')


# our cast bust  ->  vanilla portrait slot whose graphic files we overwrite.
# Slots are FE8's earliest-available cast so one early chapter shows many faces.
# (portrait-only mapping; class/stat mapping comes in Milestone B.)
PORTRAIT_MAP = {
    'braulo':     'Eirika',    # the prologue lord -- first face the player sees
    'marty':      'Seth',
    'wolfram':    'Franz',
    'meesmickle': 'Gilliam',
    'prof-rbg':   'Moulder',
    'rootis':     'Vanessa',
    'sclorbo':    'Ross',
    'pinky':      'Neimi',
    'pepperjack': 'Garcia',
    'brie':       'Colm',
}


def _load_unit_yaml(campaign, unit):
    """Find <unit>.yaml under pcs/ or npcs/ and return its parsed dict (or {})."""
    for sub in ('pcs', 'npcs'):
        p = os.path.join(REPO, 'campaigns', campaign, sub, unit + '.yaml')
        if os.path.isfile(p):
            with open(p) as f:
                return yaml.safe_load(f) or {}
    return {}


def inject_portraits(campaign, verbose=True):
    """Overwrite each mapped vanilla portrait slot with our authored bust."""
    bust_dir = os.path.join(REPO, 'campaigns', campaign, 'portraits')
    if not os.path.isdir(PORTRAIT_DIR):
        sys.exit('ERROR: decomp portrait dir not found: %s' % PORTRAIT_DIR)

    for unit, vanilla in PORTRAIT_MAP.items():
        bust_path = os.path.join(bust_dir, unit + '.png')
        if not os.path.isfile(bust_path):
            sys.exit('ERROR: missing bust for %s: %s' % (unit, bust_path))

        im = Image.open(bust_path)
        portrait_tool._check_indexed(im, bust_path)
        if im.size != (portrait_tool.BUST_W, portrait_tool.BUST_H):
            sys.exit('ERROR: %s is %s, expected %dx%d bust'
                     % (bust_path, im.size, portrait_tool.BUST_W, portrait_tool.BUST_H))

        # Facing: FE8's canonical portrait faces screen-LEFT (the engine HFLIPs
        # for the right-side speaker). A bust authored facing right reads backwards
        # in cutscenes, so flip it here. Per-unit fact: art.render.flip_h in YAML.
        render = (_load_unit_yaml(campaign, unit).get('art') or {}).get('render') or {}
        if render.get('flip_h'):
            im = im.transpose(Image.FLIP_LEFT_RIGHT)

        # static_portrait=True: custom busts are non-animated (no mouth flap, no
        # eye-blink) -- aligning per-frame mouth/eye art for custom portraits is
        # infeasible, so we lock them still. See portrait_tool.generate.
        tileset, mouth, chibi, pal_bytes = portrait_tool.generate(im, static_portrait=True)

        base = os.path.join(PORTRAIT_DIR, 'portrait_' + vanilla)
        tileset.save(base + '_tileset.png')
        mouth.save(base + '_mouth.png')
        chibi.save(base + '_chibi.png')
        with open(base + '_palette.agbpal', 'wb') as f:
            f.write(pal_bytes)

        if verbose:
            print('  %-10s -> portrait_%s (tileset/mouth/chibi/palette)' % (unit, vanilla))


def main():
    ap = argparse.ArgumentParser(description='Inject campaign content into the decomp build.')
    ap.add_argument('--campaign', default='rime-of-the-frostmaiden')
    ap.add_argument('--portraits-only', action='store_true',
                    help='(default in Milestone A) only inject portrait assets')
    args = ap.parse_args()

    print('build_campaign: injecting "%s" into %s' % (args.campaign, DECOMP))
    print('portraits:')
    inject_portraits(args.campaign)
    print('done. Run `make` to compile the ROM.')


if __name__ == '__main__':
    main()
