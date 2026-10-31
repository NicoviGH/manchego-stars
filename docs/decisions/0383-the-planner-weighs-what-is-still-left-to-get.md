---
id: 383
title: "The planner weighs what is still left to get: each open goal's worth x the chance of getting it, and the win closes the rest"
date: "2026-10-30"
section: "Combat System"
issues: [510]
---

# The planner weighs what is still left to get: each open goal's worth x the chance of getting it, and the win closes the rest

**Decided (2026-10-30), #510 step 9, the planner's open item "Ch5's village at (5,1)".**
Design: #510 comment 6534885686; plan: #510 comment 6535169947.

**Why.** Vanilla Ch5 attempt 8 won turn 8 with no loss and Joshua recruited, and missed the
village at (5,1). Gilliam, sent there on turn 1, held still four turns of eight: a step toward
a goal earned a flat `progress` of 2, an HP an enemy might take cost `taken` 2, so any tile an
enemy reached lost to holding at zero chance to die. And the boss died on turn 8 with Gilliam
three turns short: the win counted 100,000 and nothing weighed what it closes (the game gives
Ch5's Guiding Ring at the chapter's end only with all four village flags set,
`EventScr_Ch5_EndingScene`). Nicolas rejected discrete rules for this ("hold the boss while a
village is open"): every chapter is different, and the bot should work out how to get
everything, helped by the guide and the goals.

**What the planner does now.**

1. **The goals** (`tools/playtest/goals.lua`, pure): every village and chest still open,
   every Talk recruit, each guide-claimed end-of-chapter reward, and each unit's own way to the
   objective (where its march heads: the Seize tile, the boss, the nearest enemy on Rout; none
   on Survive).
2. **Worth, from the game.** An item is FE8's `GetItemCost` (price x uses), the number the game
   sums for the party's worth. A village or chest whose gift a new player cannot know is the
   mean of every vanilla village gift (17 at HEAD, none of them gold); a House (its location
   entry's flag is 0: it never closes) the mean of every vanilla House (19: one item, the rest
   only talk), and no `villages` reward counts one; a guide's `reward` claim
   (new kind: `item`, `needs`) shares its item over the goals it needs, and is void once one is
   lost. A recruit is one death plus its items. A unit's way to the objective is one death
   shared over the army. Points per gold by style: careful 0.04, even 0.08, bold 0.15 (under
   careful no single item outweighs a life; under bold a good one does).
3. **Chance, from the board.** `GAMMA ^ (max(t, 1) - 1 + late)`, with `t` the taker's
   turns there on its own movement costs (`sight.turnsTo`: the game's extended movement map,
   cost / MOV, not rounded, so every step counts; through the door or wall that opens the way
   when one cuts it off, bot.lua `turnsFor`), `late` 1 once it has acted -- within reach, 1
   now and GAMMA for a unit that has acted, so taking a goal now beats waiting on it; 0 when
   the goal closes before the taker gets there. `GAMMA = 0.85` (one owner: goals.lua). It closes when a
   looter takes it: `sight.closings` plays the field's looters (a red whose own AI script holds
   `AI_CMD_PILLAGE`) up to 8 enemy phases forward with the game's AI, our units hidden from it
   (when it falls undefended), a taken tile left off the AI's loot lists so the looter goes on;
   it is read again when a looter or an open tile changes; and it times a guide-known wave (a reinforcements
   claim now resolves to the waves the chapter loads, `difficulty.arrival_waves`) from its
   spawn tile on its class's costs.
4. **Scoring.** A plan earns `sum worth x (chance after - chance before)`, in the beam, in
   each unit's menu ranking (an act alone) and in the judge (after the enemy phase, as each
   unit lives). This replaces the flat `progress`, `W.recruit` and the no-risk visit credit: a
   Visit or Talk takes its goal; an attack on a recruit or our counter felling it loses its
   goal (and costs the chapter when its death ends the game). A green recruit's death in the
   enemy phase costs one death, as any unit's does: the clear spoiled and the unit lost are one
   price, never two.
5. **The win** (a Seize; the boss's death, our blow or our counter in the enemy phase; a Rout's
   last red unit, counting those the fog hides) completes every unit's way to the objective and closes every other goal. It
   earns no sum of its own -- a later win is the same win, and a 100,000 credit would beat any
   goal -- only one death x (1 - GAMMA) for coming now rather than a turn later, so a chapter
   with nothing left to get is finished. `W.win` now prices only a death that ends the game.
   The boss's own damage credit (5x) is scaled by how much the win is wanted now (`bossWant`:
   the win-now worth against it plus every open goal's worth x chance). The mend tries the
   other acts of a unit whose counter may end the chapter: the beam cannot see that counter.
6. **Who goes where.** Exploring sends a unit by worth x the chance that unit gets there, so a
   fast unit wins a race a nearer slow one would lose.

**Measured (2026-10-30; main's bot on the same envs, since the new claims change the style
draw).** Lowest clean attempt, this branch vs main: vanilla Ch2 2 vs 1 (attempt 1 lost Ross to
a 0.33 roll main's plan also took at 0.37, and won); Ch3 1 vs 1 (3 of 3 clean); Ch4 1 (3 of 3);
Ch5 5 vs 9 (main, older env), with (5,1) taken; ours ch01 1 vs 1. Ours ch02 is never clean on
either (two greens die on turns 2-3): an existing gap. CPU per turn played, ours ch02: 1.51 vs
1.38 s (+9.6%), from the mend's extra judged plans; vanilla Ch2 and Ch3 per attempt inside
main's range; vanilla Ch5 attempt 8, 24.8 vs 25.5 s. Rounds and runs: #510 tuning comment.

**Not modelled.** A guide-claimed arrival whose claim is unresolved (an uncurated twin: Ch5x,
Ch9 on) closes nothing. A wave's arrival turn for a zone-triggered wave is `_UNPLACED_TURN`.
