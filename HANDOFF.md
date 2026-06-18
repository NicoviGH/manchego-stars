# Handoff — Manchego Stars · live state + pointers (backlog lives in GitHub issues, not here)

**Date:** 2026-06-18 (session 14)
**Session focus:** Designed the Ch1+ difficulty model with Nicolas and **landed the decision** —
donor personal lines + a per-lord survivability floor + roster-growth-to-match-vanilla, no enemy or
stat inflation. Recorded in `docs/decisions.md` ("Party-side parity"); execution tracked in **#45**.
`make` unaffected (docs only this session).

## ✅ Ch1 difficulty — DECIDED · execution → #45
Settled: each PC inherits its `STAT_DONOR`'s personal **bases** (the build already inherits that
donor's growths+ranks) → cast at vanilla parity on durability *and* kills/round; the chosen lord
(#42) gets a runtime HP/Def top-up to a **~5-hits-to-down floor** (one-time, fades as the party
levels). Roster grows to match vanilla's recruit cadence. No enemy or stat inflation. Full
rationale: `docs/decisions.md` → "Party-side parity". Checklist (difficulty engine, donor-base
inheritance, lord floor, `pinky.yaml`→`pcs/`, recruit schedule) + open dials (anchor trajectory;
2nd-shaman donor) live in **#45**. Analysis tool: `python3 tools/balance_report.py`.

> Backlog/todos live in **GitHub issues** (labelled, e.g. `balance`/M3), not this file. HANDOFF =
> live state + pointers. (Tracking work *here* is what makes it go stale — Nicolas, 2026-06-18.)

## Already resolved (no action)
- **#44 "rescued cast sprite renders BLACK" — closed, not-a-bug.** It's Meesmickle (a black cat by
  design); the session-12 `mu.c:856 facing==STANDING → PutMuSMS` root cause is dead code (facing is
  never STANDING), so the "decided fix" was a no-op. Cast verified rendering correctly across the
  rescue lift, rescue menu, and trade menu. mu.c untouched. Full record: **closed issue #44**.
- **Playtest tooling shipped:** `recordtrade` scenario (trade-screen capture) + action-menu /
  target-select shots in `recordrescue` (`harness.lua`, `run.sh`; on main).

## Builds
`tools/build.sh test` (lean) · `tools/build.sh dist` (with #43 montage; stamps `dist/`). NEVER a
bare `make` for a shippable ROM — it strips the montage.

## Gotchas (operational)
- Background `run.sh` calls need an explicit `cd`/absolute path (shell cwd resets between tool calls).
- `record*` defaults to 60fps+videoSync; `PT_FPS=240 tools/playtest/run.sh <scen>` for fast
  static/menu captures. Built ROM at `fireemblem8u/fireemblem8.gba`. Nicolas can't see inline
  renders — save to `map-review/` and `open`.
- **Never commit the `fireemblem8u` submodule pointer** (build artifact); stage repo files explicitly.
- Story text → `make` regenerates bodies; gate with `python3 tools/verify_text.py` after text changes.

## Standing rules
Combat = pure vanilla FE; field parity with vanilla ch N is doctrine. Custom art where it matters,
**show before committing**; bring 2-3 options, let Nicolas drive. **Project knowledge lives in the
repo** (decisions.md / YAML / lore / issues), NOT private memory. Auto-push to main once green; never
commit the `fireemblem8u` submodule pointer.
