---
id: 410
title: "A door opens its whole map change, and a way may run through several doors"
date: "2026-11-14"
section: "Combat System"
issues: [510]
---

# A door opens its whole map change, and a way may run through several doors

On the scout lap, two Seize maps ended `stuck` in every attempt: Ephraim's Ch9 (12 of 12)
and Eirika's Ch14 (13 of 13). Every unit read no way to the throne (`breach -`), every plan
scored progress 0, and holding won the tie (#510 comment 6878903339). The breach read
(`bot.lua` `breachFor`) knew one obstacle, one tile deep: a tile both beside the goal's ground
and walkable from the unit. Ch9's south gate is four door tiles under one map change, and no
single tile is both. Ch14's throne is three doors in, the first onto a room drawn as roof
until that door's change uncovers it.

**Decision.** Two corrections to the same read, no new rule:

1. A door or wall opens what its map change opens. The game applies the change's whole
   rectangle (`ApplyMapChangesById`), so `sight.mapChange` reads its drawn tiles
   (`Sight.mapChangeTiles`, the one walk `Sight.openMap` also applies), and an obstacle opens
   the way when any of those tiles is beside the goal's ground. The steps through it are
   counted to that tile (`stepsThrough`).
2. A way may run through several obstacles, opened one after another as a player opens them.
   `breachFor` takes first an obstacle the unit can walk to, the nearest; else one it has
   turns to through others (`turnsFor`, which asks the breach again for that obstacle), the
   fewest. The march (`stepFor`) and its length (`marchLength`) step to the first obstacle
   of the chain, as they already did for a door's key.

**What it proved** (one attempt each, from the lap's saved starts): Ch14 won in 28 turns
with one death; Colm opened (17,19) on turn 2, Seth (10,14) on turn 6 and a third door from (17,1) on turn 15,
and the objective read a chance on turn 1 (0.17) where it read 0 before. Ch9 still ends
`stuck`, at the next wall: Colm, the one unit the read sends to the gate (every other unit's line says `breach -`), marches there and is offered
the Door, but opening it alone reads a 49 to 90% chance he dies, so the careful plan refuses
it; the units with no key read no way until the gate is open and hold in their corner.

**Cost.** The read adds no game call per decision beyond a change's tiles, kept for the run
(84 and 113 `GetMapChange` calls per attempt). Ch9 used 1.57 s of CPU per player phase
against 1.0 to 1.3 before (more units moving, 209 judged phases against 149); Ch14's 393 s
is its first real fight (1146 judged phases, 43 kills).
