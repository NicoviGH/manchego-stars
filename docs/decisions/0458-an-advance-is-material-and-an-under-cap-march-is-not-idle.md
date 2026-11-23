---
id: 458
title: "An advance is material, and an under-cap march is not idle"
date: "2026-11-23"
section: "Combat System"
issues: [744, 699, 510]
---

# An advance is material, and an under-cap march is not idle

**Decided (Nicolas, 2026-11-23, #744), #510 step 9.** Amends ADR 0439 (the idle rule).

**The fault.** ADR 0439 counted any win, kill or counter-kill chance above `DUST` (1e-9) as an
advance. In Ch21 an all-wait plan with one unit in reach had a 0.0003 win chance: it read as
"baiting", ranked `idle = 0`, and outranked every under-cap plan, which only marched and so read
idle. charId 2 died to it at a 0.92 to 0.93 predicted death, three times (`m740c`: s4003 a2, a3;
s4005 a1). Report and replays: #744.

**The rule, two changes.**

1. **An advance is material.** A win, kill or counter-kill chance advances only above
   `M.ADVANCE_MIN = 0.05` (`planner.lua`). A weight, Nicolas's: 0.05 is the value replayed; the
   death caps run 0.01 to 0.15. The wound read follows: a needed red's wound is read on its
   survivor's mean HP (the plan's mean HP over the kill branches too, divided by the chance it
   lives), so a small kill chance's share is no wound either (a 4% crit, else a miss, on the
   boss).
2. **An under-cap march is not idle.** A plan with `max_exceed` 0 and `progress` above `DUST`
   (it brings a unit nearer its goal) ranks `idle = 0`. `idleOn` is still turned on only by a
   real advance (`pick()`), so a march never switches the rule on.

**What it changes.** ADR 0439 said nearing is idle. Now, once a real advance is on the board, a
safe march outranks an over-cap advance, as any admitted plan outranks any plan over the cap
(ADR 0384); only holds that near nothing stay idle. A winning sacrifice is played only when no
under-cap plan advances or marches.

**Kept.** Lord first (`first_game_over` leads): 5 of its 7 witnesses are real lord risk, and the
one floor replay on a lord case got worse (#744).

**Proof (ADR 0430).** Unit tests that fail without each part (`test_bot.lua`: a 3% bait, a 4%
crit on the boss, an under-cap march over an over-cap kill), and one replay of each Ch21 witness.
