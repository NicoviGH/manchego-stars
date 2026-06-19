# Handoff — Manchego Stars · live state + pointers (backlog lives in GitHub issues, not here)

**Date:** 2026-06-19 (session 17)
**Session focus:** Ran **Phase 0** (#45 lord-floor wiring + `parity_reference` landing), then
course-corrected the parallel-work plan: the old "branch-per-track + stay-in-your-section"
idea was brittle and fought this repo's trunk-based norm. **Next session = ONE last single
instance** that cuts the friend release + lays the real parallel infra, THEN we split.

## Shipped this session (all on main, green, pushed)
- **Lord survivability floor (#45 3b + 3c)** — `1456ecf`, playtest-verified. `gLordFloorDeltas[]`
  build table (`build_campaign.lord_floor_rows`, TDD) + `LordFloor_ApplyOnce` (eventinfo.c),
  applied once at **`EndPrepScreen`** (the deployment-finalization seam — phase-start hooks fire
  before prep deploys on turn 1, so they land the floor a phase late). Flag-gated `0xFA`. Guard
  in `check.py`; decision in `decisions.md`. `tools/playtest/run.sh lordfloor` PASSes (marty
  +7HP/+4Def at Ch1 t1, stable, no double-apply); `ch01win` still PASSes.
- **`parity_reference` across Prologue–Ch8 (#48 item 1)** — `fe8cd06`. Per-chapter enemy-pressure
  bar from each chapter's authored cadence base. **ch08 → "FE8 Ch13" flagged informational** (its
  objective is a scripted defeat) — confirm when #48's extractor/CI lands.
- **`.gitignore` fix** so `tools/playtest/states/` is actually ignored.

## Next session — ONE single instance, three tasks (do in this order)

### 1. Cut the friend release `v0.1.0` (quick — unblocks shipping)
The friends' current build is `dist/ManchegoStars-Alpha-2026-06-17.gba` — it **predates the
floor fix**, so a frail-lord pick could soft-trap them before the ending. This build fixes that.
- **Versioning convention** (implement exactly this): scheme `v0.<chapters-playable>.<patch>`,
  staying `0.x` until the full MVP (Prologue+8ch) ships as `v1.0`. **This build = `v0.1.0`**
  (Prologue+Ch1 playable + balanced; the 06-17 Alpha was pre-versioning — start the scheme clean
  here, don't retro-tag it). Implement: add a `VERSION` file (`0.1.0`); make `tools/build.sh dist`
  read it and stamp `dist/ManchegoStars-v0.1.0-YYYY-MM-DD.gba`; `git tag v0.1.0 && git push
  --tags` on each shipped build. "Alpha" stays as the title-screen/README *label* for the whole
  0.x phase. Record the scheme in `decisions.md` in the same commit.
- **Smoke-test the DIST build** (montage, not the lean test build): `tools/build.sh dist`, then
  `tools/playtest/run.sh ch01win` against the dist ROM — confirm boot → prologue → Ch1 → seize →
  ending. (Optionally `win`/`titlecard` for the opener.) Then it's friend-shippable.
- Optional: a 1-line release note for friends — "v0.1.0: fixes Ch1 difficulty so every lord can
  reach the ending."

### 2. Decompose the shared seam so parallel work can't collide (the real de-confliction)
`build_campaign.py` is a **4,203-line monolith** both tracks would otherwise share. Extract the
**11 `_patch_*` / `_inject_*` engine-hook functions** into a new `tools/inject/engine_hooks.py`
module (to be created); `build_campaign.py` imports + orchestrates them. Result: pipeline owns
`engine_hooks.py` + `difficulty.py` + `fe_combat.py`; content owns `build_campaign.py`'s
`inject_*` + chapter YAMLs — ownership maps to **files**, not etiquette.
- **CRITICAL — rewrite the guard, don't just re-point it.** `check_engine_guards_present` counts
  each hook fn `>=2x` in `build_campaign.py` (def + call co-located). The split breaks that: the
  **def** moves to the new module, the **call** stays in the orchestrator, so neither file has it
  twice and the guard fails (loudly — good) until fixed. Rewrite to two precise checks per hook —
  `def <fn>` present in the engine-hooks module (defined) AND `<fn>` present in `build_campaign.py`
  (orchestrator calls it). Then prove it still bites: delete one call, confirm `make check` fails,
  restore.
- Pure refactor → keep `make check` green and re-run `lordfloor` + `ch01win` to prove no behavior
  change.

### 3. Stand up the trunk-based parallel setup (then we can split)
- **Trunk-based, not branch-per-track.** Repo already auto-pushes to main once green and CI
  (`.github/workflows/checks.yml`: drift guard + build) gates it. Keep that. Small, frequent
  commits; **no long-lived per-track branches** (that was the brittle bit).
- **Worktrees for BUILD ISOLATION only** (not source isolation): the build mutates the
  `fireemblem8u/` submodule working tree, so two agents in one checkout would race. Give each its
  own working dir, both committing small + pulling often. **Verify** git-worktree + submodule
  isolation actually works (each worktree may need its own submodule checkout — test a build in
  each before trusting it).
- **Regenerate the two instance prompts** (drop the branch-per-track framing; trunk-based +
  build-isolation worktree instead). **Seed per-track handoff files** `HANDOFF-content.md` /
  `HANDOFF-pipeline.md` so the two instances don't clobber a shared `HANDOFF.md`.

> After task 3, split into Content (instance A: Ch2→Ch8 slices #22–#28, +#18/#17/#19/#38/#39,
> #45-4/-5) and Pipeline (instance B: #48 next items → playtest platform → #11/#9/#8/#46).
> Roadmap #49. Backlog lives in GitHub issues, not here.

## Builds / tools
`make difficulty CH=chNN [--lord-floor]` · `make test` (60) · `make check` (drift guard) ·
`tools/build.sh test` (lean dev) · `tools/build.sh dist` (montage; **the friend build**) ·
`tools/playtest/run.sh lordfloor|ch01win|win|titlecard`. NEVER a bare `make` for a shippable ROM.

## Gotchas (operational)
- **New decomp patch target → add it to `PATCHED_DECOMP_FILES`** or the build is non-idempotent
  (2nd inject sees the patched file; the `count==1` guard aborts). Bit `bm.c` this session.
- **Engine stat changes to the chosen lord go in `EndPrepScreen`, not a phase-start seam** — those
  fire before prep deployment finalizes on turn 1. `make`-green can't prove apply timing; playtest it.
- **If/when engine hooks move to a new module, point `check.py check_engine_guards_present` at it.**
- **git worktree + the `fireemblem8u` submodule is finicky** — verify build isolation per worktree.
- Vanilla decomp reads go through `build_campaign.vanilla_decomp_text()` (HEAD), never the working tree.
- Static difficulty engine = proxy; `tools/playtest/` is the dynamic arbiter (it caught the floor timing bug).
- **Never commit the `fireemblem8u` submodule pointer.** Nicolas can't see inline renders — save to
  `map-review/` + `open`. Story text → `make` regenerates bodies; gate with `tools/verify_text.py`.

## Standing rules
Combat = pure vanilla FE; field parity with vanilla ch N is doctrine. **Process:** superpowers
(brainstorm → spec → TDD → verify → review); spec = `decisions.md` ADR + GitHub issue. Custom art
where it matters, **show before committing** (2-3 options, Nicolas drives). **Project knowledge
lives in the repo**, not private memory. **Trunk-based: auto-push to main once green; small
commits; never long-lived branches; never the submodule pointer.**
