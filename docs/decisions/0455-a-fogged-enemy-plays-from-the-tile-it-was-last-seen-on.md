---
id: 455
title: "A fogged enemy plays from the tile it was last seen on"
date: "2026-11-22"
section: "Combat System"
issues: [713, 699, 510]
---

# A fogged enemy plays from the tile it was last seen on

**Decided (Nicolas, 2026-11-22, "Oh yeah I approve your recommendations": #713 fix 1, option A
of comment 7078483524).** Extends ADR 0399 within an attempt. It adds threats the planner reads;
it changes no price.

**The gap.** Before this, a fogged enemy played as seen only if an earlier attempt remembered it
(ADR 0399), and then from where it truly stands. Within an attempt, an enemy that stepped back
into fog was gone from every danger read and both judged phases. In vanilla Ch19 `b640e-cs-s4003`
attempt 1 (`isomain`), the turn-5 death of charId 23 was to arrival 155, which the turn's earlier
plans listed as a striker at (9,18) and the plan that put the victim in reach did not (#713
comment 7082062860).

**The call.** A red unit this attempt has shown out of the fog, now in fog, is a **ghost**: it is
played from the tile it was last seen on, which is what a player knows, never from its true tile.
- **Where it was seen.** botrun tells the sight every red each board shows out of the fog
  (`sight.sighted`); the sight keeps its tile under its slot, character, class and arrival turn
  (ADR 0449). A slot an arrival refilled is another unit, with no ghost (`Sight.ghostOf`).
- **Where it plays.** In the danger and threat grids and in both judged phases (`enemyPhase`, and
  both of `nextPhase`'s phases with the army's reply between), inside their sandbox: the ghost's
  struct and its `gBmMapUnit` cell are moved to the seen tile (`placeGhosts`, journaled writes,
  so the sandbox puts it back), its tile is lifted out of the fog as a remembered unit's is, and
  `decides` and the reply count it as seen (`s.plays`). In the judged phase it then moves and
  strikes from there as the game's AI decides. `Bot.enemiesOf` lists it as a threat, a copy
  standing on the seen tile (`ghost = true`); it is never a target (the game refuses one in fog).
- **Its cell taken.** A ghost whose tile another unit holds does not play: on the board, the
  player sees it is not there; in a judged phase, a plan that stands one of ours there has the
  cell, as our units are placed first.
- **Precedence.** A unit a retry remembers plays where it stands (ADR 0399), so it has no ghost.

**Left out, by the approved scope.** `closings`' looters and `keySources` still ask ADR 0399's
memory only (`s.knows`): both read a unit's tile or kit for a goal, not a strike. An enemy the
screen showed only in a fight (it struck from fog and stayed there) has no seen tile: the record
holds its slot, not where it stood (`sawEnemy`). The approved sum of unseen strikes (#713 fix 3)
is its own PR.

**Why not B (ADR 0399's memory for the same attempt).** It plays a fogged enemy where it truly
stands, every turn: more than a player knows, so Ch19 would read easier than a player could play
it (comment 7078483524).

**Proof.**
- Unit tests that fail on main: `test_sight.lua` (`Sight.ghostOf`'s matching; `sighted`/`ghostOf`
  and a held cell; every ghost-placing sandbox is `ghostly`), `test_bot.lua` (a ghost is a
  threat on its seen tile, never a target, the board's unit not moved), `test_botrun.lua` (every
  board tells the sight its reds in sight, never a fogged one).
- Emulator probe `PT_VANILLA=1 PT_LEAKGUARD=1 tools/playtest/run.sh ghostprobe` (retail
  Prologue): the enemy farthest from Eirika (6 tiles off), put in fog and told as last seen
  beside her, threatens her tile, strikes her in `enemyPhase` and moves in `nextPhase`'s first
  phase, and `enemiesOf` lists it at the seen tile. The control, a sight told nothing, reads none
  of it. Its struct and the seen cell are as they were after every read, and no sandbox leak is
  logged: PASS.
- One replay, tag `fix713g` (vanilla Ch19 `b640e-cs-s4003` attempt 1): see #713.
