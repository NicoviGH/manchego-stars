---
id: 175
title: "A retile inherits vanilla's GIFT PLACEMENT, not just its terrain"
date: "2026-08-07"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A retile inherits vanilla's GIFT PLACEMENT, not just its terrain

**Which gift sits on which tile is vanilla's decision**, gated by
`assert_village_gifts_match_vanilla` for any chapter whose `map:` names a `vanilla_layout:`.
Deliberate divergence is one key on the village — `vanilla_gift_divergence: <why>` — and the error
message names it. **The default is inheritance because exceptions are rarer than re-deriving four
placements every time** (Nicolas, 2026-08-07); a from-scratch canvas is skipped, and so is a site
vanilla does not have (one we added rather than moved).

It earns a gate because nothing else can see it. Swap two gifts and the item set, the economy total
and the parity verdict are all unchanged — `difficulty.py` counts the SET, not the tiles — so
`make difficulty` still reads PARITY while the chapter's risk/reward is inverted. ch05 shipped that
way: `(12,19)` is the south-east site and the turn-2 eruption pair spawns at `(14,16)/(14,15)` beside
it, so vanilla puts its richest gift (Dracoshield, 8000g) on the site the first raiders reach and its
cheapest (Torch, 500g) at `(5,1)`, behind the whole enemy line. We had them swapped, paying the most
for the safest errand in a chapter whose structure *is* the race for the reward-sites.

Sibling of `validate_terrain_matches_vanilla` (a retile inherits vanilla's terrain), one layer up:
the rewards standing on that terrain.
