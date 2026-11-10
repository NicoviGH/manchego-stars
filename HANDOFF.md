# Handoff - Manchego Stars live state

**Read this from main** (`git show main:HANDOFF.md`): on a feature branch this file is the copy
from when the branch was cut, and may be days old.

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`**; how-tos live in the files they are about;
operating rules in `CLAUDE.md`/`AGENTS.md`; findings, scope and backlog on GitHub issues. Nothing
here should still be true in a month. Before a context rollover, warn Nicolas, refresh this file,
and start a fresh instance; don't rely on auto-compaction.

Refreshed 2026-11-10, afternoon (Claude): **the vanilla playthrough ran; Ch6 is the wall. Next
is PR 1 of "retries that learn" (Nicolas approved it all, retry cap 12).** The plan and the
findings are ONE comment, #510 comment 6776176601 (edited in place); read it first. Earlier:
the vanilla route plan 6758779876, its results 6770045525.
- **`starts --count 10 --game vanilla` on main** (Normal, instrument `7a0822786e03+v2`, 62 min
  on 8 workers). The 2026-11-09 pins were deleted first (Nicolas's call), since `starts` only
  plays unpinned seeds. Every campaign reached Ch5; **8 of 10 stop at Ch6** (index 7), 4003 at
  Ch5x (index 5), **4008 reached Ch7** (index 8). All `bot_fault`.
- **Ch6, why** (38 attempts): the bot WINS 31 of 38, clean 1. A Bael walks from (27,4) in fog
  down column 26 and kills a Civilian at (26,11) on turn 8: every win of 8+ turns lost it (24
  of 24), none of 7 turns or fewer did (0 of 8). 33 of 55 blue deaths are `fog`-labelled.
  Retries replay the same deaths (they only re-roll the style). H2 (the planner weighs a
  green's death only one enemy phase ahead) holds on one trace: `green_die` 0 on turns 1-7, 0.835
  on turn 8 (4001 Ch6 attempt 3).
- **4008 carried on past Ch7** as campaign `full-s4008` (its Ch7 start copied in; records in
  `references/sim/vanilla/c25b145e3745/full-runs.jsonl`, apart from `runs.jsonl`): Ch7 clean on
  attempt 1; Ch8 (index 9) won 4 times, never clean (chests (1,3) and (2,3) `unreached` every
  time, why untested; a thief stole in attempts 3 and 4); attempt 5 crashed in the harness
  ("the move failed" on an attack). Its Ch8 start is saved at `states/full-s4008/9.ss`.
- **Decided by Nicolas today** (record each in the PR's ADR):
  1. A retry learns what earlier attempts showed on screen (reverses ADR 0386's narrowing, back
     to ADR 0376 decision 3): every red unit seen un-fogged, and every death (who, turn,
     killer). Never a dice result.
  2. A retry cap of **12 a chapter start** replaces "every style tried, stop" (styles are drawn
     again once used up; memory makes a repeat play differently).
  3. A second measured number beside the first-try death rate (ADR 0385 stays): **tries until
     the first clean clear**, both arms. That is PR 2; its method goes to Nicolas as an ADR 0385
     amendment before it is built.
- **Keep the campaigns' progress (Nicolas asked; don't replay from New Game).** Every chapter
  start is saved: the 9 stopped campaigns' last starts are `states/cs-s<seed>/7.ss` (Ch6; 4003's
  is `5.ss`, Ch5x) and 4008's is `states/full-s<seed>/9.ss` (Ch8). After PR 1, carry each on from
  there: `campaign_env.vanilla_env(1)` with `id` and `from` (no `attempt`, `last` left at the
  game's end), copied first under a NEW id, because resuming re-saves the start it loads and
  `cell-starts.json` pins `cs-s<seed>`'s by sha1. Last session's one-off driver did exactly this
  through `montecarlo.Pool` (it was in the session scratchpad, gone now); PR 1 should make it a
  `starts --resume` (or similar) so it is not a scratch script again.
- **Where PR 1's code goes** (read, not changed): `campaign.lua` lines 246-318 (the attempt loop:
  `remembered`, `drawStyle`, `MAX_ATTEMPTS = 300`, `noClean`); `botrun.lua` `arrivals_seen` (line
  ~690) is the model for recording what was seen; the planner's fog: `planner.lua` 1745-1771
  (`plan.enemies`, `fogged`), `FOG_REACH`/`W.fog`; `sight.fullInfo` (sight.lua 980-1011) lifts
  the fog for judging only ("knowledge, not powers", botrun.lua ~975), the model for treating a
  remembered enemy as seen. `test_campaign.lua` must keep attempt 1 memory-free.
- **Witness recipe:** `campaign_env.pinned_env(campaign_env.vanilla_env(1), 'cs-s<seed>',
  <chapter index>)` (drop `attempt`) as `montecarlo.py attempts --env <it> --attempts N --jobs N
  --vanilla --seed <seed>`. Its attempts run side by side WITHOUT memory (ADR 0386 "one
  consequence"): PR 1's witness needs them in sequence. Ch6 is index 7.
- **Lessons this session:**
  - `starts` skips a seed already pinned, whatever bot pinned it: to replay, clear its pins.
  - A trace file (`trace-vanilla-<id>-a<n>.jsonl`) is written when its attempt ends, and its
    number is the game's chapter id: 5 is Ch5x, 6 is Ch5 (Ch5 is played first).
  - Vanilla chapter ids on Eirika's route: 9 Ch8, 10-21 `CHAPTER_E_9`..`E_21`, 22 `E_21X`.

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

1. **#510: PR 1, retries that learn** (above; branch `feat/510-retry-memory` from `origin/main`),
   witness on Ch6 starts 4001 and 4007 (attempts in sequence so memory carries), `suite
   --held-out`, then carry the campaigns on from their saved starts. Then PR 2 (tries to the
   first clean clear). **#510 step 10** after.
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
