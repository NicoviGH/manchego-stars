# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-10-02 (Claude), #430 step 2b landed (#439, #440); step 3's report is posted.
**What landed and why is in `git log` and the ADRs it cites** -- this file keeps no "recently
landed" list.

## In flight

**Nicolas wants this run AUTONOMOUSLY in a fresh instance: work the queue below end to end
without checking in, except for a genuine design call (a move AWAY from vanilla).**

1. **#430 step 3 fixes, one PR each.** The picks are in #430's step-3 comment; each moves toward
   vanilla, so they are mine (Nicolas, 2026-10-02: a parity correction is not a design
   change). Re-measure with `make difficulty CH=chNN` (the split line: force vs party).
   - **ch00 guests.** The prologue injector zeroes Scramsax's and Hlin's personal lines
     (`inject/chapters/prologue.py`, guest_patch), so they fight at bare class base: party
     effect x3.95 / x2.59. Write each guest's twin line instead (Seth's, Eirika's: effective
     line minus our class base), and make `difficulty.fixed_roster_careers` read the same
     source. ch00's scenarios run once.
   - **ch01's goblin wave** `spawn_turn` 3 -> 2 (vanilla's turn).
   - **ch05's eruption waves** 2/3/5 -> 2/6/8, same tiles.
   - **ch02's front heats a phase early** with a 100% force copy. Our deploy front is y3-5
     against vanilla's y1-3, several enemy tiles sit closer, and four vanilla pursuers never
     reach the front. Check the vanilla terrain read before calling it a chapter fault.
2. **Step 4 (#403), then step 5 (#135), then step 6 (locks)**, all DATA-DRIVEN, not Nicolas's call:
   - **Founding party:** ch00's guests bank nothing, so the party runs 0.63-0.75 levels behind
     vanilla's route through ch06 (rewrite ADR 0295's "the curves converge"). Give the founding
     PCs the prologue's exp (~73), or L2 if that needs an engine setter that costs too much.
   - **Recruits:** each joins where vanilla's equivalent joins against vanilla's party. Plus
     #403's remainder: lupin and trex ride mid-game donor lines (Kyle L6, Colm L2) at level 1,
     so they run HOT; ADR 0042 is the precedent (a different BASE donor).
   - **After step 4, bring Nicolas the no-Seth residual with a pick.** ADR 0042 chose no
     Seth-tier unit; whatever party effect remains is that choice's cost, and it is his call.
   - **Locks:** ch00-ch02 were unlocked in #439. A chapter re-locks when its re-measure holds
     parity on v2.
   - ch07 still names **FE8 Ch6**; ADR 0315's route rule fails it the moment it is hosted, so
     re-point it (FE8 Ch7 by sequence) when its slice is grounded. ch08 -> FE8 Ch13 is deliberate.
   - The Monte Carlo simulator stays parked in #430 with its trigger.

## Owed by NICOLAS, not by the next session

- **The boat crews have no voice.** No lore file names Tali or either crew, and Tali carries
  ch06's plot-critical hint.

## Chapter work, after #430

- **#26 — ch06's own body.** `make chapter CH=ch06` is its state (HOSTED, not FINISHED). The
  reskins, the boarding pass and nerra's art need no dialogue and can go first.
- **#335** — the AI audit (behavioural drift is invisible to every gate; proposes an
  `ai_divergence:` allowlist).
- **#135** — v0.1.0 playtester feedback, never triaged; the only open player-facing item.

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
- **Merging:** the auto-mode classifier blocked `gh pr merge` once on 2026-09-30 until Nicolas
  said "merge and carry on"; after that it went through. If it blocks again, stop and tell him.
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
