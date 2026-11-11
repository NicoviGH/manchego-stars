# Handoff - Manchego Stars live state

**Read this from main** (`git show main:HANDOFF.md`): on a feature branch this file is the copy
from when the branch was cut, and may be days old.

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`**; how-tos live in the files they are about;
operating rules in `CLAUDE.md`/`AGENTS.md`; findings, scope and backlog on GitHub issues. Nothing
here should still be true in a month. Before a context rollover, warn Nicolas, refresh this file,
and start a fresh instance; don't rely on auto-compaction.

**Next session starts here (2026-11-11, PR B in review).** **#510 PR B is PR #599**
(branch `feat/510-pr-b-retry-memory`, ADR 0399; not merged). Read #599 and #510 comments
6786147872 (the campaign rerun), 6786005697 (late-game deaths) and 6786548233 (Fable's design).
- **What #599 does:** a retry remembers every enemy earlier attempts showed and every killer
  (by slot, character and class, `Board.memoryKey`); `sight.remember`/`knows` and
  `Board.playsAsSeen` are the one owner of "counts as seen" (judged phases, danger maps lifted,
  exposure via `ctx.threats`, keySources, closings, the lookahead's boss trigger, `plan.enemies`).
  12 tries a chapter start; a try already played (same style, same memory) is never spent
  again. `montecarlo.py resume`. Guard goal and deadline dropped (Nicolas). The fog read's
  enemies seen stay this attempt's.
- **Proof so far:** each new test fails without its fix; all 130 test files pass; attempt 1
  played event for event as main on `scout-ch6`, `vanilla-ch5`, `ours-ch02` (seeds 1001, 1002)
  after the first fix round. **Still owed when this session ended:** (a) the same six-start
  check on head `ba1db30b` (it was running: driver at the scratch path below; rerun it if its
  result is not on #599), (b) a scoped re-review of `ba1db30b` (a fresh subagent was running;
  its 10 verdicts are not recorded anywhere: run `/code-review 599 medium` on the fix commit
  again if unsure), (c) CI on the head, then merge (step 9 PRs merge after review + CI, his
  standing permission).
- **The rerun (`prb2`, before the review fixes):** all 10 vanilla campaigns stop at the cap.
  Ch6: memory ends the fog ambush (6 blue deaths in 78 retries vs 9 in 8 first attempts), but
  the villagers die on every retry (the Bael, turns 8-12; the horizon). Ch5x (4003): 4 of 12
  `stuck` on turn 33. Ch8 (4008, 4009): the chests at (1,3) and (2,3) unreached in every
  deathless win. Step 4 ("retries that differ") is not needed as a rule.
- **Next after #599 (Nicolas, 2026-11-11): ask Fable to EXPAND its design to scale** (comment
  6786548233: a retry watches the enemy that killed and plays the loss forward; retries only;
  a shadow run that can refute it). As designed it covers only Ch6's kind of loss, an unseen
  walker onto someone we must protect. What it does not scale to (comment 6786005697 and this
  session's read): **(1) over-cap trades the bot measured**, most late-game deaths (Ch5 28 of
  40, Ch10 8 of 8, Ch13 21 of 25): a retry should learn "that attack was a mistake", not only
  "who killed"; **(2) reinforcements**: a wave's killer cannot be watched until it is on the
  map (the look-ahead places no arrival; a retry knows the wave's turn, ADR 0386, not its
  route); **(3) cost on big maps**: the look plays every known enemy several phases deep, so
  its cost grows with units x depth (the +15 to 23% estimate is Ch6's only). Goal in his words:
  "emulate human players learning from their mistakes and losses". Give Fable the comment, the
  late-game table and these three gaps; Fable designs, Opus builds. His two open calls on the
  comment (the assignment; retries only) wait for the expanded design.
- **New, untracked:** vanilla `scout-ch14` ends `stuck` on turn 19 in all 16 kept runs (no
  deaths). Not checked against existing issues beyond #510's comments.
- **How the witnesses were played:** `montecarlo.py resume --game vanilla --tag <t>` (one tag a
  run; a taken tag is refused). Six-start attempt-1 check: a 25-line scratch driver around
  `pinned_setup` + `chapter_tasks(..., 'tuning')` + `Pool`, its traces compared on act, event
  and death lines with PR A's kept traces (`84d8eba48d70+v2`). Not kept.
- **Lessons:**
  - A function board.lua adds must also go in `Board.bind`: the emulator hands sight the bound
    table (the first rerun, `prb`, crashed on every attempt 2 for this).
  - Most enemies share one generic character id (0x80 is no named `CHARACTER_`): slot +
    character does not identify a unit; class too.
  - `tools/callsites.py` reads Python only; for Lua, sweep callers with `rg`.
  - `/code-review` must run in a fresh subagent (review-to-clean): the author's own inline pass
    missed 10 findings the independent one found.
  - A playtest run reads the working tree's Lua: never switch branches while one runs (this
    HANDOFF was committed to main by plumbing for that reason).

Earlier the same night (Claude, Fable session): **the Fable review is done and its plan is
locked by Nicolas: two PRs and one suite run, then a small third PR before any cell verdict.
The plan is ONE comment, #510 comment 6779357154
(edited in place; it has the findings, both PRs' steps and a file map). Read it first.** Nothing
was built or run in the emulator this session.
- **What the review found** (detail and witnesses on the comment): fog is read as empty ground
  by every danger estimate and by admission; the bot has no way to pull back together and makes
  no further plan when none is under the cap; an enemy-phase death is graded by the phase's
  last plan, so some fog deaths read `over_cap`; retries are reruns.
- **Read from the kept runs the same night** (offline; tables on the comment): 2,750 kept
  vanilla traces are 490 distinct games. The bot's death chances are about right where it gives
  one (37% predicted, 34% died; 70%, 73%), so the enemy phase's prediction gets no fix. Ch5's
  wall is plans the bot knows are over the cap (81 of 110 blue deaths); Ch6's is fog (21 of 42,
  plus 5 exposed after they moved). Ch5's 18 deaths at a predicted 0 with the killer in sight
  have no named cause yet.
- **The verdict method was reviewed too** (PR C on the comment): a chapter cell's seed draws
  only the style, the dice are the start state's (`b.seed` is a no-op in campaign mode), so a
  cell's pairs are far fewer distinct games than they count; proposed: seed a cell
  replicate's dice, report expected losses beside the any-death rate, read a cell by its
  interval since `EQUIVALENT` at +/-10 will rarely be reached.
- **Nicolas confirmed the goal:** winning clean is his proxy for "the bot is capable", as a
  human is after retries and learning. Clean clears stay the campaign's carry-on rule.
- **Nicolas approved every call the comment proposes** (2026-11-10, "yes I approve all";
  each PR records its own as an ADR): the
  fog rule (a unit beside unseen ground is judged against one strike from the strongest enemy
  seen so far), the regrade (a death graded by the plan that moved its unit), and a cheap proof
  in place of a suite run for the retries-only PR.
- **`feat/510-retry-memory`** (commit 73948dd6, local, not pushed, no PR; ADR 0399 drafted) is
  kept as the source for both PRs: its fog-ambush harness fix (`moveUnit(..., haltOk)` returns
  `"trapped"`) goes into PR A, its retry memory into PR B. Its guard march is reworked in PR B
  (the guard targets the green's tile, is barred as stuck once adjacent, and is re-picked at
  every replan). `suite --held-out` has NOT run on it. The earlier Ch6 witness (4001 and 4007,
  12 attempts each) is on #510 comment 6776176601.
- **How to work it cheaply** (agreed with Nicolas): a fresh session a PR, started from the plan
  comment; Opus for the building; Fable comes back for two reads only (the comment's
  "Where Fable comes back in"): PR A's stepping-back witness on the Ch5 starts, and PR B's
  campaign rerun; never read the five bot files whole (435 KB: use the comment's file map and
  `sed -n`); scripts read the runs, not a model; unit tests on the fake board before any
  emulator run; while working, only the starts a change can touch (Ch5 starts, the Ch6 fog
  start); the full suite once, on PR A's final code.
- **Lessons:**
  - The pool prints a campaign's attempts only when its worker ends; `resume` of one campaign
    to the cap takes about 1 h (Ch6, 12 attempts).
  - A worker reads harness/botrun at launch: editing them mid-run mixes versions. Stop the run
    first.
  - HANDOFF is refreshed on main only; the branch's pre-commit refuses it.
  - Earlier lessons still hold: `starts` skips pinned seeds; trace numbers are game chapter ids
    (5 = Ch5x, 6 = Ch5, 7 = Ch6); vanilla Eirika ids 9 = Ch8, 10-21 `E_9`..`E_21`, 22 `E_21X`.
  - The "25 min" suite wall below is not reconciled with `suite-frozen.json`'s `wall_s`
    (2,296 s tuning, 4,313 s held-out; perhaps summed over workers). Unchecked.
- **The campaigns' saved starts** are untouched (resume copies them first): the 9 stopped
  ones at `states/cs-s<seed>/7.ss` (4003's `5.ss`), 4008 at `states/full-s4008/9.ss`. The
  witness's state copies were deleted; its traces and records are kept.

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
1. **#510 PR B, retries: PR #599** (above). Finish the owed checks, merge. Then **Fable expands
   its design to scale** (above: over-cap trades, reinforcements, cost), then it is built as its
   own PR after Nicolas's calls. Then tries to the first
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
