# Handoff - Manchego Stars live state

**Read this from main** (`git show main:HANDOFF.md`): on a feature branch this file is the copy
from when the branch was cut, and may be days old.

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`**; how-tos live in the files they are about;
operating rules in `CLAUDE.md`/`AGENTS.md`; findings, scope and backlog on GitHub issues. Nothing
here should still be true in a month. Before a context rollover, warn Nicolas, refresh this file,
and start a fresh instance; don't rely on auto-compaction.

Refreshed 2026-11-10, evening (Claude): **PR 1 (retries that learn) is built and witnessed on
branch `feat/510-retry-memory` (commit 73948dd6, local, not pushed, no PR). It is waiting on
Nicolas's call about a different retry rule.** Everything is in ONE comment, #510 comment
6776176601 (edited in place; its last two sections are this session's). Read it first.
- **Built on the branch** (ADR 0399 drafted; unit tests added, each checked to fail without
  its fix): `style.memory` (enemies seen + killers, by slot and character; every death), a
  remembered enemy plays in the judged phases in fog (`Sight.plays`, `plan.known`, `Bot.known`),
  a green lost before is a guard goal (`Goals.guarded`, `Goals.PULLS`) with a march in
  `exploring`, `MAX_ATTEMPTS = 12` with styles redrawn, and `montecarlo.py resume` (carry
  campaigns on under `<tag>-<campaign>`, records in `resume-runs.jsonl`).
- **Harness fix found by the witness:** FE8's fog ambush (bmidoten.c: a move onto a hidden unit
  halts, `UNIT_ACTION_TRAPPED`, no command menu; the last unit's ends the phase). Before this
  fix the harness crashed with "the move failed". Now `moveUnit(..., haltOk)` returns
  `"trapped"` for the bot's `api.act` only, and botrun takes it as the act's end. This is very
  likely 4008's Ch8 attempt 5 crash too (not re-run). Proven on 4007: 6 halts, no crash.
- **Witness (Ch6, 4001 and 4007, 12 attempts each, in sequence):** attempt 1 is unchanged.
  The fog deaths every old retry repeated are gone (H1 holds), but over-cap deaths replace
  them. **The Civilian (unit 65) dies on turn 8 in all 17 won retries**: the guard goal is in
  the plans and a unit is sent, but the march is never taken (why is untested). **Retries
  become reruns** once the memory stops growing (the bot is deterministic): 4001 attempts 5 to
  12 are three games repeated. 4007's `careful` style got `stuck` (50 turns) twice, cause
  untested. Both campaigns: no clean clear, `bot_fault`.
- **Open for Nicolas (asked; not answered):** he asked why the bot doesn't "try different
  things" like a player. Proposal on the comment: **a retry changes the decision behind the
  earliest death of the last attempt** (plays another plan the planner judged there; every
  earlier turn the same), in place of redrawing a style; `montecarlo.py replay` (PR-F)
  already swaps one decision. Build it in PR 1, or land PR 1 as built first?
- **`suite --held-out` has NOT run** on the branch: the first run was stopped when the harness
  changed under it (it may have left partial records). Run it once the code is final.
- **Lessons:**
  - The pool prints a campaign's attempts only when its worker ends; `resume` of one campaign
    to the cap takes about 1 h (Ch6, 12 attempts).
  - A worker reads harness/botrun at launch: editing them mid-run mixes versions. Stop the run
    first.
  - HANDOFF is refreshed on main only; the branch's pre-commit refuses it.
  - Earlier lessons still hold: `starts` skips pinned seeds; trace numbers are game chapter ids
    (5 = Ch5x, 6 = Ch5); vanilla Eirika ids 9 = Ch8, 10-21 `E_9`..`E_21`, 22 `E_21X`.
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

0. **Fable review first (Nicolas asked, 2026-11-10; there are Fable credits).** Before building
   more, start a Fable session (`claude-fable-5-2`) and give it a GOAL, not our questions (so
   it isn't anchored on our framing):
   - **Goal:** #510's north star, a trustworthy difficulty model. A bot plays the real ROM, both
     games, so Manchego Stars' chapters can be judged against vanilla FE8's. On vanilla, which
     strong players clear clean, the bot must clear every chapter of Eirika's route clean
     (ADR 0376). A chapter it can't clear is the bot's fault, never the chapter's. Today it
     stops at Ch6 in 8 of 10 campaigns. Ask what Fable would change to get there, and what in
     the approach so far it would keep, drop or rethink.
   - **Context to point it at:** the #510 issue body and plan comments 6563384018 (spec),
     6563384310 (step 9 plan) and 6776176601 (this week: the findings, the witness, the open
     retry proposal); `docs/decisions.md` (ADRs 0376 and 0384 to 0399 are #510's);
     `tools/playtest/{campaign,botrun,planner,goals,bot,sight}.lua`; the branch
     `feat/510-retry-memory`; `AGENTS.md`.
   - **Constraints to state:** the bot knows only what a player sees (never a dice result);
     attempt 1 is the measured one (ADR 0385); playtest runs are expensive (AGENTS.md);
     Nicolas's standing rules in AGENTS.md.
   - **What comes back:** a short written recommendation for Nicolas. Bring it to him; don't
     build on it unasked.
1. **#510: PR 1, retries that learn** (above): get Nicolas's answer on the retry rule; build
   it, or not; find why the guard march to the Civilian is never taken (one instrumented run on
   4001 Ch6); then `suite --held-out`, a PR, `/code-review <PR> medium`, and
   `resume --game vanilla --tag <t>` to carry the 10 campaigns on. Then PR 2 (tries to the first
   clean clear; its method goes to Nicolas as an ADR 0385 amendment first). **#510 step 10**
   after.
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
