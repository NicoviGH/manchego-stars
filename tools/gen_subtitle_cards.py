#!/usr/bin/env python3
"""Render the #43 lore-crawl cards (240x160 indexed PNGs) in the vanilla style.

FE8's "long ago..." opening monologue is seven prerendered 4bpp slides
(graphics/op_subtitle/OpSubtitle_00..06.png), not message text -- the proc in
fireemblem8u/src/opsubtitle.c walks exactly seven gOpSubtitleGfxLut entries
with hardcoded transitions (plain fades for 0-1, the flare reveal for 2,
cross-blends for 3-4, the palette-scroll close for 5-6). Our crawl was locked
at seven cards to ride that structure unmodified; this tool re-renders the
seven slides from the campaign YAML.

Style is matched to the vanilla cards, measured off the shipped PNGs: slate
background (palette index 0), cream text quantized into the vanilla 16-color
ramp (the warm antialiasing browns come from the quantization), 24px line
pitch, text block centered on (120, 80), <= 214px line width. Letterforms are
Georgia 13px with +1px tracking -- side-by-side closest to vanilla's serif
(see the 2026-06-10 decisions.md entry).

Usage: gen_subtitle_cards.py <montage.yaml> <out_dir> [preview.png]
(out_dir gets OpSubtitle_00.png .. OpSubtitle_06.png; the optional preview is
a 2x contact sheet of all seven cards for eyeballing.)
"""
import os
import sys

import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OP_SUBTITLE_DIR = os.path.join(REPO, 'fireemblem8u', 'graphics', 'op_subtitle')

FONT_PATH = '/System/Library/Fonts/Supplemental/Georgia.ttf'
FONT_SIZE = 13
TRACKING = 1          # vanilla letter-spacing is airier than Georgia's default
LINE_PITCH = 24       # vanilla line starts: y=27,51,75,99,123
MAX_LINE_W = 220      # vanilla's densest card draws cols 10-229 on the 240px slide
MAX_LINES = 5         # vanilla card 0/4 shape; more would crowd the fades
CENTER = (120, 80)    # vanilla text blocks center on x=120, y~80
BG_RGB = (80, 96, 112)
FG_RGB = (248, 248, 240)
CARD_COUNT = 7        # gOpSubtitleGfxLut is walked with hardcoded thresholds
MURAL_BRIGHTNESS = 0.75  # mural darkness so the cream text stays readable

_pal = None


def _vanilla_palette():
    """16-color palette of the vanilla cards (read pre-overwrite: the build
    git-restores graphics/op_subtitle before this tool runs)."""
    global _pal
    if _pal is None:
        im = Image.open(os.path.join(OP_SUBTITLE_DIR, 'OpSubtitle_00.png'))
        _pal = im.getpalette()[:48]
    return _pal


def _draw_tracked(draw, xy, text, font, fill):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + TRACKING


def _tracked_width(draw, text, font):
    return sum(draw.textlength(ch, font=font) + TRACKING for ch in text) - TRACKING


def _wrap(draw, text, font):
    words = text.split()
    lines, cur = [], []
    for w in words:
        cand = ' '.join(cur + [w])
        if cur and _tracked_width(draw, cand, font) > MAX_LINE_W:
            lines.append(' '.join(cur))
            cur = [w]
        else:
            cur.append(w)
    if cur:
        lines.append(' '.join(cur))
    return lines


def compose_card(text):
    """Render one card's prose as a 240x160 P-mode Image, vanilla-style."""
    font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    im = Image.new('RGB', (240, 160), BG_RGB)
    draw = ImageDraw.Draw(im)
    text = text.replace("'", '’')  # typographic apostrophe, vanilla-style
    lines = _wrap(draw, ' '.join(text.split()), font)
    if len(lines) > MAX_LINES:
        sys.exit('ERROR: card wraps to %d lines (max %d): %r'
                 % (len(lines), MAX_LINES, text))
    top = CENTER[1] - (len(lines) * LINE_PITCH) // 2 + 4
    for i, line in enumerate(lines):
        w = _tracked_width(draw, line, font)
        if w > MAX_LINE_W:  # a single word overflowed the wrap
            sys.exit('ERROR: line %r is %dpx (max %d)' % (line, w, MAX_LINE_W))
        _draw_tracked(draw, (round(CENTER[0] - w / 2), top + i * LINE_PITCH),
                      line, font, FG_RGB)
    pal = _vanilla_palette()
    pal_rgb = np.array(pal, dtype=np.int32).reshape(16, 3)
    a = np.array(im, dtype=np.int32)
    q = ((a[:, :, None, :] - pal_rgb[None, None, :, :]) ** 2).sum(-1)
    out = Image.fromarray(q.argmin(-1).astype(np.uint8))
    out.putpalette(pal)
    return out


def compose_mural(src_png):
    """Render the crawl's backdrop mural (256x160 P-mode) from the campaign's
    source painting. Replaces vanilla's shared rune wall (Img_CommGameBgScreen)
    via opsubtitle-local symbols -- shops/chapter-intro/endings keep theirs.
    The engine draws it as 640 sequential 4bpp tiles on palette row 15
    (opsubtitle.c sub_80C48F0), faded in to its real palette during the flare
    slide; tile color 0 is GBA-transparent (black backdrop), so all art pixels
    are kept off index 0 and palette[0] is black."""
    im = Image.open(src_png).convert('RGB').resize((256, 160), Image.LANCZOS)
    im = ImageEnhance.Brightness(im).enhance(MURAL_BRIGHTNESS)
    q = im.quantize(colors=15)
    pal = q.getpalette()[:45]
    out = q.point(lambda i: i + 1)
    out.putpalette([0, 0, 0] + pal)
    return out


def mural_gbapal(mural):
    """The mural's 16 colors as GBA BGR555 palette bytes (for the .gbapal incbin)."""
    pal = mural.getpalette()[:48]
    data = bytearray()
    for i in range(16):
        r, g, b = (c >> 3 for c in pal[3 * i:3 * i + 3])
        v = r | (g << 5) | (b << 10)
        data += bytes((v & 0xFF, v >> 8))
    return bytes(data)


def crawl_cards(montage_yaml):
    """The locked lore-crawl card texts, validated to the engine's slot count."""
    with open(montage_yaml, encoding='utf-8') as f:
        montage = yaml.safe_load(f)
    cards = montage['lore_crawl']['cards']
    if len(cards) != CARD_COUNT:
        sys.exit('ERROR: lore_crawl has %d cards; opsubtitle.c walks exactly %d'
                 % (len(cards), CARD_COUNT))
    return cards


def card_timer(text):
    """Display frames for a card, vanilla-paced (vanilla LUT runs 250-335
    frames for 6-33 words; START always skips)."""
    words = len(text.split())
    return min(360, max(240, 120 + 8 * words))


def main():
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    cards = crawl_cards(sys.argv[1])
    out_dir = sys.argv[2]
    sheets = []
    for i, text in enumerate(cards):
        im = compose_card(text)
        path = os.path.join(out_dir, 'OpSubtitle_%02d.png' % i)
        im.save(path)
        sheets.append(im.convert('RGB'))
        print('wrote %s (%d frames: %r...)'
              % (path, card_timer(text), ' '.join(text.split())[:40]))
    if len(sys.argv) == 4:
        sheet = Image.new('RGB', (2 * 488 - 8, 4 * 328 - 8), (16, 16, 16))
        for i, im in enumerate(sheets):
            sheet.paste(im.resize((480, 320), Image.NEAREST),
                        ((i % 2) * 488, (i // 2) * 328))
        sheet.save(sys.argv[3])
        print('wrote %s' % sys.argv[3])


if __name__ == '__main__':
    main()
