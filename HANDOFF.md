# Handoff - Manchego Stars live state

**Read this from main** (`git show main:HANDOFF.md`): on a feature branch this file is the copy
from when the branch was cut, and may be days old.

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-10-15 (Claude, evening). **#487 is the one PR in flight:** the wiki on the Fire
Emblem Wiki's own templates (#493). Script and character pages and the character list are done;
the cast's in-game help text is their own (ADR 0346). Nicolas's order stands: finish the wiki
and merge it, THEN resume ch07+ planning with it. What landed and why is in `git log`, the PRs
and #493 -- this file keeps no "recently landed" list.

## In flight

- **PR #487 (`feat/486-chapter-wiki`, base `main`)**, published at
  https://claude.ai/artifact/Nv1KWW44LV7NMDK7PwoK3m (on the branch, run `gen_wiki.py`, then
  republish `build/wiki/index.html` to that URL). It carries deliberate ROM changes, so a fingerprint here
  proves only what a change claims not to move: #489's recruit kit, the green chwinga bust,
  ch02's Armory (ADR 0345).
  - **The engine (the branch's `wiki/` package)**: `vendor.py` vendors one real FE8 page per page type we
    publish, every template and Lua module it reaches, and the wiki's render as golden tokens
    (`wiki/vendor/`). `mw.py` expands the templates, `render.py` renders wikitext,
    `site.py` resolves links (our page, else the real wiki) and files (the build's art).
    `test_wiki_engine.py`: 14 exemplars, 12 exact, two quirks named beside their floors.
  - **Done on the templates**: chapter, Script (`script_sections` sorts scenes into the wiki's
    sections by trigger) and character pages (cast, bosses, planned recruits, lore NPCs), and the
    character list. `wiki/pages.py` is the layout, `gen_wiki` the data; every number is the
    injector's own (`inject.stats.cast_growths`/`cast_ranks`, `boss_modes`, `promotions`).
    `test_wiki_pages.py` holds each page type to its exemplars' section order.
  - **Character prose** is each lore file's `## Profile` (lore/README.md says what it is; drafts,
    Nicolas to red-pen on the wiki). HD art: `references/References/PCs/HD Art/<Name>HD.jpeg`,
    all eight PCs present.
  - **Still on the old HTML path (`wiki/markup.py`)**: home, design notes, open decisions.
    `markup.py` retires once the last of them moves.
- **Draft PR #485 (`feat/27-ch07-scenes`)**, text only: ch07's opening, boss quotes and houses are
  locked; nothing wired. **ch07 is moving to Distant Blade's map** (Nicolas, 2026-10-12), so the
  locked "harpoon heads-up before prep" beat needs rework (its ballistae move to ch13).
- **#490** -- the difficulty model's autolevel diverges from the ROM (unflagged bosses grown,
  promoted bonus missing); fix before ch09 is measured.

**Next, in order** (the full state, every decision and every open pick: #486 and #493):

1. **#493 on #487** -- its unticked boxes, in this order:
   - Pages: the availability chart, the lord-select concept page (`Imperial Three` /
     `Sacred Stone (object)` are the exemplars), the chapter list on templates, Nav8's navbox at
     every page's foot, the home page off `markup.py`, and Open decisions off the wiki (it lives
     in the YAML and on #486). Supports wait on #494 (the ROM loads each slot's vanilla partners).
   - Readers: ch01's money gift (`vanilla_payload` reads no gold, nor event GIVEITEMTOs or chest
     gold), boss personal lines from the INJECTED CharacterData, enemy names, and the **wield
     check** (every unit can use what it carries); #490's autolevel divergence.
   Then republish, Nicolas's layout list, `/code-review medium`, merge on his word. Nicolas is
   leaning toward ch01 on vanilla Ch1's map with Hamill Canyon back as ch08 -- raise it in the
   planning step.
2. **#486 planning, continue WITH Nicolas** on the updated wiki: the open picks on the Open
   decisions page (ch07's exit hook first: #27's ending waits on it); then Act IV beats (ch17
   beat and map, ch18 map); the recruit pass (who fills each vanilla role ch09-ch17); the
   legendary-weapon pass (one per PC); the back-half onboarding catalog; then the arc ADR.
3. **#27 -- ch07's ending** once its exit hook is settled, and the move to Distant Blade. The rest
   of the ending is known: Messie in the top hat, the fish tax, his farewell reveal, the 10,000
   gold, **Meriwa + Esio Trot join** (ADR 0342), the town crier. Ask Nicolas for his flow first.
   Recruit art inputs: `references/References/Recruits/esio-trot/`; Meriwa is the ch06 Mermaid
   plus a portrait. Still write NO custom or copied code (`docs/adding-a-chapter.md`).
   `make CH07BOOT=1`.
4. **#25 -- the White Moose retreats in ch05** instead of dying (Nerra's pattern, ADR 0337), and
   loses its blood (cast palette index 6). It joins at ch08's start (#28).
5. **#459** stays open for the parity CHECK itself (plan item 2: ours vs vanilla per chapter, by
   count and role). Its comment corrects vanilla's Ch9-14 party counts (Ephraim leaves after Ch8).

- **Owed in Nicolas's next playtest** (on #31): ch06's closing cue by ear, and the stat-screen face.
  Proven headless instead, never owed to him: a shop (the DSL's `shop:` step, ch02armory,
  ch05shops) and R on a cast member's name (`casthelp`, ADR 0346). Nicolas, 2026-10-15: a
  check the harness can make headless is never his to make.
- `make difficulty-gate` enforces ch00-ch07. A change that moves a locked chapter's force
  reddens CI: re-measure, and fix toward the twin or bring Nicolas the residual.
- ch01-ch02 lock through `accepted_residual` (ADR 0326): ch01 ceiling 1.41 at x1.4078; ch02
  ceiling 1.43 at x1.4216 with #489's kit (Pinky's real Slim Lance, on #487), so a party-side
  regression there fails the gate too.
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
