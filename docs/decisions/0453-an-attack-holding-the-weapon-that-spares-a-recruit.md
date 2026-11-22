---
id: 453
title: "An attack holding the weapon whose counter spares a recruit"
date: "2026-11-22"
section: "Combat System"
issues: [730, 699, 510]
---

# An attack holding the weapon whose counter spares a recruit

**Decided (#730 fix 4), #510 step 9.** Adds acts only; no scoring change, no new weight. It is the
case ADR 0451 left out ("one that attacks and is then struck").

**The gap.** Of the 106 recorded recruit counter deaths, 60 were by a unit that had attacked that
turn (52 of them countering with the weapon they attacked with, 53 carrying two or more weapon
ids); a wait cannot help them, since a unit that has acted holds what it struck with into the enemy
phase. `attackOptions` already builds one option per enemy, tile and weapon, but `proposeOne` keeps
`best`, `safe` and `guard` per enemy and dedupes them by `act@x,y>target` with no slot, and none
reads a recruit's counter (`worstCase` asks `exposure` with no slot). The judged phase did price the
counter with the attack's weapon (`strikeAct` sets `slot`, `stageWear` arms it), but it was never
shown a strike holding the sparing one.

**What changed.** `Bot.candidates` offers `sparingStrikes` beside `sparingWaits`: for each target
and strike tile among the unit's options, the attack holding the weapon with the lowest cost, the
recruits' chance to fall to our counter (`counterOn`) plus our unit's own chance to die there
(`dieAt`), when it beats the weapon held now by more than `Goals.DUST`. The weapon held now is the
pick kept on that tile, or `betterAttack`'s on a tile no pick took. The act is `strikeOf(u, c)` (the
one owner of what a strike carries, lifted out of `proposeOne`'s `strike`), with `slotKey` so
`Planner.key` tells it from the kept pick, and `why = "gentle"`, so the planner's per-unit cut keeps
it (ADR 0451's line) and the mend's recruit menu finds it. The loop that picks, orders and caps is
shared with `sparingWaits` (`sparingPicks`), as is who counts as a recruit (`sparingRecruit`:
`ctx.recruits` and ADR 0452's `ctx.looseRecruits`).

**The cap is separate, `M.GENTLE` (2) each.** A unit strikes or waits, never both, so a plan holds
one gentle act of one unit; a shared count would let strikes crowd waits out of the menu and change
ADR 0451's behaviour. The bound is two extra judged phases per struck unit per mend round for waits
and two for strikes.

**What it does not do.** It decides nothing: a weaker weapon may fail the kill, and the judge reads
that trade (the kill's value against the forfeit). It offers nothing where no weapon spares the
recruit (a weapon whose damage still fells it), where the sparing weapon kills our unit, or where
the unit has one weapon. It does not cover a unit that uses an item (4 of the 60) or the units that
waited (38; ADR 0451).

**Proof.** `test_bot.lua`: a unit with two weapons strikes T from a tile in reach of a recruit R;
slot 0's counter fells R, slot 2's does not. On main no strike carries slot 2; now the menu offers
`attack#2` ("gentle", `slotKey`), the plan played is that attack with no forfeit at `PER_UNIT` 1 and
0 (it fails without the planner's `gentle` exemption, as does ADR 0451's wait). Negative: a
weapon whose strike kills our unit is not offered; with a third weapon that spares both, that one
is. Cap: three sparing tiles, two kept (fails without the cap; three with `M.GENTLE` 3).

**Cost.** Recruit boards only (`sparingRecruit` is nil with no recruit or one weapon): the
exposure read per strike tile and weapon, memoised, with the same cap as ADR 0451. Timed on vanilla
Ch10 `m699c10-b640e-cs-s4002`, `resume --attempts 1`, base then branch back to back: 78.3 s base,
81.2 s and 81.3 s on two branch runs (about 4 percent, same outcome: won turn 16, 1 death).

**Replay (tag `fix730i`).** Vanilla Ch10 `b640e-cs-s4007`, `resume ... --attempts 2 --scout --route 1
--seal-at 10`. Both attempts won (turns 19 and 18, one death each, neither Amelia's counter by an
attack). Attempt 1: a gentle wait was played on turn 7 (unit 11 holding its Iron Sword) and Amelia
still fell to its counter: the iron sword hit for 15, then 1, on her 16 HP, so no weapon in its bag
spared her. Attempt 2: she was never struck by our counter. The replayed games did not reach the
recorded attack-counter death, so the new act was not played; the unit test is its proof.
