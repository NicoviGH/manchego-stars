---
id: 398
title: "The bot rescues and drops a green unit, and a recruit's death chance breaks ties after the forfeit"
date: "2026-11-10"
section: "Combat System"
issues: [510]
---

# The bot rescues and drops a green unit, and a recruit's death chance breaks ties after the forfeit

**Decided (Claude, 2026-11-10, on Nicolas's brief to teach the bot to rescue), #510.** Stop 3
of the vanilla route: vanilla Ch2's Ross, a green recruit at 5 HP, killed by the Brigand at
(12,3) on enemy phase 1 (seed 4008, 4 of 4 attempts, 37.4% each). The plan is #510 comment
6771845566.

## 1. A recruit's death chance breaks ties after the forfeit

**The error.** A recruit's death reached the rank only as a yes/no forfeit. `Goals.forfeited`
closes its goal at any chance past `Goals.DUST` (1e-9), and `green_die` left recruits out. So a
plan that left Ross at 5% forfeited exactly as one that left him at 37%, and nothing ranked a
safer plan above a riskier one.

**The fix.** `green_die` counts a recruit's death chance too, in the judged phase and the
lookahead's second phase (`planner.lua`). The forfeit still ranks first. This only orders plans
that forfeit alike (ADR 0396: an ordering of the game's outcomes).

**Alone it did not save Ross.** All 5 plans judged on turn 1 left him at 37.4%, because no act
the bot had touched his attacker.

## 2. Rescue and Drop

**Why.** Every guide read says to save Ross by having Vanessa Rescue him on turn 1: the Fire
Emblem Wiki chapter page, the game's own Easy Mode tutorial, and the LP Archive. Our research
record `docs/research/0014` lines 26-32 already said so. The bot had no Rescue act.

**The game's rules** (decomp):
- **Target:** Rescue takes an adjacent allied unit, blue or green (`TryAddUnitToRescueTargetList`
  bmtarget.c:263; `AreUnitsAllied` bmphase.c:50 compares bit 0x80 only), when the rescuer's Aid
  covers its Con (`CanUnitRescue` bmunit.c:905).
- **The carried unit:** gets `US_RESCUED|US_HIDDEN`, is off the map, is never the AI's target
  (cp_battle.c:92, 190, 324), and does not act (cp_order.c:71).
- **The carrier:** gets `US_RESCUING`, which halves its Skill and Speed (bmunit.c:285-300). If
  it dies, the carried unit is dropped alive (`DropRescueOnDeath` bmmind.c:473).
- **Drop:** sets the unit on an empty adjacent tile it can stand on (`TryAddToDropTargetList`
  bmtarget.c:303).

**The build:**
- **The offers.** `bot.lua` offers a Rescue of each green unit, from each wait tile beside it
  where the game's own Rescue menu lists it (`RescueUsability`). It offers a Drop from the
  carrier's tile and from each tile near a unit that may Talk the carried one over, onto each
  tile the game's drop list holds (`DropUsability`, `sight.drops`). These are offers only; the
  rank chooses.
- **The plan.** In `planner.lua` the plan keeps who carries whom (`carry`). A carried recruit's
  goal stands at its carrier's tile, a turn later (GAMMA), because Talk lists only units on the
  map. Dropped, the goal stands at the drop tile.
- **The judged phase.** `sight.stagePhase` writes the carry into the game's memory: both state
  bits and both `rescue` bytes. The game's AI and its forecasts then see the hidden unit and
  the halved stats.
- **The rest.** `board.lua` reads `carrying` and `carriedBy`. The controller and harness drive
  Rescue and Drop through the unit menu (0x63, 0x64) and their selectors. Canto is section 3.

**Not built:**
- **Rescue of a blue unit.** A carried blue cannot act, and the guides' Rescue is of a green in
  danger.
- **Take and Give.**

## 3. Canto is a decision

**Why.** Nicolas (2026-11-10): Canto is a choice the player makes, not a rule hard-coded either
way. Spent in place, it left Vanessa where she rescued; the guides fly her back.

**The game's rule** (`TryMakeCantoUnit`, playerphase.c:800): a unit whose character or class
carries `CA_CANTO` gets a second move after any act but Wait, Combat or Staff, unless it has
already had one (`US_HAS_MOVED`) or its move used all its Mov (`moveCount`, the movement map's
cost of the act's tile). The map is refreshed first (`RefreshEntityBmMaps` in
`PlayerPhase_FinishAction`: a rescued unit is off it, a dropped one on it), then
`GenerateUnitMovementMapExt(unit, MOV - moveCount)` from the act's tile. After it, only Wait.

**The build:**
- **The read.** `sight.cantoTiles(u, act)` asks the game: the act's board staged (the unit on
  the act's tile, the carry as `stageCarry` writes it for the judged phase), the map refreshed,
  the game's own movement map with what Mov is left. The bot plays it after a Rescue, Drop,
  Visit, Chest or Talk (`sight.CANTO_ACTS`).
- **The offers.** Per such act, `bot.lua` (`cantoMoves`) adds variants with `canto` set: the
  `M.HOLDS` safest tiles of the game's map and the one that gains the most ground. Staying is
  the plain act. The rank chooses (ADR 0396).
- **The plan.** `Board.endTile(a)` (the canto tile, else the act's) is where the unit ends, for
  the plan's positions, occupancy, the judged phase's blues, its exposure, the boss trigger and
  `surprise`. The act's key carries the tile (`~x,y`) and reads back.
- **Driving it.** `sight.legal` checks the tile against the live board; `harness.lua`
  `awaitActed` moves the cursor there instead of confirming in place.

## Witness

Vanilla Ch2, seed 4008, attempts 1..4 (`montecarlo.py attempts`):
- **Before:** Ross died on turn 1 in 4 of 4; no clean clear.
- **After:** 2 of 4 clean, Ross recruited. In each, Vanessa rescues Ross from (9,5) on turn 1.
- **Attempt 3:** Gilliam died on turn 6, with no plan within the cap (`fallback_sacrifice`).
- **Attempt 4:** Vanessa carried Ross for four turns, then dropped him at (1,3) on turn 5 into a
  Brigand's 37.4%. Every plan judged that kept him safe put a blue over the cap. The plan the bot
  did not judge, keeping him carried and backing off, is a search-coverage gap, not a Rescue
  rule.
- **With Canto (section 3):** 3 of 4 clean, Ross recruited. In all four, Vanessa rescues Ross
  from (9,5) and moves on to (8,4); each Drop moves on too. Attempt 3 lost Ross on turn 5 to an
  enemy's 53.3% after his drop, and still won.
- **The driver's first try crashed all four** on the Canto move: the Wait menu comes after the
  walk, and `awaitActed` looked for it once, while the unit was still walking. It now waits for
  the menu.

Suite: see the PR.
