---
id: 414
title: "The plan counts the experience the game would award: its attacks, its counters, its heals"
date: "2026-11-14"
section: "Combat System"
issues: [510]
---

# The plan counts the experience the game would award: its attacks, its counters, its heals

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
exchange's other played results (`Sight.known`), under the same battle key. `exchange`'s
`teaches` names our unit's side: the actor for our attack, the target for an enemy's strike on
a player unit (decision 4).

**Decision 3: the plan picks which of the three applies, at the HP it leaves the target.**
`taught(x, ways, hp, unitHp, struck)` walks the exchange's ways (`f.joint`). A way whose
counter kills our unit teaches nothing. A way that deals at least the HP the plan leaves the target is a kill.
Any other damage is a hit; no damage is `none`. So when an earlier blow of the plan chips the
target, the kill belongs to the unit that finishes it, and the plan can choose who that is.

**Decision 4: a counter in the judged enemy phase scores what it teaches.** BattleApplyExpGains
awards both sides, so a unit struck in the enemy phase learns from its counter: 1 when its
blows deal nothing (or it cannot answer), more when they wound, the kill's count when they kill.
An enemy's strike on a player unit reads that unit's count (`Sight.expOf` with the side
`"target"`: the same two fields, on the swapped battle units) and keeps it on the strike
(`taught`, beside its `joint`). The judged phase adds `W.exp` times, over every way the phase
can go (its chance), each strike's count over its exchange's ways (`taught` with `struck`: our
blows are the counter, our loss the strike's damage), at the HPs the phase had left when the
strike came (`Sight.strikeAt`), the target's level beside it. Its phase's ways already play a
counter that kills the striker both ways. So standing where a counter will kill trains the
unit that stands there, within the cap. Only the judged phase reads the count
(`s.enemyPhase`); the lookahead's second phase and a single strike's forecast do not, as
nothing scores them. A memo entry keeps the side it counted, and a read of that key for the
other side is an error.

**Decision 5: a heal scores what its staff teaches.** `GetBattleUnitStaffExp`
(`bmbattle.c`): 10 plus the staff's cost per use over 20, halved once promoted, 0 for a unit
that cannot gain levels. `Sight.staffExp` reads it on the battle unit the Staff command sets
up (`BattleInitItemEffect`, which also clears the blows, so the count's 1 for a miss never
applies to a heal). `s.staves` and `s.heals` carry it, the heal acts carry it, and `score()`
adds `W.exp` times it to a heal that restores anything. Both heal proposals carry it through
one helper (`healWith`, `bot.lua`). A dance (20 a use) is not counted: the bot proposes no
Dance (neither `bot.lua` nor `planner.lua` has one).

**The record.** Each player-phase attack in the trace gains `taught`: the three numbers the
plan read. Every run checks them against the battle's own `exp` (its actor's):
`Botrun.taughtMiss` takes the case from the battle (actor dead, target dead, a blow of the
actor's that dealt damage, else none), and a read that differs is an anomaly, `taught_miss`,
on the attempt's record, which the report prints with the unit, case, read and award. A
counter is checked the same way, side `"target"`, against the committed plan's strike by that
enemy on that unit, when the unit fights at the level the read was made at (a level-up since
changes the count honestly). A heal is checked against the Staff command's award
(`Board.itemUser`: gBattleActor's `expGain`). The record's `taught_checked` counts the checks
made by kind, and `taught_unchecked` the battles no read could be checked against: a counter
in a rarer way than the plan's likeliest, on another target or at another level, and a heal
whose battle unit is another unit's. The report's attempt line prints both, so a pass with
few checks shows as one.

**What it proved.** `lap1d`'s prologue and Ch1 starts, one attempt each (tag `exp1`). Both
were won clean, in 2 and 6 turns. All 7 player attacks matched: in each one, the read for the
outcome that happened equals the experience the battle awarded. That covers five kills
(Seth's 4, 4, 45 and 45, the 45s on the two bosses, and Franz's 34) and two hits (10 each,
Gilliam (0x03) and Franz).

Counters and heals (tag `exp2`, `lap1d`'s prologue to Ch4, one attempt each): all five won
clean, no `taught_miss`. Replayed from Ch2 with the check counter (tag `exp2b`): Ch2 checked 5
attacks and 9 counters, Ch3 9 attacks, 11 counters and 4 heals, every one equal to the game's
award. The 9 and 11 counters are every enemy battle on a player unit in those two chapters.

**Cost.** Three short game calls a new exchange; a memo hit costs nothing more. The prologue
played on main (tag `exp1ctl`) and on this branch (tag `exp1b`), back to back, gave the same
acts (`acts_hash` cb9c483f). It took 3,055 frames on main and 3,079 on the branch, and 4.42
and 4.46 CPU seconds. The slowest decision took 414 and 432. After the review's fixes the
prologue and Ch1 played the same acts and frames again (tag `exp1c`), with no `taught_miss`.
The counter and staff reads, Ch1 back to back without and with them (tags `exp2ctl`, `exp2c`,
same `acts_hash` 4c0fbb8a): 13,889 and 14,183 frames, 4.23 and 4.20 CPU seconds.

**Unit tests** (`test_bot.lua`, `test_sight.lua`, `test_botrun.lua`). `Sight.expOf` sets
each case's two fields and calls the game's count on the battle units; `taughtMiss` reads each
case off a battle and names a wrong read. Of two sure kills, the unit the kill teaches more takes it.
On a target neither kills alone, the plan chips with the unit that learns less, so the other
finishes. A unit stands where its counter learns; of two healers, the one the staff teaches
heals. Each of these fails on the code without its term. `Sight.staffExp` and the struck side
of `Sight.expOf` have their own tests, and a run test shows a wrong heal or counter read on
the record, and a counter at another level unchecked. Two guards pass on both: a unit that cannot gain levels
adds nothing to its plan's value, and experience never takes a plan over the cap.

**Not covered here.** The count is read on the plain simulation, where nothing procs, so an
Assassin's Silencer kill, which the game doubles (`GetUnitExpMultiplier`), is read at single
value. The run's check catches it when the Silencer kill is a checked battle: the battle
gives twice the read, and the attempt records a `taught_miss`. It is made exact if a run shows
one. A counter's count is read at the HP the
phase had left when its strike came, the phase's expected HP, as the strike itself is played.
Whether the terms move the party's levels is the proof lap's to show: from the prologue,
against `lap1d`, on the four measures the plan comment set.
