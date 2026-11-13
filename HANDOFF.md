# Handoff - Manchego Stars live state

**Read this from main** (`git show main:HANDOFF.md`): on a feature branch this file is the copy
from when the branch was cut, and may be days old.

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`**; how-tos live in the files they are about;
operating rules in `CLAUDE.md`/`AGENTS.md`; findings, scope and backlog on GitHub issues. Nothing
here should still be true in a month. Before a context rollover, warn Nicolas, refresh this file,
and start a fresh instance; don't rely on auto-compaction.

**Next session starts here (2026-11-13, evening): PR #606 is reviewed, green and waiting for Nicolas's "merge"; then make the suite cheap to probe BEFORE any more sandbox work.**
Nicolas (2026-11-11): "right now we're focused on getting the bot to play vanilla". Fable owns
the direction and may pivot from the plan when the data says so (Nicolas, 2026-11-13); **use
cheaper subagents** to check source, ADRs and research. The plan is **#510 comment 6810567866**;
item D's results are comment 6842371541; the leak's findings are comment 6860128405.
**Nicolas, 2026-11-13: the suite passes have slowed development badly and #510's scope keeps
growing. Run the full suite ONCE per PR, at the end; prove a fix on the one run that showed it.**

**PR #606 (`feat/510-closings-leak`, head f7e1e002): reviewed, every finding applied, CI green on the head, NOT merged (Nicolas has not said "merge").**
- What it is now: a simulated enemy decision puts back what the game wrote on unit structs.
  Four leaks, each with a unit test that fails without its fix: the AI bytes (`Sight.keepAi`,
  once a sandbox, every unit), the fog bits a map refresh rewrites (`keepFog` / `refresh`;
  vanilla Ch6 turn 2), a ballista's rider stepped off by the AI's attack decision and the
  redraw's map-sprite pointers (`keepRide`; vanilla Ch13 scout, seed 2002, turn 11).
- **`PT_LEAKGUARD=1`** (off by default, about a fifth slower): a nested sandbox that leaves a
  unit struct or the trap pool changed raises, naming the struct and the word. It found the
  last three leaks. Set it for one run after any change to what a sandbox calls.
- Review: `/code-review 606 medium` by a fresh subagent (9 findings) and one scoped re-review
  (4 notes), all applied; the PR body lists them with the proofs and the back-to-back timings.
- Frozen suite with held-out seeds on f7e1e002, guard on: **PROMOTED, 0 regressions, 0 runs
  without a result, no leak raised** (instrument `70cb82b1f331+v2`). All 56 runs play the acts
  of the PR's earlier suite, so the fog and ballista fixes moved no suite game; 45 of 56 are
  main's.
- Campaign 4006's Ch9 attempt 1 is a win in 19 turns on main and a loss on turn 10 on this
  PR (the lord dies on a plan over the cap); so it was before the review (tags `keepai1` to
  `keepai6`). Not looked into.
- **Finding 6, real and older than the PR, NOT in it:** a judged enemy phase never runs the
  game's phase-start AI setup (`AiPhaseInit`, cp_phase.c: `gAiState.flags`, `cmd_result`,
  `specialItemFlags`, `UpdateAllPhaseHealingAIStatus`, `SetupUnitInventoryAIFlags`; the first
  again after each act, cp_perform.c). Shape of the fix: do it where the phase's order is
  built (`aiOrder`) and in `strike`; the two functions need adding to `gen_symbols.py`. It
  changes play: its own PR, one suite at the end.
- **Still open in the looting read, cause untested:** the last read of each player phase has
  the looters attacking red units and taking no village (tags `keepai4`, `keepai6`). The
  phase-start setup is the first thing to test it against.

**Agreed with Nicolas (2026-11-13), not built: two tool changes so a probe costs minutes, not a suite.**
- `montecarlo.py suite --only <start_id>[/<seed>]`: play just those runs and judge nothing
  (no regressions, SC-003 or promotion). Today one run of interest costs all 56 (16 minutes).
  Where: `run_suite` builds `tasks` from `suite_tasks`; filter there and return before the
  judging. A held-out seed named this way prints only whether it came back with a game result.
- The guard lists every leak in one run: log each (`M.leaks`), put the bytes back, play on,
  and fail the run at its end. Today it raises on the first, so leaks surface one per pass.
- Neither changes how the bot plays, so neither needs a suite run. One small PR.

**The march from each unit's own turns was built and is NOT shipped** (branch
`feat/510-own-march`, ad247931, local only). On Ch7 it ends the 28-turn pocket and splits the
army from the lord, who then dies alone (tags `ownmarch1` against `ownmarch1ctl`). With PR
#604's dice main clears Ch7 clean on attempt 2 from both starts: Ch7 is no longer a wall.
The pocket itself is terrain: the river at (5,14) costs the lord her whole move (inferred from
her reach), so (5,15) is her only way in, and an ally stood on it. **Step 2 of the agreed
order is therefore the wrong base for item E; Nicolas has not been asked yet.** My
recommendation, his call (it is a weight): on a Seize map count the seizing unit's progress
above an escort's, so the plan that clears her tile wins.

**Probes are throwaway and gone** (written to the session scratchpad); the tags above are in
the vanilla store's `resume-runs.jsonl`. `story` names every enemy "the Archer" on vanilla Ch7
(seen, not looked into).

**PR #605 is merged** (2aa69c3c; Nicolas: "yeah merge", 2026-11-13), no open PR of this work.
ADR 0405 has the tables; the results are also a #510 comment of 2026-11-13.
- **What it does:** a judged plan for each ledger goal's offered Talk, Visit or chest no plan
  holds (`goal`); two plans without the Seize while a goal is `feasible` and every plan seizes
  (`noseize`: the first plan less its Seize, and every unit holding); and **no enemy phase is
  judged after the Seize**, nor the lookahead's. That last one was a judge error older than
  the PR: a unit at risk anywhere put the win over the cap.
- **What the runs say:** the beam no longer hides the act (confirmed on Ch9 4006 turn 11 and
  Ch8 4001 turn 16), and **neither chapter's result is better**. Ch9: the Talk plan is over
  the cap (30.8% the lord dies after it), same games as main's before. Ch8 4001 attempt 1: the
  bot waits turns 16 to 18 for the thief (Colm, charId 9) and seizes on turn 19 when he is at
  63.5%; 19 turns against 16, the same one death, the chests still missed. The other three Ch8
  attempts are the same games as before (the chests were already `stalled`).
- **The suite** on the final code: PROMOTED, 0 regressions (instrument `2374a75d5563+v2`, not
  refrozen); 7 of 56 runs play different acts, each with the same outcome, deaths and missed
  rewards.
- **Found, not built:** the ledger does not know a recruit can leave. Ch9's recruit (Amelia,
  charId 18) left the map in the enemy phase of turn 11 (`missed_recruits`: `left_map`); her
  row had no `closes_on`, so the plan played read `forfeits` 0.
- **Untested:** whether the judge error was behind the earlier late deaths on Ch8 (Colm,
  turns 17 to 23).
- **Names:** a unit is named from the decomp's `constants/characters.h` by its charId before
  any pronoun is used (the thief was written "she" for a day; Nicolas caught it).

**Item D's leads still open** (#510 comment 6842371541 has all of them): Ch7's pocket (4007):
the march's field is the lord's for every unit, so an ally sits on her one nearer tile for 22
turns. Ch8's west chests: the thief (Colm) is sent alone and stops short with enemy id 142 on his
road. Ch7 4005 turn 3 and the Ch9 flyer on turn 2: under the cap this phase, wounded and alone
the next (item F's case). Ch9's village: `closings` has an empty looter list from turn 2 on.
**The dump is kept, not merged:** local branch `probe/510-fwd1-d` (c7c27494), `PT_DPROBE=1`
before `montecarlo.py resume`; `DPROBE <json>` lines land in `workers/*.log`. Rebase it before
reuse.

**Asked by Nicolas (2026-11-13), answered from a code read, nothing measured:** the bot's item
handling is basic. It buys each unit the cheapest Vulnerary and the cheapest usable weapon of
each type it lacks (`Bot.shop`), picks a weapon per attack from the game's forecast, and sorts
a full bag. It never trades on the map, never takes from the convoy at prep, and does not plan
around weapon uses. Whether that has cost a run is not checked; a read of the kept records
(units ending a chapter with no usable weapon or no healing) would say.

**PR #604 is merged** (Nicolas: "Merge and handoff", 2026-11-12), no open PR of this work.
- Attempt k of a chapter start has the game's RNG moved on (k - 1) * 1009 draws, no re-seed;
  attempt 1 moves none. The stop "every style played" is gone: a chapter stops at the cap of
  12. `resume --attempts N` bounds it, and a run that hits a lowered cap ends `capped`.
- **One draw was not enough** (the first build): the game gave it back in turn 1 (59 draws
  against 60) and played the same game. The PR body has the tables. What drew one fewer is a
  lead only (the die per tied path direction, bmidoten.c:218-226). Not proven: that a
  1009-draw lead can never be given back. Nicolas was told both stay open (not item D's).
- The dice are in the record: `dice_advanced`, `dice_start`, and `rn` on each player phase's
  `progress` trace line.
- The frozen suite was NOT run, on purpose: it plays only attempt 1, which was frame-identical
  to main's in runs `call1c` and `call1d`.
- With different dice, vanilla Ch8 (campaigns 4001 and 4004, three attempts each) still has
  no clean clear: 5 won and 1 lost, none taking the chests.

**PR #603 (item C, ADR 0403) is merged** (Nicolas: "merge", 2026-11-12), no open PR of this work.
- CI green on its head, `/code-review` (high) and one scoped re-review applied,
  `suite --held-out` PROMOTED with 0 regressions.
- What it does: a progress record per player phase (a kill made in the player phase, a Visit,
  a Talk, a chest, a door or wall opened, the Seize, or a new low in turns for the objective's
  nearest unit or an open ledger goal's best taker); a ledger goal nobody nears over three
  WAITING player phases has a `stalled` row that no longer holds the win; sixteen player
  phases in a row with no progress end the attempt `stuck` (N = 16: Nicolas left the number to
  Fable); the Seize is always judged when the game offers it.
- Evidence (the PR body has the tables): vanilla Ch8, 24 attempts, went from 13 won and 10
  stuck to 20 won and 3 stuck, with half the emulated frames; no offered Seize is skipped
  without a reason. The frozen suite was not refrozen.
- **Nicolas has not confirmed one narrowing:** call 3 said "three phases"; the rule counts only
  waiting phases (no event, nobody nearer to anything), because counting every phase cost
  vanilla Ch4 seed 1001 its clean clear in the first suite run. He was told; no answer yet.

**What item C does NOT fix: no vanilla Ch8 attempt is a clean clear** (0 of 24, four runs).
- Every win misses the chests at (1,3) and (2,3), behind the door at (1,5): `never_offered`
  to any unit, or `stalled`. The door opens to the thief's Lockpick or to the Door Key the
  armor knight at (20,10) drops; no Chest Key is on the map (decomp, read by a subagent; lines
  in #510 comment 6828202335). Read the door first.
- 12 of the 13 wins that were already wins lose a unit, most often charId 9 late (turn 17 to
  23) on a plan over the cap, and charId 10 on turn 10 or 11.
- Three attempts still end `stuck` with the boss alive (campaign 4001 attempts 7 and 10,
  campaign 4004 attempt 2): no plan that kills the boss is under the cap.

**Next steps, in order.**
1. PR #606: Nicolas's "merge" (squash; CI is green on f7e1e002).
2. The two tool changes above, one small PR.
3. The phase-start AI setup in judged phases (finding 6), its own PR; prove it on single runs
   (`--only`, `PT_LEAKGUARD=1`), one suite at the end; test the end-of-phase looting read
   against it.
4. Ask Nicolas about the seizer's progress weight (below), then size item E on the shared
   field, not on per-unit marches. Item F's test as the plan wrote it.

**Three calls waiting for Nicolas.**
- Put one vanilla Ch8 start in the frozen suite, so a change to the wait rules needs one run,
  not two. Recommended. It changes what the suite measures.
- Fold the `idle_3` stall event into the new definition of progress (it still counts the
  lord's moves). Recommended, as its own PR: it changes what the suite's stall count means.
- The narrowing of call 3 above.

**Found while running, not looked into.**
- The suite's promotion check does not block a lost clean clear: the Ch4 village was found only
  by comparing `acts_hash` and `missed_rewards` with main's kept run of the same seed.
- A replay of a trace kept from before #603 can differ from its original under the new rules
  and then reports `matched = false` (read from the replay code by a subagent, not run).
- The five "dies, and lived when frozen" signals in the suite (`ours-ch02/1001`, `ours-ch03/1001`
  twice, `vanilla-ch5/1002` twice) are the same games as on main (`acts_hash` equal), not #603's.

**Not looked into.**
- The replay of campaign 4006's Ch9 start on #601 plays the same acts as run `fwd1`'s (four
  attempts compared act for act) but its frame counts differ a little (505261 against 505263;
  2354316 against 2353490). The suite's frames are identical.
- `tools/test_verdict_diff.py` failed twice on a clean local `main` (it lists the `tools`
  folder as an unlisted input) and passed on a later run; CI on main is green.

**Run `fwd1` (2026-11-11), for reference.** The eight vanilla campaigns all clear Ch6 and none
gets past chapter index 10: Ch7 (index 8) stops 4005 and 4010 (the lord dies on turn 4), Ch8
(index 9) stops 4001, 4004, 4007, 4009 (and 4002, whose "crash" was the lord's player-phase
death #601 now records as `lost`), Ch9 (index 10) stops 4006 (recruit and village missed).
Older scout walls still stand: `scout-ch13` loses 108 of 161, `scout-ch14` ends `stuck` on
turn 19, Ch5x (4003) stalls on turn 33.

**Key files:** `tools/playtest/sight.lua` (`s.look`, `s.walkers`, `s.reveals`, `s.after`,
`s.staged`), `tools/playtest/planner.lua` (the look block after "The look, in shadow";
`opts.unjudged`; `M.joinTurn`), `tools/playtest/bot.lua` (`M.explain`),
`tools/playtest/montecarlo.py` (`look_table`, `resume`, `story --why`), `tools/playtest/botrun.lua`
(`readNearest`, `closePhase`, `M.QUIET_BOUND`, `M.GOAL_QUIET`), `tools/playtest/goals.lua`
(`M.ledger`'s `stalled` rows), tests in
`test_bot.lua`, `test_sight.lua`, `test_montecarlo.py`. A Ch6 retry pair:
`montecarlo.py resume --game vanilla --tag <new> --campaigns cs-s4001 --chapter 7 --last 7`
(`--attempts N` caps it); `montecarlo.py look <trace dirs>` reads it.

- **Lessons:**
  - A plan kept in a trace's `considered` has its `rank` and `acts`: "was the plan judged, and
    why was it refused" is a read of the trace (`kind`, `rejected`, `rank.max_die`), no run.
  - The judge plays `sight.enemyPhase` on every plan it is not told to skip: when a plan's
    act ends the chapter, check the phase is not charged to it.
  - Stopping a run worked this session: `pkill -f "montecarlo.py suite"`, then `run.sh` and
    `mgba-headless`; a stopped suite leaves part of an instrument's runs in `runs.jsonl`.
  - Three runs at once (the suite and two `resume`s, 10 emulators) gave the same games as
    alone (`acts_hash` equal); they take longer, not timed.
  - The game's dice at a phase start are in the trace (`rn` on `progress` lines): "same dice?"
    and "how many draws did a turn take" are a read, not a run (count NextRN steps between two
    phases' words).
  - A harness change has no unit test: after one, replay a kept attempt and compare frames
    (`resume --campaigns fwd1-cs-s4001 --chapter 9 --last 9 --attempts 2`, about 10 minutes).
  - The frozen suite plays only attempt 1 (`chapter_tasks`): a change that only touches
    attempt 2 on cannot move it.
  - Start a `resume` and the suite at the same time: each works in its own `/tmp` folders and
    the suite's budget is counted in calls, not seconds (done once on 2026-11-12, no run without
    a game result). On a bot change run the suite FIRST: it is the shorter one (22 to 37
    minutes against 46 or more for the Ch8 set) and it caught what the Ch8 runs could not.
  - After a suite run, compare each tuning run's `acts_hash` and `missed_rewards` with main's
    kept run of that seed (`references/sim/<game>/<rom>/runs.jsonl`, the same `campaign`,
    `chapter`, `seed`, the older `instrument`): PROMOTED does not mean no clean clear was lost.
  - A subagent's test can pass on a hand-written row the real code never produces (#603: a
    ledger row with `unitId`): have the re-review check each fake's shape against its producer.
  - The Ch8 `resume` set is `--campaigns fwd1-cs-s4001,fwd1-cs-s4004 --chapter 9 --last 9`;
    its four kept runs are tags `fwd1c` to `fwd1c4` in `resume-runs.jsonl`.
  - A campaign's resumable start lives under the campaign that reached it: Ch8 and Ch9 starts
    are `fwd1-cs-s<seed>`, not `cs-s<seed>` (`resume` refuses and lists the indexes it has).
  - While a `resume` runs, a worker's live output is `/tmp/playtest-campaign@pool-*/`
    (`playtest.log`, and `mgba-stdout.log` for the BOTRUN lines); `workers/*.log` is written
    at the end. `resume` has no attempts cap on main: to read only the picks, stop it and kill
    `run.sh` and `mgba-headless`.
  - The chapter's talks (`Sight.talks`) are not its recruits: vanilla Ch8's six are
    conversations with player units or units who arrive on our side.
  - A worker log is megabytes of JSON lines: `grep` it, never `sed -n` a range of it.
  - The team pick's reasons are only in `references/sim/<game>/<rom>/workers/*.log`
    (`campaign: team`), not in the records or traces.
  - A trace keeps 5 to 7 plans a decision and no per-act offers: "was it offered" needs an
    instrumented run, not a read.
  - A record's `wall_s` is the campaign's; an attempt's is `run_s`. Equal `frames` on two
    attempts of one start means an exact replay.
  - **A probe's Lua table with both string keys and [1..n] is written as a JSON array**, the
    string keys lost: keep a probe's lists under a named key.
  - The beam's score gives a march no credit for ground gained: anything that picks "the
    beam's best" without the rank holds where the bot marches.
  - The look's enemy phase leaves red the active faction (`aiOrder`); set `PLAY_FACTION` back
    to blue before reading the board as our phase (bmidoten.c:780).
  - A function or constant board.lua adds must go in `Board.bind` too.
  - `sight.staged` isolates `seen`, `s.cache`, answer()'s village race and closings()' replays.
  - Prose check: "one of our units", never "one of ours"; "our units", never "ours".
  - In the turn between, a unit the plan holds has NO act in `st.acts`: "units still to act"
    is `ctx.actors` minus the acted, never "acts left".
  - Check a shadow step's result against what would refute it before building the next step.
  - A campaign builds a fresh bot for each attempt (`campaignApi`'s `api.play`): a switch set
    on the campaign's api never reaches botrun. Check a new switch's mark in the run's record.
  - A stopped `montecarlo.py` leaves its `run.sh` and `mgba-headless` workers running: kill
    those too, and check with `pgrep -fl mgba`.
  - Stopping a run with `pkill` is refused by the permission check in auto mode: before a
    long run, be sure the commit is the one to measure (review first, then the suite).
  - A commit's pre-commit takes over two minutes: run `git commit` in the background.
  - A playtest run reads the working tree's Lua: never edit Lua or switch branches while one
    runs. HANDOFF goes to main by plumbing (the branch's pre-commit refuses it).
- **From PR B (#599, merged), still open:** vanilla `scout-ch14` ends `stuck` on turn 19 in all
  16 kept runs (no deaths), untracked; Ch5x (4003) stalls on turn 33; Ch8's chests at (1,3)
  and (2,3) are never reached. None are deaths, so W1-W3 do not cover them (the design's "Not
  covered"). The campaigns' saved starts are untouched (`resume` copies them first).

## Where things stand

- **The parity model is being rebuilt: epic #510.** ch00-ch07 are unlocked and re-lock at its end
  (ADR 0354). Never widen an `accepted_residual` to get green.
- **#510 step 9, the difficulty instrument** (a bot plays the real ROM, both games; the plan is
  #510 comment 6563384310, ticked in place, spec 6563384018):
  - **Merged:** PR-A #558 (frozen suite), PR-B #559 (graded records), PR-C #560 (risk caps),
    PR-D #564 (goal ledger, no stalls), PR-E #568 (lookahead, retry memory), #570's fix #571
    (lookahead budget 128 an attempt, so the boss fight is no longer judged one phase deep), and
    PR-F #576 (a failure label needs a replayed witness: `montecarlo.py replay` / `audit`, ADR 0392).
    PR-F's answer to ours-ch03 seed 1002 unit 3: no evidence the hold caused it; every judged plan
    was over the cap, and the best alternative traded the death to unit 5. **PR-G #581** (ADR
    0395): the instrument is frozen in `tools/playtest/suite-frozen.json`. `suite` judges the
    tuning runs on it; `--held-out` adds the held-out seeds as counts plus the promotion result;
    `--freeze` refreezes; `--kept` re-judges kept runs. The fog start (vanilla Ch6) was added and
    three failing-decision snapshots load back to their boards in a fresh emulator. The
    surprise-replan rule stayed strict (no bot change). **PR-H #582** (ADR 0385, "Built
    (PR-H)"): `paired_verdict` now judges any protected death on attempt 1 with exact bounds
    (N = 24 in `instrument.cells`, ±10 margin); chapter cells, `pilot` and `cell`. The pilot
    (Manchego Stars ch03 vs vanilla Ch3, Nicolas's pick): Manchego Stars lost someone on 18 of
    50 first attempts, the twin on 0 of 50. Every death was a careful-style run; 6 of 50 (12%) were blind-spot
    deaths, over PR-I's 10% validity bar; and a seed only draws the style, so 50 seeds made 30
    distinct plays an arm. **PR-I #593** (ADR 0385, "Built (PR-I)") weighs both: a cell is
    NOT READABLE when a validity invariant fails.
  - **PR-E's open items are decided** (Nicolas, 2026-11-04; ADR 0389): the hold stays, the
    budget was raised instead of narrowing the boss trigger, the breach's "first crossing" is
    not built.
  - **Frozen suite** (instrument `ce1e3adb8c57+v2`, PR #587; same play as #585's): 14 starts, 56 runs, 25 min
    wall on 8 workers, 2,490,781 `AiDecideMain` calls (SC-003's baseline; the jump from 567,629
    is T100b's counter branches, accepted by Nicolas); every run has a game result; 4 of 28
    held-out runs lost. A bot change makes a new instrument: run `suite --held-out` and read its
    promotion line before trusting it.
- **On hold** (label `on-hold`, the hold comment says what reopens each): #565 (chipping a step
  back), #569 (placing a claim's wave in the lookahead).
- **Merged 2026-11-08:** #583 (ADR 0396: a bot decision is an ordering of the game's outcomes;
  only the game forbids), on Nicolas's "merge".
- **Merged 2026-11-07 after review, every finding fixed:**
  - **#578** (closed #577, ADR 0393): agent teams only for a named reason;
    `.claude/settings.json` holds the subagent prompt cache for an hour
    (`subagentPromptCacheTtl`, documented in Claude Code's settings reference).
  - **#580** (closed #579, ADR 0394): the pre-commit hook runs only the unit tests a staged
    path can reach. `run_tests.ReadRecorder` (audit hook) records each test's reads under
    `build/test-reads/`; a record whose reads moved since (mtime, size), a failing test, or an
    opaque one (a process it cannot see into) always runs. `test_difficulty.py` is dealt
    across three shards. A HANDOFF-only commit runs 22 of 130 test files. `make test`,
    `make check` and CI still run all of them. If the hook ever lets a broken test through,
    suspect a read the recorder does not see, and look at ADR 0394 first.
- **#574 merged (PR #575, ADR 0391):** a passing tagged run's `/tmp/playtest-<scenario>@<tag>`
  is deleted once its records are written; failing ones are kept (marked `FAILED`, newest 20);
  the per-run ROM is an APFS clone. The matrix drops a green verdict run's `/tmp` dir once the
  verdict cache holds it. If `/tmp` fills again, look there first.

## Next

0. **#510 PR A, first attempts**: merged (PR #598, ADR 0400).
1. **#510 PR B merged (#599).** **PR #600** (the boss goal, above) is open; **the look
   (W1-W3: comment 6786548233) is parked**. The bot plays vanilla forward first (above). Then tries to the first
   clean clear (its method goes to Nicolas as an ADR 0385 amendment first), **PR C** (a cell's
   dice, expected losses; small, no suite run) before any cell verdict, **#510 step 10** after.
   Still owed from PR-I:
   - **The pilot is ch02, not ch03**: no Manchego Stars campaign reaches ch03 (every one stops at
     ch02 on the chwinga finding), so `pilot --chapter 3` is refused. ch02 vs vanilla Ch2: every
     validity check holds; Manchego Stars lost someone 10 of 50, the twin 3 of 50; 0.63 CPU-h.
     `build/report-9d0b15b542e2-v2.md` predates #594 (it still prints the canary and human
     lines): regenerate it with `montecarlo.py report --post`, and **post it to #510 only on
     Nicolas's go-ahead** (T107). Clean clears in that pilot: Manchego Stars 0 of 50 (two chwinga die and
     the village at (12,3) is closed in every play), vanilla 35 of 50.
   - **Bot hash drift**: main's bot hash is `9d0b15b542e2`, the frozen suite's `ce1e3adb8c57`;
     #589's comment-only edits to the Lua moved it. Play is unchanged; a `suite --held-out`
     would refreeze it under the new hash.
2. **Chapter findings the bot made are owned by #510 step 10** (ch02's green chwinga, ch03's
   boss: bullets in the issue body; evidence in comment 6752603255 and on #547). Stop chasing
   them in the bot.
3. **#592** (found by #591): the ROM names ch03's grell boss (0xBF) and Icewind Brute (0xB6)
   "Monster"; the build writes no "Grell" text. Not checked in the emulator.
4. **Names in a story:** `montecarlo.py story`/`audit` read them from the build tree and print a
   note when the run played another ROM; build that ROM to read its names.
5. **Nicolas's stance (2026-11-09): stop chasing single deaths.** Judge a bot change by rates (the
   held-out counts, the pilot's Manchego Stars-vs-twin numbers), crashes, stalls and cost.
   **Decided:** a tuning-seed death flip is a signal, not a promotion blocker (T107a on the plan
   comment, built in PR-I with ADR 0395's amendment). Still to log on #510 as open: the over-cap
   order question (game over strictly first).
6. **Shelved, local:** `feat/510-t100b-counter-outcomes` (the reseat; its 162aa67c,
   `considered[].dies`, is worth porting), `feat/510-t100a-r`, `feat/510-lookahead-between-turn`
   (honest turn-between: right numbers, 4.6x cost), `park/510-t100a-pullback`.
7. Tell Nicolas where step 9 stands in plain words at the start of a session.

## Parked or owed elsewhere

- **Draft PR #485** (ch07 moves to Distant Blade's map): parked until #510's difficulty and roster
  work is done (Nicolas, 2026-10-28).
- **Nicolas's next playtest** owes the items on #31.
- **Chapter work:** #27 (ch07, waits on #486), #493 (the wiki's remaining findings), #486
  (planning the rest of the campaign with Nicolas).
- **Where a chapter stands** is `make chapter CH=chNN`, never this file.

## Before you touch anything

This list is the INDEX; do not re-inline the content.

- **How to work here** → `CLAUDE.md` / `AGENTS.md`.
- **Why anything is the way it is** → `docs/decisions.md` (index; open the two or three you need).
  Most likely to bite: *"Playtest runs are the most expensive thing in this repo"*, *"A scenario
  written against the old design will FAIL ON SUCCESS"*, *"An artifact is not its inputs"*, and
  for injector work 0300 and 0304.
- **What is left to build** → GitHub issues; #20–#28 per chapter; the open epics are #510 (parity) and #302
  (chapter as code).
- **Which asset the FE-Repo has** → `docs/fe-repo-scouting.md` (its table says where an anim
  LIVES, not what it does).
