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
for the HP the tile `u` stands on heals it. `Planner.healed(heal, e, hp)` is the one owner of
"HP after the heal" for one HP: `min(max HP, hp + heal)`, floored at the HP the unit stands on now;
a unit at 0 HP gains nothing. The survivors' share of an expectation that mixes a kill lives in
`Planner.outlasting` only. `advances()` credits a wound on a needed unit only as far as it
outlasts that heal: `e.hp - healed > DUST`. The enemy stands on its tile through our
phase and the heal comes before it acts, so its tile now is the one that heals it. A kill chance, a
bait kill, a goal or a win chance advance as before: the heal does not touch them.

**The heal everywhere the bot reads an enemy's HP across a phase boundary (Nicolas: "a human sees
the fort healing so the bot should too").** One amount, `sight.terrainHeal` / `healAmount`
(sight.lua, the game's own read), applied at every boundary through one clamp, `Board.addHp`:

- The simulated enemy phase: `healFaction(..., "red")` runs in `stagePhase` after the plan's red HP is written,
  so `enemyPhase` and `nextPhase`'s first phase begin as the game's do, before any enemy acts. The
  planner's `plan.reds` carries the unhealed HP the plan leaves.
- The lookahead's second phase: `nextPhase` heals each faction at the start of its own phase, as
  the game does (`MakeTerrainHealTargetList(gPlaySt.faction)`): the greens and our units on a heal
  tile before the army's reply, then the reds again after the reply and before the second phase
  plays. So the reply sees the reds at the HP the first phase left (no heal between a red phase and
  the player phase) and our units healed. Each phase is healed once: `stagePhase` heals the first
  red phase, `nextPhase` the rest, and nothing else heals.
- `W.dealt` in `score()`: a blow is credited only for the wound that outlasts the heal
  (`Planner.outlasting`): the whole blow where nothing heals; with a kill chance `k`, `k * hp` for
  the kill branch (the dead heal nothing) plus the surviving branch's wound that outlasts the heal,
  `healed(hp) - healed(hp - its mean damage)`. `st.healOf` is the plan's one read of each enemy's
  heal. `st.enemyHp` is an expectation over the kill and the survival, so the heal is applied to the
  surviving share only.
- `advances()` (the idle rule): `e.hp - Planner.healed(heal, e, hp)`. It needs no kill share: a kill
  chance above `DUST` has already returned as progress in the kill loop, so `hp` there is a
  survivor's, to within `DUST`. The wound loop returns on the first needed enemy that passes, but every
  such return is the same `(true, true)`, so its result does not depend on `pairs` order.

`plan.reds` and `st.enemyHp` stay the unhealed HP the plan leaves, so no read counts a heal twice.

**Over the cap, a wound is not progress (G; Nicolas, 2026-11-21: "Yeah, try that").** Amends ADR
0439's "the least-risk advancing plan is then played" line. A plan under the death-risk cap
(`rank.max_exceed == 0`) keeps the rule above: a wound that outlasts the heal advances. A plan over
the cap counts a wound as progress no more; it advances only by a kill chance above `DUST`, a goal,
a carry or the win, as before. Over the cap a wound counts whether or not its target heals (the call as Nicolas made it).
`advances()` returns `woundOnly` for a plan whose only progress is
a wound, and `advancing()` in `admit()` and `pick()` reads it against the rank. No new number.
*Diagnosis:* Caellach 47 HP on a fort (+9 a phase); the seven-unit assault of trace fix709c turn 27
took his expected HP 36.97 to 45.97 after the heal (nets 1.03), max_die 0.999, while the holds at
max_die 0 were rejected as idle (diag709b). *Kill chance:* only this phase's is read. A kill chance
on any red is a return of its own in `advances()`, ahead of the wound read, so a plan that reaches
the wound read has none. (`admit()` runs for every plan at the end of `judge()`, before `pick()`
reads `rank.max_exceed`, and again after the lookahead; `advancing()` reads the rank `admit()` has
just set. After that second `admit()` a finalist's `max_exceed` includes the second phase's deaths,
so a finalist is tested over the cap on the lookahead-extended rank and every other plan on the
first phase's. That is intended: the cap is the plan's death risk, and a finalist known to die in
the next phase is over it, as `rank.admitted` already treats it.) The lookahead's second-phase kill comes from `sight.nextPhase`, a search
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
arithmetic in `score()`. The sandbox side adds `healFaction` to each judged phase: it walks `byId` once per
call, one call in `enemyPhase` and four in the lookahead's `nextPhase` (red, green, blue, red), with
four memory reads a unit and, only on a heal tile, one `GetUnitMaxHp` call; the percent is read once
a terrain.

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
