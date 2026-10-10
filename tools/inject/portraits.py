"""Portraits: the campaign's busts, their dressed guest slots, and portrait geometry.
"""
import os
import re
import sys

from PIL import Image

import portrait_tool
from inject.arena import arena_presentation_config
from inject.cast import _bust_dir, dressed_guest_slots, GUEST_PORTRAIT_MAP, PORTRAIT_MAP
from inject.chapter_ids import (
    CH02_CHWINGA_PORTRAIT_SLOT, CH02_CHWINGA_SPRITE_SRC, CH05_VISIT_FACES)
from inject.paths import PORTRAIT_DATA_C, PORTRAIT_DIR


# Our busts are all framed identically: the mouth window sits at tile (col 2, row 6)
# and eyes at (col 3, row 4) -- the geometry portrait_tool extracts the mouth from, and
# the same xMouth/yMouth/xEyes/yEyes the Eirika/Franz/Vanessa/Neimi slots already carry
# (those render our busts cleanly). Slots whose FaceData uses different coords (Seth,
# Gilliam, Moulder = 2,5; Ross = 3,6; Garcia = 2,5; Colm = 3,5) make the engine overwrite
# the mouth window one tile off -> a second, offset mouth. Normalize every dressed slot.
PORTRAIT_GEOMETRY = '2, 6, 3, 4'   # xMouth, yMouth, xEyes, yEyes

# Every dressed slot holds a static bust (portrait_tool.generate(static_portrait=True)): no eye
# frames, and its top corner strips sit in the sheet tiles the eye frames would use. This blink
# kind is how engine patch 0018 knows -- it draws the corners and never paints an eye frame.
PORTRAIT_BLINK = 'FACE_BLINK_STATIC'

# Ravisin is a chapter boss, not a recruit, so she uses the guest portrait path rather than
# PORTRAIT_MAP's cast-identity machinery. Her approved portrait is Garytop's F2E Aversa mug
# with a strict seven-entry palette substitution: silver hair -> chestnut and warm skin ->
# frost-pale. Nicolas approved this exact mapping on 2026-08-10; the original brown markings
# and every pixel position stay untouched.
RAVISIN_VENDOR_MUG = 'Aversa {Garytop} [F2E].png'
RAVISIN_RECOLOR = {
    (247, 243, 238): (172, 116, 76),
    (219, 216, 224): (140, 88, 56),
    (170, 171, 186): (104, 64, 40),
    (125, 114, 135): (72, 40, 32),
    (227, 207, 182): (240, 232, 232),
    (201, 165, 142): (208, 192, 200),
    (163, 130, 110): (176, 152, 168),
}


def dressed_portrait_slots(campaign):
    """EVERY vanilla portrait slot this build overwrites -- cast, guests, the ch02 chwinga and
    the ch05 reliquary residents.

    This exists because dressing a slot and normalizing its mouth/eye geometry are two separate
    steps, and for a long time the second one only knew about the first two groups. A slot that
    is dressed but NOT normalized keeps the vanilla character's mouth window, so the engine
    paints its blink/talk overlay at the old face's coordinates -- over ours. It does not fail
    the build, it does not fail a scenario, and on a face whose mouth happens to sit near
    vanilla's it is invisible; on the other three ch05 residents it smeared a block of skull
    across the eye sockets and doubled the teeth (Nicolas spotted it, 2026-08-09). The ch02
    chwinga had been shipping the same defect unnoticed.

    Conditioned on the asset actually existing, like dressed_guest_slots: normalizing a slot we
    did NOT dress would misalign the vanilla face still sitting in it.
    """
    slots = set(PORTRAIT_MAP.values()) | set(dressed_guest_slots(campaign))
    if os.path.isfile(os.path.join(_bust_dir(campaign), CH02_CHWINGA_SPRITE_SRC + '.png')):
        slots |= set(CH02_CHWINGA_PORTRAIT_SLOT.values())
    vendor = os.path.join(_bust_dir(campaign), 'vendor')
    slots |= {slot for mug, slot, _rc in CH05_VISIT_FACES.values()
              if os.path.isfile(os.path.join(vendor, mug))}
    slots |= {override['face_slot']
              for override in arena_presentation_config(campaign)['chapters'].values()}
    return sorted(slots)


def inject_portraits(campaign, verbose=True):
    """Overwrite each mapped vanilla portrait slot with our authored bust."""
    bust_dir = _bust_dir(campaign)
    if not os.path.isdir(PORTRAIT_DIR):
        sys.exit('ERROR: decomp portrait dir not found: %s' % PORTRAIT_DIR)

    guests = {u: s for u, s in GUEST_PORTRAIT_MAP.items()
              if s in dressed_guest_slots(campaign)}
    for unit, vanilla in list(PORTRAIT_MAP.items()) + list(guests.items()):
        bust_path = os.path.join(bust_dir, unit + '.png')
        if not os.path.isfile(bust_path):
            sys.exit('ERROR: missing bust for %s: %s' % (unit, bust_path))

        im = Image.open(bust_path)
        portrait_tool._check_indexed(im, bust_path)
        if im.size != (portrait_tool.BUST_W, portrait_tool.BUST_H):
            sys.exit('ERROR: %s is %s, expected %dx%d bust'
                     % (bust_path, im.size, portrait_tool.BUST_W, portrait_tool.BUST_H))

        # Busts are already canonical FE8 facing (screen-left) -- facing is baked
        # at the render stage (ref_to_bust --flip-h, recorded as art.render.flip_h).
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


def patch_portrait_face_data(campaign, verbose=True):
    """Rewrite every dressed portrait slot's FaceData tail for our busts: the mouth/eye
    window coords to our bust framing, so the engine's mouth-window overwrite lands on our
    baked mouth (not one tile off, which doubles it; PORTRAIT_GEOMETRY), and the blink kind
    to PORTRAIT_BLINK, so the engine draws the bust's corners and never an eye frame.

    The slot list MUST be `dressed_portrait_slots` -- every slot we overwrite, not just the
    cast. Missing one is silent: the build is green, the scenario passes, and the face is
    quietly corrupted in-game. Read that function's docstring before narrowing this."""
    slots = dressed_portrait_slots(campaign)
    with open(PORTRAIT_DATA_C, encoding='utf-8') as f:
        lines = f.read().split('\n')
    # FaceData tail: `, 0, xMouth, yMouth, xEyes, yEyes, FACE_BLINK_*`. The `, 0,`
    # constant anchors the four geometry fields uniquely on each entry line.
    tail = re.compile(r'(,\s*0,\s*)\d+,\s*\d+,\s*\d+,\s*\d+(,\s*)FACE_BLINK_\w+')
    n = 0
    for i, line in enumerate(lines):
        if any('portrait_%s_tileset' % s in line for s in slots):
            new = tail.sub(r'\g<1>%s\g<2>%s' % (PORTRAIT_GEOMETRY, PORTRAIT_BLINK), line)
            if new != line:
                lines[i] = new
                n += 1
    if n == 0:
        sys.exit('ERROR: no portrait_data.c entries matched for the FaceData patch')
    with open(PORTRAIT_DATA_C, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    if verbose:
        print('  normalized %d slot entries to mouth/eye (%s), %s'
              % (n, PORTRAIT_GEOMETRY, PORTRAIT_BLINK))
