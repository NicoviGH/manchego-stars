---
id: 448
title: "The judged enemy phase plays an AREA event's AI changes"
date: "2026-11-22"
section: "Combat System"
issues: [712, 699, 510]
---

# The judged enemy phase plays an AREA event's AI changes

**Decided (#712), #510 step 9.** A read of the game's own rules; no weight. Vanilla Ch16's Sage
(0x90) is `gAiScript_DoNothing` until a player unit ends its action inside one of two rectangles
(x 2-21 / y 0-11, x 1-13 / y 18-22); then it attacks. The judged enemy phase read the AI as it stood,
so a plan ending a unit there read 0 risk and the Sage killed Eirika (`b640e-cs-s4002` attempt 3,
turn 4, and the Sage kills of s4007 and s4009).

**Read in the decomp.**
- The Misc list runs after every unit's wait: `RunWaitEvents` (`eventinfo.c:1628-1659`) sets
  `info.xPos/yPos` and calls `SearchAvailableEvent` over `miscBasedEvents` (`ChapterEventGroup`
  +0x0C), then `StartEventFromInfo` for each entry found. `StartEventFromInfo` does `SetFlag(flag)`
  first (`eventinfo.c:71-77`), so a flag shared by two entries (Ch16's `EVFLAG_TMP(11)`, both AREA
  entries, `ch16a-eventinfo.h:27-28`) fires once.
- `EvCheck0B_AREA` (`eventinfo.c:1020`) tests `gActiveUnit->xPos/yPos` against the rectangle, not
  `info.xPos`. The game's `SearchAvailableEvent` skips an entry whose flag is set.
- The script (`ch16a-eventscript.h:563-569`) sets slot 1 to `0x10000`, `CHAI(0x8f)`, slot 1 to
  `0x10303`, `CHAI(0x90)`. `Event39_ChangeAiScript` (`eventscr.c:3604`): `ai1` is slot 1's low
  byte, `ai2` the next; `CHAI pid` (a negative pid is slot 2) calls `ChangeAiForCharacter`
  (`eventscr3.c:61`): every green and red unit of that character, through `ChangeUnitAi`
  (`eventscr3.c:33`: not hidden or dead; an `ai1` of `AI_A_INVALID` or `ai2` of `AI_B_INVALID`
  leaves that script; the counters restart; `ai2 == AI_B_0C` sets `AI_UNIT_FLAG_3`).

**What changed.**
- `Sight.scriptAiChanges(mem, script)`: the CHAIs of a script, over the one script walker
  (`walkScript`, ADR 0446), slot 1 and slot 2 tracked through CALLs; it also counts the `CHAI_AT`s
  it does not read (`positional`) and says when the budget cut the walk (`truncated`).
- `Sight.areaWake(...)`, called by `stagePhase` (the one owner of the judged phase's staging, so
  `enemyPhase` and the lookahead's first phase share it) with the plan's **waits**
  (`plan.waits`, `Planner.waitsIn`: each unit the plan acts, with its act's index): in act order
  (the game runs the Misc events after each wait in turn, so of two entries sharing a flag the first
  unit to wait fires its script), the unit is stood on its end tile for the ask, the game is asked
  what the Misc list offers (`availableList`, now the ordered owner of `availableScripts`), a flag
  taken by an earlier wait is not offered again, and each script's CHAIs are written through
  `M.changeUnitAi` (api writes: the journal restores them, and the decisions' own `keepAi` unwinds
  first, so no `keep16` of ours).
- A unit whose counter kills it still waits (`RunPotentialWaitEvents` after `ApplyUnitAction`,
  `playerphase.c:98-99`, `cp_perform.c:85-86`; `UnitKill` keeps its tile, `bmunit.c:958`): the
  waits of a way include the dead actors, which are in no board list, so their struct is stood on the
  end tile for the ask alone and put back. The first version woke nothing in such a way (it
  under-woke).
- The unread parts are counted, never silent: the judged phase's result and the lookahead's first
  phase's (`nextPhase`, the same staging, summed at both call sites) carry `.areaPositional` and
  `.areaTruncated`, the planner's cost line `area_positional` / `area_truncated` next to `averaged` and
  `unsplit`, and the bot's record `plans.area_positional` / `plans.area_truncated`.
- Keys: `M.phaseKey` (the kept phase start) now includes each unit's `ai1` and `ai2`: a start kept
  on a board where the Sage slept would write its `aiFlags` over a woken one (`AI_UNIT_FLAG_3`).
  `closingsKey` and the danger grids are not read inside the judged phase (the danger map is the
  game's own `AiInitDangerMap` every decision, and reads no AI). The per-board tile memo
  (`seen.area`) is dropped with the board by `refresh()`.

**Not read, labelled.** `CHAI_AT` (queue-driven, `EventScr_ChangeAIinQueue`,
`events_script_utils.c:523`) is counted, not played: vanilla E_10's and E_14's AREA scripts use it
(`ch10a-eventscript.h:368`, `ch14a-eventscript.h:411`), follow-up #727. Guards in a script are not
evaluated (a walk, as `scriptEffects`); the player's units pass the faction guard. `RunWaitEvents`'
other work is not modelled: it sets or clears `EVFLAG_DEFEAT_ALL` and runs nothing when flag 0x65 is
set or no blue unit is left. The lookahead's reply turn ends units elsewhere and wakes nothing.
Units in the plan with no act do not trigger: the game runs the event at their wait only.

**Tested how.** `test_sight.lua` "areaWake": a fake game answers `SearchAvailableEvent` as
`EvCheck0B_AREA` does; a unit ending in the area switches the Sage 6/7 -> 3/3 and the 0x8f unit to
0/0; the control (outside, or no wait) leaves them; a shared flag fires once; two entries of one flag
and different scripts fire for the first unit in act order, not roster order; a dead actor's end
tile wakes and its struct is put back; the positional count; a taken flag, a dead unit, the tile memo
and `phaseKey`. `test_bot.lua`: the judged phase is told the plan's waits with their act index, and
`Planner.waitsIn` includes a counter-killed actor and no unit without an act. Each fails
individually with its piece removed (areaWake a no-op, the call out of `stagePhase`, the act-order
sort, the end-tile stand).
