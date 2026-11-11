---
id: 400
title: "First attempts: a death is graded by the plan that moved its unit, the step back is always judged, and the fog read breaks ties only"
date: "2026-11-10"
section: "Combat System"
issues: [510]
---

# First attempts: a death is graded by the plan that moved its unit, the step back is always judged, and the fog read breaks ties only

**Decided (Nicolas, 2026-11-10, "yes I approve all", then the step 4 amendment and its
follow-up the same night), #510 PR A.** The plan is #510 comment 6779357154; each step's witness
is on its own comment. These are the calls that change what the first-attempt number means.

## 1. An enemy-phase death is graded by the plan that moved its unit

**The error.** A death was graded by the phase's last plan (FR-003 as coded). A unit moved under
the cap and found over it by a later replan read `over_cap`, and `over_cap` was tested before
`fog`, so the cause table undercounted fog.

**The call.** `botrun.lua` keeps the plan that last moved each blue unit this turn and grades the
death by it; the phase's last plan when none did (a green, a carried unit). `montecarlo.py
calibration` prints, from kept traces with each play once, the judged phase against the played
one and each chapter's deaths by what the moving plan said, so each change is read the same way.

## 2. The step back is always judged; with no plan under the cap the mend goes on

**The error.** Pulling back together was not guaranteed to reach the judge (the beam could cut
it at any depth), and with no plan under the cap the mend changed one unit, one round.

**The call.** Every unit on its safest hold tile is one plan the judge always meets (kind
`back`), as the advance is. With none under the cap the mend runs again from the plan it found,
up to `MEND_ROUNDS` (3). The audit records `step_back = { before, now }`.

**What it did not do** (comment 6780145312): on the Ch5 starts, 15 of 39 decisions with no plan
under the cap gained one (38%, under the plan's half), so it is not Ch5's fix: the board was
lost a turn earlier. It stays because it costs nothing where it does not help and halved the
fallback decisions (37 to 19). The look one more turn ahead waits on Nicolas (comment
6780629895).

## 3. The fog read breaks ties only

**The error.** Fog was empty ground to every danger estimate, and the flat `W.fog` penalty sat
in `value`, where admission never read it.

**The read.** `Bot.fogRead`: a unit ending within `FOG_REACH` (6) of an unseen tile meets one
strike from the strongest enemy seen so far this attempt (`opts.seen`, botrun's: every red a
board showed out of fog), stood on the nearest unseen tile; `sight.fogStrike` asks the game's AI
from there, the unit its one target. `W.fog` is gone. Under fog the units the read threatens
move last, so what a sturdier unit reveals is planned around on the replan.

**The call (Nicolas, after four witnesses).** The read is a rank key, `fog` (`M.outranks`): the
summed chance over the plan's units, on the ways the plan does not end the chapter (a Seize
beside the fog is still a win). It comes after everything else the rank reads (goals, the win,
progress, value), before the death-chance tail. The cap reads enemies in sight only.

**What was tried, on the 9 campaigns' Ch6 starts, attempt 1** (one run a start; comments
6780781911, 6781405996, 6781704202, 6782312560):

| | before | in the cap | ranked after admission + follow | ranked after admission | tie-breaker |
|---|---|---|---|---|---|
| blue deaths (fog) | 14 (12) | 15 (11) | 14 (11) | 12 (10) | 13 (11) |
| green deaths | 14 | 23 | 22 | 22 | 12 |
| fallback decisions | 12 | 57 | 7 | 7 | 4 |
| turns | 7 to 12 | 10 to 20 | 7 to 42 | 7 to 36 | 7 to 16 |

- **Inside the chance to die** it froze the bot: nearly every useful Ch6 tile is beside fog, so
  68 of 87 fallback decisions were over the cap only through the fog.
- **Ranked right after admission** the army hung back from the fog, and the Bael reached the
  Civilians (turns 8, 9, 11); one start stalled at 97 turns. "The sturdy lead, the fragile
  follow" (only a unit the read cannot kill marches into unseen ground) changed neither.
- **No version moved the fog deaths.** Of the 11 in the first ranked witness: 3 came before any
  enemy had been seen, 4 the read put at 76% to 87% and no plan avoided, 4 it put near 0 and an
  enemy not yet seen killed. A first attempt cannot know what the fog hides.

**Where Ch6 goes.** A player learns Ch6 from losses: where the fog hid enemies, and the Bael's
clock (it reaches the Civilians about turn 7-8; seven guides send Vanessa east, research 0014).
Both are PR B's (retry memory and deadlines; plan comment 6779357154, PR B step 2).

## The suite (`suite --held-out`, instrument `7a55592bc493+v2`, 2026-11-10)

**Promotion refused: 2 deterministic regressions**, both new stalls on Manchego Stars ch03
(seed 1001: 11 stalls, 1 when frozen, lost on turn 47; seed 1002: 13, 2 when frozen, won clean
on turn 54), `idle_3` every three turns from turn 11 or 15 on. Their cause is untested; the PR
waits on it (#510 comment on the suite run). Also: 5 deaths that lived when frozen,
unexplained (signals, not blockers); held-out 3 of 28 lost, none new; SC-003 2,641,665
`AiDecideMain` calls against the budget 2,988,937 (+6.1% on the frozen 2,490,781): within.
