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
- **Only fresh plan builders step aside:** the beam, the advance, the assault, the bait, the
  Seize and goal offers, and `unstall`. A replay of acts a plan already holds passes `exact`:
  `complete`, `rebuild`, the mends, the kept `rest` and the fog reorder. An aside there would
  silently swap an ally's own act for another (#770's review).
- **The beam carries a plan whose every unit is already placed** to the next depth as it is. A
  step aside places two units in one depth, and such a plan would otherwise extend to nothing at
  the last depth and lose its place (#770's review). The loss needs a last-depth beam that mixes
  such a plan with plans one act short that can still extend. No board built so far shows it
  (2026-11-24, #771): on three door boards, at beam widths 1 to 16 and per-unit widths 1 to 4,
  and on a fourth built for the mixed case, the result was the same without the rule. Either
  every plan in the beam was fully placed, or the beam or the advance built the same door plan
  in another order. So this is held by reading, not by a test.

## Proof

- `test_bot.lua` `test_an_act_on_an_allys_tile_brings_the_allys_move_off_it`: the Ch8 aside
  board with the beam cut to one plan of one act per unit. It fails before this change.
- `test_bot.lua` `test_the_door_is_opened_from_a_crowded_corridor_at_the_default_beam` (added
  2026-11-24): the Ch14 stall at the default beam. It uses the real row-1 positions of `r766f`
  attempt 2, turn 13, with the door locked to the keyless units and reach along the row only.
  Without the step aside it fails, and so does the test above. With it, board id 3 steps aside
  and id 10 opens the door from (17,1). The door plan wins on progress, 7.6 against 1.6.
- Replay `r766g`, Ch14 s4003, two attempts:
  - Attempt 1 won in 20 turns with 0 deaths; Rennac was missed.
  - Attempt 2 **won clean** in 19 turns with 0 deaths. L'Arachel talked Rennac over on turn 5
    for 0 gold, Innes opened the door from (17,1) on turn 8, and Eirika seized on turn 19.
  - Before: `r765c` won both attempts and missed Rennac each time; `r766e` won attempt 1 and was
    stuck in attempt 2.
- Replay `r766i`, after #770's review fixes, Ch14 s4003, two attempts:
  - Attempt 1 won in 22 turns with 0 deaths.
  - Attempt 2 won in 21 turns. L'Arachel talked Rennac over on turn 5, and there was no stall.
  - Rennac died on turn 13 in a plan that read him at 0.59 to die, over the 0.05 cap. The run
    first parts from `r766g` on turn 11: both runs played a `spare` plan that was not admitted
    (0.835 for some unit) over admitted beam plans, and Rennac's wait tile differs, (15,7)
    against (15,6). That death is #743's (over-cap deaths), not this record's.
- Lua tests, three laps each, back to back: base user 2.11 s and 2.13 s, branch 2.25 s and
  2.12 s.
