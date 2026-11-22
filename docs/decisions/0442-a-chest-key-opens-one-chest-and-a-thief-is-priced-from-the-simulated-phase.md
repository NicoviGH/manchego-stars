---
id: 442
title: "A Chest Key opens one chest, and a thief's steal is priced from the simulated enemy phase"
date: "2026-11-21"
section: "Combat System"
issues: [711, 699, 510]
---

# A Chest Key opens one chest, and a thief's steal is priced from the simulated enemy phase

**Decided (#711 parts 1 and 3), #510 step 9.** Part 2 (the bot never buys a Chest Key or Lockpick;
a Lockpick wears out) stays with #693's shopping. Extends ADR 0379 (what a thief takes) and ADR 0369
(the game's own AI decides).

**Part 1: one key per locked tile at prep.** `takeKeys` took one key per lock kind ("the next
arrives mid-map"). A Chest Key is one use and opens one chest; vanilla Ch21 has two, and the
mid-map fetch happened in 1 of 12 attempts (#699). `sight.demandsOf` now counts the tiles a lock
demand covers (`locks`); `need` stays the openers the team seats, so `Bot.team` is unchanged.
`locks` counts only a lock a key may still be needed for (`Sight.lockNeeded`): still shut, and
reached by a fielded unit's march (`sight.turnsTo`, the game's costs); with no unit on the map
every shut lock counts. The units read are the prep screen's default deployment, not `Bot.team`'s pick (the team is chosen
from these demands, and a benched unit has no tile): a lock only a benched flier reaches is the
mid-map fetch's, a walk, where an over-count costs a bag slot for good. A door behind another lock
reads unreached and is the mid-map fetch's too, and
a door nobody reaches no longer pulls a spare Door Key into a bag (Ch21's replay took one).
`takeKeys` wants `locks` uses, less what the fielded bags already open. An item that opens counts
its `uses` (a Chest Key 1, a Lockpick as many as it has left), and one item's uses are spent once
across the kinds, the narrowest opener first (a Chest Key answers chests before a Lockpick does), so
a 3-use Lockpick against 2 chests and 3 doors covers 3 of the 5. The rest is taken from the convoy,
one item per pass, by the unit with the most free slots then, until the want is met or the convoy
has no more.

**Part 3: what a thief can take, from the decomp.** The AI thief (class `CA_STEAL`) weighs a steal
before any attack (`cp_battle.c:44-52`). `AiAttemptStealActionWithinMovement` (`cp_battle.c:377`)
visits every unit it can stand beside this turn, skips one whose Spd is above the thief's
(`cp_battle.c:412`), asks `AiGetUnitStealItemSlot` (`cp_utility.c:914`) for the target's
best-ranked slot (`cp_battle.c:416`), and keeps the lowest rank over all targets
(`cp_battle.c:424`). It runs only with a free bag slot (`cp_battle.c:46`). The rank is
the item's place in `gAiStealPriorityItemList` (`cp_data.c:921`); an item not on it ranks 0xFF and is
never taken, so a weapon is never stolen and an equipped one is no safer than a carried one: only
the list decides. The Lockpick is the 5th entry (index 4) of the list, above every key and booster. (The player's own
steal, `AddAsTarget_IfCanStealFrom`, `bmtarget.c:760-787`, and `IsItemStealable`, `bmitem.c:824`,
are the player's menu, not the AI's.) `ActionSteal` (`bmmind.c:365-390`) removes the slot's item and
appends it to the thief's bag. A stolen item comes back only if the thief carries `US_DROP_ITEM`
(`popup.c:506`, set when a red unit gets an item through the item-got popup, not by the steal) and
falls with the item last in its bag; ADR 0379 saw a Ch3 thief give no drop.

**Part 3: the simulated phase already plays the game's AI, but a steal was dropped.** `aiDecide`
returned a strike or a staff act; a thief's `AI_ACTION_STEAL` came back as nothing, so the thief
stayed where it stood and the planner never saw the theft. Now:

- `sight.stealAct` reads the decision (target, item slot, tile). `sight.pilfer` stands the thief on
  its tile, moves the item with the game's own `UnitRemoveItem` and `UnitAddItem` through `call`
  (ADR 0369), after `api.keep16` on both bags, since a nested sandbox undoes only `api.write*` and
  a game call that writes a unit struct would otherwise leak one plan's theft into the next
  (`sight.moveItem`, which also clears the target's `US_DROP_ITEM` when the slot was its last item,
  as `ActionSteal` does), so a second thief finds the item gone, and reads whether the
  target opened a chest before and no longer does (`lock`, `GetUnitKeyItemSlotForTerrain` through
  `sight.opensAt`, the one owner of that read). A Chest Key, a Door Key or a Lockpick can all be
  stolen (all are on the list, `cp_data.c:921`) and all are priced the same way: whichever item
  was the holder's last chest opener sets `lock`. A theft never misses, so it is no branch: it
  rides on the way's strikes list (`.thefts`, carried by `sight.chain`) and `enemyPhase` returns it
  per outcome (`sight.phaseList`). The lookahead's first phase applies it too.
- The planner keeps, per unit a theft robs of its last chest opener in some outcome, the chance
  `st.opens` that it lives AND keeps an opener, summed per outcome: a way where the thief also kills
  the holder is not counted twice. `Goals.chance` takes a chest goal's taker at `p.opens`. The price
  is therefore the chest goals' existing worth times the theft's chance; there is no new number. A
  plan that moves the holder out of the thief's reach, or kills the thief (it is `gone`, so it does
  not decide), reads no theft. The chest the plan opens this turn (`st.took`) is not priced.
- After a theft the thief holds the key in game memory. The reads that could see it stale do not:
  the simulated phase's later enemies decide through the game's own AI on that memory
  (`aiDecide`); `units()` inside a sandbox is read fresh and dropped (`sight.lua:2561`); the
  closings replay is keyed by the turn and decides by `aiDecide` (`sight.lua:3743`), and a real
  theft happens in the enemy phase, so the next player turn's key is new; and `M.opensChests` is
  asked only of a wave's units not yet loaded (`sight.lua:3777`), never of a thief.
- A plan with no thief able to steal scores as before: `thefts` is empty and `lock` never set.

**Not built (reported on #711).** (1) A thief carrying a stolen item as a goal. Killing the thief
gives the item back only when the thief has `US_DROP_ITEM` (above), so a goal worth the item
would pay a value the game gives only to a drop-flagged thief. Whether Ch16's thieves carry the flag
is not read here. Such a goal needs a goal kind with a moving tile and an escape time, and is left
as its own change. (2) Doors: a stolen Lockpick also
costs the doors the holder opens, but a door is a way (`turnsTo`), not a goal, so only the chests are
priced. (3) A theft in the lookahead's second phase is played on the board but not priced.

**Evidence.** Unit tests, each mutated to fail: `Bot.supply` takes two Chest Keys for two chest
tiles, one where a one-use Lockpick is held, and shares a Lockpick's uses across chests and doors;
`Sight.demandsOf` counts `locks` and `Sight.lockNeeded` drops the shut-out; a planner fixture moves
a Lockpick or Chest Key holder out of the thief's reach, counts a robbed-and-killed way once, and
leaves a holder whose stolen item opens nothing where it was; `Goals.chance` reads `p.opens`;
`Sight.pilfer`, `moveItem`, `chain` and `phaseList` run on fake memory and a fake `call`.
`Sight.stepOf` is the one dispatch of an enemy's act (steal, then staff, then strike) for
`enemyPhase` and `nextPhase`, tested with stub handlers; `s.demands`'s reach is tested on a real
`Sight.new` (a reached, a cut-off, an opened and a no-unit lock).

**Replays** (ADR 0430's one game each; both on vanilla, before the review's fixes above):
- `fix711`, Ch16 `b640e-cs-s4009` attempt 1: won in 22 turns, 0 deaths, not clean (the original:
  14 turns). It diverged at turn 1 from the extra prep key. The misses are #714's pattern (Colm
  pinned at (2,17) and (2,18)); the lock factor was 1 throughout, so no Lockpick theft was priced.
- `fix711b`, Ch21 `s4003` attempt 1: prep took two Chest Keys and opened one chest more than the
  original, but the game ended stuck after 44 turns.
Neither is a before-and-after of the theft price: the bot changed since #699's measurement, and no
main replay controlled for it.

**Ch16's doors, checked against `fix711c`'s prep.** The team demands read `doors locks 3` and
`chests locks 4`; Eirika took two Door Keys (item 106), one fewer than the doors, which fits one
use of Colm's Lockpick covering the third. That is what the rule intends. Whether Ch16's doors are
needed is not settled here: the trace plays no door act, so the two keys went unused, and why is not read
here. The count itself did not over-take.
