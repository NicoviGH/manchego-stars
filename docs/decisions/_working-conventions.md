---
section: "Working Conventions (Definition of Done)"
kind: section-note
---

**Why this section exists:** the project drifted because the plan was written up front,
then implementation pivoted (Python not TS, decomp-native not Event Assembler, stock
classes not homebrew) and the canonical docs/issues were never reconciled. The same
fact lived in CLAUDE.md, PRD.md, README, rules-mapping, decisions.md, and GitHub, so
no update ever propagated. These conventions keep a single source of truth.

**Single source of truth — link, don't restate.** Each fact lives in exactly one place:
- *Settled decisions & rationale* → this file (`decisions.md`).
- *Per-chapter facts* → chapter YAML → generated `CHAPTERS.md`. *Unit facts* → unit YAML → `CLASSES.md`.
- *Work backlog* → GitHub issues (milestones M0–M4).

**HANDOFF.md is authored on `main` only (2026-07-30).** Gated by
`check.py check_handoff_only_on_main`; a branch may leave it untouched or sync it to main's
tip, but may not author its own. Refresh it on main *after* a merge, never on the branch.

*Why it needed a gate rather than a habit.* HANDOFF describes **global** live state, but it
is a tracked repo-root file — so every branch and worktree gets a private copy that quietly
stops describing the project and starts describing *the project as that branch last saw it*.
Merge the branch and the stale copy overwrites main's. With one short-lived branch at a time
this never surfaced: every HANDOFF commit before 2026-07-21 landed on main. Two long-lived
parallel branches (ch04 and ch05, nine days) made divergence certain, and the last merge won
regardless of which copy was newer. The ch05 merge put ch04 back to a "WIP checkpoint" four
committed stages out of date; it was only caught because `git pull` refused to clobber an
unrelated local edit.

This is the same root cause as *"feature-flow only works if each feature LANDS before the
next starts"* (below), showing up in a file instead of a rebase — and it had **already been
caught once**, on 2026-07-21, with the mitigation "keep the copies in sync". That is a
memory, not a control, and it failed nine days later. Hence a check: the guard passes the
two states that are actually safe (untouched — git's 3-way merge keeps main's version; or
byte-identical to main's tip, the ideal state for a worktree people read HANDOFF in) and
fails only a branch carrying live state it does not own. It reports *skipped* rather than
*violated* when it cannot see a base, because a guard that cries wolf gets bypassed.
- *Live state* → the single **`HANDOFF.md`** (one trunk, feature-flow — the per-track handoffs were retired 2026-06-24); `/handoff` refreshes it in place. Keep it lean: live Now/Next + gotchas + pointers, no per-session history (that's `git log` + closed issues). *Vision/pitch* → `PRD.md` (no specifics that live elsewhere).
- `CLAUDE.md` is lean **operating instructions + pointers**, not a fact store (a bloated CLAUDE.md gets ignored). If a fact belongs in two docs, one of them should link instead.

**Record decisions when made.** Any change that alters architecture, scope, tooling, or a
settled rule gets a dated entry here in the same session — ADR-style, while context is
fresh. Don't leave it in chat or agent memory only.
