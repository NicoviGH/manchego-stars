---
id: 217
title: "ch06 departs from its donor's terrain in 21 declared cells, and replaces forest composition wholesale"
date: "2026-08-28"
section: "Operational Gotchas (durable)"
issues: [26]
---

# ch06 departs from its donor's terrain in 21 declared cells, and replaces forest composition wholesale

> **Superseded in part (2026-09-03, #360):** the count is now **7**, not 21 — the boats became
> pockets that KEEP the donor's own impassable cells. See *"ch06's boats sit in POCKETS…"*. The
> reasoning below stands; only the number moved.

ch06 paints FE8 Ch13 (Ephraim) as a frozen lake. The departures from the donor's terrain are
deliberate, and all of them are DECLARED rather than tolerated.

**21 cells diverge, listed in the chapter YAML under `terrain_divergence`**, and
`validate_terrain_matches_vanilla` rejects any drift not on that list. The breakdown:

| cells | change | why |
|---|---|---|
| 16 | `TILE_2E` -> `FOREST` | the two village footprints, repainted as ice outcrops that are WALKABLE underneath (cliff art, forest terrain) |
| 2 | `VILLAGE_REGULAR` -> `FOREST` | the door tiles inside those footprints; there is no village terrain left on the map |
| 1 | `SEA` -> `CLIFF` | seals the dead south-west corner |
| 1 | `SNAG` -> `PLAINS` | the map-change pair, after the crossing opens |
| 1 | `RIVER` -> `BRIDGE_SNAG` | the other half of that pair |

The allowlist is per-coordinate on purpose. A blanket per-chapter opt-out would have re-opened
the ch05 fence->wall accident, where eleven cells changed role while looking right and would
have walled out our only flier.

**The south-west beach is NOT diverged, and that was the fix.** Vanilla has walkable SAND along
that coast; painting it as cliff had quietly closed the left-hand approach. Restoring the SAND
terrain byte (under the cliff art) re-opened it and brought the west boat from turn 10 to turn
6, matching the east -- the symmetric two-route split the donor's own layout creates. It cost
two entries off the allowlist rather than adding any.

**Forest composition is replaced, not retiled.** A frozen lake has no trees, so all 23 FOREST
cells become snow drifts drawn with snowy-bern's rough/rock art. The winter-retile invariant
(#193) preserves the vanilla artists' forest SEQUENCES; that guard assumes we are translating a
forest, and here the concept is gone from the chapter. This is the "deliberate
forest-composition departure is a new map-design decision" case that invariant names, taken
explicitly: `validate_vanilla_retile` now exempts exactly the declared cells, so a chapter that
merely retiles a forest is still held to the sequence.

**The drifts keep FOREST terrain, and that is load-bearing.** The snow piles are painted with
MOUNTAIN art but stamped `TERRAIN_FOREST` (+20 avoid, +1 def, cost 2) rather than left as
MOUNTAIN (+30 avoid, but IMPASSABLE to armour and horse). Measured on the painted map: as
Mountain, cavalry and Braulo reach 194 of 265 passable cells -- the drifts wedge into the spiral
and cut 71 cells off; as Forest, both reach all of them. The terrain byte is what keeps the map
playable for mounted and armoured units, not merely what grants cover.

**The outcrops are opened because vanilla's hostages are exposed.** Two of vanilla Ch6's three
civilians can be attacked from 4/4 sides on foot; only one sits in a 2/4 pocket. So boats that
can be reached and killed from every side is parity, not cruelty -- and it is what gives the
`CHECK_ALIVE` bonus its stakes.

**All of it lands in `snowy-bern-ice` alone.** That variant is snowy-bern with **4 palette
entries** changed and **21 metatiles** added in slots snowy-bern declares unused (19 stamped
FOREST, 2 stamped SAND); its `.4bpp` is byte-identical, so the copies cost no new tile ids.
`snowy-bern` itself and every map already shipped on it are untouched -- ch04 rides it, and
25.6% of ch04's pixels use the four recoloured entries, so an in-place edit would have restyled
a finished chapter. `tilesets_are_compatible_variants` derives that relation from the files
(identical `.4bpp`; `.bin` differing only at slots the BASE declares unused) so the learned
reskin, the protected-terrain targets and a seed `.mar` all carry across -- and an edit that
ever touches a live slot fails loudly instead of quietly
(`test_map_tileset.TestVariantCompatibility`).
_Decided: 2026-08-28 (Nicolas: "it's an artistic choice I made for this chapter, so don't do
anything to impact the core tileset or past maps")._
