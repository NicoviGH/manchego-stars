# Handoff — Manchego Stars · live state + pointers (backlog lives in GitHub issues, not here)

**Date:** 2026-06-18 (session 14)
**Session focus:** Designed and **decided** the Ch1+ difficulty model with Nicolas, and moved
work-tracking onto GitHub issues (it had been drifting in this file). Design/planning + docs only —
no code changed; `make` unaffected.

## This session
- **Ch1+ difficulty model — DECIDED.** Donor personal lines + a per-lord survivability floor +
  roster-growth-to-match-vanilla; **no enemy or stat inflation**. Recorded in `docs/decisions.md`
  → "Party-side parity". Cast lands at vanilla parity on durability *and* kills/round
  (`tools/balance_report.py`).
- **Both design dials resolved:** lord floor is **one-time (fades)**; shamans split growths toward
  their promotions — **Marty = Knoll → Druid**, **Meesmickle = Ewan → Summoner** (both keep Ewan's
  Ch1-appropriate bases).
- **Growth model verified in the decomp:** player level-ups roll *character* growths only
  (`bmbattle.c:1278`); class growths are autolevel-only (`bmunit.c:792`) — so a unit grows exactly
  like its `STAT_DONOR`.
- **Issues created:** **#45** (difficulty model + per-chapter *difficulty engine* — the execution
  plan + checklist), **#46** (lord-select UX — recovered alpha-feedback item #4: explain the choice
  + show candidates), **#47** (alpha playtest feedback tracker — the friends' 6-item list, durable).
- **Convention recorded:** backlog/todos → GitHub issues, not HANDOFF (memory
  `feedback_github_issues_as_backlog`); retired the stale Ch1-difficulty memory; deleted the
  redundant `docs/difficulty-model.md` (folded into #45 + decisions.md).

## Where things stand
Difficulty is fully designed and tracked in **#45**; nothing is in flight code-wise (implementation
not started). `tools/balance_report.py` holds the Ch1 analysis the engine will generalize.

> Backlog/todos live in **GitHub issues** (labelled, e.g. `balance`/M3), not this file. HANDOFF =
> live state + pointers. (Tracking work *here* is what makes it go stale — Nicolas, 2026-06-18.)

## Next (all in the tracker)
1. **#45**, in checklist order: difficulty engine → donor-base inheritance (`build_campaign.py`,
   mirror the existing growths/ranks path) → lord-floor hook → `pinky.yaml`→`pcs/` → recruit schedule.
2. **#46** — lord-select UX (needs Nicolas's UI direction first).
3. Broader backlog → GitHub issues (chapters #20–#28, art #38/#39, etc.).

## Already resolved (no action)
- **#44 "rescued cast sprite renders BLACK" — closed, not-a-bug.** It's Meesmickle (a black cat by
  design); the session-12 `mu.c:856` root cause is dead code. Cast verified rendering correctly.
  Full record: closed issue #44.
- **Playtest tooling:** `recordtrade` + action-menu/target-select shots in `recordrescue`
  (`harness.lua`, `run.sh`; on main).

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
repo** (decisions.md / YAML / lore / issues), NOT private memory. **Backlog/todos → GitHub issues,
not HANDOFF.** Auto-push to main once green; never commit the `fireemblem8u` submodule pointer.
