# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-09-30 (Claude), after #413/#414/#415 landed. **What landed and why is in `git log`
and the ADRs it cites** — this file no longer keeps a "recently landed" list; it went stale
faster than anything else in it.

## In flight

**Nothing. No open PRs, no branches.**

## The sequence Nicolas agreed (2026-09-30) — run it without asking

Nicolas's instruction: work these **in order, one PR at a time, without his input** — branch →
PR → `/code-review <n> medium` → fix every finding → CI green → squash-merge → next. Come to him
only for a genuine design fork (record the question + your pick on the issue and keep going on
the next item) or when ready for a handoff. The canonical list is **#389's 2026-09-30 comment**;
state as of now:

| | item | state |
|---|---|---|
| 1 | PR A — one source reader for the injector (#413, ADR 0297) | **done** |
| 2 | #407 — every check carries a canary (#414, ADR 0298) | **done** |
| — | CI: cache the vanilla decomp build (#415, ADR 0299) | **done** (added by Nicolas mid-sequence) |
| 3 | **#389 — the moves.** `build_campaign.py` → `tools/inject/` bottom-up, ch06 INCLUDED, `test_build_campaign.py` split alongside | **NEXT** |
| 4 | #416 — injection forces ~1,500 asset conversions + every C file to rebuild on every build | after the moves (my pick: it is the biggest remaining build-time lever, local AND CI) |
| 5 | #408 out-of-tree build → #409 declared steps → #410 decomp fork → #411 message-id allocation + YAML schema → #412 blank-template chapters (with #302's driver) | in that order |
| 6 | Trim this file again once the sequence lands | last |

Then ch06's own body (#26) resumes — see "Chapter work" below.

### What the moves (#389) need to know before the first cut

- **Gate every move on `tools/injection_fingerprint.py`** (`--write before.json` on main, move,
  `--check before.json`; ~2 min, 975 files) **plus the unit suite** — ADR 0287. The fingerprint
  cannot see monkeypatching; the tests can.
- **Measured 2026-09-30: `build_campaign.py`'s top-level definition graph is a DAG** — the only
  cycles are three trivial 2-node pairs (`_HANGS`/`_NOOPS`, two `CH04_*_MSG`/`_SCRIPT` pairs). So
  any downward-closed set can move: extract bottom-up (shared layer first — text/script
  helpers, unit entries, asset table, SMS, tileset/map registration — then domains, then
  chapter injectors). Of ~15.5k lines: ~9.3k are owned by exactly one `inject_*`, ~2.8k shared
  by several, ~2k reached by no injector (main, guards, re-exported readers). Recompute with an
  `ast` pass rather than trusting these numbers.
- **Every source-reading guard now reads through `tools/inject/source.py`**, and
  `check_injector_source_has_one_reader` fails anything that opens `build_campaign.py` by path.
  A moved function is found wherever it lives — but a name defined in TWO injector files makes
  `def_source` raise: move, don't copy.
- **Tests patch `bc.X`** (e.g. `UNIT_ICON_WAIT_C`, `REPO`, `CHAPTER_SETTINGS_JSON`,
  `_layout_sidecar`). Once the function that reads `X` moves, the patch must target its new
  module. Expect these as the moves' main test churn.
- **`inject/hosts.py` discovers `inject_chNN` by AST across every injector file** and attributes
  bare message literals to the enclosing injector, so chapter injectors may move freely.

## Owed by NICOLAS, not by the next session

- **#367's proposal 4** — lock ch03–ch06, or accept the gate is decorative for them. ⚠️ Not the
  mechanical yes it looks like: ch06 reads x1.00 because it reproduces 100% of FE8 Ch6's force —
  a checksum on the donor pipeline, not a measurement. Ask; do not infer.
- **#403's remainder** — lupin and trex inherit a mid-game donor's personal line (Kyle L6,
  Colm L2) while declaring level 1, so those lines run HOT. ADR 0042 is the precedent (a
  different BASE donor, not a different level).
- **The boat crews have no voice.** No lore file names Tali or either crew, and Tali carries
  ch06's plot-critical hint.

## Chapter work, when the sequence is done

- **#26 — ch06's own body.** `make chapter CH=ch06` is its state (HOSTED, not FINISHED). The
  reskins, the boarding pass and nerra's art need no dialogue and can go first.
- **#335** — the AI audit (behavioural drift is invisible to every gate; proposes an
  `ai_divergence:` allowlist).
- **#135** — v0.1.0 playtester feedback, never triaged; the only open player-facing item.

## Traps a fresh session walks into

- **Our own scenes are named `MS_*`.** Any code that matches `EventScr_` must ask whether it
  also means `MS_` (#401 reported 26 of 40).
- **A new `check_*` must ship a canary** in `tools/test_check_canaries.py` (ADR 0298;
  `check_every_gate_has_a_canary` enforces it). A canary doctors a real input at `open()` and
  names the fault; a file it doctors or reads to aim goes in `CANARY_FILES`.
- **A guard that imports `build_campaign` or `map_placement_preview` cannot run on the CI
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
  intentionally dirty `fireemblem8u` submodule and the untracked `.agents/`, `map-review/`,
  `review/` — preserve those and **stage paths explicitly**.
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
  for this sequence 0287, 0296, 0297, 0298, 0299.
- **What is left to build** → GitHub issues; #20–#28 per chapter; #302 is the live epic.
- **Which asset the FE-Repo has** → `docs/fe-repo-scouting.md` (its table says where an anim
  LIVES, not what it does).
