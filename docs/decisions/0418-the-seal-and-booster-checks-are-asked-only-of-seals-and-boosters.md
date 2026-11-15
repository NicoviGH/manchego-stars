---
id: 418
title: "The seal and booster checks are asked only of seals and boosters"
date: "2026-11-15"
section: "Combat System"
issues: [510]
---
# The seal and booster checks are asked only of seals and boosters

The fresh lap on Ephraim's route (tag `lap3p`, campaign `cs-s4006` from the prologue, scout)
crashed at the start of vanilla Ch13 on his route (chapter id 26, `CHAPTER_I_13`): "use 0x0F
item 0x6D: the item could not be used". Ephraim (charId 0x0F) was sent to use an Elixir
(0x6D), which is neither a seal nor a booster.

**Cause (the code path is the decomp's; that it fired here is shown by the control below).**
`INSPECT.unitItemFacts` asked `CanUnitUsePromotionItem` of every item that is not a weapon.
The game itself never does: its Use (`CanUnitUseItem`, `bmitemuse.c`) routes only the promotion
items there. `CanUnitUsePromotionItem` returns false under level 10, then sets a class list by
item and walks it (`CHECK_LIST`) with no guard: for any item that is not a seal the list is
NULL, so a unit at level 10 or higher walks memory from address 0. (Eirika's and Ephraim's
earlier branch, for the two braces, does guard its walk.) For Ephraim's Elixir, at level 10,
that came back true, so `Bot.uses` played it as a seal.

**Decision: each check is asked only of the items the game's own Use routes to it.** `promotes`
is read only when the item's `use` is "seal" and `gains` only when it is "booster" (ADR 0416's
`INSPECT.BAG.USE`, pinned to the switch by `tools/test_harness_item_use.py`). The booster check
is `CanUnitUseItemPrepScreen`, which for a booster is `CanUnitUseStatGainItem`; the earlier
gate on a stat-bonus pointer goes, since `use` now says what a booster is.

**Proof** (the start `lap3p-cs-s4006/26`, saved by the lap's own bot, one attempt each). Control
on main's harness (tag `elix0`): the same crash, "use 0x0F item 0x6D". With the fix (tag `elix1`):
Ephraim takes the convoy's Luck booster (0x5F) and uses it, another unit uses its Defense booster
(0x60), nothing touches the Elixir, and Ch13 is won in 16 turns with no death.

**Earlier runs.** Every unit at level 10 or higher was exposed. No run ever used a wrong item:
the 4,290 vanilla worker logs hold 88 seal and booster uses, every one a seal or booster id
(the Ephraim crash was the first, and a failed act is not logged as played). What a wrong
`promotes` did in `Bot.fullBag` is not recoverable from the records. That path is guarded now:
`Bot.fullBag`'s "a seal or booster it cannot use" asks the item's `use` too, so Pure Water, a
Torch or the Juna Fruit is no longer sent as one (review of PR #626).

**Why no Lua unit test.** `unitItemFacts` runs only inside mGBA (no Lua test loads
`harness.lua`); the control and fix runs above are the test that fails without the fix.
