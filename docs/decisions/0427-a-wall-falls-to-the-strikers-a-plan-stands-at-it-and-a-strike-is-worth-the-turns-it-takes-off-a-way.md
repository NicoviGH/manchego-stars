---
id: 427
title: "A wall falls to the strikers a plan stands at it, and a strike is worth the turns it takes off a way"
date: "2026-11-18"
section: "Combat System"
issues: [655, 510]
---
# A wall falls to the strikers a plan stands at it, and a strike is worth the turns it takes off a way

**Decided 2026-11-18 (#655; Nicolas's calls in the issue's design comment, ADR 0396).** It
amends ADR 0410 (a way runs through several obstacles) and ADR 0420 (a door a teammate opens
is every unit's way) for walls.

**The problem.** No vanilla Ch8 game ever opened the west chests at (1,3) and (2,3). The
chests sit behind a cracked wall at (4,8) (50 HP, `InitMapObstacles`) and a door at (1,5).
Three faults were measured:
- `obstacleTurns` charged a wall only the walk to it. The planner read 4.8 turns to the chest
  through a wall that Colm (charId 9, 9 damage a strike) alone needs 6 turns to break.
- The march (`stepFor`) and the planner (`turnsFor`) read the way differently. The march only
  took an obstacle when the unit was cut off.
- Only the unit whose own march goal was the wall was offered a strike. No Ch8 run ever
  struck a wall.

**The rules (`tools/playtest/bot.lua`, `planner.lua`).**
1. **A wall's cost is its fall.** A unit's turns through a wall are the later of its own
   arrival and the turn the wall falls (`fallTurn`). The fall counts the unit itself, striking
   from its arrival. It also counts each striker the read stands on a tile its weapon reaches
   the wall from (`firstStrike`): it strikes this turn, or next turn once it has acted. Each
   striker deals the game's own forecast (`sight.strikeWall`) once a turn against the wall's
   current HP, counted at its chance to be alive after the judged enemy phase (the planner's
   positions): a striker the plan leaves to die at the wall does not break it. A two-tile
   wall's tiles share their trap's HP (`sight.obstacles`' `trap`, `wallKey`), so a strike on
   either is read through both. A wall no one at it can hurt is no way. The planner's read moves with the plan
   (`turnsOn`): it uses the HP the plan leaves the wall (`st.walls`) and stands each striker
   where the plan puts it.
   - **Rejected: every striker that could walk to the wall** (the first build). With 8 to 11
     units marching past the wall to the throne, the wall always read "falls on turn 2". So
     no strike was ever worth making, and the thief waited for a fall that never came
     (instrumented replay `t639-cs-s4003` Ch8 a1).
2. **One measure.** `turnsFor` is the fewer of the walk and the way through obstacles
   (`viaObstacle`), for every unit, cut off or not. The march steps to the first obstacle on
   that same chain (`chainTo`, from `obstacleTurns`' predecessor read). `breachFor` and
   `marchLength` read it too.
3. **The strike is offered to any unit that can hurt the wall.** It is offered on a wall that
   is on some unit's cheapest chain to its goal. It is also offered on a wall that unit could
   pass sooner than its way now if the wall stood open (`wallsOnWays`). The second half is
   needed: priced with no striker at the wall, the cheapest chain never named Ch8's wall. The
   thief's own 9 a strike made the door round the cheaper way, so no strike was offered and no
   striker came. The judge prices each strike like any act. There is no new weight.
4. **No flat `breach` for a wall strike.** Its worth is the turns it takes off the ways through
   the wall. The flat 25 counted that twice. Doors and the convoy key keep `breach` for now
   (#658). So does a strike with no forecast of its blow: the wall is then costed by the walk,
   so no turns price the strike, and it is offered only to the unit whose own way it is.
5. **The stuck rule waits on a wall only while a strike can come.** A unit with no nearer tile
   is not stuck when a unit able to act (itself included) can strike a wall on its way this
   turn and shorten it (`strikersNear`). Otherwise the goal is recorded like any blocked goal,
   and tested again next turn (ADR 0422's record).

**Proof (2026-11-18).**
- **Unit tests** (`test_bot.lua`, #655 block). Each fails on main. The rule-1 tests also fail
  on the first build: a striker standing off the wall is not counted. The rule-3 test fails
  with the cheapest-chain offer alone. The tests check that the cost falls with HP and with
  strikers at the wall, that a striker off the wall is not counted, that a lone weak striker
  walks round, that the march follows the wall when strikers are at it, that a strike is
  offered to a unit whose way it is not, that a strike is offered on a wall off the cheapest
  way, that the plan reads strikers at plan positions, that a strike earns no flat worth, and
  both halves of the stuck rule.
- **Ch8, attempts 1 to 4 of `t639-cs-s4001`, `-s4003` and `-s4007`** (12 games a side,
  `montecarlo.py attempts`):
  - Main: 7 won, 4 stuck, 1 lost. Every win left the west chests.
  - Branch: 8 won, 4 stuck, 0 lost.
  - Two branch games were clean, every chest taken: s4001 a3 in 21 turns and s4003 a2 in 27.
  - In s4001 a3, Franz (charId 4) struck the wall on turns 12 and 13, then Forde (0x10) and
    Colm (9) on turn 16. Colm went through, opened the door and both chests. In s4003 a2,
    Forde struck it. No main game struck a wall.
  - Average turns to win: main 17.9, branch 22.1.
  - CPU per player phase: main 2.76 s, branch 2.66 s.
- **`suite --only` (#655 runs), branch beside main:**
  - vanilla-ch3/1001 won clean in 12 turns. On main it took 21, with a stall (#652).
  - scout-ch10/1001 and scout-ch13/1001 are unchanged.
  - scout-ch14/1001 was lost on turn 10 (won on turn 28 on main). Both deaths were graded
    `reinforcement`, in the player phase. The game left the main game's line on turn 1, as the
    door ways are now read for every unit (rule 2). This is a different route into units the
    plan could not see, not a wall: the map has no wall.

**Consequences.** Rule 1 assumes a striker at the wall keeps striking until it falls. A plan
that walks it away loses those strikes in the read, so the next decision prices that honestly.
A striker more than one move from the wall gains nothing in the read until a plan brings it
there. Rule 3's offer is what lets such a plan be judged. Where the planner's one-turn horizon
cannot see a two-turn walk to the wall, the wall is left. That is the outcome deciding, not a
script.

**Amended 2026-11-19 (#663): rule 3 reads each way to its goal and to each obstacle on it.** A
goal behind a door has a field that stops at the door (a closed door is no ground to walk), so
the "could pass sooner if it stood open" check never found a wall that opens onto the door's
side. Vanilla Ch8's west chests sit behind the (1,5) door, and the cracked wall at (4,8) opens
onto that door's room. Once Colm (charId 9) turned for the chests, the wall left every list.
Instrumented replay of `t639-cs-s4003` Ch8 a1: the wall was listed on turns 2 to 6 (through
Ephraim's (0x0F) way to the throne alone), never from turn 7, with Colm's steps through it read as
none. No strike was judged, Colm walked the south route and died on turn 16, and both west
chests were left. `wallsOnWays` now asks the same question of each obstacle on the unit's
cheapest chain (`chainTo`): a wall that brings it to that door sooner, stood open, is on its way.
- Proof: `test_a_strike_is_offered_on_a_wall_on_the_way_to_a_door` fails on main. One replay
  of that game (`fix663-t639-cs-s4003`, attempt 1): won clean in 19 turns, no deaths. Forde
  (0x10) struck the wall from (5,8) on turns 10, 11 and 13; Colm opened the door on turn 17
  and took both chests. On main the same attempt won in 18 turns with Colm dead and both
  chests missed.
