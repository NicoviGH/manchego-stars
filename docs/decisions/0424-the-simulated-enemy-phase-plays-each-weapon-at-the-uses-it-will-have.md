---
id: 424
title: "The simulated enemy phase plays each weapon at the uses it will have"
date: "2026-11-18"
section: "Combat System"
issues: [644, 510]
---
# The simulated enemy phase plays each weapon at the uses it will have

**Accepted (2026-11-18, #644).** Found by #644: in vanilla Ch19 Myrrh (charId 0x1E) spent the
Divinestone's last use, once on her own attack and once on a counter, and an enemy Ranger
(class 0x1D) then killed her in one shot. Every plan read her at 0% death. The simulated enemy
phase (`sight.lua` `stagePhase`, `strike()`) staged tiles, HP and the equipped weapon, and never
took a use off a weapon. So she kept the stone (+15 Def, +20 Res, a counter) for the whole phase.

**The rule.**
- **What a blow spends is read off the game's own battle, not a model.** `M.played` already
  plays every way an exchange can go (ADR 0377). After each way, `M.worn` reads how many uses
  each side's weapon lost (`weaponBefore` less `weapon`; all of them when `weaponBroke`). So the
  game's rules come with it: `BattleGenerateHitEffects` spends a use on a hit, or on every blow
  of an `IA_MAGIC` / `IA_UNCOUNTERABLE` weapon. A blow the target's death cuts off spends
  nothing. A broken weapon throws no more rounds (`BattleGenerateRoundHits`). An
  `IA_UNBREAKABLE` item spends nothing (`GetItemAfterUse`). An exchange's `wear` is the
  expected uses over its ways, for the actor and for the target (`M.exchangeOf`).
- **Which item the uses come off is the game's too.** `BattleApplyUnitUpdates` writes the
  battle's weapon back to `items[weaponSlotIndex]` only when `canCounter` (`M.wearSlotOf`). A
  ballista's strike (`SetBattleUnitWeaponBallista`) leaves `canCounter` FALSE and a stale slot,
  so it wears no item of its rider's bag; its uses come off the ballista's trap
  (`BattleApplyBallistaUpdates`, `M.wearBallista`). An attack the game armed itself (no slot
  asked) may use slot 2 behind two Vulneraries; the uses come off that item, wherever the equip
  moves it (`M.armAsPlanned`, `M.afterEquip`).
- **The phase takes the expected uses as a running total, rounded** (PR #645 review): each
  strike adds its expected wear to a ledger per unit and slot, and the item has lost the
  rounded total (`M.tally`). Three strikes at 0.45 on a 1-use stone spend it (1.35; it is
  gone 83% of the time), where rounding each alone never would. The plan's own attacks seed
  the ledger. Each way of a split phase keeps the ledger its strikes left, and the lookahead's
  second phase starts from the first one's and the army reply's. A weapon at 0 is removed as
  the game does: the item is written back to its slot and the bag packed
  (`UnitRemoveInvalidItems`, `M.wear`); that unit fights the rest of the phase unarmed.
- **A plan's attack spends the uses the HP the plan leaves allows.** Each way's blows are read
  off the game's hit array by the HP the target had lost before them (`M.wornBy`, which must
  count what `M.worn` counted, or it raises). The planner reads that at the target's HP in the
  plan (`Planner.wearAt`): a second attacker whose first blow kills a target the first attacker
  left on 4 HP spends 1 use, not the 2 it spends at the target's own HP.
- Where it applies: our unit's planned attack (`M.armAsPlanned`), the counter it draws off the
  enemy's weapon (`plan.redWear`: an enemy whose counter spent its last javelin strikes without
  it), each phase strike on both weapons (`M.strikeWear`), a planned wall strike (every blow on
  a wall lands: `ComputeBattleObstacleStats`; `sight.strikeWall`'s `M.worn`), and the army
  reply's kills between the lookahead's phases. This covers the judged phase and both of the
  lookahead's phases.
- One use less is `Board.itemAfterUse`, which mirrors `GetItemAfterUse` (bmitem.c). The first
  cut called the game function once per use: about 23,000 calls in one Ch19 attempt, and the
  same play cost 198.5 CPU s against 192.2 on main. `test_playtest_harness.py`
  `TestItemAfterUse` compiles the game's function on the host and runs it and the copy over
  every item of `data_items.c`; it found them apart on item id 0 (the copy now reads that row's
  empty attributes as the game does).

**Why not the worst case.** A worst-case read (the weapon breaks whenever some way breaks it)
would read a 1-use weapon at a 10% hit as gone. Everywhere else the phase plays the likelier
way (an enemy is gone at a kill of 0.5 or more, HP is the rounded mean). A break read on any
chance would make our units unarmed in ways they are unlikely to be.

**Measured (Ch19 from `bag1-heal4-heal1-lap4e-cs-s4006`, `attempts`, dice seed 4006, 3
attempts an arm).** Main: lost, lost, lost; 23 deaths read at 0%, 7 of them player units.
The first cut: lost, won, lost; 24 / 8. With the review's fixes: lost, lost, lost; 23 / 6.
Attempts 1 and 2 play main's games (same `acts_hash`); attempt 3 differs. Myrrh died in no arm,
and no player death read at 0% was a unit that had lost a weapon. CPU back to back on attempt 1
(the same play): 173.9 s on main, 174.6 s here, 24.85 against 24.95 s a player phase (+0.4%);
`BattleGenerateSimulation` 75,438 against 76,139 (battle keys now differ by uses).

**Not covered by it.** Nothing the phase plays strikes without its wear. `s.strike`, the one
strike a fog or exposure read asks, plays no phase after it, so no use it spends is read again.
A planned ballista shot of ours does not exist to stage: the bot has no act that mounts a
ballista (no Ride act in `bot.lua` or `harness.lua`; a unit on foot attacks from its bag), so
only enemies ride one, and their shots wear the trap.
