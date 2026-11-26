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
spare), and ADR 0379's premise "a stolen item never comes back".

**A clean clear is the state at the chapter's end (Nicolas, 2026-11-26).** A theft spoils it only
if the item is still lost when the chapter ends. An AI thief that holds the drop flag
(`US_DROP_ITEM`) drops its last item when a blue unit downs it, and `ActionSteal`'s `UnitAddItem`
puts the loot last (`bmmind.c`), so its theft is recovered by killing it; ADR 0379's "never comes
back" holds only for a thief without the flag. The record (`Botrun.unrecovered`) counts a
spoiling theft unless a later drop from the same thief gave the item back; the planner forfeits
(`stolen:<id>`) only a theft by a thief that keeps it (`Sight.dropsLoot`). A player thief may steal it back only with Spd at least the
thief's (`bmtarget.c` `AddAsTarget_IfCanStealFrom`); the bot plays no Steal yet.

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
- **The mend tries a robbed unit's way out** (`planner.lua`). Pricing the theft was not enough.
  Replay `i730b` (Ch16 s4005, turn 13): all 9 plans the planner weighed forfeited `stolen:7` (the
  Knight Crest, p up to 1.0), and every one kept Colm at (17,10), his march step, or attacking the
  thief. The mend tried the other acts only of units with a chance to die, and Colm's was 0. Now:
  - a unit a plan's `stolen:<id>` names is mended first (the forfeit ranks before any death): its
    own other acts, and every unit's strike on the thieves that rob it (`st.thieves`), as a green
    unit's strikers are tried;
  - a round that takes the plan under the cap with the theft still in it is not the last (replay
    `i730g`: Colm's mend, from the over-cap base, stayed over the cap; Eirika's took it under with
    Colm still robbed, and the mend stopped).

  Any act that only avoids a theft (a step away, a strike on the thief, a Trade or convoy give
  once built, #688) scores nothing on its own, so only the mend brings it to the judged phase.
- **Tried and reverted: a move list that keeps a holder out of reach.** A cut that made the
  careful and even gates refuse, and `bySafety` rank last, a tile a thief that keeps its loot could
  stand beside put Colm on turn 13 in the one such tile, the (19,1) corner; on turn 14 every act of
  his was robbed and the Crest went a turn later (replays `i730h`-`i730j`, which also lost Eirika
  on turn 18 where the original game won; untested whether the escape caused it). It refused
  tiles outright (ADR 0396: only the game forbids) and saved nothing. The Ch16 Crest is saved by
  handing it off (Trade or a convoy give, #688) or a player Steal back, not by running.
- `lock` pricing stays: a Chest Key ranks below the boosters, so its theft spoils nothing, but it
  still costs the chest the key would have opened.

**Not changed.** The rank's order (forfeits first) and every weight. A forfeit is yes/no on any
chance past `Goals.DUST`, as every forfeit is (FR-014).

**Proof.** `test_bot.lua`: a recruit whose Talk row stalled is still forfeit by its death; a
spoiling theft moves the holder off the thief's tile; with a beam and a final of one, the mend
moves the robbed unit off the thief's tile, goes on past the cap while the plan is still
robbed, and brings another unit's strike on a cornered holder's thief; a theft by a thief that drops its loot
forfeits nothing; `test_botrun.lua`: a theft a later drop gave back spoils nothing; `test_sight.lua`: `pilfer`'s `spoils` from the game's rank, `dropsLoot`. Each fails on the code before this change.
