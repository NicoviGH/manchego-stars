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
left its start tile (`M.stayedPut`): our units' states are put back as they stood, the unit is stood
on its start tile, and the same enemy-phase replay (one local `replay`, shared with the looters')
plays it again, the game's AI deciding where it goes. `M.takeSecondLook` keeps that path only where
the unit left its tile, so a unit the AI does not move stays the stationary path and its chance stays
0: an unreachable recruit that never moves holds no win. Every other path (a unit that moved the
first time, an escape) is as it was. `Goals.chance` already prices a recruit's `goal.path` (ADR
0436's `meet`), so nothing else changed: no `meetingTile` for an on-field recruit.

**Result (Ch13 s4009 a1, same replay).** The replay path now reads (2,6) in phase 1, as the game
played it. Cormag's goal is feasible on turns 5-10 and holds the win: the chapter is won on turn 11
(PR #725: turn 5), 1 death (Cormag killed a unit on an enemy phase), and he is still **not recruited**:
he flew on and Eirika, his only talker, was 1.2-2.6 turns away on every plan, never beside him.
Pricing him is what this changes; meeting a moving flier is the march's problem, untouched here.

**Cost.** `closings` over that replay: 640 ms CPU in 1157 reads (mean 0.55 ms, max 47 ms) against
55 ms in 597 reads (mean 0.09 ms, max 6.6 ms) on the PR #725 base: not the same game (11 turns
against 5), and the second look runs only for a watched unit that stood still, once per board.
