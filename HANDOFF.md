# Handoff — Manchego Stars · `main` = integration/solo router

**What this file is.** You're on `main` — the integration/solo tree (cross-track merges and ad-hoc
one-offs). This file holds only what belongs to no single lane, and carries **no per-session
snapshot**, so it can't go stale. For what shipped recently, read `git log --oneline -20` + closed
issues — that's the live record, not this file.

## Where the live state lives
- **Content track** (Ch2+ slices, dialogue, art) → `HANDOFF-content.md` — owned by the content instance.
- **Pipeline track** (difficulty/parity engine, playtest, CI) → `HANDOFF-pipeline.md` — owned by the pipeline instance.
- **Backlog & milestones** → GitHub issues (#49 roadmap). **Decisions** → `docs/decisions.md`.
  **Operating instructions** → `CLAUDE.md`.
- Each lane runs in its own worktree (`../ms-content`, `../ms-pipeline`); don't do track work on `main`.

## Current release
**v0.1.0** friend release — Ch1 playable. Versioning `v0.<chapters-playable>.<patch>` (`VERSION` file,
tag `v0.1.0`); `tools/build.sh dist` is the friend build. ADR: `decisions.md` §Distribution & Scope (#37).

## Builds / tools
`tools/build.sh test` (lean dev) · `tools/build.sh dist` (montage; **the friend build**) ·
`make difficulty CH=chNN [--lord-floor]` · `make test` · `make check` (drift guard) ·
`tools/playtest/run.sh lordfloor|ch01win|win|titlecard` · `tools/worktree-setup.sh ../ms-<track>`.
**Never a bare `make` for a shippable ROM.**

## Cross-cutting gotchas
- New decomp patch target → add it to `PATCHED_DECOMP_FILES`, or the build is non-idempotent.
- Engine stat changes to the chosen lord go in `EndPrepScreen`, not a phase-start seam.
- Engine hooks live in `tools/inject/engine_hooks.py`; the drift guard points there.
- `make`-green can't prove apply timing — `tools/playtest/` is the dynamic arbiter.
- Vanilla decomp reads go through `build_campaign.vanilla_decomp_text()` (HEAD), never the worktree.
- **Never commit the `fireemblem8u` submodule pointer.** A behavior-preserving refactor ⇒ byte-identical
  ROM (md5 = proof). Nicolas can't see inline renders — save to `map-review/` + `open`.

## Standing rules
Combat = pure vanilla FE; field parity with vanilla ch N is doctrine. **Process:** superpowers
(brainstorm → spec → TDD → verify → review); spec = `decisions.md` ADR + GitHub issue. Custom art where
it matters, **show before committing** (2-3 options, Nicolas drives). **Project knowledge lives in the
repo** (issues = backlog, `decisions.md` = decisions, lane HANDOFFs = live state), not private memory.
**Trunk-based: auto-push to main once green; small commits; never long-lived branches.**
