---
id: 336
title: "A chapter plays its vanilla twin's music"
date: "2026-10-09"
section: "Art & Audio"
issues: [26]
---

# A chapter plays its vanilla twin's music

Nicolas, 2026-10-09, choosing ch06's hall music: "let's go with vanilla's music, and apply that
rule across the chapters." The twin is the chapter's `parity_reference`, the same vanilla
chapter its force is measured against.

**Map music** is the twin's whole `bgm` block (player, enemy and green phase, plus the
alternates), written by `apply_chapter_music`: a total pass beside fog and difficulty, read from
the vanilla decomp. Before it, no pass wrote the field, so every hosted chapter played its HOST
slot's music. Each chapter sits one slot after its twin, so that was the NEXT vanilla chapter's:
ch04 and ch05 had Distant Roads and Follow Me swapped, ch06 played Ch7's whole set, and the
prologue's green phase was Ch1's. `chapter_bgm(chap)` is the one lookup; anything that names
"the chapter's theme" (ch06's Messie scene) reads it.

**Scene music** follows the twin's cues beat for beat where our beat has a vanilla
counterpart: the same song for the same kind of moment (the opening backdrop scene, the enemy's
first appearance on the map, the victory sting, the closing reflection). ch06's opening is the
first: Solve the Riddle over the hall, silence as it ends, Raid! as the merfolk surface. A beat
with no vanilla counterpart keeps the staging Nicolas set for it (Messie's silent entrance).

A twin past the route split has no row yet: `twin_settings_index` refuses it, so the first
such chapter has to name its row and does not inherit a guess.
_Decided: 2026-10-09 (Nicolas)._
