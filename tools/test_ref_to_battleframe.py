#!/usr/bin/env python3
"""Tests for the battle-frame conversion (#65 M-A): static sprite -> FE8 banim assets.

The pure core here is the TILER: cut a transparent sprite into the 8x8 tiles a GBA OBJ
sheet is built from, and emit one OAM entry per non-empty cell (tile index + pixel
offset). Fully-transparent cells carry no hardware sprite, so they're skipped. Everything
in this file runs with no emulator (in `make test`). Format grounding: data/banim/*.s
(banim_frame_oam tile,x,y) + the decomp's banim build (graphics/banim/*_sheet_*.4bpp).
"""
import os
import sys
import unittest
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ref_to_battleframe as rb  # noqa: E402


def blank(w, h):
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


class TestMergeObjects(unittest.TestCase):
    """Greedy merge of filled 8x8 cells into the largest legal GBA square OBJ.

    The naive tiler emits one 8x8 OBJ per filled cell (RBG@64x64 -> 47). The GBA can
    draw a 2x2 or 4x4 block of tiles as a SINGLE OBJ (16x16 / 32x32), so vanilla covers
    a battle sprite in ~16. merge_objects packs the filled cells into the fewest square
    OBJs, never covering an empty cell (that would draw a garbage tile).
    """

    def test_solid_4x4_block_becomes_one_32x32_object(self):
        filled = {(c, r) for c in range(4) for r in range(4)}  # full 4x4-cell grid
        objs = rb.merge_objects(filled, 4, 4)
        self.assertEqual(len(objs), 1)
        self.assertEqual(objs[0], {"cx": 0, "cy": 0, "w": 4, "h": 4})

    def test_solid_2x2_block_becomes_one_16x16_object(self):
        filled = {(c, r) for c in range(2) for r in range(2)}
        objs = rb.merge_objects(filled, 2, 2)
        self.assertEqual(len(objs), 1)
        self.assertEqual(objs[0], {"cx": 0, "cy": 0, "w": 2, "h": 2})

    def test_never_covers_an_empty_cell(self):
        # L-shape: 3 of a 2x2 block filled. No 16x16 fits (would cover the empty cell);
        # must fall back to three 8x8 objs covering exactly the filled cells.
        filled = {(0, 0), (1, 0), (0, 1)}
        objs = rb.merge_objects(filled, 2, 2)
        covered = {(o["cx"] + dx, o["cy"] + dy)
                   for o in objs for dx in range(o["w"]) for dy in range(o["h"])}
        self.assertEqual(covered, filled)            # exactly the filled cells, no more
        self.assertTrue(all(o["w"] == 1 and o["h"] == 1 for o in objs))

    def test_partitions_cover_all_filled_with_legal_square_sizes(self):
        # 4x4 solid plus one stray cell -> one 32x32 + one 8x8, covering all, no empties.
        filled = {(c, r) for c in range(4) for r in range(4)} | {(5, 0)}
        objs = rb.merge_objects(filled, 6, 4)
        covered = {(o["cx"] + dx, o["cy"] + dy)
                   for o in objs for dx in range(o["w"]) for dy in range(o["h"])}
        self.assertEqual(covered, filled)
        for o in objs:
            self.assertIn(o["w"], (1, 2, 4))         # legal GBA square cell-sizes
            self.assertEqual(o["w"], o["h"])
        self.assertLess(len(objs), len(filled))      # actually merged


class TestAgbpal(unittest.TestCase):
    """16-colour palette -> the 128-byte .agbpal the banim build links (4x16 BGR555).

    FE8 banim palettes are 4 sub-palettes of 16 colours (64 BGR555 hwords). Our OAM
    references palbank 0; we mirror our one 16-colour palette across all 4 banks so any
    bank renders sanely. Colours are 5-bit BGR555: hword = (b>>3)<<10 | (g>>3)<<5 | r>>3.
    """

    def test_length_is_128_bytes(self):
        self.assertEqual(len(rb.agbpal_bytes([(0, 0, 0)])), 128)

    def test_encodes_colours_as_bgr555(self):
        b = rb.agbpal_bytes([(0, 0, 0), (255, 255, 255), (255, 0, 0)])
        import struct
        v = struct.unpack("<64H", b)
        self.assertEqual(v[0], 0x0000)   # black
        self.assertEqual(v[1], 0x7FFF)   # white
        self.assertEqual(v[2], 0x001F)   # pure red -> low 5 bits

    def test_pads_short_palette_then_mirrors_across_4_banks(self):
        b = rb.agbpal_bytes([(0, 0, 0), (255, 255, 255)])
        import struct
        v = struct.unpack("<64H", b)
        self.assertEqual(v[2], 0)        # padded within the bank
        for bank in range(4):            # each 16-entry bank mirrors bank 0
            self.assertEqual(v[bank * 16 + 0], 0x0000)
            self.assertEqual(v[bank * 16 + 1], 0x7FFF)


class TestSheetPng(unittest.TestCase):
    """Deduped 8x8 tiles + palette -> the indexed sheet PNG gbagfx turns into .4bpp.

    The banim build does `%.4bpp: %.png` via gbagfx, so we emit a mode-"P" PNG: tiles
    laid out row-major in a tiles_per_row grid, every pixel an index into the <=16-colour
    palette (index 0 = transparent backdrop, FE convention).
    """

    def _tile(self, rgba):
        im = Image.new("RGBA", (8, 8), rgba)
        return im

    def test_is_indexed_mode_with_grid_dimensions(self):
        tiles = [self._tile((255, 0, 0, 255)), self._tile((0, 0, 255, 255))]
        pal = [(0, 0, 0), (255, 0, 0), (0, 0, 255)]
        sheet = rb.build_sheet_png(tiles, pal, tiles_per_row=2)
        self.assertEqual(sheet.mode, "P")
        self.assertEqual(sheet.size, (16, 8))     # 2 tiles wide, 1 row tall

    def test_pixels_map_to_palette_indices(self):
        tiles = [self._tile((255, 0, 0, 255)), self._tile((0, 0, 255, 255))]
        pal = [(0, 0, 0), (255, 0, 0), (0, 0, 255)]
        sheet = rb.build_sheet_png(tiles, pal, tiles_per_row=2)
        self.assertEqual(sheet.getpixel((0, 0)), 1)    # red tile -> index 1
        self.assertEqual(sheet.getpixel((8, 0)), 2)    # blue tile -> index 2

    def test_transparent_pixels_are_index_zero(self):
        tiles = [self._tile((0, 0, 0, 0))]             # fully transparent tile
        pal = [(0, 0, 0), (255, 0, 0)]
        sheet = rb.build_sheet_png(tiles, pal, tiles_per_row=2)
        self.assertEqual(sheet.getpixel((0, 0)), 0)

    def test_wraps_to_next_row_past_tiles_per_row(self):
        tiles = [self._tile((255, 0, 0, 255))] * 3
        pal = [(0, 0, 0), (255, 0, 0)]
        sheet = rb.build_sheet_png(tiles, pal, tiles_per_row=2)
        self.assertEqual(sheet.size, (16, 16))         # 3 tiles -> 2 rows
        self.assertEqual(sheet.getpixel((0, 8)), 1)    # 3rd tile wrapped to row 2


class TestObjAttrs(unittest.TestCase):
    """Square merged OBJ (cell-side 1/2/4) -> GBA OAM shape+size control bits.

    attr0 bits14-15 = shape (square=0), attr1 bits14-15 = size. For squares:
    1 cell (8x8)=size0, 2 cells (16x16)=size1=0x4000, 4 cells (32x32)=size2=0x8000.
    """

    def test_square_sizes(self):
        self.assertEqual(rb.square_obj_attrs(1), (0x0000, 0x0000))
        self.assertEqual(rb.square_obj_attrs(2), (0x0000, 0x4000))
        self.assertEqual(rb.square_obj_attrs(4), (0x0000, 0x8000))


class TestPackFrameOam(unittest.TestCase):
    """Merged OBJs -> oam_r entries with 2D-addressed tile indices + centred offsets.

    FE8 banim sheets are 2D char-mapped (stride 32): a w*h-cell OBJ at sheet (col,row)
    has base tile row*32+col and spans a contiguous 2D block, so the allocator must keep
    each OBJ's tiles a rectangle. dx/dy are pixel offsets from the sprite centre.
    """

    def test_single_obj_base_tile_and_centred_offset(self):
        objs = [{"cx": 4, "cy": 4, "w": 2, "h": 2}]   # at pixel (32,32)
        entries, _ = rb.pack_frame_oam(objs, center_px=(32, 32))
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual((e["attr0"], e["attr1"]), (0x0000, 0x4000))  # 16x16
        self.assertEqual(e["attr2"], 0)                                # first block, tile 0
        self.assertEqual((e["dx"], e["dy"]), (0, 0))                   # centred

    def test_second_obj_gets_next_2d_tile_block(self):
        objs = [{"cx": 0, "cy": 0, "w": 2, "h": 2}, {"cx": 2, "cy": 0, "w": 1, "h": 1}]
        entries, _ = rb.pack_frame_oam(objs, center_px=(0, 0))
        # A spans sheet cols 0-1; B is the next free column on the same shelf -> tile 2.
        self.assertEqual(entries[0]["attr2"], 0)
        self.assertEqual(entries[1]["attr2"], 2)

    def test_offsets_are_relative_to_center(self):
        objs = [{"cx": 0, "cy": 0, "w": 1, "h": 1}]
        entries, _ = rb.pack_frame_oam(objs, center_px=(32, 32))
        self.assertEqual((entries[0]["dx"], entries[0]["dy"]), (-32, -32))


class TestMirrorOam(unittest.TestCase):
    """oam_r -> oam_l: set the h-flip bit and mirror dx about the sprite centre line."""

    def test_sets_hflip_and_mirrors_dx(self):
        r = [{"attr0": 0x0000, "attr1": 0x4000, "attr2": 5, "dx": -8, "dy": -16}]  # 16x16
        l = rb.mirror_oam(r)
        self.assertEqual(l[0]["attr1"], 0x5000)        # 0x4000 | 0x1000 hflip
        self.assertEqual(l[0]["attr0"], 0x0000)        # shape unchanged
        self.assertEqual(l[0]["attr2"], 5)             # same tiles
        self.assertEqual(l[0]["dx"], -8)               # -(dx + 16px) = -(-8+16) = -8
        self.assertEqual(l[0]["dy"], -16)              # vertical unchanged


class TestSheetFromPlacements(unittest.TestCase):
    """Blit each OBJ's source pixels to its 2D placement on a 256-wide (32-tile) sheet.

    pack_frame_oam emits attr2 = row*32+col; the sheet must put that OBJ's pixels at
    (col*8, row*8) so the 2D char-map address resolves. Output is indexed mode "P".
    """

    def _frame(self):  # 16x16 sprite, top-left cell red, others transparent
        im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        for y in range(8):
            for x in range(8):
                im.putpixel((x, y), (255, 0, 0, 255))
        return im

    def test_width_is_256_and_indexed(self):
        frame = self._frame()
        placements = [{"cx": 0, "cy": 0, "w": 1, "h": 1, "col": 0, "row": 0}]
        sheet = rb.build_sheet_from_placements(frame, placements, [(0, 0, 0), (255, 0, 0)])
        self.assertEqual(sheet.mode, "P")
        self.assertEqual(sheet.size[0], 256)            # 32 tiles wide (2D stride)

    def test_blits_obj_pixels_at_its_col_row(self):
        frame = self._frame()
        # place that red cell at sheet col 3, row 1 -> pixels at (24, 8)
        placements = [{"cx": 0, "cy": 0, "w": 1, "h": 1, "col": 3, "row": 1}]
        sheet = rb.build_sheet_from_placements(frame, placements, [(0, 0, 0), (255, 0, 0)])
        self.assertEqual(sheet.getpixel((24, 8)), 1)    # red -> palette index 1
        self.assertEqual(sheet.getpixel((0, 0)), 0)     # elsewhere transparent -> 0

    def test_multi_tile_obj_blits_its_whole_block(self):
        frame = Image.new("RGBA", (16, 16), (255, 0, 0, 255))  # full 16x16 red
        placements = [{"cx": 0, "cy": 0, "w": 2, "h": 2, "col": 0, "row": 0}]
        sheet = rb.build_sheet_from_placements(frame, placements, [(0, 0, 0), (255, 0, 0)])
        for (x, y) in [(0, 0), (15, 0), (0, 15), (15, 15)]:
            self.assertEqual(sheet.getpixel((x, y)), 1)  # whole 2x2-tile block filled


class TestEmitMotionS(unittest.TestCase):
    """Assemble the full banim motion.s text (oam_l, oam_r, script, modes sections).

    Clones the archer ranged cadence onto 3 beats (Ready/Wind-up/Peak): the arrow fires
    via call_spell_anim on the peak. Script references the _r oam offsets; oam_l mirrors
    1:1 so frame N sits at the same byte offset in both tables (engine flips by base).
    """

    def _frames(self):
        e0 = [{"attr0": 0, "attr1": 0x4000, "attr2": 0, "dx": -8, "dy": -8}]
        return [{"oam_r": e0, "oam_l": rb.mirror_oam(e0)} for _ in range(3)]

    def test_has_all_four_sections_and_globals(self):
        s = rb.emit_motion_s("rbg_ar1", self._frames())
        for sect in [".section .data.oam_l", ".section .data.oam_r",
                     ".section .data.script", ".section .data.modes"]:
            self.assertIn(sect, s)
        self.assertIn(".global banim_rbg_ar1_script", s)
        self.assertIn("banim_rbg_ar1_oam_r:", s)

    def test_attack_modes_fire_the_projectile_on_the_peak(self):
        s = rb.emit_motion_s("rbg_ar1", self._frames())
        self.assertIn("banim_rbg_ar1_mode_attack_range:", s)
        self.assertIn("banim_code_call_spell_anim", s)        # the arrow
        self.assertIn("banim_code_wait_hp_deplete", s)

    def test_references_all_three_frames(self):
        s = rb.emit_motion_s("rbg_ar1", self._frames())
        for i in range(3):
            self.assertIn("banim_rbg_ar1_oam_frame_%d_r" % i, s)
            self.assertIn("banim_rbg_ar1_oam_frame_%d_l" % i, s)

    def test_modes_table_is_12_modes_plus_12_zero_padding(self):
        s = rb.emit_motion_s("rbg_ar1", self._frames())
        modes = s.split(".section .data.modes")[1]
        self.assertEqual(modes.count("- banim_rbg_ar1_script"), 12)  # 12 named modes
        self.assertEqual(modes.count(".word 0"), 12)                 # 12 zero padding

    def test_oam_entry_emits_five_attr_fields(self):
        s = rb.emit_motion_s("rbg_ar1", self._frames())
        # the one OBJ in frame 0 right: attr0=0x0, attr1=0x4000, attr2=0, dx=-8, dy=-8
        self.assertIn("banim_frame_oam 0x0, 0x4000, 0x0, -8, -8", s)


class TestMeleeMotionS(unittest.TestCase):
    """The melee cadence (FE8 Pirate axe study): lunge in, swing, hit on contact, return.

    Differs from the ranged (archer) cadence cloned for RBG: NO projectile
    (call_spell_anim); the hit is banim_code_hit_normal on the swing-through; the unit
    lunges (start_attack_1/2 + start_opposite_turn) and dodges BACKWARD (dodge_to_back); and
    a melee unit cannot strike at range, so attack_range just holds the ready frame.
    """

    def _frames(self):
        e0 = [{"attr0": 0, "attr1": 0x4000, "attr2": 0, "dx": -8, "dy": -8}]
        return [{"oam_r": e0, "oam_l": rb.mirror_oam(e0)} for _ in range(3)]

    def _mode(self, s, name, abbr="brau_an1"):
        after = s.split("banim_%s_mode_%s:" % (abbr, name))[1]
        return after.split("\nbanim_%s_mode_" % abbr)[0]

    def test_attack_close_lunges_swings_and_lands_no_projectile(self):
        s = rb.emit_motion_s("brau_an1", self._frames(), motion="melee")
        body = self._mode(s, "attack_close")
        self.assertIn("banim_code_start_attack_1", body)        # lunge in
        self.assertIn("banim_code_sound_axe_swing_long", body)  # the swing
        self.assertIn("banim_code_effect_dirt_kick", body)
        self.assertIn("banim_code_hit_normal", body)            # melee contact
        self.assertNotIn("banim_code_call_spell_anim", body)    # no arrow/spell

    def test_melee_holds_the_lunge_through_the_hit(self):
        # match the Pirate cadence: the peak (frame 2, the lunged OAM) stays on-screen THROUGH
        # banim_code_hit_normal -- not a snap back to the resting frame 0 -- so the forward step
        # lingers like the donor's frames 2/3/5 instead of flicking.
        body = self._mode(rb.emit_motion_s("brau_an1", self._frames(), motion="melee"),
                          "attack_close")
        after_hit = body.split("banim_code_hit_normal")[1]
        first_frame = after_hit.split("banim_code_frame", 1)[1].split("\n")[0]
        self.assertIn("brau_an1_sheet_2", first_frame)   # holds the peak, not sheet_0 (rest)

    def test_melee_dodges_backward(self):
        s = rb.emit_motion_s("brau_an1", self._frames(), motion="melee")
        self.assertIn("banim_code_dodge_to_back", self._mode(s, "dodge_close"))

    def test_melee_cannot_strike_at_range(self):
        s = rb.emit_motion_s("brau_an1", self._frames(), motion="melee")
        body = self._mode(s, "attack_range")
        self.assertNotIn("banim_code_start_attack_1", body)     # no lunge
        self.assertNotIn("banim_code_hit_normal", body)         # no hit at range

    def test_ranged_motion_is_still_the_default(self):
        s = rb.emit_motion_s("rbg_ar1", self._frames())         # no motion= -> ranged
        self.assertIn("banim_code_call_spell_anim", s)
        self.assertNotIn("banim_code_dodge_to_back", s)


class TestMeleeLunge(unittest.TestCase):
    """Melee bakes a per-beat forward step into the OAM dx so the unit LUNGES into the swing
    like the donor Pirate (vanilla frame-2 mean dx ~ -40). Ranged keeps the static anchor."""

    def _frame_img(self):
        im = Image.new("RGBA", (24, 24), (0, 0, 0, 0))
        for x in range(8, 16):
            for y in range(8, 16):
                im.putpixel((x, y), (200, 40, 40, 255))   # one opaque 8x8 block
        return im

    def test_lunge_shifts_every_entry_dx(self):
        e = [{"attr0": 0, "attr1": 0, "attr2": 0, "dx": 5, "dy": -3}]
        out = rb._lunge(e, -40)
        self.assertEqual(out[0]["dx"], -35)
        self.assertEqual(out[0]["dy"], -3)                # dy untouched
        self.assertEqual(e[0]["dx"], 5)                   # original not mutated

    def test_lunge_zero_is_identity(self):
        e = [{"attr0": 0, "attr1": 0, "attr2": 0, "dx": 5, "dy": -3}]
        self.assertIs(rb._lunge(e, 0), e)

    def test_melee_peak_frame_lunges_forward_vs_ranged(self):
        imgs = [self._frame_img() for _ in range(3)]
        pal = [(0, 0, 0), (200, 40, 40)]
        melee = rb.build_battle_anim("brau_ax1", imgs, pal, motion="melee")
        ranged = rb.build_battle_anim("brau_ax1", imgs, pal, motion="ranged")
        # parse peak (frame 2) oam_r dx from each motion.s
        import re
        def peak_dx(s):
            after = s.split("banim_brau_ax1_oam_frame_2_r:")[1]
            body = after.split("banim_frame_end")[0]
            return [int(m) for m in re.findall(r"banim_frame_oam[^\n]*?,\s*(-?\d+),\s*-?\d+", body)]
        # peak lunges forward by MELEE_LUNGE_DX[2] (negative dx in oam_r) vs the static ranged frame
        self.assertEqual([d - rb.MELEE_LUNGE_DX[2] for d in peak_dx(melee["motion_s"])],
                         peak_dx(ranged["motion_s"]))
        self.assertLess(rb.MELEE_LUNGE_DX[2], 0)          # forward = toward the foe


class TestBuildBattleAnim(unittest.TestCase):
    """End-to-end driver: 3 frame images + abbr + palette -> sheets, agbpal, motion.s.

    Orchestrates the tested pieces (tile -> merge -> pack -> sheet) per frame against one
    shared anchor, then assembles the motion.s. Integration guard over the wiring.
    """

    def _frames(self):
        out = []
        for n in range(3):
            im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
            for y in range(8, 16):
                for x in range(8, 16):
                    im.putpixel((x, y), (200, 0, 0, 255))
            out.append(im)
        return out

    def test_returns_three_sheets_palette_and_motion(self):
        res = rb.build_battle_anim("rbg_ar1", self._frames(), [(0, 0, 0), (200, 0, 0)])
        self.assertEqual(len(res["sheets"]), 3)
        self.assertTrue(all(s.mode == "P" for s in res["sheets"]))
        self.assertEqual(len(res["pal"]), 128)
        self.assertIn("banim_rbg_ar1_script", res["motion_s"])
        self.assertIn("banim_code_call_spell_anim", res["motion_s"])

    def test_all_frames_share_one_anchor(self):
        # identical frames -> identical oam offsets across all 3 (same anchor used)
        res = rb.build_battle_anim("rbg_ar1", self._frames(), [(0, 0, 0), (200, 0, 0)])
        m = res["motion_s"]
        f0 = m.split("banim_rbg_ar1_oam_frame_0_r:")[1].split("banim_frame_end")[0]
        f1 = m.split("banim_rbg_ar1_oam_frame_1_r:")[1].split("banim_frame_end")[0]
        self.assertEqual(f0.strip(), f1.strip())


class TestTiler(unittest.TestCase):
    def test_skips_fully_transparent_cells_and_places_the_filled_one(self):
        # 16x16 = a 2x2 grid of 8x8 cells; fill only the bottom-right cell.
        im = blank(16, 16)
        for y in range(8, 16):
            for x in range(8, 16):
                im.putpixel((x, y), (0, 200, 0, 255))
        tiles, oam = rb.tile_sprite(im)
        self.assertEqual(len(tiles), 1)          # only the one non-empty 8x8 tile
        self.assertEqual(len(oam), 1)
        self.assertEqual(oam[0]["tile"], 0)      # first emitted tile
        self.assertEqual((oam[0]["dx"], oam[0]["dy"]), (8, 8))  # its cell's top-left

    def test_emits_one_tile_and_oam_entry_per_filled_cell(self):
        # fill the top-left and bottom-right cells with DISTINCT content -> 2 tiles
        im = blank(16, 16)
        for (ox, oy, col) in [(0, 0, (200, 0, 0, 255)), (8, 8, (0, 0, 200, 255))]:
            for y in range(oy, oy + 8):
                for x in range(ox, ox + 8):
                    im.putpixel((x, y), col)
        tiles, oam = rb.tile_sprite(im)
        self.assertEqual(len(tiles), 2)
        self.assertEqual({(o["dx"], o["dy"]) for o in oam}, {(0, 0), (8, 8)})
        self.assertEqual(sorted(o["tile"] for o in oam), [0, 1])

    def test_identical_cells_share_one_tile(self):
        # two cells with byte-identical content -> ONE sheet tile, two OAM entries on it
        im = blank(16, 8)
        for (ox, _) in [(0, 0), (8, 0)]:
            for y in range(0, 8):
                for x in range(ox, ox + 8):
                    im.putpixel((x, y), (10, 20, 30, 255))
        tiles, oam = rb.tile_sprite(im)
        self.assertEqual(len(tiles), 1)              # deduped
        self.assertEqual(len(oam), 2)                # both cells still drawn
        self.assertEqual([o["tile"] for o in oam], [0, 0])


if __name__ == "__main__":
    unittest.main()
