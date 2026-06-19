# Handoff — Manchego Stars · live state + pointers (backlog lives in GitHub issues, not here)

**Date:** 2026-06-19 (session 18)
**Session focus:** Shipped the **v0.1.0 friend release** and stood up the **parallel-work
infrastructure** (#50) so two instances can run at once. Single instance this session.

## Shipped this session (all on main, green, pushed)
- **v0.1.0 friend release** — versioning scheme `v0.<chapters-playable>.<patch>` (`VERSION` file;
  `tools/build.sh dist` stamps `dist/ManchegoStars-v<VERSION>-DATE.gba`; tagged `v0.1.0`). Fixes the
  Ch1 difficulty soft-trap (carries the #45 lord floor). Smoke-tested: `ch01win` PASS on the dist
  montage ROM (boot → prologue → Ch1 → seize → ending → title). **Friend-shippable.** ADR in
  `decisions.md` §Distribution & Scope; noted on #37.
- **Parallel-work infrastructure (#50)** — the dev-infra to run content 🔒 + pipeline ⚡ as two
  instances:
  - **Build isolation proven**: git 2.50 gives each worktree its own submodule gitdir; an isolated
    build succeeded (~1m46s). `tools/worktree-setup.sh` bootstraps an instance worktree (add
    worktree → init submodule from local objects → symlink the gitignored toolchain).
  - **Engine/content file seam**: extracted the 5 campaign-agnostic engine hooks into
    `tools/inject/engine_hooks.py` + shared `tools/inject/decomp.py`; `build_campaign.py` (4204→3713
    lines) orchestrates them. Sprite/palette hooks stay with content. `check.py` guard rewritten
    (def-in-module + call-in-orchestrator; both arms verified to bite). **Behavior-preserving:
    byte-identical ROM** + `make test` (60) + `lordfloor` PASS.
  - **Per-track files**: `HANDOFF-content.md` / `HANDOFF-pipeline.md` (each has its launch/kickoff
    prompt + ownership map + next steps).
  - Two ADRs in `decisions.md` §Delivery model.

## Next session
**To go parallel:** launch two instances using the kickoff prompts at the top of
`HANDOFF-content.md` (→ Ch2 slice #22) and `HANDOFF-pipeline.md` (→ #48 next items). Each
bootstraps its own worktree via `tools/worktree-setup.sh`; both trunk-based onto main.
**Single-instance** work continues from those same per-track Next lists. Roadmap: #49.

## Builds / tools
`tools/build.sh test` (lean dev) · `tools/build.sh dist` (montage; **the friend build**) ·
`make difficulty CH=chNN [--lord-floor]` · `make test` (60) · `make check` (drift guard) ·
`tools/playtest/run.sh lordfloor|ch01win|win|titlecard` · `tools/worktree-setup.sh <path>`
(bootstrap a parallel instance). NEVER a bare `make` for a shippable ROM.

## Gotchas (operational)
- **New decomp patch target → add it to `PATCHED_DECOMP_FILES`** or the build is non-idempotent.
- **Engine stat changes to the chosen lord go in `EndPrepScreen`**, not a phase-start seam.
- Engine hooks now live in `tools/inject/engine_hooks.py`; the drift guard points there.
- `make`-green can't prove apply timing — `tools/playtest/` is the dynamic arbiter.
- Vanilla decomp reads go through `build_campaign.vanilla_decomp_text()` (HEAD), never the worktree.
- **Never commit the `fireemblem8u` submodule pointer.** Nicolas can't see inline renders — save to
  `map-review/` + `open`. Behavior-preserving refactor ⇒ byte-identical ROM (use the md5 as proof).

## Standing rules
Combat = pure vanilla FE; field parity with vanilla ch N is doctrine. **Process:** superpowers
(brainstorm → spec → TDD → verify → review); spec = `decisions.md` ADR + GitHub issue. Custom art
where it matters, **show before committing** (2-3 options, Nicolas drives). **Project knowledge
lives in the repo** (issues = backlog, `decisions.md` = decisions, HANDOFF = live state), not private
memory. **Trunk-based: auto-push to main once green; small commits; never long-lived branches.**
