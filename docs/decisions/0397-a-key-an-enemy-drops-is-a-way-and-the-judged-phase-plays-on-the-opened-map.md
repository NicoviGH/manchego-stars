---
id: 397
title: "A key an enemy drops is a way to a chest or through a door, and the judged enemy phase plays on the map the plan opens"
date: "2026-11-10"
section: "Combat System"
issues: [510]
---

# A key an enemy drops is a way to a chest or through a door, and the judged enemy phase plays on the map the plan opens

**Decided (Claude, 2026-11-10, on Nicolas's brief to make the bot clear vanilla's Eirika route
clean), #510.** Two model errors (ADR 0396 rule 5), both found in the kept records of
`starts --game vanilla` (seeds 4001-4010, #510 comment 6751678084; the plan, #510 comment
6758779876).

## 1. A key an enemy drops is a way

**The error.** A chest counted as a goal only while one of our units could open it now
(`goals.lua`: no taker, no goal). A door was a breach only for a unit already holding a Door
Key (`bot.lua` `breachFor`). So a chest whose key is on an enemy was worth nothing, and so was
the walk to that enemy.

**Witness.** Vanilla Ch5x: its two chests (4,8) and (5,8) sit in a room behind the door at
(4,10) (`ch5x-eventinfo.h`). Ephraim's party holds no key; the keys are drops
(`UnitDef_088B5AC8`, `itemDrop = 1`): a Door Key from the Armor Knight at (4,11), Chest Keys from
the Mage and the Fighter inside the room. In 84 attempts the Door Key reached us 24 times and a
Chest Key 8 times, never both. No attempt opened the door, and every one missed both chests.

**The fix.** `sight.keySources(u, terrain)` names the enemies whose fall gives `u` what opens a
chest or a door. That is the game's own drop (`US_DROP_ITEM`, the last item, `bmmind.c`) and
its own key check (`Sight.keyItemOpens`: `GetUnitKeyItemSlotForTerrain` with the item alone in
the bag, which also serves `INSPECT.isKey`). A fogged enemy is no source, since its bag is not
shown. A chest a unit has no key for has that unit as a taker while such an enemy stands. Its
turns (`turnsFor` / `keyWay`) are the walk to the enemy plus the walk on from that tile with the
key, and a door's key is fetched the same way on the way. The march heads for the key's holder
(`stepFor`).

The quantity is the goals' own turns and chance (worth x gamma^turns). There is no new
ordering and no ban, and no chapter or unit is named. Each part follows the game:
- A key behind its own lock is no way (the `seeking` set).
- A door counts as a breach only when its key's holder can be reached (`doorOpens` asks
  `keyWay`), so a wall the unit can strike stays its way through.
- A key opens the one lock it was fetched for (`keyed`), since a Door Key and a Chest Key are
  one use each.
- Only a red unit is a source: a green ally is never struck (ADR 0384).
- A cut-off unit strikes whatever its march steps to (`stepFor`), which can be a wall in front
  of the key's holder.

## 2. The judged enemy phase plays on the map the plan opens

**The error.** `sight.enemyPhase` and `nextPhase` staged our units, the enemies gone and their
HP, but not the plan's breaches. A door the plan opens, or a wall it breaks, was still shut when
its enemy phase was judged, so the enemies behind it could reach no one.

**Witness.** Vanilla Ch3, seed 4005, all 48 attempts: Colm opens the door at (6,9) on turn 8,
and the Brigand behind it kills him at a predicted 0% (`blindspot: unrevealed_killer`). With
fix 1 alone, vanilla Ch5x seed 4003 did the same: Forde opened (4,10) on turn 4 and the
Fighter and Mage inside killed him at a predicted 0% (`sandbox_fault: forecast_desync`).

**The fix.** The planner keeps the tiles a plan opens (a door act's door, a wall whose HP the
plan takes to 0) and hands them to both phases as `plan.opened`. The sight applies each change
before the phase is played (`Sight.openMap`), doing what a door's tile event (`EvtListDOOR`,
script 1: the map change alone) and `UpdateObstacleFromBattle` both do. That is
`ApplyMapChangesById` then `RefreshTerrainBmMap` on the change's rectangle: each base tile, and
its terrain from `gTilesetTerrainLookup`. It writes these through the journal itself rather than
calling `TriggerMapChanges`, because a game function's own writes are not journaled, and one
plan's open door then stood open in every later plan's phase (PR #596 review). It leaves out
the change's enabled bit and a wall's trap (no enemy's move reads them), and roofs (a door or
wall is none).

## Measured

Filled in by the PR (#510): the witnesses on Ch5x seed 4003 and Ch3 seed 4005, and the frozen
suite's promotion line (`suite --held-out`, ADR 0395).
