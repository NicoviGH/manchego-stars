---
id: 224
title: "Ravisin's map sprite rides SCRIPTED_NEUTRAL_SPRITES, boss or not"
date: "2026-08-17"
section: "Operational Gotchas (durable)"
issues: [25]
---

# Ravisin's map sprite rides SCRIPTED_NEUTRAL_SPRITES, boss or not

She is ch05's boss, not a neutral, but the table's name describes its ORIGIN rather than its
rule. What it actually serves is *a raw pid wearing our own art*, which `classed_cast` never
sees — the same reason her bust, name and stats are all bound explicitly off the ch05 YAML.
Without a row her pid falls through `GetUnitSMSId` to `CLASS_DRUID`'s stock sprite: the hooded
**man** she stopped being when her battle animation landed, with her own committed sheets sitting
unused. That is the white moose's #24 failure exactly, and `assert_custom_art_pid_wired` now
guards her pid the way it guards the moose's.

The **cast palette** is right for her on the table's own test — she never changes faction
(hostile from spawn, never recruited, never converted; her death ends the chapter), so leaving
the faction ramp costs nothing, and only the cast bank can hold the exact black robe /
near-white skin / auburn hair her battle anim was hand-edited to. The sprite was chosen
**hoodless** for the same reason the anim was: her bust has no hood, and the mismatch being
closed is a hooded man standing in for her on the map.
