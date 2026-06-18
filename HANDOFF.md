# Handoff — Manchego Stars · live state + pointers (backlog lives in GitHub issues, not here)

**Date:** 2026-06-18 (session 15)
**Session focus:** Built the **difficulty engine** (#45 item 1) — the static per-chapter parity
arbiter — on a tested combat core, and laid the shared stat primitive item 2 will consume. The
engine modeling **confirms donor-base inheritance reaches vanilla Ch1 parity**. `make` ROM output
unchanged (the new primitives aren't wired into the build path yet — that's item 2).

## This session (shipped)
- **`tools/fe_combat.py`** — the FE8 combat math (AS, doubling, triangle, hit, damage incl.
  magic-vs-Res + effective ×3, RTK, **kills/round capped 1.0/unit**) as ONE tested source of truth
  (the decomp's own formulas). 31 tests, incl. a canonical Eirika-one-rounds-the-Ch1-boss oracle.
- **`tools/difficulty.py`** — per-chapter analyzer: `make difficulty CH=ch01` (or
  `python3 tools/difficulty.py --chapter ch01`). Resolves cast effective stats (class base + donor
  personal line), parses chapter `enemy_units`, reports durability / throughput / carry /
  **lord×team sweep** / **vanilla-delta**. 11 tests (pure metrics + I/O vs real Ch1 data).
- **`tools/build_campaign.py`** — added `donor_base_stats()` + `BASE_DONOR` map (shamans→Ewan
  bases), the shared primitive item 2 uses. 3 tests. **Not yet called by `patch_character_data`.**
- **Tests gated:** `make test` + `check.py`/CI/pre-commit now run all `tools/test_*.py` (45 total).
- **Retired the old one-off `balance_report.py`** — superseded by `difficulty.py`; its untested
  duplicate of the combat math is gone (now `fe_combat.py`). decisions.md refs updated.

### What the engine says about Ch1 (the alpha-feedback chapter)
With donor bases modeled, our **best-4 field is at vanilla parity**: throughput **3.94 vs 3.74**,
durability(min) **2.6 vs 2.8**, and **rootis one-rounds the lv4 armor boss with magic** (def→res).
The **Spd-0 cliff still shows on Wolfram (dura 1.8) and Pinky (1.4)** — exactly the glass lords the
per-lord survivability floor (#45 item 3) is designed to lift. Sweep: every lord choice is viable.

## Next (all in #45, in checklist order)
1. **Item 2 — donor-base inheritance in the BUILD.** Wire `patch_character_data` to add
   `donor_base_stats(BASE_DONOR[uid])` into the personal layer (currently sets `fe_stats − class_base`
   = 0). Makes the ROM cast match what the engine models. **Then `make` green + re-run
   `make difficulty CH=ch01` to confirm ROM parity.** Sub-item (Part B): shaman growth split — Mees's
   growth/rank donor KNOLL→EWAN (NB: check Ewan vs Knoll `baseRanks` keeps Dark rank so the flux tome
   still equips); Marty stays Knoll growths. Bases already correct via `BASE_DONOR`.
2. **Item 3** — per-lord HP/Def floor (build-generated delta table + engine hook).
3. **Item 4** — `pinky.yaml` → `pcs/`. **Item 5** — recruit schedule (#17).
4. **#46** lord-select UX (needs Nicolas's UI direction). **#47** alpha-feedback tracker.

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
  (`tools/playtest/`) is the dynamic arbiter. It models the donor-base DESIGN; item 2 makes it real.

## Standing rules
Combat = pure vanilla FE; field parity with vanilla ch N is doctrine. Custom art where it matters,
**show before committing**; bring 2-3 options, let Nicolas drive. **Project knowledge lives in the
repo** (decisions.md / YAML / lore / issues), NOT private memory. **Backlog/todos → GitHub issues,
not HANDOFF.** Auto-push to main once green; never commit the `fireemblem8u` submodule pointer.
