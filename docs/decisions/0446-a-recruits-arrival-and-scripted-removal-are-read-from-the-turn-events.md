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
- `sight.lua`, `M.walkScript(mem, script, visit)`: the one walk of an event script's bytes (command
  length from the head halfword, LABEL/GOTO/END, CALL and ENQUEUE_CALL followed). `M.callsScript`
  is now a visit of it, not a second copy. A script CALLed twice is walked twice (the guard is the
  stack of scripts being walked), because slot 2 can differ between the calls.
- `M.scriptEffects(mem, script)`: the units a script loads (`LOAD1-3` arrays, slot 2 set by `SVAL`
  and read through the CALL as `LOAD1(1, -1)`; `LOADSINGLEUNIT`) and removes (`CHANGESTATE` DISA or
  KILL). Encodings are cited in its comment (`eventscript.h`, `eventscr.c`, `bmunit.h`).
- `M.turnScripts(api, call, info, turn, phase)`: the game's per-phase turn-event check, lifted out
  of `nextTurnEvent` so the scan and `nextTurnEvent` share it.
- `s.scriptedUnits()`: for turns 1-30 and each phase, the scripts the game offers (each at the first
  phase it is offered) are walked once, cached for the run: about 90 `SearchAvailableEvent` calls at
  the first plan, none per turn. A blue-phase event's `boardTurn` is its turn; a green or red one's
  is the next, as `arrivals_seen` records.
- `botrun.lua` `pendingRecruits`: an owed unit with no remembered arrival gets the scripted one. An
  arrival actually seen still wins.
- `goals.lua` `M.closings`: a scripted removal closes the recruit after enemy phase
  `boardTurn - turn`, the smaller of that and the AI's escape; a removal already past is none.

**Estimates, labelled.** The walk does not evaluate a script's guards (`CHECK_ALIVE`,
`CHECK_ALLEGIANCE`, flags), so a removal that holds only in some state reads as always; a `REDA`
walks a loaded unit off the tile read. An event a later flag opens is not in the scan (flags are
those of the first plan). A script that loads and removes one unit in the same event (a cutscene
cast) reads as an arrival and a removal at once; only an owed recruit is affected.

**Read off the ROM (vanilla, b640e-cs-s4009, Eirika route).** Ch13: Cormag 0x0E, turn 5, (0,15).
Ch9a (chapter index 10): Amelia arrives turn 5 at (2,23), removed turn 12. Rennac's turn-2 load is in
`ch14b`, the Ephraim route, not read here.
