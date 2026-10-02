---
id: 322
title: "Hlin carries a Killer Axe, and ch00's guards carry lances"
date: "2026-10-02"
section: "Combat System"
issues: [430]
---

# Hlin carries a Killer Axe, and ch00's guards carry lances

#430, after step 4. Hlin fights on Eirika's exact line (ADR 0319), yet ch00 still read x1.89
threat. The gap was the weapon triangle. Eirika's Rapier is a sword, and the Prologue's
bandits swing axes, so they hit her less and for less. Our guards swung axes at Hlin's axe,
which is neutral, and no axe can beat an axe.

**Measured, ch00 headline threat / clear-load:**

| Hlin | guards keep axes | guards carry lances |
|---|---|---|
| Hand Axe (before) | x1.89 / x1.52 | x1.14 / x1.44 |
| Iron Axe | x1.83 / x1.38 | x1.10 / x1.33 |
| Killer Axe | x1.83 / x1.19 | **x1.10 / x1.12** |

The reavers (Swordreaver, Swordslayer) reverse and double the triangle against Sephek's sword,
but their weight 13 on Hlin's Con 11 costs two points of attack speed, which gives most of the
gain back.

**Decided (Nicolas, 2026-10-02: "if it makes it feel more like parity then do it"):**
- **Hlin carries a Killer Axe**, equipped first. Her C axe rank already reaches it. Her Hand
  Axe stays second, for chip damage at range 2, and her Vulnerary third.
- **The two caravan guards are Soldiers with Iron Lances,** the same Lv1/Lv2 bodies. Hlin's
  axe beats a lance the way Eirika's sword beats an axe.

ch00 reads **PARITY: x1.10 / x1.12**. Her class, her line, Sephek, Scramsax and the story are
unchanged.

The prologue injector now reads the guards' class and both guests' inventories from the YAML
(`guest_items_for`; the Vulnerary goes through a local consumable map, because
`WEAPON_ITEM_ENUM` stays weapons-only), so a kit change authored in the chapter ships.
