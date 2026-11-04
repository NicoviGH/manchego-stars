---
id: 390
title: "One checkout, one writer; a branch's HANDOFF drift is undone, never synced"
date: "2026-11-04"
section: "Working Conventions (Definition of Done)"
issues: [572]
---

# One checkout, one writer; a branch's HANDOFF drift is undone, never synced

**Supersedes ADR 0023** (per-instance git worktrees) **and amends the HANDOFF rule** in
`_working-conventions.md`. Both were Nicolas's calls on 2026-10-29, held until now only in a
session memory and in HANDOFF.md, while the repo still said the opposite.

**One checkout, one writer.** A task is a plain branch in the repo's main checkout. A worktree is
created only with Nicolas's say-so: he had told sessions to stop and repeated it on 2026-10-29
after one was made for a HANDOFF commit, and a worktree lacks the `fireemblem8u` submodule, so
the pre-commit checks cannot run in it. Two ROM builds in one tree corrupt each other, so a second
writer waits. Cut branches from `origin/main`.

**HANDOFF drift is undone, never synced.** A branch that carries a HANDOFF.md change is undone by
how the change got there, and `check_handoff_only_on_main` names that fix:
- **staged:** `git restore --staged --worktree HANDOFF.md`;
- **main's own unpushed commits** (the branch was cut from a local main that held them): push
  main, then `git merge origin/main` into the branch;
- **written by the branch:** restore the copy the branch started from and commit it
  (`git checkout $(git merge-base origin/main HEAD) -- HANDOFF.md`), so its net change is zero.

Copying main's file onto the branch (`git checkout main -- HANDOFF.md`) is never the fix, though
the guard still passes a byte-identical copy. Nicolas, 2026-10-29: "we don't need a branch copy
of handoff, just the main one!!!" A copy is a branch commit of HANDOFF, so main's next refresh
makes it drift again, and each "fix" by copying added another: a loop that cost several sessions.
Undoing the drift leaves the branch with no net change, so main can refresh freely.
