# Handoff — Pipeline track ⚡ live state

Per-track live state for the **pipeline lane** (difficulty/parity engine, playtest, CI — the CD machine
agents accelerate). Worktree doctrine, ownership map, and trunk rules → `CLAUDE.md` §Tracks (read first;
the lane guard is `check.py check_lane_ownership`). Seam enforcement (#55) + parallel-work model →
`docs/decisions.md` §Seam enforcement / §Delivery model. Backlog → GitHub issues (#49 ② Pipeline).
**Shared builds/gotchas/rules → `HANDOFF.md` + `CLAUDE.md`; this file holds only my current state +
pipeline-lane-specific gotchas.** Don't touch `HANDOFF-content.md`.

## Now (2026-06-19) — parity engine live; playtest smoke net + clear-bot + seeded fuzzer
- **CI fixed + `make test` gated in CI.** The `checks` job had been RED since ~23:15 2026-06-19:
  `check.py` runs the Python unit tests, two of which read the `fireemblem8u` decomp
  (`vanilla_decomp_text` → `git -C fireemblem8u show HEAD:…`) and import `build_campaign`
  (→ PIL/numpy) — but the lightweight `checks` job has neither those deps nor the submodule
  (2.3GB, deliberately omitted). Fix, two parts: (1) `check_tests_pass` now **self-skips when the
  submodule isn't checked out**, keeping the drift guard decoupled from the heavy checkout (local
  pre-commit still runs the full suite); (2) **`make test` now runs in the `build` job** — the only
  CI job with the submodule + numpy/pillow — plus `lua5.4`, so the pure-Lua playtest tests
  (`test_liveness`/`test_clearbot`/`test_fuzzrng`) are gated too. Resolves old Next #2.
- **#49 stability fuzzer LANDED & verified — seeded "smart monkey"** (decisions.md §Playtest platform brick
  3). Random inputs over the same I/O layer to hunt crashes/soft-locks the directed bots miss. Own LCG PRNG
  (`fuzzrng.lua`, NOT host `math.random` — so a `PT_SEED=N` crash replays identically on the CI `lua` and
  mGBA's Lua); PRNG + weighted policy TDD'd (`test_fuzzrng.lua`, 9 asserts, in `make test`). Broad in-chapter
  key surface (incl START/SELECT) + a **B-mash unstick watchdog**: liveness gained a shorter `nudge_frames`
  stall → `NUDGE` → driver mashes B (TDD'd, `test_liveness.lua` now 10 asserts). Two false positives fixed in
  the *driver* (liveness stayed pure): off-map title-screen (drive menus forward via `liveOnMap`, not
  `inChapter`) and cursor-roam (feed a **responsiveness** fingerprint, `fuzzFingerprint` folds the cursor into
  `procfp` — "no change" = game stopped *responding*, not "bot made no progress"). Scenarios `fuzz` /
  `fuzz_ch01`; `PT_SEED=N run.sh fuzz`. Verified: 5 seeds clean on the prologue (1 win, 4 budget-survival).
  **Next:** the LLM-player (swap the rule-based policy); ch02+ coverage needs per-chapter save-state checkpoints.
- **#60 greedy clear-bot LANDED & verified — clears prologue AND ch01** (decisions.md §Playtest platform
  brick 2). One generic `clearDrive` loop PLAYS a chapter with real combat (no `pokeFrail`): march/attack
  toward the boss, then if not already won, **Seize** the boss's old tile. Won both the prologue (DefeatBoss)
  and **ch01 (Seize, real combat through 10 goblins)** in 3 turns each, no game-over. Generic boss detection
  via `CA_BOSS` (CharacterData attrs `+0x28`, `1<<15`) — no hardcoded ids (finds Sephek `0x68`, chief `0x46`).
  Pure target core `clearbot.lua` `pickTarget`, TDD'd (`test_clearbot.lua`, 9 asserts, `make test`).
  Scenarios: `clear` / `clear_ch01` / `clearprobe`. **Next:** stability fuzzer; ch02+ needs checkpoints.
- **#49 smoke liveness net LANDED & verified** (decisions.md §Playtest platform first brick). Pure classifier
  `liveness.lua` + `test_liveness.lua` (6 asserts, TDD, in `make test`; needs `lua` — `brew install lua`).
  Driver is a `harness.lua` scenario (`smokeDrive` + `scenarios.smoke` / `scenarios.smoke_ch01`) reusing
  in-scope primitives (no `io_core` extraction — one file = single source of truth; YAGNI). `reachCh01Map`
  factored out of `scenarios.ch01` (shared lead-in, no dup). **2 outcomes:** PASS = no crash/soft-lock over
  the run (clean terminal OR survived the 30-turn budget); FAIL = soft-lock/crash. Verified on a built ROM:
  `run.sh smoke` + `run.sh smoke_ch01` both PASS (idle party survives 30 turns on both — completability is
  the clear-bot's job); `ch01`/`win` unregressed. ch02+ needs save-state checkpoints (deferred).
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
1. **LLM-player** (#49, next platform brick — fuzzer now landed): swap the clear-bot's rule-based policy for
   an LLM, with the **graduation benchmark: play vanilla FE8** (#49 comment, Nicolas). The clear-bot already
   clears prologue + ch01 (DefeatBoss + Seize) with real combat; harder chapters may still need gang-up /
   don't-feed-the-lord / heal logic. The fuzzer (`fuzz`/`fuzz_ch01`) now soaks for crashes/soft-locks on the
   prologue; **fuzz_ch02+ smoke/clear coverage needs per-chapter save-state checkpoints** (reuse `states/`
   infra), deferred till those chapters are built. Seed-sweep DONE: `tools/playtest/fuzz_sweep.sh [N]` (or
   `PT_SEEDS="…"`) soaks many seeds and fails on any — a **LOCAL pre-release gate, NOT CI** (CI builds a mock
   ROM + has no mGBA, so it can't run any in-emulator scenario; see checks.yml). `fuzz_boot` (New
   Game→title→prep) is NOT a quick follow-up after all — it needs a **non-cursor responsiveness signal**
   (`fuzzFingerprint` folds the *map* cursor, useless on menus), so treat it as its own small design piece.
2. **#53 tail — FE8 Ch13 reference** (→ our ch08, deferred/optional): bigger than billed — needs ~11 *standard*
   weapons modeled (silver/steel/killer/slim/short-spear/elfire/zanbato/swordslayer/purge), not a few exotics.
   ch08 is a scripted-defeat objective (never CI-gated), so it's informational polish; do it only if idle.
3. **Flip the CI parity gate to enforcing** (#48 (b)): once content authors the Ch2+ enemy inventories,
   change the CI step's `difficulty` → `difficulty-gate`. Leveled stat projection (#45 item 5) pairs here.
4. Mechanics/flavor leaves once specced: lord-select UX #46, d20 crit #11, spell-economy #9, iconic
   matchups #8. Injection pipeline #14 / maps #40 gate content.

## Watch out (pipeline-lane only)
- **CI unit tests run in the `build` job, not the lightweight `checks` job.** Two tests
  (`test_build_campaign`/`test_difficulty`) read the `fireemblem8u` decomp (`vanilla_decomp_text`) and
  import `build_campaign` (→ PIL/numpy); only the `build` job checks out the submodule + has those deps.
  `check_tests_pass` self-skips when the submodule is absent, so the `checks` job stays lightweight
  (`pyyaml` only). A new test/import needing a new lib → add it to the **`build`** job's deps, and the
  pre-commit hook (submodule present locally) is your fast local gate.
- **Running playtest scenarios needs a built ROM + `lua`.** Build via `tools/build.sh` (it applies the
  decomp's `#!/bin/python3`→`env python3` shebang fix); a bare `make` dies `Error 126` on the gfx tools on
  macOS. The pure Lua tests (`test_liveness.lua`/`test_clearbot.lua`) need `lua` (`brew install lua`); `make
  test` skips them with a notice when it's absent. Regenerate `symbols.lua` (`gen_symbols.py`, auto by run.sh)
  after a rebuild.
- **Vanilla-only weapons (monster/exotic) belong in `difficulty.py`, not `WEAPON_ITEM_ENUM`** — that map is
  content-owned; keep it to weapons our cast actually uses, and derive `ITEM_TO_WEAPON` from it + the
  difficulty-local vanilla-only extension.
- **Curation gotcha (#48):** an `events_udefs.c` array a chapter eventscript references may be a *cutscene*
  array (endgame villains placed with empty `.items`). Filter to arrays whose RED units **carry weapons** —
  that excludes both cutscene arrays and unreferenced skirmish/tower data.
- `vanilla_decomp_text()` strips inherited git env (`dcbb247`): `git -C fireemblem8u show HEAD:…` was exiting
  128 under the pre-commit hook in a worktree (git exports `GIT_DIR`, which overrode `-C` discovery). If a
  worktree commit fails on a submodule read, that's the class of bug — don't reach for `--no-verify`.
