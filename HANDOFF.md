# Handoff - Manchego Stars live state

**Read this from main** (`git show main:HANDOFF.md`): on a feature branch this file is the copy
from when the branch was cut, and may be days old.

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`**; how-tos live in the files they are about;
operating rules in `CLAUDE.md`/`AGENTS.md`; findings, scope and backlog on GitHub issues. Nothing
here should still be true in a month. Before a context rollover, warn Nicolas, refresh this file,
and start a fresh instance; don't rely on auto-compaction.

Refreshed 2026-11-08, evening (Claude): T100a-R built and piloted on ch03 with no effect (and one
spike reverted); ADR 0396 (how a bot rule is written) is PR #583, reviewed. Next: a fresh session
investigates why careful has no plan under its cap on ch03's boss fight.

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

1. **Investigate careful on ch03, from records only (no new runs first).** Nicolas's order
   (2026-11-08): style first (done, #583), then this, in a fresh context. Question: on careful's
   death turns, why was **no** plan under the 1% cap? Read the pilot's plan records (each death's
   `plan_ref` → the trace's plan entry: `considered`, `protected`, `audit.offered_n`, what
   `Bot.candidates` refused). Turns: game B (12 runs; any careful seed but game A's six) turn 11 (unit 4, 0.79) and
   turn 21 (unit 5, 0.91); game A (seed 3001) turn 22 (unit 28) and 26 (the lord). Records:
   `references/sim/ours/fd3cb9d8dca6/runs.jsonl`, instrument `bc53967aab08+v2` (T100a-R) and
   `e6fc3854f2a3+v2` (main); `montecarlo.py story <trace> --turn N` narrates a turn.
   - **First lead:** `bot.lua`'s counter refusal (`spent < u.hp`, every style but greedy) means
     the cap never sees counter risk, so careful near the boss may be left only bad moves (ADR
     0396 "Known breaks"; research record 0025). **Second:** turn-start fort/throne heals are not
     modelled, so holding on one reads as waiting for nothing. Changing the refusal changes play:
     **Nicolas's call**, then one pilot, then the frozen suite (`suite --held-out`) before keeping.
   - Write every fix as ADR 0396 says: an ordering or price over the game's outcomes, no ban,
     no chapter named; check every style, turns to win, and the suite, not only ch03.
2. **The T100a-R branch** (`feat/510-t100a-r`, commit 62d0c023, local only, not pushed, no PR):
   the lookahead's turn between plays our units' blows; the cap gives way to a striking plan when
   the plan under it only waits (`COMMIT_OVER_CAP`). **Piloted: no change** (18 of 50 deaths both,
   bold and even identical, the commit never fired; ADR 0384's "Piloted" bullet on that branch).
   Hold it until step 1 says whether it earns its place. Owed before review: the rewrites listed
   on the plan comment's T100a-R (ADR 0396). Its first pilot found a real bug, fixed
   (`Sight.betweenMay`): a strike between phases could kill one of ours unseen.
3. **PR #583 (ADR 0396 + research record 0025)**: reviewed at medium, every finding fixed
   (docs/comments only, no re-review). Needs CI on its head and **Nicolas's "merge"** (not covered
   by the step-9 standing OK: it is a docs PR, not PR-A..J).
4. Then T100b (the enemy phase branches on our counter: Wolfram, turn 16, is still dying), T100c,
   T100d (**still unanswered**: ask Nicolas), T100e, then T100-T108 and PR-J, then #510 step 10.
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
