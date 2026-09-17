---
id: 261
title: "A map sprite is 32x32 or it is nothing"
date: "2026-08-26"
section: "Operational Gotchas (durable)"
issues: [26]
---

# A map sprite is 32x32 or it is nothing

Established while sizing Messie for ch06, and every line of it applies to the next custom unit too.

- **The idle is a TWO-POSE BOB, not three drawings** (added 2026-09-03). FE8 holds frame 0 for 32
  ticks, frame 1 for 4, frame 2 for 32, frame 1 for 4 (`bmudisp.c`, the `GetGameClock() % 72`
  ladder). Both long holds are 32 ticks, so if frames 0 and 2 are different drawings the sprite
  SNAPS between two poses half a second apart and reads as jumpy. The cast's 32x32 beasts do not
  do this: white-moose's frame 2 is within 12 cells of frame 0 and its frame 1 is the whole
  silhouette shifted (0,+1) at **0.0% residual**; lupin and lycanroc-pack have frame 2 **byte-
  identical** to frame 0. So the shape to paint is: frame 0, frame 2 = frame 0, frame 1 = frame 0
  nudged one pixel down with only the head or neck retouched. Measured counter-example, caught
  mid-authoring: a Messie draft with 141 of 415 inked cells differing between the two held frames
  read as jumpy, and **no timing change can fix that** — the engine snaps by design.
- **What must not move is the SILHOUETTE, not every pixel** (refined 2026-09-03, the same day, by
  the next draft). Messie's finished sheet differs by 77 of 321 inked cells between the held frames
  and reads correctly, because every one of them is in the front FLIPPERS: body, neck and head are
  pixel-identical, so the eye sees a plesiosaur paddling rather than a pose swapping. The test is
  therefore *where* the cells differ, not how many — a localized moving part held against a fixed
  body is the two-pose bob doing its job, and a whole-silhouette redraw is the failure. Diff the
  two held frames and look at the map before judging the count.

- **32x32 is a HARD ENGINE CEILING.** `UNIT_ICON_SIZE_*` has exactly three values (16x16, 16x32,
  32x32) and `bmudisp.c` switches on them in five places. Bigger means new enum cases plus SMS VRAM
  we do not have spare — the same VRAM that already bounds the TESTCH bench. Braulo, Meesmickle,
  Wolfram, Baxby, Lupin and the white moose ALREADY sit in that top tier next to Manakete 2 and the
  Demon King. **There is no rung above them**, so "make it bigger" is never the answer.
- **Size reads as FILL, not as cell size.** The Demon King touches all four edges and reads huge.
  Baxby is the same 32x32 and reads tiny, because he sits centred with air around him. The moose
  earns its size with antlers — pure silhouette width. When a unit must read BIG, the spec is
  corner-to-corner, not a larger class.
- **Geometry is DERIVED from the donor, never from sheet pixels.** A 16x96 sheet is ambiguous —
  6x 16x16 vs 3x 16x32 — and only the wait table resolves it, which is what
  `map_sprite_tool.donor_sms_geometry` is for and what its docstring says outright. Inferring from
  pixel dimensions got Draco Zombie, Cyclops and Basil wrong in a single pass.
- **A map sprite carries NO palette of its own.** It picks a resident faction bank, so the palette
  stored in a decomp PNG is a leftover from whoever ripped it — the Demon King's is player-blue,
  and rendering him with it makes the final boss look like a frost golem. Render vanilla sprites
  through `graphics/unit_icon/palette/unit_icon_pal_enemy.agbpal`; ours are authored directly in
  `map_sprites/cast_palette.png` (a cast sheet's embedded palette IS that file, byte for byte).
- ⚠️ **`footprint:` in a unit YAML is NOT the size class.** It is an art-direction note for how big
  the creature READS in the world — "PC-sized", "cat-sized" — written explicitly AGAINST the frame
  in four files: *"sprite frame is 32x32 but the unit reads party-scale"*. It disagrees with the
  donor on eight of twelve units BY DESIGN. A session mistook that for drift and came within a
  review of deleting all twelve as stale. It does carry two meanings across files (Basil and Lupin
  use it as the engine size class) — worth one disambiguating line, never a delete.

**WALK vs GLIDE, and what it means for buying art tooling.** Our units split cleanly, and the line
is not the one you would guess:

- **WALK (15)** — basil, fire-imp, hlin-trollbane, lizard-wildling, lizardzerker, lupin,
  lycanroc-pack, ravisin, sahnar, skel-{axe,bow,lance,sword}, trex, white-moose. Every one is a
  **vendored community sprite** that arrived as a complete sheet, 9-15 unique frames of 15.
- **GLIDE (9)** — baxby, braulo, marty, meesmickle, pinky, prof-rbg, rootis, sclorbo, wolfram. The
  **original PCs, whose art we generated ourselves.** With no committed `_mu.png`, `synth_mu_sheet`
  tiles ONE idle pose into all 15 MU blocks, so they slide across the map without moving their legs.

So the gap is not "we cannot do walk cycles" — it is that **we can only get one by vendoring someone
else's sprite.** Any art tool is worth paying for exactly insofar as it closes THAT. The target is
documented on the moose's sheet in ch04's YAML: `side[0-4] / down[5-9] / up[10-14]`, 32x480, fourth
facing by H-flip. The success test is cheap and does not need a ROM: generate, then diff the frames
for uniqueness — a glide is 1 unique frame, a walk is 9+.

_Established: 2026-08-26, sizing Messie. Moved here from HANDOFF the next day: every bullet was
still true three sessions later, which is the test for belonging in this file rather than that one._

---
