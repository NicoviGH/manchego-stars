# Value vs progress panel: full transcript (2026-11-02)

Model-simulated experts, not people. Their answers are opinions, not evidence. The record that
says what this is and what it led to is `docs/research/0024-*.md`; the decision is ADR 0384's
amendment of 2026-11-02, "progress before the judged score".

Turns are in the order they finished. Seats were played through the sidecar advisor tools where
a provider answered. Once it returned HTTP 402 (payment required), they were played by Anthropic
models as subagents, each re-seated with its round-1 answer as a recap. The dossier is
appendix A, the round-1 digest the round-2 seats read is appendix B.

## Round 1 (opening positions)

<details><summary>Prompt (the same for every seat, with the role's own line)</summary>

You are role-playing **{name}, {role}**. On 2026-11-01 you sat on this project's advisory
panel, which recommended a survival-first rank with fixed per-style risk caps (now built).
Fellow panelists: {the other five}.

The project owner has delegated ONE decision to the panel and will ship what it decides. Read
dossier.md.

ROUND 1 (opening position), ≤600 words:
1. Your vote, one line: **A** or **B**.
2. Why, grounded in the dossier's numbers and the mechanism. Say plainly what 26 runs can and
   cannot show.
3. Optional: at most one concrete, testable amendment (and whether it ships now or later).
4. What evidence would change your vote.
Be adversarial and decisive; do not hedge to be polite.

(Wójcik's prompt added: "do the paired arithmetic: discordant runs, a sign/exact test if
meaningful".)

</details>

### 1. Game AI search researcher (Reyes)

*Model: `openai/gpt-6-luna-pro` (the first seat, `openai/gpt-6.1-sol-pro`, returned 402)*

**Vote: B**

The primary endpoint is protected-unit death, and B has the better observed result: 14 deaths
versus A's 18, including 8 versus 13 over-cap deaths. Wins and clean clears are tied at 23 and
14. A is faster by 7 total turns, but that is not enough to justify four additional protected
deaths under a survival-first policy. The clearest cost is Ch5 seed 1002: B clears cleanly; A
takes three over-cap deaths. A's advantage is not universal—on Ch4, B skips a village while A
gets a clean clear—but the aggregate clean-clear count remains tied.

The fallback pattern matters. Every over-cap death occurred on a FALLBACK_SACRIFICE turn, so
this does **not** show A chose an admitted plan that violated its cap. It is consistent with the
proposed mechanism: choosing damage over fractional progress can leave a worse state later, when
no candidate is within the cap. That mechanism is plausible, not proven; the outcome difference
is enough for me to reject A for now.

These 26 paired runs show what happened on this fixed suite, not a reliable general effect size.
They cannot establish statistical significance, generalize to held-out seeds, or prove that A's
ranking caused the later fallbacks. The death difference is also concentrated in a few cases.

I would change my vote if a broader, paired held-out evaluation showed A no worse on protected
deaths and clean clears while retaining its turn advantage—and preferably showed, from decision
traces, that A does not increase later fallback-scarifice turns.

### 2. RL/ML engineer (Brandt)

*Model: `minimax/minimax-m3.1-flash`*

**Vote: B.**

#### Why

The primary endpoint is any protected-unit death, and A is directionally worse on it: **18
versus 14 deaths**, including **+4 net** against B. A's seven-turn reduction does not compensate
for that safety regression. Wins and clean clears are tied at 23 and 14, respectively.

This is a textbook constrained-objective/proxy failure. A's immediate `value` signal rewards
damage now without pricing the loss of future safe options. The dossier's evidence is consistent
with that mechanism: all over-cap deaths occurred after fallback turns, when **no current plan
was admissible**. A may be satisfying today's cap by choosing a less-forward striking position,
then leaving itself without an admissible successor one or two turns later. The admitted plan
was locally legal; the policy was globally unsafe.

B puts progress before value only within the existing admission and whole-turn buckets, so it
preserves the long-horizon objective without abandoning damage entirely: value still breaks
exact progress ties and permits chip damage from suitably forward positions. That better matches
the project's survival-first constraint.

The mechanism is plausible, not proven. A slightly cheaper CPU does not outweigh the observed
death increase.

#### What 26 runs can and cannot show

These are 13 chapter starts with two seeds each, so observations are correlated rather than 26
independent trials. Only a handful of runs are discordant, deaths cluster within runs, and no
confidence interval or held-out confirmation is supplied. Thus the sample cannot establish that
A causes future fallback dead ends, estimate the population effect reliably, or generalize to
unseen chapters. It can establish a **directional, paired warning**: styles and seeds match, the
difference concentrates in protected deaths, and A's extra turns do not produce better
completion outcomes.

That is insufficient for a causal claim, but sufficient to choose the safer tie-break when wins
and clean clears are equal.

#### Amendment

**Later, not with this ship:** test a two-ply feasibility tie-break among admitted plans: prefer
a plan that leaves at least one admitted successor at the next player phase; if none does, leave
ranking unchanged. Accept it only on untouched held-out seeds if fallback turns fall without
increasing protected deaths.

#### Evidence that would change my vote

I would consider A only if frozen held-out runs showed **no excess protected deaths**, preserved
wins/clean clears, retained a meaningful turn advantage, and trace evidence showed that
value-first actions do not increase next-turn fallback incidence. A significant reduction in
deaths would make the issue more than sampling noise; confirmation that the current excess
vanishes would reopen A's efficiency benefit. Until then, B ships.

### 3. Engineering lead (Hale)

*Model: `deepseek/deepseek-v4.1-flash` (the first attempt did not complete; answered on retry)*

**Vote: B (progress, value).**

**Why**

1. **A is worse on the primary endpoint and buys nothing the endpoint cares about.** Same wins
   (23), same clean clears (14), +4 protected deaths (18 vs 14), +5 over-cap (13 vs 8). The only
   gain is 7 turns across 26 runs — a non-endpoint, and well inside the 1–2 turn spread the
   brief itself calls "same outcome" elsewhere. Speed is not the thing being measured; deaths
   are.

2. **A's cost is structural, not luck, which is exactly what the per-turn cap cannot see.**
   Every over-cap death in both arms lands on a FALLBACK_SACRIFICE turn: no candidate plan was
   within cap. So A never breaks its contract — it exploits the contract's one-turn horizon.
   "Chip from a step back" is only free if the position it costs never comes due. A's own worst
   rows say it does: vanilla Ch5 seed 1002 loses a clean t9 win and takes three over-cap deaths;
   scout-ch10 takes an over-cap death at t3 on both seeds. B's rule is positional: chip only
   from the most forward tile the cap allows. That is the rule that keeps future turns
   admissible, and admissibility is the whole point of the cap.

3. **The owner's remark is conditional, not absolute.** "A strike from a step back is still
   worth taking" — worth it when the step back is not the reason the next two turns are over
   cap. He saw A's deaths and handed it over; the evidence answers the condition against A.

4. **A isn't uniformly worse** (ch01: faster, one fewer death; ch04: clean t8 vs B's t5 with a
   village skipped), which is why this is a real trade rather than a bug — but the aggregate on
   the pre-settled endpoint points one way, and A/B differ only in the one line.

CPU is a wash (A 2463, B 2558, noise ~13%).

**Amendment (optional, testable):** keep B's order and insert one key after `progress`, before
`value` — *position potential*: summed remaining goal-distance (fractional turns) of protected
units after the plan, ascending; value breaks ties. It costs nothing extra (same simulated
end-states) and directly encodes the hypothesised mechanism. Falsifiable predictions: (i)
vanilla Ch5 seed 1002 and scout-ch10 seeds 1001/1002 lose their t3/t4 over-cap deaths, or the
first over-cap fallback turn moves later, with turns within 1 of B; (ii) ch01 seed 1001 keeps
A's t8/1-death result; (iii) suite deaths ≤ 14 with clean clears ≥ 14. If (i) fails, drop the
key — the debt story is wrong.

**What would change my vote**

- A one-shot **held-out-seed** evaluation (legitimate: never read for tuning) with the decision
  rule pre-registered as deaths-first. B's own count moved 12→14 across review fixes, so the +4
  gap is roughly twice the observed jitter on N=26; if A's death excess shrinks to ≤1 while
  keeping the turn gain, and especially if it converts to extra wins or clean clears, A becomes
  defensible.
- Evidence that A's over-cap turns are preceded by the *same* position state as B's — i.e. the
  deaths are draw variance, not position debt. Then A's speed is the only signal left and I'd
  flip.
- If "deaths on fallback turns are already-lost turns" were adopted as doctrine — it isn't; the
  endpoint counts them.

### 4. FE designer (Mori)

*Model: `qwen/qwen3.8-flash` (the first attempt did not complete; answered on retry)*

**Vote: B.**

**Why.** The settled primary endpoint is ANY protected unit death on attempt 1. On the pinned
suite, B has **14 protected deaths** versus A's **18**. Wins and clean clears are tied: both win
23 runs and both clear cleanly 14 times. So the measured difference is not success; it is
**mortality versus pace**. A finishes 7 total turns faster, but at the cost of 4 extra deaths
and 5 extra over-cap deaths.

Those deaths are not incidental. The only runs that diverge materially are runs where A turns a
clean or lower-death outcome into a death-heavy one:

- Ch5 seed 1002: B clean at t9; A wins at t10 with 3 over-cap deaths.
- scout-ch10 seeds 1001 and 1002: B wins t18 with no deaths both seeds; A wins t19 with an
  over-cap death both seeds.

The A mechanism is plausible: value-first selects chipping from tiles further back, leaving the
army poorly positioned so that one or two turns later no plan is within cap. That is still a
failure under the primary endpoint, even if the selected admitted plan was within cap when
chosen. "Fallback sacrifice" deaths are still deaths.

B also preserves the owner's concern. Value is not dropped; it breaks exact progress ties. B
simply refuses to let damage outrank forward fractional progress. That seems the right trade
while A's extra deaths remain visible.

**Amendment.** Ship B with a concrete safety amendment:

> Add a projected fallback-capacity tie-breaker before value. Among plans tied on
> `behind`/`green_die`, prefer value only if the plan does not increase the simulated count of
> future player phases with no within-cap plan compared with a higher-progress alternative. If a
> value-first strike creates a next-phase no-admitted-plan state while a progress-first plan
> preserves at least one within-cap option, demote the value-first strike.

Pin it with the existing divergence cases: Ch5 seed 1002 and both scout-ch10 seeds must choose
the progress-preserving plan and must not reproduce A's extra over-cap deaths. This keeps "a
strike from a tile a step back is still worth taking" when it is genuinely safe, but blocks the
specific pattern where chipping back leaves the bot trapped in fallback turns.

**What would change my vote.** I would move toward A if additional runs show A's deaths are
mostly noise, or if A can be amended to preserve its strikes without increasing protected
deaths, over-cap deaths, or future no-admitted-plan turns. I would also reconsider if the owner
changes the primary endpoint to weight clean-clear timing or total turns above raw deaths. For
now, because deaths are the endpoint and clean clears are tied, B is the safer ship.

### 5. Playtesting lead (Nair)

*Model: Claude Sonnet, a subagent (the sidecar seat, `google/gemini-3.8-flash`, returned 402)*

**Vote: B**

**Why.** The owner's stated endpoint (ADR 0385) is ANY protected death on attempt 1. On that
endpoint B beats A, and the gap is in the direction that matters. Protected deaths: PR-C 12, B
14, A 18. Over-cap deaths, which come only from FALLBACK_SACRIFICE turns: B 8, A 13. Clean
clears are tied at 14, and wins are tied at 23. A's one apparent edge is 7 fewer total turns
(242 vs 249), and turns are not the endpoint. The two numbers I'd also stress: B's vanilla Ch5
run is clean where A's has three over-cap deaths, and scout-ch10 is a clean win for B on both
seeds against one over-cap death for A on both.

The mechanism fits the data, though it is hypothesised, not proven. Chipping from a step back
leaves units in worse positions, so a later turn has NO plan inside the cap, and that is exactly
the FALLBACK_SACRIFICE state. A pays for chip value in the one currency the instrument is graded
on. B also keeps the owner's ruling that value is in the rank. Value still orders plans within
the same progress fraction and still beats a wait. B only stops value from outbidding a march
within a whole-turn bucket, and `behind` already makes buckets whole turns.

**What 26 runs can and cannot show.** They cannot show that A is worse by a real margin. 26 runs
is 13 starts x 2 seeds, and the seeds are not independent: several results are the same start at
two seeds, and style is drawn per seed. The A-vs-B protected-death difference is 18 vs 14, and
the whole difference sits in about 6 runs. Those are paired runs where the only change is one
line, so the A-B comparison is cleaner than the PR-C comparison, but it is still a handful of
flips. Two things further weaken any claim. First, B moved from 12 to 14 deaths between
measurements at the first commit and the review head, so B's own count is not stable under
unrelated fixes. Second, the CPU numbers have about 13% noise, so they say nothing about either
arm.

What the runs do show is that neither arm is catastrophic. A lowers neither deaths nor clean
clears, and it gets 7 fewer turns. That is a thin win, and it is a thin win on a column that is
not the endpoint. When the evidence is this noisy, I decide on the direction of the mechanism
and on which cost lands on the primary endpoint. Both point to B.

**B's real defect, stated plainly.** Vanilla Ch4 seed 1002 under B won turn 5 but skipped a
village. That is a missed goal in the clean-clear definition, though it is not a death. It is
one run, and the cause is the chapter ending in the enemy phase. The owner should watch it. It
is not a reason to pick A, because A's cost is deaths and B's is a miss in a derived column.

**Owner ruling.** I take the ruling "a strike from a tile a step back is still worth taking" at
face value, but it was made before he saw the trade. His own list says the trade was put back to
the panel. B is the choice that honours the primary endpoint when the two conflict.

**Amendment (testable, ships LATER, not now).** Add a tie band: let value decide inside the
whole-turn bucket only when progress differs by less than some epsilon such as 0.25 turns, and
let progress decide beyond that. This is the middle option, and it would test whether the
A-over-B death gap comes from large step-backs or small ones. It must not hold up B shipping
now. Pre-register it. Run it on the same 13 starts with seeds 1001/1002, and compare over-cap
deaths only.

**Required test change.** `test_a_chip_beats_a_step_within_the_turn` flips under B. Rename it and
state the new rule in its comment, so the reversal reads as a decision and does not look like a
regression.

**What would change my vote to A.**
1. A paired rerun on fresh tuning seeds, at least 3 new seeds per start, where A's
   protected-death count is within 1 of B's. That would show the 18 was seed luck.
2. A trace showing the A-only over-cap deaths come from something other than position after
   chipping. For example, if they all trace to one planner fault that a separate fix removes,
   the positional hypothesis is wrong.
3. A finding that B's skipped village at Ch4 is a systematic stall (a unit that never reaches
   its goal) and not a one-off enemy-phase ending.

Without one of those, B ships.

### 6. Statistician (Wójcik)

*Model: Claude Opus, a subagent (the sidecar seat, `z-ai/glm-5.3-flash`, did not complete, then
returned 402)*

**1. Vote: B** (progress, then value).

**2. Why**

The primary endpoint under ADR 0385 is any protected death on attempt 1, scored per run. So I
score per run and leave death counts aside. A's 18 deaths against B's 14 is inflated by
clustering: vanilla Ch5 alone puts 3 deaths on one run. Deaths within a run are not independent
observations.

Paired table on the primary endpoint, 26 runs:

| Run | B | A | Discordant? |
|---|---|---|---|
| vanilla Ch5 1002 | clean | death | yes, A worse |
| scout-ch10 1001 | clean | death | yes, A worse |
| scout-ch10 1002 | clean | death | yes, A worse |
| ours ch03 1001 (bold) | clean | death | yes, A worse |
| ours ch03 1002 (careful) | death | clean | yes, B worse |
| ours ch01 1001 | death | death | no (2 vs 1 deaths is not on the endpoint) |
| vanilla Ch4 1002 | no death | no death | no (B's skipped village is the derived column) |
| the other 19 | same | same | no |

That gives 5 discordant runs, split 4–1 against A.

- **Exact sign test:** two-sided p = 2·(1+5)/32 = 0.375; one-sided 0.19. Not significant, and
  not close.
- **Flat-prior posterior** on the share of discordant runs that favour B: Beta(5,2), so P(B
  better) = 57/64 ≈ 0.89.
- **Scout-ch10 is probably one observation, not two.** Same start, same careful style, same
  death on turn 3 at the same predicted 62.5%. That looks like one deterministic decision, not
  two draws. Counted once, the split is 3–1 and P(B better) ≈ 0.81.
- **ours ch03 cancels out.** A's death is under bold, B's under careful.

What 26 runs can show: the direction. B leads on the endpoint the owner chose, and both arms are
tied on everything else that matters. Wins are 23–23 and clean clears are 14–14.

What they cannot show:
- **Significance.** That is not available at this sample size.
- **Whether the gap is the key order or chaos.** A one-line rank change perturbs whole
  trajectories, so once a run diverges the pairing only partly holds. The dossier's own
  evidence: B's death count moved from 12 to 14 across review-fix commits with its key order
  unchanged. That is about the size of the A–B gap.
- **The mechanism.** It is stated as a hypothesis. It is plausible: chipping from a tile further
  back leaves units in positions where, a turn or two later, every plan is over the cap. It is
  unproven.

Why decide anyway: the owner delegated a decision, not an inference. Under uncertainty I take
the arm whose point estimate wins on the pre-registered endpoint.

A's advantages are on columns the owner did not choose:
- **7 fewer turns over 26 runs.** Turn count is not the endpoint.
- **The Ch4 village.** B missed it because the chapter ended in the enemy phase. That is a
  derived-column ledger miss, not a protected death.

There is also a validity argument. This bot is a difficulty instrument. Every extra over-cap
fallback death caused by the bot's own positioning is the instrument's error, and it biases the
chapter reading toward "too hard". Given equal evidence, I prefer the order that produces fewer
fallback deaths. B keeps value inside a progress bucket, so a chip from a tile as forward as the
march is still taken. The owner's "value must be in the rank" ruling stands under B.

**3. Amendment: a counterfactual attribution log (ships now, logging only, changes no play)**

At every decision, re-rank the recorded admitted candidates under the other key order and log
whether the chosen plan would change ("flip"). Then, for each FALLBACK_SACRIFICE turn, check
whether a flip happened in the same unit's previous 2 decisions.

- This needs no extra runs. It reads data the planner already holds.
- It tests the mechanism directly. If A's extra fallback turns are preceded by flips that pulled
  a unit back, the mechanism is real. If they are not, the gap is trajectory chaos.

**4. What would change my vote**

- **The attribution log comes back null.** If A's extra fallback turns have no flip in the 2
  decisions before them, the gap is chaos, not the order. Then the owner's stated preference ("a
  strike from a tile a step back is still worth taking") breaks the tie and I switch to A.
- **A larger paired sample comes back even.** Detecting an 80/20 discordant split with 80% power
  at two-sided α = 0.05 needs about 20 discordant runs. At the observed discordance rate (5/26 ≈
  19%), that is about 105 runs: 8 tuning seeds × 13 starts, roughly 5,000 CPU-seconds per arm.
  If that sample splits 55/45 or flatter on the endpoint, I switch to A.

Neither result exists yet. Ship B.

## Round 2 (what ships with B; final vote)

<details><summary>Prompt</summary>

ROUND 2 (final). All six panelists voted B in round 1, so the panel's decision on the order is
B. Their answers are in r1-answers.md. Now decide what ships WITH B in this PR versus later.
Candidate items:
1. Rename and re-comment the unit test that pins A, so the reversal reads as a decision (Nair).
2. Counterfactual flip log, logging only, no play change: re-rank admitted candidates under the
   other order, log flips, check flips before each fallback turn (Wójcik).
3. Two-ply feasibility / fallback-capacity tie-break: prefer plans that leave an admitted plan
   next phase (Brandt, Mori).
4. Position-potential key after progress, before value (Hale).
5. A 0.25-turn tie band where value decides only on near-equal progress (Nair).
Project constraints: any change to play must be re-measured on the pinned suite and re-reviewed;
the PR is otherwise review-clean; no PR may slow the suite or CI noticeably; follow-ups become
GitHub issues.
Answer ≤400 words: for each item, NOW / LATER / NEVER with a one-line reason. Then cross-examine
ONE named panelist's proposal (≤150 words). End with a single line: "Final: B" or "Final: A".

(Seats re-seated on a new model got, before it: "re-seated on a new model after a provider
failure. Your round-1 answer (written by the previous model in your seat) is the {name} section
of r1-answers.md; you own it now.")

</details>

The sidecar returned 402 for all four of its seats in this round, so every round-2 seat is an
Anthropic model.

### 7. Playtesting lead (Nair) round 2

*Model: Claude Sonnet, the same subagent as round 1*

1. **Rename and re-comment the test that pins A: NOW.** The PR flips the rule, so the test must
   state the new rule. Otherwise the reversal reads as a regression. Rename it to something like
   `test_a_march_beats_a_chip_within_the_turn`. Add a comment citing the panel decision and the
   measured 14 vs 18 protected deaths.

2. **Wójcik's counterfactual flip log: LATER.** It is the right instrument, and it also settles
   whether A's gap is key order or trajectory chaos. It is logging only, so it changes no play
   and needs no re-measure of play. But it re-ranks every admitted candidate at every decision,
   which costs CPU in a suite that has no CPU headroom (about 13% noise). Make it opt-in, off in
   CI. File it as its own issue, with the guard that it must be off by default. The PR is
   otherwise review-clean and should not gain a new surface.

3. **Two-ply feasibility / fallback-capacity tie-break (Brandt, Mori): LATER.** It is the only
   item that attacks the mechanism directly. But it is a new search stage, and it roughly
   doubles the per-decision planning cost at the exact moment we have a CPU constraint. It also
   needs re-measurement and a re-review. Open an issue and pre-register: accept only if fallback
   turns fall with no extra deaths, on fresh seeds.

4. **Hale's position-potential key: NEVER in this PR, and probably never.** A key placed after
   progress and before value is the same hypothesis as item 3, but weaker. Remaining goal
   distance is largely what progress already measures, so the key would mostly duplicate
   progress. A duplicate key is a duplicate-code violation of the project's rules in spirit.
   Fold it into item 3's issue if anything survives.

5. **My 0.25-turn tie band: LATER, pre-registered.** It is play-changing, so it must be
   re-measured and re-reviewed. Bundling it with B would hide which change produced any
   movement in the numbers. Run it as a separate experiment against the B baseline.

**Cross-examination of Brandt.** Brandt says to prefer a plan that leaves at least one admitted
successor at the next player phase, and to accept it on held-out seeds. That demands that the
successor test be computed on the enemy phase's outcome. The bot only knows death chances, not
the enemy's chosen moves. So "an admitted successor exists" is a probabilistic claim, and the
plan needs a rule for which branch counts. If it is the modal branch, the key ignores the tails
where the deaths happen. If it is an expectation, it needs another cap. Brandt should say which
branch counts and what the check costs per decision before this is built. Also, "held-out seeds"
cannot be read here, because their outcomes are never read by project rule, so acceptance has to
run on fresh tuning seeds.

Final: B

### 8. Statistician (Wójcik) round 2

*Model: Claude Opus, the same subagent as round 1*

**What ships with B**

1. **Rename and re-comment the test that pins A: NOW.** Under B the test flips to the march
   anyway. Its name and comment have to state the new rule, or the reversal reads as a
   regression. Play does not change.
2. **Counterfactual flip log: LATER.** I said NOW in round 1; I'm changing that. The log informs
   no decision in this PR, and it adds review surface to a PR that is review-clean. It is the
   instrument for the follow-up, so it lands first in that issue, before items 3 and 5 are
   measured. It needs a guard that play and traces stay byte-identical apart from the new field.
3. **Two-ply feasibility / fallback-capacity tie-break (Brandt, Mori): LATER.** It changes play,
   and judging successor plans costs CPU against the suite budget. It needs the flip log plus
   about 8 tuning seeds × 13 starts, and acceptance only if fallback turns fall without more
   deaths.
4. **Position-potential key (Hale): NEVER.** It duplicates `progress`. Cross-examination below.
5. **0.25-turn tie band (Nair): LATER, pre-registered.** It is a partial return to A, so it
   carries A's burden of proof. It has to be measured from the best plan's progress, the way
   `behind` is. A pairwise "within 0.25 of each other" is no order a sort can keep (0, 0.2,
   0.4).

The three LATER items go into one GitHub issue, in this order: flip log, then the 8-seed paired
run, then items 3 and 5 as candidates judged against it.

**Cross-examining Hale (item 4)**

Hale's key is "protected units' summed remaining goal distance after the plan." `progress` is
already "the turns a plan cuts from each unit's way to its assigned goal, summed," read from one
board at the decision's start. For a fixed starting distance, the distance left equals the start
minus the turns cut. So the two keys differ only where:

- a unit has no goal,
- a unit is not protected,
- `turnsTo` disagrees with itself.

Placed after `progress`, Hale's key sees only plans whose progress ties exactly, and those plans
almost surely tie on the new key too. In practice it breaks no ties and costs one more `turnsTo`
read per plan.

If Hale means something else, such as exposure or the next phase's options, that is Brandt's
two-ply proposal under another name. It belongs in item 3, not in a new key. And it is a second
owner of the same quantity, which this repo's no-duplicate-code rule forbids.

**Final: B**

### 9. FE designer (Mori) round 2

*Model: Claude Sonnet, re-seated*

Items (B ships):

1. Rename/re-comment the A-pinning test (Nair): NOW. It is required anyway, because under B the
   test flips. A reversal that keeps A's name and comment reads as an accident rather than a
   decision. It costs no CPU and changes no play.

2. Wójcik's counterfactual flip log: LATER, as a GitHub issue. Logging only, but the dossier
   shows no CPU headroom. B's suite already cost 2,558s against 1,926/2,176 for PR-C, and
   re-ranking every decision under the other order adds more. The PR is also review-clean, and
   new code would need a new review. The log is worth building, but behind a flag or run once on
   the held-out seeds. It is not wanted in the default suite.

3. Two-ply feasibility / fallback-capacity tie-break (Brandt, mine): LATER. It is the amendment
   aimed at the real mechanism, but it needs a next-phase search and a re-measurement. It would
   slow every decision, and it cannot be proven on 26 runs.

4. Position-potential key (Hale): LATER. It changes play and needs its predictions pre-stated.
   It is also close to a second progress key.

5. 0.25-turn tie band (Nair): NEVER in this PR, and LATER only if the flip log shows value is
   under-used. B has already reordered the keys, and a band brings back A's problem: it lets a
   strike from a tile a step back beat a march a step on. That is the trajectory that produced
   A's extra over-cap deaths.

Follow-ups go to GitHub issues, each with its own measurement plan.

Cross-examination of Hale: you say a step back is fine when the step back is not why the next
turns are over cap. That cannot be told from one phase, which is exactly why the key sits so
late in the order. Your position-potential key is progress measured again, as remaining distance
to the goal. It also sits after progress, so it can only break exact progress ties, and B
already leaves value to decide those. It adds a third quantity that tracks the same thing as the
first two. FE8's enemy AI punishes the shape of a formation: who holds the chokepoint, who baits,
who is exposed on the next enemy phase. Summed distance does not measure that. A
fallback-capacity check does, because it asks whether any admitted plan exists next turn. If you
want a key here, make it that check, and let it earn its place on held-out seeds. Otherwise the
PR carries a new key whose only evidence is your prediction list.

Final: B

### 10. Engineering lead (Hale) round 2

*Model: Claude Opus, re-seated*

1. **Rename and re-comment the test that pins A: NOW.** Under B the test flips anyway, so it has
   to change in this PR. It costs no play and no re-measure. The new name and comment record the
   reversal as the panel's decision, citing ADR 0384, so it doesn't read as a regression.

2. **Wójcik's counterfactual flip log: LATER, as the first task of the follow-up issue.** It
   doesn't change play, so it needs no re-measure. It does add a trace field, which means
   another review round on a PR that is otherwise clean. Nothing reads its output until the
   follow-up runs, so it belongs at the start of that issue and gates items 3 and 4.

3. **Two-ply feasibility / fallback-capacity tie-break (Brandt, Mori): LATER, as an issue.** It
   changes play and adds a second search ply to every decision. That is the most likely of these
   items to slow the suite noticeably. It ships only if held-out seeds show fewer fallback turns
   and no extra deaths.

4. **Position-potential key, my own proposal: LATER, in the same issue.** It changes play, so it
   needs a re-measure and a re-review. It also rests on the mechanism we haven't proven. It waits
   until the flip log ties fallback turns to earlier flips, and it gets dropped if its
   pre-stated predictions fail.

5. **0.25-turn tie band (Nair): NEVER as stated.** It is a threshold tuned on about 6 differing
   runs, which is tuning on noise. Its pairwise form also can't be kept by a sort, as explained
   below.

**Cross-examining Nair's tie band**

ADR 0384 already settled this. "Within a turn of each other" was rejected because it isn't an
order a sort can keep: 0, 0.8 and 1.6 each tie their neighbour. That is why `behind` is measured
from the best plan. A band of "progress differs by less than 0.25" between two plans has the
same flaw. Take 0, 0.2 and 0.4: the first ties the second, the second ties the third, but the
first doesn't tie the third. Which plan the sort returns would then depend on the order the
candidates arrive in. That is a determinism regression in a tool whose only job is repeatable
measurement.

The only form a sort could keep is a second bucket measured from the best, like `behind` but
finer. That is just order A again inside a quarter-turn, and A is the arm that lost on the
endpoint. The 0.25 number also has no basis: no run in the dossier separates 0.2 from 0.3. If
the flip log later shows that A's chips are safe at small progress gaps, the band can come back
as a measured-from-best key with pre-stated predictions.

Final: B

### 11. RL/ML engineer (Brandt) round 2

*Model: Claude Haiku, re-seated*

1. **Rename the A-pinning test: NOW.** B flips its assertion, so the test name and comment must
   state the new rule and the measured reason, or the reversal reads as an accident.

2. **Wójcik's flip log: NOW, logging only.** It is the one item that separates "the key order"
   from "trajectory chaos," and it changes no play. Put it behind the trace flag so default cost
   is zero, and confirm the suite CPU delta is within noise.

3. **Two-ply fallback tie-break: LATER.** It is a play change with no measurement. Open an issue
   now with the acceptance rule: held-out seeds, fallback turns fall, no added deaths. It does
   not ship untested in this PR.

4. **Position-potential key (Hale): LATER.** Same reason. Predictions go into the issue before
   any run; drop the key if they fail.

5. **0.25-turn tie band (Nair): LATER, reformulated.** Not in the pairwise form, which is
   intransitive (see below). Only a band measured from the best plan, as `behind` is, can ship
   later.

Correction to my round-1 answer: "textbook proxy failure" overstated it. Five discordant runs,
sign test p = 0.375. I vote B on the endpoint direction, not on a demonstrated mechanism.

**Cross-examination of Nair.** Item 5 says value decides "only when progress differs by < 0.25
turns." Read pairwise, that is not an order a sort can keep. Take plans at 0, 0.2 and 0.4 turns
of progress. 0 ties 0.2, and 0.2 ties 0.4, yet 0 leads 0.4 by progress, so the rank is
non-transitive and the sort's output depends on input order. The ADR's `behind` comment names
this exact failure (0, 0.8, 1.6). A band must be anchored to the best plan, which is a different
rule with a different suite result, so it needs re-specifying before pre-registration. Your
rename and "state the rule" demand is right.

Final: B

### 12. Game AI search researcher (Reyes) round 2

*Model: Claude Opus, re-seated (a first re-seat on Claude Fable returned "requires usage
credits")*

**1. Rename and re-comment the test that pins A: NOW.** Under B the test fails anyway. Rewrite
it as `test_a_step_beats_a_chip_within_the_turn`, expecting the march. Its comment should cite
the panel's decision and the endpoint numbers (14 vs 18 deaths), so the reversal reads as a
decision, not drift. This changes nothing in play, and B's numbers are already measured.

**2. Wójcik's counterfactual flip log: LATER, as the first deliverable of the follow-up issue.**
It is cheap: it re-runs the comparator over plans already judged and judges nothing new. But it
is new code that needs its own review, and it only pays off inside the follow-up study. The PR
is review-clean now, so don't reopen it for a tool whose result cannot change what ships today.

**3. Two-ply feasibility / fallback-capacity tie-break: LATER.** It changes play. It also
multiplies judging cost by however many successor plans it checks per candidate, which breaks
the rule against slowing the suite unless it is bounded. And it must be re-measured on held-out
seeds. Its own issue, gated on what item 2 finds.

**4. Position-potential key after progress, before value: NEVER as specified.** Under B it is
close to a duplicate of `progress`. `progress` is the turns cut from each unit's distance to its
goal, read from the same starting board. So the summed remaining distance orders plans almost
the same way, differing only by being restricted to protected units. A near-duplicate key is the
duplicate-code rule applied to a ranking. If restricting it to protected units matters, item 3's
fallback-capacity measure already covers that.

**5. The 0.25-turn tie band: LATER, pre-registered.** It brings A back inside the band, so it
changes play and needs the full re-measurement. To stay an order a sort can keep, the band must
be measured from the best plan, as `behind` is, not between each pair. Write that into the
issue.

**Cross-examination: Brandt's two-ply feasibility.** "Leaves at least one admitted successor at
the next player phase" is not a yes/no fact. The enemy phase is random, so it is a probability
over enemy-phase outcomes. Define it as the chance-weighted share of enemy-phase outcomes from
which some plan is admitted, or the key is ill-posed. Next, cost: running the successor check on
every admitted candidate breaks the rule against slowing the suite. Bound it to the top two
admitted plans under B's order and report CPU next to deaths. Third, the horizon effect: one
more ply only moves the cliff one turn back. Ch5 seed 1002's deaths came on turns 3, 4 and 9,
and nothing shows a one-ply look from the turn before would have seen them. Make the test
pre-registered: on Ch5 seed 1002 and scout-ch10, the key must change the choice on the turn
before each FALLBACK_SACRIFICE turn. If it doesn't, it buys nothing. That is exactly what item
2's flip log measures, so log first and build second.

Final: B

## Appendix A: the dossier

The text every round-1 seat read as `dossier.md` (the sidecar seats inline; the subagent seats
read a longer copy with the same table and runs, plus `M.outranks`' comment and the PR #564
body's description of the change).

> # Dossier: value vs progress among admitted plans (#564)
>
> ## Context
> A solo developer builds a GBA Fire Emblem 8 ROM hack and a playtesting bot that plays the
> real ROM (emulator) to measure each chapter's difficulty. Primary endpoint (settled): ANY
> protected unit's death on attempt 1. 'Clean clear' (won, no protected death, no
> recruit/reward missed) is a derived column. Three play styles with fixed risk caps on any
> protected unit's predicted death chance this turn: careful 1%, even 5%, bold 15%. A lord's
> death is game over; lords get the style's cap.
>
> Each player phase the bot judges candidate multi-unit plans (a beam of width 6 plus mends, an
> 'assault' plan and an 'advance' plan) by simulating the enemy phase with the ROM's own AI,
> branching up to 8 uncertain kills. It then ranks plans with M.outranks:
> - Admission first: a plan whose every protected unit is within the cap is ADMITTED. If none
>   is, the least-excess plan is played and labelled FALLBACK_SACRIFICE (over cap, the order
>   is: chance of game over, max excess, summed excess, max death chance).
> - Among admitted plans: forfeits (goals the completion ledger says this plan gives up:
>   villages, chests, recruits) ascending -> complete (win chance) desc -> behind (WHOLE turns
>   short of the best progress among playable plans; integer) asc -> green_die (allied green
>   units' summed death chance) asc -> ??? -> ??? -> then max death chance, summed death
>   chance, HP left, stable key.
>
> The two keys in question:
> - value: the judged score: damage dealt, kills, heals, HP taken, each weighted by chance.
> - progress: fractional turns cut from each unit's way to its assigned goal, summed.
>
> ## The decision
> - A (as built, the PR head): ... green_die, value, progress. Within the same whole-turn
>   'behind' bucket, a strike from a tile a step back beats a march a step on. Pinned by a unit
>   test: A can strike enemy X for 20 of its 40 HP from (1,0), one step toward the goal, or
>   march two steps to (2,0); A picks the strike.
> - B: ... green_die, progress, value. Any fraction of a turn gained beats any damage, so a
>   unit chips an enemy only from as forward a tile as its march; value only breaks exact
>   progress ties.
> - Dropping value entirely is ruled out by the owner (then a unit within the cap never chips
>   an enemy it cannot kill this turn).
> Owner's earlier remark that led to A: 'a step is a fraction of a turn, and a strike from a
> tile a step back is still worth taking.' He then saw A's extra deaths and handed the trade to
> the panel to decide.
> The vote must be A or B for what ships now. One concrete testable amendment may be attached.
>
> ## Measurements, same code (only the one line differs)
> Pinned regression suite: 13 chapter starts x 2 tuning seeds = 26 runs (held-out seeds exist
> and are never read for tuning). Style is drawn per seed and is the same in A and B for a
> given (start, seed). PR-C = main before this PR, for reference.
>
> | | PR-C | B (progress, value) | A (value, progress) |
> |---|---|---|---|
> | clean clears | 10 | 14 | 14 |
> | wins | 22 | 23 | 23 |
> | protected deaths | 12 | 14 | 18 |
> | of which over-cap (all on labelled FALLBACK_SACRIFICE turns) | 6 | 8 | 13 |
> | total turns, 26 runs | 245 | 249 | 242 |
> | suite CPU s, 52 runs (noise ~13% on identical play) | 1926/2176 | 2558 | 2463 |
>
> Every run where A and B differ (all others: same outcome, turns within 1-2):
> - vanilla Ch5 seed 1002 (even): B clean t9. A won t10 with 3 over-cap deaths (t3, t4, t9;
>   predicted 46.7%, 68.4%, 70%).
> - scout-ch10 seeds 1001 and 1002 (careful, a late-game chapter): B won t18, no deaths, both
>   seeds. A won t19 with one over-cap death at t3 (predicted 62.5%), both seeds.
> - ours ch01 seed 1001 (bold): B won t9, 2 deaths (one over cap 51.9%, one unexplained
>   'other'). A won t8, 1 over-cap death (51.1%).
> - ours ch03: B seed 1002 (careful) one over-cap death (78.6%), seed 1001 clean t16; A seed
>   1001 (bold) one over-cap death (88.7%) t12, seed 1002 clean t16. (Swapped.)
> - vanilla Ch4 seed 1002 (careful): B won t5, no death but a village skipped (chapter ended in
>   the enemy phase). A clean t8.
> - vanilla Ch5 seed 1001: identical in both (3 over-cap deaths + 1 other).
> Net: A minus B = +4 deaths (Ch5 seed 1002: +3; scout-ch10: +2; ch01: -1; ch03: 0), clean
> clears equal, 7 fewer turns.
> Every over-cap death in both arms came on a FALLBACK_SACRIFICE turn: a turn where NO candidate
> plan was within the cap. A's hypothesised mechanism (not proven): chipping from a tile further
> back leaves units positioned so that one or two turns later every plan is over the cap. The
> admitted plan itself was within the cap when chosen.
> An earlier B measurement (before review fixes) read 12 deaths, 14 clean; A unchanged across
> its two measurements.
>
> ## What the PR does besides (unchanged by A/B)
> Completion ledger (forfeits), 'behind' as whole turns from the best, the 'advance' plan (each
> unit's most-progressing act within the cap; the beam alone never kept the lord's walk to a
> House), goal reassignment after a whole blocked turn, seize-skip justification. Live proof:
> ours ch01 attempts went from stuck/clean/stuck (main) to clean/won-1-death/clean.

## Appendix B: the round-1 digest

Round 2's seats read a digest of round 1 (`r1-answers.md`), one paragraph per seat, condensed
from the answers above by the convening session. It carried each seat's vote, its reasoning in
two to four sentences, its amendment and its "would change my vote" line; the answers above
are the full text.
