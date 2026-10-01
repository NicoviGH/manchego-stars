---
id: 303
title: "CI caches the INJECTED build with its compiled record, and pins agbcc's headers"
date: "2026-10-01"
section: "Operational Gotchas (durable)"
issues: [408]
---

# CI caches the INJECTED build with its compiled record, and pins agbcc's headers

The vanilla cache (ADR 0299) left our own content to rebuild on every run. CI now packs every
build output in `build/fireemblem8u` plus `.build-compiled` after `make green`, and restores
the newest one for the ref (else `main`'s) in place of the vanilla cache. The vanilla cache
stays as the fallback. Every run saves, PRs included.

## What is cached

`tools/build_tree.py outputs`: the files git does not track in the tree, minus the toolchain
links and minus the injector's own writes. The next build injects those afresh, and the record
holds their mtimes. The key is the vanilla key (the objects embed that compile) plus the run;
restore is by prefix.

## The rules that make a restore correct

- **A recorded file whose bytes differ from what was compiled is left newer than its record**
  (`inject.warm._rewind_unchanged_mtimes`). CI pins tracked sources to 2000-01-01, so a file
  injected in the cached build but vanilla now would otherwise keep its stale object.
- **`load_compiled` ignores the worktree's `.git` file and every link.** A fresh checkout makes
  both newer than any restored record, which would void it.
- **A record carries forward only paths in its own tree.** Records from before ADR 0302
  listed the submodule's files and passed them on forever, so the rewind could write our
  `msg.h` into the vanilla submodule.
- **agbcc's headers are pinned with the sources.** Every object depends on
  `tools/agbcc/include`, which "Install agbcc" rewrites each run, so unpinned they rebuilt all
  357 C files on every hit. The key already hashes every file under `tools/agbcc`.
- **The tars are `--format=posix`.** GNU tar's default truncates mtimes to the second.

## Measured (#421)

| | miss | hit |
|---|---|---|
| `make green` | 103s, 1,516 conversions, 357 C files | 27s, 1 conversion, 0 C files |
| `build` job | ~150s | 77s |

ROM sha1 `c62dd296...` for both. The key includes the runner's `ImageVersion`. GitHub rotates
images, so a flip is a miss until that image has a cache of its own.
