---
id: 145
title: "Adopting sprites, part 2 — Lupin (Lycanroc) + Sahnar (spectral skeleton)"
date: "2026-07-17"
section: "Art & Audio"
issues: []
---

# Adopting sprites, part 2 — Lupin (Lycanroc) + Sahnar (spectral skeleton)

Two more recruits' art adopted from community/non-FE sprites (#181). What generalizes:
- **Sources beyond PMD/Pokémon:** a plain DeviantArt overworld sheet works too. Lupin's map sprite is
  the **Midday Lycanroc** form from *"Rockruff & Lycanroc Overworlds"* by **princess-phoenix** (CC-BY 3.0
  — cleaner licensing than most FE-Repo assets). Get the signed image URL via the DeviantArt **oEmbed**
  endpoint (`backend.deviantart.com/oembed?url=…`) — the raw wixmp URL 401s without the token.
- **Hand-drawing identity details onto an adopted sprite:** Lupin's glasses were drawn per-frame,
  **anchored to the source's eye pixel** (detected by color) so they track the walk-cycle head-bob
  automatically — the eye moves, the glasses follow. Iterate the design on the un-recolored base first
  (bold vs thin, opaque vs clear lens, height, pupil), THEN recolor. Draw glasses only on face-visible
  directions (down + both sides); the back/up run has no face.
- **`base:` for a quadruped map sprite = geometry token only.** Lupin uses `base: Gwyllgi` (FE8's own
  dire-wolf: `{3 frames, UNIT_ICON_SIZE_32x32}` wait-table row) — apt AND correct geometry; the class
  stays Cavalier. Committed both the 32×96 wait + 32×480 MU (real directional walk from the sheet;
  right = engine H-flip of the side run), unlike Baxby's synth-MU.
- **The community has NO mummy — only skeletal undead.** Swept FE-Repo (40k-file listing) + FEUniverse +
  broader web (FFTA/Castlevania exist but can't port a battle **anim** into FE's frame format). Undead
  busts are green-zombie recolors or bare skeletons; undead sword **anims** are all skeletal monsters
  (Bonewalker/Wight/Specter). So a literal "mummy" = custom/generation for everything; a **skeletal
  revenant** is the cohesive, fully-sourced alternative. Sahnar took the skeleton route (Nicolas's call).
- **Trio cohesion via one artist + palette-lock:** Sahnar's map sprite + battle anim are a matched
  **Alexsplode** pair (the "Specter"); the portrait is **Glaceo**'s "Skeleton (Assassin)" bust. No single
  artist made all three, so the **portrait is the free variable** — recolor its robe to the map sprite's
  *exact* cast cloak shade (don't grab a mismatched premade undead bust). Match the map's dominant tone,
  not its lightest: the cloak read dark because idx1 dominated, so the portrait's hood bulk must be dark
  too (a big-canvas hood over-reads any light highlight). **Do NOT recolor the battle anim** — keep its
  native palette (Nicolas: it's polished/consistent; the skull + spectral glow are the throughline).
- **Recoloring an anim GIF:** remap by matching the source cloak RGBs on the composited RGBA frames
  (robust), or swap the GIF's palette entries directly (cloak lives in a contiguous index band).
- **Deferred anims now have a home:** Sahnar's Specter sword anim + Lupin's Lycanroc #0745 anim both ride
  the **#90 enemy-anim import pipeline** (`tools/feditor_to_banim.py`) once picked up — source pointers in
  the YAMLs + on #24 (Lupin) / #25 (Sahnar). Not vendored yet (re-fetch on pickup).
_Decided: 2026-07-17_

---
