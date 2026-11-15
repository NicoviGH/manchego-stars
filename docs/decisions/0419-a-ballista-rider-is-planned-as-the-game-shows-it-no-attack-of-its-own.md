---
id: 419
title: "A ballista's rider is planned as the game shows it: no Attack of its own, no other ballista's tile"
date: "2026-11-15"
section: "Combat System"
issues: [510]
---
# A ballista's rider is planned as the game shows it: no Attack of its own, no other ballista's tile

The lap on Eirika's route (tag `lap3e`, campaign `cs-s4006`) crashed at vanilla Ch10 on her
route (chapter id 11), attempt 3, turn 14: "the attack did not play out". The bot planned Innes
(charId 11) to shoot from (7,23) with his Silver Bow; the game's unit menu there held Attack
w/Ballista (greyed), Exit, Item and Wait, and no Attack.

**Cause (read off the run's own log and the decomp).** Innes was riding a ballista: his unit
state read `0x800` (`US_IN_BALLISTA`) and the menu offered Exit. As a green unit he had fired its
last shot on turn 10. The trace's `broke: true` there is the ballista emptying, since the Silver
Bow is still in his bag. He joined on turn 11 still riding. A rider moves with the ballista,
and `AttackCommandUsability` (`bmmenu.c`) hides Attack from it. `AttackBallistaCommandUsability`
greys its own command when the ballista has no uses left. `Sight.weapons` copied that function's
weapon loop without its `US_IN_BALLISTA` gate, so the bot thought the rider could use his bow.
The earlier lead, that his bow had broken, is refuted.

**Decision: the two places that copy a game check for the rider follow the game.**
- `Sight.weapons` lists no weapons for a rider, so no plan, `legal` read or answer has a rider
  strike with his own weapon. The bot never plays Attack w/Ballista.
- `Sight.reach` drops the tiles the game's own `CanMoveActiveUnitTo` (`playerphase.c`) refuses
  a rider: a tile with any ballista on it except the one he set out from. The ridden ballista's
  trap keeps the tile it was boarded on until the rider exits. `Sight.riderTiles` asks the game,
  and asks about an ally's tile with that ally lifted off `gBmMapUnit`.
- Every other command the bot plays is asked of the game's own `*Usability` with the unit
  active (`Sight.legal`'s `menuOffers`), so it already saw the rider.

**Proof.** Unit tests (`test_sight.lua`, "weapons: a ballista's rider…", "riderTiles: …") fail
on the reverted gates (4 failures) and pass with them. Run: the lap's own start
`lap3e-cs-s4006/11` on the fixed bot (tag `rider1`, scout). Attempt 3 plays the same 153 player
acts as the crashed one, then on turn 14 Innes waits at (6,22) instead of the impossible
attack. All 8 attempts end with a real result (5 stuck, 1 lost, 1 more stuck, then a win on
attempt 8) and none crashed. Attempts 1 and 2 have the same acts hashes as before the fix.

**Not built: Exit.** A rider with an empty ballista now holds for the rest of the chapter. The
game's Exit returns him to the unit menu, where he could still act (`ExitCommandEffect`, then
`PlayerPhase_CancelAction`, like Trade). Planning Exit, and Attack w/Ballista for a rider with
shots left, is an act the bot does not have yet.
