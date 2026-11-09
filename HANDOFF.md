# Handoff - Manchego Stars live state

**Read this from main** (`git show main:HANDOFF.md`): on a feature branch this file is the copy
from when the branch was cut, and may be days old.

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`**; how-tos live in the files they are about;
operating rules in `CLAUDE.md`/`AGENTS.md`; findings, scope and backlog on GitHub issues. Nothing
here should still be true in a month. Before a context rollover, warn Nicolas, refresh this file,
and start a fresh instance; don't rely on auto-compaction.

Refreshed 2026-11-09, midday (Claude): **ship the T100b branch** (Nicolas: "push it and move
on"). T100b's counter branches cost the 4.6x calls (Nicolas accepts the cost: the suite is rarely
re-run). A new fix, the replan judges the rest of the plan in hand, cleared 3 of the 4 death
regressions. Next: one suite run, refreeze on this bot with Nicolas's OK, PR, review, merge.

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

1. **Ship branch `feat/510-t100b-counter-branch`** (local, not pushed, no PR; off main 09c350aa,
   now several commits behind: rebase on `origin/main` first). Holds 33538ed1 (T100b: the enemy
   phase on each way a counter leaves its attacker), d754facd (counter-kill attacks offered),
   5a936ef4 (over the cap, the next phase ranks first), bb3d7820 (ADRs 0384/0389/0396),
   5af47bb5 (`pilot --bench-vanilla`), and **59b44c66 (new, 2026-11-09): a replan judges the
   rest of the plan in hand** (`opts.rest`, kind `rest`; ADR 0384's bullet beside the advance;
   tests in `test_bot.lua` and `test_botrun.lua`, both fail without it). 1c350f2e is reverted.
   The findings and numbers are on #510's plan comment 6563384310, last bullets under T100b.
   Steps, in order:
   1. Rebase; `make test` green.
   2. One `suite --held-out` run (~25 min). Tell Nicolas the death rates in plain words (held-out
      lost N of 28, vs 4 of 28 frozen), not each death.
   3. It will refuse promotion (cost, and vanilla-ch5/1002's death). **Ask Nicolas for "refreeze
      anyway"**; on his yes, write the new baseline (`suite --freeze` writes only when promoted,
      so the override must be explicit and recorded in ADR 0395 with why) in the same PR.
   4. PR, `/code-review <PR> medium` by a separate reviewer (subagent), fix every finding, CI on
      the head sha, merge (step 9 PRs merge after review + CI).
   **What is already known (do not re-derive):** the cost is all 33538ed1 (5.3x enemy phases
   judged, same decisions); vanilla-ch5/1002 Natasha's death is honest risk plus ADR 0384's
   over-cap order (game over ranks first: a 6.85% lord risk lost to a 62% Lute risk); ours-ch03/
   1002 now wins t23 with no deaths; vanilla-ch5/1001 wins (Lute dies to a fogged killer).
2. **Nicolas's stance (2026-11-09): stop chasing single deaths.** Judge a bot change by rates (the
   held-out counts, the pilot's ours-vs-twin numbers), crashes, stalls and cost. Proposed, not
   decided: make a tuning-seed death flip a thing to read, not a promotion gate (ADR 0395); log
   the over-cap order question (game over strictly first) on #510 as open, not blocking.
3. **The ch03 finding is owned by #510 step 10** (its ch03 bullet in the issue body; evidence for
   #547 on #547). Ours ch03's boss: 36 HP vs Bazba's 25, hits our army for a mean 14 (up to 16)
   vs Bazba's 8.6 on vanilla's, same throne heal. Stop chasing ch03 deaths in the bot.
4. Then T100c, T100d (**still unanswered**: ask Nicolas), T100e, then T100-T108 and PR-J, then
   #510 step 10.
5. **Shelved, local:** `feat/510-t100b-counter-outcomes` (the reseat; its 162aa67c,
   `considered[].dies`, is worth porting), `feat/510-t100a-r`, `feat/510-lookahead-between-turn`
   (honest turn-between: right numbers, 4.6x cost), `park/510-t100a-pullback`.
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
