---
id: 472
title: "A job blocked by enemies makes them clear targets, while the job can still be had"
date: "2026-11-25"
section: "Combat System"
issues: [767, 764, 510]
---

# A job blocked by enemies makes them clear targets, while the job can still be had

**Decided (2026-11-25, #767; approved by Nicolas the same day, #767 comment 7170318277).** The
clear job of #764's plan. It builds on ADR 0471 (a job is priced by the death on its way).

**Why.** In PR #773's last attempts, 7 rewards were missed, and none of them came down to
`progress`. In each case the way to the job was deadly. The death cap turned the holder back, or
its route loss outweighed the job, which was then dropped. In vanilla Ch14 s4002 attempt 2,
L'Arachel was Rennac's only talker, with a 78-87% chance of meeting him on turns 3-4. Her way north
read a 99.98% death, so the Talk was no job (#767 comment 7170884306). A player kills the enemies
that make the way deadly, then sends the talker.

## What changed

- **`routeLoss` reads the way**: besides the death chance, it gives the deadliest stop's death
  chance (`worst`). It also gives the enemies that strike the unit at a stop it may die on
  (`by`).
- **`exploring` marks blocked jobs.** A job is blocked when no taker can take it: every taker's
  way either costs more than the job is worth or has a stop over the style's cap
  (`Planner.CAPS`). Talks, villages and chests are all read this way.
- **`clearJobs`** makes each enemy on a blocked job's way a clear target:
  - **Its taker** is a unit with no other job whose forecast (`sight.attack`) kills the enemy as
    a kill is counted (`Planner.GONE`, likelier than not), with its own death within the cap.
  - **Its worth** is the blocked job's worth, shared over the enemies blocking it (no new weight,
    #764), less the death on the clearer's own way.
  - **The deadline:** the job's worth is counted from the turn the clearer reaches the enemy. It is
    the holder's own chance of making the job starting then (`Goals.chance` with `late`). So a
    clear that lands after the job closes is worth nothing (#764: a job no one can make in time
    is dropped, not chased).
  - **The goal** is the enemy's tile (`exploreGoal.target`). The plan record shows it as
    `goals[].clears`.
- **The planner** credits a plan that kills the clear job's enemy with the clearer's whole way
  (`progress`). Otherwise it would count only the way left from where the clearer ends.

## Proof

- **Unit tests:** `test_bot`
  (`test_a_job_blocked_by_an_enemy_sends_a_unit_to_kill_it`) fails without the change. Its
  checks: the clearer is sent, the kill is credited, and no clear is sent that lands after the
  job closes. That last check fails without the deadline rule.
- **Test time:** unchanged at 0.30 s CPU for `test_bot.lua`, base and branch run back to back.
- **Replays** (vanilla; each start, two attempts):
  - **Ch14 s4002** (`c767c`) plays as on main (`r767a`): won in 16 and 17 turns, no deaths.
    Rennac is still missed: his corridor holds six enemies, and they fall on turns 4-7, after he
    has gone through. Without the deadline rule (`c767a`), clear jobs chased his Talk west after he
    left, and the wins took 21 and 20 turns.
  - **Ch10 s4007** (`c767b`, against PR #773's `j766b`): in attempt 2, clear jobs on the enemies
    around Amelia from turn 7 let Artur talk her over on turn 9. `j766b` lost her in both attempts.
    In attempt 1, Kyle, sent to clear beside her, killed her with his counter in turn 9's enemy
    phase. Every plan judged on turn 9 forfeited her. That the turn-8 move set it up is untested;
    it is an open finding on #767.
  - **Ch10 s4002 and s4005** (`c767d`): both clean clears hold (15 turns each; `j766b`: 16 and 15).
