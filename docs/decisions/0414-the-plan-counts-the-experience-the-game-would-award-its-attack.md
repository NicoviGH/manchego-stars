---
id: 414
title: "The plan counts the experience the game would award its attack"
date: "2026-11-14"
section: "Combat System"
issues: [510]
---

# The plan counts the experience the game would award its attack

At campaign 4006's Ch15 start (tag `lap1d`) Eirika was level 5 and the army averaged 5.1. From
Ch9 to Ch13, Seth took 94 of 209 kills and Eirika 2. The planner credited a kill the same
whoever made it. This is the party plan's PR 3 (#510 comment 6883980081). Nicolas settled the
weight on 2026-11-14 ("go with your recommendation"): 0.3 a point, the same in every style.

**Decision 1: an attack scores the experience the game would award it.** `score()`
(`planner.lua`) adds `W.exp` (0.3) times the experience the attack teaches its unit. A full
level is 100 points, worth about one kill (30, or 40 under bold). The number is the game's own
count, `GetBattleUnitExpGain` (`bmbattle.c`), so nothing names a level, a unit or a class.
The count is already large for a low-level unit and small for a promoted one. Seth (0x02),
promoted, gets 4 for killing a prologue soldier; Franz (0x04) gets 34 for the same kind of
kill. The term sits in the plan's value, which the rank reads after the risk cap and progress
(`Planner.outranks`). So experience never buys a plan over the cap. Inside the cap it weighs
against death chance like any other part of the value. Under careful, 30 points of
experience (9) weigh as much as a 0.9% death chance (1000 × 0.009).

**Decision 2: the count is read in the sandbox, three ways an exchange.** The forecast's
simulation does not award experience: only `BattleApplyExpGains` does, after a real battle.
So after the plain simulation, `Sight.expOf` calls `GetBattleUnitExpGain` on the
simulation's battle units three times. The count tells outcomes apart by two fields only: the
actor's `nonZeroDamage` and the target's HP. Each call sets those two, for blows that deal
nothing (`none`), blows that deal damage (`hit`) and a kill (`kill`). The actor's HP is set to
1, because a dead actor gains nothing. The read happens before the played ways run. Those runs
leave the battle units at the last way's state. The three numbers are stored with the
exchange's other played results (`playedBy`), under the same battle key. Only our attack
reads them (`exchange`'s `teaches`); an enemy's strike does not.

**Decision 3: the plan picks which of the three applies, at the HP it leaves the target.**
`taught(f, hp, unitHp)` walks the exchange's ways (`f.joint`). A way whose counter kills our
unit teaches nothing. A way that deals at least the HP the plan leaves the target is a kill.
Any other damage is a hit; no damage is `none`. So when an earlier blow of the plan chips the
target, the kill belongs to the unit that finishes it, and the plan can choose who that is.

**The record.** Each player-phase attack in the trace gains `taught`: the three numbers the
plan read. Every run checks them against the battle's own `exp` (its actor's):
`Botrun.taughtMiss` takes the case from the battle (actor dead, target dead, a blow of the
actor's that dealt damage, else none), and a read that differs is an anomaly, `taught_miss`,
on the attempt's record, which the report prints. The read is stored with the exchange's
played ways, and is filled in whenever a teaching read finds the key's entry without it.

**What it proved.** `lap1d`'s prologue and Ch1 starts, one attempt each (tag `exp1`). Both
were won clean, in 2 and 6 turns. All 7 player attacks matched: in each one, the read for the
outcome that happened equals the experience the battle awarded. That covers five kills
(Seth's 4, 4, 45 and 45, the 45s on the two bosses, and Franz's 34) and two hits (10 each,
Gilliam (0x03) and Franz).

**Cost.** Three short game calls a new exchange; a memo hit costs nothing more. The prologue
played on main (tag `exp1ctl`) and on this branch (tag `exp1b`), back to back, gave the same
acts (`acts_hash` cb9c483f). It took 3,055 frames on main and 3,079 on the branch, and 4.42
and 4.46 CPU seconds. The slowest decision took 414 and 432. After the review's fixes the
prologue and Ch1 played the same acts and frames again (tag `exp1c`), with no `taught_miss`.

**Unit tests** (`test_bot.lua`, `test_sight.lua`, `test_botrun.lua`). `Sight.expOf` sets
each case's two fields and calls the game's count on the battle units; `taughtMiss` reads each
case off a battle and names a wrong read. Of two sure kills, the unit the kill teaches more takes it.
On a target neither kills alone, the plan chips with the unit that learns less, so the other
finishes. Both fail on main's code. Two guards pass on both: a unit that cannot gain levels
adds nothing to its plan's value, and experience never takes a plan over the cap.

**Not covered here.** The count is read on the plain simulation, where nothing procs. So an
Assassin's Silencer kill, which the game doubles (`GetUnitExpMultiplier`), is read at single
value. A staff's experience (`BattleApplyItemExpGains`) is not counted. Neither is the
experience a counter in the enemy phase awards. Whether the term moves the party's levels is
the proof lap's to show: from the prologue, against `lap1d`, on the four measures the plan
comment set.
