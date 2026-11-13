---
id: 405
title: "The rank sees each offered goal act, and one plan without the Seize"
date: "2026-11-13"
section: "Combat System"
issues: [510]
---

# The rank sees each offered goal act, and one plan without the Seize

**The planner item fwd1 item D found (#510 comment 6842371541); Nicolas agreed to the order on
2026-11-12.** It extends ADR 0403's Seize plan and follows ADR 0396: an ordering, never a rule
that forbids.

**The error.** The beam decides which plans the rank judges, and the rank picks only among
those. Two decisions on main showed the beam hiding a goal from it:

- Vanilla Ch9, campaign 4006 turn 11: the lord's Talk to the recruit (enemy id 155) was offered
  and in none of the 8 plans judged.
- Vanilla Ch8, campaign 4001 turn 16: all 6 plans judged took the Seize while two chests were
  `feasible` and the thief had neared them every turn, so the rank's first key (forfeits) had
  nothing to choose between.

**The decision.** Beside the plans M.plan already judges (planner.lua):

- **A goal plan** (`kind = "goal"`) for each open ledger goal (`feasible` or `stalled`) whose
  Talk, Visit or chest the game offers and no plan judged so far holds: that act (the best by
  its own score where several units or tiles offer it), then the first judged plan's other acts
  where they still fit, as the mend keeps a plan.
- **A plan without the Seize** (`kind = "wait"`) while a ledger goal is `feasible` and every
  plan judged so far seizes: the first plan with its Seize left out, that unit holding. A
  `stalled` goal asks for none: it no longer holds the win (ADR 0403).

The rank is unchanged. A goal plan over the cap is still refused, and a Seize under the cap
still beats plans over it.

**What the runs say** (commit 40c04cca; one start each, two attempts: leads, not rates).

- **The mechanism: confirmed on both decisions.** Ch8 4001 attempt 1 turn 16 (run `goal8`):
  the plan without the Seize was judged, forfeits 0 against 2, and was played. Ch9 4006 attempt
  1 turn 11 (run `goal9`): the Talk plan was judged.
- **The outcomes: unchanged.** Ch9: the Talk plan is over the cap, a 30.8% chance the lord dies
  in the enemy phase after it, so the rank refuses it and both attempts play main's games
  (`acts_hash` 0d40a8e5 and 864cbd01). Ch8: on turn 17 the plan without the Seize is over the
  cap (63%; it carries the first plan's attack by unit 16 on enemy 148) and the Seize is played
  with the thief 5.2 turns from the chests: won in 17 turns, not 16, the chests still missed.
  Attempt 2 is main's game (the chests were already `stalled`).
- **So the block in both is the risk at the goal, not the beam**: a lord alone beside the
  recruit, and a wait the army cannot hold safely. That is what the escort (item E) and the
  look (item F) are for.
- **The frozen suite** (`suite --held-out`, instrument `629b4cfd2497+v2`): PROMOTED, 0
  regressions, 0 runs without a game result. Against main's kept runs of the same seeds, 7 of
  56 play different acts; each has the same outcome, deaths and missed rewards, two are shorter
  (vanilla Ch4 seed 1001: 8 turns to 7; Manchego Stars `e1-ours-ch07` seed 2002: 17 to 15).
  Emulated frames: 11,012,882 against main's 11,026,574. The suite was not refrozen.

**Not looked into.** On Ch9 turn 11 the played plan reads `forfeits` 0 and the recruit's row
is gone from the ledger on turn 12: the forfeit read did not see her leave. Whether a plan
without the Seize where every unit holds would have been under the cap on Ch8 turn 17 is
untested.
