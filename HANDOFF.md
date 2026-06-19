# Handoff — Manchego Stars · live state + pointers (backlog lives in GitHub issues, not here)

**Date:** 2026-06-19 (session 17)
**Session focus:** Ran **Phase 0** (the on-`main`, pre-split groundwork): finished the #45
lord-floor wiring (items **3b + 3c**) and landed `parity_reference` across every authored
chapter (#48 item 1, Nicolas-approved). Both shared-file streams are now de-conflicted, so the
campaign can split into the two parallel instances. Phase 0 is **done**.

## Shipped this session
- **Lord survivability floor (#45 3b + 3c)** — commit `1456ecf`, playtest-verified:
  - **3b** `build_campaign.py` emits `gLordFloorDeltas[]` (events_udefs.c): one
    `{+maxHP,+Def,+Res}` row per lord candidate = `difficulty.lord_floor_delta` @3.5 vs Ch1
    enemies, parallel to `gLordSelectCandidates[]`. Ch1 → shamans +7HP/+4Def, armor tanks 0.
    TDD: `bc.lord_floor_rows` (2 tests; suite now 60).
  - **3c** `LordFloor_ApplyOnce` (eventinfo.c, beside `LordSelect_GetPid`) bakes the chosen
    lead's row into HP/Def/Res **once**, gated by permanent flag `0xFA`, **spent only on a
    real application** (pick flag set AND lead found) so the prologue/pre-deploy phases skip.
  - **Hook point = `EndPrepScreen`** (prep_sallycursor.c, after `ShrinkPlayerUnits`). The open
    Q is resolved with a real lesson (below): phase-start seams fire too early on a prep
    chapter's turn 1.
  - Guarded in `check.py check_engine_guards_present`; decision in `decisions.md`
    ("Lord floor, runtime mechanism").
  - **Verified:** `tools/playtest/run.sh lordfloor` (new scenario) — marty +7HP/+4Def at Ch1
    **turn 1**, stable across 3 player phases (no double-apply). `ch01win` still PASSes.
- **`parity_reference` across Prologue–Ch8 (#48 item 1)** — commit `fe8cd06`. Per-chapter
  enemy-pressure bar; values follow each chapter's authored cadence base (ch01 → FE8 Ch1, not
  its Ch13a layout; others → `fe8_base_map`). ch04/ch05 both → FE8 Ch4 (its two halves). **ch08
  → FE8 Ch13 but flagged informational** (its objective is a scripted defeat, not a clearable
  gate) — confirm that's the intent when #48's extractor/CI is built.
- **Drive-by:** fixed `.gitignore` so `tools/playtest/states/` is actually ignored (the line
  had an inline comment, which git doesn't honor).

## Hook-point lesson (worth keeping)
A one-time stat change to the **chosen lord must apply at `EndPrepScreen`** (deployment
finalization), NOT at a player-phase-start seam. On a **prep chapter's turn 1**, the prep
"Fight!" path reaches the player phase *before* `BmMain_StartPhase` and *before* the cursor
reset run — and the lead isn't deployed/`GetUnitFromCharId`-findable until prep finalizes — so
a floor hooked at either seam silently lands a **phase late** (it worked turn 2, not turn 1).
Only the playtest caught this; `make`-green did not.

## Next — Phase 0 done; split into the two parallel instances (HANDOFF §protocol below)
- **Content track (instance A) 🔒** — author Ch2→Ch8 slices (#22–#28): brainstorm +
  `dialogue-pass` + wire + pass CI gates + ship. Plus enemy YAML #18, NPC stubs #17, art
  #19/#38/#39, `pinky.yaml`→`pcs/` (#45-4), recruit schedule (#45-5). **Owns** `build_campaign.py`
  `inject_*`/chapter section + most chapter-YAML fields.
- **Pipeline track (instance B) ⚡** — **#48** next items (run `writing-plans` now that the
  issue is approved → TDD the `vanilla_enemies` extractor + `enemy_pressure` metric + the
  per-chapter / campaign-curve reports). Then the playtest platform (I/O harness → fuzzer →
  LLM-player), then mechanics/flavor #11/#9/#8/#46. **Owns** the stat/engine-hook section of
  `build_campaign.py` (+ `difficulty.py`/`fe_combat.py`, pipeline-only) + `parity_reference`.
- **Parallel protocol:** worktree/branch per track; `build_campaign.py` is the one file both
  touch — keep edits in each track's section, **rebase often, small batches**. Each instance
  creates its own worktree at launch (none created yet — nothing to use them this session).
- Bird's-eye roadmap: **#49**.

> Backlog/todos live in **GitHub issues** (labelled), not this file. HANDOFF = live state + pointers.

## Builds / tools
`make difficulty CH=chNN --lord-floor` (per-lord floor table) · `make difficulty CH=chNN`
(parity report) · `make test` (60 unit tests) · `make check` (drift guard, incl. tests). ROM:
`tools/build.sh test` (lean) · `tools/build.sh dist` (with #43 montage). NEVER a bare `make`
for a shippable ROM — strips the montage. Floor playtest: `tools/playtest/run.sh lordfloor`.

## Gotchas (operational)
- **New decomp patch target → add it to `PATCHED_DECOMP_FILES`** (build_campaign.py) or the
  build is non-idempotent: `restore_vanilla_sources` won't reset it, so the *second* inject
  sees the already-patched file and the `count == 1` guard aborts. (Bit `bm.c` this session.)
- **Engine stat changes to the chosen lord go in `EndPrepScreen`, not a phase-start seam** —
  see the hook-point lesson above. `make`-green can't prove apply timing; playtest it.
- **Vanilla decomp reads go through `build_campaign.vanilla_decomp_text()` (HEAD), never the
  working tree** — the build overwrites donor slots + reskins classes (`difficulty._characters_text`
  / `_classes_text` already do this, so `lord_floor_rows` is hermetic mid-build).
- The difficulty engine is a **static proxy** (no positioning/turns/AI) — `tools/playtest/` is
  the dynamic arbiter (it caught the floor timing bug).
- **Never commit the `fireemblem8u` submodule pointer** (build artifact); stage repo files
  explicitly.
- Background `run.sh` needs an explicit `cd`/absolute path; `PT_FPS=240 tools/playtest/run.sh
  <scen>` for fast captures. Built ROM at `fireemblem8u/fireemblem8.gba`. Nicolas can't see
  inline renders — save to `map-review/` + `open`.
- Story text → `make` regenerates bodies; gate with `python3 tools/verify_text.py` after text changes.

## Standing rules
Combat = pure vanilla FE; field parity with vanilla ch N is doctrine. **Process:** superpowers
workflow (brainstorm → spec → TDD → verify → review) layered on this repo's knowledge
architecture; spec = `decisions.md` ADR + GitHub issue (NOT `docs/superpowers/specs/`). Custom
art where it matters, **show before committing**; 2-3 options, Nicolas drives. **Project
knowledge lives in the repo** (decisions.md / YAML / issues), NOT private memory. Auto-push to
main once green; never commit the submodule pointer.
