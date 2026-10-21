---
id: 357
title: "The parity read rolls every enemy's stats as the engine loads them, once per career"
date: "2026-10-21"
section: "Combat System"
issues: [510]
---

# The parity read rolls every enemy's stats as the engine loads them, once per career

The party has been read over 1001 simulated careers since ADR 0311. Every enemy was still one
mean-value line, rounded per growth chunk (#510 step 4). The engine rolls each red unit at load
instead: `GetAutoleveledStatIncrease` (bmbattle.c) jitters growth x levels by
`NextRN_N(gn/4) - gn/8`, then `GetStatIncrease` rolls the remainder on 1RN. It does this once
per `UnitAutolevelCore` call, which `unit_load.growth_steps` lists.

- **`unit_load.autolevel_increase` is that roll, transcribed**, beside `_increase_bounds`, the
  range the wiki prints. `stat_increase` (`GetStatIncrease`) lives there too, and the party's
  `level_up` reads the same one.
- **A loaded enemy carries its own roll** (`difficulty.LoadedUnit.roll`: its growth chunks, and
  per stat the offset back to an unrounded, uncapped base). `enemy_careers` rolls it 1001
  times, seeded on the chunks, and caps each line at the class maxima (UnitCheckStatCaps). A
  unit that loads without growing (unflagged, unshifted) has one career, itself.
- **`party_matchup` reads every body once per career**, paired like the party's careers. Each
  body is shuffled on its own key, so two copies of one generic are independent draws, as two
  `LoadUnit` calls are. The mean line stays the planning number every other reader uses (the
  cast tables, the yardstick, the timeline).

**Why the mean line was wrong, not just coarse:** it rounded each chunk on its own. ch02's
Difficult raider (two 2-level chunks) read HP 24, the top of what it rolls (22-24, median 23),
and Def 3 and Spd 5 with growths of 10% and 20% rounded away. In the ROM it rolls Def 4-5 a
third of the time and Spd 6-7 two times in three, which costs party members their doubles.

**Proof in the engine:** the `ch07redstats` (Difficult) and `ch04redstats` (Normal) runs
logged 203 loaded stat values over 25 red units. Every one falls inside its unit's careers.
Graded against them, the 140 that can vary sit at a mean percentile of 0.493 (uniform is 0.5,
sd 0.024). 56 of the 203 differ from the mean line. No new emulator run was needed.

**What moved:** two verdicts, both on Difficult and both in the party half, not the force.
ch02 goes OK -> OFF: its party half reads x1.51 against ADR 0042's x1.43 ceiling, so the
accepted residual no longer applies, and it is not widened (#510). ch03 goes OK -> OFF on
clear-load x1.254, just past the band edge (it was x1.23); its force half improved, x1.12 to
x1.09. The model is not settled until a step stops moving verdicts, so step 5 follows.

**Cost, and why it went down instead of up:** with both sides rolled, almost no (enemy, member)
pairing repeats, so the old memo-per-distinct-pair approach cost 1.5-2.9x a read. Instead,
`party_matchup` reads each unit over all its joint careers at once. It passes a Combatant whose
stats are numpy arrays, and `fe_combat` and `ai_target` take either ints or arrays through
`max0`/`clamp`/`where`/`maximum`/`minimum`. The rules stay in one place; only the simulated
battle has an array branch, and `test_ai_target.OverCareers` pins it to the scalar one element
by element. A full Normal read went from 27s on main to 4.7s, and agrees with the slow version
to within 3e-14 (the order floats are summed in). numpy is imported lazily, so the pyyaml-only
checks job can still import these modules.
