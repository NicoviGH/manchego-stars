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

**What does not change.** Without `opts.idle` nothing reads it: `advances()` only decides the idle
rule. The plan's score and the judged enemy phase are untouched: the wound's `W.dealt` credit and the
army's reply still read the HP the plan leaves, unhealed. Modelling the heal there changes how every
plan is scored, which is a weight call, not a game rule, and is left to a measurement. The
second phase's HP in the lookahead is the same.

**Replay (ADR 0430's one game).** Vanilla Ch15, b640e-cs-s4005, attempt 1 (stuck in the #699
measurement, 30 turns): still stuck on turn 30 with the same two deaths. Its loop is not the fatal
chip. Innes shoots Valter from range for 6, Valter cannot strike back, and the fort heals 9 each
phase. The chip is now read as no progress, but no plan advances in that board, so the idle rule
stays off and the hold-or-chip order is as before. What the board needs is a plan that kills Valter
(45 HP, +9 per phase): that is a separate fault, not this rule.
