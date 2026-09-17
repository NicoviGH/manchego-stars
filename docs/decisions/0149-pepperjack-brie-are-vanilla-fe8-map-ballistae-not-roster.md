---
id: 149
title: "Pepperjack & Brie are vanilla FE8 map ballistae (siege the party mans), NOT roster recruits"
date: "2026-06-20"
section: "Class Mapping & Promotions"
issues: []
---

# Pepperjack & Brie are vanilla FE8 map ballistae (siege the party mans), NOT roster recruits

RBG (an Artillerist artificer) builds his ordnance — the cannon-golem art (barrel snout, rope fuse) was always artillery — so they're implemented the **vanilla way**: a map-placed siege emplacement (ballista terrain + the ballista object), not a unit class. **No recruit slot, no `deploy_limit` cost**; their YAML carries `fe_stats.class: null` with `role: ballista`, because a ballista is map equipment, not a character. They appear from the vanilla ballista era — FE8 debuts ballistae in Ch10 "Revolt at Carcino" (Eirika route) → our ~Ch10 onward — as flavored emplacements on relevant maps; the party mans them like any FE8 ballista (`US_IN_BALLISTA`). They're a couple (Brie built for Pepperjack, Adam/Eve framing) with mirrored designs in opposing palettes, and speak Pokémon-style (each only says its own name — "Pepperjack!" / "Brie!"). Brie is the only female of the cast (`gender: female`). Combined concept ref → `data/portraits/pepperjack-and-brie.jpeg`; full flavor → `lore/pepperjack-and-brie.md`.
_Decided: 2026-06-20 (supersedes the 2026-05-29 "ordinary recruits, not summons" and the 2026-06-04 "join as regular FE8 units, not ballistae" framings — we don't break from vanilla, so ballistae stay map siege)_
