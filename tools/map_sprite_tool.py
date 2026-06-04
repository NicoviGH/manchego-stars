#!/usr/bin/env python3
"""map_sprite_tool.py -- validate/describe a cast member's overworld (map) sprite.

FE8 overworld sprites ("standing map sprites", SMS) are tiny indexed sheets: a
vertical strip of N idle frames. The decomp stores each as a single indexed PNG
in graphics/unit_icon/wait/ and the build (gbagfx) compresses it to .4bpp.lz; we
only have to hand the build a correctly-laid-out PNG.

Two hard engine constraints shape the art (see HANDOFF / issue #38):

  * One shared palette. Every PLAYER map sprite draws from a single 16-colour OBJ
    palette (the others are the enemy/NPC team tints). So a cast sprite cannot
    carry its own palette -- it must be drawn in the shared cast ramp
    (graphics/unit_icon/palette/unit_icon_pal_player.agbpal). Index 0 = transparent.

  * Fixed frame geometry. Wait sheets are a vertical strip of 16x16 (most classes),
    16x32 (mounted/tall) or 32x32 (monsters) frames. Width fixes the size class;
    height must be an exact multiple of it (the idle animation's frames).

This tool does NOT generate art; it validates that a sheet conforms so the build
won't silently emit garbage, and reports its SMS size class. Injection into the
decomp (table slot + character override) lives in build_campaign.inject_map_sprites,
parallel to portrait injection.
"""

import os
import sys

from PIL import Image

# (sprite width, sprite height) -> decomp UNIT_ICON_SIZE_* macro name.
SMS_SIZES = {
    (16, 16): 'UNIT_ICON_SIZE_16x16',
    (16, 32): 'UNIT_ICON_SIZE_16x32',
    (32, 32): 'UNIT_ICON_SIZE_32x32',
}
MAX_COLORS = 16  # 4bpp: index 0 transparent + 15 usable.


def sheet_info(path):
    """Validate a wait-sheet PNG and return (size_macro, frame_w, frame_h, nframes).

    Exits with a clear error if the sheet won't encode to a valid SMS.
    """
    if not os.path.isfile(path):
        sys.exit('ERROR: map sprite not found: %s' % path)
    im = Image.open(path)
    if im.mode != 'P':
        sys.exit('ERROR: %s is mode %s; map sprites must be indexed (mode P) so they '
                 'share the cast palette' % (path, im.mode))
    ncolors = len(im.getcolors() or range(MAX_COLORS + 1))
    if ncolors > MAX_COLORS:
        sys.exit('ERROR: %s uses %d colours; the 4bpp map-sprite palette allows %d '
                 '(index 0 transparent + 15)' % (path, ncolors, MAX_COLORS))

    w, h = im.size
    # The frame is square (16x16/32x32) or 16x32; width picks the candidate, height
    # must be a whole number of frames of that height.
    for (fw, fh), macro in SMS_SIZES.items():
        if w == fw and h % fh == 0 and h >= fh:
            return macro, fw, fh, h // fh
    sys.exit('ERROR: %s is %dx%d -- not a stack of 16x16/16x32/32x32 frames '
             '(expected width 16 or 32, height an exact multiple of the frame)'
             % (path, w, h))


def main():
    if len(sys.argv) != 2:
        sys.exit('usage: map_sprite_tool.py <wait_sheet.png>')
    macro, fw, fh, n = sheet_info(sys.argv[1])
    print('%s: %s, %d frame(s) of %dx%d' % (sys.argv[1], macro, n, fw, fh))


if __name__ == '__main__':
    main()
