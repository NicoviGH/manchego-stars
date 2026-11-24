---
id: 465
title: "A unit's march distance reads its own movement costs"
date: "2026-11-24"
section: "Combat System"
issues: [730, 510]
---

# A unit's march distance reads its own movement costs

**Decided (Claude, #730), #510 step 9.** `sight.field(goal)` was one grid, on the seizer's (a
ground unit's) movement costs, and `bot.lua` read it as every unit's distance to a goal.

**Why.** An instrumented replay (`i730a`) of vanilla Ch10 showed Vanessa and Tana, the two
pegasus knights, standing on tiles the ground grid leaves unreached. `exploring` paired units
with goals by `marchLength`, found no way for either, and dropped both pairs, while the goal's
chance (`sight.turnsTo`) read each unit's own costs and called the village (11,15) feasible. The
plan counted on a trip no one was sent on, and the village was razed.

## What changed

`sight.field` is gone: `sight.march(unit, goal)` is the one owner of a unit's march grid (its
own movement costs). `bot.lua` `fieldFor` / `walkFrom` take the unit wherever the distance is one
unit's, and there is no unit-less read left in `bot.lua`. The grid is memoised per class and tile
by `costGrid`'s existing behaviour, not new here; the one new memo key is `stepsOnto`'s, which now
carries the unit because its field is the unit's.

- `marchLength` (pairing, `talkersOf`), `cutOff`, `lockedOnWay`: a flier on a cliff no longer
  reads "cut off" and is not routed to a door.
- `groundFor` (the march's progress), the `pickMove` field in the march, the wait and the Talk
  march, `meetingTile`, and the debug dump's `fd`.
- The obstacle chain (`obstacleTurns`, `viaObstacle`, `wallsOnWays`' `shorter`): the steps from
  an obstacle onto the goal's ground are divided by that unit's MOV, so they are read on that
  unit's costs, as `turnsFor` reads its walk.

**Left on the shared (lead unit's) costs, on purpose:** `sight.mapChange` is the chapter's map
change, cached per class, not a unit's walk; the village demand in `sight.lua` asks whether the
lead unit gets there (`turnsTo(u, tile, fieldUnit())`).
