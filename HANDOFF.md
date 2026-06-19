# Handoff — Manchego Stars · live state + pointers (backlog lives in GitHub issues, not here)

**Date:** 2026-06-19 (session 16)
**Session focus:** Finished the #45 difficulty work through **item 3a** (the per-lord floor *solver*),
then ran a **full planning session** with Nicolas: decomposed the road to ship into streams, locked a
**delivery model** (vertical-slice CD pipeline), and specced the first pipeline sub-project (#48).
Pickup is sequenced for **parallel two-instance work** (content track ‖ pipeline track) — see Next.

## Shipped this session
- **Balance engine (#45 items 1–3a)** — commits `6a40cb4` / `f380696` / `7bb3efc`:
  - `tools/fe_combat.py` — FE8 combat math, ONE tested source of truth (31 tests; canonical
    Eirika-one-rounds-the-Ch1-boss oracle).
  - `tools/difficulty.py` — `make difficulty CH=ch01` (durability / throughput / carry / lord×team
    sweep / vanilla-delta) + `--lord-floor` solver (item 3a: `bulk_durability` + `lord_floor_delta`,
    HP/Def/Res only, Res-vs-magic, target 3.5 reproduces the hand-set +7/+4).
  - `build_campaign.py` — donor-base inheritance (item 2: `BASE_DONOR` / `GROWTH_DONOR` /
    `personal_base_deltas`; shaman split keeps Knoll's Dark rank) + the **hermetic-read fix**
    (`vanilla_decomp_text` — read donors from HEAD, not the build-mutated tree).
  - 58 tests gated in `check.py`. Retired `balance_report.py`.
  - **Ch1 verdict:** cast at vanilla parity (best-4 thru 4.00 vs 3.74, dura 2.8 = 2.8, rootis
    one-rounds the armor boss via magic); every lord viable; shamans are the glass picks (dura 2.6)
    the floor targets. Wolfram is a tank (5.9) — "frail Wolfram" was the dirty-tree artifact.
- **Planning artifacts** — commit `f813654`:
  - `decisions.md` ADRs: **process hybrid** (superpowers layered on this repo's knowledge
    architecture; spec = ADR + issue, no `docs/superpowers/specs/`), **delivery model** (vertical
    slices through a CD pipeline; content track ‖ pipeline track), **enemy-pressure parity**.
  - **#48** — static-engine→all-chapters spec (awaiting Nicolas's review). **#49** — roadmap epic
    (streams + dependency spine).

## Next — pickup is sequenced for parallel work

**Phase 0 — do these in ONE session on `main` before launching the two instances** (they clear the
shared-file collisions so two Claudes don't stomp each other):

1. **Finish #45 3b + 3c (the floor wiring).** It's in-flight, the most `build_campaign.py`-invasive
   pipeline change, and needs playtest — land it on `main` first so both tracks start from a clean base.
   - **3b (build table):** emit `gLordFloorDeltas[]` right after the `gLordSelectCandidates[]`
     emission (`build_campaign.py` ~L3514, `events_udefs.c`), one row per candidate (menu order) =
     `difficulty.lord_floor_delta(...)` @target 3.5 vs Ch1 enemies (`difficulty.load_field(campaign,
     'ch01')`; **local-import difficulty inside the fn** — avoid the import cycle). Ch1 → marty/mees
     +7HP/+4Def, tanks 0.
   - **3c (engine hook):** campaign-agnostic C, mirror `_inject_lord_select_engine`'s
     string-replace + guard idiom. At chapter start, gated by a permanent "applied" flag (free one
     near `LORDSEL_FLAG_BASE=0xF0`), find the chosen lord via `LordSelect_GetPid()`, add its
     `gLordFloorDeltas` row to `unit->maxHP`/`curHP`/`def`/`res`. Apply-ONCE → bakes into the saved
     unit, fades as it levels. Register the guard in `check.py check_engine_guards_present`.
     **Open Q to resolve first:** the chapter-init hook point that runs once after units load (the
     cursor guard hooks `GetPlayerStartCursorPosition` turn-1 — semantically wrong for stats).
   - **3c MUST be playtest-verified** (`tools/playtest/`): pick a frail lord (marty), confirm +7 HP at
     Ch1 start and that it carries into Ch2 (no double-apply). `make`-green won't prove persist.
     *(This is also the first brick of the pipeline track's I/O harness.)*

2. **Set up the parallel protocol.** A git worktree/branch per track + ownership of the shared seams:
   - `build_campaign.py` — content owns the `inject_*`/chapter section; pipeline owns the
     stat/engine-hook section (`difficulty.py`/`fe_combat.py` are pipeline-only).
   - chapter YAMLs — content owns most fields; pipeline owns `parity_reference`. **Land
     `parity_reference` across all authored chapter YAMLs in one early commit** (de-conflicts; it's
     #48's first checklist item).
   - Rebase often; small batches.

**Then split into two parallel instances:**
- **Content track (instance A) 🔒** — author Ch2→Ch8 slices (#22–#28): each via brainstorm +
  `dialogue-pass` + wire + pass the CI gates + ship to friends. Plus enemy YAML #18, NPC stubs #17,
  art #19/#38/#39, `pinky.yaml`→`pcs/` (#45-4), recruit schedule (#45-5).
- **Pipeline track (instance B) ⚡** — **#48** first (run `writing-plans` once Nicolas OKs the issue →
  TDD), then the playtest platform (I/O harness → stability fuzzer → LLM-player), then mechanics/flavor
  #11/#9/#8/#46.
- Bird's-eye roadmap: **#49**. The one file both tracks touch is `build_campaign.py` — keep edits in
  each track's section + rebase often.

> Backlog/todos live in **GitHub issues** (labelled), not this file. HANDOFF = live state + pointers.

## Builds / tools
`make difficulty CH=chNN` (per-chapter parity) · `make difficulty` (campaign curve — after #48) ·
`make test` (58 unit tests) · `make check` (drift guard, incl. tests). ROM: `tools/build.sh test`
(lean) · `tools/build.sh dist` (with #43 montage). NEVER a bare `make` for a shippable ROM — strips
the montage.

## Gotchas (operational)
- **Vanilla decomp reads go through `build_campaign.vanilla_decomp_text()` (HEAD), never the working
  tree** — the build overwrites donor portrait slots (Gilliam/Neimi/Moulder/Vanessa) + reskins classes,
  so a working-tree read of donor/class stats is silently wrong (bit the engine this session).
- The difficulty engine is a **static proxy** (no positioning/turns/AI) — `tools/playtest/` is the
  dynamic arbiter.
- **Never commit the `fireemblem8u` submodule pointer** (build artifact); stage repo files explicitly.
- **Parallel work:** `build_campaign.py` is the one file both tracks touch — keep edits localized +
  rebase often (Phase 0.2).
- Background `run.sh` needs an explicit `cd`/absolute path; `PT_FPS=240 tools/playtest/run.sh <scen>`
  for fast captures. Built ROM at `fireemblem8u/fireemblem8.gba`. Nicolas can't see inline renders —
  save to `map-review/` + `open`.
- Story text → `make` regenerates bodies; gate with `python3 tools/verify_text.py` after text changes.

## Standing rules
Combat = pure vanilla FE; field parity with vanilla ch N is doctrine. **Process:** superpowers workflow
(brainstorm → spec → TDD → verify → review) layered on this repo's knowledge architecture; spec =
`decisions.md` ADR + GitHub issue (NOT `docs/superpowers/specs/`). Custom art where it matters, **show
before committing**; 2-3 options, Nicolas drives. **Project knowledge lives in the repo** (decisions.md
/ YAML / issues), NOT private memory. Auto-push to main once green; never commit the submodule pointer.
