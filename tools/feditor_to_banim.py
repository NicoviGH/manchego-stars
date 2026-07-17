#!/usr/bin/env python3
"""Import a community FEditor battle animation into decomp banim assets (#90).

Where ref_to_battleframe FAKES a 3-frame animation from static poses (the PC path, #65),
this transcribes a REAL FE-native community animation whole: an FEditor "For Each Frame"
`.txt` script + its per-frame indexed PNGs -> the same decomp banim shape (per-frame OBJ
sheets + oam_l/r + a transcribed motion.s + agbpal), reusing ref_to_battleframe's low-level
emitters. Used for generic ENEMY classes (kobolds, fire imps) that carry a custom map sprite
but animate vanilla in the battle close-up; build_campaign binds the result at the class via
ClassData.pBattleAnimDef (not the per-character _u25 path PCs use).

Grounding:
  * FEditor format: https://fe-battle-animations.neocities.org/  (12 modes; 2 & 4 are
    "handled automatically" == duplicates of 1 & 3; 7-8 dodge, 9-11 standing, 12 miss)
  * command codes: a FEditor `Cxx` line IS the low byte of a 0x850000XX banim command word
    -- see fireemblem8u/include/banim_code.inc (banim_code_hit_normal == 0x8500001A == C1A).
    Emitted uniformly as the raw `banim_code_85 0xXX` escape: byte-exact and unambiguous
    (several named macros collide on one word), the raw fallback the #90 design anticipated.
"""
import collections
import os
import re

from PIL import Image

import ref_to_battleframe as rb

Frame = collections.namedtuple("Frame", ["duration", "file"])
Cmd = collections.namedtuple("Cmd", ["code"])

Anim = collections.namedtuple("Anim", ["modes"])


def parse_feditor(text):
    """Parse an FEditor "For Each Frame" `.txt` into an Anim of ordered modes.

    `modes` is an ordered {mode_number: [Frame|Cmd, ...]}. A `Cxx` line becomes Cmd(0xXX);
    a `<dur> p- file.png` line becomes Frame(dur, file). Mode sections open with
    `/// - Mode N` and close with `~~~`; `/// - End of animation` ends the script.
    """
    modes = collections.OrderedDict()
    cur = None
    for raw in text.splitlines():
        # Drop inline FEditor "#..." annotations (some exports comment every line, incl. the
        # "delete # on import" header and per-command notes) before parsing what remains.
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.match(r"/// - Mode (\d+)", line)   # header may have carried an inline #comment
        if m:
            cur = int(m.group(1))
            modes[cur] = []
            continue
        if line.startswith("///") or line == "~~~":
            cur = None
            continue
        if cur is None:
            continue
        if line[0] == "C" and len(line) == 3:
            modes[cur].append(Cmd(int(line[1:], 16)))
        else:
            parts = line.split()
            modes[cur].append(Frame(int(parts[0]), parts[-1]))
    return Anim(modes=modes)


def unique_frames(anim):
    """The distinct frame filenames across all modes, in first-appearance order.

    Each distinct PNG becomes one decomp sheet + one oam block; a display line reuses its
    frame's index. (Axe_000, held in most modes, is one sheet referenced many times.)"""
    seen = []
    for insns in anim.modes.values():
        for i in insns:
            if isinstance(i, Frame) and i.file not in seen:
                seen.append(i.file)
    return seen


# The decomp mode table is 12 slots (see ref_to_battleframe._MODE_ORDER, proven in-engine).
# FEditor writes modes 1,3,5,6,7,8,9,10,11,12 and OMITS 2 & 4 as "handled automatically" --
# per the format spec they duplicate 1 & 3 (the near/far attack "back" variants). So slot i
# reads FEditor mode i+1, except slots 1/3 fall back to modes 1/3.
_SLOT_FALLBACK = {2: 1, 4: 3}


def mode_table_slots(anim):
    """The 12 FEditor mode numbers the decomp mode-table slots point at (slot 0..11).

    slot i -> mode i+1, except an omitted mode (2 or 4) points at its front sibling (1/3).
    A mode still absent after that fallback is an error (the other 10 are always present)."""
    slots = []
    for i in range(12):
        mode = i + 1
        if mode not in anim.modes:
            mode = _SLOT_FALLBACK.get(mode, mode)
        if mode not in anim.modes:
            raise ValueError("FEditor script missing required mode %d" % (i + 1))
        slots.append(mode)
    return slots


def emit_command(cmd):
    """A FEditor `Cxx` command -> the byte-exact raw `banim_code_85 0xXX` escape.

    `Cxx` IS the low byte of a 0x850000XX command word (banim_code.inc); the raw escape is
    unambiguous where named macros collide on one word (0x50, 0x19), so we use it uniformly."""
    return "\tbanim_code_85 0x%02X" % cmd.code


def emit_frame(abbr, frame, index):
    """A FEditor `<dur> p- file` line -> a banim_code_frame referencing frame `index`'s
    sheet + oam (the _r offset; the engine adds it to oam_l's base when facing the other way)."""
    return ("\tbanim_code_frame %d, banim_%s_sheet_%d, %d, "
            "banim_%s_oam_frame_%d_r - banim_%s_oam_r"
            % (frame.duration, abbr, index, index, abbr, index, abbr))


def _oam_line(e):
    return ("\tbanim_frame_oam 0x%X, 0x%X, 0x%X, %d, %d"
            % (e["attr0"], e["attr1"], e["attr2"], e["dx"], e["dy"]))


def emit_motion_s(abbr, anim, frames):
    """Assemble the full decomp motion.s from a parsed FEditor `anim` + per-frame OAM.

    `frames` parallels unique_frames(anim): each {"oam_l": [...], "oam_r": [...]} is one
    distinct FEditor frame's tiled OBJ entries (built by ref_to_battleframe's tiler). Emits
    the four banim sections: oam_l / oam_r (one block per distinct frame), script (one block
    per PRESENT FEditor mode -- a display line -> banim_code_frame, a Cxx -> the raw 0x85
    escape, and the mode's `~~~` terminator -> banim_code_end_mode), and the 12-slot modes
    table (slot i -> mode i+1, with the auto-handled 2 & 4 pointing at their 1 & 3 siblings).
    Byte-shape identical to ref_to_battleframe.emit_motion_s so the same banim build links it.
    """
    files = unique_frames(anim)
    findex = {f: i for i, f in enumerate(files)}

    L = ["@ vim:ft=armv4",
         "\t.global banim_%s_script" % abbr,
         "\t.global banim_%s_oam_r" % abbr,
         "\t.global banim_%s_oam_l" % abbr,
         '\t.include "../include/banim_sheet.inc"',
         '\t.include "../include/banim_code.inc"',
         '\t.include "../include/banim_code_frame.inc"',
         "@ imported FEditor battle animation (#90)"]

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
    for mode, insns in anim.modes.items():
        L.append("banim_%s_mode_%d:" % (abbr, mode))
        for insn in insns:
            if isinstance(insn, Frame):
                L.append(emit_frame(abbr, insn, findex[insn.file]))
            else:
                L.append(emit_command(insn))
        L.append("\tbanim_code_end_mode")

    L.append("\t.section .data.modes")
    for mode in mode_table_slots(anim):
        L.append("\t.word banim_%s_mode_%d - banim_%s_script" % (abbr, mode, abbr))
    for _ in range(12):
        L.append("\t.word 0")
    return "\n".join(L) + "\n"


# --- Image build (FEditor frame PNGs -> decomp sheets + OAM + palette) ------------
# FEditor "For Each Frame" PNGs are the full battle canvas (248x160, some 488x160 wide),
# 256-index with the light-green FEditor backdrop at palette index 0 (the corner pixel).
# We key that out to transparent, then reuse ref_to_battleframe's tiler exactly as the faked
# path does -- the only difference is that ALL frames of one anim share ONE anchor (so the
# sprite's per-frame shift on the canvas becomes real OAM motion), and there are N distinct
# frames, not a fixed 3.

# FEditor "For Each Frame" PNGs bake the 16-colour palette into a swatch strip along the top
# rows of the canvas (preserving the palette for re-import). It is NOT sprite content -- left
# in, it tiles as a garbage floating strip AND inflates the sprite bbox, which throws the OAM
# origin off (both x and y). A battle sprite never occupies the top rows, so we clear them.
SWATCH_ROWS = 2


def _strip_top_swatch(rgba, rows=SWATCH_ROWS):
    """Return `rgba` with its top `rows` cleared to transparent (drops the FEditor palette swatch)."""
    out = rgba.copy()
    px = out.load()
    for y in range(min(rows, out.height)):
        for x in range(out.width):
            px[x, y] = (0, 0, 0, 0)
    return out


def _quantize5(rgb):
    """Round an 8-bit colour to what the GBA can actually show (5 bits/channel, low 3 bits
    dropped). Colours that quantize equal are one colour on hardware, so they share a palette
    slot -- keeps a PNG with hardware-identical near-duplicates inside the 15-colour budget."""
    r, g, b = rgb
    return (r & 0xF8, g & 0xF8, b & 0xF8)


def _load_frame(path):
    """Load an FEditor indexed PNG as RGBA: index-0 backdrop keyed transparent, the top-row
    palette swatch stripped, and opaque colours quantized to GBA BGR555 (so the sprite is the
    only content -- clean tiling, a correct bbox, and no hardware-duplicate palette overflow)."""
    im = Image.open(path)
    bg = im.getpixel((0, 0))            # the light-green backdrop sits at the canvas corner
    rgb = im.convert("RGB")
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    src, col, dst = im.load(), rgb.load(), out.load()
    for y in range(im.height):
        for x in range(im.width):
            if src[x, y] != bg:
                dst[x, y] = _quantize5(col[x, y]) + (255,)
    return _strip_top_swatch(out)


def _palette(frame_imgs):
    """A <=16-colour palette for the anim: index 0 transparent + each opaque colour once,
    in first-appearance order (shared across every frame's sheet so an index means one
    colour everywhere). An FE8 4bpp OBJ palette is 16 entries; a real FE-native anim fits."""
    pal = [(0, 0, 0)]
    seen = set()
    for im in frame_imgs:
        for _cnt, rgba in im.getcolors(1 << 24):
            if rgba[3] == 0:
                continue
            rgb = rgba[:3]
            if rgb not in seen:
                seen.add(rgb)
                pal.append(rgb)
    if len(pal) > rb.PAL_BANK:
        raise ValueError("imported anim uses %d opaque colours; FE8 OBJ palette holds 15"
                         % (len(pal) - 1))
    return pal


def _anchor(rgba):
    """The single per-anim OAM origin: horizontal centre + ~5/8 down the reference (standing)
    frame's opaque bbox -- the FE8 sprite pivot, matching the working faked path's
    center_px=(w//2, h*5//8) (ref_to_battleframe). Requires the CLEAN sprite bbox: _load_frame
    strips the FEditor palette swatch first, else the top-corner swatch inflates the bbox and
    shoves this origin ~30px off in x (to the sprite's edge) and up in y. Every frame tiles
    against this same point, so a pose drawn forward on the canvas yields shifted OAM -- the
    lunge the animation encodes."""
    x0, y0, x1, y1 = rgba.getbbox()
    return ((x0 + x1) // 2, y0 + (y1 - y0) * 5 // 8)


def enemy_red_recolor(rgb):
    """Map an anim's faction-blue 'clothing' colours to a red ramp at the same brightness,
    leaving skin/metal/highlights alone -- turns a community anim's native (ally-blue) palette
    into an ENEMY-red one for an always-hostile reskin (#90). The engine reads agbpal bank
    BANIMPAL_RED for enemies, so build_campaign bakes THIS palette into that bank."""
    r, g, b = rgb
    if b > r + 30 and b >= g:            # blue-dominant = the faction-swappable clothing
        return (b, g // 3, r // 3)
    return rgb


def build_import(abbr, txt_path, frames_dir, palette=None, anchor=None, recolor=None):
    """Import an FEditor animation folder -> {"sheets": [P-image], "pal": bytes, "motion_s": str}.

    Parses the `.txt`, loads each DISTINCT frame PNG, tiles it against one shared anchor (via
    ref_to_battleframe's OBJ tiler), and transcribes the script. Same asset shape as the faked
    path, so build_campaign links it through the identical banim machinery. `palette`/`anchor`
    may be supplied to share a palette across a class's weapons or hand-tune placement; `recolor`
    (an rgb->rgb map, e.g. enemy_red_recolor) recolours the AGBPAL only -- the sheet indices are
    unchanged, so the same tiles just index recoloured entries (the enemy-faction palette pass)."""
    with open(txt_path, encoding="utf-8") as f:
        anim = parse_feditor(f.read())
    imgs = [_load_frame(os.path.join(frames_dir, fn)) for fn in unique_frames(anim)]
    palette = palette or _palette(imgs)
    anchor = anchor or _anchor(imgs[0])
    sheets, frames = [], []
    for im in imgs:
        cols, rows = im.size[0] // rb.TILE, im.size[1] // rb.TILE
        _, oam = rb.tile_sprite(im)
        filled = {(o["dx"] // rb.TILE, o["dy"] // rb.TILE) for o in oam}
        objs = rb.merge_objects(filled, cols, rows)
        entries, placements = rb.pack_frame_oam(objs, anchor)
        sheets.append(rb.build_sheet_from_placements(im, placements, palette))
        frames.append({"oam_r": entries, "oam_l": rb.mirror_oam(entries)})
    agb_pal = [recolor(c) for c in palette] if recolor else palette
    return {"sheets": sheets, "pal": rb.agbpal_bytes(agb_pal),
            "motion_s": emit_motion_s(abbr, anim, frames)}
