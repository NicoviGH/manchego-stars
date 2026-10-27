# Handoff - Manchego Stars live state

**Read this from main** (`git show main:HANDOFF.md`): on a feature branch this file is the copy
from when the branch was cut, and may be days old.

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-10-27 (Claude: #510 step 9 PR E in progress on `feat/510-step9-e-campaigns`, 33ad9e8, no PR yet). **The parity model is being
rebuilt before any party or chapter change: epic #510** (Nicolas, 2026-10-19). #490 found the model
misloads units; **all of ch00-ch07 are under re-evaluation** and re-lock at the end of #510. Never
widen an `accepted_residual` to get green: design or model fidelity is the fix.

**#510 step 9 is being built, INLINE (Nicolas, 2026-10-26: subagent-driven development is too
token-hungry; write the code in the main session, a subagent only for `/code-review` and its
scoped re-reviews).** **Standing rule (Nicolas, 2026-10-26): never re-create or approximate a
vanilla rule -- "we need not reinvent vanilla AI behavior, it's all there." Any "what would the
game/AI do" runs FE8's own function in sight.lua's sandbox (ADR 0369); a divergence from vanilla is
a gap to close, not a ruling to record. Check every constant against the decomp.** Its plan is ONE comment, edited in place (the
amendment and Task C4 are folded in): <https://github.com/NicoviGH/manchego-stars/issues/510#issuecomment-6370592835>.
The bot plays the ACTUAL ROM, never a Python re-creation. **Merged:** A #530 (Ch8 cutscene loads are
not enemies), B #532 (`tools/playtest/board.lua`, the one board reader: `onField`, lean reads,
`canSeize` from engine patch 0005; `gen_symbols.py` has an OPTIONAL list so `PT_VANILLA=1` works).
**Inserted before C, at Nicolas's ask, and now DONE: the harness clean-up #531** (G1 #533, G2 #534,
G3 #537 78105ed; the summary is on #531).
- Use the helpers G2 added: `Board.each`, `INSPECT.place`/`freeBeside`, `INSPECT.settle`/`advanceDialogue`/`talkUntil`.
- A chapter case's `lua:` names the function that runs it (ADR 0214, amended). A generic probe is bound
  with `lua: INSPECT.redStats` and never with a one-line wrapper. A bound `INSPECT` probe takes no
  parameters (`matrix.entry_defined`).
- Read harness.lua in Python through `matrix.harness_source()` / `harness_functions_at()`.
- **Record and diagnostic scenarios are ARCHIVED** (#538, PR #539 d27f69a, ADR 0367). Nicolas: "I am
  not running 45 headed scenarios ever." No headed run is ever owed. A scene is filmed when it changes.
  - Use `recordscene` (any dialogue scene a checkpoint reaches) or `mapshot` for that.
  - Otherwise restore the specific recorder from commit f4ff003; ADR 0367 lists what it needs.
  - Kept live: `recordscene`, `mapshot`, `vanillagold` (step 9 reuses its retail boot), and
    `recordunitlist`/`recordsupply` (verdict kind).
  - harness.lua is ~7,500 lines with 156 top-level locals (the ratchet).
  - The seven boot-only ROM configurations stay in matrix.yaml, because the injection fingerprint
    enumerates them.
- #531 audit #8, #11 and #12 went with the archive. #17 (chunking) stays open on #531.

**Next, in order:**
1. **PR C is DONE** (#541 4dc5e73): `bot.lua`, the pure careful bot, ADR 0368. Summary:
   <https://github.com/NicoviGH/manchego-stars/issues/510#issuecomment-6425325716>.
2. **PR D is DONE** (#542 70e01bb): the bot plays one chapter of the real ROM, headless, and
   emits a `BOTRUN <json>` record. Record: ADR 0369.
   - **How it reads the game:** sight.lua runs FE8's own functions in a sandbox: save state, set
     registers, run frames until the call returns to a scratch `b .` loop, read, load back. NEVER
     `emu:step()` (it deadlocks across a frame end). The enemy's strike is
     `AiAttemptOffensiveAction` itself; `threat` is `GenerateDangerZoneRange` with the other
     enemies marked under a roof; Seize = `CanUnitSeize`, reach = `GetUnitEquippedWeapon`.
     botrun.lua is the drive loop. Unit state bits have ONE owner, `Board.US_*` in board.lua,
     pinned against bmunit.h by `TestUnitStateBits`.
   - Run by hand: `tools/playtest/run.sh bot` / `sightprobe` (ours ch01), and with `PT_VANILLA=1`
     (retail Prologue + Ch1). At 70e01bb's last fix: ours ch01 won t9 all alive (23,910 frames);
     retail won both, all alive. The review summary is on the PR.
3. **NOW: PR E (campaigns), then F** (stack E->F only). Branch `feat/510-step9-e-campaigns`
   (pushed, a4af19f, no PR yet). Everything settled + the open proposal is in the plan comment's
   "E1 as built and settled" block (link at the top): READ IT FIRST.
   - **Built:** `campaign.lua` (pure loop, `test_campaign.lua`), `INSPECT.campaignApi` + scenario
     `campaign` in harness.lua (world map by its own L/A to `GetNextUnclearedNode`; Pick Units;
     shops via `StartShopScreen` as a KEPT sandbox call, `Sight.machine(cpu, true)`; seals via
     Item > Use), controller states `shop_buy`/`world_map_idle`/`item_submenu`,
     `campaign_env.py` (PT_CAMPAIGN), ADR 0370 drafted. Retail ran New Game -> Prologue -> Ch1
     -> world map -> Ch2 (`PT_VANILLA=1 PT_CAMPAIGN='{"id":"probe","last":[3]}'
     tools/playtest/run.sh campaign`, ~40k frames to Ch2). Shop and seals NOT yet exercised.
   - **Finding that reshaped E:** a restart with the same style replays the identical game (the
     RNG is in the state). Settled with Nicolas after web research: varied draws, never
     repeated; same budget/rule both games; role-covering team where Preparations exists;
     Formation is its own later PR.
   - **Party selection is being redesigned (Nicolas rejected the role-tag draw, 2026-10-27):**
     explicit FE8 class choices, a party that builds up over the campaign like a player's,
     a rule for duplicate classes, informed by the twin Strategy claims and guides. The
     research is on the PR E branch as research records (ADR 0371, records 0001-0019; their
     index is generated beside the decisions index). Records 0012-0019 are
     the per-chapter "whom guides field" research. **Next:** brainstorm the party design with
     Nicolas one decision at a time, then implement, run retail to Ch4+ and ours, PR.
   - Every Ch2 attempt loses Vanessa (0x06) on turn 2: a bot-fault candidate for F's list, not
     tuned here.
**Standing rules from 2026-10-24 (Nicolas):**
- **Never skip a review finding.** Minors and nits get fixed too; only a stale or duplicate one is
  dropped, with evidence. Apply every review with the global `review-to-clean` skill
  (`~/.claude/skills/`; the rule is also in `~/.claude/CLAUDE.md`). It overrides SDD's "minors
  don't enter the loop".
- **No duplicate code ever reintroduced.** A mechanical duplicate-code gate (pre-commit + CI) is
  **#535**, not built yet; until it is, every review checks the diff for new copies.
**Merging:** Nicolas pre-approved merging step 9's and #531's PRs once `/code-review` (in a
subagent) is clean and CI is green on HEAD; every other PR still needs his "merge".
Ledgers (gitignored, the recovery map): `.superpowers/sdd/step9plan/progress.md` and
`.superpowers/sdd/plan531/progress.md`. No plan file is kept locally: fetch the plan fresh from its
GitHub comment (`gh api repos/NicoviGH/manchego-stars/issues/comments/6370592835 --jq .body`).
Rulings made on Nicolas's behalf are posted on #510 and #531, not only in the ledgers.
Lessons from the 2026-10-23 build session (read before dispatching):
- Cut feature branches from `origin/main`, never from a local `main` holding unpushed handoff
  commits: the pre-commit drift guard then sees the branch "edit" HANDOFF.md. Never `--no-verify`.
- After a matrix run the tree holds a non-canonical ROM (e.g. ch06boot): `controller_turn` refuses
  to run, and the pre-commit hook trips. Rebuild canonical or pick a scenario that build hosts.
- A step-9 PR's fix rounds each end in a scoped re-review; the reviews kept finding real defects
  (DefeatBoss hang, turn skips, a `PT_VANILLA` break from a required symbol), so don't skip them.
- `check.py` ratchets harness.lua's top-level local COUNT (156 after #539; it may only go down).
  New helpers and runtime state hang on `INSPECT` (declared above `log()` since #542); `TUNE` is
  for tuning knobs only.
- The session scratchpad is wiped when the date rolls over: refetch the plan from its GitHub comment.
- A matrix group that ERRORs in 0s with "the ROM is OLDER than campaign sources" was a make that
  wrote nothing (a comment-only edit), not a mid-run edit. Fixed in #539: the Makefile touches the
  ROM after every successful build.
Open thread on #531: a matrix run leaves the build tree non-canonical, so the pre-commit
`test_scene_actors` fails until `make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba`.

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
   **Step 8 is DONE** (#529, ADR 0365): each party carries its KIT (`tools/kits.py`): joining
   load plus every pickup the chain hands out before the chapter, the same rules on both sides,
   world-map shops included (ours projected from the twin's until `campaign.yaml` stocks a town).
   Each unit strikes each enemy with its fastest-killing weapon. The verdict reads the HAPPY
   path; `make difficulty CH=chNN` prints the guaranteed path beside it. Healing, durability, the
   arena and stat boosters are OUT by decision. `difficulty.item_weapon` is the one item ->
   weapon reader (fc.W, else data_items.c). It moved 5 cells to OFF, almost all from vanilla's
   second joining weapons (Seth's Silver Lance: ch01 Normal x1.41 -> x1.56); pickups move
   <=0.04. Nothing widened.
   - **Step 9 (real-ROM Monte Carlo) is BUILDING**: state and links at the top. Step 10 waits
     for its vanilla baseline.
   - Verdicts OFF now: ch01 all three modes; ch02 Difficult; ch03 and ch04 all three modes.
     ch00 and ch05-ch07 read OK. All of it waits for step 10; nothing is widened.
   - **ADR 0363 (Nicolas, edited in place 2026-10-23): an unwritten (`status: planned`)
     chapter gets no difficulty reading at all** (PR #529): neither its draft YAML nor its twin
     is read for it until it is written. Don't build or test around planned rosters.
   - `party_matchup` reads each unit as ONE Combatant whose stats are numpy arrays over the
     careers; `fe_combat`/`ai_target` take ints or arrays (`max0`/`clamp`/`where`). Keep new
     combat math array-safe, or `test_ai_target.OverCareers` fails. The full curve is ~6.5-7s
     on a quiet Mac; under load (2026-10-23: load average 6-9) it read 11s for BOTH main and the
     branch. Time base and branch back to back, never against an old number.
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
