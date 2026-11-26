---
id: 477
title: "A door that unroofs a room brings its units out in the forecast"
date: "2026-11-26"
section: "Combat System"
issues: [766, 764, 767, 510]
---

# A door that unroofs a room brings its units out in the forecast

**Decided (#764's "After R4" item 3, worked as a root-cause investigation, 2026-11-26).** Corrects
`sight.lua` `openMap`, whose comment said "a door or wall is no roof".

**Why.** R4 lost Rennac (0x1C) in 14 of 15 vanilla Ch14 tries. He and about 10 reds start the
chapter in the corridor past the (22,17) door, loaded at the start (`UnitDef_088BBCAC`) on roof
tiles, so the game hides them (`UnitHideIfUnderRoof`: `US_HIDDEN | US_UNDER_A_ROOF`, read as
state `0x81` on every one of them in replay `q766d`). The door's map change removes the roof, and
`TriggerMapChange` then runs `UpdateRoofedUnits` (`bmtrick.c`, `eventscr_utils.c`), which brings
them out. The bot's sandbox opened a door by writing the map change by hand and skipped that
step. So every plan that opened the door was judged against an empty corridor, and no plan could
strike what the door revealed: the planner re-lists acts past a door on the board as read before
the plan, where those units are off the field.

## The rule

- **`sight.openMap` runs `UpdateRoofedUnits` by hand** (`sight.unroof`): a unit under a roof the
  change removes loses `US_HIDDEN | US_UNDER_A_ROOF`, is marked seen, and the entity maps are
  refreshed through `sight.refresh` (journaled). The judged enemy phase plays the room's units.
- **The planner's re-listing past a change** (`menusFor`) puts a roofed unit standing on a tile of
  that change on the field, so the acts past the door may target it.

Every door, wall or chapter alike. Nothing here names a unit, a chapter or a tile.

## Also in this change

Each decision's plan record carries `jobs`: every first job the strategy layer priced
(`bot.lua` `notePrice`), with its worth at chance 1, chance, expected loss on the way, net, turns,
meeting tile, and `chosen` when a unit's chain took it. #767's count reads it. Nothing in the bot
does.

## What it did and did not fix (replays, Ch14 s4005, attempts 1-2)

- **Forecast:** the turn-3 door decision's considered plans read death chances up to 0.52 where
  every one read 0 before (`q766a` vs `q766d`).
- **Play:** with both parts (`q766e`), attempt 1 waited to open the door until turn 4, and
  attempt 2 opened it on turn 3 and struck a revealed red the same turn, which no earlier run did.
  Attempt 2 won in 16 turns (18 before), 0 deaths. Attempt 1 won in 21 turns with 1 death (19 and
  0 before on the same start). The death is L'Arachel on turn 14, a `FALLBACK_SACRIFICE` turn:
  no plan was under the cap and the least bad left her at a predicted 0.61 (#743's case, #764's
  fix order item 5), in a game that had gone another way since the door's turn.
- **Rennac is still lost.** The one try that recruited him (`r768a14` a3) had three strikers
  beside the door when it opened, which killed 3 reds that turn, and L'Arachel then went through.
  In these replays the army was 4 to 8 tiles back when the door opened. Nothing yet gathers
  strikers before an act that releases a squad. That is multi-turn coordination, the job layer's
  "stage" and "clear" (#767).
- **Two leads, measured and not kept here.** (1) The Talk job's route loss reads death 0.995 to
  1.0 on walks where she died 0 of 4 times with the army around her. Counting only this turn's
  stop kept her job alive one turn longer (`q766f`). (2) A rule that held the door until a talker
  could meet him on his remembered walk did not move play on s4005. Both are on #766.

## Against ADR 0396's five tests

(1) It changes what the forecast reads, not a weight. (2) Orderings come from the existing score.
(3) Every door or wall whose change removes a roof. (4) It repeats no ordering. (5) No unit,
chapter or tile is named in the code.

## Proof

- `test_a_door_onto_a_roofed_room_brings_its_units_out` (sight) and
  `test_a_plan_strikes_what_its_door_unroofs` (planner) each fail on main and pass with the change.
- So does `test_a_plan_records_each_jobs_price`.
- Replays `q766d` and `q766e` are listed above.
