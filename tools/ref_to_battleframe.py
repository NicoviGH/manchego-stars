#!/usr/bin/env python3
"""Battle-frame conversion (#65 Milestone A): a static sprite -> FE8 banim assets.

Sibling of ref_to_bust.py: where that turns a reference into an FE8 portrait, this turns
1-3 transparent static frames into a faked battle animation -- 4bpp tile sheet(s) + OAM
frame layouts + palette + a motion script (timing/effects cloned from a donor class). No
hand-drawn motion frames; the engine's projectile/hit effects sell the action (epic #65).

This module is built bottom-up, TDD'd in test_ref_to_battleframe.py (in `make test`):
  * tile_sprite -- cut a sprite into the 8x8 OBJ tiles a GBA sheet is built from, emitting
    one OAM entry per non-empty cell. (further stages added as TDD proceeds)
"""
import struct

from PIL import Image

TILE = 8  # GBA OBJ tiles are 8x8
SQUARE_SIZES = (4, 2, 1)  # legal GBA square OBJ side, in 8x8 cells (32x32 / 16x16 / 8x8)
PAL_BANK = 16     # colours per GBA 4bpp sub-palette
PAL_BANKS = 4     # a banim .agbpal holds 4 sub-palettes (64 BGR555 hwords, 128 bytes)
SHEET_COLS = 32   # banim sheets are 2D char-mapped, 32 tiles (256px) wide
OBJ_HFLIP = 0x1000  # attr1 bit12 (h-flip)


def _bgr555(rgb):
    """Pack an 8-bit (r, g, b) into a GBA BGR555 hword."""
    r, g, b = rgb
    return ((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3)


def agbpal_bytes(palette):
    """A <=16-colour palette -> the 128-byte .agbpal the banim build links.

    Encodes the colours as BGR555, pads the bank to 16 entries with 0, and mirrors that
    one 16-colour bank across all 4 sub-palettes (our OAM only references palbank 0; the
    other banks are kept sane in case the engine touches them).
    """
    bank = [_bgr555(c) for c in palette[:PAL_BANK]]
    bank += [0] * (PAL_BANK - len(bank))
    return struct.pack("<%dH" % (PAL_BANK * PAL_BANKS), *(bank * PAL_BANKS))


def merge_objects(filled, cols, rows):
    """Pack the filled 8x8 cells into the fewest legal square GBA OBJs.

    `filled` is a set of (cx, cy) cell coords; `cols`/`rows` bound the grid. Returns a
    list of {cx, cy, w, h} placements (w==h, in cells) covering EXACTLY the filled cells.
    A larger OBJ is placed only when every cell it spans is filled -- so a merged OBJ
    never draws a transparent/garbage tile, the way one 16x16 over an L-shape would.

    Greedy, row-major, largest-first: 47 stray 8x8 cells collapse to ~16 when the sprite
    body has solid 2x2/4x4 blocks; irregular edges stay 8x8.
    """
    remaining = set(filled)
    objs = []
    for cy in range(rows):
        for cx in range(cols):
            if (cx, cy) not in remaining:
                continue
            for s in SQUARE_SIZES:
                if cx + s > cols or cy + s > rows:
                    continue
                block = {(cx + dx, cy + dy) for dx in range(s) for dy in range(s)}
                if block <= remaining:
                    objs.append({"cx": cx, "cy": cy, "w": s, "h": s})
                    remaining -= block
                    break
    return objs


def build_sheet_from_placements(frame_img, placements, palette, sheet_cols=SHEET_COLS):
    """Blit each placed OBJ's pixels onto a 256-wide (32-tile) indexed sheet.

    The sheet is 2D char-mapped (stride `sheet_cols`), so an OBJ that `pack_frame_oam`
    addressed at base tile row*32+col must have its source pixels at (col*8, row*8).
    Each OBJ's source is `frame_img` cropped at its sprite cell (cx,cy) for w*h tiles.
    Returns a mode-"P" image (transparent->index 0), height = used tile rows * 8.
    """
    used_rows = max((p["row"] + p["h"] for p in placements), default=1)
    w, h = sheet_cols * TILE, used_rows * TILE
    lut = {c: i for i, c in enumerate(palette[:PAL_BANK])}
    sheet = Image.new("P", (w, h), 0)
    flat = []
    for c in palette[:PAL_BANK]:
        flat += list(c)
    flat += [0] * (3 * PAL_BANK - len(flat))
    sheet.putpalette(flat)
    src = frame_img.load()
    for p in placements:
        sx0, sy0 = p["cx"] * TILE, p["cy"] * TILE
        dx0, dy0 = p["col"] * TILE, p["row"] * TILE
        for dy in range(p["h"] * TILE):
            for dx in range(p["w"] * TILE):
                r, g, b, a = src[sx0 + dx, sy0 + dy]
                if a != 0:
                    sheet.putpixel((dx0 + dx, dy0 + dy), lut.get((r, g, b), 0))
    return sheet


def build_sheet_png(tiles, palette, tiles_per_row=32):
    """Lay deduped 8x8 `tiles` row-major into an indexed (mode "P") sheet PNG.

    Every pixel becomes an index into `palette` (<=16 (r,g,b) colours); a transparent
    pixel (alpha 0) maps to index 0, the FE backdrop convention. gbagfx turns the PNG
    into the linked .4bpp at build time (`%.4bpp: %.png`).
    """
    rows = (len(tiles) + tiles_per_row - 1) // tiles_per_row
    w, h = tiles_per_row * TILE, max(rows, 1) * TILE
    lut = {c: i for i, c in enumerate(palette[:PAL_BANK])}
    sheet = Image.new("P", (w, h), 0)
    flat = []
    for c in palette[:PAL_BANK]:
        flat += list(c)
    flat += [0] * (3 * PAL_BANK - len(flat))
    sheet.putpalette(flat)
    for ti, tile in enumerate(tiles):
        ox, oy = (ti % tiles_per_row) * TILE, (ti // tiles_per_row) * TILE
        px = tile.load()
        for y in range(TILE):
            for x in range(TILE):
                r, g, b, a = px[x, y]
                sheet.putpixel((ox + x, oy + y), 0 if a == 0 else lut.get((r, g, b), 0))
    return sheet


def square_obj_attrs(w):
    """Square OBJ cell-side (1/2/4) -> (attr0 shape bits, attr1 size bits)."""
    size = {1: 0x0000, 2: 0x4000, 4: 0x8000}[w]
    return (0x0000, size)


def _obj_wpx(attr0, attr1):
    """Pixel width of a square OBJ from its attr bits (size0/1/2 -> 8/16/32)."""
    return {0x0000: 8, 0x4000: 16, 0x8000: 32}[attr1 & 0xC000]


def pack_frame_oam(objs, center_px, sheet_cols=SHEET_COLS):
    """Merged OBJs -> (oam_r entries, placements), 2D-addressed tile blocks.

    Each OBJ is laid into the sheet on a shelf (left-to-right, wrap at sheet_cols),
    keeping its w*h tiles a contiguous 2D rectangle so its base tile = row*32+col
    addresses the whole OBJ the way the banim 2D char map expects. Returns oam entries
    {attr0, attr1, attr2(base tile), dx, dy(pixel offset from centre)} plus parallel
    placements {cx, cy, w, h, col, row} for the sheet builder to blit the pixels.
    """
    cxp, cyp = center_px
    entries, placements = [], []
    col = row = shelf_h = 0
    for o in objs:
        w, h = o["w"], o["h"]
        if col + w > sheet_cols:          # wrap to the next shelf
            col, row, shelf_h = 0, row + shelf_h, 0
        attr0, attr1 = square_obj_attrs(w)
        entries.append({
            "attr0": attr0, "attr1": attr1, "attr2": row * sheet_cols + col,
            "dx": o["cx"] * TILE - cxp, "dy": o["cy"] * TILE - cyp,
        })
        placements.append({"cx": o["cx"], "cy": o["cy"], "w": w, "h": h,
                           "col": col, "row": row})
        col += w
        shelf_h = max(shelf_h, h)
    return entries, placements


def mirror_oam(entries):
    """oam_r -> oam_l: add the h-flip bit and mirror each OBJ's dx about the centre."""
    out = []
    for e in entries:
        wpx = _obj_wpx(e["attr0"], e["attr1"])
        out.append({
            "attr0": e["attr0"], "attr1": e["attr1"] | OBJ_HFLIP, "attr2": e["attr2"],
            "dx": -(e["dx"] + wpx), "dy": e["dy"],
        })
    return out


# The 12 banim modes, in banim_data modes-table order. For a faked ranged unit every
# attack_* mode runs the draw-and-fire template, dodges hop, stands hold frame 0.
_MODE_ORDER = [
    ("attack_close", "attack"), ("attack_close_back", "attack"),
    ("attack_close_critical", "attack"), ("attack_close_critical_back", "attack"),
    ("attack_range", "attack"), ("attack_range_critical", "attack"),
    ("dodge_close", "dodge"), ("dodge_range", "dodge"),
    ("stand_close", "stand"), ("stand", "stand"), ("stand_range", "stand"),
    ("attack_miss", "miss"),
]


def _frame_cmd(abbr, dur, i):
    """A banim_code_frame line: frame i lives on sheet i, oam at frame i's _r offset."""
    return ("\tbanim_code_frame %d, banim_%s_sheet_%d, %d, "
            "banim_%s_oam_frame_%d_r - banim_%s_oam_r" % (dur, abbr, i, i, abbr, i, abbr))


def _mode_body(abbr, kind):
    """Emit one mode's script lines for the 3-beat (Ready/Wind-up/Peak) fake."""
    if kind == "attack":   # draw (0->1 held) -> peak (2) + loose arrow -> recover
        return ["\tbanim_code_start_attack_1", "\tbanim_code_start_attack_2",
                _frame_cmd(abbr, 3, 0), "\tbanim_code_sound_pull_bow",
                _frame_cmd(abbr, 18, 1), _frame_cmd(abbr, 3, 2),
                "\tbanim_code_call_spell_anim", _frame_cmd(abbr, 1, 2),
                "\tbanim_code_wait_hp_deplete", "\tbanim_code_start_opposite_turn",
                _frame_cmd(abbr, 3, 0), "\tbanim_code_end_dodge",
                "\tbanim_code_end_mode"]
    if kind == "dodge":    # hop: 0 -> 1 -> 2 -> (wait) -> 1
        return ["\tbanim_code_dodge_to_before", _frame_cmd(abbr, 1, 0),
                _frame_cmd(abbr, 3, 1), _frame_cmd(abbr, 1, 2),
                "\tbanim_code_wait_hp_deplete", _frame_cmd(abbr, 3, 1),
                "\tbanim_code_end_dodge", "\tbanim_code_end_mode"]
    if kind == "stand":    # hold the ready frame
        return [_frame_cmd(abbr, 1, 0), "\tbanim_code_wait_hp_deplete",
                "\tbanim_code_end_mode"]
    return [_frame_cmd(abbr, 4, 0), "\tbanim_code_end_mode"]   # miss


def _oam_line(e):
    return ("\tbanim_frame_oam 0x%X, 0x%X, 0x%X, %d, %d"
            % (e["attr0"], e["attr1"], e["attr2"], e["dx"], e["dy"]))


def emit_motion_s(abbr, frames):
    """Assemble the full banim motion.s text for `abbr` from 3 frames' OAM.

    `frames` is a list of {"oam_r": [...], "oam_l": [...]} (Ready/Wind-up/Peak). Emits the
    .data.oam_l / .oam_r / .script (12 modes) / .modes sections. oam_l mirrors oam_r 1:1 so
    frame i is at the same byte offset in both tables (the script references the _r offset;
    the engine adds it to the oam_l base when the unit faces the other way).
    """
    L = ["@ vim:ft=armv4",
         "\t.global banim_%s_script" % abbr,
         "\t.global banim_%s_oam_r" % abbr,
         "\t.global banim_%s_oam_l" % abbr,
         '\t.include "../include/banim_sheet.inc"',
         '\t.include "../include/banim_code.inc"',
         '\t.include "../include/banim_code_frame.inc"',
         "@ faked battle animation (donor-prime, #65)"]

    for side in ("l", "r"):
        L.append("\t.section .data.oam_%s" % side)
        L.append("banim_%s_oam_%s:" % (abbr, side))
        for i, fr in enumerate(frames):
            L.append("banim_%s_oam_frame_%d_%s:" % (abbr, i, side))
            for e in fr["oam_%s" % side]:
                L.append(_oam_line(e))
            L.append("\tbanim_frame_end")

    L.append("\t.section .data.script")
    L.append("banim_%s_script:" % abbr)
    for name, kind in _MODE_ORDER:
        L.append("banim_%s_mode_%s:" % (abbr, name))
        L += _mode_body(abbr, kind)

    L.append("\t.section .data.modes")
    for name, _ in _MODE_ORDER:
        L.append("\t.word banim_%s_mode_%s - banim_%s_script" % (abbr, name, abbr))
    for _ in range(12):
        L.append("\t.word 0")
    return "\n".join(L) + "\n"


def build_battle_anim(abbr, frame_imgs, palette, center_px=None):
    """Drive the whole faked-anim build: 3 frames -> sheets + agbpal + motion.s text.

    Per frame: tile -> merge filled cells into OBJs -> pack to oam_r + 2D placements ->
    mirror to oam_l -> blit the sheet. All frames use ONE shared anchor (`center_px`,
    default a torso point) so the body stays put on screen. Returns
    {"sheets": [P-image x N], "pal": <128 bytes>, "motion_s": <str>}.
    """
    if center_px is None:
        w, h = frame_imgs[0].size
        center_px = (w // 2, h * 5 // 8)
    sheets, frames = [], []
    for im in frame_imgs:
        cols, rows = im.size[0] // TILE, im.size[1] // TILE
        _, oam = tile_sprite(im)
        filled = {(o["dx"] // TILE, o["dy"] // TILE) for o in oam}
        objs = merge_objects(filled, cols, rows)
        entries, placements = pack_frame_oam(objs, center_px)
        sheets.append(build_sheet_from_placements(im, placements, palette))
        frames.append({"oam_r": entries, "oam_l": mirror_oam(entries)})
    return {"sheets": sheets, "pal": agbpal_bytes(palette),
            "motion_s": emit_motion_s(abbr, frames)}


def _cell_is_empty(im, ox, oy):
    """True if the 8x8 cell at (ox, oy) is fully transparent."""
    for y in range(oy, oy + TILE):
        for x in range(ox, ox + TILE):
            if im.getpixel((x, y))[3] != 0:
                return False
    return True


def tile_sprite(im):
    """Cut `im` (RGBA) into 8x8 tiles, returning (tiles, oam).

    `tiles` is the list of non-empty 8x8 tile images in emission (row-major) order.
    `oam` is a parallel list of {tile, dx, dy}: the tile's index and the top-left pixel
    offset of its cell in `im`. Fully-transparent cells carry no hardware sprite and are
    skipped (no tile, no OAM entry) -- that's what keeps a sparse sprite cheap.
    """
    w, h = im.size
    tiles, oam = [], []
    index = {}  # tile bytes -> sheet index, so identical cells share one tile
    for oy in range(0, h, TILE):
        for ox in range(0, w, TILE):
            if _cell_is_empty(im, ox, oy):
                continue
            cell = im.crop((ox, oy, ox + TILE, oy + TILE))
            key = cell.tobytes()
            idx = index.get(key)
            if idx is None:
                idx = len(tiles)
                index[key] = idx
                tiles.append(cell)
            oam.append({"tile": idx, "dx": ox, "dy": oy})
    return tiles, oam
