# Handoff - Manchego Stars live state

**Read this from main** (`git show main:HANDOFF.md`): on a feature branch this file is the copy
from when the branch was cut, and may be days old.

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-10-22 (Claude, #525 and #527 merged; #510 step 7 DONE, step 8 next). **The parity model is being
rebuilt before any party or chapter change: epic #510** (Nicolas, 2026-10-19). #490 found the model
misloads units (unflagged units grown, no promoted bonus, no realistic levelling): it read
Dorbulgruf at 63 HP where the ROM loads 37. Every lock was measured on that model, so **all of
ch00-ch07 are under re-evaluation** and re-lock at the end of #510. Never widen an
`accepted_residual` to get green: design or model fidelity is the fix.
This session merged #525 (one reader per force, plus the decomp-reader fold and ADR 0363) and
#527 (step 7, ADR 0364). Nothing is open from it. Step 7's design and proof are on #510.

## In flight

- **Draft PR #485 (`feat/27-ch07-scenes`)**, text only, unchanged: ch07 moves to Distant Blade's map.

**Next, in order (#510's list is the plan):**

1. **#510 steps 0-2 are DONE.** #511: the verdict diff (`make verdict-diff`; CI runs it on a
   PR that touches a parity input, comments only when a cell moved, and spells out each per-unit
   finding that changed; ADR 0353). #513: units load as the ROM loads them; ch00-ch07 unlocked
   (ADR 0354). #514: the gate grades Tutorial, Normal and Difficult, never the authored table, and
   reads only locked chapters; role checks read the mode (ADR 0355). The twin's force has ONE
   loader now, `difficulty.vanilla_loaded_units`; read it, don't re-parse UnitDefinitions.
2. **#510 steps 3-5 are DONE.** #515 (ADR 0356): enemies attack with the weapon the AI picks per
   target. #516 (ADR 0357): every enemy's stats are rolled 1001 times as the engine loads them,
   both sides; it flipped ch02 and ch03 on Difficult to OFF, both on the party half (ch02's
   ADR 0042 residual lapses, not widened). #517 (ADR 0358): the team is fielded per career,
   forced units first (vanilla's `gForceDeploymentList`), in the ROM's unit order
   (`inject.cast.load_order`, proven by `ch07blueorder`); ch01 Difficult went OK at its
   residual's edge (x1.407 vs 1.41). #518 closed step 5's open item: slot order = join order on
   both sides (the twin's Moulder now sits before Ross/Garcia), `vanilla_recruits` raises on
   any join order the player could change, and the enemy-cap invariant is a test.
   **Step 6 is DONE** (#519, ADR 0359): Strategy sections as cited claims, checked and printed
   by `make difficulty CH=chNN`, **never a model input** (Nicolas, 2026-10-21).
   **The decomp audit of steps 3-6 is DONE** (Nicolas asked for it before step 7, 2026-10-22):
   - #520 (ADR 0360): tomes carry their FE8 type (anima/light/dark) and sit on the magic
     triangle (`fc.TRIANGLE_RULES`, tested against `sWeaponTriangleRules`; `fc.is_magic`).
     No verdict moved. Twin Ch4's Artur/Mogall claim is now a real 0.06-round near tie.
   - #521 (ADR 0361): `difficulty.class_tags` reads effectiveness tags from data_itemuse.c
     (Rangers/Troubadours had no `cav`), plus `critbonus` (+15 crit) and `slayer` (Bishops).
     No verdict moved.
   - #522 (ADR 0362, Nicolas: reskins are cosmetic, they play as their base): the ROM now puts
     each reskin on its base's effectiveness lists; the reskin step refuses a base the engine
     tests by id. A ROM change: Shark Rider / Ironshell / Lamia / Tentacruel / Lycanroc /
     the Mercenary reskins take effective damage as their base classes do.
   - #524: one parser for decomp enums (`inject.decomp.enum_values`) and `.attributes` lines
     (`unit_load.attributes_in`); vanilla class facts live in `inject.class_ids`
     (`vanilla_class_values`, `slayer_classes`). Use those; don't add a regex.
   - Matching the decomp: all 34 `fc.W` weapons, `ComputeBattleUnitStats`, and `ai_target` vs
     `AiComputeCombatScore`. Not modelled (supports, S-rank, brave/magic swords/Luna, Silencer,
     status) is logged on #510 (comment 2026-10-22); none moves ch00-ch07 today.
   - **Reviews go to a SUBAGENT** (`/code-review <PR> medium`), never inline by the author.
   **Step 7 is DONE** (#527, ADR 0364): threat is the HEAVIEST ENGAGEMENT, not every enemy at
   once. `timeline.engagements` reads WAVES (pursuers by the phase they first strike the held
   deploy front, `timeline.front_contacts`) and POCKETS (each waiting enemy pulled from its
   cheapest walkable tile: a careful player, Nicolas 2026-10-22). `party_matchup(engage=)` takes
   the heaviest per career, and a wave member defends with the weapon it swung. In-engine proof:
   `ch04waves` matches 20 of 23 first-attack phases. The 3 misses all strike later in the engine
   (FE8 walks a pursuer at its chosen target), so that limit goes to step 9 (Nicolas: accept it,
   2026-10-22). **No verdict moved against main**; ch04 Difficult threat x1.46 -> x2.19 (already
   OFF), logged on #510.
   - **Next: step 8** (kits and sustain: healing, shop buys, gifts, durability). Brainstorm the
     design WITH Nicolas first and post it as a comment on #510 (designs never go in a doc file,
     2026-10-22). `make difficulty CH=chNN` lists each side's `unmodelled, step 8` claims: that
     is what it inherits. Then step 9 only if verdicts still move.
   - Verdicts OFF now: ch01 Tutorial/Normal; ch02, ch03, ch04 on Difficult (ch01 Difficult
     reads OK at its ceiling's edge). All of it waits for step 10; nothing is widened.
   - **ADR 0363 (Nicolas, edited in place 2026-10-23): an unwritten (`status: planned`)
     chapter gets no difficulty reading at all** (PR #529): neither its draft YAML nor its twin
     is read for it until it is written. Don't build or test around planned rosters.
   - `party_matchup` reads each unit as ONE Combatant whose stats are numpy arrays over the
     careers; `fe_combat`/`ai_target` take ints or arrays (`max0`/`clamp`/`where`). Keep new
     combat math array-safe, or `test_ai_target.OverCareers` fails. The Normal curve is ~7s.
   - **One force list per side** (#525): `difficulty.chapter_force` (ours) and
     `difficulty.vanilla_loaded_units` (the twin's) are the only walks; `arriving_fields` returns
     `our_bodies`/`van_bodies` (`danger_map.Body`, carrying `unit` and `ai`) index-aligned with
     each force. Read those; never re-walk a roster.
   - **Findings for step 10 are logged on #510** (comment 2026-10-19), not here: not acted on
     before step 10 (Nicolas, 2026-10-19).
3. **#510 step 10: re-evaluate.** Re-run the party-lever survey in all three modes and bring
   Nicolas the options. Read the twin BOTH with Seth fielded and with Seth benched (the Let's
   Play Archive's run benches him from Ch4); Baxby-as-Seth is back on the table as a lever and
   Nicolas says it fits Baxby (both on #510, 2026-10-22). Baseline (2026-10-19, in #510): the force side is near parity, and the
   clear-load excess is the party, mostly vanilla's Seth. Baxby-as-Seth is a past discussion, NOT a
   decision (ADR 0342 rejected it). Nicolas wants it TIGHTER (2026-10-21, on #510): clear-load
   above x1.0 means our game is harder than vanilla, so bring party levers toward x1.0 and a
   narrower band as options.
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
- **#335** -- the AI audit is closed (ADR 0265: a donor carries its AI); its "factor AI into the
  difficulty math" stretch is ADR 0364.

## Traps a fresh session walks into

- **A tie in FE8's AI order goes to the unit that LOADED first** (`timeline.ai_priority` key,
  ADR 0364): list order is not slot order. Breaking it on list position read ch02 OFF at x0.74
  against a twin with the same map and enemies. When a ratio moves on a mirrored chapter, diff
  the two sides body by body before believing it.
- **`ch04waves` holds every unit on BOTH sides at full HP every frame** and fails if a red
  dies: 0 Pow still counters through weapon Mt. A proof scenario where something dies is not
  evidence of a model that kills nothing.
- **A comment-only YAML edit leaves the ROM "up to date"** but newer than the ROM by mtime, so
  `run.sh` refuses it. After a clean rebuild that wrote nothing, `MX_SKIP_ROM_CHECK=1` is honest.
- **The parity read now opens our maps and the submodule's map files**, so they are parity inputs
  (`verdict_diff.DATA_PATTERNS`); `test_verdict_diff.ParityInputs` fails if a new read is not.

- **A verdict scenario may not drive the UI with raw `press()`** (`check.py`, #238): wrapping a
  `record*` scenario as a verdict fails the drift check. Run the record path once headless as
  one-off evidence instead, or write the verdict on `guardedInput`/`selectSemantic`.
- **What the ROM loads, read off the map:** `INSPECT.redStats` (`ch04redstats`), one run per
  `PT_DIFFICULTY`. Compare it against `unit_load.load`'s ranges before trusting either model.
  `INSPECT.blueOrder` (`ch07blueorder`) logs the blue table in slot order after prep.
- **Combat math takes ints OR numpy arrays** (`fe_combat.max0/clamp/where/maximum/minimum`):
  `party_matchup` reads every unit over all its careers at once. New combat code must stay
  array-safe, or `test_ai_target.OverCareers` fails. A full Normal read is ~5s; keep it there.
- **Grep the campaign before proposing a name.** "Halvar", offered for a recruit, was already
  ch02's raider captain (`npc-bench.md`'s name bank is not a list of free names).
- **Our own scenes are named `MS_*`.** Any code that matches `EventScr_` must ask whether it
  also means `MS_` (#401 reported 26 of 40).
- **`make difficulty --curve` takes ~5s a mode** (1001 careers per unit, read as arrays);
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
