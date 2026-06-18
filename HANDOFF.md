# Handoff — Manchego Stars · live state + pointers (backlog lives in GitHub issues, not here)

**Date:** 2026-06-18 (session 15)
**Session focus:** Built the **difficulty engine** (#45 item 1) on a tested combat core, then landed
**donor-base inheritance in the build** (#45 item 2) so the ROM cast actually reaches vanilla Ch1
parity — `make` green, ROM rebuilt. Two commits: `6a40cb4` (engine), then this one (item 2 + a
hermetic-read fix that corrects several units the engine had misread).

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
- **Tests gated:** `make test` + `check.py`/CI/pre-commit run all `tools/test_*.py` (45 total).
- **Retired the old one-off `balance_report.py`** (superseded by `difficulty.py`/`fe_combat.py`).

### Corrected Ch1 parity (the alpha-feedback chapter)
Best-4 field at vanilla parity: throughput **4.00 vs 3.74**, durability(min) **2.8 = 2.8** (exact),
**rootis one-rounds the lv4 armor boss with magic** (def→res). **Every lord choice is viable**
(sweep thru 3.74–4.00). Wolfram is a proper **tank** (HP25/Def9, dura 5.9 — the earlier "frail
Wolfram" was the dirty-tree artifact). The real glass units are the **shamans (dura 2.6)** — exactly
the per-lord survivability floor's target (#45 item 3).

## Next (all in #45, in checklist order)
1. **Item 3** — per-lord HP/Def floor: build-generated per-lord delta table + an engine hook applying
   the chosen lord's delta at chapter start (keyed on the lord-select flag). **One-time** (fades).
   Target ~5-hits-to-down: ~0 for tanks (Wolfram/Braulo), +7/+4 for the glass shamans.
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
