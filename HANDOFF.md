# Handoff - Manchego Stars live state

**Read this from main** (`git show main:HANDOFF.md`): on a feature branch this file is the copy
from when the branch was cut, and may be days old.

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`**; how-tos live in the files they are about;
operating rules in `CLAUDE.md`/`AGENTS.md`; findings, scope and backlog on GitHub issues. Nothing
here should still be true in a month. Before a context rollover, warn Nicolas, refresh this file,
and start a fresh instance; don't rely on auto-compaction.

**Next session starts here (2026-11-11, late): items A and B of the fwd1 plan are built and in PRs; C is next.**
Nicolas (2026-11-11): "right now we're focused on getting the bot to play vanilla". Fable owns
the direction; use cheaper subagents to check source, ADRs and research before claiming or
building. The plan is **#510 comment 6810567866** (six items A to F, six calls, all approved);
its findings are comment 6810177817.

**Open PRs (a stack; neither merged, both waiting on Nicolas's "merge").**
- **PR #601, item A: the attempt's record says what happened** (`feat/510-fwd1-a-records`,
  three commits, CI green on the first two; check the third, `c5b1495f`). No change of play:
  the suite's 28 runs have the same frames as main's. Reviewed (`/code-review medium`, six
  findings) and re-reviewed by an independent reviewer; every finding closed. ADR 0388 amended.
  What it changes: a lord felled by our own act is `lost` (the plan was wrong that the check
  was missing: the game-over screen starts only after the death quote, so the check came too
  early); a red unit is killed only when the game says so, and a recruit a script removed is
  `left_map`; `unreachable` is `never_offered`; a razed village has its `closed_by`; the record
  carries `team` (the prep screen's pick), `player_phases` and `acts_hash`.
- **PR #602, item B: the team pick covers the scarcest demand first** (ADR 0402,
  `feat/510-fwd1-b-team-pick`, based on #601's branch). Witness: the thief is fielded in 6 of 6
  replayed Ch8 attempts (campaigns 4001 and 4004, tag `b2`). **Still owed on #602:
  `montecarlo.py suite --held-out` with its promotion line, and `/code-review 602 medium`.**
  When #601 merges, retarget #602 to `main` before deleting #601's branch.

**Evidence turned against one approved part: the Talk demand (call 4's second half).** Built,
refuted at vanilla Ch9's prep screen by one probe, and removed (ADR 0402 has it): the recruit
(charId 18) is not on the board at the prep screen, and the lord, who is forced, is one of her
two talkers, so a Talk demand cannot field the second (charId 4). **Nicolas has not answered
this yet.** Fable's recommendation: leave it dropped and let item D's instrumented run say
whether any fielded unit can reach her before turn 12 (calls 5 and 6).

**What the new records already show.**
- Campaign 4006's Ch9 start: its 8 attempts are 4 games (`acts_hash`: attempts 2, 5, 8 are
  one; 3 and 4; 6 and 7). Call 1 (advance the dice per retry) is not built.
- Ch8 with the thief fielded: still no clean clear in 6 attempts. The chests at (1,3) and
  (2,3) are `never_offered`, and two attempts end `stuck` (one after 406 player phases). That
  is items C and E.

**Next steps, in order.**
1. Finish #602: the held-out suite, then `/code-review 602 medium`, fix every finding.
2. **Item C** (a wait that gains nothing ends; calls 2 and 3; amends FR-015, so an ADR).
   First compute, offline over the kept winning traces, the longest run with no progress, and
   propose N with that table.
3. **Call 1** (retries get different dice), then **item D** (one instrumented run on each of
   two starts), then E and F as the plan sizes them.

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
`tools/playtest/montecarlo.py` (`look_table`, `resume`, `story --why`), tests in
`test_bot.lua`, `test_sight.lua`, `test_montecarlo.py`. A Ch6 retry pair:
`montecarlo.py resume --game vanilla --tag <new> --campaigns cs-s4001 --chapter 7 --last 7
--attempts 2` (~3.5 min); `montecarlo.py look <trace dirs>` reads it.

- **Lessons:**
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
