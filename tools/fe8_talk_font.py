#!/usr/bin/env python3
"""FE8's talk font, and the only honest way to measure a line of dialogue.

**The engine never counts characters.** `StartTalkExt` (scene.c:403) sets
`activeWidth = Div(GetStrTalkLen(str, 0) + 7, 8) + 2`, and `GetStrTalkLen` accumulates
`glyph->width` -- a per-glyph PIXEL width (`fontgrp.c` -> `GetStringTextLenASCII`, the path
English text takes). The `/8 + 2` turns pixels into the bubble's tile width plus its border.

So a character count is not a conservative proxy for the real constraint; it is an unrelated
quantity that merely correlates. `i` and `.` are 2px while `W` is 8px, so two 29-character lines
can differ by more than a factor of three. Long form: `docs/decisions.md` -> "We wrapped on-map
talk at 29 CHARACTERS; the engine measures PIXELS".

PROVENANCE. Read out of `TextGlyphs_Talk` in the built ROM -- an array of `struct Glyph *`
indexed by ASCII, with `width` at offset 5 (fontgrp.h: a 4-byte `sjisNext`, then `sjisByte1`,
then `width`). Re-verify with `python3 tools/fe8_talk_font.py --regenerate`, which reads the
address out of `fireemblem8u/fireemblem8.map`. CHECKED IN rather than read during the build,
because the campaign build is what PRODUCES that ROM -- reading it there would be circular.
"""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# width in pixels -> every printable ASCII character drawn at that width
_BY_WIDTH = {
    2: "',.:;`il|",
    3: '![]j',
    4: ' ()-1I_ry{}',
    5: '"L^bcdefhknopqstuz',
    6: '$02356789<=>ABCDEFGHJKNOPRTUVXYZamvwx',
    7: '&/4?QSg~',
    8: '#%*+@MW\\',
}

GLYPH_WIDTH = {ch: w for w, chars in _BY_WIDTH.items() for ch in chars}

# What a character the font has no glyph for costs. Nothing in the campaign should reach this --
# `verify_text` would already have flagged an undecodable byte -- but a silent 0 would make an
# over-wide line measure as narrow, which is the one failure this module exists to prevent.
FALLBACK_PX = 8

# The budget, in pixels, for ONE DRAWN LINE of dialogue.
#
# Taken from what vanilla SHIPS rather than from the geometry, because the geometry has a
# per-podium term (the bubble anchors at `gTalkFaceHPosLut`, clamped to [0,30] tiles) and
# vanilla's own widest lines are the proof that a width is safe from the podiums we use.
# Measured across both channels -- and they AGREE, which is itself the finding, since our old
# character rule had them at 29 and 42:
#
#   on-map TEXTSHOW   MSG_9CC  203px (43 ch)  <- vanilla's Natasha->Joshua Talk, ch05's twin
#                     MSG_9C3  182px (39 ch)
#                     MSG_910  140px (29 ch)  <- the ONE narrow message our 29 was read off
#   full-screen BACG  MSG_9C9  201px (41 ch)
#                     MSG_9BE  193px (42 ch)
#
# The budget IS vanilla's measured maximum in the tighter of the two geometries -- the on-map
# bubble, which carries a 2-tile border and still fits inside a 240px screen at this width.
# Deliberately not rounded DOWN: 200 was tried first purely as "a bit under", and a round number
# nobody measured is exactly the kind of proxy this module exists to replace. One authored ch04
# box overflowed a line by 3px under it, which is the arbitrary margin showing up as content.
TALK_BUDGET_PX = 203

# ...and the two OTHER windows, which are not the talk bubble and do not get its budget.
# "Not every panel is the talk window" is the whole hazard of measuring in pixels: the number
# is only valid for the renderer it was measured on.
#
# THE BATTLE BUBBLE. A quote shown during a battle animation goes through the same
# `PutTalkBubble`, but `IsBattleDeamonActive()` pushes it into case 2/3 (scene.c:1769), which
# HARD-FORCES `width = 20` tiles and `x = 9`/`1` -- the text width is ignored entirely, and text
# draws from `xText = x + 1`. A 203px line from `[OpenMidLeft]` would start at tile 10 and run
# to tile ~36 on a 32-tile tilemap: off the map, wrapping the row. 20 tiles less the 2 border
# tiles is 144px, and vanilla agrees to the pixel -- all 123 of its battle-quote messages cap
# at 143px. Battle quotes, defeat quotes and death quotes all ride this.
BATTLE_QUOTE_BUDGET_PX = 143

# THE OPAQUE AUTO-CENTERED BOX. `SOLOTEXTBOXSTART` (faceless narration, #58) and
# `TUTORIALTEXTBOXSTART` (the lord-select explainer) both land in helpbox.c, whose box width is
# clamped to `0xC0` = 192px (helpbox.c:114, :977, :1436) while the text itself draws unclamped.
SOLO_BOX_BUDGET_PX = 192


def text_px(text):
    """Drawn width of one line, in pixels. Control tags are the caller's problem: this measures
    exactly the characters it is handed."""
    return sum(GLYPH_WIDTH.get(ch, FALLBACK_PX) for ch in text)


def _regenerate():
    import struct
    rom = os.path.join(REPO, 'fireemblem8u', 'fireemblem8.gba')
    mapf = os.path.join(REPO, 'fireemblem8u', 'fireemblem8.map')
    addr = None
    with open(mapf, encoding='utf-8', errors='replace') as fh:
        for line in fh:
            if line.rstrip().endswith(' TextGlyphs_Talk'):
                addr = int(line.split()[0], 16)
                break
    if addr is None:
        sys.exit('ERROR: TextGlyphs_Talk not in the map file -- build the ROM first')
    data = open(rom, 'rb').read()
    out = {}
    for c in range(0x20, 0x7F):
        p = struct.unpack_from('<I', data, addr - 0x08000000 + c * 4)[0]
        if 0x08000000 <= p < 0x0A000000:
            out[chr(c)] = data[p - 0x08000000 + 5]
    diffs = [ch for ch in out if out[ch] != GLYPH_WIDTH.get(ch)]
    if diffs:
        for ch in sorted(diffs):
            print('  {0!r}: {1} -> {2}'.format(ch, GLYPH_WIDTH.get(ch), out[ch]))
        sys.exit('ERROR: the checked-in table no longer matches the ROM')
    print('the checked-in table matches the built ROM ({0} glyphs)'.format(len(out)))


if __name__ == '__main__':
    if '--regenerate' in sys.argv:
        _regenerate()
    else:
        print(__doc__)
