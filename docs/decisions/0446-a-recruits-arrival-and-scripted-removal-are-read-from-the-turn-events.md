---
id: 446
title: "A recruit's arrival and scripted removal are read from the turn events"
date: "2026-11-22"
section: "Combat System"
issues: [724, 699, 510]
---

# A recruit's arrival and scripted removal are read from the turn events

**Decided (#724), #510 step 9.** A read of what the game's own scripts do; no weight, no change to
how a plan is scored. Before this the bot learned a recruit loaded by a turn event only from an
earlier attempt that saw him arrive (ADR 0436), and never learned that a script removes one: vanilla
Ch13's Cormag (0x0E) is loaded by E_13's turn-5 event with no goal on attempt 1, and Amelia's goal
still read 0.8-0.97 on turn 11 although `ch9a`'s turn-12 event removes her with `DISA`.

**What changed.**
- `sight.lua`, `M.walkScript(mem, script, visit, opts)`: the one walk of an event script's bytes
  (command length from the head halfword, LABEL/GOTO/END, CALL and ENQUEUE_CALL followed).
  `M.callsScript` is a visit of it with `memo` (each script walked once: it holds no state between
  CALLs, and a diamond of CALLs stays linear; a probe of 21 scripts each CALLing the next twice was
  6,291,453 visits without it). `M.scriptEffects` walks a script CALLed twice twice, because slot 2
  can differ between the calls, so its total is bounded by a `budget` (`M.EV_WALK_BUDGET` = 8 x
  `EV_SCRIPT_LIMIT` commands).
- `M.scriptEffects(mem, script)`: the units a script loads (`LOAD1-3` arrays, slot 2 set by `SVAL`
  and read through the CALL as `LOAD1(1, -1)`; `LOADSINGLEUNIT`) and removes (`CHANGESTATE` DISA or
  KILL; `DISA_IF` waits for a death fade and is not one). A unit the same script loads and removes
  (a cutscene cast) is no removal. Encodings are cited in its comment (`eventscript.h`,
  `eventscr.c`, `bmunit.h`).
- `M.turnScripts(api, call, info, turn, phase)`: the game's per-phase turn-event check, lifted out
  of `nextTurnEvent` so the scan and `nextTurnEvent` share it.
- `s.scriptedUnits()`: for turns 1-`M.SCRIPT_HORIZON` (30) and each phase, the scripts the game
  offers (each at the first phase it is offered) are walked once, folded by the pure
  `M.foldScripted`: a removal at or before the unit's earliest arrival is dropped. Cached for the
  run only when read with no sandbox open (a plan's sandbox may have set a defeat flag); botrun
  reads it once, outside any plan, when a recruit is owed (`owed` empty: never). Timed on vanilla
  Ch13: 10.4 ms of CPU once; `freeTalks` (the callsScript change) 0.004 ms main, 0.005 ms branch.
  A blue-phase event's `boardTurn` is its turn; a green or red one's is the next, as
  `arrivals_seen` records.
- `botrun.lua` `pendingRecruits`: an owed unit with no remembered arrival gets the scripted one. An
  arrival actually seen still wins.
- `goals.lua` `M.scriptedCloses`, folded in by `Goals.list` (not `M.closings`, which `openTiles`
  calls with no board): a scripted removal closes the recruit after enemy phase `boardTurn -
  turn`, the smaller of that and the AI's escape; its path is cut to the deadline less one (the
  closings contract); a removal already past is none. No recruit watched: no scan.

**Horizon.** An event names its turn in a byte (`M.LAST_EVENT_TURN` = 0xFF). The scan stops at turn
30, because each turn costs three game calls and the latest start turn any vanilla turn event names
is 19 (grep of `src/events/*eventinfo.h`, `TurnEvent*`). A later event is not read.

**Estimates, labelled.** The walk does not evaluate a script's guards (`CHECK_ALIVE`,
`CHECK_ALLEGIANCE`, flags), so a removal that holds only in some state reads as always; a `REDA`
walks a loaded unit off the tile read; `LOAD_SETCOUNT` and `LOAD_SETCHANCE`
(`eventscript.h:451-453`) are not read, so an array loads whole. An event a later flag opens is not
in the scan (flags are those of its first read). A unit loaded in one event and removed in a later
one is kept as a removal only after its arrival (Amelia: loaded turn 5, removed turn 12).

**Read off the ROM (vanilla, b640e-cs-s4009, Eirika route).** Ch13: Cormag 0x0E, turn 5, (0,15).
Ch9a (chapter index 10): Amelia arrives turn 5 at (2,23), removed turn 12. Rennac's turn-2 load is in
`ch14b`, the Ephraim route, not read here. Index 14 has a turn-2 cast, Lyon (0x40), Caellach
(0x53) and Ismaire (0xCB), loaded and removed together; none is an owed recruit, and the fold drops
those removals. Chapter indices 10-12, 14 and 15 were read: no owed recruit sits in such a cast.
