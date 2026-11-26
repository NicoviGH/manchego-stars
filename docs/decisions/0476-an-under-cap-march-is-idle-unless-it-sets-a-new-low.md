---
id: 476
title: "An under-cap march is idle unless it sets a new low"
date: "2026-11-26"
section: "Combat System"
issues: [698, 764, 510]
---

# An under-cap march is idle unless it sets a new low

**Decided (Nicolas, 2026-11-26, #764's "After R4" item 2).** Amends ADR 0458, part 2 (an
under-cap march is not idle).

**The fault.** ADR 0458 exempted from the idle rule (ADR 0439) any plan under the cap whose
`progress` is above `DUST`: one that brings some unit nearer its goal than this turn's board has
it. A shuffle always does, so once the stall reading fired the army kept moving back and forth
and never handed the turn to a plan that wounds the boss. R4 (#768): vanilla Ch15 6 of 14 tries
and Ch21 5 of 12 ended `stuck`. Over R4's Ch15 and Ch21 traces, on turns where the idle rule was on
and a march-exempt plan played, an admitted under-cap plan that struck a boss (Ch15's charIds
0x43 and 0x53, Ch21's 0x6C) was outranked by it in 4 of the 8 starts where the idle rule turned
on (Ch15 s4002, s4003, s4007; Ch21 s4003; #698).

**The rule.** A plan under the cap is exempt only when it sets a new low: some goal (the
objective's nearest unit, or a feasible or stalled ledger row's best taker, in the turns
`plan.nearest` reads) is nearer on the plan's end board than the army's best so far. The best so
far is the least of botrun's `lows` (every earlier phase's reading this attempt, passed as
`opts.lows`) and this board's reading; a goal no earlier phase read is measured against this
board alone, and one with no way to it on this board sets no low. "Nearer than the low" has one
owner, `Goals.nearer` (with `Goals.lowest`, the merge), which botrun's progress count now takes
too, so the stall reading and the idle rule cannot drift. `M.setsLow` applies it to a plan;
`rank.progress` is unchanged, so no plan's score moves.

**What it changes.** The idle rule now bites on a stationary boss: once the stall reading fired,
a shuffle is idle, and an under-cap wound on the boss (an advance) is admitted over it. Where no
plan under the cap advances, every plan is over the cap or idle and the order is as before
(`first_game_over` first): Ch21 s4005, where the only advance is an assault that ends the game,
still waits.

**Proof (ADR 0430).** Unit tests that fail without the change (`test_bot.lua`
`test_planner_idle_march_needs_a_new_low`, `test_botrun.lua`'s `opts.lows` check) and one replay
of each chapter, attempt 1 of R4's s4003 start (tags `n698a15`, `n698a21`, against `r768a15`,
`r768a21`). Ch15: won in 22 turns, not 24; the three deaths of turns 1, 5 and 7 are R4's own
(before the idle rule turned on), and R4's fourth, charId 0x13 to the boss 0x53 on turn 20, is
gone. Ch21: won in 33 turns, not 40, no deaths either way; turns 26-31 now read idle and the
boss falls on turn 33. Neither replayed try was one of R4's stuck ones: that the stuck tries
clear is for the R4 set over the whole fix order, as #764 plans.
