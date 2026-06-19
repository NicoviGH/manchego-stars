# Handoff — Pipeline track ⚡ live state

Per-track live state for the **pipeline lane** (difficulty/parity engine, playtest, CI — the CD machine
agents accelerate). Worktree doctrine, ownership map, and trunk rules → `CLAUDE.md` §Tracks (read first;
the lane guard is `check.py check_lane_ownership`). Seam enforcement (#55) + parallel-work model →
`docs/decisions.md` §Seam enforcement / §Delivery model. Backlog → GitHub issues (#49 ② Pipeline).
**Shared builds/gotchas/rules → `HANDOFF.md` + `CLAUDE.md`; this file holds only my current state +
pipeline-lane-specific gotchas.** Don't touch `HANDOFF-content.md`.

## Now (2026-06-19) — parity engine live; playtest smoke net underway (liveness brick landed)
- **#49 playtest platform started — smoke liveness net** (decisions.md §Playtest platform first brick). The
  pure stability classifier `tools/playtest/liveness.lua` + `test_liveness.lua` (6 asserts) **landed TDD,
  green in `make test`** (gated on `lua`; `brew install lua` done on this box). Design: a generic driver boots
  any reachable chapter, idles all units + ends each turn, asserts a clean terminal with no crash/soft-lock —
  PASS / FAIL / INCONCLUSIVE. **Next two bricks:** extract `io_core.lua` (lift harness.lua's primitives, no
  behavior change — verify by re-running `win`/`ch01win`/`gameover`/`retreat`), then `smoke.lua` + a
  `run.sh smoke <prologue|ch01>` runner (integration-verify on a built ROM). Then fuzzer / LLM-player.
- **#48 parity engine + informative CI curve** are live: `make difficulty` runs the campaign curve in CI
  (always exits 0) so balance spikes / parity regressions surface on every PR. Ch1 validates at parity.
- **Hard gate built but unwired** (#48 (b)): `make difficulty-gate` (`difficulty.py --curve --check`) exits
  non-zero on any chapter that claims a `parity_reference` and is off-parity, or has a dropped boss
  (no-ref chapters never gate). **The flip is one word in CI** (`difficulty` → `difficulty-gate`) once
  content authors Ch2+ enemy inventories — RED-by-design today (our side `0.0` / `!!boss dropped`).
- **#53 monster/extended weapons** landed: 9 vanilla-only weapons in `fe_combat.W` (monster claws,
  evil-eye, thunder/iron-blade/venin-axe/halberd/horseslayer), mapped via difficulty-local
  `VANILLA_ONLY_ITEM_TO_WEAPON` (merged into `ITEM_TO_WEAPON`) — **not** content's `WEAPON_ITEM_ENUM`.
- **Parity registry** covers Prologue, Ch1, Ch2, Ch3, Ch5, plus FE8 Ch4 (all-monster → our ch04/ch05) and
  Ch6 (→ our ch07). FE8 Ch13 (→ our ch08) is the lone deferred reference.

## Next (priority order)
1. **Playtest smoke net — continue** (#49, IN PROGRESS; see "Now"): `io_core.lua` extraction → `smoke.lua`
   driver + `run.sh smoke` runner. Then the stability fuzzer (randomized/seeded inputs) and the LLM-player.
   ch02+ reachability needs per-chapter save-state checkpoints (reuse `states/` infra), deferred till those
   chapters exist; Prologue + Ch01 are reachable from New Game now.
2. **#53 tail — FE8 Ch13 reference** (→ our ch08, deferred/optional): bigger than billed — needs ~11 *standard*
   weapons modeled (silver/steel/killer/slim/short-spear/elfire/zanbato/swordslayer/purge), not a few exotics.
   ch08 is a scripted-defeat objective (never CI-gated), so it's informational polish; do it only if idle.
3. **Flip the CI parity gate to enforcing** (#48 (b)): once content authors the Ch2+ enemy inventories,
   change the CI step's `difficulty` → `difficulty-gate`. Leveled stat projection (#45 item 5) pairs here.
4. Mechanics/flavor leaves once specced: lord-select UX #46, d20 crit #11, spell-economy #9, iconic
   matchups #8. Injection pipeline #14 / maps #40 gate content.

## Watch out (pipeline-lane only)
- **Vanilla-only weapons (monster/exotic) belong in `difficulty.py`, not `WEAPON_ITEM_ENUM`** — that map is
  content-owned; keep it to weapons our cast actually uses, and derive `ITEM_TO_WEAPON` from it + the
  difficulty-local vanilla-only extension.
- **Curation gotcha (#48):** an `events_udefs.c` array a chapter eventscript references may be a *cutscene*
  array (endgame villains placed with empty `.items`). Filter to arrays whose RED units **carry weapons** —
  that excludes both cutscene arrays and unreferenced skirmish/tower data.
- `vanilla_decomp_text()` strips inherited git env (`dcbb247`): `git -C fireemblem8u show HEAD:…` was exiting
  128 under the pre-commit hook in a worktree (git exports `GIT_DIR`, which overrode `-C` discovery). If a
  worktree commit fails on a submodule read, that's the class of bug — don't reach for `--no-verify`.
