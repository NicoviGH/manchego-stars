---
id: 416
title: "What a unit cannot use goes to the convoy, and a spare comes before the last weapon breaks"
date: "2026-11-15"
section: "Combat System"
issues: [510]
---
# What a unit cannot use goes to the convoy, and a spare comes before the last weapon breaks

Vanilla Ch15's party on Eirika's route (`party1e`, #510 comment 6896123722) still carried
items nobody could put to use. The Fable design pass of 2026-11-15 (#510 comment 6896261936)
read the code, the kept states and the decomp and found two of the five gaps need no rule:
Eirika's Lunar Brace is given in Ch16's ending (`ch16a-eventscript.h`), and Innes took the
convoy's Steel Bow at Ch15 (the saved start is read before the supply runs). The other three
are one gap, and the bow gap was a second one. Nicolas approved both rules, and one PR for
them, on 2026-11-15.

**Decision 1 (rule A): before the shop, every roster unit gives the convoy what it cannot use
this chapter.** A weapon or staff the game says it cannot use (`CanUnitUseWeapon` /
`CanUnitUseStaff`, `cannotUseWeapon`, the test `Bot.fullBag` already uses); a seal or booster
the game says it cannot use now (`CanUnitUsePromotionItem`, `CanUnitUseStatGainItem`); and a
benched unit's every seal and booster, since only a fielded unit uses one (`api.use` is the
map's Item command). From the convoy the existing rules hand each to a fielded unit that can
use it (`takeWeapons`, `Bot.uses`). It replaces ADR 0413's "only if another roster unit can
use it today": a seal nobody can use yet (every Guiding Ring class under level 10) stayed in a
bag, and a benched unit's booster never reached a fielded unit. A Vulnerary, a key or a gem
stays where it is.

Which item is a seal or a booster is the game's own split: the two id lists of
`CanUnitUseItem`'s switch (`bmitemuse.c`) that route to `CanUnitUsePromotionItem` and to
`CanUnitUseStatGainItem`, kept as `INSPECT.BAG.USE` and read into every item's facts as
`use`. No use-effect value marks a seal (each item has its own), so the ids are listed, and
`tools/test_harness_item_use.py` checks them against the switch. Metis's Tome and the Juna
Fruit are neither (the switch sends them elsewhere), so they stay where they are.

**Decision 2 (rule B): a unit is short of a weapon type when its usable items of the type hold
fewer uses, together, than half of one full weapon of the type.** "One full weapon" is the
fewest full uses (ItemData `maxUses`, read into every weapon's facts) among the type's items on
offer that it can use and the ones it holds. So Innes with a Silver Bow at 4 of 20 uses takes
the convoy's Longbow, Eirika with a Rapier at 4 of 40 buys an Iron Sword, and an Elfire at 29
of 30 buys no 40-use Fire. One test (`shortfall`, `M.SPARE` times one full weapon less the uses
held) serves the convoy's take, the shop and `Bot.arms` (through `lackedTypes`) and
`Bot.fullBag` (a weapon arriving in a full bag is wanted when its holder is short of the type);
`Bot.armed` does not change. The convoy's take prefers a weapon whose uses end the shortage,
then the highest rank, so the shop does not buy another after it. A weapon on offer without its
full uses raises, so a missing read never passes as "holds none". The line is Nicolas's call (a
purchase with a line in it, ADR 0396 test 2): half a weapon (`M.SPARE` = 0.5, 2026-11-15), to
be tuned if it has adverse effects. At one whole weapon (the PR's first draft) a unit that had
spent one use of its smallest full weapon was short, so it bought a spare at every chapter
start (review of PR #624). Our research has no record of how vanilla players keep spares.

**Decision 3: each attempt's prep is on its own record.** ADR 0413 said the chapter line keeps
`supply`; `montecarlo.py`'s `records_of` dropped every chapter line, so `resume-runs.jsonl` had
neither `supply` nor `buys` and they lived only in the worker log. The chapter line now keeps
`prep`, one `{ attempt, supply, buys }` an attempt (each attempt loads the start and preps
again; an attempt whose prep failed keeps the acts that ran before the failed one), and
`records_of` files each on its attempt's BOTRUN record as `supply` and `buys`. An attempt whose
prep failed never played, so it has no BOTRUN record: its prep goes on the campaign's end
record as `prep`.

**ADR 0396's five tests.** Both rules name the game's own answers (can-use, uses, full uses);
rule A is a free move only the game can refuse (no convoy access, a full convoy), rule B a
purchase whose cost is gold and a bag slot (a full bag still buys nothing); neither reads an
objective or style; each widens the one owner (`Bot.supply` step 1, `shortfall`); neither names
a unit, chapter or witness.

**Proof.** Unit tests that fail on main: `test_bot.lua` (a weapon its holder cannot use goes
back while a usable seal and a Vulnerary stay; a seal nobody can use yet goes back; a benched
unit gives its seals, boosters and unusable weapons; a full convoy takes none; a 4-use bow
takes the convoy's bow; a 4-use Rapier buys a sword; a Rapier at half its uses buys none and
under half buys one; a weapon with no full uses raises; the convoy's bow that ends the shortage
beats a higher-rank worn one; a full bag takes a lance when its own is near breaking),
`test_campaign.lua` (the benched bags reach `Bot.supply`; a failed prep keeps the acts that
ran), `test_montecarlo.py` (each attempt's prep lands on its BOTRUN record, a failed one on the
campaign's end), `tools/test_harness_item_use.py` (the seal and booster ids are the switch's).
The run proof is the fresh lap from the prologue on main (Nicolas, 2026-11-15: no more proofs
on outdated saves), whose records now carry the prep.

**Known cost and untested.** Up to three more units spend their first turn on a booster (ADR
0413). A spare costs gold and a bag slot; how often half a weapon buys one is untested.
Mid-chapter, a unit under half a weapon that is handed a same-rank weapon in a full bag now
keeps it: with room in the convoy something else is sent there (money first), and with a full
convoy a spare healing item is discarded for it, for good (`Bot.fullBag`'s discard order;
review of PR #624). Untested: a give from a benched unit in a real run; whether Ch16's ending
promotes Eirika by itself and passes the harness; whether any unit stood unarmed for turns
before rule B.
