---
id: 150
title: "Promotions are FE8's vanilla BRANCHED choice (the player picks at the Master Seal)"
date: "2026-05-30"
section: "Class Mapping & Promotions"
issues: []
---

# Promotions are FE8's vanilla BRANCHED choice (the player picks at the Master Seal)

Every promoting class has two vanilla options (`fireemblem8u/src/classchg-data.c`); each unit YAML
lists the `branch` + a thematic `default` (in **bold**):
- Braulo: Pirate → {Warrior, **Berserker**}
- Marty: Shaman → {**Druid**, Summoner} — Druid = his D&D class name; Summoner = the Summon command
- Meesmickle: Shaman → {Druid, **Summoner**}
- RBG: Archer → {**Sniper**, Ranger}
- Rootis: Mage → {**Sage**, Mage Knight}
- Sclorbo: Priest → {**Bishop**, Sage}
- Wolfram: Armor Knight → {**General**, Great Knight}
- Pinky: Pegasus Knight → {**Falcon Knight**, Wyvern Knight}
_Decided: 2026-05-30 (fixes the illegal Monk→Summoner and the non-existent "Dark Sage")_
