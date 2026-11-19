---
id: 431
title: "A plan that opens the map lists its later units' acts again on the map it leaves"
date: "2026-11-19"
section: "Combat System"
issues: [661, 510]
---
# A plan that opens the map lists its later units' acts again on the map it leaves

**Decided 2026-11-19 (#661; Nicolas: "try it" on the issue's root-cause comment).** It follows
ADR 0396: an ordering of outcomes, no new rule or weight.

**The problem.** The planner listed each unit's acts once, from the board before anyone acts
(`Bot.candidates`), and the beam combined those lists. A door opened or a wall broken mid-plan
changed the map. The judged enemy phase already saw that change (`sight.openMap`). The units
acting later in that plan did not: no act was ever listed on the doorway or the room behind it.
In vanilla Ch8 (seed 4002, the `dbg661` trace), 101 plans opened the door at (20,7), and none
had a later act on or past the doorway. All of them left Lute (charId 12) beside five Armor
Knights with nobody blocking or striking, and all were over the death cap. The bot waited
beside the door for 20 turns.

**The rule (`tools/playtest/planner.lua` `menusFor`, `sight.lua` `opened`).**
1. When a partial plan in the beam has opened doors or broken walls (`st.opened`), the units
   it has not used get their acts listed again by `Bot.candidates`, on the map with those
   changes applied. `sight.opened` applies them with `M.openMap` (the judged phase's own
   journaled writes, `M.openAll`) in one sandbox. The board's cached answers (reach paths,
   danger, cost grids) are swapped for fresh ones for the call (`M.isolated`, shared with
   `fullInfo`), so nothing read on the opened map is kept for the shut one. The phase cache
   is kept, since its memos key on `mapKey`, which reads the opened terrain. `closings`' memo
   now keys on the map too.
2. A re-listing is made once per set of changes per decision, not once per partial plan. `extend`
   still keeps out a unit the plan has used and a tile it has taken.
3. Re-listed menus are cut by the same function as the board's (`menusOf`). Every act that
   ends on a tile the change opened is also kept past the `PER_UNIT` cut, as a step aside
   is: what standing in a doorway is worth is the opener it shields, and only the judged
   phase reads that.
4. The exposure memo keys a re-listed act by its map (`a.map`), since the same act on the shut
   map is another risk.
5. Not re-listed: an offered replay (`opts.offer`, whose acts come from another board) and a
   sight without the read. The mend still tries the board's menus.

**Not built: a kill that frees a tile mid-plan has the same gap.** `sight.reach` keeps only the
tiles no other unit stands on (`movementTiles`: `by == 0`), and an enemy blocks the movement map.
So no act is listed on, or past, the tile of an enemy the plan kills. Applying it needs the unit
taken off the board in the sandbox (the judged phase's `remove`) and a re-listing per set of
kills, and plans hold far more distinct kill sets than door sets. It is left for its own issue.

**Proof (2026-11-19).**
- Unit test `test_a_plan_steps_through_the_door_it_opens` (`test_bot.lua`). It fails on main's
  planner (the plan is `1>wait@0,0 2>wait@0,1`) and passes with the change
  (`1>door@1,0 2>attack@2,0`). It also checks that one door is re-listed once.
- One replay, vanilla Ch8 from `e639-t639-cs-s4002/9`, attempt 1, with `PT_LEAKGUARD=1`
  (`relist661`). The game was won in 20 turns with no deaths. Lute opened (20,7) on turn 4,
  and Natasha (charId 13) took the doorway. Main's run from the same start (`base661`) won
  in 57 turns with no deaths, and Colm (charId 9) opened the door on turn 39. Both missed the
  west chests. No leak was logged. Of the branch's 16 judged plans that opened the door,
  9 had a later act on or past the doorway; main had 0 of 178.
- Timings, the two runs back to back with `PT_LEAKGUARD=1`. In-game CPU per player phase:
  main 2.24 s, branch 3.74 s. The whole chapter: main 127.9 s, branch 74.8 s. On the one
  board both runs shared (turn 3's first decision, where the same plan was played), the
  decision took 7,252 frames on the branch against 4,667 on main.
