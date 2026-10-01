# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-10-01 (Claude), after #421 (#408), #422 (#409) and the #410 draft (#423). **What landed and why is in `git log`
and the ADRs it cites** -- this file keeps no "recently landed" list.

## In flight

**#423 (draft), branch `engine-patch-series` -- #410: the engine hooks are now a patch series,
`engine/patches/` (ADR 0305; my pick of a patch series over a GitHub fork is on #410).** Built,
reviewed by nobody yet, check.py clean. Owed before it leaves draft:
1. `injection_fingerprint --check` on the other 11 configurations (`--montage`,
   `--test-chapter`, `--lord-boot`, `--ch01/03/04/05/06-boot`, ch05 `--ch05-lupin`,
   `--ch05-moose`, `--ch05-ending=full`). Baselines: record them on `main` first (`--write`),
   then `--check` on the branch. Default is already IDENTICAL. They did not run because the Mac
   was at load ~44 (VS Code's `chrome_crashpad_handler` at 400% + a Unity batchmode job): one
   configuration took ~2h. Check `uptime` before starting.
2. `/code-review medium` on the checked-out branch, fix findings, CI green, mark ready, merge.

## The sequence Nicolas agreed (2026-09-30) -- run it without asking

Nicolas's instruction: work these **in order, one PR at a time, without his input** -- branch ->
PR -> `/code-review medium` on the checked-out branch -> fix every finding -> CI green ->
squash-merge -> next. Come to him only for a genuine design fork (record the question + your
pick on the issue and keep going) or when ready for a handoff. The canonical list is **#389's
comments** (latest: 2026-09-30, "the moves landed").

| | item | state |
|---|---|---|
| 1-2 | PR A (#413) + #407 canaries (#414), CI decomp cache (#415) | **done** |
| 3 | #389 the moves -- `build_campaign.py` is 379 lines, passes in `tools/inject/` (#418, ADR 0300) | **done** |
| -- | #417: boot/test-chapter builds died at the #396/#398 guards (found by the moves' gate) | **done** |
| 4 | #416 -- the mtime rewind keys off what `make` compiled (#419, ADR 0301) | **done** |
| 5a | #408 -- the ROM is built in `build/fireemblem8u`, a worktree of the submodule (#420, ADR 0302) | **done** |
| 5b | #408's last box: CI caches the injected build (#421, ADR 0303) | **done** |
| 6a | #409 declared steps (#422, ADR 0304) | **done** |
| 6b | #410 engine changes as a patch series (#423, ADR 0305) | **draft: finish the gate above** |
| 6c | #411 message-id allocation + YAML schema -> #412 blank-template chapters (with #302's driver) | in that order |
| 7 | Trim this file again once the sequence lands | last |

Then ch06's own body (#26) resumes -- see "Chapter work" below.

### Working in the split injector (ADR 0300 has the why)

- **Where a name lives**: `inject.source.def_source(name)` or grep `^def name`/`^NAME =` under
  `tools/inject/`. A chapter id another module reads lives in `inject/chapter_ids.py`; one only
  its chapter reads stays in `inject/chapters/chNN.py`.
- **Stub in tests with `inject.namespace.stubbed('NAME', value)`**, never
  `mock.patch.object(inject.X, ...)`: each importer holds its own binding.
- **Registries discover constants via `inject.namespace.injector_constants(pattern)`**, never
  `globals()`.
- **Never name a local `inject`** in a file that uses `inject.X` (and a function-local
  `import inject.X` makes `inject` local to the whole function).
- **A new injection pass is a `Step` in `inject/steps.py`** declaring its `writes`, `needs`,
  `flags` and `scope` (ADR 0304). `INJECT_STRICT=1` (CI, the fingerprint gate) names the step
  behind an undeclared write; an ordinary build only names the path.
- **Refactor gate**: `tools/injection_fingerprint.py --write/--check PATH --flags="..."`, one
  manifest per configuration; the twelve configurations are in ADR 0304. ~2.5 min each on an
  idle Mac. A KILLED run leaves `.build-config.json`, `.build-scopes.json`, `.build-compiled`
  and `.injectcache` stashed as `*.fingerprint-bak`; move them back before the next run.
- **`inject.decomp.DECOMP` is the BUILD TREE; `inject.decomp.SUBMODULE` is vanilla** (ADR 0302).
  A new vanilla reader uses SUBMODULE; anything reading the injected tree or the ROM uses DECOMP.

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
  for this sequence 0287, 0296, 0297, 0298, 0299, 0300.
- **What is left to build** → GitHub issues; #20–#28 per chapter; #302 is the live epic.
- **Which asset the FE-Repo has** → `docs/fe-repo-scouting.md` (its table says where an anim
  LIVES, not what it does).
