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

**The decision.** Beside the plans M.plan already judges (planner.lua; each added through
`offer`, the one owner of "complete it, and add it unless it is there"):

- **A goal plan** (`kind = "goal"`) for each ledger goal, whatever its row's status, whose
  Talk, Visit or chest the game offers and no plan judged so far holds: that act (the best by
  its own score where several units or tiles offer it), then the first judged plan's other acts
  where they still fit, as the mend keeps a plan.
- **Plans without the Seize** (`kind = "noseize"`) while a ledger goal is `feasible` and every
  plan judged so far seizes. Two: the first plan with its Seize left out, that unit holding; and
  every unit holding, because the first plan's other acts can put the wait over the cap by
  themselves. A `stalled` goal asks for none: it no longer holds the win (ADR 0403).
- **No enemy phase is judged after the Seize.** The game plays none: the chapter is over. The
  judge played one all the same (older than this ADR), so a unit at risk anywhere on the map
  put the win over the cap. A plan that takes the Seize now meets no enemy phase and no
  lookahead phase (`sight.nextPhase`), and costs neither call; a counter to a blow struck
  before the Seize is still the cap's.

The rank is unchanged. A goal plan over the cap is still refused, and a Seize under the cap
still beats plans over it.

**What the runs say** (vanilla, one start each, two attempts: leads, not rates).

- **The beam no longer hides the act: confirmed on both decisions.** Ch9 4006 attempt 1 turn
  11: the Talk plan is judged. Ch8 4001 attempt 1 turn 16: a plan without the Seize is judged,
  forfeits 0 against 2, and is played.
- **Ch9's outcome is unchanged** (runs `goal9`, `goal9d`): the Talk plan is over the cap, a
  30.8% chance the lord dies in the enemy phase after it, and both attempts play main's games
  (`acts_hash` 0d40a8e5 and 864cbd01). The recruit (charId 18) left the map in the enemy phase
  of turn 11 (`missed_recruits`: `left_map`). Her ledger row had no `closes_on`, so the plan
  played read `forfeits` 0: the ledger does not know a recruit can leave. With it known the
  Talk plan would still be over the cap.
- **Ch8, campaign 4001 attempt 1, in three steps.**
  - First build (run `goal8`): the one plan without the Seize was played on turn 16 and was
    over the cap on turn 17 (63%: it carried the first plan's attack by unit 16 on enemy 148),
    so the Seize was played. Won in 17 turns.
  - With every unit holding (run `goal8b`): that plan was under the cap on turn 17 and played.
    On turn 19 the thief, alone in the west at 5 HP, was at 63.5%; every plan was over the cap,
    the Seize among them, so the win was not taken. She died, and the Seize came on turn 20: 2
    deaths. This is what showed the judge's error above.
  - With no enemy phase after the Seize (runs `goal8c`, `goal8d`, the final code): the bot
    waits turns 16 to 18 and seizes on turn 19. Won in 19 turns against main's 16, the same
    one death (charId 10, turn 10), the chests still missed.
- **The other three Ch8 attempts** (4001 attempt 2, 4004 attempts 1 and 2) play main's games:
  the chests were already `stalled`.
- **So what blocks both goals is the risk at the goal, not the beam**: a lord alone beside the
  recruit, and a thief alone on the road to the chests. That is what the escort (item E) and
  the look (item F) are for. Whether the judge's error is behind any of main's earlier late
  deaths on Ch8 is untested.
- **The frozen suite** (`suite --held-out`, final code, instrument `2374a75d5563+v2`):
  PROMOTED, 0 regressions, 0 runs without a game result, 4 of 28 held-out runs lost and none
  new. Against the last kept suite runs before this branch (instrument `6871bf3e35aa+v2`), 7
  of 56 play different acts; each has the same outcome, deaths and missed rewards, and two are
  shorter (vanilla Ch4 seed 1001: 8 turns to 7; Manchego Stars `e1-ours-ch07` seed 2002: 17 to
  15). Cost over the 56 runs: 6,570 judged enemy phases against 6,615, 11,012,599 emulated
  frames against 11,026,574; 2,695,079 `AiDecideMain` calls, within SC-003's budget of
  2,988,937. The suite was not refrozen.
- **Two suite runs were stopped part-way on purpose** (the review's fixes changed play under
  them) and have no result.
