# Handoff — Pipeline track ⚡ live state

Per-track live state for the **pipeline lane** (difficulty/parity engine, playtest, CI — the CD machine
agents accelerate). Worktree doctrine, ownership map, and trunk rules → `CLAUDE.md` §Tracks (read first;
the lane guard is `check.py check_lane_ownership`). Seam enforcement (#55) + parallel-work model →
`docs/decisions.md` §Seam enforcement / §Delivery model. Backlog → GitHub issues (#49 ② Pipeline).
**Shared builds/gotchas/rules → `HANDOFF.md` + `CLAUDE.md`; this file holds only my current state +
pipeline-lane-specific gotchas.** Don't touch `HANDOFF-content.md`.

## Now (2026-06-20) — save carry-forward shipped (#59 closed); LLM-player epic spec'd (#63); lord-select UX up next (#46)
- **#59 LANDED & CLOSED — testers carry their own `.sav` across builds; public patch rejected.**
  FE8 save validity = a **fixed** magic + a checksum (`bmsave-lib.c` `ReadGlobalSaveInfo`/`ReadSaveBlockInfo`),
  so a rebuild alone never invalidates a save — only a save-block *layout* shift does. We reskin within
  FE8's fixed slots and never touch the save structs or the dims that size `GameSaveBlock`
  (`BWL_ARRAY_NUM`/`WIN_ARRAY_NUM`), so an old `.sav` stays valid drop-to-drop → **no per-release starter
  save needed**. New guard **`check.py check_save_layout_stable`** pins those constants + the magics (TDD
  `tools/test_check_save_layout.py`); a red = the one drop that needs the starter-save fallback. Tester
  landing page: README "▶ Play it" + **`docs/playtesters.md`** (carry-save steps for Pizza Boy / Delta;
  in-game Save, not save-states). **Public `.bps` evaluated & REJECTED:** our decomp build is non-matching
  vs retail (~67% of bytes differ → an 11.4 MB "patch"), so distribution stays the **private pre-patched
  `.gba`** Nicolas links to friends. Pure-Python BPS encoder **`tools/make_bps.py`** (TDD, round-trips real
  16MB ROMs) kept for a future byte-matching build / inter-build deltas. ADRs: decisions.md §Distribution.
- **#63 LLM-player brainstormed → captured as a GitHub epic (NOT started).** Soak/balance tool, built
  policy-and-transport-first, vanilla-FE8 as the validation milestone. Locked architecture: **sidecar
  file-handshake** (mGBA Lua ↔ `tools/playtest/llm_player.py`), **per-turn commander** policy (whole board
  → ordered unit orders; the harness executes via existing primitives), **Sonnet default** (`PT_MODEL`
  knob), **board-hash-keyed transcript = cache + replay in one** (satisfies the "identical on CI lua &
  mGBA" rule and makes re-soaks free). TDD-ordered milestones **M1–M5** on the issue; ADR lands with M1.
  No spec doc (per convention). The swap point is still the pure `clearbot.lua` `pickTarget`.
- **Next: #46 lord-select UX** (alpha feedback #4 / #47) — Nicolas is picking this up next. New mechanic/UX
  → brainstorm/spec pass FIRST, captured as a GitHub issue (no spec doc), then TDD. Engine-labeled but a
  pipeline-lane "mechanics/flavor leaf" per #49. Engine already has `_inject_lord_select_engine` +
  `_inject_lord_floor_engine` hooks (guarded in `check_engine_guards_present`) — this is the *selection-menu
  UX* on top (show each candidate's PC summary, explain the choice).

## Earlier (2026-06-20) — party-side parity delta auto-derived + healer modeling (#61/#62)
- **#61 + #62 LANDED & verified — the party-side parity delta works for Ch2+ and models healers**
  (decisions.md §A fielded healer… / §The vanilla PLAYER deploy field…). Two content-track-filed bugs found
  bringing ch02 (#22) to parity: (a) the player-side delta was hand-keyed in a `VANILLA_FIELDS` dict (Ch1 only →
  every other chapter printed "delta skipped"); (b) a staff-only healer crashed the run (`NoneType.wt`) or got
  mis-roled as an attacker. Fixes: **`fe_combat` is now None-weapon-safe** (a `weapon=None` support unit = 0
  throughput, still a body for durability); **`_weapon_for` honors the YAML `unlock` flag** (base Sclorbo →
  weaponless support, not an inflated 0.84 kpr); the **vanilla player field auto-derives from the decomp**
  (`PARITY_REFERENCE_ALLY_UDEFS` → blue force-deploy/reinforce arrays, `.charIndex` → class base + personal line,
  no autolevel, first-attacking weapon — mirrors `player_combatant`). `VANILLA_FIELDS` deleted. Ch1 delta
  materially unchanged (thru 3.74→3.69, dura/carry identical; HEAD is more faithful). `make difficulty`,
  `make test`, `make check` all green; 50 difficulty + 35 fe_combat asserts. **Healing stays unmodeled** (proxy
  disclaimer; both sides run a healer → largely canceling). **Next:** content authors Ch2+ enemy inventories so
  the curve's enemy-pressure half has a real our-side force (today CH2+ reads 0.0 / OFF by design).

## Earlier (2026-06-19) — parity engine live; playtest smoke net + clear-bot + seeded fuzzer
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
1. **#46 lord-select UX** (immediate — Nicolas is picking this up): resolves the last open alpha-feedback
   item (#47 #4 — "explain the choice + show the candidates" at the lord-select menu). New mechanic/UX →
   **brainstorm/spec pass FIRST**, capture as a GitHub issue (no spec doc, per `feedback_no_spec_docs`), then
   TDD. The selection *mechanic* already exists (`_inject_lord_select_engine` in `tools/inject/engine_hooks.py`,
   guarded by `check_engine_guards_present`); this adds the prep-screen-style PC summary + framing on top.
2. **LLM-player #63 — M1** (epic spec'd this session): the pure cores — board serializer + order-schema
   validator + board-hash transcript record/replay — TDD'd on plain `lua`/Python (`test_llm_player.*`, in
   `make test`), **no LLM calls yet** (replay a hand-written transcript). ADR for the settled design lands with
   M1. Then M2 (sidecar handshake, replay-only on the prologue) → M3 (live policy) → M4 (soak report → curve)
   → M5 (vanilla-FE8 validation). Swap point: `tools/playtest/clearbot.lua` `pickTarget`. ch02+ soak still
   needs per-chapter save-state checkpoints (deferred till those chapters exist).
3. **#53 tail — FE8 Ch13 reference** (→ our ch08, deferred/optional): bigger than billed — needs ~11 *standard*
   weapons modeled (silver/steel/killer/slim/short-spear/elfire/zanbato/swordslayer/purge), not a few exotics.
   ch08 is a scripted-defeat objective (never CI-gated), so it's informational polish; do it only if idle.
4. **Flip the CI parity gate to enforcing** (#48 (b)): once content authors the Ch2+ enemy inventories,
   change the CI step's `difficulty` → `difficulty-gate`. Leveled stat projection (#45 item 5) pairs here.
5. Other mechanics/flavor leaves once specced: d20 crit #11, spell-economy #9, iconic matchups #8.
   Injection pipeline #14 / maps #40 gate content.

## Watch out (pipeline-lane only)
- **The decomp build is NON-MATCHING vs retail FE8 (~67% of bytes differ).** Confirmed by diffing the base
  ROM against our built `.gba` (only the trailing ~5MB of padding matches). So **no small retail→build patch
  exists** — a `.bps` is ~ROM-sized (11.4 MB). Distribution is therefore the **private pre-patched `.gba`**,
  not a public patch. Don't re-attempt a public `.bps` without first making the build byte-match (a separate
  toolchain effort). `tools/make_bps.py` is correct + tested but intentionally **unwired** for public patches.
- **Save layout must stay stable for testers to keep progress (#59).** `check_save_layout_stable` fails the
  build if `BWL_ARRAY_NUM`/`WIN_ARRAY_NUM`/`SAVEMAGIC16/32` ever drift (e.g. a submodule bump). If it goes
  red, that drop genuinely breaks old saves → ship a per-release starter `.sav` for it and re-pin the guard.
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
