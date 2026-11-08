# Handoff - Manchego Stars live state

**Read this from main** (`git show main:HANDOFF.md`): on a feature branch this file is the copy
from when the branch was cut, and may be days old.

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`**; how-tos live in the files they are about;
operating rules in `CLAUDE.md`/`AGENTS.md`; findings, scope and backlog on GitHub issues. Nothing
here should still be true in a month. Before a context rollover, warn Nicolas, refresh this file,
and start a fresh instance; don't rely on auto-compaction.

Refreshed 2026-11-08, night (Claude): the careful-on-ch03 investigation found four causes (on
#510 plan comment 6563384310, under T100b); a tile fix was piloted and not kept as is. Nicolas:
"we're chasing this in circles". Next: check whether the bot's death numbers near the boss are
right, from records only, before any more fixes.

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
    (ours ch03 vs vanilla Ch3, Nicolas's pick): ours lost someone on 18 of 50 first attempts,
    the twin on 0 of 50. Every death was a careful-style run; 6 of 50 (12%) were blind-spot
    deaths, over PR-I's 10% validity bar; and a seed only draws the style, so 50 seeds made 30
    distinct plays an arm. PR-I has to weigh both.
  - **PR-E's open items are decided** (Nicolas, 2026-11-04; ADR 0389): the hold stays, the
    budget was raised instead of narrowing the boss trigger, the breach's "first crossing" is
    not built.
  - **Frozen suite** (instrument `e6fc3854f2a3+v2`): 14 starts, 56 runs, 642.6 wall s on 8
    workers, 567,629 `AiDecideMain` calls (SC-003's baseline now, budget 681,154); every run has
    a game result; 4 of 28 held-out runs lost. A bot change makes a new instrument: run
    `suite --held-out` and read its promotion line before trusting it.
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

1. **Break the circle: check the bot's death numbers against what happened (records only, no
   runs).** Three changes (pull-back, T100a-R, the reseat) each fixed one ch03 death and exposed
   another, all by changing which plans are offered, while every plan near the boss reads 80-95%
   death. The exact check, its inputs and how its answer decides the next step: #510 plan comment
   6563384310, the last bullets under **T100b** ("Next, decided with Nicolas"). Report it to
   Nicolas in plain words before building anything.
   - Findings so far (same place): the turn-11 heal lost its one tile; a unit left out of a plan
     for want of a tile; no judged plan ever pulls everyone out of the boss's reach; the second
     phase's hold. **Cause 1 (counters averaged) was wrong and is withdrawn**: `judge` chains the
     counter on real HP (`struckIn`). Read the code before saying what it does.
   - The Mogall attacks only from 14,1, range 1-2 (319 of 319 attacks over 60 traces); the
     recorder's moving `from` is T100c's stale `from`.
2. **Branch `feat/510-t100b-counter-outcomes`** (local, not pushed, no PR): b0c5a099 seats a hold
   or heal on its next free tile (`Bot.reseat`); piloted 21 of 50 lost (main 18): careful game B
   saved, careful game A stalls out of reach (6 of 6 `stuck`), bold 13 of 22 lose Baxby on turn
   13 (witnessed: the boss fight's, not a misplaced seat). 162aa67c records each judged plan's
   units at risk (`considered[].dies`), no play change, keep either way. Waits on step 1.
3. **The T100a-R branch** (`feat/510-t100a-r`, 62d0c023, local): shelved, no effect.
4. Then T100b as written (the AI's target choice on real boards), T100c, T100d (**still
   unanswered**: ask Nicolas), T100e, then T100-T108 and PR-J, then #510 step 10.
5. **Tried and dropped 2026-11-08** (so nobody retries it): ranking "chance to end the chapter"
   right after "game over" among plans over the cap. ch03 pilot: 40 of 50 runs lost someone (bold
   lost the lord on turn 14 in 13 of 22), careful unchanged. Reverted, never committed. Output:
   `build/pilot/ch03-pilot-complete.txt`.
6. Tell Nicolas where step 9 stands in plain words at the start of a session.

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
