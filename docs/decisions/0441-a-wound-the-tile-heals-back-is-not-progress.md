---
id: 441
title: "A wound the tile heals back is not progress"
date: "2026-11-21"
section: "Combat System"
issues: [709, 699, 510]
---

# A wound the tile heals back is not progress

**Decided (#709), #510 step 9.** Extends ADR 0439 (holding still is not a plan once the bot stalls).

**The bug.** `advances()` counted any expected wound on a unit the win needs as progress. In vanilla
Ch15 the last two enemies, Valter and Caellach, stand on forts. The game heals a unit on a heal tile
at the start of its own faction's phase: `MakeTerrainHealTargetList` (`bmtarget.c:587-608`) gives
`GetTerrainHealAmount(terrain) * GetUnitMaxHp(unit) / 100` to every unit below max HP, and
`TerrainTable_HealAmount` (`data_terrains.c:4085`) is 20 for a fort, 10 for a gate or a throne.
Under ADR 0439's idle rule the bot could not hold, so it chipped a fort boss for 1-4 and died to the
counter: the chip was healed back before the boss acted (35 of 55 deaths in #699's Ch15 measure).

**Decided.** `sight.terrainHeal(u)` asks the game (`GetTerrainHealAmount`, `GetUnitMaxHp`, ADR 0369)
for the HP the tile `u` stands on heals it. `Planner.healed(sight, e, hp)` is the one owner of
"HP after the heal": `min(max HP, hp + heal)`. `advances()` credits a wound on a needed unit only
as far as it outlasts that heal: `e.hp - healed > DUST`. The enemy stands on its tile through our
phase and the heal comes before it acts, so its tile now is the one that heals it. A kill chance, a
bait kill, a goal or a win chance advance as before: the heal does not touch them.

**The heal everywhere the bot reads an enemy's HP across a phase boundary (Nicolas: "a human sees
the fort healing so the bot should too").** One amount, `sight.terrainHeal` / `healAmount`
(sight.lua, the game's own read), applied at every boundary through one clamp, `Board.addHp`:

- The simulated enemy phase: `healReds` runs in `stagePhase` after the plan's red HP is written,
  so `enemyPhase` and `nextPhase`'s first phase begin as the game's do, before any enemy acts. The
  planner's `plan.reds` carries the unhealed HP the plan leaves.
- The lookahead's second phase: `nextPhase` runs `healReds` again after the army's reply and before
  the second phase plays. The army's reply itself needs none: the game heals at the start of the
  enemy's phase, so the reply, a player phase, sees the HP the first phase left.
- `W.dealt` in `score()`: a blow is credited only for the wound that outlasts the heal
  (`Planner.outlasting`, `healed(hp) - healed(hp - dealt)`, the whole blow where nothing heals).
  `st.healOf` is the plan's one read of each enemy's heal.
- `advances()` (the idle rule) as before: `e.hp - Planner.healed(...)`. Its rule and the idle
  ranking are unchanged; what counts as progress against a healing boss is a separate call.

`plan.reds` and `st.enemyHp` stay the unhealed HP the plan leaves, so no read counts a heal twice.

**Over the cap, a wound is not progress (G; Nicolas, 2026-11-21: "Yeah, try that").** Amends ADR
0439's "the least-risk advancing plan is then played" line. A plan under the death-risk cap
(`rank.max_exceed == 0`) keeps the rule above: a wound that outlasts the heal advances. A plan over
the cap counts a wound as progress no more; it advances only by a kill chance above `DUST`, a goal,
a carry or the win, as before. `advances()` returns `woundOnly` for a plan whose only progress is
the wound, and `advancing()` in `admit()` and `pick()` reads it against the rank. No new number.
*Diagnosis:* Caellach 47 HP on a fort (+9 a phase); the seven-unit assault of trace fix709c turn 27
took his expected HP 36.97 to 45.97 after the heal (nets 1.03), max_die 0.999, while the holds at
max_die 0 were rejected as idle (diag709b). *Kill chance:* only this phase's is read. A kill chance
on any red is a return of its own in `advances()`, ahead of the wound read, so a plan that reaches
the wound read has none. The lookahead's second-phase kill comes from `sight.nextPhase`, a search
made for the finalists after the judge, and `advances()` runs for every plan, so reading it would
be a new search per plan; ADR 0439 already leaves it out.

**Details.** `terrainHeal` truncates toward zero as C's `/ 100` does and gives 0 for the units the
game skips (`Board.terrainHealSkips`: dead, not deployed, rescued, `US_BIT16`). It is required:
a sight without it is an error where a blow is scored. `sight.maxHps` reads every unit on the
field, so an enemy's `maxhp` is `GetUnitMaxHp` (weapon HP bonus included), the max the heal and
its cap use. `Planner.healed` keeps the floor at the HP the unit stands on now and returns the HP
as given when nothing heals. `Board.addHp` is the one owner of AddUnitHp's clamp (a staff heal,
the plan's heal of a unit that lives, the terrain heal). `Board.bind` must export every
`Board.<name>` sight.lua reads: the emulator's Board is that table, and test_board.lua scans
sight.lua for the names (the first push of this change crashed every emulator run on turn 1 for
want of one).

**Cost.** The planner side adds one memoised `sight.terrainHeal` read per enemy per search and
arithmetic in `score()`. The sandbox side adds `healReds` to each judged phase: four memory reads
a red and, only on a heal tile, one `GetUnitMaxHp` call; the percent is read once a terrain.

**Evidence.** The 35 of 55 deaths and the Caellach count are from #699's measurement (comment
7071434440), not re-measured here. Replays (ADR 0430's light proof), all on `b640e-cs-s4003`/
`s4005` Ch15 starts:

- `s4005` attempt 1 (stuck in the measurement): still stuck, 30 turns, the same 2 deaths. Its loop
  is a different one: Innes shoots Valter from range for 6, Valter cannot strike back, and the
  fort heals 9 a phase. That is not the fatal-chip case and is no proof of this fix.
- `s4003` attempts 1-2 (`fix709c`). Attempt 1: won in 21 turns, 4 deaths (Valter killed 2 on
  turns 13 and 15, Caellach 2 on turn 21), not clean; originally won in 25 turns, 6 deaths.
  Attempt 2: lost in 27 turns, 4 deaths, all to Caellach (turns 18, 19, 24, 27); originally lost
  in 28 turns, 8 deaths, all to Caellach (turns 21 to 28). Not clean. The runs diverge at turn 18
  (the fix's Joshua kills Valter in one blow, where the original's Seth chipped Caellach for 7), so
  the original's chip turns do not recur. Unit-proven; the replay did not reach the case: the fix's
  Caellach deaths are not single-unit chips the fort heals back. They are plans of five to seven
  units attacking at once (turn 18 `spare`, turn 23 `assault`, turn 27 `assault`), played as
  `FALLBACK_SACRIFICE` with `max_die` 1.0, 0.9986 and 0.9998 while the holds were rejected as
  idle (`max_die` 0 on turns 18, 19 and 27). They advance under the rule. Why they read as
  advancing (a kill chance on Caellach, or a total wound past his 9-HP heal) is untested.
