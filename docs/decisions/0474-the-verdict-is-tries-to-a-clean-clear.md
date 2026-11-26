---
id: 474
title: "The verdict compares tries to the first clean clear, pair by pair, within the cap (amends ADR 0385)"
date: "2026-11-25"
section: "Combat System"
issues: [742, 640, 510]
---

# The verdict compares tries to the first clean clear, pair by pair, within the cap (amends ADR 0385)

**Decided (Nicolas, 2026-11-23 and 2026-11-25, #742).** On 2026-11-23 he set the measure:
"I never understood the emphasis on the first attempt anyway, as it's normal for players to go
through several attempts." On 2026-11-25 he approved the method below (#742 comment
7179142787). Turns, first-try deaths and total deaths were weighed as the verdict and are
reported instead: turns measure the bot's style more than the map (careful ch03 took 23 to 25
turns, bold 14 to 16, ADR 0385), first-try deaths ignore retries, and total deaths are a
noisier copy of tries.

**Why ADR 0385 chose attempt 1, and why that no longer holds.** Retries then learned nothing,
so attempt 1 was the only like-for-like comparison. Now the same code replays the same game,
retries included (#699 comment 7106711753); a retry remembers what failed attempts showed
(ADR 0467); and a chapter is beaten by a clean clear on any attempt within the cap (ADR 0399).
ADR 0385's other objection, that a clean clear mixes danger with how well the bot collects, is
answered by the retries: a missed village costs an attempt in both games alike.

## 1. The endpoint

A replicate is one seed on one pinned chapter start, in each arm. It plays every attempt, with
memory, until the first clean clear or the cap (`MAX_ATTEMPTS`, 12, campaign.lua's own rule).
Its **tries** are the attempt of that first clean clear. No clean clear within the cap is one
value, worse than every attempt. A protected death on attempt 1, the old endpoint, stays on
every record and report as a column.

## 2. The statistic

Each pair is one of three: Manchego Stars needed more tries (b), the twin did (c), or the same
(ties, two with no clean clear within the cap included). The verdict bounds b/n − c/n, the share
of starts where Manchego Stars took longer minus the share where the twin did. Nothing else of
ADR 0385's method changes: exact one-sided Clopper–Pearson bounds on b/n and c/n, each at
0.05 / (4 × 3 × N), looks at 50, 100 and 200 pairs, N = 24, the ±10-point margin and the label
order.
- **Why this and not a median or a mean:** the cap needs no assumption. Twelve against none is
  just "Manchego Stars cleared sooner", and the statistic needs no new mathematics.
- **Always this form.** The arms are different games, so pairing by seed is arbitrary. But b and
  c are each a binomial count whatever the arms share, so their bounds stay valid. ADR 0385's
  marginal analysis bounded two death rates, which an ordinal has no counterpart for, so the
  pilot's paired-or-marginal choice and `cell --analysis` are gone.

## 3. Unresolved replicates

A play whose attempt k has no game result, with no clean clear before it, needed k tries or
more. A play cut short after attempt k with no end saying its attempts ran out needed k + 1 or
more. Each is retried once on its own seed (`RETRIES`), and the retry replays the whole play.
If it is still unresolved, `bound_unresolved` reads it at its fewest tries one way and at none
within the cap the other, as ADR 0385 did with a death.

## 4. Validity

Every check reads every attempt a replicate played, not only attempt 1: environment-clean at
90%, no sandbox-fault death, blind-spot or unclassified attempts under 10%, no unlabelled
over-cap death, no unjustified seize skip. The vanilla bar moves with the endpoint:
`vanilla_uncleared` fails when the twin has no clean clear within the cap on 85% or more of its
replicates. The reason is ADR 0385's: a twin that almost never clears leaves Manchego Stars no
room to read HARDER.

## 5. What it costs

A replicate costs its tries in attempts, and 12 when it never clears. A cell's CPU is the old
cell's times the mean tries. `pilot` still refuses a job over 8 wall-hours (SC-007). A start
that a run of this instrument has measured is estimated at its measured whole-play wall. One
that no run has measured is estimated at the manifest's one attempt times the cap, a bound, and
the pilot says how many starts are bounded that way. The suite is unchanged: it plays attempt
1 only.

## Built (#742)

- `montecarlo.py`: `plays` splits a replicate's records at each campaign end. `play_result`
  reads one play's tries (`clean_at`, `first_clean`'s), and `chapter_result` returns the first
  play whose tries are known. `span`/`pair_of` give each arm (lo, hi). `table_of`,
  `confirmatory_interval`, `bound_unresolved`, `paired_verdict` and `pilot_summary` read spans,
  with no `analysis` argument. `tries_summary`/`tries_words`/`tries_lines` say each arm's
  median and share cleared. `cell_record` writes `endpoint: tries_to_clean` and each arm's
  tries, and `report_cells` refuses a record judged on the old endpoint. `NO_CLEAN` names
  campaign.lua's three no-clean ends, which `PASSED_CAMPAIGN` builds on.
- `chapter_tasks(..., tries=True)` (every chapter cell) runs `campaign_env.pinned_env(...,
  tries=True)`, a resumed play with no `attempt` and `shared_start`. harness.lua's `api.save`
  then keeps the start in memory only, so the retries load it without writing the pinned file
  that every worker on that start reads.
- A chapter cell keeps each play's campaign end beside its attempts (`suite_run_of(...,
  ends=True)`), and never a run stamped `task_attempt` (attempt 1 alone, whose tries are
  unknown). A clean clear after an attempt with no game result is unresolved. `records_of` stamps the end with its task's instrument so the filter can take
  it. `kept_walls` reads a run once, by its attempt 1, since every attempt of a run carries
  that run's one wall.
- `verdict-diff` and its CI comment read `tools/difficulty.py` (ADR 0353), not these cells:
  nothing there changed.
