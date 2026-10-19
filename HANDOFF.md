# Handoff - Manchego Stars live state

**Read this from main** (`git show main:HANDOFF.md`): on a feature branch this file is the copy
from when the branch was cut, and may be days old.

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-10-19 (Claude, after #513). **The parity model is being rebuilt before any party or chapter
change: epic #510** (Nicolas, 2026-10-19). #490 found the model misloads units (unflagged units
grown, no promoted bonus, no realistic levelling): it read Dorbulgruf at 63 HP where the ROM loads 37.
Every lock was measured on that model, so **all of ch00-ch07 are under re-evaluation** and re-lock at
the end of #510. Never widen an `accepted_residual` to get green: design or model fidelity is the fix.
This session also merged #507 (the twin-payload reader reads every give-site: enum gifts, Ch15's
shared-script treasures, route and either/or branches) and #509 (#508: ch03's grell rode vanilla's
generic Mogall pid 0xb7, so ch04's Mogalls fought with its boss line; ADR 0098 now covers every
rewritten raw-pid row, enforced by `assert_rewritten_raw_pids_are_exclusive`).

## In flight

- **Draft PR #485 (`feat/27-ch07-scenes`)**, text only, unchanged: ch07 moves to Distant Blade's map.

**Next, in order (#510's list is the plan):**

1. **#510 steps 0 and 1 are DONE.** #511: the verdict diff (`make verdict-diff`; CI runs it on a
   PR that touches a parity input and comments only when a cell moved; ADR 0353). #513: units
   load as the ROM loads them (ADR 0354) and ch00-ch07 are unlocked. 9 of 32 cells flipped; ch01
   is OFF in every mode (its party half reads x1.415, past its x1.41 residual ceiling, NOT widened).
2. **#510 step 2: the gate grades all three modes**, then steps 3-9 in order, each with an
   in-engine proof and the verdict diff. Stop when a step moves no verdict. The verdict diff's
   `table` column (authored levels, no shift) is not a game mode: drop it once step 2 lands.
3. **#510 step 10: re-evaluate.** Re-run the party-lever survey in all three modes and bring
   Nicolas the options. Baseline (2026-10-19, in #510): the force side is near parity, and the
   clear-load excess is the party, mostly vanilla's Seth. Baxby-as-Seth is a past discussion, NOT a
   decision (ADR 0342 rejected it).
4. **#493 -- the wiki's remaining findings** (navbox, #490's stat ranges, supports after #494), and
   **#486 planning with Nicolas**, as before. #493's `vanilla_payload` audit is done (#507).

- **Owed in Nicolas's next playtest** (on #31): ch06's closing cue by ear, and the stat-screen face.
  Proven headless instead, never owed to him: a shop (the DSL's `shop:` step, ch02armory,
  ch05shops) and R on a cast member's name (`casthelp`, ADR 0346). Nicolas, 2026-10-15: a
  check the harness can make headless is never his to make.
- **ch04's line Mogalls changed in game with #509:** 15 HP where playtesters met 32.
- The Monte Carlo simulator is #456, now #510 step 9.

## Chapter work

- **#27 -- ch07** is hosted on slot 8, under re-evaluation with the rest (#510); its ending and
  the Distant Blade move wait on #486. `make chapter CH=ch07` is its state.
- **#24 -- ch04 owes the terrain-bonus lesson** (vanilla Ch4's "stay in the woods"), a dialogue pass.
- **#335** -- the AI audit (behavioural drift is invisible to every gate; proposes an
  `ai_divergence:` allowlist). It feeds #510 step 7.

## Traps a fresh session walks into

- **A verdict scenario may not drive the UI with raw `press()`** (`check.py`, #238): wrapping a
  `record*` scenario as a verdict fails the drift check. Run the record path once headless as
  one-off evidence instead, or write the verdict on `guardedInput`/`selectSemantic`.
- **What the ROM loads, read off the map:** `INSPECT.redStats` (`ch04redstats`), one run per
  `PT_DIFFICULTY`. Compare it against `unit_load.load`'s ranges before trusting either model.
- **Grep the campaign before proposing a name.** "Halvar", offered for a recruit, was already
  ch02's raider captain (`npc-bench.md`'s name bank is not a list of free names).
- **Our own scenes are named `MS_*`.** Any code that matches `EventScr_` must ask whether it
  also means `MS_` (#401 reported 26 of 40).
- **`make difficulty --curve` takes ~25s** (instrument v2 runs over 1001 careers per unit);
  `chapter_matchup` memoises on the chapter's CONTENT, so a doctored chapter dict still misses.
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
  gitignored `.agents/`, `map-review/`, `review/` — preserve those and **stage paths explicitly**.
  `.agents/skills` is a link to `.claude/skills` (Codex reads the tracked skills; its own copies
  had drifted). `map-review/` is ~46 MB of throwaway renders: prune it when the disk is tight.
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
