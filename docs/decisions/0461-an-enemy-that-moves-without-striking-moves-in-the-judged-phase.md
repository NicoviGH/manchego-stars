---
id: 461
title: "An enemy that moves without striking moves in the judged phase"
date: "2026-11-23"
section: "Combat System"
issues: [743, 510]
---

# An enemy that moves without striking moves in the judged phase

**Decided (Claude, 2026-11-23, on Nicolas's standing word to build a found fix: "my approval is
just going to be a bottle neck"), #510 step 9.** It completes the copy's enemy phase that ADR
0460 split on a death.

**The problem (measured, #743 comment 7119556199).** In the copy's judged first phase, an enemy
whose decision was a move with no strike, staff or theft went to `none = function() return nil
end`. It stayed on its old tile, so the enemies after it decided on a board the game no longer
had: a tile the game had filled looked free, and the friend-zone score (`cp_battle.c`
`AiGetFriendZoneCombatPositionScoreComponent`) read the friend where it had stood. Of the 8
phases where the copy first departed from the game with the decider's tile and target HP alike,
5 had such an unmoved enemy near the chosen tile. In vanilla Ch21 (`fc743d21`, turn 12) enemy 134
moved onto (2,2) in the game; the copy left it at (7,1), and enemy 138 struck from (2,2), a tile
it could not take. The lookahead's first phase (`nextPhase`) already moved such an enemy
(`followMove`).

**The change (`sight.lua` `M.idleMove`).** Both judged phases send `none` to one owner. The
decider stands on the tile it decided (`followMove`, as the game's AI phase moves each unit
before the next decides); an escape (`AI_ACTION_ESCAPE`) then leaves the map (`M.takeOff`),
holding no tile. A decider that performs nothing stays. Each way of the phase plays in its own
sandbox (`M.phaseWays`), so the move is undone between ways as a strike's stand is.

**Not changed.** A struck unit that lives still carries the mean HP its blow leaves (#743's
cause (b), in 7 of the 8 departures): splitting on every blow's HP outcome multiplies the ways
and is sized on its own. The lookahead's `replay` (the route watcher) keeps its own escape
handling.

**Proof (ADR 0430).** A unit test that fails without the change (`test_sight.lua`: `idleMove`
stands a mover, takes an escaper off from its tile, leaves a decider that performs nothing, and
both judged phases dispatch `none` to it; with the first phase's old `return nil` the last check
fails). One replay: vanilla Ch21 `b640e-cs-s4009` attempt 1, `PT_FORECAST` on (run `fx743i`,
against main's `fc743d21`). Copy strikes from a tile an enemy had already moved onto without
striking in the game: 2 in this game on main (turn 12, enemy 138 on (2,2)), 0 on the branch; 5
(3 decisions) over all 7 of main's instrumented games. Phases where no way of the copy matches the game: 3 of 40 on main,
2 of 32 on the branch, neither with such a mover near the decider. The branch played another
game (stuck on turn 33, 2 deaths), so the outcome is no verdict.
