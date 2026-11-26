---
id: 479
title: "A teammate's key is a way, by Trade"
date: "2026-11-26"
section: "Combat System"
issues: [688, 764, 711, 768, 510]
---

# A teammate's key is a way, by Trade

**Decided (#764's "After R4" item 4, Nicolas 2026-11-26: fix them all, one PR each).** The bot
gets the game's unit-menu Trade, for keys first: a key in a teammate's bag is a way to the lock
it opens, as an enemy's drop already is.

**Why.** R4 (#768): vanilla Ch21 s4009 a1 won with no deaths and missed only the (2,18) chest,
because its spare Chest Key sat on Eirika, who held at (12,18) and never handed it over. The bot
had no Trade, so a key in a teammate's bag opened nothing for anyone else.

## The rule

- **A source of a key** (`keyWay`) is an enemy whose fall gives it (`keySources`) or a teammate
  that spares one (`Goals.spareKey`, the one test; `Goals.spareKeys` lists them for `keyWay`, the pairing's `sure` and `Goals.list`'s takers
  alike). A teammate spares its key for a chest only once its own trip to that chest has stalled
  (`ctx.tried`: the units a stalled chest was taken from), and never for a door. A holder opens
  its own chest itself and the job matcher already weighs it there; a door's holder opens it and
  its escort is already every unit's way (`doorMates`). The key must open the lock for the taker
  (`sight.bagKey`: the game's own key check, `GetUnitKeyItemSlotForTerrain`, as the taker; a
  thief's Lockpick opens nothing for anyone else). A chest whose key a teammate spares has a
  taker, so it is a goal.
- **The price** is the taker's own walk: to the holder, then on from there. Never the holder's
  walk to the taker: nothing sends the holder, so that price counts a meeting no one walks.
- **Why both limits, from two replays of vanilla Ch21 s4009 a1** (control on main, `c688m`: won
  in 30 turns, no deaths, the (2,18) chest stalled):
  - `t688a` priced both meetings: Dozla stood by the (21,18) chest four turns, priced 1 turn
    through Gerik's Chest Key while Gerik held back under the risk cap; both died (18 turns, 5
    deaths).
  - `t688b` priced every holder's key as every teammate's way: the only two Chest Keys were
    Eirika's and Dozla's, the two chest jobs' own takers, yet every unit's way to a chest read
    2-5 turns nearer (Marisa's to (2,18): 9 turns to 5). The game left main's on turn 1 and lost
    two units (19 turns, 2 deaths).
- **The act** `trade` (`tradeAct`): from the safest wait tile the gate allows where the game's
  Trade lists the other unit (`ItemSubMenu_IsTradeAvailable`), the actor takes the key, or, with
  `gives`, the holder hands it over. A taker with a full bag gives back what the game's full-bag
  chooser would send (`Bot.fullBag` over `sight.bagFacts`); with everything it carries needed, no
  Trade is offered. The act ends with a Wait (the game returns to the unit menu; a Wait after a
  Trade earns no Canto). The planner scores it as the convoy's Take (`W.breach`); a second Trade
  of the same key in one plan is blocked.
- **Legality** (`sight.legal`) is the game's Trade check with the selection's taken-action flags
  cleared (`BmSt +3D`, as the game clears them for a selected unit), the other unit listed, and
  the bags still holding the items the act names.
- **The harness** drives the real Trade screen (`INSPECT.trade`, `ProcScr_TradeMenu`): the
  holder's item, then the taker's free cell or the item it gives back, A swaps them, the bags are
  read back, B ends the screen. Every Trade is in the run's record (`rec.trades`, trace `trade`).

## Left out

- **Counting a door only when its opener is sent** (#688's old step-1 design, "honest pricing").
  It reprices every door way, not only a Trade's, so it is not part of this change; it is built
  only if a run shows a door priced through an opener nobody sends.
- **Trade for weapons and Vulneraries** (#688 step 2), a mid-map convoy Give and a player Steal
  (#688 comment of 2026-11-26): each needs its own pricing call first.
