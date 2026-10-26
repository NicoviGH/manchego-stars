---
id: 368
title: "The step-9 bot is one pure policy, styled by what it refuses to end its move on"
date: "2026-10-26"
section: "Combat System"
issues: [510]
---

# The step-9 bot is one pure policy, styled by what it refuses to end its move on

#510 step 9 plays the real ROM. Its policy is `tools/playtest/bot.lua`: a pure function,
`Bot.decide(board, sight, style)`, from Board.read's board and a `sight` table the ROM layer
supplies (danger zone, battle forecast, reach, objective) to ONE action for the unit that should
act next, or nil to end the phase. It computes no combat, danger or objective of its own (step
9's constraint: the bot plays the game, nothing is re-created); `test_bot.lua` drives it with a
fake `sight`.

**One bot, not two.** The greedy clear-bot core (`pickTarget`, `pickMove`, the stall and
throne-step-off helpers, `gridHostileInReach`) moved whole into bot.lua, and its file and test
were deleted. Greedy is the fourth aggression, `"greedy"`: it reads no forecast and no danger, and
the clear scenarios keep calling its functions directly through harness.lua's `BOT` binding,
picking exactly as before (every old test case is ported unchanged).

**One forecast direction.** `sight.forecast(unit, target, x, y, slot)` is always our unit's attack
from (x, y). The enemy phase is read from the `taken*` fields of the forecast our unit would get
against each threatening enemy; there is no enemy-side call.

**Worst case on an end tile** = the sum, over every enemy that reaches the tile (some tile of
`sight.reach(enemy)` within its weapon range; `danger(x, y) = 0` skips the walk), of
`takenDmg x takenHits`, tripled when `takenCrit > 0` (FE8 triples a crit), zero when
`takenHit = 0`. A sure kill's target (`killsTarget` at hit 100) is left out: it dies before the
enemy phase.

**The styles are gates, not weights:**
- `careful`: no `diesWorst`, and the worst case is below the unit's current HP;
- `even`: no `diesWorst`, and no single enemy's worst case reaches the unit's current HP (it takes
  one fight at a time, not a gang);
- `bold`: no `diesWorst`; the enemy phase is not weighed;
- `greedy`: nothing.

None of these gates or the attack ranking was chosen by looking at a survival rate.

**Order within a turn:** the lord seizes when it can reach the seize tile, whatever the danger
(seizing ends the chapter, so no enemy phase follows); then the unit with an allowed sure kill;
then the unit whose own tile has the largest worst case (the threat measure is the worst case
everywhere; the number of reaching enemies only breaks a tie); then slot order. Greedy keeps its old order: seize,
then slot order. A unit attacks when an allowed attack exists (sure kill, then kill chance, then
expected damage, then the boss, then the lowest HP), else it marches toward the objective (its
tile, the boss, or the nearest enemy; it holds on `survive`) over allowed tiles, and with none
allowed (or nothing to march to) it ends where the worst case is smallest.

**A unit that cannot Seize never blocks the throne.** Who may Seize is `Board.canSeize(unit,
objective.lord, objective.ruledOut)`, its one owner: with no lord pid, anyone not in the ruledOut
memo may try. A unit that cannot never ends on the seize tile, nor on or beside it
(`needsToStepOff`) while another tile is left, to wait or to attack. The one exception is a target
standing ON the seize tile (the boss on the throne), which it strikes from the approach.

**What PR D supplies beyond the first interface:**
- `objective.lord` (Board.lordPid) and `objective.ruledOut` (the slots that stood on the tile with
  no Seize command), so Board.canSeize answers who may Seize.
- `sight.field(goal)`, optional: a pathing.distanceField-shaped field toward `goal`, from the
  game's terrain. A function of the goal because the bot picks the goal. Without it the march is
  Manhattan, which strands a unit against a wall (#60).
- `sight.cache`, optional: one table per player phase. Forecasts are kept in it across decide
  calls, keyed by the board signature (every unit's id, tile, HP, and held item with its uses,
  built once per call) plus the exchange (attacker, target, strike tile, weapon slot). FE8's
  forecast reads more than the pair: support bonuses from allies in range, and the held weapon. A
  narrower key returned a stale forecast after an ally moved. Correctness over savings: a hit is
  only the same board asked again, such as a re-decide after a cancelled input. Reach and worst
  case are per call only.
- The action carries `unitId` and `targetId` (Board's unique index byte) beside the charIds,
  because generics share a charId and the ROM layer has to know which body to act on.

**Between chapters (PR C2): four pure rules, fixed now from the Wiki's general strategy.** Same
contract as `decide`: plain tables in, no memory read, no character id, chapter number or item id
in the Lua (the caller marks the Vulnerary with `kind = "vulnerary"` and a seal that promotes THIS
unit with `promotes = true`; the bot never knows which seal fits which class). The input shapes
are in bot.lua's header.
- `Bot.prep(roster, cap, style)`: forced units in slot order, then `style.deploy` in listed order
  (a charId not in the roster is skipped, a repeat counts once), then the highest level, ties by
  slot order, up to the cap. The cap is never exceeded except by forced units: when they alone
  exceed it, all of them still go and nothing else does. `give` is always `{}`: no transfer rule
  is decided yet.
- `Bot.shop(gold, stock, party)`: one cheapest Vulnerary per deployed unit, then, per unit in
  deploy order and per weapon type it has a rank in, the cheapest stock weapon at or under that
  rank when the unit holds none of the type. A purchase gold cannot cover is skipped and later
  ones are still tried; the result is aggregated `{{item, qty}}`.
- `Bot.promote(unit, items)`: level 10 or above with a promoting seal held. The order is
  `Bot.promoteOrder(units)` (highest level first, ties by slot order); the caller spends a seal
  per true.
- `Bot.route(options, style)`: `style.route` validated as an index into `options` (it raises on
  anything else). `route` joins `Bot.STYLES` as an axis the runner samples, 50/50 per campaign.
