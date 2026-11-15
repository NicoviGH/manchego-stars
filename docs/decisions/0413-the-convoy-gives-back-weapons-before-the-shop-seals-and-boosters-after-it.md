---
id: 413
title: "The convoy gives back: weapons before the shop, seals and boosters after it"
date: "2026-11-14"
section: "Combat System"
issues: [510]
---

# The convoy gives back: weapons before the shop, seals and boosters after it

The bot sent seals, boosters and spare weapons to the convoy (the party's shared storage) and
never took anything out. It promoted a unit only when that unit carried its own seal, and it
never used a booster. At campaign 4006's Ch13 start (tag `lap1d`) the convoy held a Knight
Crest, a Guiding Ring, three boosters and an Elfire, while Forde (Cavalier, level 10) went
unpromoted, Lute (Mage, level 10) had no tome and Eirika carried a Guiding Ring and an Orion's
Bolt she can never use. This is the party plan's PR 2 (#510 comment 6883980081), built as the
convoy design settled it (#510 comment 6872948037), with one change of mechanism (decision 3).

**Decision 1: one pure rule in two steps, every "can use" the game's own.**
`Bot.supply(party, convoy)` runs before the shop. A fielded unit carrying a seal or booster it
cannot use, which another roster unit can (a benched unit too), gives it to the convoy. Then
each fielded unit takes, for each weapon or staff type in the convoy that it can use and holds
no usable item of, the convoy's best of that type: the highest rank, then the most uses. The
unarmed go first, as in the shop. `Bot.uses(party, convoy)` runs after the shop. It gives a
seal to each fielded unit the game says one promotes, highest level first. Then it gives a
booster to each unit left that the game says gains from one: the units the game forces onto
the map first (the lord), then the lowest level. A unit uses its own item first, else the
convoy's. A full bag first gives the convoy what `Bot.fullBag` would send. A unit uses one
item a chapter, the seal first, because each use is the Item command and costs that unit its
first turn. The facts are the game's: `CanUnitUseWeapon` / `CanUnitUseStaff`,
`CanUnitUsePromotionItem`, and for a booster an item with stat bonuses that the prep screen's
Use offers (`CanUnitUseItemPrepScreen`, which asks `CanUnitUseStatGainItem` and says no once a
stat is capped). No unit, class or chapter is named.

**Decision 2: `Bot.fullBag` keeps a seal or booster its holder can use.** A new one is wanted.
A held one is no longer the second thing to leave; only one its holder cannot use is.

**Decision 3: take and give are the game's own container calls, not the Supply screen
driven by keys.** The design opened the convoy screen on the map (`StartBmSupply`) and drove
Take and Give with keys. The screen itself is three calls (`prep_itemsupply.c`). A give clears
the bag slot, `UnitRemoveInvalidItems` packs the bag, and `AddItemToConvoy` stores the item. A
take is `UnitAddItem` then `RemoveItemFromConvoy`, which packs the convoy. The harness makes
those calls kept, on the first player phase, so no screen is opened and no turn is spent. They
leave the bags and the convoy as the prep screen's Supply would have, and that screen reaches
every unit for free. Each act finds its item by id and uses, and checks after the call that
the item has moved; a failed act stops the campaign with its reason. The supply runs only when
the game gives the party a convoy (`HasConvoyAccess`). Use stays the Item command, as for
seals before; `api.use` widens `api.promote` to boosters, and a seal's use counts only once
the unit's class has changed.

**Decision 4: the pick reads the convoy too.** `Bot.arms(gold, stock, roster, convoy)` runs
`Bot.supply`'s weapon step and then the shop over the unarmed units, so a unit the convoy will
arm is read holding that item at its stored uses (`api.needs`), and the shop buys none of that
type.

**Decision 5: the convoy is read to its first empty slot, not by `gConvoyItemCount`.** ADR
0412's read took its count from `gConvoyItemCount`, which `convoymenu.c` sets only when the
send-to-convoy chooser opens, in an overlay other screens reuse. The game keeps the array
packed, so the read stops at the first empty slot, at most 100. At `lap1d`'s Ch13 start the old
read listed 8 items and the new one lists 16. That matches the 16 the design comment read from
the `.ss`.

**The record.** Each chapter line gains `supply`, the acts in order:
`{ act, unit, item, uses, seal, why }`.

**What it proved** (`lap1d`'s saved Ch13 start, campaign 4006, one attempt, tags `conv1`
to `conv3`, one game (`conv2` and `conv3` share `acts_hash` 6193d3a3); `gear2` is PR 1's run
of the same start). Eirika (0x01) gave the convoy her Guiding
Ring. Lute (0x0C) took the convoy's Elfire, then the Guiding Ring, and used it: class 0x26 to
0x28, Mage to Sage. Forde (0x10) gave a Barrier staff he cannot use to make room, took the
Knight Crest and used it: class 0x05 to 0x07, Cavalier to Paladin. Seth (0x02) took a Silver
Sword. Eirika used a Secret Book, Gerik (0x14) the Secret Book he carried, and Dozla (0x1A),
Innes (0x0B) and Moulder (0x05) an Angelic Robe or a Dracoshield each. The chapter was won in
4 turns with no death (`gear2`: 8 turns, no death). Seth took 10 of 24 kills (`gear2`: 15 of
35), Lute 4 (`gear2`: 1). Both runs miss the same recruit (charId 0x0E, as `gear2` did). One
game is a lead, not a verdict.

**Cost.** A convoy read asks the game about each bag item and convoy item for every roster
unit. A non-weapon's answers read only its id (`GetUnitItemSlot`, `GetUnitItemHealAmount`,
the two use checks), so one read serves each unit and id. A chapter start reads the convoy
once for the pick. An attempt reads it twice: before the supply and after the shop. On the
Ch13 start the sandbox ran about 6,000 frames of game code before the first move in `gear2`.
It ran 16,800 in `conv2` and 14,400 in `conv3` (the memo); one of `conv3`'s three reads per
attempt is now gone. A Ch15 decision costs about a million.

**Unit tests** (`test_bot.lua`, `test_campaign.lua`). Each rule has a test, and each test was
seen to fail with its rule broken: unarmed first, forced first, one use a unit, and a give only
for an item someone can use. The two `fullBag` twins fail on main's code. On main the
`Bot.supply` and `Bot.uses` tests error, because neither function exists there.

**Not covered here.** Each use costs the unit its first turn: in the run 7 of 12 fielded units
used an item on turn 1. The prep screen's Items, then Use, would cost none; build it only if
the lap's records show this costing a chapter. A branched promotion still takes the first class
the menu offers. A benched unit's bag is out of reach. Whether `HasConvoyAccess` closes the
supply on the chapters before the convoy opens is shown by the proof lap from the prologue, not
here.
