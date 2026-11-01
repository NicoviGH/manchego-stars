---
id: 385
title: "Step 9's verdict is any player death on attempt 1, compared with exact bounds at 50, 100 and 200 pairs and a ±10-point margin"
date: "2026-11-01"
section: "Combat System"
issues: [510]
---

# Step 9's verdict is any player death on attempt 1, compared with exact bounds at 50, 100 and 200 pairs and a ±10-point margin

**Decided (Nicolas, 2026-11-01), #510 step 9.** Taken from the step 9 spec (FR-023 to FR-030 and
FR-033), which an advisory panel drafted (research record 0023). The plan is on #510. Amends ADR
0376 and replaces the method `montecarlo.py` runs today: exact McNemar, Haybittle–Peto looks and
research record 0022's reading. **Not built yet:** until PR-H and PR-I of the plan land,
`paired_verdict` still reads `clean`.

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
  cell (point 3's unresolved rule).
