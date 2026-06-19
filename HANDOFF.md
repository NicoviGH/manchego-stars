# Handoff — Manchego Stars · live state + pointers (backlog lives in GitHub issues, not here)

**Date:** 2026-06-18 (session 15)
**Session focus:** #45 items 1–3a. Built the **difficulty engine** (item 1) on a tested combat core,
landed **donor-base inheritance in the build** (item 2, + a hermetic-read fix), then built the
**per-lord survivability-floor solver** (item 3a) and decided its design with Nicolas (target locked
**3.5**). `make` green, ROM rebuilt. Three commits: `6a40cb4` (engine), `f380696` (donor-base +
hermetic fix), `7bb3efc` (floor solver). **Item 3 engine wiring (3b+3c) is the pickup — see Next.**

## This session (shipped)
- **`tools/fe_combat.py`** — the FE8 combat math (AS, doubling, triangle, hit, damage incl.
  magic-vs-Res + effective ×3, RTK, **kills/round capped 1.0/unit**) as ONE tested source of truth
  (the decomp's own formulas). 31 tests, incl. a canonical Eirika-one-rounds-the-Ch1-boss oracle.
- **`tools/difficulty.py`** — per-chapter analyzer: `make difficulty CH=ch01`. Resolves cast
  effective stats (class base + donor line), parses chapter `enemy_units`, reports durability /
  throughput / carry / **lord×team sweep** / **vanilla-delta**. 11 tests.
- **`tools/build_campaign.py` (item 2 — the build change):** `patch_character_data` now injects each
  cast slot's **donor personal bases** (`BASE_DONOR`; shamans→Ewan) via the tested
  `personal_base_deltas()`. Shaman growth split: `GROWTH_DONOR` (Mees grows on Ewan→Summoner, Marty
  on Knoll→Druid) while **ranks stay on Knoll** (`STAT_DONOR`) so both keep ITYPE_DARK and the flux
  tome equips (Ewan is Anima-only — switching the rank donor would have broken it). 8 tests.
- **Hermetic-read fix (correctness):** donor/class stats are now read from the **committed (HEAD)**
  decomp via `vanilla_decomp_text()`, not the build-mutated working tree. Four donors
  (Gilliam/Neimi/Moulder/Vanessa) ride portrait slots the build overwrites, so working-tree reads
  showed them *naked* — which had made the engine (and `6a40cb4`'s oracles) understate
  Wolfram/Pinky/sclorbo/prof-rbg. Oracles corrected; tests now pass clean-tree AND dirty-tree.
- **Lord-floor solver (item 3a):** `difficulty.py --lord-floor [--target/--def-cap/--res-cap/--hp-cap]`
  — `bulk_durability()` (worst-case, dodge ignored) + `lord_floor_delta()` (cheapest HP/Def/Res to a
  target; Res vs magic threats, Def vs physical; never Spd/Lck; `reached=False` flags effective-weapon
  cases stats can't fix). Defaults (target 3.5, caps 4/4/12) reproduce the hand-set +7/+4. 8 tests.
- **Tests gated:** `make test` + `check.py`/CI/pre-commit run all `tools/test_*.py` (58 total).
- **Retired the old one-off `balance_report.py`** (superseded by `difficulty.py`/`fe_combat.py`).

### Corrected Ch1 parity (the alpha-feedback chapter)
Best-4 field at vanilla parity: throughput **4.00 vs 3.74**, durability(min) **2.8 = 2.8** (exact),
**rootis one-rounds the lv4 armor boss with magic** (def→res). **Every lord choice is viable**
(sweep thru 3.74–4.00). Wolfram is a proper **tank** (HP25/Def9, dura 5.9 — the earlier "frail
Wolfram" was the dirty-tree artifact). The real glass units are the **shamans (dura 2.6)** — exactly
the per-lord survivability floor's target (#45 item 3).

## Next (all in #45, in checklist order)
1. **Item 3 — per-lord survivability floor.** Analysis tool BUILT: `difficulty.py --lord-floor`
   (`--target/--def-cap/--res-cap/--hp-cap`) emits the per-lord delta table. Design decided with
   Nicolas: **survival-only stats HP/Def/Res** (never Spd/Lck — they add offense/dodge); **Res** in
   the model (threat-driven: armor-vs-magic gets Res, not inert Def); metric = **bulk durability**
   (worst-case rounds-to-down, hits assumed to connect — a must-survive lord shouldn't lean on dodge
   RNG); target **~3.5** from "survive a chokepoint gang-up + a reaction turn", bounded below the
   natural tanks. Defaults reproduce the hand-set **+7/+4** on shamans; Braulo/Wolfram → 0.
   **Target LOCKED at 3.5** (Nicolas, this session). Remaining = the engine wiring (do 3b+3c
   together; emitting 3b without 3c is dead data):
   - **3b (build-time table, low-risk):** emit `gLordFloorDeltas[]` right after the
     `gLordSelectCandidates[]` emission (`build_campaign.py` ~L3514, in `events_udefs.c`), one row
     per candidate (same menu order) = `difficulty.lord_floor_delta(...)` @target 3.5 vs Ch1 enemies
     (use `difficulty.load_field(campaign,'ch01')`; **local-import difficulty inside the fn** —
     difficulty imports build_campaign, so avoid the top-level cycle). Verify generated rows vs the
     (unit-tested) solver; Ch1 → marty/mees +7HP/+4Def, tanks 0.
   - **3c (engine hook, careful):** campaign-agnostic C, mirror `_inject_lord_select_engine`'s
     string-replace+guard idiom. At chapter start, gated by a permanent "applied" flag (grab a free
     one near `LORDSEL_FLAG_BASE=0xF0`), find the chosen lord via `LordSelect_GetPid()` (already in
     eventinfo.c), look up its `gLordFloorDeltas` row, add to `unit->maxHP`/`curHP`/`def`/`res`
     (Unit fields confirmed in `include/bmunit.h`). Apply-ONCE so it bakes into the saved unit and
     **fades as it levels**. Register the new guard in `tools/check.py check_engine_guards_present`.
   - **3c MUST be PLAYTEST-verified** (`tools/playtest/`): build-green won't prove the bump persists
     across the Ch1→Ch2 transition / doesn't double-apply. Pick a frail lord (e.g. marty), confirm
     +7HP at Ch1 start and that it carries into Ch2. Open question to resolve first: the exact
     chapter-init hook point that runs once after units load (the cursor guard hooks
     `GetPlayerStartCursorPosition`, turn-1 — semantically wrong for stats; find the proper init fn).
2. **Item 4** — `pinky.yaml` → `pcs/` (he's the 8th PC + a lord candidate). **Item 5** — recruit
   schedule to match vanilla cadence (#17).
3. **#46** lord-select UX (needs Nicolas's UI direction). **#47** alpha-feedback tracker.

> Backlog/todos live in **GitHub issues** (labelled), not this file. HANDOFF = live state + pointers.

## Builds / tools
`make difficulty CH=chNN` (static parity report) · `make test` (45 unit tests) · `make check`
(drift guard, now incl. tests). ROM: `tools/build.sh test` (lean) · `tools/build.sh dist` (with #43
montage). NEVER a bare `make` for a shippable ROM — it strips the montage.

## Gotchas (operational)
- Background `run.sh` calls need an explicit `cd`/absolute path (shell cwd resets between tool calls).
- `record*` defaults to 60fps+videoSync; `PT_FPS=240 tools/playtest/run.sh <scen>` for fast captures.
  Built ROM at `fireemblem8u/fireemblem8.gba`. Nicolas can't see inline renders — save to
  `map-review/` and `open`.
- **Never commit the `fireemblem8u` submodule pointer** (build artifact); stage repo files explicitly.
- Story text → `make` regenerates bodies; gate with `python3 tools/verify_text.py` after text changes.
- The difficulty engine is a **static proxy** (no positioning/turns/AI) — the playtest harness
  (`tools/playtest/`) is the dynamic arbiter.
- **Vanilla decomp reads go through `build_campaign.vanilla_decomp_text()` (HEAD), never the working
  tree** — the build overwrites donor portrait slots (Gilliam/Neimi/Moulder/Vanessa) + reskins
  classes, so a working-tree read of donor/class stats can be silently wrong (this bit the engine).

## Standing rules
Combat = pure vanilla FE; field parity with vanilla ch N is doctrine. Custom art where it matters,
**show before committing**; bring 2-3 options, let Nicolas drive. **Project knowledge lives in the
repo** (decisions.md / YAML / lore / issues), NOT private memory. **Backlog/todos → GitHub issues,
not HANDOFF.** Auto-push to main once green; never commit the `fireemblem8u` submodule pointer.
