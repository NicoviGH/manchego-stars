---
id: 353
title: "While chapters are unlocked, the verdict diff is the regression signal"
date: "2026-10-19"
section: "Combat System"
issues: [510]
---

# While chapters are unlocked, the verdict diff is the regression signal

#510 unlocks ch00-ch07: every lock was measured on a model that misloaded units (#490), so
`difficulty-gate` stops enforcing anything until the chapters re-lock at #510 step 10. With no
lock, a change that moves a chapter's parity would land silently, and a model step could not
show that it moved the verdicts it claimed to move.

**Every PR that touches a parity input gets a verdict diff** (`tools/verdict_diff.py`,
`make verdict-diff`): the campaign curve read on the base commit and on the PR, in
Tutorial, Normal and Difficult (the authored table too until #510 step 2 retired it, ADR
0355), and every chapter-by-mode cell whose
verdict, threat ratio, clear-load ratio, accepted residual or per-unit finding moved. It runs
on every PR rather than only on #510's, because the moves it exists to catch come from PRs
that were not about difficulty: #508's pid rewrite took ch04's Mogalls from 32 HP to 15.

**It stays out of day-to-day work (Nicolas, 2026-10-19).** Most PRs are not about difficulty:
- **A PR that touches no parity input skips the read**, and the submodule checkout with it.
  The inputs are derived, not listed by hand: the read's import closure from the source (the
  whole injector, since it loads itself whole), every campaign YAML, and the engine patches.
  `test_verdict_diff` traces a real read and fails if a module it loads or a file it opens is
  not covered, so the skip cannot quietly go stale. A sprite, a Lua probe or a doc skips.
- **The PR gets a comment only when a cell moved.** An unmoved read goes to the job summary.
  When a later push stops moving anything, the earlier comment is edited to say so.
- It runs as its own job beside `build`, which is the PR's critical path, so it adds no wall
  clock.

- **It never fails a build.** A model step exists to move verdicts. The diff is evidence a
  reviewer reads against the step's claim, and #510's stopping rule ("stop when a step moves
  no verdict") is read off it.
- **A ratio moves when its printed value would.** The curve prints two decimals, and the
  diff compares those, not a delta.
- **Both trees read the same vanilla.** The base tree is a worktree with this checkout's
  submodule linked in; the submodule pointer is never committed, so this is the decomp both
  sides were measured against.
- **The lock is not part of it.** Unlocking a chapter changes no verdict, so it moves no row.

When the chapters re-lock at #510 step 10, the gate is the regression signal again. Keeping
the diff after that is a separate decision.
