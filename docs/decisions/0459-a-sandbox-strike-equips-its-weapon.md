---
id: 459
title: "A sandbox strike equips its weapon"
date: "2026-11-23"
section: "Combat System"
issues: [743, 510]
---

# A sandbox strike equips its weapon

**Decided (Nicolas, 2026-11-23, #743 comment 7116037866: the plan that cut PR #755 to its two bug
fixes), #510 step 9.** Amends ADR 0389 (the second phase); how a later phase is played and counted
is unchanged, and so is who the wear (ADR 0421) reads.

**The problem.** The game equips the weapon a unit strikes with (`EquipUnitItemSlot` reorders the
bag). The sandbox's enemy strike wore the ledger and never equipped, so every phase read after the
first (the lookahead's second phase, the wear's later ones) started from the bag in its old order.
Ch13's enemy 138 alternates a Steel and a Killer Lance (22, 26, 22, 26 damage over turns 6 to 11);
the real kill was a Killer Lance crit, and the second phase read the Steel Lance, which has none.

**1. The enemy's strike equips (`sight.lua` `M.strikeLedger`).** The strike equips `side.slot`
through `M.armAsPlanned`; the ledger's rows follow their items, and the strike's uses are read off
the weapon where the equip put it (`M.strikeWear`'s `armed`). A ballista shot (slot 0xFF) and a
strike with no slot or from slot 0 equip nothing: `M.equip` is the one owner of which slots it
equips (1 to `Board.ITEM_COUNT - 1`), and a slot it refuses leaves the bag, the rows and the wear
slot as they were for every caller (`strikeLedger`, `replyArm`, `stageWear`'s blues).

**2. Our berserked unit's strike does not equip (`t.berserk`).** The army's reply picks its weapon
by the slot the board lists (`s.weapons`) when the berserk ends before it; a bag the strike
reordered would give that slot another item.

**3. The defender's counter is not equipped, and the game does not either.** A battle takes the
defender's weapon with `SetBattleUnitWeapon(&gBattleTarget, BU_ISLOT_AUTO)` (`bmbattle.c` 97, 126):
the first slot `GetUnitEquippedWeaponSlot` finds usable (`bmitem.c` 487), read in place, with no
`EquipUnitItemSlot` on that bag. `EquipUnitItemSlot` is called for the acting unit only
(`cp_perform.c` 218 and 361 for the AI, the menus for a player's unit; `bmbattle.c` 216 on a copy
for the forecast), so the counter's wear stays at `t.counterSlot` on a bag left as it was.

**Not done: the wider wounded read.** PR #755 first also read a wounded unit (struck, or left at
or under half its HP, a heal in reach or not) on the phases after the next. It was cut before
merge: the read past the first phase is not calibrated in either direction (#699 comment
7106711753, #743 comment 7113644701), the widening saved no unit the replays could point to, it
moved a Ch21 choice (vanilla `b640e-cs-s4007` attempt 1, turn 2) on a 57.5% read of Ephraim (charId 0x0F) that
plays no heal between the phases, and it cost +12.6% CPU. The calibration comes first (#743 plan,
step 2).

**Proof (ADR 0430).** Unit tests that fail without each part (`test_sight.lua` `strikeLedger`: a
slot-1 strike equips its weapon and spends its use where the equip put it, the ledger's rows follow
their items, a berserked striker and a slot-0 or slot-less strike leave the bag as it was, a slot
5 or a 0xFF leaves bag and rows alone through `strikeLedger` and `replyArm`, two phases' strikes by
one enemy each wear their own weapon). An enemy decides once per phase (`playPhase`'s order list),
so the second weapon is the next phase's strike, read off the bag the first reordered.

One replay of the witness: vanilla Ch13 `b640e-cs-s4007`, attempt 1 (`montecarlo.py resume`, scout,
`--seal-at 10`), with a temporary log of each decision's weapon. The copy's strike weapon for enemy
138 against the weapon the game struck with (`act` events), the copy's first phase against the same
turn's enemy phase and its second phase against the next turn's:

| Turn | Copy's phase | Copy's weapon | Game's weapon | Match |
|---|---|---|---|---|
| 1 | first | 20 | 20 | yes |
| 6 | first | 22 (Steel Lance) | 22 | yes |
| 7 | first | 26 (Killer Lance) | 26 | yes |
| 8 | first | 22 | 22 | yes |
| 10 | first | 26 | 26 | yes |
| 5 to 6 | second | 22 | 22 | yes |
| 10 to 11 | second | 22 | none: the attempt ended on turn 10 | not testable |

Enemy 138 had no strike in the copy on turns 2 to 4 (no decision logged for it), on turn 5 (its
first-phase decision was "none") and on turn 9 (at 8 HP, "none"), and the game made no `act` for
it on turns 2 to 5 and 9 either. The alternation 22, 26, 22, 26 that the old second phase got wrong
is read right.
