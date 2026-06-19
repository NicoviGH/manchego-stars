# Handoff — Pipeline track ⚡ (instance B)

Live state for the **pipeline instance** (the CD machine — the part agents accelerate). The
parallel-work model is the ADR in `docs/decisions.md` (§Delivery model → Parallel work model /
Engine-content file seam); work tracker #50; backlog is **GitHub issues** (#49 ② Pipeline track),
not this file. Don't clobber the content track's `HANDOFF-content.md`.

> **Always work in this `../ms-pipeline` worktree, never on `main`** (the doctrine, per CLAUDE.md
> §Tracks + decisions.md — even solo). Stay strictly in the pipeline lane: **don't edit
> `tools/build_campaign.py`** (content-owned; the lane guard blocks it, and it's the main parallel
> merge-conflict risk). Pure-pipeline files (`difficulty.py`, `fe_combat.py`, `playtest/**`, CI) are
> conflict-safe. If a content instance is running in parallel, `git pull --rebase origin main` often.

## Seam enforcement landed (2026-06-19, #55) — READ IF YOU RUN PARALLEL
The first parallel run had violations (pipeline edited content's `build_campaign.py`) because the
seam was honor-system and no worktree isolation was actually engaged. Now **enforced**:
- `check.py check_lane_ownership` (pre-commit + CI) blocks cross-lane edits **when you're in a lane
  worktree** (branch `inst/<track>`). `main` is lane-unrestricted but, per the always-worktree rule
  (#35debda), is for integration/cross-track merges only — **never solo track work** (do that in the worktree).
- `worktree-setup.sh` derives/announces the lane + ensures the hook runs. **Each instance MUST work
  in its `../ms-<track>` worktree** (CLAUDE.md §Parallel Tracks; decisions.md §Seam enforcement).
- The shared weapon↔ITEM map moved to `tools/inject/decomp.py`; **#53 weapon work never touches
  `build_campaign.py`** now. Proven: in an `inst/pipeline` worktree, editing `build_campaign.py` is
  blocked, `difficulty.py` allowed; `--no-verify` is the only escape. The primary checkout is
  integration-only (lane unset).

## Last session (2026-06-19, pipeline) — #48(b) informative CI parity gate (worktree, green)
- **Parity curve now runs in CI informatively.** Added an "Enemy-pressure parity curve (informative)"
  step to the `build` job (`make difficulty`; uses the submodule that job already checks out to read
  decomp HEAD) — so balance spikes/sags and parity regressions show on every PR. Always exits 0.
- **Hard gate built but unwired.** `difficulty.py --curve --check` (=`make difficulty-gate`) exits
  non-zero on any chapter that claims a `parity_reference` and is off-parity OR has a dropped boss
  (unreliable OK ≠ pass); no-ref chapters never gate. Pure `curve_gate_failures(rows)`; `curve_report`
  now returns rows. **The flip is one word in CI** (`difficulty` → `difficulty-gate`) once content
  authors Ch2+ inventories — RED-by-design today (our side 0.0). TDD: +4 tests, 42 pass; 4 suites green.

## Earlier session (2026-06-19, pipeline) — #53 monster/extended weapons (worktree, green)
- **#53 landed** (in the `inst/pipeline` worktree): added 9 vanilla-only weapons to `fe_combat.W`
  (monster claws `fetid/rotten/venin-claw`, `evil-eye`, + `thunder/iron-blade/venin-axe/halberd/horseslayer`),
  stats from `data_items.c` HEAD. Mapping lives in a **difficulty-local** `VANILLA_ONLY_ITEM_TO_WEAPON`
  merged into `ITEM_TO_WEAPON` — **not** in content-owned `WEAPON_ITEM_ENUM` (seam rule; see decisions.md).
- Curated registry entries for **FE8 Ch4 (23, all-monster)** and **FE8 Ch6 (25)** — our ch04/ch05 (Ch4)
  and ch07 (Ch6) now resolve a reference bar. Method: armed-RED arrays the eventscript references. Ch6's 2
  staff-only healers drop by design (weaponless ≠ unmodeled-weapon). TDD: +3 tests, 38 pass; all 4 suites green.
- Curve confirms the references are live; **our side still 0.0 / !!boss dropped** because content hasn't
  authored Ch4–7 enemy inventories yet (expected — that's the content track's job; gates the hard CI flip, #48 (b)).
- **FE8 Ch13** (our ch08) is the lone deferred reference — informational scripted-defeat, lowest priority.

## Earliest session (2026-06-19, pipeline) — #48/#51/#52, all on main, green, pushed
- **#48 enemy-pressure parity engine** landed: `vanilla_enemies` (decomp extractor),
  `enemy_pressure` (threat/slot + clear-load/slot vs a fixed yardstick), `pressure_verdict`,
  `chapter_enemy_force`; per-chapter report section + `make difficulty` (no CH) campaign curve. Ch1
  (1:1 FE8 Ch1 mirror) validates at parity (×0.89 / ×0.97).
- **#51** (closed): warn instead of silently dropping unmodeled-weapon enemies; loud
  `!!boss dropped — verdict UNRELIABLE` when a boss has no FE-base weapon.
- **#52** (closed): the ch00 prologue boss weapon is now driven by the YAML `fe_base`
  (`build_campaign.fe_item_enum` + `WEAPON_ITEM_ENUM`), not hardcoded — **byte-identical ROM** proven
  (md5 `3fed0f62…` before==after). Also fixed the ch00 `ice-longsword` → `fe_base: steel-sword` gap
  that was dropping the boss from the metric.
- **#48 registry** now covers Prologue, Ch1, **Ch2 (9), Ch3 (10), Ch5 (23)** — all fully modeled.
  Curation method documented at the `PARITY_REFERENCE_UDEFS` block.
- Deduped the weapon↔item maps: `build_campaign.WEAPON_ITEM_ENUM` is the single source;
  `difficulty.ITEM_TO_WEAPON` derives from it. Added `steel-axe` + `killing-edge` to `fe_combat.W`.

## Start here (fresh instance — do this first)
You are the **Pipeline-track** instance for Manchego Stars (trunk-based, your own worktree).
1. **MANDATORY first — work in the pipeline worktree, never on `main`.** It already exists at
   `../ms-pipeline` on branch `inst/pipeline` — `cd ../ms-pipeline` and confirm with
   `git rev-parse --abbrev-ref HEAD`. Only if missing, bootstrap it: `tools/worktree-setup.sh
   ../ms-pipeline` (branch + toolchain symlinks), then `cd ../ms-pipeline`. This is **enforced**:
   `check.py check_lane_ownership` (pre-commit + CI) blocks pipeline edits to content-owned files and
   blocks any lane-exclusive file when you're not in a lane worktree. Don't work loose on `main`.
2. Read `CLAUDE.md` (§Parallel Tracks) and `docs/decisions.md` (§Seam enforcement), then continue from
   **Next** below.
3. Trunk-based: small commits, `git pull --rebase origin main` often, push when green, no
   long-lived branches, never commit the `fireemblem8u` submodule pointer.

## You own (edit freely)
- `tools/inject/engine_hooks.py` — the 5 campaign-agnostic engine hooks
- `tools/inject/decomp.py` — shared decomp paths + brace-patch primitives (content imports these;
  changing a signature ripples into `build_campaign.py`, so keep them stable / coordinate)
- `tools/difficulty.py`, `tools/fe_combat.py`, `tools/check.py` (drift guard), `tools/playtest/**`
- `.github/workflows/**` (CI), `tools/build.sh`, `tools/worktree-setup.sh`

## Hands off (content track owns — coordinate via an issue if you need a change)
- `campaigns/**`, dialogue, and `tools/build_campaign.py`'s `inject_*` + sprite/palette hooks
- If you need a new engine hook wired, add it in `engine_hooks.py` and add the one orchestrator
  call in `build_campaign.py` (the only content-file line you touch) — then update the guard.

## Next (priority order)
1. **#53 tail — FE8 Ch13 reference** (→ our ch08, informational only, lowest priority). Ch4/Ch6 + the
   monster/extended weapon set landed last session. Ch13 "Hamill Canyon" is a large mixed force with several
   more exotic/monster weapons; curate via the same method (`grep UnitDef_ src/events/ch13-eventscript.h`,
   keep armed-RED arrays), add any missing weapons to `fe_combat.W` + `VANILLA_ONLY_ITEM_TO_WEAPON`, TDD the
   count. Since ch08 is a scripted-defeat objective (not a CI-gated chapter), this is genuinely optional polish.
2. **Flip the CI parity gate to enforcing** (#48 (b)): the informative curve now runs in CI and the
   enforcing form exists (`make difficulty-gate`). When the content track has authored the Ch2+ enemy
   inventories (today our side is `0.0` / `!!boss dropped`, so enforcing would red the build), change the
   CI step's `difficulty` → `difficulty-gate` — that's the whole flip. Leveled stat projection (#45 item 5)
   pairs here (sharpens the projection the gate measures against).
3. **Playtest platform** (the #49 strategic spine — good fresh-instance work): grow `tools/playtest/`
   from the floor/ch01win scenarios toward an I/O harness → stability fuzzer → LLM-player.
4. Mechanics/flavor leaves once specced: lord-select UX #46, d20 crit #11, spell-economy #9,
   iconic matchups #8. Injection pipeline #14 / maps #40 gate content.

## Watch out
- **Vanilla-only weapons (monster/exotic) belong in `difficulty.py`, not `WEAPON_ITEM_ENUM`** — that
  map is content-facing (drives the build's YAML loadouts) and content-owned; keep it to weapons our
  cast actually uses, and derive `ITEM_TO_WEAPON` from it + a difficulty-local vanilla-only extension.
- **Curation gotcha (#48):** an `events_udefs.c` array a chapter eventscript references may be a
  *cutscene* array — endgame villains (Riev/Caellach/Valter) placed with empty `.items`. Filter to
  arrays whose RED units **carry weapons**; that excludes both cutscene arrays and (unreferenced)
  skirmish/tower data.
- New decomp patch target → add it to `PATCHED_DECOMP_FILES` (build idempotency / `count==1` guard).
- Engine stat changes to the chosen lord go in `EndPrepScreen`, not a phase-start seam.
- `make`-green can't prove apply timing — `tools/playtest/` is the dynamic arbiter; run it.
- Vanilla decomp reads go through `build_campaign.vanilla_decomp_text()` (HEAD), never the worktree.
  It now **strips inherited git env** (`dcbb247`) — `git -C fireemblem8u show HEAD:…` was exiting 128
  under the pre-commit hook in a worktree (git exports `GIT_DIR`, which overrode `-C` discovery). If a
  worktree commit fails on a submodule read, that's the class of bug; don't reach for `--no-verify`.
- A behavior-preserving refactor should yield a byte-identical ROM (md5) — use that as proof.
