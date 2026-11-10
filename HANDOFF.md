# Handoff - Manchego Stars live state

**Read this from main** (`git show main:HANDOFF.md`): on a feature branch this file is the copy
from when the branch was cut, and may be days old.

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`**; how-tos live in the files they are about;
operating rules in `CLAUDE.md`/`AGENTS.md`; findings, scope and backlog on GitHub issues. Nothing
here should still be true in a month. Before a context rollover, warn Nicolas, refresh this file,
and start a fresh instance; don't rely on auto-compaction.

Refreshed 2026-11-10, evening (Claude): **the vanilla route work (#510) is under way.** Step 9 is
closed (PR-J merged as #595, squash cd9bb060). The plan is #510 comment 6758779876; the results so
far are comment 6770045525. Known stops from `starts --game vanilla` (seeds 4001-4010, comment
6751678084): Ch5x's two chests (7 of 10 campaigns), Ross on Ch2 (2), Colm on Ch3 (1).
- **PR #596 is open and ready for Nicolas's "merge"** (branch `feat/510-vanilla-keys-doors`,
  ADR 0397). It fixes Ch5x and Ch3:
  - **Ch5x:** a key an enemy drops (`sight.keySources`) is a way to a chest or through a door.
  - **Ch3:** the judged enemy phase plays on the map the plan opens (`Sight.openMap`, journaled).
  - **Witnesses:** Ch5x seed 4003 cleared clean in 3 of 4 attempts (the fourth lost Kyle to a
    0.1% roll; before, 0 of 12). Ch3 seed 4005 cleared clean in 4 of 4 (before, 0 of 48).
  - **Suite** (`suite --held-out`): **PROMOTED**, no regressions, held-out 4 of 28 lost (as at the
    freeze), +0.4% calls.
  - **Review:** both reviews' findings are fixed. CI was green on 87646ac3; the last commit
    (8fcc88ba, docs only) re-runs it: check `gh run list --branch feat/510-vanilla-keys-doors`
    before merging.
- **Ch2 (Ross) is next, not started.** H3b is confirmed by the code: a green recruit's death
  reaches the rank only as a yes/no forfeit, and `green_die` skips recruits (`planner.lua`, the
  `greenDie` loop). With Ross at 37% in every turn-1 plan, all of them tie, so a plan lowering his
  chance ranks no higher. The fix to try: count a recruit green's death chance in `green_die` (a
  tiebreak after forfeits). Then witness on seed 4008's Ch2 start. H3a (whether any act the bot
  has saves Ross without the game's Rescue command, which the bot lacks) is untested until then.
- **Witness recipe:** build an env with `campaign_env.pinned_env(campaign_env.vanilla_env(1),
  'cs-s<seed>', <chapter index>)` (drop `attempt`), then run `montecarlo.py attempts --env <it>
  --attempts 4 --jobs 4 --vanilla --seed <seed>`. Ch5x is index 5, Ch3 index 3, Ch2 index 2. The
  kept starts are in `references/sim/vanilla/c25b145e3745`.
- **After Ch2:** re-run `starts --count 10 --game vanilla` (about 1 h) once the witnesses are
  clean, and report where the campaigns stop next.

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

1. **#510 step 10**, after the vanilla route above (Ch2 next, then `starts --game vanilla`).
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
