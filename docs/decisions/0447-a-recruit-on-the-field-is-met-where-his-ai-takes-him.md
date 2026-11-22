---
id: 447
title: "A recruit on the field is met where his AI takes him"
date: "2026-11-22"
section: "Combat System"
issues: [724, 699, 510]
---

# A recruit on the field is met where his AI takes him

**Decided (#724), #510 step 9.** A read of the game's own AI; no weight. Vanilla Ch13's Cormag
(0x0E, a Wyvern Rider) lands on turn 5 at (2,13), in impassable peaks (rows 12-15, x 0-5): no foot
talker can stand beside him, so `Goals.chance` read his goal as 0 and the boss kill forfeited
nothing (the PR #725 replay, turn 5: won with him unrecruited).

**Read before building (instrumented replay, `b640e-cs-s4009` Ch13 attempt 1).**
- `sight.closings` replays the AI with our units hidden (so a looter beside one does not attack it
  every phase and never loot, ADR 0399's note). The replayed `paths[138]` was (2,13) in all 8
  phases: with no unit to see he stays put. Confirmed.
- The game's own AI, our units visible, moves him out: in a lap game (`m699c13` s4007 a1) he was at
  (2,13) on turn 5 and (2,6) on turn 6, then (5,2), (10,1). Confirmed.

**What changed.** `sight.closings` takes a second look at a watched unit whose replayed path never
left its start tile (`M.secondLook`: `M.stayedPut`, then the replay, then `M.takeSecondLook`, the one
wiring, tested with a fake replay). The first look (our units hidden, the looters, the waves' reach)
now runs in a sandbox of its own, rolled back when it returns, and the second look in another: it
starts from the board as it stood (AI words, tiles, terrain a looter sacked, fog bits) with our units
visible, and plays only the stayed-put units, tile only (`aiDecide`'s `tileOnly` skips the battle
simulation a decision to attack would run, since only the tile is read). The looters' loop and the
second look share one local `replay`; the hide has one owner, `M.hideUnit`. `M.takeSecondLook` keeps
the second path only where the unit left its tile, so a unit the AI does not move stays the stationary
path and its chance stays 0: an unreachable recruit that never moves holds no win; one that escapes in
the second look has its path cut to the phases before the escape (empty when it goes in the first).
`closingsKey` now keys each of our units by id, tile, HP and what it carries when a unit is watched
(only then can the second look run, and it reads them as targets); with none, the tiles alone, as
before. `Goals.chance` already prices a recruit's `goal.path` (ADR 0436's `meet`), so
nothing else changed: no `meetingTile` for an on-field recruit.

**Tested how.** `M.secondLook`, `takeSecondLook`, `stayedPut` and `hideUnit` are tested with a fake
replay (each case fails with its wiring removed: mutated and run). The `closings` call site itself is
source-pinned (it calls `M.secondLook`, hides only through `M.hideUnit`), not fake-replay tested: the
sandboxed game calls cannot run in the unit tests, so the Ch13 replay is its proof. The rollback is a
behaviour test of the sandbox primitive (a `keep16`'d word a game call wrote in the first look is
back for the second) with its control. A `PT_LEAKGUARD=1` replay of the same game logged no leak
(no `leaks` key in the record; the guard's env reaching the emulator is assumed, not shown).

**Estimates, labelled.** Our units are taken to stand still for all 8 phases (they will move). Only a
recruit that stayed put in the hidden look is read again: one that moved there keeps the path the
hidden look gave it.

**Result (Ch13 s4009 a1, same replay).** Cormag's goal is feasible on turns 5-10 and holds the win:
the chapter is won on turn 11 (PR #725: turn 5), 1 death (Marisa, 0x16, killed by Cormag on an enemy
phase), and he is still **not recruited**: he flew from (2,13) to (2,6) on turn 6, then (5,2) and
(10,1), and Eirika, his only talker, was 1.2-2.6 turns away on every plan, never beside him.
Pricing him is what this changes; meeting a moving flier is the march's problem, untouched here.

**Cost.** On identical boards (the branch and PR #725 agree on turns 1-4 within 1.5%, so turn 5's first
board is the same) the second look takes 22.7-27 ms of CPU per uncached board on turn 5 and 25-38 ms on
turns 6-10 (14 boards, about 450 ms over the game). Turn 5's first plan took 5.0 s on the branch and
6.6 s on PR #725: the second look is about 0.5% of it.
