---
id: 57
title: "Lord floor, runtime mechanism (#45 3b/3c): a build-baked table applied once at the first player phase."
date: "2026-06-19"
section: "Combat System"
issues: [45]
---

# Lord floor, runtime mechanism (#45 3b/3c): a build-baked table applied once at the first player phase.

The build emits `gLordFloorDeltas[]` (`events_udefs.c`, parallel to `gLordSelectCandidates[]`): one
`{+maxHP, +Def, +Res}` row per candidate = `difficulty.lord_floor_delta` @target 3.5 vs Ch1 enemies (Ch1 →
shamans +7HP/+4Def, the armor tanks 0). The engine applies the **chosen** lead's row once — `LordFloor_ApplyOnce`
(`eventinfo.c`, beside `LordSelect_GetPid`), called from **`EndPrepScreen`** (`prep_sallycursor.c`), right after
`ShrinkPlayerUnits` finalizes deployment on the prep "Fight!". **Hook-point lesson (the #45 3c open question, found by
playtest):** every player-*phase-start* seam — `BmMain_StartPhase`, and the cursor-reset
`ProcFun_ResetCursorPosition` the crash guards use — fires BEFORE prep deployment finalizes on turn 1, so the chosen
lead isn't findable yet (`GetUnitFromCharId` → NULL) and the floor lands a phase late (ch01: +7 at turn 2, not turn
1). The deployment-finalization seam in `EndPrepScreen` is the first point the lead is deployed + valid; lord-select is
always a prep chapter, so it suffices. Apply-once is a permanent flag (`0xFA`, just above the `0xF0` candidate block)
**spent only on a real application** — a pick flag is set AND the lead is found — so the prologue (no pick) skips
cleanly; the buff then bakes into the saved unit and fades as it levels. Presence-guarded in
`check.py check_engine_guards_present`; playtest-verified by `tools/playtest/run.sh lordfloor` (marty +7HP/+4Def at
ch01 turn 1, stable across phases — no double-apply).
_Decided: 2026-06-19 (CLAUDE; decomp-traced + playtest-corrected — resolves #45 3c open hook-point question)_
