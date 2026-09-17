---
id: 88
title: "MVP weapons = stock FE weapons (no custom Might); personal weapons are post-MVP"
date: "2026-05-30"
section: "Weapon & Magic Systems"
issues: []
---

# MVP weapons = stock FE weapons (no custom Might); personal weapons are post-MVP

PCs carry plain vanilla FE weapons whose stats (Mt/Hit/Crit/Wt/uses) come verbatim from a stock
FE8 item, named in each inventory entry's `fe_base` field — there is **no custom Might authoring**.
Conventions:
- **Physical weapons use stock names** (Iron Axe, Hand Axe, Iron Bow, Iron Lance, Javelin, Heal).
  Visual identity rides on the **sprite/portrait art** (an Iron Axe can be drawn as an anchor).
- **Tomes keep an element-right flavor NAME but are mechanically the basic stock tome** (name-only
  reskin, stock stats): Rootis "Ray of Frost" = `Fire`; Marty "Shillelagh" / Meesmickle "Eldritch
  Blast" = `Flux`; Sclorbo "Frostsong"/"Withering Impression" = `Lightning`. This avoids a stock
  tome name (e.g. "Fire") clashing with an ice/fungal caster's element.
- **Personal/signature weapons return post-MVP** as story progression, each mapped to an FE
  equivalent (e.g. Braulo's "Ole Shipwrecker" → Killer Axe, looted at the Ch 10 frozen wreck). Their flavor names are parked in
  `lore/<pc>.md` ("Signature gear").
This resolves the old "weapon Might TBD" / "uses: null TBD" placeholders.
_Decided: 2026-05-30_

---
