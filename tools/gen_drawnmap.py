#!/usr/bin/env python3
"""Convert an Icewind Dale regional map into FE8's WM drawn-map format.

The drawn map (WM_SHOWDRAWNMAP -> StartGmapRm, worldmap_rm.c) is one 240x160
screen: a 30x20 TSA over <=640 unique 4bpp tiles decompressed to BG VRAM 0,
with 4 palette rows (5-8; raw TSA entries get +0x5000 so row bits 0-3 map to
5-8).  A fully unique screen needs 600 tiles, so any 240x160 image fits.

Three candidate sources (Nicolas supplies the art; this tool makes it
GBA-true): the book's engraved regional map (page 1 of the maps PDF), the
Gemini Magvel-style repaint, and the purchased hand-drawn ten-towns maps.

Pipeline per source: crop (3:2) -> Lanczos to 240x160 -> erase the source's
own lettering (it never survives the downscale; median filter melts thin
strokes) -> re-letter with a 3x5 micro-caps font -> per-tile 4-row palette
quantization.  Default run writes review PNGs to map-review/; --emit writes
the locked pair (EMIT) into campaigns/.../events/ as preview PNG + the raw
4bpp/tsa/gbapal trio that build_campaign incbins (make LZ-compresses).
"""

import argparse
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REFS = os.path.join(REPO, 'references/References')
PAGE_PDF = os.path.join(
    REFS, 'Ten-Towns-Maps',
    'icewind-dale-rime-of-the-frostmaiden-maps_compress.pdf')
GEMINI_PNG = os.path.join(REFS, 'Ten-Towns-Maps', 'IcewindDaleGemini.png')
HAND_DIR = os.path.join(
    REFS, 'Ten-Towns-Maps', 'Icewind Dale Ten Towns hand drawn maps')

W, H = 240, 160
TILE = 8
PAL_ROWS = 4
COLORS_PER_ROW = 15  # index 0 reserved per row

GEORGIA = '/System/Library/Fonts/Supplemental/Georgia.ttf'

# ---------------------------------------------------------------- micro font
# 3x5 caps for map labels (engraved small-caps look).  1px column spacing.
F = {
    'A': '010 101 111 101 101', 'B': '110 101 110 101 110',
    'C': '011 100 100 100 011', 'D': '110 101 101 101 110',
    'E': '111 100 110 100 111', 'F': '111 100 110 100 100',
    'G': '011 100 101 101 011', 'H': '101 101 111 101 101',
    'I': '111 010 010 010 111', 'J': '001 001 001 101 010',
    'K': '101 101 110 101 101', 'L': '100 100 100 100 111',
    'M': '101 111 111 101 101', 'N': '101 111 111 111 101',
    'O': '010 101 101 101 010', 'P': '110 101 110 100 100',
    'Q': '010 101 101 011 001', 'R': '110 101 110 101 101',
    'S': '011 100 010 001 110', 'T': '111 010 010 010 010',
    'U': '101 101 101 101 011', 'V': '101 101 101 101 010',
    'W': '101 101 111 111 101', 'X': '101 101 010 101 101',
    'Y': '101 101 010 010 010', 'Z': '111 001 010 100 111',
    '-': '000 000 111 000 000', "'": '010 010 000 000 000',
    ' ': '000 000 000 000 000', '.': '000 000 000 000 010',
}


def micro_text(draw, x, y, text, fill, halo=None):
    if halo is not None:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx or dy:
                    micro_text(draw, x + dx, y + dy, text, halo)
        # spaces have no glyph pixels and therefore no halo; fill their cells
        # so dark terrain can't show through as a fake dash
        for i, ch in enumerate(text):
            if ch == ' ':
                cx = x + i * 4
                draw.rectangle((cx - 1, y, cx + 2, y + 4), fill=halo)
    cx = x
    for ch in text.upper():
        rows = F.get(ch, F[' ']).split()
        for ry, row in enumerate(rows):
            for rx, bit in enumerate(row):
                if bit == '1':
                    draw.point((cx + rx, y + ry), fill=fill)
        cx += 4


def micro_width(text):
    return len(text) * 4 - 1


TOWNS = ['Bremen', 'Targos', 'Termalaine', 'Lonelywood', 'Bryn Shander',
         'Caer-Konig', 'Caer-Dineval', 'Easthaven', 'Good Mead',
         "Dougan's Hole"]
LAKES = ['Maer Dualdon', 'Lac Dinneshere', 'Redwaters']

# ============================================================ source: book
# Coordinates on the 200dpi page-1 render (4000x2810), eyeballed from crops
# and iterated against draft renders.
BOOK_POINTS = {
    'Bremen':        (1112, 1435),
    'Targos':        (1184, 1499),
    'Termalaine':    (1477, 1291),
    'Lonelywood':    (1445, 1216),
    'Bryn Shander':  (1309, 1592),
    'Caer-Konig':    (1883, 1293),
    'Caer-Dineval':  (1947, 1421),
    'Easthaven':     (1885, 1629),
    'Good Mead':     (1536, 1741),
    "Dougan's Hole": (1400, 1840),
    "Kelvin's Cairn": (1867, 1080),
    'Maer Dualdon':  (1290, 1360),
    'Lac Dinneshere': (2050, 1530),
    'Redwaters':     (1660, 1885),
    'Sea of Moving Ice': (735, 768),
    'Reghed Glacier': (3590, 520),
    'Spine of the World': (2250, 1760),
    'Ten-Towns':     (955, 1680),
}

# Original lettering survives the downscale as half-readable smudges that
# fight our crisp relabels; median-filter those areas before resizing (thin
# dark strokes on light ground melt away, terrain mostly survives).
BOOK_GHOSTS = [
    (980, 1380, 1240, 1450),    # Bremen
    (1080, 1480, 1330, 1560),   # Targos
    (1290, 1290, 1560, 1360),   # Termalaine
    (1290, 1190, 1560, 1260),   # Lonelywood
    (1160, 1460, 1440, 1630),   # Bryn Shander (2 lines)
    (1840, 1230, 2110, 1300),   # Caer-Konig
    (1740, 1390, 2010, 1460),   # Caer-Dineval
    (1750, 1570, 2010, 1645),   # Easthaven
    (1410, 1690, 1680, 1760),   # Good Mead
    (1230, 1760, 1560, 1910),   # Dougan's Hole (2 lines)
    (1690, 1030, 2060, 1110),   # Kelvin's Cairn
    (1180, 1240, 1440, 1400),   # Maer Dualdon (2 lines, italic)
    (1880, 1380, 2120, 1650),   # Lac Dinneshere (rotated)
    (1480, 1780, 1740, 1880),   # Redwaters (curved)
    (1820, 1620, 2120, 1700),   # The Eastway
    (1810, 1110, 1990, 1330),   # Dwarven Valley (rotated)
]
# Big display lettering: thick strokes need a heavier median.
BOOK_GHOSTS_BOLD = [
    (650, 1600, 1240, 1740),    # Ten-Towns
    (560, 1480, 1100, 1620),    # Shaengarne River
    (150, 80, 1000, 220),       # Icewind Dale title
    (450, 650, 1050, 880),      # Sea of Moving Ice (curved)
    (3320, 150, 3870, 650),     # Reghed Glacier (rotated)
    (2030, 2270, 2900, 2440),   # Spine of the World (curved)
]

BOOK_CROP_FULL = (60, 95, 3940, 2682)      # page minus border, 1.5 AR
BOOK_CROP_TOWNS = (900, 1000, 2400, 2000)  # ten-towns + three lakes, 1.5 AR

# ========================================================== source: gemini
# Gemini repaint of gemini-input-fulldale.png (2048x1366 resize of
# BOOK_CROP_FULL), output 1224x864 -- so book page coords map by affine.
GEM_W, GEM_H = 1224, 864


def book_to_gemini(pt):
    x0, y0, x1, y1 = BOOK_CROP_FULL
    return (round((pt[0] - x0) * GEM_W / (x1 - x0)),
            round((pt[1] - y0) * GEM_H / (y1 - y0)))


GEMINI_POINTS = {k: book_to_gemini(v) for k, v in BOOK_POINTS.items()}

# Gemini redrew the town/lake lettering cleanly but it still melts at the
# downscale, so it gets the same erase + re-letter treatment.  Rects placed
# relative to the affine dot positions, verified against marked renders.
GEMINI_GHOSTS = [
    (290, 430, 340, 448),   # Bremen (label left-above dot)
    (313, 460, 365, 480),   # Targos
    (438, 396, 522, 440),   # Termalaine (Gemini put it below the dot)
    (438, 356, 527, 376),   # Lonelywood
    (390, 462, 498, 492),   # Bryn Shander (right-above its dot)
    (430, 482, 514, 510),   # The Eastway (along the road)
    (538, 380, 627, 402),   # Caer-Konig
    (528, 426, 612, 448),   # Caer-Dineval
    (570, 400, 668, 480),   # Lac Dinneshere (slanted along NE shore)
    (578, 503, 662, 525),   # Easthaven
    (398, 518, 498, 566),   # Good Mead
    (373, 558, 452, 597),   # Dougan's Hole (2 lines)
    (453, 568, 542, 594),   # Redwaters (italic)
    (353, 393, 442, 442),   # Maer Dualdon (2 lines, in-lake)
    (175, 446, 312, 492),   # Shaengarne River
    (260, 593, 342, 642),   # rotated trail label, bottom-left
    (488, 388, 542, 458),   # Dwarven Valley (rotated)
    (528, 312, 638, 344),   # Kelvin's Cairn
]

GEMINI_CROP_FULL = (0, 24, 1224, 840)    # trim to 1.5 AR
GEMINI_CROP_TOWNS = (250, 330, 700, 630)  # towns cluster, 1.5 AR

# ============================================================ source: hand
# Purchased hand-drawn ten-towns maps (3300x2100).  Town dots machine-
# detected (connected components), Lonelywood/Easthaven located manually.
HAND_POINTS = {
    'Bremen':        (934, 1046),
    'Targos':        (1028, 1156),
    'Termalaine':    (1519, 805),
    'Lonelywood':    (1372, 690),
    'Bryn Shander':  (1239, 1304),
    'Caer-Konig':    (2401, 832),
    'Caer-Dineval':  (2222, 1073),
    'Easthaven':     (2155, 1445),
    'Good Mead':     (1674, 1605),
    "Dougan's Hole": (1418, 1724),
    "Kelvin's Cairn": (2530, 430),
    'Maer Dualdon':  (1250, 950),
    'Lac Dinneshere': (2330, 1250),
    'Redwaters':     (1850, 1815),
}

HAND_GHOSTS = [
    (1390, 655, 1690, 730),    # Lonelywood
    (1540, 775, 1830, 835),    # Termalaine
    (2280, 745, 2640, 815),    # Caer-Konig
    (950, 985, 1170, 1045),    # Bremen
    (1900, 995, 2380, 1065),   # Caer-Dineval
    (935, 1185, 1135, 1250),   # Targos
    (1150, 1230, 1565, 1315),  # Bryn Shander
    (2185, 1415, 2450, 1475),  # Easthaven
    (1690, 1540, 1905, 1600),  # Good Mead
    (1285, 1615, 1565, 1685),  # Dougan's Hole
    (1880, 1695, 2130, 1765),  # Redwaters
    (1230, 860, 1520, 1000),   # Maer Dualdon (italic, in-lake)
    (2180, 1170, 2540, 1300),  # Lac Dinneshere (slanted)
    (1450, 1370, 1710, 1435),  # The Eastway
    (300, 1230, 720, 1310),    # Shaengarne River
    (2280, 330, 2690, 470),    # Kelvin's Cairn
]
# The hand-script title survives the downscale only as a half-readable
# smudge (Nicolas: hard to read) -- erase it and re-letter in Georgia like
# the gemini-full draft.  The compass rose is kept.
HAND_GHOSTS_BOLD = [
    (230, 380, 1160, 730),   # TEN-TOWNS / of Icewind Dale title (2 lines)
    (230, 40, 640, 140),     # Sea of Moving Ice script, top-left inlet
]

HAND_CROP = (220, 30, 3300, 2083)  # 3080x2053, 1.5 AR; keeps the full title

# Icy duotone for the clean (white-paper) hand-drawn map: paper -> pale ice,
# ink -> dark navy.
ICE_DUO = [(0.0, (24, 30, 56)), (0.55, (130, 152, 178)),
           (1.0, (236, 242, 248))]

# -------------------------------------------------- label layout per draft
# (dx, dy) places the label's top-left relative to the town dot.
OFFSETS_BOOK_TOWNS = {
    'Bremen':        (-26, -3),
    'Targos':        (-25, 2),
    'Termalaine':    (3, -2),
    'Lonelywood':    (-12, -8),
    'Bryn Shander':  (3, 1),
    'Caer-Konig':    (-9, -8),
    'Caer-Dineval':  (3, -2),
    'Easthaven':     (3, 2),
    'Good Mead':     (-8, 4),
    "Dougan's Hole": (-30, 3),
}
OFFSETS_GEMINI_TOWNS = {
    'Bremen':        (-26, -2),
    'Targos':        (-25, 1),
    'Termalaine':    (3, 1),
    'Lonelywood':    (3, -5),
    'Bryn Shander':  (4, 0),
    'Caer-Konig':    (3, -2),
    'Caer-Dineval':  (3, -2),
    'Easthaven':     (4, 0),
    'Good Mead':     (4, 1),
    "Dougan's Hole": (-30, 3),
}
OFFSETS_HAND = {
    'Bremen':        (-26, -2),
    'Targos':        (-25, 1),
    'Termalaine':    (3, 0),
    'Lonelywood':    (3, -6),
    'Bryn Shander':  (4, -1),
    'Caer-Konig':    (3, -2),
    'Caer-Dineval':  (3, -2),
    'Easthaven':     (4, 0),
    'Good Mead':     (4, -2),
    "Dougan's Hole": (-44, -3),
}


def page_render(dpi=200):
    out = '/tmp/wm43/regional-1.png'
    if not os.path.exists(out):
        os.makedirs('/tmp/wm43', exist_ok=True)
        os.system(f'pdftoppm -r {dpi} -f 1 -l 1 -png "{PAGE_PDF}" /tmp/wm43/regional')
    return Image.open(out).convert('RGB')


def erase_ghosts(im, rects, size=13):
    out = im.copy()
    for x0, y0, x1, y1 in rects:
        region = im.crop((x0, y0, x1, y1)).filter(ImageFilter.MedianFilter(size))
        out.paste(region, (x0, y0))
    return out


# ------------------------------------------------------------------- tones
# Parchment gradient stops, dark ink -> aged gold -> cream highlight.  (A
# straight gradient-map through Pal_EventGmap fails: the vanilla rows mix
# sea-greens with parchment golds, so luminance-sorting them zebra-stripes.)
PARCHMENT = [(0.0, (40, 26, 12)), (0.35, (124, 92, 42)),
             (0.7, (196, 164, 96)), (1.0, (238, 222, 170))]


def gradient_lut(stops):
    lut = np.zeros((256, 3), dtype=np.uint8)
    for i in range(256):
        f = i / 255
        for (f0, c0), (f1, c1) in zip(stops, stops[1:]):
            if f0 <= f <= f1:
                t = (f - f0) / (f1 - f0)
                lut[i] = [round(c0[c] * (1 - t) + c1[c] * t) for c in range(3)]
                break
    return lut


def gradient_map(im, stops):
    g = np.asarray(im.convert('L'))
    return Image.fromarray(gradient_lut(stops)[g])


# ------------------------------------------------------------- GBA quantize
def _tile_palettes(im):
    """Assign each 8x8 tile one of 4 palette rows (k-means on tile mean/std
    color) and quantize each row to 15 colors (index 0 stays reserved).
    Returns (labels[600], palettes[4][15] RGB, indices[600][8][8] in 1..15)."""
    a = np.asarray(im, dtype=np.float32)
    th, tw = H // TILE, W // TILE
    tiles = a.reshape(th, TILE, tw, TILE, 3).transpose(0, 2, 1, 3, 4)
    feat = np.concatenate([
        tiles.mean(axis=(2, 3)), tiles.std(axis=(2, 3))], axis=2
    ).reshape(-1, 6)

    rng = np.random.default_rng(43)
    centers = feat[rng.choice(len(feat), PAL_ROWS, replace=False)]
    for _ in range(20):
        d = ((feat[:, None] - centers[None]) ** 2).sum(axis=2)
        lab = d.argmin(axis=1)
        for k in range(PAL_ROWS):
            if (lab == k).any():
                centers[k] = feat[lab == k].mean(axis=0)

    flat = tiles.reshape(-1, TILE, TILE, 3)
    palettes = [[(0, 0, 0)] * COLORS_PER_ROW for _ in range(PAL_ROWS)]
    indices = np.ones((th * tw, TILE, TILE), dtype=np.uint8)
    for k in range(PAL_ROWS):
        idx = np.where(lab == k)[0]
        if not len(idx):
            continue
        strip = Image.fromarray(
            flat[idx].reshape(-1, TILE, 3).astype(np.uint8))
        q = strip.quantize(colors=COLORS_PER_ROW, method=Image.MEDIANCUT,
                           dither=Image.NONE)
        pal = q.getpalette()[:COLORS_PER_ROW * 3]
        palettes[k] = [tuple(pal[c * 3:c * 3 + 3]) for c in range(COLORS_PER_ROW)]
        qi = np.asarray(q, dtype=np.uint8).reshape(len(idx), TILE, TILE)
        indices[idx] = qi + 1  # shift past the reserved index 0
    return lab, palettes, indices


def gba_quantize(im):
    """Render the image exactly as the GBA will show it."""
    lab, palettes, indices = _tile_palettes(im)
    tw = W // TILE
    out = np.zeros((H, W, 3), dtype=np.uint8)
    for t in range(len(lab)):
        ty, tx = divmod(t, tw)
        rgb = np.array([(0, 0, 0)] + palettes[lab[t]], dtype=np.uint8)
        out[ty * TILE:(ty + 1) * TILE,
            tx * TILE:(tx + 1) * TILE] = rgb[indices[t]]
    return Image.fromarray(out)


def gba_binaries(im):
    """Emit the drawn-map ROM trio: raw 4bpp tile data (make LZ-compresses
    it), the TSA (header bytes w-1,h-1 then row-major u16 entries of
    palrow<<12|tile; FillTileRect's +0x5000 base lifts rows to 5-8), and the
    4-row GBA palette (index 0 black, as vanilla's blend backdrop).

    Tile 0 must be fully transparent (all index 0): during the blocking
    display GmapRm_80C2320 parks BG1 at priority 3 behind a BG2 cleared to
    tile 0, so the map only shows through if tile 0 renders transparent --
    vanilla's Img_EventGmap leads with a blank tile for exactly this.

    TSA rows are stored bottom-up: TmApplyTsa (asm/arm.s) starts its dest at
    tilemap row `height` and walks upward, so source row 0 lands at the
    bottom of the screen."""
    lab, palettes, indices = _tile_palettes(im)
    tiles, tile_index = bytearray(32), {}
    entries = []
    for t in range(len(lab)):
        data = bytearray()
        for y in range(TILE):
            for x in range(0, TILE, 2):
                data.append(indices[t][y][x] | (indices[t][y][x + 1] << 4))
        key = (bytes(data), int(lab[t]))
        if key not in tile_index:
            tile_index[key] = len(tiles) // 32
            tiles += data
        entries.append((int(lab[t]) << 12) | tile_index[key])
    assert len(tiles) // 32 <= 640, 'tile budget: %d > 640' % (len(tiles) // 32)

    tw, th = W // TILE, H // TILE
    tsa = bytes((tw - 1, th - 1))
    for ty in reversed(range(th)):
        for e in entries[ty * tw:(ty + 1) * tw]:
            tsa += bytes((e & 0xFF, e >> 8))

    pal = bytearray()
    for row in palettes:
        for r, g, b in [(0, 0, 0)] + row:
            v = (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)
            pal += bytes((v & 0xFF, v >> 8))
    return bytes(tiles), tsa, bytes(pal)


# ------------------------------------------------------------------ drafts
def scale_pt(pt, crop):
    x0, y0, x1, y1 = crop
    return (round((pt[0] - x0) / (x1 - x0) * W),
            round((pt[1] - y0) / (y1 - y0) * H))


def centered(name, x, y):
    """Center-anchor a micro label, clamped to the screen."""
    lx = min(max(x - micro_width(name) // 2, 1), W - micro_width(name) - 1)
    return lx, min(max(y - 2, 1), H - 6)


def letter_towns(im, crop, points, offsets, ink, halo):
    d = ImageDraw.Draw(im)
    for name in TOWNS:
        x, y = scale_pt(points[name], crop)
        dx, dy = offsets[name]
        d.rectangle((x - 1, y - 1, x, y), fill=halo)
        d.point((x, y), fill=ink)
        micro_text(d, x + dx, y + dy, name, ink, halo)
    for name in LAKES + ["Kelvin's Cairn"]:
        x, y = scale_pt(points[name], crop)
        micro_text(d, *centered(name, x, y), name, ink, halo)
    return im


def letter_regions(im, crop, points, ink, halo):
    d = ImageDraw.Draw(im)
    # placed for the WM tour viewport: the gold frame eats the top ~10 rows
    # and the text window covers everything below ~110
    title = ImageFont.truetype(GEORGIA, 13)
    d.text((9, 12), 'Icewind Dale', font=title, fill=ink,
           stroke_width=2, stroke_fill=halo)
    for name in ['Sea of Moving Ice', 'Reghed Glacier',
                 'Spine of the World', 'Ten-Towns']:
        if name in points:
            x, y = scale_pt(points[name], crop)
            micro_text(d, *centered(name, x, y), name, ink, halo)
    return im


INK_ICY, HALO_ICY = (24, 28, 48), (238, 242, 246)
INK_SEPIA, HALO_SEPIA = (43, 22, 8), (235, 222, 168)


def downscale(im, crop):
    return im.crop(crop).resize((W, H), Image.LANCZOS)


def draft_book(towns_crop, tone):
    page = erase_ghosts(erase_ghosts(page_render(), BOOK_GHOSTS),
                        BOOK_GHOSTS_BOLD, 31)
    crop = BOOK_CROP_TOWNS if towns_crop else BOOK_CROP_FULL
    im = downscale(page, crop)
    ink, halo = (INK_SEPIA, HALO_SEPIA) if tone == 'sepia' else (INK_ICY, HALO_ICY)
    if tone == 'sepia':
        im = gradient_map(im, PARCHMENT)
    if towns_crop:
        return letter_towns(im, crop, BOOK_POINTS, OFFSETS_BOOK_TOWNS, ink, halo)
    return letter_regions(im, crop, BOOK_POINTS, ink, halo)


def draft_gemini(towns_crop):
    src = erase_ghosts(Image.open(GEMINI_PNG).convert('RGB'), GEMINI_GHOSTS, 9)
    if towns_crop:
        im = downscale(src, GEMINI_CROP_TOWNS)
        return letter_towns(im, GEMINI_CROP_TOWNS, GEMINI_POINTS,
                            OFFSETS_GEMINI_TOWNS, INK_ICY, HALO_ICY)
    im = downscale(src, GEMINI_CROP_FULL)
    return letter_regions(im, GEMINI_CROP_FULL, GEMINI_POINTS,
                          INK_ICY, HALO_ICY)


def draft_hand(variant):
    name = f'ten towns hand drawn_{variant}.png'
    src = Image.open(os.path.join(HAND_DIR, name)).convert('RGB')
    src = erase_ghosts(erase_ghosts(src, HAND_GHOSTS), HAND_GHOSTS_BOLD, 31)
    im = downscale(src, HAND_CROP)
    if variant == 'no weathering':
        im = gradient_map(im, ICE_DUO)
        ink, halo = INK_ICY, HALO_ICY
    else:
        ink, halo = INK_SEPIA, HALO_SEPIA
    im = letter_towns(im, HAND_CROP, HAND_POINTS, OFFSETS_HAND, ink, halo)
    # No "of Icewind Dale" subtitle: the establishing shot (gemini-full)
    # already says where we are.
    # the tour shows this map scrolled to y=24 (y=48 for the Redwaters card);
    # row 34 puts the title just below the WM frame at the resting scroll
    d = ImageDraw.Draw(im)
    d.text((6, 34), 'Ten-Towns', font=ImageFont.truetype(GEORGIA, 13),
           fill=ink, stroke_width=2, stroke_fill=halo)
    return im


# The locked #43 tour pair (Nicolas, 2026-06-10): gemini full dale as the
# establishing shot, hand-drawn icy close-up for the town cards.  --emit
# writes them as campaign assets: a 1x preview PNG (the review artifact) plus
# the ROM trio that build_campaign incbins (A = dale, B = towns).
EMIT = {
    'tour-map-a-dale':  lambda: draft_gemini(False),
    'tour-map-b-towns': lambda: draft_hand('no weathering'),
}
EVENTS_DIR = os.path.join(REPO, 'campaigns', 'rime-of-the-frostmaiden', 'events')


def emit_final():
    for name, build in EMIT.items():
        im = build()
        img, tsa, pal = gba_binaries(im)
        base = os.path.join(EVENTS_DIR, name)
        gba_quantize(im).save(base + '.png')
        for ext, data in (('.4bpp', img), ('.tsa', tsa), ('.gbapal', pal)):
            with open(base + ext, 'wb') as f:
                f.write(data)
        print('%s: %d tiles, %d bytes 4bpp' % (name, len(img) // 32, len(img)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(REPO, 'map-review/43-tour-map'))
    ap.add_argument('--only', help='comma list of draft keys to regenerate')
    ap.add_argument('--emit', action='store_true',
                    help='write the locked pair as campaign assets')
    args = ap.parse_args()
    if args.emit:
        emit_final()
        return
    os.makedirs(args.out, exist_ok=True)

    builders = {
        'B-book-towns-icy':   lambda: draft_book(True, 'icy'),
        'E-gemini-full':      lambda: draft_gemini(False),
        'F-gemini-towns':     lambda: draft_gemini(True),
        'G-hand-weathered':   lambda: draft_hand('weathered'),
        'H-hand-clean-icy':   lambda: draft_hand('no weathering'),
    }
    keys = args.only.split(',') if args.only else list(builders)
    drafts = {k: gba_quantize(builders[k]()) for k in keys}

    for name, im in drafts.items():
        im.save(os.path.join(args.out, f'43-tour-{name}-1x.png'))
        im.resize((W * 3, H * 3), Image.NEAREST).save(
            os.path.join(args.out, f'43-tour-{name}-3x.png'))

    if not args.only:
        cols = 2
        rows = (len(drafts) + cols - 1) // cols
        sheet = Image.new('RGB', (W * 3 * cols + 8 * (cols + 1),
                                  (H * 3 + 8) * rows + 8), (20, 20, 20))
        for i, (name, im) in enumerate(drafts.items()):
            x = (i % cols) * (W * 3 + 8) + 8
            y = (i // cols) * (H * 3 + 8) + 8
            sheet.paste(im.resize((W * 3, H * 3), Image.NEAREST), (x, y))
        sheet.save(os.path.join(args.out, '43-tour-contact-sheet.png'))
    print('wrote', args.out, ':', ', '.join(drafts))


if __name__ == '__main__':
    main()
