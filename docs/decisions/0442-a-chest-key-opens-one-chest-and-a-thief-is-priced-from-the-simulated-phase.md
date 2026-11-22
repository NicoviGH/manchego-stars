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
`takeKeys` wants `locks` keys, less what the fielded bags already open (an item that opens counts
its `uses`: a Chest Key 1, a Lockpick as many as it has left), and takes from the convoy, one per
pass, to the unit with the most free slots then, until the want is met or the convoy has no more.

**Part 3: what a thief can take, from the decomp.** The AI thief (class `CA_STEAL`) weighs a steal
before any attack (`cp_battle.c:44-52`). `AiAttemptStealActionWithinMovement` (`cp_battle.c:377`)
visits every unit it can stand beside this turn, skips one whose Spd is above the thief's
(`cp_battle.c:412`), asks `AiGetUnitStealItemSlot` (`cp_utility.c:914`) for the target's
best-ranked slot (`cp_battle.c:416`), and keeps the lowest rank over all targets
(`cp_battle.c:424`). It runs only with a free bag slot (`cp_battle.c:46`). The rank is
the item's place in `gAiStealPriorityItemList` (`cp_data.c:921`); an item not on it ranks 0xFF and is
never taken, so a weapon is never stolen and an equipped one is no safer than a carried one: only
the list decides. The Lockpick ranks 4 of the list, above every key and booster. (The player's own
steal, `AddAsTarget_IfCanStealFrom`, `bmtarget.c:760-787`, and `IsItemStealable`, `bmitem.c:824`,
are the player's menu, not the AI's.) `ActionSteal` (`bmmind.c:365-390`) removes the slot's item and
appends it to the thief's bag. A stolen item comes back only if the thief carries `US_DROP_ITEM`
(`popup.c:506`, set when a red unit gets an item through the item-got popup, not by the steal) and
falls with the item last in its bag; ADR 0379 saw a Ch3 thief give no drop.

**Part 3: the simulated phase already plays the game's AI, but a steal was dropped.** `aiDecide`
returned a strike or a staff act; a thief's `AI_ACTION_STEAL` came back as nothing, so the thief
stayed where it stood and the planner never saw the theft. Now:

- `sight.stealAct` reads the decision (target, item slot, tile); `sight.moveItem` does
  `ActionSteal`'s bag change; `stagePhase`'s `pilfer` stands the thief on its tile, moves the item
  (so a second thief finds it gone) and reads, with `GetUnitKeyItemSlotForTerrain`, whether the
  target opened a chest before and no longer does (`lock`). A theft never misses, so it is no
  branch: it rides on the way's strikes list (`.thefts`) and `enemyPhase` returns it per outcome.
  The lookahead's first phase applies it too.
- The planner sets `st.robbed[unit]`: the chance, over the phase's outcomes, that the unit lost its
  last chest opener. `Goals.chance` multiplies a chest goal's taker by `1 - robbed`. The price is
  therefore the chest goals' existing worth times the theft's chance; there is no new number. A plan
  that moves the holder out of the thief's reach, or kills the thief (it is `gone`, so it does not
  decide), reads no theft. The chest the plan opens this turn (`st.took`) is not priced.
- A plan with no thief able to steal scores as before: `thefts` is empty and `lock` never set.

**Not built (reported on #711).** (1) A thief carrying a stolen item as a goal. Killing the thief
gives the item back only when the thief has `US_DROP_ITEM` (above), so a goal worth the item
would pay a value the game gives only to a drop-flagged thief. Whether Ch16's thieves carry the flag
is not read here. Such a goal needs a goal kind with a moving tile and an escape time, and is left
as its own change. (2) Doors: a stolen Lockpick also
costs the doors the holder opens, but a door is a way (`turnsTo`), not a goal, so only the chests are
priced. (3) A theft in the lookahead's second phase is played on the board but not priced.

**Evidence.** Unit tests (each fails on the code before this change): `Bot.supply` takes two Chest
Keys for two chest tiles, and one key where a one-use Lockpick is held; `Sight.demandsOf` counts a
demand's `locks`; a planner fixture moves a Lockpick holder off the tile the fixture's thief steals
from, and leaves a holder whose stolen item opens nothing where it was. `Sight.stealAct` and
`Sight.moveItem` read and move on a fake memory. The replay is on #711's PR.
