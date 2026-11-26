---
id: 475
title: "The planner forfeits what the record's clean clear loses: a spoiling theft, and an owed recruit's death whatever its row"
date: "2026-11-26"
section: "Combat System"
issues: [730, 711, 764, 510]
---

# The planner forfeits what the record's clean clear loses: a spoiling theft, and an owed recruit's death whatever its row

**Decided (Nicolas, 2026-11-26, #764's "After R4" item 1).** Amends ADR 0442 (a thief's steal is
priced from the simulated phase) and ADR 0452 (an owed recruit no one may Talk yet is a recruit to
spare).

**Why.** A clean clear is defined once, where the record is written (`botrun.lua`, `rec.clear`):
won, no death, no reward missing, no owed recruit missing, no theft the game ranks above the stat
boosters (ADR 0376, ADR 0379). The planner kept costs of its own, and in R4 (#768) two of them had
drifted from that definition:
- **A theft cost the plan only when it took a chest opener** (`lock`, ADR 0442). Whether a theft
  spoils the clear was already the game's own answer (`AiGetItemStealRank` against the Skl
  booster, `Sight.stealRanks`), but only the record read it. Vanilla Ch16: a Knight Crest or a
  Lockpick stolen from Colm (0x09) spoiled 8 of 14 tries and was the only spoiler of 4; the plan
  that walked him into the thief's reach cost nothing more.
- **An owed recruit's death cost the plan only while its Talk row was feasible**
  (`Goals.forfeited` counts feasible rows). Vanilla Ch10: Pirates ring Amelia (0x12), so every
  Talk plan is over the cap, her row goes, and Seth's (0x02) or Franz's (0x04) counter killed her
  as an ordinary red in 7 of 15 tries.

**What.**
- `Sight.stealSpoils(call, S, item)` is the one reading of ADR 0379's line, inside a sandbox. The
  record's `stealRanks` and the forecast's `pilfer` both call it; a forecast theft carries
  `spoils`.
- `Goals.forfeited` takes `owed` (every owed recruit on the field whose death is not the win: the
  loose ones of ADR 0452 and the ones a blue may Talk) and `stolen` (the units a spoiling theft
  robs in some judged branch). An owed recruit's death is counted once: by its row when the row is
  feasible, else as `"owed:<unit id>"`. A spoiling theft is `"stolen:<unit id>"`. Both are death
  or theft only: a win does not close them, so no row nobody can take holds the win (ADR 0452's
  reason, kept). `loose` is retired into `owed`.
- `lock` pricing stays: a Chest Key ranks below the boosters, so its theft spoils nothing, but it
  still costs the chest the key would have opened.

**Not changed.** The rank's order (forfeits first) and every weight. A forfeit is yes/no on any
chance past `Goals.DUST`, as every forfeit is (FR-014).

**Proof.** `test_bot.lua`: a recruit whose Talk row stalled is still forfeit by its death; a
spoiling theft moves the holder off the thief's tile; `test_sight.lua`: `pilfer`'s `spoils` from
the game's rank. Each fails on the code before this change.
