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

**What does not change, and the open follow-up.** Without `opts.idle` nothing reads the heal:
`advances()` only decides the idle rule. Outside it the bot still credits a fort chip through
`W.dealt` in `score()` (`planner.lua`, the attack branch), and the judged enemy phase and the army's
reply read the boss's unhealed HP. The same bias therefore persists in normal scoring. Modelling
the heal there moves every plan's score, which is a weight call and goes to Nicolas, not this rule.
The lookahead's second phase has the same gap: it reads `st.enemyHp` as the plan left it, with no
heal between the phases (`planner.lua`, the `reds` table built from `st.enemyHp` in the judged
phase).

**Details.** `terrainHeal` truncates toward zero as C's `/ 100` does and gives 0 for the units the
game skips (`Board.terrainHealSkips`: dead, not deployed, rescued, `US_BIT16`). It is required:
`Planner.healed` errors on a sight without it. `sight.maxHps` now reads every unit on the field,
so an enemy's `maxhp` is `GetUnitMaxHp` (weapon HP bonus included), the max the heal and its cap
use. `Planner.addHp` is the one owner of AddUnitHp's clamp: a staff heal, the plan's heal of a unit
that lives and the terrain heal all go through it.

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
