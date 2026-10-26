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
- `careful`: no `diesWorst`, and the worst case is below the unit's HP after its own attack's
  worst-case counter (none when the first blow is a sure kill), so an exchange plus an enemy
  phase that kill together are refused;
- `even`: no `diesWorst`, and no single enemy's worst case reaches that same HP (it takes one
  fight at a time, not a gang);
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
  calls, keyed by what FE8's forecast reads for that exchange: both fighters (id, HP, held item
  and its uses), the strike tile, the enemy's tile, and every other unit within support range of
  either fighter (`SUPPORT_BONUSES_MAX_DISTANCE` = 3, bmreliance.h). A whole-board key missed on
  every action, so in the ROM each decide would have re-paid a full sweep of emulator round trips;
  a pair-only key returned a stale forecast after an ally moved. Reach and worst case are per call
  only, and each unit's allowed attacks are worked out once per call. A supporter that is rescued
or hidden leaves the on-field list, so it leaves the key too; the chapter-wide flag that lifts the
support range check (gameStateBits 0x40) does not change within a phase, the cache's lifetime.
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

**Claims become behaviours (PR C3).** A Strategy claim (`tools/strategy.py`'s kinds) reaches the
bot RESOLVED by the runner (PR D/F), which reads the YAML and maps every name: `{ id, kind,
unit = {charIds}, vs = {classIds} | "boss" | "all", tile = terrain id, turns = {arrival turns} }`,
each kind with the fields it uses. The bot maps no name and reads no YAML. Each behaviour,
`Bot.CLAIM_BEHAVIOURS[kind](claim, style)`, returns a NEW style with its entry added (the given
style is never edited, because the runner samples one style and may apply claims to it more than
once), and `Bot.decide` reads those entries:
- `carry`: the units go AHEAD of the sampled `style.deploy` (deduped). `Bot.prep` fills its cap in
  list order, so appended they were cut whenever the sampled list already filled it. After the sure kills and
  before the most-threatened rule they attack an enemy `vs` names when one can.
- `answer`: those units rank an enemy `vs` names above every other target, a sure kill elsewhere
  included.
- `wall`: at the same point, a wall attacks an enemy `vs` names, else ends on its approach (the
  gate-allowed wait tile nearest that enemy among the tiles it reaches), else takes the normal
  pick: a wall that dies is not a wall. Every other unit marches only to tiles no nearer that
  enemy than the nearest wall, when any such tile is left; attacks are not held back.
- `terrain`: the march keeps to gate-allowed tiles of that terrain that an enemy `vs` names
  reaches, when any is in reach (strategy.py: the party holds the tile AGAINST those enemies). A
  unit out of their reach marches on: holding a fort nothing threatens would stall a rout or boss
  chapter whose boss never moves. It reads the new optional `sight.terrain(x, y)` (PR D, from
  game memory); without it the claim is a no-op. No avoid bonus is coded: the gate already reads
  what the terrain does through the game's own forecast.
- `reinforcements`: on the turn before any cited arrival turn the march holds (the no-goal rule:
  the allowed tile with the smallest worst case, its own tile first). Attacks are still made: a
  strike from a safe tile is not an advance. It reads `board.turn` (Board.read's, the one source
  for the turn), and decide raises when a reinforcements claim is in the style and that is missing.
A claim missing a field its kind needs raises, naming the claim id; nothing is skipped silently.
Every element of `unit`, `vs` (other than `"boss"`/`"all"`) and `turns`, and `tile`, must be an
integer: an unresolved name (`unit = {"some-name"}`) would never match and silently do nothing.
A claim without a string `id` and `kind` raises before dispatch, in `applyClaims` and `unplayed`.
`Bot.applyClaims(claims, style)` folds them in order, and `Bot.unplayed(claims)` returns the id of
every claim whose kind has no behaviour (`threat`, `kits`, `unmodelled`, any unknown kind), so a
run reports what it did not play. Greedy ignores every claim field in `decide` (only `deploy`
reaches `Bot.prep`): the clear scenarios' picks are unchanged.

**The twin's claims run to the end, and topics are one taxonomy (2026-10-26, C4; Nicolas: semantic
judgement over keyword matching, a shared tagging taxonomy).** `tools/wiki/twin_strategy.yaml`
now covers every vanilla page with a Strategy section: Ch5x, Ch8, Ch9-14 on both routes (`FE8 ChN`
is Eirika's, `FE8 ChN Ephraim` Ephraim's, as `gen_wiki.VANILLA` names them), Ch15-20, and both
final maps (`FE8 Final`, and `FE8 Final 2` for the second map, which had no key). Village of
Silence's section is empty, and Lagdou Ruins and Tower of Valni have none, so they get no entry.
These claims are bot data for the vanilla baseline ONLY. ADR 0363 stands: `strategy.findings`
raises on a planned chapter, so they never reach the parity model. `make verdict-diff`: 0 cells
moved. A line is tagged by what it MEANS, not by a word it uses. "Rangers are not that much
stronger" is no `threat` claim, and a Cormag line whose target class the page does not name became
`baiting`, not a guessed `vs`. `unmodelled` and `kits` topics come from ONE taxonomy in
`strategy.py` (`TOPICS`, each with its meaning and its #510 step; `KIT_TOPICS`), shared by our
claims, the twin's and the bot. A topic outside it raises, and a claim no longer carries a `step`:
the topic fixes it, so the two can no longer disagree. Our YAML was re-tagged onto it: ch05's
"niches" and the twin's "village race" are the same play (`site-race`); "chokepoint" is `hold`;
"recruit rescue" is `rescue` and "recruit escort" is `escort` (what those lines ask the player to
do). A test checks every twin `unit`/`vs`/`tile` against the decomp's CHARACTER_/CLASS_/TERRAIN_
names, so the runner's resolver cannot meet an unknown name mid-run.

**PR C review fixes (2026-10-26).** A unit always keeps its own tile, so one that cannot Seize and
is boxed in on the throne waits there instead of having no tile. The kill chance is the hit rate
once per blow the kill needs (a doubling 70% that needs both blows is 49%). The shop buys a
Vulnerary only for a unit holding none (a held item can carry `kind = "vulnerary"`); the plan's
order, Vulneraries before weapons, stands. Claim tags that were folded too far by keyword went
back to what their lines mean: "keep Ross and Garcia safe if you want to recruit them" is
`escort`, "putting her in a nearby forest and rescuing her" is `rescue`.
