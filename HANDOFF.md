# Handoff - Manchego Stars live state

**Read this from main** (`git show main:HANDOFF.md`): on a feature branch this file is the copy
from when the branch was cut, and may be days old.

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-10-30 (Claude, latest). **Nicolas's sweep of the bot code is MERGED (#550,
ef1dc4a). Speed is settled for now** (Nicolas, 2026-10-30: "we're fine with speed for now; if it's
an issue later we'll dig further"). main is clean and no branch is in flight. Results and numbers
are on #510: <https://github.com/NicoviGH/manchego-stars/issues/510#issuecomment-6524301360>.
Read **ADR 0380** (the sandbox halts in the BIOS instead of spinning), plus 0376 (its "Lost"
amendment), 0377 and 0379.
- **Cost now, in CPU s:** Manchego Stars ch01 clean t9 9.61 (was 13.56); vanilla Ch4 attempt 1
  clean t5 19.83 (was 36.49). Both play the same games as before.
- **If speed comes back:** the next lever is the harness's per-frame UI observation
  (`observeController`, about a quarter of a ch01 run's CPU), during `awaitActed` waits and boot.
  Not started on purpose.
- **The previous sessions' results are on #510 too:** step 9 E+F,
  <https://github.com/NicoviGH/manchego-stars/issues/510#issuecomment-6513563594>, and the audit,
  <https://github.com/NicoviGH/manchego-stars/issues/510#issuecomment-6504714008>.

**NEXT SESSION: the planner's open items (#510 step 9 parts B-D).** These were left as "raise with
Nicolas, don't patch", so open with them and agree an order before building. Recommended order:
1. **Vanilla Ch2: Talk recruits as goals, which protect the recruit (part D).** From New Game
   (seed 1), Ch2 has no clean clear in any of its 6 styles, because Ross is killed on turn 2-3.
   It goes first because it BLOCKS the vanilla store: no start past Ch2 can be re-saved until a
   clean Ch2 exists. The old Ch2 start is still clean (bold, no claims: attempt 5), so compare
   the two starts.
2. **Vanilla Ch5 is never clean:** the recruit 0x20 is missed. This is probably the same Talk
   goal. Ch6 was reached only through an uncommitted probe, and Ch5x follows Ch5 (ADR 0376).
3. **Manchego Stars ch03 is won t12 but not clean:** two units are lost to the boss on plans
   judging 0.88-0.89 death. This is a design question for Nicolas (look-ahead vs a sampled
   rollout; see "Ours bold loses units to the Mogall" below), not a patch.
4. **Forced fog stalls on the last hidden red unit** (part C, decided behaviour 17). Real Ch6
   does not hit it.
- The older "Still owed" list further down (ours ch02 (1,12) `left_open`, convoy before buying,
  promote at 10, claims as goal/weight terms) is still open. Fold it into the same conversation.

**Lessons from this session (tooling):**
- `print()` from a scenario goes nowhere headless: write a file under /tmp instead.
- A Lua `debug.sethook` covers only the thread it is set on: hook `coroutine.create` too, or the
  bot's own code (it runs in the scenario coroutine) is never sampled.
- An overnight background run can take hours of wall time for seconds of CPU (the Mac throttles
  it). Read `cpu_s`, not wall time, and don't mistake that for a hang.

**Running a chapter alone:**
1. `campaign_env.py vanilla --id e1-vanilla-ch3 --from N` (the store has 0-4 and 6; 6 is Ch5,
   index 7 is Ch6).
2. Set `last: [N]` and `attempt: k` in the JSON.
3. Run `PT_VANILLA=1 PT_RUN_TAG=x PT_CAMPAIGN="$(cat env)" tools/playtest/run.sh campaign`.

The old start records have no carried team: they resume with a WARNING and `carried_unknown`.
`attempt` k picks the k-th style drawn from (seed, chapter), so the old clean Ch2 style (bold, no
claims) is attempt 5. A full (non-attempt) run re-saves the starts it passes, so back the store up
first. Reaching Ch6 needs a scratch copy of the store and a won-carries-on patch (uncommitted).


**Part A (the four-part clean clear) as it stands.** Design: #510 comment 6485197805. Plan:
#510 comment 6485521139 (its Task 4 text is out of date: update it with what follows). Record:
**ADR 0376**.
- fbc4443: both envs carry `recruits` (still the regex; finding 7 replaces it).
- 6837811: botrun judges `clear` / `clean`; campaign.lua clears on `clean == true`; a vanilla
  chapter with no clean clear stops as `bot_fault` (Manchego Stars keeps `infeasible`);
  montecarlo reads `clean` and says what spoiled a clear; the old all-alive flag is retired.
- 6567cdc, 0f7c010, 08a906c: "joined" is now the game's party (`INSPECT.prepList()`); why
  (Ch5's ending leaves an unrecruited Joshua blue AND dead) is in ADR 0376. Unit tests only;
  the ROM proof is owed (the probe run above).
- 0aedbee: ADR 0376 (decisions 1-4 of the design).
- **Measured in the ROM:** vanilla Ch2 attempt 1 CLEAN (Eirika talks Ross t4, Ross talks Garcia
  t5; 28,445 frames, 12.2 CPU s). Vanilla Ch4 clean at attempt 1. Vanilla Ch5: 3 styles, none
  clean, stops as a BOT FAULT (Franz/Artur lost, the village at 5,1 unreached, Joshua killed).
- The clean store `references/sim/vanilla/c25b145e3745/states/e1-vanilla-ch3/` has 0-4 and 6,
  no 5: Ch5x follows Ch5 (ADR 0376) and no clean Ch5 clear exists yet. A campaign run re-saves
  the starts it passes, so back the store up first (this session restored 4 and 6 from a copy).
- Reading a chapter start's units with no run: ADR 0378.
- After A: B (varied retries), C (retries that learn), D (capability gaps: Talk recruits as
  goals, the held Doorkey, Ch10's stalls), E (vanilla's Eirika route cleared chapter by chapter).


**The parity model is being
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
3. **DONE: PR E (campaigns) and PR F (the runner)**, merged as #548 (dc5ed4b); then #549 (a
   unit is lost only when the game killed it, 96cf9d1). What they built, for reference. Read in the plan comment (link at the top): "Party
   selection, SETTLED", "Lords, SETTLED", "The planner", and Tasks 11-13 (F1-F3; F2 and F3
   were amended 2026-10-27).
   - **Built, E:** `Bot.team` picks the team by the map's DEMANDS, read at the prep screen
     (`Sight.demands`/`Sight.answer`). The group caps come from `team_groups.py` (an explicit
     class table). campaign.lua carries the cleared team and never repeats a style. Route
     (vanilla) and lead (ours, `INSPECT.pickMenuRow`) are campaign SETTINGS. The bot breaks walls,
     heals, ends Canto, uses Talk and doors, and ignores enemies in fog. `campaign_env.py`
     resolves claims to game ids and resumes with `--id X --from N`.
   - **Lords (Nicolas):** each of our 8 leads becomes its own cell, but only on #543's lord
     classes, after the runner. Until then ours runs the default lead.
   - **Built, the planner** (`planner.lua`; `Bot.candidates` proposes, `sight.enemyPhase` runs
     the game's own AI phase in one batch):
     - Every act carries its end tile's exposure, every unit has a safe retreat, and the beam
       pays each moved unit's death chance (020864d).
     - A plan's next act is played unless `Planner.surprise` finds the board off the plan's
       expectation (fb207ae). Heals are never planned on a unit the plan has moved (that was
       a Staff crash).
     - **Measured, ch03 alone:** careful won turn 13, all alive, 19.5 CPU s, 28 plans for 141
       acts. Before these two changes it lost 1-3 units an attempt at ~38 CPU s.
     - Speed: `Sight.batching` (one save/load per decision), cached unit facts, and `costs` in
       every BOTRUN. Report timings on every change (Nicolas).
   - **Built, F1, the pool** (9993947): `montecarlo.py attempts --env <env.json> --attempts N
     --jobs J` plays attempts 1..N from the env's `from` start side by side and names the lowest
     clean one. It is exactly what the sequential loop finds: every attempt loads one start
     state, RNG included. Proven in the ROM: ch03 attempts 1-3 took 23 s wall vs ~60 s, and
     attempt 1 matched the sequential run. run.sh `PT_RUN_TAG` isolates copies of a scenario
     (run dir, kill, ROM copy and .sav). The campaign env's `attempt: k` plays only the k-th.
   - **Built, F2's verdict** (5add902, `paired_verdict`): looks only at 50/100/200 pairs
     (early stop at exact McNemar p < 0.001), Wilson rates, and Newcombe's paired interval for
     the gap. Nicolas accepted this over the old "stop when the interval excludes 0" rule.
     **Cross-checked** against statsmodels (~1e-16). In simulation the old rule falsely flagged
     29-32% of no-difference cells and the new one 3-5%; a real 10-point gap is caught 71% of
     the time. #510 comments 6455985418, 6456079024. Research records 0021 (planning a
     multi-unit turn) and 0022 (Monte Carlo statistics).
   - **F3's report format, settled (Nicolas, 2026-10-27: "I don't want to read a big table"):**
     one plain sentence per cell, in the plan's Task 13. The only words are HARDER, EASIER or
     "no clear difference", each with both clean-clear rates and the gap's range. A summary line
     sits on top, flagged cells first, noting that about 1 flag in 24 is chance.
   - **NEXT, in order:**
     1. **F2 is DONE** (c0382b3): `montecarlo.py cell --ours <env> --vanilla <env> [--mode]
        [--jobs]` plays a cell to its verdict. Pair s = each side's chapter start, the game seeded
        with s (env `reseed`) and attempt 1's style. Each game's runs go in
        `<run.sh --simdir>/runs.jsonl`, stamped with cell + Lua hash, and a kept run is never played
        again. A crash's pair is left out and replaced by a new seed. `sample_style` IS
        `Campaign.drawStyle` + `Bot.team` (no Python copy). The rulings are on #510 (comment
        6457132394). `make sim` is not written yet (F4 needs it).
     2. **F3's trace is DONE** (909e9ef; #510 comment 6457580533). Every run keeps a gzipped JSONL
        trace in the store (`traces/<campaign>/...`, named in the record). It holds the start,
        unit snapshots, plans (score, the others judged, predict, replan reasons), each act of
        both sides with the game's battle record (`Board.battle`: forecast hit/crit, can-counter,
        every blow), arrivals, recruits and items, and the record last. `montecarlo.py story
        <trace>` tells one run in plain text. The trace costs no measurable CPU. A Talk recruit
        no longer counts as a kill. Not traced: map-tile events (chests and villages show only
        as items).
        **Fixed after Nicolas's review (ba06c8e; #510 comment 6458549710):** each campaign keeps
        its seed (pair s = campaign s from New Game, its FIRST attempt at the chapter; no
        reseed). A run without a game result stops the cell and is reported in its own words.
        Enemy acts follow `gActionData` as vanilla writes it. The stamp hashes the whole env.
        `test_inject_unit_art`'s shared-temp-dir race is fixed.
        **Built since (b243941 + 2026-10-28: 2026147, 6d68721, 76c3a33; #510 comments 6459066722,
        6473075402, 6478205562):**
        - **Villages and chests, under Nicolas's NO-RISK RULE** (he rejected the made-up
          `explore = 200`; the rule is ON TRIAL, not locked):
          - `sight.explorable`/`canExplore` run the unit menu's own Visit/Chest checks.
          - Each open tile sends its nearest able unit marching to it, and the send STICKS while
            the tile is open and reachable; a unit cut off by a door or wall is sent through it
            (`breachFor`). A tile we explored is never offered again (vanilla Ch1's Houses).
          - The planner credits a visit only at zero chance to die, in both the beam and the
            judged phase. The credit (the recruit's 200) only orders a SAFE visit.
          - The record's `explore` says what became of each tile; a won run that leaves a usable
            tile open records a `left_open` bot fault.
          - Ours ch02 careful: 3 of 4 villages, won t9 all alive; the 4th was razed on turn 8.
            Ours ch03: careful and bold now open 4/4 chests (the 4th is behind a door).
        - **The full-bag rule (Nicolas, 2026-10-28), `Bot.fullBag`:** it answers FE8's own
          send-to-convoy / discard chooser, and the record has `bag`. Ours ch03: all 4 chests
          opened, and a duplicate Iron Sword went to the convoy.
        - **Boss maps (Nicolas agreed: option 2, plus "go at the boss with multiple units"):**
          - The ASSAULT plan: every unit that reaches the boss strikes it, judged beside the beam.
          - A repeated board is first a STALL: the planner must play a plan that changes it, and
            only a repeat after that is stuck. The record has `stalls`.
          - The boss is read from the game's own Defeat Boss goal (`GetDefeatTalkEntry`, flag 2),
            not CA_BOSS (before #545's fix the grell had none, so the bot saw no boss at all;
            every boss carries it now, and the goal read stays).
          - The judge CHAINS the counter with the enemy phase. Averaging it had let the lord
            strike the grell alone and die.
        **Done 2026-10-28 (late):** the fix list of #510 comment 6478205562, and the boss
        assault's starvation, ally swaps, three holds, free-tile march (see the top of this file).
        Still owed (the accepted design at the top orders all of this now):
        - Ours ch02 (1,12) is unreached in 7 of 8 (`left_open`); ours ch02 even loses one unit.
        - Ours bold loses units to the Mogall: no plan chips the boss now and finishes it next
          turn. Whether that becomes a look-ahead or a sampled rollout is the brainstorm's call.
        - Nicolas: **use convoy items before buying anything** (between chapters; drive the prep
          Supply screen). And: promote at level 10, between chapters, configured separately.
          Seals found in battle go to the convoy for now.
        **Then F3's rest:** the report (one plain sentence per cell first; Task 13), "what kills
        us" as a query over traces, bot faults, feasibility, attempts buckets, `--post`.
     2b. **Where runs live (plan Task 16, F5, SETTLED; Nicolas: give them "a good home in the
        repo"):** ONE home each (Nicolas: no copies). The WRITE-UP is a committed record per
        sweep, `sim/<id>-<slug>/RUN.md`: full YAML frontmatter of inputs and cost, plus the plain
        verdicts. It is indexed by gen_decisions_index as a third collection (the index file is
        to be built). The DATA is every run's trace, in one GitHub Release asset per sweep, sha256
        in the frontmatter, fetched by `montecarlo.py fetch`. No run data is kept in git:
        summaries are read from the traces. The local `references/sim` is only a cache (fetched
        traces, save states). Runs are reused by cell key; `--fresh` re-runs. The repo is
        PUBLIC, so releases are too.
     3. **The planner barely reads claims:** two ch03 attempts differing only in claims
        (`avoid` vs `kits`) played identically. The plan says claims become goal and weight
        terms; build that.
     4. DONE 2026-10-29: game calls run as lists (434c351). What remains is Lua and emulation.
     5. ch04 (fog), convert the other chapters' `unmodelled` claims, then the PR and
        `/code-review <PR> medium` in a subagent. (Vanilla Ch2's crash is fixed, 6c1d47c.)
     6. Whole-turn search (record 0021) is part of the design brainstorm at the top.
   - **How to run:** build PT_CAMPAIGN with `campaign_env.py`. Ours needs `--store` of a vanilla
     campaign through Ch8 for its shops; until one exists, pass `shops: {}` and `last: [host]`
     by hand. **PT_CAMPAIGN holds the JSON ITSELF, not a path:** `PT_CAMPAIGN="$(cat env.json)"
     tools/playtest/run.sh campaign`. A path is silently ignored, and a New Game runs. Retail:
     add `PT_VANILLA=1`.
   - **Fast loop:** an env with `id: e1-ours-ch07, from: 4, last: [4]` plays ch03 alone (~20 CPU
     s per attempt). The saved starts are in `references/sim/ours/9405eea0cb9f/states/e1-ours-ch07/`
     (4 = ch03, 5 = ch04).
   - **Gotcha:** switching to main (for a HANDOFF commit) and back touches the chapter YAMLs'
     mtimes, and run.sh then refuses the ROM as stale. Run
     `make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba` afterwards (the ROM hash is
     unchanged).
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
  Parked: chapter work resumes after #510's difficulty and roster work is done (Nicolas, 2026-10-28).

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
   Nicolas says it fits Baxby (both on #510, 2026-10-22). Baseline (2026-10-19, in #510): the
   force side is near parity, and the clear-load excess is the party, mostly vanilla's Seth.
   **The party decisions are tracked in GitHub, not here:** #510 step 10's checklist, and the
   tree under #459 (Roster parity): #547 (Cavaliers: Baxby as Seth, Lupin as Franz, joins
   levelled to their chapter) and #526 (Lord system), whose #543 is built FIRST in step 10.
   #459 is marked blocked by #510. Nicolas wants it TIGHTER (2026-10-21, on #510): clear-load
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
