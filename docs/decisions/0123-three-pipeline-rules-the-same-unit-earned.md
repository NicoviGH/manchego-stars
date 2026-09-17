---
id: 123
title: "Three pipeline rules the same unit earned:"
date: "2026-08-03"
section: "Art & Audio"
issues: [206]
---

# Three pipeline rules the same unit earned:

- **A CASCADED pose sheet splits on ink, not on gutters.** The generator may lay its poses out
  diagonally so their bounding boxes overlap on BOTH axes with no transparent column or row
  anywhere — the gutter splitter then sees the whole page as one pose. `split_pose_sheet` now falls
  through to connectivity inside each gutter cell, and two rules keep a pose whole: a blob under
  `POSE_SHARE` of the biggest is that pose's own detached art (an impact spark's outer rays, a
  motion streak) and is merged into the nearest pose by real ink distance, never dropped; and two
  pose-sized blobs that merely sit within `gap` of each other are one pose (a raised paw across an
  empty column, a shadow under the feet) — only OVERLAPPING blobs are separate poses. **The
  non-obvious half is the per-pose ink MASK**: cascaded boxes intersect, so each crop contains a
  slice of the next pose's art and cropping the box alone tows a neighbour's feathers into the
  frame. Pixels below `ALPHA_ON` belong to no pose and are left exactly as they lie, which is what
  keeps a gutter-separated sheet splitting byte-identically (pinned against the shipped sources).
- **A subject with ONE dominant hue must reserve its identity colours.** The `<=15`-colour median
  cut is area-weighted, so a tan bird spent every slot on one tan ramp (13 shades of it) and the
  saddle, the crest and the eye vanished — he read as a monochrome blob. `reserve:` was built to
  rescue a single colour the art lacked (a carrot nose, a lens to paint with); the general rule is
  broader: **reserve the colours that carry IDENTITY, not the ones that carry volume**, sampled
  from the source art rather than invented. Three reserved entries cost nothing real here — twelve
  tans still carry the body.
- **Read the arc's fixed points off already-approved anims.** A new unit's placement is not free
  invention: the foe's near edge (x≈73) and a grounded mount's ground line (y=141) were MEASURED
  off the shipped, filmed frames of two approved units, and everything else was solved from
  geometry against them. Same discipline as the recorded body-height recipe — don't re-derive a
  number the cast has already settled.

**The debugging lesson, because it is the transferable part: SYMMETRY IS A HYPOTHESIS-KILLER, and
the swap is what proved it.** Baxby's assets verified clean at every offline stage — palette bytes,
sheet PNGs, PNG→4bpp round trip, sheet-packing collisions, OAM/`attr2` ranges, mode tables, frame
commands, and a full engine-accurate reassembly of every frame from sheet+OAM (0 mismatched pixels,
for both units). All of that only ever narrowed *where* the fault was not. What actually located it
was **giving Baxby LUPIN's assets and rebuilding**: the wolf rendered corrupt — in Baxby's colours
— which proved in one run that the fault was the SLOT, not the art, and pointed straight at a
palette rather than tiles. When two units differ only in which one works, stop auditing the broken
one's data and swap them. Corollary to [[verify via data, not pixels]]: correct data proves the
asset chain, and says nothing about what the engine does with it afterwards.
_Decided: 2026-08-03 (Baxby, #206)_

**Lupin's wolf pounce: the import path grows an OUTLINE, and the detail it cannot carry gets PAINTED (#206)**
Lupin fought as a stock red Cavalier — a man on a horse — because he rides `CLASS_CAVALIER` so the wolf can
*be* the mount. He takes the **imported** path (`poses_to_feditor` → `feditor_to_banim`, Pinky's), not the
faked 3-pose one, for the same structural reason Pinky did: a quadruped's attack **is travel** (coil → leave
the ground → land on the foe), and `descale_battleframe` deliberately PINS the feet.

- **The donor repoints ALL THREE Cavalier weapon slots** (`BANIM_DONORS['cavalier']`: SWORD, LANCE and the
  unarmed/`ITYPE_ITEM` entry). Any slot left vanilla is a slot where the wolf renders as a horseman, which
  is the entire defect. His ch04 kit is Iron Sword + Iron Lance (`CLASS_LOADOUT`), so both fighting slots
  are live. Baxby (#206's other half) is the same class and reuses the row.
- **Cadence and sound are read off FE8's OWN WOLF, `banim_mdg_at1`** (`CLASS_MAUTHEDOOG`, banim 0xB0 — what
  the rest of his pack fights as), NOT off the Cavalier donor: a gallop-and-thrust is the wrong rhythm for a
  beast that leaps. That yields the wolf sound codes (C5A opens, C5B just before contact, C5D on recovery,
  C20 the impact SFX), and it re-confirms the #24 rule from vanilla's own hand — its `attack_miss` is the
  attack body with **only** the hit code and impact SFX removed; `prepare_hp_deplete` stays.
- **Three OPT-IN manifest keys on the import path**, all defaulting off so Pinky's shipped frames re-render
  byte-identical (verified): `outline: true` re-strokes the silhouette in the palette ink — the faked path
  has always done this and the import path never did, which is why Lupin first read as a grey blob next to
  the eight finished anims; `sharpen:` pre-unsharps before the area shrink (his 1.6 = Wolfram's approved
  value); `reserve:` forces a colour into the ≤15-colour palette (the seam `descale --reserve` opened for
  Rootis's carrot nose) — here a **true white** that the grey art does not contain, to paint a lens with.
- **Measured, and it corrected the obvious guess: `sharpen` does not rescue small detail.** It rescues
  detail at or above one shrink cell; anything FINER comes out slightly *worse*, because the unsharp halo
  brightens exactly the neighbours the box filter then averages back in. Pinned in
  `test_poses_to_feditor.TestSharpen`. So sub-cell features have no generated answer at all.
- **Which is why the frames are HAND-PAINTED and are themselves the deliverable.** Lupin's spectacles land
  ~4×3 px with a sub-pixel frame stroke — and they are the whole reason #206 chose generated art over the
  FE-Repo wolf anims that were already free. Nicolas paints them at final size in the browser pixel editor
  (`tools/banim_paint.py`, which hands `map_sprite_editor` one shared window of the 248×160 canvas via its
  new `--frame WxH`), exactly as his MAP sprite already did. `poses.yaml` carries `hand_painted: true` and
  `poses_to_feditor` then **refuses to re-render without `--force`**.
- **Two ways that paint can be silently destroyed, both now closed.** (1) Re-rendering the frames — the
  guard above. (2) Re-opening the editor: the sheet is scratch *derived from* the frames, so the naive
  `edit` rebuilt it every run. Both nearly fired in one session (the frames were re-rendered mid-paint to
  add the white; only the saved sheet still held the glasses, and they were carried across by colour).
  `prepare_sheet` now KEEPS an existing sheet unless its shape changed or `--reset` is passed.
- **`tools/split_pose_sheet.py`** turns one generated sheet into per-pose sources: reading order over a
  GRID (not just a strip), and keying the baked ground shadow by **morphological reconstruction** — grey fur
  lands within ~40 of that teal in RGB, so any flat colour key wide enough to catch the ellipse's own
  gradient also eats the wolf. The shadow must go: the battle screen draws its own platform, and an
  airborne pose would tow a floating blob.
- **Trap worth naming: a unit's SLOT is `PORTRAIT_MAP`, its STATS are `STAT_DONOR`, and they differ.** Lupin
  is Duessel (0x1D) wearing Kyle's growths (0x11). Taking the donor for the slot put `PT_CHAR=lupin` on a
  unit that is not on the map; the injector's own output is what caught it.
