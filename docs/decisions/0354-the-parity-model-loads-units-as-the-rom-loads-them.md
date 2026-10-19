---
id: 354
title: "The parity model loads units as the ROM loads them"
date: "2026-10-19"
section: "Combat System"
issues: [490, 510]
---

# The parity model loads units as the ROM loads them

Every red unit in the parity model, ours and the twin's, now takes the engine's own load path
(`LoadUnit`, `bmunit.c`), described once as data in `unit_load.growth_steps` and read by both
`unit_load` (the wiki's stat ranges) and `difficulty.py` (the mean-value model):

- **Only a flagged unit autolevels.** A `UnitDefinition` without `.autolevel` loads at class +
  personal base whatever level it declares. Our side's flag is the YAML's `autolevel:`, which
  is what the injector emits. The model used to grow every unit, which read vanilla Ch7's
  Dorbulgruf at 63 HP where the ROM loads 37.
- **A promoted class takes GetCurrentPromotedLevelBonus()**: 9 levels, or 19 on Difficult.
  ch04's Entombed (`CA_PROMOTED`, flagged) loads at 43 HP in the ROM, and now in the model.
- **An autolevelled CA_BOSS or pid < 0x40 levels realistically**, from `baseLevel` on its
  personal growths (vanilla Ch13's Amelia and Cormag; none of ours).
- **The mode shift runs after, flagged or not**, for every red pid >= 0x3C. Difficult adds
  class-growth levels. Easy/Normal's penalty rebuilds from base and re-autolevels, which grows
  even an unflagged unit (`UnitAutolevelPenalty`).
- **Stats cap at the class maxima** (`UnitCheckStatCaps`).

**Proof in the engine:** `INSPECT.redStats` reads every red unit's loaded line off the map, once
per `PT_DIFFICULTY` (`ch04redstats`, `ch07redstats`). 259 ch07 stat reads and ch04's promoted
Entombed fall inside `unit_load.load`'s ranges.

**What it moved:** every chapter (#511's verdict diff, 9 of 32 cells flipped). Every chapter
lock was measured on the old model, so ch00-ch07 are unlocked in the same change (#510 step 1,
ADR 0353) and re-lock at #510 step 10. ch01 loses its accepted residual: its party half now
reads x1.415, past ADR 0042's x1.41 ceiling. Per #510, the ceiling is not widened to keep it green.
