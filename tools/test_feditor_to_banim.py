#!/usr/bin/env python3
"""Tests for the FEditor->decomp battle-anim importer (#90).

Where ref_to_battleframe FAKES a 3-frame anim from static poses, this transcribes a REAL
community FEditor animation (a `.txt` "For Each Frame" script + per-frame PNGs) into the
same decomp banim asset shape. The pure core here is the PARSER: turn the FEditor script
into structured modes of Frame/Cmd instructions, keyed by FEditor mode number. Format
grounding: https://fe-battle-animations.neocities.org/ (modes 1-12; 2 & 4 auto-handled) +
the vendored Lizard Brigand Wildling under engine/battle_anims/_vendored/wildling/.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feditor_to_banim as fb  # noqa: E402


class TestParseFeditor(unittest.TestCase):
    def test_one_mode_frames_and_commands_in_order(self):
        text = (
            "/// - Mode 1\n"
            "C03\n"
            "5 p- f0.png\n"
            "C1A\n"
            "~~~\n"
            "/// - End of animation\n"
        )
        anim = fb.parse_feditor(text)
        self.assertEqual(list(anim.modes.keys()), [1])
        self.assertEqual(anim.modes[1], [
            fb.Cmd(0x03), fb.Frame(5, "f0.png"), fb.Cmd(0x1A),
        ])

    def test_skips_hash_comment_lines(self):
        # Some FEditor exports carry a '#'-commented header ("delete # on import"); ignore them.
        text = (
            "#######################\n"
            "#02 lorm_sp1 Hoplite Item\n"
            "/// - Mode 1\n"
            "C03\n"
            "# a stray comment INSIDE the mode body\n"
            "5 p- f0.png\n"
            "~~~\n"
        )
        anim = fb.parse_feditor(text)
        self.assertEqual(anim.modes[1], [fb.Cmd(0x03), fb.Frame(5, "f0.png")])

    def test_mode_header_with_inline_comment(self):
        # Some exports annotate the mode header: "/// - Mode 1   #Melee Animation".
        anim = fb.parse_feditor(
            "/// - Mode 1               #Melee Animation\n1 p- f.png\n~~~\n"
            "/// - Mode 3   #Melee Critical\n1 p- g.png\n~~~\n")
        self.assertEqual(list(anim.modes.keys()), [1, 3])
        self.assertEqual(anim.modes[1], [fb.Frame(1, "f.png")])

    def test_real_vendored_unarmed_txt(self):
        # The smallest real Wildling script: 12 modes, 3 unique frames (000/001/002).
        path = os.path.join(os.path.dirname(__file__), "..", "engine", "battle_anims",
                            "_vendored", "wildling", "unarmed", "Unarmed.txt")
        with open(path, encoding="utf-8") as f:
            anim = fb.parse_feditor(f.read())
        self.assertEqual(list(anim.modes.keys()), [1, 3, 5, 6, 7, 8, 9, 10, 11, 12])
        # Mode 1 (melee) ends on the dodge/end code C0D and shows the 3 poses.
        files = [i.file for i in anim.modes[1] if isinstance(i, fb.Frame)]
        self.assertEqual(files, ["Unarmed_000.png", "Unarmed_001.png", "Unarmed_002.png",
                                 "Unarmed_001.png"])
        self.assertEqual(anim.modes[1][-1], fb.Cmd(0x0D))


class TestUniqueFrames(unittest.TestCase):
    def test_distinct_files_in_first_appearance_order(self):
        anim = fb.parse_feditor(
            "/// - Mode 1\n1 p- b.png\n2 p- a.png\n3 p- b.png\n~~~\n"
            "/// - Mode 3\n1 p- c.png\n1 p- a.png\n~~~\n"
        )
        self.assertEqual(fb.unique_frames(anim), ["b.png", "a.png", "c.png"])


class TestModeTable(unittest.TestCase):
    """FEditor mode N -> decomp 12-slot mode-table (slot = N-1); 2 & 4 auto-duplicate 1 & 3."""

    def test_missing_2_and_4_duplicate_1_and_3(self):
        anim = fb.parse_feditor(
            "".join("/// - Mode %d\n1 p- f.png\n~~~\n" % n
                    for n in (1, 3, 5, 6, 7, 8, 9, 10, 11, 12)))
        slots = fb.mode_table_slots(anim)
        self.assertEqual(len(slots), 12)
        self.assertEqual(slots[0], 1)   # attack_close      <- mode 1
        self.assertEqual(slots[1], 1)   # attack_close_back <- auto-dup of mode 1
        self.assertEqual(slots[2], 3)   # crit              <- mode 3
        self.assertEqual(slots[3], 3)   # crit_back         <- auto-dup of mode 3
        self.assertEqual(slots[4], 5)   # attack_range      <- mode 5
        self.assertEqual(slots[11], 12)  # miss             <- mode 12


class TestEmitLines(unittest.TestCase):
    def test_command_is_raw_0x85_escape(self):
        # C1A (hit_normal, 0x8500001A) emitted as the byte-exact raw escape.
        self.assertEqual(fb.emit_command(fb.Cmd(0x1A)), "\tbanim_code_85 0x1A")

    def test_frame_references_its_sheet_and_oam(self):
        line = fb.emit_frame("wild_ax", fb.Frame(5, "Axe_003.png"), 3)
        self.assertEqual(
            line,
            "\tbanim_code_frame 5, banim_wild_ax_sheet_3, 3, "
            "banim_wild_ax_oam_frame_3_r - banim_wild_ax_oam_r")


class TestEmitMotionS(unittest.TestCase):
    def _anim(self):
        path = os.path.join(os.path.dirname(__file__), "..", "engine", "battle_anims",
                            "_vendored", "wildling", "unarmed", "Unarmed.txt")
        with open(path, encoding="utf-8") as f:
            return fb.parse_feditor(f.read())

    def test_sections_and_mode_labels_present(self):
        anim = self._anim()
        frames = [{"oam_l": [], "oam_r": []} for _ in fb.unique_frames(anim)]  # 3 stubs
        s = fb.emit_motion_s("wild_un", anim, frames)
        for section in (".data.oam_l", ".data.oam_r", ".data.script", ".data.modes"):
            self.assertIn("\t.section %s" % section, s)
        self.assertIn("banim_wild_un_script:", s)
        # one script label per PRESENT FEditor mode (10), none for the auto-dup 2 & 4
        self.assertIn("banim_wild_un_mode_1:", s)
        self.assertIn("banim_wild_un_mode_3:", s)
        self.assertNotIn("banim_wild_un_mode_2:", s)
        self.assertNotIn("banim_wild_un_mode_4:", s)

    def test_every_mode_body_terminates_with_end_mode(self):
        anim = self._anim()
        frames = [{"oam_l": [], "oam_r": []} for _ in fb.unique_frames(anim)]
        s = fb.emit_motion_s("wild_un", anim, frames)
        # ~~~ becomes banim_code_end_mode; C0D stays a raw end_dodge just before it
        self.assertIn("\tbanim_code_85 0x0D\n\tbanim_code_end_mode", s)

    def test_modes_table_dedups_2_and_4_onto_1_and_3(self):
        anim = self._anim()
        frames = [{"oam_l": [], "oam_r": []} for _ in fb.unique_frames(anim)]
        s = fb.emit_motion_s("wild_un", anim, frames)
        modes = s.split("\t.section .data.modes")[1]
        words = [ln.strip() for ln in modes.splitlines() if ln.strip().startswith(".word")]
        base = "banim_wild_un_script"
        self.assertEqual(words[0], ".word banim_wild_un_mode_1 - %s" % base)   # slot 0
        self.assertEqual(words[1], ".word banim_wild_un_mode_1 - %s" % base)   # slot 1 <- dup
        self.assertEqual(words[2], ".word banim_wild_un_mode_3 - %s" % base)   # slot 2
        self.assertEqual(words[3], ".word banim_wild_un_mode_3 - %s" % base)   # slot 3 <- dup
        self.assertEqual(words[11], ".word banim_wild_un_mode_12 - %s" % base)  # slot 11


class TestBuildImport(unittest.TestCase):
    """The full image build: FEditor folder -> {sheets, pal, motion_s}, ref_to_battleframe tiler."""

    def _dir(self):
        return os.path.join(os.path.dirname(__file__), "..", "engine", "battle_anims",
                            "_vendored", "wildling", "unarmed")

    def test_returns_one_sheet_per_distinct_frame_plus_pal_and_motion(self):
        d = self._dir()
        res = fb.build_import("wild_un", os.path.join(d, "Unarmed.txt"), d)
        self.assertEqual(len(res["sheets"]), 3)     # Unarmed 000/001/002
        self.assertEqual(len(res["pal"]), 128)      # agbpal: 4 banks * 16 hwords
        self.assertEqual(res["sheets"][0].mode, "P")
        self.assertIn("banim_wild_un_script:", res["motion_s"])
        # the transcribed frames reference sheet_0.._2 (all distinct frames used)
        for i in range(3):
            self.assertIn("banim_wild_un_sheet_%d" % i, res["motion_s"])

    def test_single_anchor_shared_across_frames(self):
        # A frame drawn shifted vs the reference must produce shifted OAM (motion preserved),
        # not be re-centered per frame. Frame 001 (crouch) differs from 000 (stand), so at
        # least one OAM dx/dy differs between them under a shared anchor.
        d = self._dir()
        res = fb.build_import("wild_un", os.path.join(d, "Unarmed.txt"), d)
        # oam_r blocks are emitted frame 0,1,2 in order; grab their first banim_frame_oam
        blocks = res["motion_s"].split("banim_wild_un_oam_frame_")
        f0 = [l for l in blocks[1].splitlines() if "banim_frame_oam" in l]
        f1 = [l for l in blocks[2].splitlines() if "banim_frame_oam" in l]
        self.assertTrue(f0 and f1)
        self.assertNotEqual(f0, f1)


class TestSwatchStrip(unittest.TestCase):
    """FEditor 'For Each Frame' PNGs bake the 16-colour palette into a swatch strip in the
    top rows of the canvas. Left in, it (a) tiles as a garbage floating strip and (b) inflates
    the sprite bbox, throwing the OAM origin off horizontally + vertically. Strip it."""

    def test_clears_top_rows_keeps_sprite(self):
        from PIL import Image
        im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        for y in range(6, 12):                      # a sprite body in the middle
            for x in range(4, 12):
                im.putpixel((x, y), (200, 50, 50, 255))
        for x in range(8, 16):                      # the FEditor palette swatch, top 2 rows
            im.putpixel((x, 0), (100, 100, 100, 255))
            im.putpixel((x, 1), (120, 120, 120, 255))
        out = fb._strip_top_swatch(im, rows=2)
        for x in range(16):
            self.assertEqual(out.getpixel((x, 0))[3], 0)     # top rows cleared
            self.assertEqual(out.getpixel((x, 1))[3], 0)
        self.assertEqual(out.getpixel((6, 8)), (200, 50, 50, 255))   # body intact

    def test_real_frame_bbox_is_the_sprite_not_the_swatch(self):
        # Axe_000: swatch at (240-247, 0-1) inflated the bbox to x..247; stripped -> x..186.
        d = os.path.join(os.path.dirname(__file__), "..", "engine", "battle_anims",
                         "_vendored", "wildling", "axe")
        clean = fb._load_frame(os.path.join(d, "Axe_000.png"))
        x0, y0, x1, y1 = clean.getbbox()
        self.assertLess(x1, 200)        # no swatch column at x~247
        self.assertGreater(y0, 3)       # no swatch row at y~0


class TestQuantize(unittest.TestCase):
    """GBA OBJ palettes are BGR555 (5 bits/channel). Two 8-bit PNG colours that round to the
    same BGR555 ARE the same colour on hardware, so they must share one of the 15 slots -- else
    a 16-colour PNG spuriously overflows the palette (Lizardzerker's two near-identical yellows)."""

    def test_hardware_identical_colours_collapse(self):
        self.assertEqual(fb._quantize5((255, 255, 104)), fb._quantize5((248, 248, 104)))
        self.assertEqual(fb._quantize5((255, 255, 104)), (248, 248, 104))

    def test_already_aligned_colour_unchanged(self):
        self.assertEqual(fb._quantize5((48, 48, 216)), (48, 48, 216))   # 8-aligned = no-op


class TestFactionRecolor(unittest.TestCase):
    """Enemy classes need the enemy (red) faction palette, not the anim's native colours.
    The agbpal's 4 banks are faction-indexed (BANIMPAL_RED == 1); a recolor maps the anim's
    faction-blue 'clothing' colours to a red ramp so an always-enemy reskin reads as red."""

    def test_bluish_clothing_becomes_red_dominant(self):
        self.assertEqual(fb.enemy_red_recolor((48, 48, 216))[0] > fb.enemy_red_recolor((48, 48, 216))[2], True)
        r, g, b = fb.enemy_red_recolor((96, 152, 248))
        self.assertGreater(r, g)              # red now dominates
        self.assertGreater(r, b)

    def test_warm_colours_pass_through_unchanged(self):
        for c in [(224, 64, 0), (248, 168, 48), (32, 32, 32), (248, 248, 248)]:
            self.assertEqual(fb.enemy_red_recolor(c), c)

    def test_build_import_recolor_changes_pal_but_not_sheet_indices(self):
        d = os.path.join(os.path.dirname(__file__), "..", "engine", "battle_anims",
                         "_vendored", "wildling", "unarmed")
        plain = fb.build_import("wu", os.path.join(d, "Unarmed.txt"), d)
        red = fb.build_import("wu", os.path.join(d, "Unarmed.txt"), d,
                              recolor=fb.enemy_red_recolor)
        self.assertNotEqual(plain["pal"], red["pal"])                       # palette recoloured
        self.assertEqual([s.tobytes() for s in plain["sheets"]],
                         [s.tobytes() for s in red["sheets"]])              # indices identical


if __name__ == "__main__":
    unittest.main()
