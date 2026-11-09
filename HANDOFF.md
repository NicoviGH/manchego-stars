# Handoff - Manchego Stars live state

**Read this from main** (`git show main:HANDOFF.md`): on a feature branch this file is the copy
from when the branch was cut, and may be days old.

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`**; how-tos live in the files they are about;
operating rules in `CLAUDE.md`/`AGENTS.md`; findings, scope and backlog on GitHub issues. Nothing
here should still be true in a month. Before a context rollover, warn Nicolas, refresh this file,
and start a fresh instance; don't rely on auto-compaction.

Refreshed 2026-11-09, evening (Claude): **T100b is PR #585, refrozen on Nicolas's override;
next, review it and merge.** The suite run (held-out 4 of 28 lost, none new; tuning 3 of 28 lost
and 13 protected deaths, both as frozen) refused on two vanilla-ch5 deaths and cost; Nicolas said
"refreeze anyway", recorded in `suite-frozen.json` (`override`) and ADR 0395.

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

1. **Review and merge PR #585** (branch `feat/510-t100b-counter-branch`, pushed, rebased on main
   this session; `make test` green). Holds T100b's counter branches, the counter-kill attacks,
   the over-cap order (next phase first), the replan's rest of the plan in hand, `pilot
   --bench-vanilla`, ADRs 0384/0389/0396, and the refreeze. **New in it:** `suite --freeze
   --override WHY` (`montecarlo.py` `freeze_record`, test in `test_montecarlo.py`
   `test_a_freeze_needs_every_run_and_a_promotion`), and ADR 0395's override rule plus its
   "Refrozen on an override" bullet. Steps: `/code-review 585 medium` by a separate reviewer
   (subagent), fix every finding with `review-to-clean`, CI on the head sha, merge (step 9 PRs
   merge after review + CI). Squash drops the 86abf243/d7dad9ca experiment and its revert.
   **Do not re-run the suite for the review**: the refreeze is from this head's kept runs
   (instrument `4385f97ef0f3+v2`); a reviewer fix to bot code changes the instrument, and then
   one `suite --held-out` decides whether it needs another freeze.
   **Known, do not re-derive:** the new SC-003 baseline is 2,487,135 calls (all T100b's counter
   branches, 5.3x the enemy phases judged; Nicolas accepts the cost). vanilla-ch5/1001's new
   death is Lute (0x0C), a fog death (`unrevealed_killer`, read 0.0%), Eirika lives;
   vanilla-ch5/1002's is Natasha (0x0D), honest risk the frozen bot survived on a 93% roll.
2. **Nicolas's stance (2026-11-09): stop chasing single deaths.** Judge a bot change by rates (the
   held-out counts, the pilot's ours-vs-twin numbers), crashes, stalls and cost. Proposed, not
   decided: make a tuning-seed death flip a thing to read, not a promotion gate (ADR 0395); log
   the over-cap order question (game over strictly first) on #510 as open, not blocking.
3. **The ch03 finding is owned by #510 step 10** (its ch03 bullet in the issue body; evidence for
   #547 on #547). Ours ch03's boss: 36 HP vs Bazba's 25, hits our army for a mean 14 (up to 16)
   vs Bazba's 8.6 on vanilla's, same throne heal. Stop chasing ch03 deaths in the bot.
4. Then, on #510's plan comment 6563384310: T100c (the recorder's phantom enemy `wait`), T100d
   (**still unanswered: ask Nicolas** whether the grade reads the plan's two-phase chance), T100e
   (several starts per chapter cell, each its own campaign), then T100-T108 and PR-J, then #510
   step 10. Tick T100b in the plan comment once #585 merges.
5. **Shelved, local:** `feat/510-t100b-counter-outcomes` (the reseat; its 162aa67c,
   `considered[].dies`, is worth porting), `feat/510-t100a-r`, `feat/510-lookahead-between-turn`
   (honest turn-between: right numbers, 4.6x cost), `park/510-t100a-pullback`.
6. Tell Nicolas where step 9 stands in plain words at the start of a session. **When a log
   gives a character ID, name it from `fireemblem8u/include/constants/characters.h` and add
   nothing you have not read** (this session called Lute a Pegasus Knight from memory).

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
