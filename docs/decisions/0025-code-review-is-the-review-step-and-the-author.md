---
id: 25
title: "`/code-review` is the review step, and the author never reviews their own PR"
date: "2026-09-02"
section: "Working Conventions (Definition of Done)"
issues: []
---

# `/code-review` is the review step, and the author never reviews their own PR

The flow above names `/code-review`, and it is mandatory rather than a suggestion. Two things
kept going wrong. An author re-reading their own diff finds nothing: #338 shipped unreviewed
and a fresh reviewer then found two real defects the author had read past twice, and the #335
stack repeated it at scale — four of five PRs needed fixes and two were Critical, including a
guard that was defined, unit-tested, and never registered in the gate it was written for. And
a reviewer prompt improvised in the moment is not the skill: skills change, so reconstructing
one from memory quietly runs an older process. `superpowers:requesting-code-review` is the
variant for a STACK, or where a PR needs context the diff cannot carry — one fresh reviewer
per PR, working DOWN the stack, because a fix to an earlier PR rebases every PR above it.

- **The "not my job" propagation test runs at PR review** — push the change through the desks and watch
  the reactions (my job / I can help / no impact / no need to know). Review is where ownership is decided,
  replacing the pre-commit glob block.
- **Engine/content stays a HARD invariant.** The Engine/Content Boundary Rule (no character/chapter/plot
  in `.c`/`.s`) + the engine hooks in `tools/inject/` (`check_engine_guards_present`; its guarded tuple
  is the authoritative list — the count here read "5" long after it grew) are genuine
  decision-hiding and remain gates. The character-name half is now mechanized
  (`check_engine_campaign_agnostic` scans the hand-written engine sources for any campaign id);
  chapter-number / plot-event references stay a review-judgment call.
- **`check_lane_ownership` is demoted to an advisory** desk-span note (no longer a block). The glob map it
  carries is the seed of the **desk map**: each desk = a responsibility + its phone (interface) + its
  cabinet (private files), the design vocabulary enforced at review.
- **Design placement** follows the three reflexes (`CLAUDE.md` → Design placement test): *not my job*
  (push each line to its owner), *no need to know* (no desk reaches into another's cabinet), *futures*
  (judge boundaries by the changes they make cheap; localize decisions likely to change — but don't split
  what has no expensive future, e.g. `harness.lua`).

Supersedes the fixed-lane ADRs (Seam enforcement #55; the 2026-06-22 `record*` refinement; "track work
always in that track's worktree"). The two ADRs above — worktree isolation and the 5-hook engine/content
file seam — **stand**: worktrees are now ephemeral-per-feature, and the file seam is the hard invariant
feature-flow keeps.
_Decided: 2026-06-24 (Nicolas — chose feature-flow + PRs; codified from the "not my job" design review)_

**Feature-flow only works if each feature LANDS before the next starts — parallel unmerged lines on
shared files are what force a rebase every time you come back.** Symptom (2026-07-21): two sibling
branches off `main` — #193 (winter forest fidelity) and the ch04 map slice — were open at once, one a
committed-but-PR-less branch, the other **uncommitted WIP left in its worktree**. Both edited the same
cross-cutting "hot" files (`tools/gen_map_editor.py`, `tools/map_tileset_tool.py`,
`campaigns/.../maps/reskin-learned.json`, and `docs/decisions.md` — every ADR appends near the same
line), and both **independently re-derived** the same vanilla-layout `.bin`→`.mar` reader under
different function names. `main` then moved underneath the stale WIP, and integrating them cost a full
conflict-resolving rebase. The rebase is the *symptom*; the discipline that prevents it:

- **Land each feature end-to-end before starting or resuming the next** (commit → PR → CI → squash-merge
  → delete branch), especially anything touching shared tooling / JSON / `decisions.md`.
- **Never leave a worktree dirty across a session boundary** — at minimum commit a checkpoint on the
  feature branch so `main` can't strand it. Long `HANDOFF.md` "do not lose or revert" lists are the smell
  that this rule is being broken.
- **Reuse, don't re-derive** — grep for an existing helper before writing a new one; two branches solving
  one problem two ways guarantees both wasted work and a merge conflict.
- **Append new ADRs at the END of their section**, not mid-file, so two branches don't insert at the same
  line and collide.

This is the operational half of the feature-flow ADR above (which settled the *structure*); this settles
how it must be *practiced* by any agent (Claude or Codex) picking work up across sessions.
_Decided: 2026-07-21 (post-mortem of the #193 / ch04 parallel-branch rebase)._
