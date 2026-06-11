#!/usr/bin/env python3
"""Compose an FE8 chapter-title card (256x16 indexed PNG) from vanilla glyphs.

FE8 chapter titles are 4bpp images (graphics/chap_title/chap_title_<n>.png),
not text -- the intro banner decompresses chap_title_data[chapTitleId] (see
fireemblem8u/src/chapter_title.c). To title a custom chapter we rebuild the
image in the vanilla letterforms by cutting glyphs out of the vanilla title
cards and re-composing them, so palette indices, outline, and drop shadow all
match the runtime palette exactly.

The atlas below only covers glyphs verified by eye so far (cut columns read
off ASCII pixel dumps of the source words). Extend it per new chapter title;
unknown glyphs are a hard error, never a silent fallback.

Usage: gen_chapter_title.py "Prologue: A Dagger of Ice" out.png [preview4x.png]
"""
import os
import sys

import numpy as np
from PIL import Image

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHAP_TITLE_DIR = os.path.join(REPO, 'fireemblem8u', 'graphics', 'chap_title')

# Whole words cut intact from vanilla cards (pixel-perfect, shadows included).
# (source image index, x0, x1) -- end-exclusive columns in the 256x16 source.
WORDS = {
    'Prologue:': (0, 16, 69),   # "Prologue: The Fall of Renais"
    'of':        (0, 125, 138),
    'Ch.1:':     (1, 57, 91),   # "Ch.1: Escape!" -- vanilla's own chapter prefix
    'The':       (0, 74, 96),
}

# Single letters. Sources: img0 "Prologue: The Fall of Renais",
# img1 "Ch.1: Escape!", img4 "Ch.4: Ancient Horrors",
# img9 "Ch.7: It's a Trap!" (lone 'a' word), img10 "Ch.8: Distant Blade".
LETTERS = {
    'A': (4, 71, 80),
    'D': (10, 78, 87),
    'I': (9, 87, 93),
    'T': (9, 119, 128),         # "Trap!"
    'a': (9, 110, 117),
    'c': (4, 88, 93),
    'e': (0, 58, 64),
    'g': (0, 44, 52),
    'i': (0, 168, 172),         # "Renais"
    'l': (0, 35, 39),           # "Prologue" (second ascender)
    'n': (0, 155, 161),         # "Renais"
    'o': (0, 29, 34),           # "Prologue" (first o; 34 starts the l ascender)
    'r': (0, 23, 29),
}

# Pixels inside a glyph's cut that belong to a kerned neighbor in the source
# word: char -> list of (row_slice, col_slice) to zero out.
SCRUBS = {
    'r': [(slice(0, 4), slice(0, 2)), (slice(4, 5), slice(0, 1))],  # P's shadow
}

# Vanilla cards center their drawn extent on x ~= 99, not 128 (measured on
# imgs 0/4/9/10: centers 97.5-100).
CENTER_X = 99
WORD_GAP = 4        # blank columns between words...
COLON_GAP = 5       # ...but 5 after a "Prologue:"-style prefix (matches img0)

_cache = {}


def _load(idx):
    if idx not in _cache:
        im = Image.open(os.path.join(CHAP_TITLE_DIR, 'chap_title_%d.png' % idx))
        _cache[idx] = (np.array(im), im.getpalette())
    return _cache[idx]


def _piece(word):
    """Pixel array for one word: an intact vanilla word, or letters butted
    together with no gap (vanilla letter cuts already include their advance)."""
    if word in WORDS:
        idx, x0, x1 = WORDS[word]
        return _load(idx)[0][:, x0:x1].copy()
    cols = []
    for ch in word:
        if ch not in LETTERS:
            sys.exit('ERROR: no glyph for %r -- extend the atlas in %s'
                     % (ch, os.path.basename(__file__)))
        idx, x0, x1 = LETTERS[ch]
        glyph = _load(idx)[0][:, x0:x1].copy()
        for rows, gcols in SCRUBS.get(ch, []):
            glyph[rows, gcols] = 0
        cols.append(glyph)
    return np.concatenate(cols, axis=1)


def compose_title(text):
    """Render `text` as a 256x16 P-mode Image in the vanilla title style."""
    pieces = [_piece(w) for w in text.split(' ')]
    gaps = [COLON_GAP if w.endswith(':') else WORD_GAP for w in text.split(' ')]
    total = sum(p.shape[1] for p in pieces) + sum(gaps[:-1])
    if total > 256:
        sys.exit('ERROR: title %r is %d px wide (max 256)' % (text, total))
    out = np.zeros((16, 256), dtype=np.uint8)
    x = max(0, round(CENTER_X - total / 2))
    if x + total > 256:
        x = 256 - total
    for p, gap in zip(pieces, gaps):
        region = out[:, x:x + p.shape[1]]
        mask = p != 0
        region[mask] = p[mask]
        x += p.shape[1] + gap
    im = Image.fromarray(out)
    im.putpalette(_load(0)[1])
    return im


def main():
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    text, out_path = sys.argv[1], sys.argv[2]
    im = compose_title(text)
    im.save(out_path)
    if len(sys.argv) == 4:
        im.convert('RGB').resize((1024, 64), Image.NEAREST).save(sys.argv[3])
    print('wrote %s (%r)' % (out_path, text))


if __name__ == '__main__':
    main()
