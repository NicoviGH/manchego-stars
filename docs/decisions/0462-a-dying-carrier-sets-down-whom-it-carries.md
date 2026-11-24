---
id: 462
title: "A dying carrier sets down whom it carries, in the copy's enemy phase"
date: "2026-11-23"
section: "Combat System"
issues: [739, 743, 510]
---

# A dying carrier sets down whom it carries, in the copy's enemy phase

**Decided (Claude, 2026-11-23, on Nicolas's standing word to build a found fix), #510 step 9.**
It follows ADR 0460 (a blow that may kill splits the phase) and ADR 0461 (an idle mover moves):
the copy's board after a death is the game's.

**The problem (measured, #739 comment of 2026-11-23).** When a unit carrying another died in the
copy's enemy phase, `remove` only lifted the carrier off the map (`M.takeOff`). The carried unit
stayed hidden and carried, so the enemies after the death could not target it. The game sets it
down: bmmind.c `DropRescueOnDeath`, for a unit at 0 HP that is `US_RESCUING`, calls bmunit.c
`UnitGetDeathDropLocation` (the nearest free tile the carried unit can stand on, by a flier's
movement map from the carrier's tile) and `UnitDrop`. Run `i739` (vanilla Ch19 `b640e-cs-s4003`
attempt 1): on turn 3 carrier 5 died and enemy 135 then killed the dropped green 74; on turn 12
carrier 16 died and enemy 160 killed the dropped green 65. The copy had both enemies strike
someone else. The same pattern stands behind #739's green 65, read at 0 in `fix713g`.

**The change (`sight.lua`).**
- `M.deathDropAt` asks the game where the carried unit lands: it calls
  `UnitGetDeathDropLocation` in the sandbox. The search clears gBmMapUnit's cells of the carrier
  and of gActiveUnit (bmunit.c); a game call's writes are not journaled, so both cells are kept
  (`keep16`) and put back, and a unit off the map (a stale gActiveUnit) has no cell. The search
  also fills gBmMapMovement; that is left, as every AI read makes the movement map fresh first
  (the sandbox's journal note; every generator the AI calls sets the working map and costs,
  bmidoten.c). Its two int outputs borrow the scratch bytes, which in the judged phase are the
  AI's proc, and are put back too. The outputs start at the carrier's tile, since the game leaves
  them unset when no tile is free.
- `M.dieOff`, the phase's `remove` (a blow's kill, our counter's, a berserk strike's), sets the
  carried unit down there before the carrier leaves the map. The plan's own `gone` units are only
  taken off: that list holds a recruit talked to (not dead) as well as our kills, and no plan carry
  rides on an enemy.
- The drop itself is one owner, `M.drop` (`UnitDrop`'s writes through the journal), shared with
  `stageCarry`'s plan Drop. `UnitDrop` is not called: its writes to the unit structs would need
  keeping, and the Lua drop already wrote them for the plan's Drop.

**Not changed.** #739's other symptom, enemy 169 striking Franz at a read of 0 after the replan,
is not explained: its board could not be rebuilt on main's bot (the run was a resume of an old
instrument), and a fresh game did not reach it.

**Proof (ADR 0430).** A unit test that fails without the change (`test_sight.lua`:
`deathDropAt` returns the carried unit and the game's tile, starts the outputs at the carrier's
tile, keeps both map cells and puts them back, skips a cell off the map, puts the proc's bytes
back, and asks nothing of a unit that carries no one or a carrier off the map; `M.dieOff` leaves
the carried unit on the drop tile, shown, both rescue words cleared, and the carrier off the map).

Emulator probe `PT_VANILLA=1 PT_LEAKGUARD=1 tools/playtest/run.sh dropprobe` (retail Prologue:
Seth, charId 2, carries Eirika, charId 1, at 1 HP beside two enemies given Power and Skill 30):
PASS on the branch: in the way where enemy 0x82 kills Seth (p 0.60), enemy 0x83 strikes the
dropped Eirika; the control (Seth at full HP, killed at most by the last enemy) has no such
strike; no leak. FAIL on main: no enemy ever strikes her.

Not yet seen in a played game: the green 65 / 74 deaths themselves. #739 names the replay that
would show it.

One replay, `PT_LEAKGUARD=1 PT_FORECAST=1` (run `fx739a`, vanilla Ch19 `b640e-cs-s4003` attempt
1): won on turn 13, no leak. It did not reach a carrier death the copy splits on. Turn 3 played as
in `i739`, and there the copy read no kill for the blow that killed carrier 5 (enemy 134), because
the earlier blows left him at the mean HP (#743's cause (b)). So the drop came only after enemy 135,
too late for green 74. The game diverged before turn 12.
