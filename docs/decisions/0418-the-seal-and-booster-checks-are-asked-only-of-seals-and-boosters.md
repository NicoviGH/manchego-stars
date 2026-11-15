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
items there. For Eirika and Ephraim, `CanUnitUsePromotionItem` first sets a class list only for
the Lunar and Solar Braces, then walks it (`CHECK_LIST`) whatever the item, so for any other item
it walks a NULL list and reads memory at address 0. For Ephraim's Elixir that came back true,
so `Bot.uses` played it as a seal.

**Decision: each check is asked only of the items the game's own Use routes to it.** `promotes`
is read only when the item's `use` is "seal" and `gains` only when it is "booster" (ADR 0416's
`INSPECT.BAG.USE`, pinned to the switch by `tools/test_harness_item_use.py`). The booster check
is `CanUnitUseItemPrepScreen`, which for a booster is `CanUnitUseStatGainItem`; the earlier
gate on a stat-bonus pointer goes, since `use` now says what a booster is.

**Proof** (the start `lap3p-cs-s4006/26`, saved by the lap's own bot, one attempt each). Control
on main's harness (tag `elix0`): the same crash, "use 0x0F item 0x6D". With the fix (tag `elix1`):
Ephraim takes the convoy's Luck booster (0x5F) and uses it, another unit uses its Defense booster
(0x60), nothing touches the Elixir, and Ch13 is won in 16 turns with no death.

**Untested:** whether a wrong `promotes` from the NULL list ever led an earlier run astray in a
quieter way (a seal kept or sent by `Bot.fullBag`); the lap's kept records do not say.
