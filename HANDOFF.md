# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-10-09 (Claude): the ch06 story frame (#468, ADR 0332) and ch06's opening with
Speaker Dorbulgruf (#469) merged. **What landed and why is in `git log` and the ADRs it cites**
-- this file keeps no "recently landed" list.

## In flight

Nothing on a branch. **Next, in order:**

1. **#26 -- `boss_defeated`, Messie on the ice: dialogue pass.** Settle BEATS with Nicolas
   before any line (the dialogue-pass skill). The frame is ADR 0332 and the event's YAML
   description: local to Bremen only (the Frostmaiden reveal is ch07's ending), Marty and
   Braulo carry it, the book's own Messie lines (Rime p.31), and it closes on Messie-for-Speaker.
   Messie is pid 0xbd on the Syrene face slot.
2. **#26 -- `chapter_end`: dialogue pass.** Open call to bring with a pick: ch06 pays 400 gold
   at chapter end while Dorbulgruf's bounty (300, "for its head") is never paid. Pick: the
   rescued crews pay the 400.
3. **#26 -- claim `status-effects` and `terrain-bonuses`** in ch06's `introduces:` ledger
   (Grynsk's Antitoxin, Tali's snow drifts), then `python3 tools/gen_onboarding_index.py`.
4. **#459 -- roster parity with vanilla**, chapter by chapter (unchanged; Baxby-as-Seth is the
   open call there).

- `make difficulty-gate` enforces ch00-ch06. A change that moves a locked chapter's force
  reddens CI: re-measure, and fix toward the twin or bring Nicolas the residual.
- ch01-ch02 lock through `accepted_residual` (party clear-load 1.41, ADR 0042), with x1.4078 /
  x1.4081 measured, so a party-side regression there fails the gate too.
- The Monte Carlo simulator is #456, parked behind its trigger. ch07's twin re-point is on #27.

## Chapter work

- **#26 -- ch06's own body.** `make chapter CH=ch06` is its state. The opening is written,
  wired and filmed (`recordch06opening`, `recordch06ice`); `boss_defeated` and `chapter_end`
  are what is left.
- **#27 -- ch07** is reframed by ADR 0332 (Dorbulgruf refuses out of disbelief; Messie's fish
  tax; his farewell carries the Frostmaiden's orders to the merfolk). Still `status: planned`.
- **#335** -- the AI audit (behavioural drift is invisible to every gate; proposes an
  `ai_divergence:` allowlist).

## Traps a fresh session walks into

- **Our own scenes are named `MS_*`.** Any code that matches `EventScr_` must ask whether it
  also means `MS_` (#401 reported 26 of 40).
- **A wave's arrival turn has four spellings** (`arrives_turn`, `trigger_turn`, `spawn_turn`,
  `arrives: {turn:}`). Read it through `inject.raw_pids.entry_arrival_turn`, never a field.
- **`make difficulty --curve` takes ~25s** (instrument v2 runs over 1001 careers per unit);
  `chapter_matchup` memoises on the chapter's CONTENT, so a doctored chapter dict still misses.
- **`levels:` (per-body levels) is honoured only by ch02's and ch04's emitters.** ch01, ch03,
  ch05 and ch06 read `level` alone and would silently emit one level for every body. A parity
  fix that splits a pack's levels there must first route the emitter through
  `inject.raw_pids.entry_body_levels` (#438 is the pattern: diff the emitted rows).
- **The TESTCH bench seats ONE chapter's creatures** (`make TESTCH=1 BENCH=chNN`, the newest by
  default; it was full at 14 tiles). `recordenemy` with no `PT_CHAR` films the first creature on
  it, and a staff-only foe gets a 1-HP patient and is filmed healing on the enemy phase.
- **The FE-Repo is not the whole community.** Search FEUniverse too before calling an asset
  missing (`docs/fe-repo-scouting.md` says how): ch06's shark-rider anim was only there.
- **A new `check_*` must ship a canary** in `tools/test_check_canaries.py` (ADR 0298;
  `check_every_gate_has_a_canary` enforces it). A canary doctors a real input at `open()` and
  names the fault; a file it doctors or reads to aim goes in `CANARY_FILES`.
- **A guard that imports `build_campaign`, an `inject/` pass module, or `map_placement_preview` cannot run on the CI
  `checks` job** (pyyaml only, no submodule). Read source through `inject.source` instead.
- **Before changing a signature, or what a parameter MEANS**: `tools/callsites.py`, then diff
  the OUTPUT (decisions.md → "We wrapped on-map talk at 29 CHARACTERS").

## Current state

- **Where a chapter stands is `make chapter CH=chNN`** (#312), derived on demand. Do not write
  chapter status into this file.
- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
  2026-09-30: VS Code's `chrome_crashpad_handler` was burning ~430% CPU, which made every timing
  noisy — suspect it before believing a slowdown.
- **Primary checkout: `/Users/Yonick/Projects/manchego-stars`**, holding `main`. Clean except the
  untracked `.agents/`, `map-review/`, `review/` — preserve those and **stage paths explicitly**.
  The submodule is pristine now; the ROM is `build/fireemblem8u/fireemblem8.gba` (ADR 0302).
- **This Mac's disk is ~97% full (6.3 GB free, 2026-09-30).** A decomp tree with outputs is
  ~470 MB; don't add per-config build trees or keep scratch ROM copies around.
- **Two sandbox false negatives on this Mac:** `gh auth status` reports the token invalid (a
  restricted process cannot read the Keychain — run `gh` with escalation); an mGBA AppKit abort
  before the ROM runs is the sandbox, not the ROM.
- **Merging:** the auto-mode classifier blocks `gh pr merge` until Nicolas says "merge" for that
  PR (2026-09-30, again 2026-10-04 on #458). When it blocks, stop and tell him.
- **Cross-agent continuity:** Nicolas uses Codex only between Claude sessions; Codex leaves an
  explicit HANDOFF entry (what changed, branch/PR state, verification run, exact next step).
  **One task at a time = a plain BRANCH in this tree**; worktrees only for concurrent workers.

## Workflow facts that have nowhere better to sit

- **`HANDOFF.md` is authored on `main` ONLY** (`check_handoff_only_on_main`). If the guard fires
  on a branch: `git checkout main -- HANDOFF.md`.
- **A commit takes ~45–60s**: the pre-commit hook runs the full `tools/check.py`. It skips the
  check canaries unless the commit stages `tools/**.py` or a file in `CANARY_FILES` (ADR 0298);
  `make check`, `make test` and CI always run them. Commit with a message FILE
  (`git commit -F <file>`), never a heredoc — a heredoc's stdin has hung the hook.
- **CI:** `build` (~2.5 min) is the PR's critical path; `tests` ~1 min and `checks` ~25s run
  beside it. The vanilla decomp build is cached (ADR 0299); `build.yml`'s `workflow_dispatch`
  with `no_cache` builds clean, and the `ROM checksum` step makes the two comparable.
- **A SUBAGENT is not woken by its own background task.** Tell it to run long commands in the
  FOREGROUND.

## Before you touch anything

This list is the INDEX; do not re-inline the content.

- **How to work here** → `CLAUDE.md` / `AGENTS.md`.
- **Why anything is the way it is** → `docs/decisions.md` (index; open the two or three you need).
  Most likely to bite: *"Playtest runs are the most expensive thing in this repo"*, *"A scenario
  written against the old design will FAIL ON SUCCESS"*, *"An artifact is not its inputs"*, and
  for injector work 0300 and 0304.
- **What is left to build** → GitHub issues; #20–#28 per chapter; #302 is the live epic.
- **Which asset the FE-Repo has** → `docs/fe-repo-scouting.md` (its table says where an anim
  LIVES, not what it does).
