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
- **The phase takes the expected uses, rounded**, the same way a strike takes its expected
  damage, rounded: the phase is played along its expected way (`s.nextPhase`). A weapon at 0 is
  removed as the game does: the item is written back to its slot (`BattleApplyUnitUpdates`)
  and the bag is packed (`UnitRemoveInvalidItems`). That unit then fights the rest of the phase
  unarmed (`M.wear`).
- Where it applies: our unit's planned attack (its weapon equipped, then less the attack's
  `wear`: `M.armAsPlanned`), and each phase strike, on both weapons: the striker's and the one
  its target counters with (`M.strikeWear`). This covers the judged phase and both of the
  lookahead's phases.
- One use less is `Board.itemAfterUse`, which mirrors `GetItemAfterUse` (bmitem.c, a five-line
  read of the item's attributes). The first cut called the game function once per use: about
  23,000 calls in one Ch19 attempt, and the same play cost 198.5 CPU s against 192.2 on main.

**Why not the worst case.** A worst-case read (the weapon breaks whenever some way breaks it)
would read a 1-use weapon at a 10% hit as gone. Everywhere else the phase plays the likelier
way (an enemy is gone at a kill of 0.5 or more, HP is the rounded mean). A break read on any
chance would make our units unarmed in ways they are unlikely to be.

**Measured (Ch19 from `bag1-heal4-heal1-lap4e-cs-s4006`, `attempts`, dice seed 4006).** Attempt
1 plays the same game on main and here (same `acts_hash`). CPU back to back: 172.3 s on main,
173.0 s here, 24.62 against 24.71 s a player phase. The extra simulations come from battle keys
that now differ by uses: 75,438 against 76,079.

**Not covered by it.** An enemy's weapon worn by the counter it gives our planned attack (the
plan keeps an enemy's HP only). The army reply's kills between the lookahead's phases. A
wall's strike. #642's price still counts every blow as thrown (`attackOf.uses`). That count
could now come from `wear`, but that would change what the price means, so it stays a call for
later.
