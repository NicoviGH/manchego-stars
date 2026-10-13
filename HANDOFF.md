# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-10-13 (Claude): the campaign-arc planning pass (#486) is half done. The plan for
ch09-ch20 now lives in `status: planned` chapter YAMLs, read through a generated wiki, on draft PR
#487. **What landed and why is in `git log`, the PRs and #486** -- this file keeps no
"recently landed" list.

## In flight

- **Draft PR #487 (`feat/486-chapter-wiki`), ROM byte-identical** (injection fingerprint, all 16
  configs). It holds the chapter wiki generator (on that branch until it merges; published privately at
  https://claude.ai/artifact/Nv1KWW44LV7NMDK7PwoK3m; regenerate and republish to the same file
  after any chapter edit), the ch09-ch20 planned stubs, and the data standardization
  (faces in campaign.yaml, one class-token vocabulary, `location:`, three recruit stubs, keyed
  busts). Not yet `/code-review`ed; do that before asking Nicolas to merge.
- **Draft PR #485 (`feat/27-ch07-scenes`)**, text only: ch07's opening, boss quotes and houses are
  locked; nothing wired. **ch07 is moving to Distant Blade's map** (Nicolas, 2026-10-12), so the
  locked "harpoon heads-up before prep" beat needs rework (its ballistae move to ch13).

**Next, in order** (the full state, every decision and every open pick: #486, latest comments):

1. **Queued, approved work:** (a) recruit level and kit get one home (the build ignores a unit
   file's `inventory:`, `difficulty.py` reads it first; plan on #486), proved by fingerprint plus
   `make difficulty-gate`; (b) re-render the 15 ref-pipeline busts with `matte` to clear the edge
   halo, before/after shown to Nicolas before any commit.
2. **#486 planning, continue WITH Nicolas:** the open picks on the wiki's Open decisions page; then
   Act IV beats (ch17 beat and map, ch18 map); the recruit pass (who fills each vanilla role
   ch09-ch17); the legendary-weapon pass (one per PC); the back-half onboarding catalog; then the
   arc ADR, and close the ledger.
3. **#27 -- ch07's ending** once its exit hook is settled (pick pending on #486), and the move to
   Distant Blade. The rest of the ending is known: Messie in the top hat, the fish tax, his
   farewell reveal, the 10,000 gold, **Meriwa + Esio Trot join** (ADR 0342), the town crier. Ask
   Nicolas for his flow first. Recruit art inputs: `references/References/Recruits/esio-trot/`;
   Meriwa is the ch06 Mermaid plus a portrait. Still write NO custom or copied code
   (`docs/adding-a-chapter.md`). `make CH07BOOT=1`.
4. **#25 -- the White Moose retreats in ch05** instead of dying (Nerra's pattern, ADR 0337), and
   loses its blood (cast palette index 6). It joins at ch08's start (#28).
5. **#459** stays open for the parity CHECK itself (plan item 2: ours vs vanilla per chapter, by
   count and role). Its comment corrects vanilla's Ch9-14 party counts (Ephraim leaves after Ch8).

- **Owed in Nicolas's next playtest** (on #31): ch06's closing cue by ear, and the stat-screen face.
- `make difficulty-gate` enforces ch00-ch07. A change that moves a locked chapter's force
  reddens CI: re-measure, and fix toward the twin or bring Nicolas the residual.
- ch01-ch02 lock through `accepted_residual` (party clear-load 1.41, ADR 0042), with x1.4078 /
  x1.4081 measured, so a party-side regression there fails the gate too.
- The Monte Carlo simulator is #456, parked behind its trigger.

## Chapter work

- **#27 -- ch07** is hosted on slot 8 and locked at x0.95 / x1.09. `make chapter CH=ch07` is its
  state.
- **#24 -- ch04 owes the terrain-bonus lesson** (vanilla Ch4's "stay in the woods"), a dialogue pass.
- **#335** -- the AI audit (behavioural drift is invisible to every gate; proposes an
  `ai_divergence:` allowlist).

## Traps a fresh session walks into

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
