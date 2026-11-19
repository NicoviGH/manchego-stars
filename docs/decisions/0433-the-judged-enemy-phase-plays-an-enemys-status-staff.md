---
id: 433
title: "The judged enemy phase plays an enemy's status staff"
date: "2026-11-19"
section: "Combat System"
issues: [674, 660, 510]
---
# The judged enemy phase plays an enemy's status staff

**Decided 2026-11-19 (#674).** It completes ADR 0432 (the berserk phase): the game's own
decision, played as the game plays it. No new rule or weight.

**The problem.** The judged enemy phase kept an enemy's decision only when it was an attack
(`AI_ACTION_COMBAT`). A Bishop's Berserk or Sleep staff was dropped, so the unit it would
berserk was never berserked for the lookahead's second phase, and a unit it would put to sleep
still countered and still moved in the army's reply. The berserk phase (ADR 0432) saw only units
berserked before the plan. Vanilla Ch14 (`scout-ch14/1001`): the Bishop (class 69) berserked Colm
(charId 9) and Garcia (charId 0x0A) during enemy phases.

**What the game does (decomp).**
- `cp_staff.c` `AiTryDoStaff` runs each staff's AI routine. `AiStaffSleepBerserk` and
  `AiStaffSilence` pick a target and call `AiSetDecision(x, y, AI_ACTION_STAFF, target, slot)`.
  The AI scripts try a staff before an attack (`cp_script.c`, `cp_0803E2F4.c`).
- `bmusemind.c` `ExecStatusStaff`: one roll, `Roll1RN(GetOffensiveStaffAccuracy(actor,
  target))`. A hit sets `statusOut` by the item: Berserk (0x53) BERSERK, Sleep (0x52) SLEEP,
  Silence (0x51) SILENCED.
- `bmbattle.c` `BattleApplyUnitUpdates` writes it through `SetUnitStatus`: five turns.
- `bmunit.c` `TickActiveFactionTurn`: each of the unit's phase starts ticks a duration that is
  not 0 and clears the status at 0.

**The rule (`tools/playtest/sight.lua`, `board.lua`).**
1. **The act.** `aiDecide` returns a status staff's act as a third value (`Sight.staffAct`: the
   target, the status `Board.STATUS_STAVES` names for the slot's item, the tile). A heal staff
   sets no status and is still not played.
2. **Its hit.** `stagePhase`'s `cast` stands the caster on its tile and reads
   `GetOffensiveStaffAccuracy` there (it reads the distance). `land()` writes the status for
   five turns (`Sight.setStatus`).
3. **The judged phase.** In `playPhase` the act is a way of its own: `phaseWays` splits on the
   hit as it splits on a counter kill, at the same floor, and one left unsplit lands when the
   hit is even odds or better (it is counted in `unsplit`). The staff strikes no one, so no
   strike is added.
4. **The lookahead.** `nextPhase`'s first phase plays its expected way: the status lands when
   the hit is even odds or better. The second phase's berserk phase then lists the unit
   (`Sight.berserkers`), and the army's reply between the phases leaves a unit asleep or
   berserked where it stands. Both read the status after one more player-phase tick
   (`Board.statusAfter`), as the planner's own `held` does.
5. **What follows from the status.** Nothing else is written. The game's own reads carry it: a
   sleeping unit gives no counter in the simulation (`bmbattle.c`: its weapon is cleared and
   `canCounter` false), a silenced one casts no tome (`bmitem.c` `CanUnitUseWeapon`), and a
   berserked one moves in the berserk phase.

**Proof (2026-11-19).**
- Unit tests, each failing on main's code: `test_sight.lua`'s `statusAfter`, `staffAct`,
  `setStatus`, `phaseWays`' staff split and the source checks on both phases and the reply.
- **No replay of the losing game.** As for ADR 0432, its record is of the #655 branch's
  instrument and `replay` refuses it.
- **The probe in the emulator (`PT_VANILLA=1 tools/playtest/run.sh staffprobe`).** On the
  retail Prologue the enemy nearest Eirika (charId 1) is handed a Berserk staff and the rank to
  use it, and Eirika is stood beside it. Its Power at her Resistance + 4: `sight.enemyPhase`
  splits 0.570 / 0.430, the hit's way at the chance the decomp's formula gives from the tile the
  AI casts from (0.43, four tiles off), and the caster strikes in no way. Control, the staff
  taken away: it strikes, and no way is at the hit's chance. At Power 30 (a sure hit),
  `sight.nextPhase`: Eirika strikes in the second phase's berserk phase and the army's reply
  leaves her be; control: no berserk strike of hers. On main's `sight.lua` and `board.lua`:
  `FAIL -- hitWay=false/false struck=false/true berserks=0/0 replied=true` (one way, and the
  reply moves her).
