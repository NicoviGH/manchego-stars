---
id: 121
title: "Imported enemy battle anims: transcribe a REAL community animation, bind per-CLASS (#90)"
date: "2026-07-17"
section: "Art & Audio"
issues: [90]
---

# Imported enemy battle anims: transcribe a REAL community animation, bind per-CLASS (#90)

Where PCs get a FAKED 3-pose anim on a per-character `_u25` (above), reskinned ENEMY *classes*
(kobolds, fire imps) that carry a custom map sprite but animate vanilla in the close-up get a
REAL, FE-native community animation imported *whole* and bound at the class via
`ClassData.pBattleAnimDef` (generic enemies have no unique character id, so `_u25` can't apply).
`tools/feditor_to_banim.py` parses an FEditor "For Each Frame" `.txt` + its per-frame PNGs into the
decomp banim shape, reusing `ref_to_battleframe`'s OBJ tiler; `build_campaign.inject_enemy_class_battle_anims`
clones the donor class's `AnimConf`, repoints each weapon animId, and points the reskin clone class's
`.pBattleAnimDef` at it (additive; the donor class + its AnimConf stay byte-vanilla). Driven by a
`battle_anim:` block on each `enemy_class_reskins` entry (source dir + per-weapon `{dir,txt,abbr,wtypes}`;
`wtypes` match the donor AnimConf verbatim; optional `recolor:`). Off-by-one shared with #65: AnimConf
`.index` = animId + 1.

The non-obvious findings (so the next importer doesn't re-derive them):
- **The author's OAM is NOT shipped.** The pack's `.bin` is FEditor's Java project blob; the `.dmp` is
  only the compiled SCRIPT (it *references* OAM by offset but doesn't contain it). FEBuilder regenerates
  the tile placements from the frame PNGs at insert — so re-tiling the PNGs (what we do) is the required
  step, not reinvention. And we can't use FEBuilder itself: it's a Windows GUI that byte-patches a built
  ROM, whereas we emit decomp source the build compiles.
- **FEditor bakes a palette SWATCH into the top rows of every frame PNG** (the 16 colours as a strip).
  Left in, it tiles as a floating garbage strip AND inflates the sprite bbox — which shoved the OAM origin
  ~30px sideways (to the sprite edge) and off vertically. Strip the top rows; then anchor at the FE8 sprite
  pivot (`w/2, h*5/8` of the CLEAN bbox — the engine origin, learned from vanilla `banm_ax1` OAM, feet below).
- **Battle palettes have 4 faction banks** (`BANIMPAL_RED=1` for enemies). A community anim ships ONE native
  (often ally-looking) palette across all banks, so an always-hostile reskin needs a recolor into the enemy
  bank (`enemy_red_recolor`: faction-blue clothing → red ramp). Goblins kept their native palette (Nicolas).
- **Quantize to GBA BGR555 before counting palette colours.** Two 8-bit PNG colours that round to the same
  5-bit value ARE one colour on hardware; without quantizing, a hardware-15-colour anim (Lizardzerker) spuriously
  overflowed the 15-slot budget.
- **FEditor `.txt` carries `#` comments** (a "delete # on import" header AND inline notes on mode headers /
  command lines); strip everything after `#` per line, and read the mode number by regex.

Sources (F2U/F2E, credited in each `_vendored/*/CREDITS.md`): Lizard Wildling {Lenh} → kobold-grunt;
Lizardzerker {Seliost1} → kobold-blade (sword) + kobold-brute (axe); Goblin Spearman {Battle of Wesnoth,
scripted Norikins} → both fire-imp goblins (lance-only, so ALL weapon slots point at the one spear anim —
the axe fighter swings a spear too). Testing is unified on the TESTCH sandbox: it deploys one hostile of
every `enemy_class_reskins` slot, and `recordenemy` (PT_CHAR=<name>) baits any into a counter to capture its
anim — the enemy analogue of `recordanim` for the PC cast (the ch03-specific `recordkobold` was retired).
_Decided: 2026-07-17 (kobolds + fire imps, PR #90)_

**A PC flier rides the IMPORT pipeline (N frames) bound per-CHARACTER (Pinky, #90→PC)**
The faked 3-pose path (`_u25`, above) can't carry a flier: a hover-and-swoop needs real motion, not
three static poses. So Pinky (the army's flier — **he/him**, RBG's homunculus son) is the first PC to
merge the two pipelines: his anim is a REAL N-frame animation transcribed by `feditor_to_banim` (the #90
enemy path) but bound per-CHARACTER via `_u25` (not per-class). `build_unit_battle_anim` is the seam — a
`battle_anim.import: {txt, frames_dir}` block builds via `feditor_to_banim.build_import`; anything else
(a `frames:` list) builds the faked 3-pose. Both return the identical `{sheets, pal, motion_s}` shape, so
the per-character binding (clone donor AnimConf → append banim row → `gUnitSpecificBanimConfigs` → set the
char's `_u25`) is byte-for-byte the same either way. The donor is a new `pegasus` `BANIM_DONORS` row
(`CLASS_PEGASUS_KNIGHT`, `ITYPE_LANCE`) — it only supplies the AnimConf to clone + the lance slot to
repoint; `motion`/`cadence` are unused on the import path (the `.txt` owns the cadence).

`tools/poses_to_feditor.py` is the art bridge: hi-res poses → the 248×160 FEditor frames the importer
eats. It is the INVERSE of `descale_battleframe.py` — descale PINS the feet so the body never moves
between beats (right for a foot unit's static poses); a flier wants the OPPOSITE, so each pose sits at its
own spot on a shared canvas and the per-frame shift BECOMES the on-screen motion. The arc lives in a
`poses.yaml` manifest (one uniform downscale for every frame + per-pose `dx/dy`).

The non-obvious findings (a flier is fussier than a foot unit — the next one will hit these):
- **Facing:** flip source to screen-left (whole-cast convention; `descale` flips by default) AND make the
  dive/impact `dx` NEGATIVE — a left-facing unit strikes toward a foe on its left (like the melee lunge).
  Un-flipped, he faced away and moon-walked.
- **Scale + the ear-clip:** Pinky is the roster's SMALLEST (idle ~27×31, under the mages' 32×39). His ear
  clipped FLAT in-engine at larger sizes — not an OBJ-budget or a source crop, but his long **tail dragged
  the `w/2, h*5/8` anchor DOWN toward the feet, lifting the whole sprite into the arena's top clip line**
  (tail-less units don't). Shrinking him dropped the ear-tip clear. (If a future tailed/tall unit clips,
  the real fix is a body-based anchor, not just shrinking.)
- **Arc = vanilla, not the layout sketch.** Trace the DONOR's real on-screen path (rise high → dive → strike
  at melee range ~56px), not a directional mock-up. My first arc followed the concept-art layout literally
  and the impact sailed *past* the foe.
- **Flyback ≠ the attack reversed.** Playing the dive pose backward moon-walks (the pose points the wrong
  way for the travel). The return bounces UP into the upright hover pose and glides home.
- **Linger like vanilla.** Hold the apex (the hover) and the impact/swirl long (≈16 / ≈15 ticks); a flier
  that darts through every beat reads cheap. Vanilla lingers at the peak and the strike.

**Dodge timing is synced by `wait_hp_deplete`, and the trigger is in the SCRIPT, not on screen.** The dodge
(Mode 7/8) fought us hardest; the durable rules:
- `wait_hp_deplete` (`0x85000001`, the FEditor `C01` "NOP") is NOT a NOP — it PAUSES the animation until the
  attacker's hit resolves (the beat the MISS fires). Frames placed BEFORE it fire early (at `start_dodge`);
  frames AFTER it fire AT the resolution. Vanilla hops at `start_dodge` (before the wait) → reads early for a
  big hop. Put the hop AFTER `wait_hp_deplete` to sync it to the miss.
- A flier dodge needs its OWN frame: `Pinky_006` = the jump art placed BACK (`+dx`, mirror of the forward
  launch). Reusing `apex`/`mid` teleports him up the attack arc; reusing the launch jump lunges him forward
  INTO the strike.
- To hold the dodge "back" for the whole thrust (hop at full lance-extension, land as the enemy retracts),
  HOLD the back-frame across many ticks (a grounded beat after the wait to reach full extension, then ~50
  ticks on `Pinky_006`). Sub-frame timing is tuned by the durations, verified against the Soldier's
  lance-reach in the capture — read the TRIGGER (lance fully out / retracting), don't chase the on-screen
  "MISS" text (Nicolas).
