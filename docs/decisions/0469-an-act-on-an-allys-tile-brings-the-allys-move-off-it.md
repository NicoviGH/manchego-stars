---
id: 469
title: "An act on an ally's tile brings the ally's move off it"
date: "2026-11-24"
section: "Combat System"
issues: [766, 764, 754, 510]
---

# An act on an ally's tile brings the ally's move off it

**Decided (Claude, 2026-11-24, #766; Nicolas asked for the stall to be diagnosed and fixed).**
This extends the `vacate`/`aside` record of vanilla Ch8 (an act names the ally on its tile, and
that ally is offered a free tile). ADR 0396 holds: nothing is banned, and the plan still has to
win the rank.

**Why.** Vanilla Ch14 s4003 attempt 2, run `r766e`, ended `stuck` on turn 21. The way to the
throne goes through the double door at (17,2)/(18,2) (`ch14a-eventinfo.h`), which opens only from
(17,1) or (18,1). Tana and Artur, who hold no key, stood on those two tiles. One instrumented
replay (`r766f`) settled it:
- Colm (Lockpick), Innes and Forde were offered the Door from those tiles on every turn from 12
  to 20.
- None of the 4 to 16 plans judged each turn held it.
- `extend` refused an act on an ally's tile until some earlier act in the plan had moved that
  ally. The beam kept the allies' holds, and the stall breaker (`unstall`) tries each unit's act
  alone from the start board, so no plan ever moved them first.
- Every plan read 0 death chance, so the risk cap played no part. The talker-price change (ADR
  0468) only changed who reached the door first.

## What changed

- **`planner.lua` `extend`:** an act whose `vacate` ally has not acted in the plan first places
  that ally's best act by its own score (`a.own`) that ends on neither tile the act needs, then
  the act. If no such move fits, the act is refused as before.
- It goes one step deep: the ally's own move is not given another ally's move in turn.
- It applies to every act with a `vacate` (a door, a strike, a heal, a march), not to doors only.

## Proof

- `test_bot.lua` `test_an_act_on_an_allys_tile_brings_the_allys_move_off_it`: the Ch8 aside
  board with the beam cut to one plan of one act per unit. It fails before this change.
- Replay `r766g`, Ch14 s4003, two attempts:
  - Attempt 1 won in 20 turns with 0 deaths; Rennac was missed.
  - Attempt 2 **won clean** in 19 turns with 0 deaths. L'Arachel talked Rennac over on turn 5
    for 0 gold, Innes opened the door from (17,1) on turn 8, and Eirika seized on turn 19.
  - Before: `r765c` won both attempts and missed Rennac each time; `r766e` won attempt 1 and was
    stuck in attempt 2.
- Lua tests, three laps each, back to back: base user 2.11 s and 2.13 s, branch 2.25 s and
  2.12 s.
