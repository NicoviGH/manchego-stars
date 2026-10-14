---
id: 344
title: "A unit's art and its items each have one resolver"
date: "2026-10-14"
section: "Engine & Tech Stack"
issues: [491, 487]
---

# A unit's art and its items each have one resolver

Nicolas, 2026-10-14 (#491): consolidating duplicated logic is an optimization, not a design change.

**What a unit looks like is `inject.unit_art`.** It answers, per unit and chapter, the bust the build
dresses and the map sprite it wears, with that sprite's palette rule: `cast` (the bespoke cast bank,
whatever the faction), `faction` (a sheet already in a vanilla role layout, tinted by the faction
ramp) or `remap` (remapped onto its donor's role layout at build time, then tinted). The injector
passes keep their emission, because each writes a different ROM table and the order they claim SMS
ids in is part of the build. Their members, though, come from the registry, as does
`dressed_portrait_slots`. The four copies of the bust-slot writer are now one `dress_slot`. The wiki
draws sprites through the same registry and the same `remap_sms_palette` call (`idle_frame`).

**What an item id means is `inject.decomp.ITEM_ENUM`.** There is one id → `ITEM_` enum table for every
item a chapter, a unit or a twin names. `difficulty.ITEM_TO_WEAPON` is derived from it: the entries
`fe_combat` models. The #53 seam (cast weapons kept apart from the twins' monster weapons) protected
that reverse map, and the derivation protects it the same way without a second list.

Why: before this, the answer lived in thirteen places for art (cast and guest slot tables, the raw-pid
table, the ch02 chwinga recolour and sprite, the ch05 reliquary mugs, the Arena attendant, the
prologue guest list, the scripted-neutral table, the pre-recruit pass, the class reskins). Items had
eight copies: the weapons-only table, seven per-chapter `CHnn_ITEM_IDS` and a ch00 consumables map.
Every reader that was not the build rebuilt the answer and missed a path. The wiki drew Ravisin and
the white moose in stock class sprites, and the build itself once shipped the moose as a red hound.
The copies agreed only because nothing had made them disagree yet.

Proof: the injection fingerprint is byte-identical across all 16 ROM configurations, and the derived
`ITEM_TO_WEAPON` is entry-for-entry the old one. `DEAD_CONCEPTS` retires the old names.

_Decided: 2026-10-14._
