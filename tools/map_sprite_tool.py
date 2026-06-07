#!/usr/bin/env python3
"""map_sprite_tool.py -- validate/describe a cast member's overworld (map) sprite.

FE8 overworld sprites ("standing map sprites", SMS) are tiny indexed sheets: a
vertical strip of N idle frames. The decomp stores each as a single indexed PNG
in graphics/unit_icon/wait/ and the build (gbagfx) compresses it to .4bpp.lz; we
only have to hand the build a correctly-laid-out PNG.

Two hard engine constraints shape the art (see HANDOFF / issue #38):

  * One shared palette per OBJ bank. A map sprite can't carry its own palette; it
    picks one of the resident faction banks. The custom cast share a bespoke 16-colour
    cast palette loaded into their own (campaign-unused) bank, so every cast sheet must
    be drawn in that one ramp -- the cast palette, campaigns/<id>/map_sprites/
    cast_palette.png (decisions.md Art & Audio). Index 0 = transparent.

  * Fixed frame geometry. Wait sheets are a vertical strip of 16x16 (most classes),
    16x32 (mounted/tall) or 32x32 (monsters) frames. Width fixes the size class;
    height must be an exact multiple of it (the idle animation's frames).

This tool does NOT generate art; it validates that a sheet conforms so the build
won't silently emit garbage, and reports its SMS size class. Injection into the
decomp (table slot + character override) lives in build_campaign.inject_map_sprites,
parallel to portrait injection.
"""

import os
import re
import sys

from PIL import Image, ImageDraw

# (sprite width, sprite height) -> decomp UNIT_ICON_SIZE_* macro name.
SMS_SIZES = {
    (16, 16): 'UNIT_ICON_SIZE_16x16',
    (16, 32): 'UNIT_ICON_SIZE_16x32',
    (32, 32): 'UNIT_ICON_SIZE_32x32',
}
MAX_COLORS = 16  # 4bpp: index 0 transparent + 15 usable.
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAIT_DATA_C = os.path.join(REPO, 'fireemblem8u', 'src', 'unit_icon_wait_data.c')
MOVE_GFX_DECOMP = os.path.join(REPO, 'fireemblem8u', 'graphics', 'unit_icon', 'move')

# FE8 MU (moving) sheets are a vertical stack of 32x32 blocks. The class motion
# script shows one block per frame via a single 32x32 OAM at a constant offset (some
# frames H-flip the block). 480/32 = 15 blocks is the common length; see
# data/const_data_unit_icon_move.s (every donor frame_0 we use is `1 oam, 0xE0,
# 0x81F0, tile 0x0` -> the same single 32x32 block).
MU_CELL = 32


def donor_sms_geometry(donor):
    """Authoritative (macro, frame_w, frame_h) for a donor map sprite, READ FROM THE
    DECOMP -- never inferred from PNG pixel dimensions (a 16x96 sheet is ambiguous:
    6x 16x16 vs 3x 16x32, and only the wait table says which). `donor` is the vanilla
    class/monster name = a unit's YAML art.map_sprite.base (e.g. 'Cyclops'), or the path
    to its vanilla sheet. Source of truth: src/unit_icon_wait_data.c, e.g.
    `{3, UNIT_ICON_SIZE_16x32, unit_icon_wait_Cyclops_sheet}`.
    """
    name = os.path.basename(donor)
    m = re.match(r'unit_icon_wait_(.+?)_sheet', name)
    if m:
        name = m.group(1)
    sym = 'unit_icon_wait_%s_sheet' % name
    with open(WAIT_DATA_C, encoding='utf-8') as f:
        for line in f:
            if sym in line:
                mm = re.search(r'UNIT_ICON_SIZE_(\d+)x(\d+)', line)
                if not mm:
                    sys.exit('ERROR: no UNIT_ICON_SIZE on the %s row of %s'
                             % (sym, WAIT_DATA_C))
                fw, fh = int(mm.group(1)), int(mm.group(2))
                return SMS_SIZES[(fw, fh)], fw, fh
    sys.exit('ERROR: donor %r (looked for %s) not in %s -- check the YAML '
             'art.map_sprite.base name' % (donor, sym, WAIT_DATA_C))


def sheet_info(path, expect=None):
    """Validate a wait-sheet PNG and return (size_macro, frame_w, frame_h, nframes).

    `expect=(fw, fh)` is the donor's authoritative size from donor_sms_geometry() (the
    decomp wait table). When given, the frame geometry is taken from it and the PNG is
    only checked to *match* -- geometry is never guessed from the pixel dimensions. The
    whole cast pipeline passes `expect`; the dimension-inference branch below is a
    last-resort for ad-hoc validation of a sheet whose donor isn't known, and it warns
    because a 16x96 sheet is genuinely ambiguous.
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
    if expect is not None:
        fw, fh = expect
        if w != fw or h % fh or h < fh:
            sys.exit('ERROR: %s is %dx%d but its donor SMS is %dx%d -- width must be %d '
                     'and height a multiple of %d' % (path, w, h, fw, fh, fw, fh))
        return SMS_SIZES[(fw, fh)], fw, fh, h // fh

    # No donor known: infer, preferring the tallest frame that divides the height. Only
    # warn when more than one size fits (e.g. 16x96 = 6x16x16 or 3x16x32) -- then the
    # caller really should pass `expect` from the decomp. A 32-wide sheet only fits 32x32,
    # so it resolves unambiguously and stays quiet.
    fits = [(fw, fh) for (fw, fh) in SMS_SIZES if w == fw and h % fh == 0 and h >= fh]
    if not fits:
        sys.exit('ERROR: %s is %dx%d -- not a stack of 16x16/16x32/32x32 frames '
                 '(expected width 16 or 32, height an exact multiple of the frame)'
                 % (path, w, h))
    fw, fh = sorted(fits, key=lambda s: -s[0] * s[1])[0]
    if len(fits) > 1:
        sys.stderr.write('WARNING: %s size is ambiguous (%s); inferred %dx%d -- pass the '
                         'donor to read it from the decomp\n'
                         % (path, ' or '.join('%dx%d' % s for s in fits), fw, fh))
    return SMS_SIZES[(fw, fh)], fw, fh, h // fh


def _read_palette(path):
    """Load cast_palette.png -> a flat 16*3 RGB palette list (index 0 = transparent)."""
    im = Image.open(path)
    if im.mode != 'P':
        sys.exit('ERROR: %s must be indexed (mode P) to define the cast palette' % path)
    raw = im.getpalette() or []
    n = len(raw) // 3
    pal = []
    for i in range(16):
        pal += list(raw[3 * i:3 * i + 3]) if i < n else [0, 0, 0]
    return pal


def _parse_overrides(spec):
    """'5:6,4:5' -> {5: 6, 4: 5}. Forces donor index -> cast index, skipping nearest."""
    out = {}
    for pair in (spec or '').split(','):
        pair = pair.strip()
        if not pair:
            continue
        d, _, c = pair.partition(':')
        out[int(d)] = int(c)
    return out


def recolour(base_path, palette_path, out_path, overrides=None):
    """Reskin a vanilla donor wait/MU sheet into the bespoke cast palette.

    The donor's own indexed colours are remapped, nearest-RGB, onto the cast palette
    (campaigns/.../map_sprites/cast_palette.png). The result is an indexed PNG whose
    *indices* are cast-palette indices -- which is what gbagfx packs to 4bpp; the engine
    loads the cast palette into the sprite's OBJ bank separately (see build_campaign /
    decisions.md Art & Audio). Transparent (index 0) stays index 0; every other donor
    colour maps to its nearest cast colour among the 15 opaque entries.

    `overrides` ({donor_idx: cast_idx}) forces specific donor colours to a chosen cast
    entry, overriding nearest-colour -- the steering knob for a creative recolour (e.g.
    Braulo's tan body -> the cast reds). Everything not listed still falls to nearest.
    This is the programmatic pass; SHAPE adds (eyestalks, shells, ears, ...) are a hand
    pixel pass on top against this same palette (see decisions.md Art & Audio).
    """
    overrides = overrides or {}
    im = Image.open(base_path)
    if im.mode != 'P':
        sys.exit('ERROR: donor %s is mode %s; expected an indexed (mode P) FE8 sheet'
                 % (base_path, im.mode))
    src_pal = im.getpalette() or []

    cast = _read_palette(palette_path)
    cast_rgb = [tuple(cast[3 * i:3 * i + 3]) for i in range(16)]

    # Build donor-index -> cast-index map. Index 0 is the engine's transparent slot in
    # both palettes; keep it fixed. Opaque donor colours take an explicit override if
    # given, else pick the nearest cast colour among indices 1..15 (never transparent).
    remap = {0: 0}
    for di in set(im.getdata()):
        if di == 0:
            continue
        if di in overrides:
            remap[di] = overrides[di]
            continue
        dr, dg, db = src_pal[3 * di:3 * di + 3]
        best, best_d = 1, None
        for ci in range(1, 16):
            cr, cg, cb = cast_rgb[ci]
            d = (dr - cr) ** 2 + (dg - cg) ** 2 + (db - cb) ** 2
            if best_d is None or d < best_d:
                best, best_d = ci, d
        remap[di] = best

    out = Image.new('P', im.size)
    out.putpalette(cast)
    out.putdata([remap[px] for px in im.getdata()])
    out.save(out_path)
    print('recoloured %s -> %s (cast palette: %s)' % (base_path, out_path, palette_path))
    print('  donor idx -> cast idx: %s'
          % ', '.join('%d->%d%s' % (d, c, '*' if d in overrides else '')
                      for d, c in sorted(remap.items())))
    print('  (* = forced override; others nearest-colour)')
    # Validate against the donor's authoritative SMS geometry (decomp), not a guess.
    _, dfw, dfh = donor_sms_geometry(base_path)
    sheet_info(out_path, (dfw, dfh))


def synth_mu_sheet(idle_path, donor, out_path, y_nudge=0, verbose=True):
    """Synthesize a static-"glide" MU (hover/walk) sheet from a finished idle sheet.

    A moving unit draws its MU sheet, not its idle SMS, so with no MU asset it reverts
    to the stock class sprite. The idle-only decision (HANDOFF / decisions.md) is honoured
    by NOT animating a walk: instead the idle pose is anchored to the donor's standing MU
    frame (feet-aligned) and tiled into EVERY 32x32 block of a sheet matching the donor's
    MU height. Because every block holds the same pose, whichever block (or H-flip) the
    reused class motion script selects, the unit shows its idle pose -- it glides.

    The pose's feet are aligned to the donor's block-0 MU content so standing<->moving is
    seamless; `y_nudge` (px, + = down) trims any residual drift. Output is an indexed PNG
    in the idle sheet's (cast) palette, ready for the move-sheet incbin.
    """
    _, ifw, ifh = donor_sms_geometry(donor)
    sheet_info(idle_path, (ifw, ifh))          # idle must match the donor SMS geometry
    idle = Image.open(idle_path)

    donor_mu_path = os.path.join(MOVE_GFX_DECOMP, 'unit_icon_move_%s_sheet.png' % donor)
    if not os.path.isfile(donor_mu_path):
        sys.exit('ERROR: donor MU sheet not found: %s (needed to anchor the glide)'
                 % donor_mu_path)
    donor_mu = Image.open(donor_mu_path)
    dw, dh = donor_mu.size
    if dw != MU_CELL or dh < MU_CELL:
        sys.exit('ERROR: donor MU %s is %dx%d -- expected a %d-wide stack of %dx%d blocks'
                 % (donor_mu_path, dw, dh, MU_CELL, MU_CELL, MU_CELL))
    # Many vanilla MU sheets carry a sub-32 remainder strip (heights 488/504, not a clean
    # multiple of 32). The motion script only references full 32x32 blocks, so we fill those
    # and leave any remainder transparent -- but keep the donor's EXACT dimensions so the
    # decompressed sheet matches the size the engine's MU buffer expects.
    nblocks = dh // MU_CELL

    # Feet anchor: our idle content's bottom-centre -> the donor's block-0 content
    # bottom-centre. getbbox() ignores index 0 (transparent), so it finds the pose.
    idle_f0 = idle.crop((0, 0, ifw, ifh))
    ib = idle_f0.getbbox()
    db = donor_mu.crop((0, 0, MU_CELL, MU_CELL)).getbbox()
    if ib and db:
        paste_x = int(round((db[0] + db[2]) / 2.0 - (ib[2] - ib[0]) / 2.0)) - ib[0]
        paste_y = (db[3] - (ib[3] - ib[1])) - ib[1] + y_nudge
    else:                                       # empty frame: fall back to cell bottom-centre
        paste_x, paste_y = (MU_CELL - ifw) // 2, MU_CELL - ifh + y_nudge

    cell = Image.new('P', (MU_CELL, MU_CELL), 0)
    cell.paste(idle_f0, (paste_x, paste_y))     # bg is index 0, so the pose's transparency is kept
    out = Image.new('P', (dw, dh), 0)           # exact donor dims; remainder strip stays index 0
    out.putpalette(idle.getpalette())
    for b in range(nblocks):
        out.paste(cell, (0, b * MU_CELL))
    out.save(out_path)
    if verbose:
        print('synth MU glide %s -> %s (%dx%d, %d blocks; anchor x=%d y=%d off donor %s)'
              % (os.path.basename(idle_path), out_path, dw, dh, nblocks, paste_x, paste_y, donor))
    return out_path


def validate_mu_sheet(path):
    """Validate a MU (move) sheet PNG and return its full-32x32-block count. MU sheets are
    indexed (<=16 colours), 32px wide, and a vertical stack of 32x32 blocks; vanilla ones
    may carry a small sub-32 remainder strip (heights like 488/504), which is allowed --
    so height need NOT be an exact multiple of 32 (unlike a wait/SMS sheet)."""
    if not os.path.isfile(path):
        sys.exit('ERROR: MU sheet not found: %s' % path)
    im = Image.open(path)
    if im.mode != 'P':
        sys.exit('ERROR: %s is mode %s; MU sheets must be indexed (mode P)' % (path, im.mode))
    nc = len(im.getcolors() or range(MAX_COLORS + 1))
    if nc > MAX_COLORS:
        sys.exit('ERROR: %s uses %d colours; the 4bpp map-sprite palette allows %d '
                 '(index 0 transparent + 15)' % (path, nc, MAX_COLORS))
    w, h = im.size
    if w != MU_CELL or h < MU_CELL:
        sys.exit('ERROR: %s is %dx%d -- a MU sheet must be %d wide and at least %d tall'
                 % (path, w, h, MU_CELL, MU_CELL))
    return h // MU_CELL


# Backgrounds the preview composites onto, to judge contrast the way the map will show
# the sprite: grass, snow (Frostmaiden's biome), and a neutral mid-grey.
_PREVIEW_BGS = [('grass', (104, 152, 56)), ('snow', (224, 232, 240)),
                ('grey', (96, 96, 96))]


def preview(sheet_path, out_path, scale=8):
    """Offline 'how does it read in-game' render -- no ROM build, no mGBA.

    Composites the sheet's frames over representative map backgrounds (index 0 = the
    engine's transparent slot is shown through), upscaled NEAREST. Writes a static
    contact sheet (frames x backgrounds). If out_path ends in .gif, instead writes an
    animated idle that cycles the frames over the grass background, for a quick motion
    read. This is the fast iteration surface for the recolour/draw loop.
    """
    macro, fw, fh, n = sheet_info(sheet_path)
    sheet = Image.open(sheet_path)
    frames = []
    for i in range(n):
        crop = sheet.crop((0, i * fh, fw, (i + 1) * fh))
        fr = crop.convert('RGBA')
        # Index 0 is the engine's transparent slot. Build the alpha mask from the raw
        # palette indices (not luminance) -- punch index 0 to alpha 0, keep the rest.
        mask = Image.new('L', (fw, fh))
        mask.putdata([0 if px == 0 else 255 for px in crop.getdata()])
        fr.putalpha(mask)
        frames.append(fr)

    def up(img):
        return img.resize((img.width * scale, img.height * scale), Image.NEAREST)

    if out_path.lower().endswith('.gif'):
        bg = Image.new('RGBA', (fw, fh), _PREVIEW_BGS[0][1] + (255,))
        gif = []
        for fr in frames:
            comp = Image.alpha_composite(bg, fr)
            gif.append(up(comp).convert('P', palette=Image.ADAPTIVE))
        gif[0].save(out_path, save_all=True, append_images=gif[1:], loop=0, duration=140)
        print('preview GIF -> %s (%d frames @140ms, scale %dx)' % (out_path, n, scale))
        return

    pad = 4
    cell_w, cell_h = fw * scale, fh * scale
    cols, rows = n, len(_PREVIEW_BGS)
    canvas = Image.new('RGB', (cols * (cell_w + pad) + pad,
                               rows * (cell_h + pad) + pad), (24, 24, 24))
    for r, (_, rgb) in enumerate(_PREVIEW_BGS):
        for c, fr in enumerate(frames):
            cell = Image.new('RGBA', (fw, fh), rgb + (255,))
            cell = Image.alpha_composite(cell, fr)
            canvas.paste(up(cell).convert('RGB'),
                         (pad + c * (cell_w + pad), pad + r * (cell_h + pad)))
    canvas.save(out_path)
    print('preview contact sheet -> %s (%d frames x %d bgs, scale %dx)'
          % (out_path, n, rows, scale))


# --- Coordinate-directed pixel editing -------------------------------------------
# Nicolas directs edits by eye off a labelled grid (he doesn't draw); these turn a
# called-out cell into an applied pixel. Convention: ROW = letter (Y, A at top),
# COLUMN = number (X, 0 at left); a cell is "<row-letter><col-number>", e.g. "C7" =
# row C (y=2), column 7. Per-frame: edits target one frame's 16x16/32x32 cell.


def _row_label(i):
    """0->A .. 25->Z, 26->a .. (enough for 16/32-tall frames)."""
    return chr(ord('A') + i) if i < 26 else chr(ord('a') + i - 26)


def _parse_cell(cell):
    """'C7' -> (x=7, y=2). Row letter (Y) first, column number (X) second."""
    cell = cell.strip()
    letters = ''.join(c for c in cell if c.isalpha())
    digits = ''.join(c for c in cell if c.isdigit())
    if not letters or not digits:
        sys.exit('ERROR: bad cell %r -- expected <row-letter><col-number>, e.g. C7' % cell)
    y = ord(letters[0].upper()) - ord('A') if letters[0].isupper() else \
        ord(letters[0].lower()) - ord('a') + 26
    return int(digits), y


def grid(sheet_path, out_path, frame=0, scale=28):
    """Render ONE frame as a labelled coordinate grid for by-eye direction.

    Each pixel becomes a big cell showing its current cast-palette index (and tinted
    with that colour); rows are lettered (Y), columns numbered (X). Transparent cells
    (index 0) are checkered. Read a cell as <row-letter><col-number> (e.g. C7) and feed
    it to `setpx` to change it. This is the offline pixel-edit surface (no mGBA).
    """
    macro, fw, fh, n = sheet_info(sheet_path)
    if not 0 <= frame < n:
        sys.exit('ERROR: frame %d out of range (sheet has %d)' % (frame, n))
    sheet = Image.open(sheet_path)
    pal = sheet.getpalette() or []
    crop = sheet.crop((0, frame * fh, fw, (frame + 1) * fh))
    px = list(crop.getdata())

    margin = 22  # room for the axis labels
    canvas = Image.new('RGB', (margin + fw * scale, margin + fh * scale), (30, 30, 30))
    d = ImageDraw.Draw(canvas)
    # Column numbers (X) along the top.
    for x in range(fw):
        d.text((margin + x * scale + scale // 2 - 3, 6), str(x), fill=(200, 200, 200))
    # Row letters (Y) down the left.
    for y in range(fh):
        d.text((6, margin + y * scale + scale // 2 - 4), _row_label(y), fill=(200, 200, 200))

    for y in range(fh):
        for x in range(fw):
            idx = px[y * fw + x]
            x0, y0 = margin + x * scale, margin + y * scale
            if idx == 0:  # transparent -> checker
                for sub, fill in (((0, 0), (70, 70, 70)), ((1, 0), (50, 50, 50)),
                                  ((0, 1), (50, 50, 50)), ((1, 1), (70, 70, 70))):
                    d.rectangle([x0 + sub[0] * scale // 2, y0 + sub[1] * scale // 2,
                                 x0 + (sub[0] + 1) * scale // 2, y0 + (sub[1] + 1) * scale // 2],
                                fill=fill)
                r, g, b = (120, 120, 120), None, None
                label_fill = (150, 150, 150)
            else:
                r, g, b = pal[idx * 3:idx * 3 + 3]
                d.rectangle([x0, y0, x0 + scale, y0 + scale], fill=(r, g, b))
                # readable label colour for the index digit
                label_fill = (0, 0, 0) if (r + g + b) > 360 else (255, 255, 255)
            d.rectangle([x0, y0, x0 + scale, y0 + scale], outline=(20, 20, 20))
            d.text((x0 + scale // 2 - 3, y0 + scale // 2 - 4), str(idx), fill=label_fill)

    canvas.save(out_path)
    print('grid -> %s (frame %d/%d, %dx%d, cells show cast index)'
          % (out_path, frame, n, fw, fh))
    print('  read cells as <row-letter><col-number> (e.g. C7); edit with: '
          'setpx %s %d C7:6 ...' % (os.path.basename(sheet_path), frame))


def palette_chart(palette_path, out_path):
    """Swatch chart of the 16 cast indices (number + RGB + colour block) so a called-out
    index is unambiguous. Index 0 is the transparent slot."""
    pal = _read_palette(palette_path)
    rowh, w = 36, 320
    canvas = Image.new('RGB', (w, rowh * 16), (30, 30, 30))
    d = ImageDraw.Draw(canvas)
    for i in range(16):
        r, g, b = pal[i * 3:i * 3 + 3]
        y = i * rowh
        d.rectangle([8, y + 4, 8 + 80, y + rowh - 4], fill=(r, g, b), outline=(80, 80, 80))
        tag = '%2d  rgb(%3d,%3d,%3d)%s' % (i, r, g, b, '  [transparent]' if i == 0 else '')
        d.text((100, y + rowh // 2 - 4), tag, fill=(220, 220, 220))
    canvas.save(out_path)
    print('palette chart -> %s' % out_path)


def setpx(sheet_path, frame, edits):
    """Apply by-eye pixel direction to one frame, in place. edits = ['C7:6', 'D7:6', ...]
    (cell -> cast index). Writes the sheet back with its palette intact."""
    macro, fw, fh, n = sheet_info(sheet_path)
    if not 0 <= frame < n:
        sys.exit('ERROR: frame %d out of range (sheet has %d)' % (frame, n))
    sheet = Image.open(sheet_path)
    px = list(sheet.getdata())
    applied = []
    for e in edits:
        cell, _, idx = e.partition(':')
        if not idx:
            sys.exit('ERROR: bad edit %r -- expected <cell>:<castindex>, e.g. C7:6' % e)
        idx = int(idx)
        if not 0 <= idx <= 15:
            sys.exit('ERROR: cast index %d out of range 0..15 (edit %r)' % (idx, e))
        x, y = _parse_cell(cell)
        if not (0 <= x < fw and 0 <= y < fh):
            sys.exit('ERROR: cell %s -> (x=%d,y=%d) outside the %dx%d frame'
                     % (cell, x, y, fw, fh))
        px[(frame * fh + y) * fw + x] = idx
        applied.append('%s(x%d,y%d)->%d' % (cell.upper(), x, y, idx))
    sheet.putdata(px)
    sheet.save(sheet_path)
    print('setpx %s frame %d: %s' % (sheet_path, frame, ', '.join(applied)))


USAGE = ('usage:\n'
         '  map_sprite_tool.py <wait_sheet.png>                     # validate\n'
         '  map_sprite_tool.py recolour <donor.png> <cast_palette.png> <out.png> '
         '[d:c,d:c]\n'
         '  map_sprite_tool.py preview <sheet.png> <out.png|out.gif> [scale]\n'
         '  map_sprite_tool.py grid <sheet.png> <out.png> [frame] [scale]\n'
         '  map_sprite_tool.py palette <cast_palette.png> <out.png>\n'
         '  map_sprite_tool.py setpx <sheet.png> <frame> <cell:idx> [cell:idx ...]')


def main():
    args = sys.argv[1:]
    if args and args[0] == 'recolour':
        if len(args) not in (4, 5):
            sys.exit(USAGE)
        recolour(args[1], args[2], args[3],
                 _parse_overrides(args[4]) if len(args) == 5 else None)
        return
    if args and args[0] == 'preview':
        if len(args) not in (3, 4):
            sys.exit(USAGE)
        preview(args[1], args[2], int(args[3]) if len(args) == 4 else 8)
        return
    if args and args[0] == 'grid':
        if len(args) not in (3, 4, 5):
            sys.exit(USAGE)
        frame = int(args[3]) if len(args) >= 4 else 0
        scale = int(args[4]) if len(args) == 5 else 28
        grid(args[1], args[2], frame, scale)
        return
    if args and args[0] == 'palette':
        if len(args) != 3:
            sys.exit(USAGE)
        palette_chart(args[1], args[2])
        return
    if args and args[0] == 'setpx':
        if len(args) < 4:
            sys.exit(USAGE)
        setpx(args[1], int(args[2]), args[3:])
        return
    if len(args) != 1:
        sys.exit(USAGE)
    macro, fw, fh, n = sheet_info(args[0])
    print('%s: %s, %d frame(s) of %dx%d' % (args[0], macro, n, fw, fh))


if __name__ == '__main__':
    main()
