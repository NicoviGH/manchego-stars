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

**Every PR that touches code or content prints a verdict diff** (`tools/verdict_diff.py`,
`make verdict-diff`): the campaign curve read on the base commit and on the PR, in the
authored table and in Tutorial, Normal and Difficult, and every chapter-by-mode cell whose
verdict, threat ratio, clear-load ratio, accepted residual or per-unit finding moved. CI
posts it as one PR comment, updated on each push, and in the job summary.

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
