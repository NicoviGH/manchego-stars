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

**Decision: every copy of a game check that a rider changes follows the game. `Sight.riding`
is the one test of the state bit.**
- **Weapons.** `Sight.weapons` lists no weapons for a rider, so no plan, `legal` read or answer
  has a rider strike with his own weapon. The bot never plays Attack w/Ballista. The answers'
  memo (`ownKey`) keys on whether the unit rides, so a rider's empty list is never served to
  the same unit on foot.
- **Move tiles.** The three readers of a move's end tiles drop the ones the game's own
  `CanMoveActiveUnitTo` (`playerphase.c`) refuses a rider: any tile with a ballista on it except
  the one he set out from. The ridden ballista's trap keeps the tile it was boarded on until the
  rider exits. The three are `Sight.reach`, `Sight.cantoTiles` (setting out from the act's
  tile) and the harness's `marchToward`. All go through `Sight.riderTiles`, which asks the game,
  and asks about an ally's tile with that ally lifted off `gBmMapUnit` (`Sight.liftOff` and
  `Sight.putOn`, now the one writer of that map in `sight.lua`).
- **Other commands.** Every other command the bot plays is asked of the game's own
  `*Usability` with the unit active (`Sight.legal`'s `menuOffers`), so it already saw the rider.

**Proof.**
- **Unit tests** (`test_sight.lua`, the "weapons:", "riderTiles:" and "riding:" checks). With
  the two gates reverted: 4 failures. With the review's wiring reverted (Canto, the memo key,
  `marchToward`, the one bit test): 5 failures. All pass with the fix.
- **Run** on the lap's own start `lap3e-cs-s4006/11` with the fixed bot (tag `rider1`, scout;
  its 8 BOTRUN records are in the vanilla store's `resume-runs.jsonl`). Attempt 3 plays the same
  153 player acts as the crashed one. On turn 14 Innes then waits at (6,22) instead of the
  impossible attack. All 8 attempts end with a real result (6 stuck, 1 lost, then a win on
  attempt 8) and none crashed. Attempts 1 and 2 have the same acts hashes as before the
  fix (`dff1c88a`, `8d8bcc33`).

**Not built: Exit.** A rider with an empty ballista now holds for the rest of the chapter. The
game's Exit returns him to the unit menu, where he could still act (`ExitCommandEffect`, then
`PlayerPhase_CancelAction`, like Trade). Planning Exit, and Attack w/Ballista for a rider with
shots left, is an act the bot does not have yet.
