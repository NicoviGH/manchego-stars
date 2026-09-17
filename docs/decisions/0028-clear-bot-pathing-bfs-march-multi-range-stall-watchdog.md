---
id: 28
title: "Clear-bot pathing: BFS march + multi-range + stall watchdog landed; #60 still open on boss-breach."
date: "2026-06-25"
section: "Working Conventions (Definition of Done)"
issues: [60]
---

# Clear-bot pathing: BFS march + multi-range + stall watchdog landed; #60 still open on boss-breach.

The #22 work exposed that the greedy clear-bot (#60) can't complete ch01/ch02 unaided. Reworked it
toward a real fair-play completability gate: (a) a **BFS distance-field march** (pure `pathing.lua`,
unit-tested in `test_pathing.lua`) over a walkable map from `gBmMapTerrain` — units route *around*
walls/water toward the boss instead of greedy-Manhattan stranding; (b) **multi-range targeting**
(`clearUnitAct` reads each unit's real `unitAttackRange` instead of hardcoding range 1); (c) a **stall
watchdog** (no-progress turns → `B`-unstick, then a clean `stuck` FAIL); (d) a **bug fix** — a title
screen without a chapter advance is now a game-over, not a false win (old `clearDrive` could PASS a
loss). `clear` (prologue) now passes fair-play. **Not fully closed:** on ch01 the bot marches to the
walled boss-camp (gate at a `TERRAIN_GATE_CASTLE` ringed by walls) but jams ~8 tiles out with a thin
2-unit deploy — the open work is last-mile **breach/unjam** logic (field more units; slip around a
chokepoint; focus-fire the nearest reachable straggler), tracked on #60. Until then `reachCh02Map`
keeps its directed ch01-seize helper (it can't ride the fair-play bot yet). Passability uses a
conservative impassable-terrain set (walls/peaks/water/fence/snag/cliff); high-cost-but-passable
terrain stays passable because the per-turn `selectAndReach` still enforces true reach.
_Decided: 2026-06-25 (CLAUDE; brainstormed-then-TDD; scope "full gate" — Nicolas; landed partial + kept #60 open after the breach proved deeper)_

---

**A stack of PRs lands with MERGE COMMITS, and every child retargets to `main` BEFORE its parent's
branch is deleted.** Squash-merge stays the default for the normal case (one feature, one branch off
`main`). It is the wrong tool for a stack — each PR based on the one below it — because a squash
collapses the parent into a *new* commit that is not in the child's history, so GitHub re-shows the
parent's diff on the child and a rebase + force-push is owed between every merge. Merging with a
merge commit keeps the parent's commits in history, so each child merges clean with no rebase at all
(verified 2026-08-06 landing #237 → #239 → #240 back to back).

The trap that is not obvious: **`gh pr merge --delete-branch` on the parent CLOSES any PR whose base
is that branch.** GitHub does not retarget it, and a closed PR cannot be retargeted afterward
(`Cannot change the base branch of a closed pull request`). The order that works:

```sh
gh pr edit <child> --base main     # retarget every child FIRST
gh pr merge <parent> --merge --delete-branch
```

Recovery if a child is already closed this way: re-push the deleted base ref from its recorded tip
(`git push origin <oldtip>:refs/heads/<branch>`), `gh pr reopen <child>`, retarget it to `main`,
merge, then delete the restored ref. This is why the handoff records each branch tip.
_Decided: 2026-08-06 (Nicolas — merge commits for the stack; the retarget-before-delete rule is from landing #237/#239/#240)_

---

**A lint may not import `build_campaign`, and a limit may not be written down.** Two rules with one
root, both from the code review of the #237/#239/#240 stack (#241).
