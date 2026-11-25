---
id: 471
title: "A talker is staged where it meets the recruit, on the route an earlier attempt saw him walk"
date: "2026-11-24"
section: "Combat System"
issues: [766, 764, 510]
---

# A talker is staged where it meets the recruit, on the route an earlier attempt saw him walk

**Decided (2026-11-24, #766, the stage job of R2 in #764's plan).** It builds on ADR 0467 (the
timeline) and ADR 0468 (the Talk job's worth).

**Why.** A recruit the game's AI moves is priced where the talker meets him on his way
(`Goals.chance` reads `goal.path`, #699). But the march aimed at the tile he stood on, so a
talker behind him chased. Two gaps stood behind that:
- **The march's goal was his current tile.** `exploring` gave the Talk job the recruit's own tile,
  and the job had no deadline: a talker that could never reach him before he left was still sent.
- **The path stopped at the forecast's horizon** (8 enemy phases, `sight.lua` `CLOSE_HORIZON`).
  Vanilla Ch14's Rennac leaves 9 turns after he appears, so the last meeting turns were never
  read. R1's remembered routes (`Timeline.routes`) were written for this, and nothing read them.

## What changed

- **`Timeline.routeOf(memory, charId, classId)`**: a character's walk from the latest attempt
  that showed it, and the turn it arrived on. A slot id changes between attempts; the character
  does not.
- **`goals.lua` `runOn`**: a recruit's path is the forecast's phases, then the remembered route
  up to his removal (or the route's end when no removal is known). Phase k is read `turn + k -
  appearance` turns after he came, where the appearance is this attempt's (`ctx.appeared`), or
  turn 0 for a unit there at the start. **The forecast's phases stand**: the board as it is now
  outranks a memory of another play. A unit that has not appeared yet this attempt, or that no
  attempt saw walk, keeps the forecast alone.
- **`Goals.meeting`**: where and in which phase a taker meets a goal. It shares one read
  (`arrive`) with `Goals.chance`, so the march aims where the chance is priced.
- **`exploring`'s Talk jobs** read the recruit goals (`Goals.recruits`, the same goals
  `Goals.list` prices). A talker's job is worth the recruit's worth less the hire (ADR 0468)
  times its chance of meeting him. Its tile is the meeting tile. **A talker with no chance of
  meeting him before he is removed has no job**: per #764, a job no one can make in time is
  dropped, not chased. The Talk itself is still offered whenever the game offers it
  (ADR 0396).

## Effect on the old pairing test

`test_each_recruit_gets_its_own_talker` changed answer. Counting the chance, A takes T2 and C
takes T1, so both recruits are reached this turn. The old answer (the nearest pair first) left C
two turns from T2.

## Proof

- Unit tests that fail without the change: `test_timeline` (routeOf), `test_goals`
  (`test_a_recruit_path_runs_on_where_the_last_attempt_saw_him_walk`), `test_bot`
  (`test_a_talker_is_staged_where_it_meets_the_recruit`: both checks fail on main).
- **Planning cost.** `exploring` reads the recruit goals only when there is a recruit to Talk
  over. The closings read is shared, on `ctx`, with the planner's `Goals.list` for the same
  board, so a turn reads the forecast once, as before.
- Lua test time is unchanged: 0.72 to 0.73 s CPU against 0.72 s on main, run back to back after the review fixes.
- **Replay `s766a`, vanilla Ch14 s4003, two attempts, against `a470a` (main):**
  - Attempt 2 plays move for move as on main. L'Arachel talks Rennac over on turn 5, so the
    remembered route is never needed, and Rennac's turn-13 death (#743) stands.
  - Attempt 1 first diverges on turn 5. From then L'Arachel's job is the meeting tile (1,8),
    on Rennac's forecast walk west to his exit; on main it was his current tile, one turn
    behind him. **She does not play it:** her ends are (20,13), (14,13), (20,13), and from
    turn 9 no meeting is left. Rennac is missed, as on main. The job is right, but the
    per-turn planner does not play it. That is R3 (#767).
  - Attempt 1 won in 24 turns with 1 death (Colm, charId 9, turn 16), against 22 turns and
    0 deaths on main. **Its cause is untested.** The two games first differ on turn 5, where
    Eirika opens the (17,20) door in place of another unit's item use. The hypothesis to test
    is that the changed Talk jobs freed Eirika for the door, and that the door changed what
    reached Colm by turn 16. The test is one instrumented replay that logs every unit's job on
    turns 5 to 16. It waits for R3 (#767): until the planner plays the jobs, the stage job
    only moves the game around.

## A Talk's recruit is judged as a player unit on its tile (2026-11-25)

**Why.** The game's Talk turns a red recruit blue where she stands (`bmunit.c`
`UnitChangeFaction`), and the reds may strike her on the enemy phase after. The planner took her
off the map instead (`fx.gone`), so a Talk plan read no death for her. Vanilla Ch10's Amelia
(charId 0x12), comparing the played Talk plan's highest death read with her own death read in
the replan just after she joined: s4002 a2, 0.017 against 0.687, and she died that phase; s4005
a1, 0 against 0.653; s4005 a2, 0 against 0.95, dead the next turn; s4009 a2, 0 against 0.914,
dead that phase. On main s4002, where she lived, both read 0.

**What changed.** The judged phase (`sight.lua` `stagePhase`, which `enemyPhase` and the
lookahead's `nextPhase` both use) is told the plan's Talk targets (`plan.joined`). It turns each
one blue with the game's own `UnitChangeFaction` (`M.joinUs`) and reports her new blue id
(`.joined`). Her red id stays gone, so she never acts as an enemy. The planner reads her death
under that id as it reads a blue's: she is in `hit`, in `predict`, and in `protected` under the
style's cap. Her death costs a unit's loss in the judged score.

**Known limit.** The game lets her act on the turn she joins, and the bot replans her move. The
phase reads her where she stands, which can be worse than her best move.

**Proof.** `test_bot`'s `test_a_talked_recruit_is_judged_as_a_player_unit_where_it_stands`
fails 3 checks on the code without the fix (the phase is never told she joins; the Talk plan's
`max_die` is 0; careful Talks her into the reds' reach). `test_sight`'s `joinUs` block checks
the game call, the kept memory and her map cell.

**The way out, and the same cause elsewhere (2026-11-25).** Judging her death was not enough on
its own. On the replay, vanilla Ch10 s4005 a2 still Talked her at 0.94: every Talk variant
filled the talker's menu (Talk from (2,20), then Canto to (2,19), to (1,20), or none), every plan
the beam kept Talked, and the mend tries a unit's own other acts, which a recruit who just joined
has none of. The mend now tries the talker's other acts for her (`tries`, `p.joined`). Two more
places took a Talk's `fx.gone` for a death. The re-listing (`deadReds`, the change key) read her
tile as freed by a kill; a talked green kept a stale green entry beside her player-unit read.
Both now skip the plan's Talk targets (`talkedIn`, which the judged phase's `joined` uses too).
`test_bot`'s mend, re-listing and talked-green checks each fail without their fix.

**PR #773 review (2026-11-25).** The plan's HP on her (`plan.reds`) and the wear its counters
left on her weapon (`plan.redWear`) are staged after the join, so they follow her to her blue id
(`M.stageRedHp`, `M.stageWear`'s `joined`); before, she stood at board HP with no wear. A Talk
whose recruit finds no free blue slot is counted (`.unjoined`, the most per decision in the plan
cost, summed over decisions in the run record's `plans.unjoined`), never silently left unread.
Two of the review's changes were taken back on evidence. The fog read for her crashed: the fog's
strike is read on the real board, where she is still red and has no blue unit, so she gets none
(the fog is a tie-breaker; her death in the phase is read in full). And the mend keeps the
talker's other Talks over her: on vanilla Ch10 s4005 a2, turn 10, the plan that Talked her under
the cap was the mend's swap to a Talk with Canto to (4,21); with those tries dropped the Talk was
never made and the start missed its clean clear.
