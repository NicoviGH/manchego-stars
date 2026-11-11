---
id: 400
title: "First attempts: a death is graded by the plan that moved its unit, the mend goes on with no plan under the cap, and the fog read breaks ties only"
date: "2026-11-10"
section: "Combat System"
issues: [510]
---

# First attempts: a death is graded by the plan that moved its unit, the mend goes on with no plan under the cap, and the fog read breaks ties only

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

## 2. With no plan under the cap the mend goes on; the step back is not always judged

**The error.** With no plan under the cap the mend changed one unit, one round, so two units
each over the cap where they stood stayed a fallback.

**The call.** With none under the cap the mend runs again from the plan it found, up to
`MEND_ROUNDS` (3), so more than one unit may change. The audit records
`mend_rounds = { before, now }`.

**Built and taken out: the step back always judged** (every unit on its safest hold tile, kind
`back`, a plan the judge always met). On the Ch5 starts only 15 of 39 decisions with no plan
under the cap gained one (38%, under the plan's half; comment 6780145312): the board was lost a
turn earlier. On Manchego Stars ch03 it stalled the suite: with every forward plan over the cap
(66% to 98%), `back` was the only plan under it, so the bot alternated `back` and `unstall` for
40+ turns, and seed 1001 lost (comment 6782827664). Without it, both seeds won in 14 turns
with no stall. A plan under the cap that gains nothing should not beat the only way forward
forever (ADR 0396 rule 4: waiting is judged by what the board after it gains). A hold plan always on
offer is not how to decide when to hold and when to push (Nicolas, 2026-11-10). The look one
more turn ahead proposed for it (comment 6780629895) is dropped too: it modelled our next turn
as every unit stepping to safety, where a player attacks, heals and pushes (comment
6783348074). The planner still reads one enemy phase deep; that stays open without a design.

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

## The suite (`suite --held-out`, 2026-11-10)

- **First run, with the step back** (instrument `7a55592bc493+v2`): promotion refused, 2
  deterministic regressions, both new stalls on Manchego Stars ch03 (section 2).
- **Final run** (instrument `84d8eba48d70+v2`): **promoted, 0 regressions.** Five deaths that lived when
  frozen, unexplained (signals, not blockers): `ours-ch02/1001` 0x01, `ours-ch03/1001` 0x06
  and 0x10, `vanilla-ch5/1002` 0x06 and 0x08. Held-out 4 of 28 lost, none new since the
  freeze. SC-003: 2,685,802 `AiDecideMain` calls against the budget 2,988,937 (+7.8% on the
  frozen 2,490,781): within. `scout-ch6` lost both seeds on turn 2 to fog, as on main.
