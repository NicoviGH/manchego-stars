---
id: 422
title: "A unit on the tile a teammate's act needs is offered a free tile"
date: "2026-11-15"
section: "Combat System"
issues: [510]
---
# A unit on the tile a teammate's act needs is offered a free tile

**Proposed (2026-11-15, #510), from the stuck `lap3e/9` game ADR 0421 left open.** It also ends
the Ch7 Seize-map pocket. That retires the weight recommended for that pocket ("on a Seize map
count the seizing unit's progress above an escort's"), which was never built.

**The problem.** On vanilla Ch8 (start `lap3e-cs-s4006/9`, even) the throne is behind the door
at (20,7), and the Door command is offered only from (20,8). From turn 5 Joshua (charId 0x20,
no key) stood on (20,8) for 17 turns. Colm, Artur and Gilliam (charIds 9, 0x13, 3) were each
offered the Door from (20,8), but only if Joshua left it first (`vacate`). Joshua was offered
three tiles: (20,8) itself, Garcia's (19,9) and Ross's (20,9). Garcia's and Ross's only other
tiles were each other's or (20,8). That is a loop of three tiles, and no order of moves frees
(20,8). The board repeated 5 times and the attempt ended stuck on turn 22 (instrumented run
`jam1`; the bot's own `stuck:` dump names the breach (20,7) for every unit).

**The model error.** Candidates treat a tile an ally may vacate as an extra way forward, never
the only one (the march has a free-tiles-only variant for that). But a unit already on the
frontmost tile has no march gain and no retreat gain anywhere, and its holds (`M.HOLDS` = 3,
safest first, own tile first on a tie) can all be its own tile or other allies' tiles. So the
unit a teammate asks to move had no free tile to move to.

**The rule (`bot.lua` `propose` and `aside`; `planner.lua`'s menu).**
- After every unit's acts are proposed, a unit whose tile any teammate's offered act asks for
  (its `vacate`) is offered one more wait, `why = "aside"`. That includes acts the rank will
  never play, so an aside can change the beam where none is played (two runs below).
  A unit whose goal has not changed keeps its proposal without the aside (`base`), so each
  pass asks again who needs its tile. It goes to the safest tile it may
  wait on that no unit stands on, other than its own (`waitTiles` with `ctx.freeOnly`). Ties
  go to the most ground toward its own march goal (`groundFor`, the gain the retreat already
  used), then board order: `bySafety`'s order with that tie-break added.
- It is not offered when the tile is already one of the unit's waits, to a benched unit (its
  claim holds it), or when there is no free tile.
- The planner's menu always keeps it, as it keeps holds, retreats, Rescues and Drops. Its own
  score never sees what it buys, which is the teammate's act on the freed tile.
- It is an offer only. The rank decides whether the plan that steps aside and then acts beats
  the plans that do not.

**ADR 0396's five tests.**
1. **It names a quantity:** none of its own. It adds an act the game offers (a Wait on a free
   tile), and the plans with it are ranked by the existing quantities.
2. **It is not a ban:** it adds a candidate and forbids nothing.
3. **It holds for every objective and style:** any act with a `vacate` asks for it: a Door, a
   Seize, a march, an attack. It changed Rout, Seize and Defeat Boss maps below. It is wrong
   only where every free tile is worse than staying, and then the rank leaves it unplayed.
4. **It has no second owner:** the rank still decides. It fills a gap in what the candidates
   offered.
5. **It names no unit, chapter or turn.**

**Evidence (attempt 1 each).**
- **The witness, `lap3e/9`:** main stuck on turn 22 (`wy9`, and `jam1` on main's merged
  code, 0 deaths). With the rule (`aside1`):
  Joshua steps aside on turn 7, Colm opens the door from (20,8) on turn 8, and the game is won
  on turn 24 with no death. The chests at (1,3) and (2,3) are still missed (`stalled`).
- **The Ch7 pocket, `fwd1-cs-s4005/8`:** main (`aside7ctl`) is stuck on turn 19. Lute (charId
  0x0C) stands on (5,15) from turn 9 to the end, with Eirika beside it on (5,16) the whole time.
  With the rule (`aside7`) units step aside on turns 3, 5, 6 and 9, Eirika goes on through
  (5,15) and (5,14), and she seizes on turn 12: won clean, no death.
- **14 suite runs** (`suite --only`, seeds 1001 and 1002 of vanilla-ch3, -ch4, -ch5, scout-ch6,
  -ch10, -ch13, -ch14; main `5958bfa4c3f8`, rule `5441b0b472f4`):
  - 6 play main's acts (vanilla-ch4, vanilla-ch5, scout-ch6).
  - vanilla-ch3, both seeds: stuck on turns 17 and 21 on main; won clean on turns 21 and 16
    with the rule. Eirika (charId 1) steps aside on turn 10 of seed 1002; Seth (charId 2) on
    turn 11 and Neimi (charId 8) on turn 19 of seed 1001.
  - scout-ch10, both seeds: won on turn 15 → 16, no death either way.
  - scout-ch13 and scout-ch14: same outcome and deaths. Turns are the same except ch14 seed
    1002 (27 → 29). Two of these four never play an aside; the extra offer changes the beam.
  - Totals: blue deaths 8 → 8, wins 10 → 12, clean clears 2 → 4. On the 10 runs both won,
    turns 132 → 136.
- **Cost:** on the 6 runs that play main's acts, CPU 228.6 → 228.5 s. All 14: CPU 916.3 →
  994.7 s, mostly the two Ch3 games that now play to a win (61.8 → 99.3 s). The unit tests are
  unchanged in time (one test added).

**Also found, not fixed** (on #510, comment 6905221090).
- On `lap3e/9` the door is opened under labelled fallbacks: `fallback_sacrifice` on turns 7 to
  9, at up to 0.73. It is the same family ADR 0421 lists (a pessimistic two-phase read deciding
  games).
