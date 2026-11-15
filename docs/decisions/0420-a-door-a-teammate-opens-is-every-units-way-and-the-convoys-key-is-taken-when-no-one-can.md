---
id: 420
title: "A door a teammate opens is every unit's way, and the convoy's key is taken when no one can open it"
date: "2026-11-15"
section: "Combat System"
issues: [510]
---
# A door a teammate opens is every unit's way, and the convoy's key is taken when no one can open it

Eirika's lap (`lap3e-cs-s4006`) stalled at vanilla Ch10 on her route (chapter id 11, Seize at
(15,1) behind the doors at (10,9) and (11,9)) in attempts 1 and 2. A design advisor read the
traces; every claim below was checked against the run.

**Cause (confirmed by an instrumented run, tag `advp1`, the same acts hash).**
- On turns 1–3 the units without a key had a way through an enemy Soldier carrying a
  droppable Door Key (`keySources`). Seth (charId 2) killed that Soldier on turn 3.
- From turn 4 every unit but Gilliam (charId 3), the one key holder, read no way to the throne.
  The way read (`openables`) listed a locked door only for a unit that could open it itself.
- So the army held in its corner, and Gilliam walked to the door alone and died there on turn 6
  (64–96% in every plan). The six guards left never moved, so the board repeated.
- The Soldier's key had dropped to Seth, whose bag was full, so it went to the convoy (trace
  `bag` line, turn 3). The game offers it back mid-map through Supply (`SupplyUsability`: the
  lord, or a unit beside the lord), and the bot had no such act.
- ADR 0410 records the same lone march on Ephraim's Ch9.

**Decision.**
- **Escort (`bot.lua`).** A locked door a living teammate opens (`doorMates`: one holding the
  means, `opener`) is a way for every unit, since the game opens the door's whole map change.
  - The door is listed only when a teammate has a way to it (`mateTurns`). A key holder cut off
    from the door opens nothing, and a wall the unit can strike stays its way.
  - A unit's turns to it (`escortTurns`) are the later of its own walk there and the soonest
    opener's, so no unit gains ground by running ahead of the one who opens it.
  - When an enemy also drops a key for it, the sooner of the two ways counts.
  - Doors only: a chest pays only its opener.
  - A teammate who would fetch a key from an enemy is not counted, since asking that teammate's
    way would ask this unit's way back.
- **The convoy's key (`supplyKey`).** A unit is offered Supply when a door locked to it stands on
  its way (`lockedOnWay`: it is cut off from its goal, walks to the door, and the door opens
  onto the goal's ground), no fielded unit opens doors, and the convoy holds an item that would
  let it open the door (`sight.convoyKey`, the game's own key check). It goes to the safest tile
  the game enables Supply on (`safest`).
  - The plan credits the Take as the act that opens the way (the breach weight, the same one
    as a door's opening or a wall's strike). The convoy's one key is taken once per plan: a
    second Take of it is no act.
  - The harness checks that the game's menu offers Supply, takes the item with the screen's own
    container calls (`INSPECT.takeFromConvoy`, lifted out of the campaign api's `take` so both
    use one copy), then waits. The game would let the unit act on after the Take; the plan
    models only the Wait.
  - `sight.legal` asks `SupplyUsability` again for a kept plan, and asks that the key the act
    names is still the convoy's. A forced diagnostic replay fills the act's item from the
    convoy through the same `Bot.takeItem` the offer uses (`botrun` `forcedAct`).

**Proof.**
- **Unit tests** (`test_bot.lua` "escort:", "supply:" and "takeItem:"; `test_sight.lua` "convoyKey:" and
  "legal:"). Every positive check fails without its part:
  - the escort's two turns checks without the escort;
  - the offer's two without `supplyKey`;
  - the value check without the planner's credit (without it the plan picked Supply only by an
    alphabetical tie with Wait);
  - the review's four (a door no teammate reaches, a door off the way, one Take a plan, the
    sooner way) on the code before the review;
  - the `convoyKey` ones without `Sight.convoyKey`;
  - the `takeItem` one without its item fill.
- **Runs** (2 attempts each from the lap's saved starts, tag `door2`).
  - Eirika's Ch10, attempt 2: won in 27 turns, where it was stuck before. Gilliam opened the
    door on turn 23.
  - Eirika's Ch10, attempt 1: Gilliam opened the door on turn 5 and lived, but the attempt is
    still `stuck` (30 turns). Every enemy was dead by turn 20, and Eirika stood boxed in at
    (13,7) among allies with no key left (Gilliam's was used up). Untested lead: allies block the
    lord's way on a Seize map once the enemies are gone, the HANDOFF's open Ch7 item.
  - Ephraim's Ch9 (chapter id 23): won in 19 turns with one death (charId 0x11), and in 21 turns
    with none; the unit holding the key (unit 2) opened the gate on turn 6 in both. Before the
    fix the same start had won in 21 turns with no death, so Ch9 shows no improvement and one
    more death on attempt 1.
- **Supply witness** (tag `supw1`, attempt 1 with the escort switched off for that run only, so
  the original lockout replays). Gilliam died on turn 6 as before. Garcia (charId 0x0A) took the
  convoy's Door Key (0x6A) with Supply on turn 7, opened the door on turn 12, and Eirika seized
  on turn 19: won.
