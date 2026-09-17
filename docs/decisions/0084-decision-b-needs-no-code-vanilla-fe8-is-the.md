---
id: 84
title: "Decision B needs (almost) no code — vanilla FE8 IS the spell economy (#9 delta audit)."
date: "2026-07-02"
section: "Weapon & Magic Systems"
issues: [9]
---

# Decision B needs (almost) no code — vanilla FE8 IS the spell economy (#9 delta audit).

Decomp-grounded findings (issue #9 has the full table): tome depletion (`bmitem.c
GetItemAfterUse`, high-byte uses counter), the uses/maxUses display on BOTH the item menu and
the stat screen, and gold-restock shops (`bmshop.c` sells fresh full-uses items at
`costPerUse × uses`; vanilla Ch5's vendor already stocks Fire + Lightning tomes) are ALL stock
behavior — and the primary-cantrip counts already sit in decision B's band (Fire 40, Flux 45,
Thunder/Lightning 35, Elfire/Shine 30). **Depleted tomes break-and-rebuy, no gray-out**
(Nicolas, 2026-07-02, settling the question posted on #9): a spent tome breaks and vanishes
like an iron sword — stock FE8 behavior IS the decision-B economy; a persistent grayed slot
would deviate from vanilla for no mechanical gain.
What remains is CONTENT, landing with its first consumer per the no-dead-code rule: a
`shops:` block + `ShopList_Event_*` injection when the first shop chapter is authored
(vanilla cadence: ~Ch5), per-PC `inventory:` → loadout wiring (today `CLASS_LOADOUT` ships
class-stock items; changing it alters playtested ch01 balance, so it rides a chapter slice
with an emulator pass), and secondary-cantrip `maxUses` overrides once the per-PC spell kits
assign them (the same data_items string-patch idiom the injector already uses elsewhere).
_Decided: 2026-07-02 (CLAUDE; resolves #9's engine half as already-vanilla; gray-out settled by Nicolas same day)_
