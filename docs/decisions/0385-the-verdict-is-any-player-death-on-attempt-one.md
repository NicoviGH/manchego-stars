---
id: 385
title: "Step 9's verdict is any player death on attempt 1, compared with exact bounds at 50, 100 and 200 pairs and a ±10-point margin"
date: "2026-11-01"
section: "Combat System"
issues: [510]
---

# Step 9's verdict is any player death on attempt 1, compared with exact bounds at 50, 100 and 200 pairs and a ±10-point margin

**Decided (Nicolas, 2026-11-01), #510 step 9.** Taken from the step 9 spec (FR-023 to FR-030 and
FR-033), which an advisory panel drafted (research record 0023): spec #510 comment 6563384018, plan and tasks #510 comment 6563384310. Amends ADR
0376 and replaced the method `montecarlo.py` ran until then (exact McNemar with an early-look
bar, research record 0022's reading). **Built in PR-H** (points 1 to 3, see "Built (PR-H)" at
the end); point 4's validity bar and point 5 are PR-I's.

**Why.** A clean clear mixes two things: how dangerous a map is, and how well the bot collects
everything. A Manchego Stars chapter can fail clean clears more often than its twin only because
the bot misses one village, and that says nothing about difficulty. A player death is what
difficulty is about.

**1. The endpoint.** For each cell, a Manchego Stars chapter and its vanilla twin at one
difficulty, the verdict compares one thing: the chance that at least one protected unit dies over
the whole first attempt. Protected units are ADR 0384's: every blue unit and every game-over VIP.
An escort green's death is reported (it spoils the clean clear and is a forfeit), but it is not
the endpoint, so an escort map reads the same whoever implements it. Only attempt 1 is measured, since a retry knows more than a first
sight-read does (ADR 0386). Clean clear stays in every record and report as a column, never as
the endpoint.

**2. Two kinds of cell.**
- **Chapter cells:** each replicate plays both arms from pinned chapter-start states with an
  independent seed. Replicates are independent, so the bounds below hold as stated.
- **Campaign cells:** each replicate starts a campaign from New Game under a frozen
  carry-forward protocol and reuses that campaign's chapter starts across its chapters. They
  report reachability in both arms and compare a chapter only when both arms reach it. Their
  replicates are clustered across chapters, so any claim across chapters must account for that.

**3. The method.**
- A 50-seed pilot on one cell comes first. Its seeds are never confirmatory, and pilot, tuning
  and confirmatory seeds are disjoint. It reports the paired table, the discordance, the
  correlation, reachability, CPU, and whether ±10 can be reached at that discordance. It also
  chooses paired analysis if the two arms' outcomes covary positively, marginal otherwise.
- Confirmatory looks come at 50, 100 and 200 pairs. Each interval is built from four one-sided
  exact Clopper–Pearson bounds, each at 0.05 / (4 × 3 × N), with N the frozen number of cells.
  In paired analysis they bound the two discordant proportions (ours died and the twin did not,
  and the reverse); in marginal analysis they bound the two arms' death rates.
- An attempt that ends unresolved stays in the denominator: it is retried on the same seed,
  then bounded adversarially. A verdict the bounded interval does not support is withheld.
- **Verdicts, checked in order at every look:** EQUIVALENT if the interval lies inside ±10
  percentage points; otherwise HARDER or EASIER if it excludes zero; otherwise INCONCLUSIVE.
- No special rule for zero discordant pairs: the bounds already handle it. With N = 24 (ch00 to
  ch07 in three modes), 0 discordant pairs of 50 gives about ±16 (not equivalent) and 0 of 200
  about ±4 (equivalent). These figures are paired; marginal analysis is wider.
- **Why ±10 and not ±5:** at 200 pairs and N = 24 the paired interval is about ±4.2 points with
  no discordant pairs, ±8.8 with 5% and ±11.7 with 10%, so ±10 is reachable below about 7%
  discordance. A ±5 margin could practically never return EQUIVALENT. If cells are added the
  figures widen, and the pilot reports them for the frozen N.

**4. A cell is NOT READABLE unless both arms' first attempts pass a validity bar:**
- at least 90% of attempts free of harness faults, with faults that depend on the outcome
  withholding the verdict;
- no death caused by a sandbox fault;
- fewer than 10% of attempts with a blind-spot or unclassified death;
- no unlabelled over-cap death (ADR 0384) and no unjustified seize skip;
- a vanilla any-death chance below 0.85, the same in every mode. A twin that nearly always
  loses someone means the bot is failing, not measuring, and Manchego Stars could not show
  HARDER. There is deliberately no floor: a twin that almost never loses anyone is a real
  reading (an easy chapter), HARDER can still be shown against it, and EQUIVALENT near zero is
  the true answer when ours is easy too. Only EASIER cannot be shown there, and it means
  nothing below zero deaths.

**5. Human calibration.** The designer and one blind friend play vanilla Ch3 and Ch5 and
Manchego Stars ch02 and ch03 on Normal, resetting on a player death, and code each reset on a
frozen one-page form per map with the bot's causes plus misplay and ignored loot. Once that data
exists, a result may gate a decision only if the bot's leading first-attempt cause matches the
humans' leading reset reason on at least three of the four maps. Otherwise it is marked
UNVALIDATED_HUMAN. They are compared by failure mode, not by rate.

**What this changes in ADR 0376:**
- The verdict no longer counts clean clears (point 1).
- **Decision 4 becomes a milestone, not a gate.** Clearing all of vanilla's Eirika route clean is
  still tracked, but a cell's verdict waits only on its own validity bar (point 4).
- **Decisions 1 and 2 stand:** a clean clear's four parts, and a vanilla chapter without one is
  a bot fault. Decision 2 labels why a campaign stops (`bot_fault`, never `infeasible`); it is
  reported, and it no longer gates a verdict. It does not contradict point 4: a twin can lose
  someone on most first attempts and still be cleared clean on a retry. A campaign that stops
  there leaves the later chapters unreached, and an unreached chapter withholds its campaign
  cell (point 2: a campaign cell compares a chapter only when both arms reach it).

**Built (PR-H, 2026-11-07).**
- **`paired_verdict` was reworked in place**, with no second verdict function. It reads each
  pair as (did ours lose a protected unit anywhere in attempt 1, did the twin), where a
  protected unit is a blue one or a green whose death ends the game (`protected_deaths`, the
  same rule the suite's `run_outcome` uses). `chapter_result` returns that endpoint and keeps
  `clean` as a reported column. Exact McNemar, its early-look bar and the score intervals it
  reported with are gone, and their names are in `DEAD_CONCEPTS`.
- **The bounds** are `clopper_pearson` (exact, found by bisection on the binomial tail; it
  matches Newcombe 1998a's exact column for all four of that paper's worked examples), each at
  `bound_level(N)` = 0.05 / (4 × 3 × N). N is the manifest's `instrument.cells`, 24.
  `confirmatory_interval` bounds the discordant proportions (paired) or the arms' rates
  (marginal). The label is checked in FR-028's order at 50, 100 and 200 pairs, and the first
  decisive look settles the cell. At N = 24 the bounds give ±15.9 points at 0 of 50, ±8.3 at
  0 of 100 (so an even cell settles EQUIVALENT at the second look) and ±4.2 at 0 of 200.
- **Unresolved attempts:** an attempt with no game result is played once more on its own seed
  (`RETRIES` = 1). The retry is counted where the play stopped, so a campaign that crashes
  before the chapter and then, on its retry, at the chapter gets one retry at each. If it still has none, `bound_unresolved` reads it as the worst case each way
  and it stays in the denominator. An interval that then decides nothing is labelled
  **WITHHELD**, not INCONCLUSIVE. In a campaign cell, a campaign that crashed before the
  chapter withholds the whole comparison, and one that ended with a game result before it is
  counted in the reachability report and left out of the pairs. A chapter cell starts at the
  chapter, so any play there with no game result (a worker that died before writing a record
  included) is one unresolved pair, never a withheld cell.
- **Chapter cells:** `chapter_tasks` gives each seed of a set (the start's own tuning or
  held-out seeds, or the manifest's pilot or confirmatory range) one attempt-1 task on the
  pinned start, through `campaign_env.pinned_env`. The suite uses it too. `load_suite` refuses
  seed sets that overlap. `cell` plays either kind of cell to its verdict with the pilot's
  analysis. `pilot` estimates its wall time first and refuses a job over 8 hours.
- **The pilot** (Nicolas chose the cell: ours ch03 against vanilla Ch3, pinned starts,
  pilot seeds 3001–3050). 100 runs, estimated at 0.20 wall-hours on 8 workers, took 0.85
  CPU-hours. Every replicate reached the chapter and every attempt had a game result:
  - **The 2×2 table:** a protected unit died in ours on 18 of 50 attempts (36%) and in the
    twin on 0 of 50. So both 0, only ours 18, only the twin 0, neither 32: 18 discordant pairs
    (36%), a difference of +36 points.
  - **Analysis: marginal.** The covariance is exactly 0 because the twin never lost anyone,
    and the rule picks paired only when it is positive. With one arm constant the paired and
    marginal intervals are the same here.
  - **Can ±10 be reached?** No: with no difference at these death rates, 200 pairs would read
    ±19.7. That matters only for EQUIVALENT. If these rates held, the confirmatory look would
    read HARDER at 100 pairs (+11.9 to +54.3) and at 200 (+20.2 to +48.8). Pilot data is never
    confirmatory, and this is a projection, not a verdict.
- **The trace review (SC-005):**
  - **All 18 ours deaths are in careful-style runs.** Careful plays ch03 in 23 to 25 turns,
    bold and even in 14 to 16. The deaths come from that longer exposure, mostly at the Mogall
    boss: 30 of the 42 deaths were over-cap fallbacks, 6 were RNG tails under 1%, and 6 were a
    blind spot (`unrevealed_killer`: the Mogall killed a unit the plan never saw it reach).
  - **The 6 blind-spot runs are 12% of ours' attempts.** That is over the 10% that point 4
    allows, so PR-I's validity check would rate this cell NOT READABLE.
  - **A seed only draws the style and the claims it plays.** Two seeds that draw the same
    style play the pinned start frame for frame the same, so each arm's 50 seeds made 30
    distinct plays. The bounds still hold, because the draws are independent and the outcome
    is fixed once the style is drawn. But a chapter cell measures the style mix, not the
    game's RNG. Recorded on #510 for PR-I's validity work.
- **Several starts a chapter cell (T100e, 2026-11-09).** That finding is why a chapter cell no
  longer plays one pinned start. `montecarlo.py starts --game ours|vanilla` plays campaigns from
  New Game on the `starts` seeds (4001-4100), each seeded once and never again (ADR 0370), and
  pins every chapter-start state each left in its game's store (`cell-starts.json` beside
  `runs.jsonl`). The pins live in the store and not in git because a store is one ROM: an ours
  ROM change (a class, a stat, a line of text) is a new store with no starts until they are
  remade. The vanilla starts are made once. `cell` and `pilot` take `--chapter N` (our chapter
  number; the twin comes from `campaign_env.cell_chapters`) and `--starts K`. Each arm plays the
  first K pinned campaigns, by seed, that reached the chapter's start. Seed s is dealt start
  (s - the set's first seed) mod K, so a look plays the same deal whichever seeds it adds. K is
  10 for a verdict to trust, and fewer (say 4) while a change is being tried. A cell refuses
  when fewer campaigns reached the chapter, and names the command that makes more. Every line
  that counts pairs says how many games they came from. A cell run costs the same as before.
  `replay` still replays suite runs only.
