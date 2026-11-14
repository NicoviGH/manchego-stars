---
id: 412
title: "The shop arms a unit by the game's own can-use and uses left, and the pick reads it holding what the shop will buy"
date: "2026-11-14"
section: "Combat System"
issues: [510]
---

# The shop arms a unit by the game's own can-use and uses left, and the pick reads it holding what the shop will buy

On the scout lap (ADR 0409), campaign 4006 reached Ch15 with 6 of 23 units holding nothing
they could fight with, and the five that ran dry through Ch13 were never fielded again
(#510 comment 6883980081, PR 1 "Gear"). `Bot.shop` bought only for the fielded team, only a
weapon type the unit "held none of", never a staff, and a unit with no weapon ranked last in
the pick and was benched: a benched unit is never bought for.

**Decision 1: a unit is armed when it holds a weapon or staff the game says it can use
(`CanUnitUseWeapon`, `CanUnitUseStaff`) with uses left.** `Bot.armed` is that test; a tome with
0 uses, or a lance its rank forbids, arms nobody. `Bot.shop` buys, for each weapon or staff
type in stock the unit can use and holds no usable item of, the cheapest stock item of that
type, as it bought weapons, now staves and tomes too. It checks bag room (five slots, one
bought each), and a unit with nothing usable in hand keeps the last slot for its arms, not a
Vulnerary.

**Decision 2: the harness reads an item once.** `INSPECT.itemFacts` is the one read of an
item's data (weapon or staff, type, rank, reach, effectiveness, the Vulnerary); `unitItemFacts`
adds what a unit changes (can-use, uses, key, heal...). The roster and the stock both go
through them, so a staff is told from a sword the same way in the bag and on the shelf. The
roster, read three times a chapter, asks only for can-use, uses and the Vulnerary (a flag on
`unitItemFacts`); the key, passive and heal classification is `Bot.fullBag`'s alone and was a
sandbox read per held item for nothing.

**Decision 3: the pick reads a unit the shop will arm holding everything it will buy, and
`Bot.arms` is `Bot.shop`'s own spend loop.** The shop's loop (the unarmed units first, then the
armed; within each, Vulneraries first, then each unit's weapons in order; one purse, five bag
slots) is the one owner of the spend order.
`Bot.arms` runs it over the unarmed units and returns, per unit, every weapon or staff it
bought (a list: a unit that can use a staff and a sword holds both, types in name order), so
a purse that arms one of four units says so, and the two cannot drift. Because the shop pays
the unarmed before the armed, no armed unit's Vulnerary takes the gold that arms a fielded
unit, and the fielded unarmed are a subset of `arms`' units in the same order: a unit `arms`
arms, the shop arms. A weapon is the game's own flag (`IA_WEAPON` or `IA_STAFF`), not a named
type, so a Divinestone's holder is armed. `api.needs` asks the game, in a sandbox, what the unit answers (`sight.holding` writes the
items after its own into its bag and puts them back; it refuses a bag with an item past a gap,
which the board read and the roster would not list). `Bot.team` is unchanged: it ranks by the
strengths it is given. A unit nothing in stock arms is read as it is, last.

**Decision 4: the state says what is left.** The chapter-start record (`startRecord`) gains
each item's uses left and the convoy's contents (`gConvoyItemArray`, read by `INSPECT.convoyItems`,
clamped to the game's 100); the chapter line gains `buys` (each purchase: unit, item) for the attempt.

Against ADR 0396's tests: each rule names a quantity the game produces (can-use, uses left,
price, the unit's strength with the item); each is a purchase or an ordering; none names a
unit, class or chapter; the owners are the existing ones (`Bot.shop`, `Bot.team`'s input,
`between()`, `api.save`/`roster`/`needs`).

**Not covered here.** Weapon quality (a better weapon than the one held), taking from the
convoy and experience are the plan's PR 2 and PR 3.

**What it proved** (`lap1d`'s saved Ch13 start, campaign 4006, one attempt, tag `gear1`). The
pick fielded Artur (0x13), Vanessa (0x06) and Lute (0x0C), three of the five units that had
run dry (Natasha stayed benched; Dozla held a Battleaxe at this start), and the shop armed each:
Artur a tome, Vanessa a lance, Lute an Anima tome, and Joshua (0x20) an Iron Sword. The attempt
was won in 8 turns with no death. `buys` also lists a Heal staff for 0x17 and an Iron Sword for
Seth: each lacked a type it could use, as the shop already bought. The saved state lists each
item's uses and the 8 convoy items (read from the saved record, not cross-checked in the
emulator).

Unit tests (`test_bot.lua`, `test_campaign.lua`), run once against main's code with the new API
stubbed: a tome with 0 uses, a lance the unit cannot use, a full bag and the last free slot
fail on main. A healer with no staff buys one passes there: on main the gap was in the harness,
whose item read gave a staff no type, which no unit test reaches.
