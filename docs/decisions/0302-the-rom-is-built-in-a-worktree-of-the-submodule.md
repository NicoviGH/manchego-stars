---
id: 302
title: "The ROM is built in `build/fireemblem8u`, a git worktree of the submodule; the submodule stays vanilla"
date: "2026-09-30"
section: "Operational Gotchas (durable)"
issues: [408]
---

# The ROM is built in `build/fireemblem8u`, a git worktree of the submodule; the submodule stays vanilla

The injector used to write into the `fireemblem8u` submodule's own working tree. That left the
submodule permanently dirty, made every vanilla read a question of "HEAD or working tree", and
made staging a commit a matter of stepping around it.

## The rule

- **`inject.decomp.DECOMP` is the build tree**, `build/fireemblem8u`. The injector writes
  there, `make` compiles there, and the ROM, `.elf` and `.map` land there. Anything that reads
  the BUILT tree or its outputs (`verify_text`, `matrix.py`, `gen_symbols`, `playtest/run.sh`,
  `build.sh`) reads it.
- **`inject.decomp.SUBMODULE` is vanilla.** Nothing writes to it. Vanilla readers use it:
  `vanilla_decomp_text` and the census HEAD reads, and any tool that wants a vanilla file on
  disk. `git -C fireemblem8u status` is clean after a build.
- **The build tree is a git worktree of the submodule**, detached at the submodule's commit
  (`tools/build_tree.py ensure`, run by every injection). A real checkout of the same commit
  keeps every `git status` / `git checkout HEAD --` / `git show HEAD:` the injector and the
  fingerprint gate use working unchanged. The worktree's metadata lives in the submodule's
  gitdir, so the submodule's working tree stays clean. On a submodule bump, `ensure` drops the
  last injection and follows. The gitignored toolchain (agbcc, the native tools, `baserom.gba`)
  is symlinked in from the submodule. The decomp's Makefile never rebuilds a tool, so a build
  cannot write through a link.
- **The tree exists wherever the submodule does.** `run_tests.py` ensures it, because the
  census and scene-actor tests read the live tree. That tree was the submodule's working tree
  before, so it always existed: vanilla on CI, injected after a local build.

**One tree, not `build/<config>/`** as #408 first proposed. This Mac had 6.4 GB free, a decomp
with outputs is ~470 MB, and after ADR 0301 a config switch costs ~6 conversions and ~25 C
files. Per-config trees for the playtest matrix would be more worktrees of the same kind.

**What did not change.** The fingerprint gate still resets the tree it measures, because
isolating runs is its job; it now resets the build tree, not the submodule. Two builds in one
checkout still collide, because they share its `build/`. Concurrent agents still get their own
worktree (`tools/worktree-setup.sh`, which reads its toolchain list from `build_tree.py`).
`setup-toolchain.sh` and `build.sh` no longer rewrite the submodule's `#!/bin/python3`
shebangs: the injector normalises the build tree's copies on every build.

## Measured

- ROM sha1 `d1831ec0...` from the build tree, identical to the in-tree build it replaces.
- Cold build of a fresh tree 437s (every vanilla asset); no-change rebuild 30s, `make` up to
  date. Both taken while VS Code's crashpad process held ~430% CPU.
- `git -C fireemblem8u status` clean after `make`. Every test file passes with no build tree
  present (CI's `tests` job condition), because `run_tests` makes one.
- The ADR 0301 record now carries its tree: a record taken in the old in-submodule tree
  restored `msg.h` INTO the submodule on the first run, so a record is void anywhere else.
