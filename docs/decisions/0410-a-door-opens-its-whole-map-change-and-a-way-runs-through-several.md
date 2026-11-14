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
   rectangle (`ApplyMapChangesById`), so `sight.mapChange` reads the change's tiles the
   march can walk once it is applied (`Sight.mapChangeTiles` with the field unit's movement
   costs: the walls a change also draws are no ground), plus the obstacle's own tile. An
   obstacle opens the way when that ground touches the goal's ground; the steps through it
   are walked over that ground alone (`stepsThrough`).
2. A way may run through several obstacles, opened one after another as a player opens them.
   `breachFor` takes first an obstacle the unit can walk to, the nearest; else one it has
   turns to through others (`turnsFor`, which asks the breach again for that obstacle), the
   fewest. The march (`stepFor`) and its length (`marchLength`) step to the first obstacle
   of the chain, as they already did for a door's key. That step never comes round: a
   breach kept for the decision was read with no open breach cut short, and an obstacle's
   turns through the next one exceed that one's own.

**A read cut short is kept only while its cut lasts.** Asking X's way asks Y's, and Y's
asks X's again while X is still open; that inner answer ("no way through X") is true only
inside X's question. Kept for the decision, it told every later question Y was cut off;
never kept, the same reads ran again for every way tried, and one turn of Ch14 ran 14
minutes and then crashed (a Lua stack overflow). So each read notes the open breaches it was cut
against, and its answer is dropped when the deepest of them closes (`beginRead`/`endRead`).

**What it proved** (one attempt each, from the lap's saved starts). The first version
(without the walkable-ground and cut-memo corrections) won Ch14 in 28 turns: Colm opened
(17,19) on turn 2, Seth (10,14) on turn 6 and a third door from (17,1) on turn 15, and the
objective read a chance on turn 1 (0.17) where it read 0 before. The final version opened
(17,19) on turn 2 too, by Eirika at 6 HP with a Doorkey just taken; the Fighters that
arrived as it opened killed her that enemy phase (a reinforcement, predicted 0%), and the
attempt was lost. Ch9 ends `stuck` in both, at the next wall: Colm, the one unit the read
sends to the gate (every other unit's line says `breach -`), marches there and is offered
the Door, but opening it alone reads a 49 to 90% chance he dies, so the careful plan refuses
it; the units with no key read no way until the gate is open and hold in their corner.

**Cost.** The read adds no game call per decision beyond a change's tiles, kept for the run.
Ch9: 35.0 s of CPU (209 judged phases, 2163 movement maps), the same as the first version
(34.6 s), against 25 s before (149 phases: units now move). Ch14's 393 s for the win was its
first real fight (1146 judged phases, 43 kills). A unit test holds a row of eight doors to
29 reads of the game's turns (217 when cut reads are never kept).
