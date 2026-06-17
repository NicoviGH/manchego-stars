#!/usr/bin/env python3
"""Regenerate Duvessa Shane's bust from vanilla FE8's Selena portrait.

  python3 campaigns/rime-of-the-frostmaiden/portraits/duvessa.py

Duvessa Shane (Speaker of Bryn Shander) is a recurring cutscene NPC introduced in
the ch01 ending ("The Rolling Cheddar"). Rather than custom art or an FE-Repo mug,
her look is a palette recolor of vanilla Selena's portrait -- Selena's mature, serious
3/4 bust with a fur-trimmed shoulder reads as an earnest young winter official, and
matches her book likeness (Rime printed p.33: dark hair, deep coat, white fur collar).
Base picked by Nicolas 2026-06-17; recolor approved same day (brown hair kept on the
sleeve -- the sleeve shares hair palette indices and a blue remap read poorly).

The transform is mechanical, mirroring guest_vendor_busts.py:
  * decode vanilla portrait_Selena_tileset.png -> 96x80 bust (from the clean submodule
    tree at git HEAD, so it is reproducible even when the working tree holds injected art)
  * recolor by source RGB: pale-blonde hair ramp -> dark brown; teal accent -> deep
    blue (earring); cool whites -> white fur collar. Skin/outline untouched.

Output: 96x80 indexed PNG, <=16 colors, index 0 = the transparent background -- the
bust-pipeline contract consumed by tools/build_campaign.py inject_portraits.
"""
import io
import os
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
DECOMP = os.path.join(REPO, 'fireemblem8u')
sys.path.insert(0, os.path.join(REPO, 'tools'))
import portrait_tool  # noqa: E402

SELENA_SHEET = 'graphics/portrait/portrait_Selena_tileset.png'
SELENA_BG = (164, 205, 156)        # vanilla Selena background green (palette index 0)

# source Selena RGB -> Duvessa RGB
RECOLOR = {
    # pale yellow-green hair ramp -> dark brown
    (255, 255, 189): (156, 106, 64),   # hair highlight
    (230, 230, 139): (126, 82, 48),    # hair light
    (189, 189, 90):  (94, 60, 32),     # hair mid
    (131, 197, 74):  (94, 60, 32),     # green accent -> merge into hair mid
    (123, 123, 90):  (56, 32, 15),     # hair shadow (also the brown sleeve -- kept brown)
    # teal accent (earring) -> deep blue
    (98, 213, 197):  (90, 120, 184),
    (74, 164, 156):  (52, 80, 126),
    # cool whites -> white fur collar
    (246, 255, 255): (240, 240, 240),
    (213, 222, 230): (192, 198, 210),
}


def _vanilla_selena_sheet():
    """The clean (pre-injection) Selena sheet, read from the submodule at git HEAD."""
    raw = subprocess.check_output(
        ['git', '-C', DECOMP, 'show', 'HEAD:' + SELENA_SHEET])
    return Image.open(io.BytesIO(raw))


def main():
    bust = portrait_tool.decode(_vanilla_selena_sheet())   # 96x80 P-mode
    mug = np.array(bust.convert('RGB'))
    for src, dst in RECOLOR.items():
        mug[(mug == src).all(axis=-1)] = dst
    out = os.path.join(HERE, 'duvessa.png')
    portrait_tool  # (kept import explicit)
    from guest_vendor_busts import to_indexed
    to_indexed(Image.fromarray(mug), SELENA_BG).save(out)
    print('-> %s' % out)


if __name__ == '__main__':
    main()
