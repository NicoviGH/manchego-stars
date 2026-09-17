---
id: 23
title: "Parallel work model: per-instance git worktrees for build isolation, not branch-per-track."
date: "2026-06-19"
section: "Working Conventions (Definition of Done)"
issues: []
---

# Parallel work model: per-instance git worktrees for build isolation, not branch-per-track.

The two tracks above run as two Claude instances against trunk. The load-bearing requirement is
**build isolation**: `make` mutates the `fireemblem8u` submodule working tree, so two instances in
one checkout would race and corrupt each other's build. Each instance therefore gets its own
**git worktree** on a short-lived `inst/*` branch (git 2.50 gives each worktree its own submodule
gitdir under `.git/worktrees/<wt>/modules/` — verified isolated). Trunk-based discipline holds:
small frequent commits, integrate to `main` often, no long-lived branches (the earlier
branch-per-track idea was dropped as brittle). Bootstrap a worktree with `tools/worktree-setup.sh`,
which inits the submodule from the local object store (no re-clone) and **symlinks** the gitignored
toolchain (`agbcc` + native binaries + `baserom.gba`) from the primary checkout — the compilers are
static and read-only during a build, so sharing them is safe and instant; isolation is only needed
for the source/build tree. Worktrees are work tracker #50. The file-level engine/content seam (below)
is preventative polish on top of isolation, not a prerequisite for it.
_Decided: 2026-06-19_
