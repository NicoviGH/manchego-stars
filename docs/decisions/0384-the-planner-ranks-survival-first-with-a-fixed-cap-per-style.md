---
id: 384
title: "The planner ranks plans by survival first: a fixed risk cap per style, then what a plan forfeits, then progress; prices order candidates and break the ties after progress"
date: "2026-11-01"
section: "Combat System"
issues: [510]
---

# The planner ranks plans by survival first: a fixed risk cap per style, then what a plan forfeits, then progress; prices order candidates and break the ties after progress

**Decided (Nicolas, 2026-11-01), #510 step 9.** Taken from the step 9 spec (FR-009 to FR-016),
which an advisory panel drafted (research record 0023): spec #510 comment 6563384018, plan and tasks #510 comment 6563384310. Supersedes ADR
0375 and amends ADRs 0381, 0382 and 0383. **Built (PR-C, then PR-D):** the caps, admission,
the fallback and branch-summed death in PR-C; the completion ledger, forfeits and progress (4)
in PR-D. Both are below, with two amendments PR-D's design needed (2026-11-02).

**Why.** A weighted score lets loot buy risk. In vanilla Ch3, careful struck Bazba alone at a
predicted 12.7% chance of losing Franz, because the kill scored more than the death cost
(#510 comment 6480158861). ADR 0375 called that variation. Raising the death weight does not
fix it: any weight is outbid by a large enough gold × points-per-gold. A cap cannot be outbid.

**1. Each style has a fixed risk cap:** careful 1%, even 5%, bold 15%, the most predicted death
chance it accepts for any protected unit in a plan. The caps are never drawn, so a pinned run
reproduces exactly. A missing cap is an error, and caps are never tuned on held-out failures.
The styles are still the variation; what varies between them is the cap, not a price.
Protected units are blue units and game-over VIPs, not ordinary allied greens.

**2. A predicted death chance is a sum over judged branches**: each protected unit's chance is the
probability-weighted sum over mutually exclusive branches the game played, never an inference
from averaged HP. Today `judge()` plays the enemy phase at the plan's mean HP and branches only
`M.BRANCH` = 2 kills. If branching every outcome breaks the CPU budget, the fallback branches
only the outcomes that can change whether a protected unit can die (plan task T036 measures it).

**3. Complete plans are ranked in this order, not summed:**
- **Admission.** A plan with every protected unit at or under its cap outranks every plan that
  is not.
- **Among admitted plans:** fewer irreversible goal forfeitures first, then objective
  completion, then progress.
- **Among plans over the cap** (only when no plan is admitted): the smaller chance of a game
  over first (amended below, 2026-11-01), then smallest largest excess, then smallest summed
  excess, then lowest largest death chance, then the admitted plans' order
  (forfeits, completion, progress). The chosen plan is labelled
  `FALLBACK_SACRIFICE`, so no over-cap death goes unexplained.
- **Remaining ties:** lower largest death chance, then lower summed death chance, then more
  expected surviving HP, then a stable order.

**4. The completion ledger counts forfeits.** At each decision it snapshots the open goals the
game can still give: offered villages and chests, owed Talk recruits and declared reward claims
(the same list as ADR 0383's goals). A plan's forfeits are the goals it closes for good, winning
first included, counted per judged branch and taken from the worst branch, never averaged. A goal
whose state the game cannot report is unknown, neither kept nor forfeited, and a goal that is
only out of reach for now is not forfeited. An escort green's death is a forfeit. An allied green's survival only breaks
ties between admitted plans whose forfeits and completion are equal and whose progress is within
one turn, and it never defers a legal seize. A seize skipped while a ledger goal is still
feasible is justified. Progress is the drop, from the decision's starting board, in the game's
own turns to the assigned goal, and to the objective once the optional goals are resolved.

**What this changes in earlier records:**
- **ADR 0375** is superseded: a style's risk tolerance is now a declared value.
- **ADR 0381:** a green unit's death is no longer priced as one of ours. An escort green is a
  forfeit; an allied green only breaks ties.
- **ADR 0382:** the planner no longer pays what the clean clear counts. No planner decision reads
  clean clear; it ranks forfeits.
- **ADR 0383:** worth × chance (`goals.lua`, `GAMMA`) stays, but only to order candidates in the
  beam, frozen like every candidate-ordering heuristic (spec FR-013, #510 comment 6563384018). It no longer decides between
  complete plans, and the per-style points per gold stop mattering once the rank decides. The
  panel's draft deleted it outright; the final spec keeps it because the beam still needs an order
  to choose which partial plans reach the judge, and an order cannot buy risk once admission
  decides.

**Built (PR-C, 2026-11-01).** `planner.lua` `M.CAPS` holds careful 0.01, even 0.05 and bold 0.15,
and `M.plan` raises on a style without one. Protected units are every blue and every unit in
`sight.objective.gameOver`; botrun grades only their deaths against the cap, so an allied
green's death has no `cap` and no `over_cap`. `judge()` plays every uncertain kill both ways, up
to `M.BRANCH` = 8 of them (256 phases a plan). Past that, the most uncertain are played and
the rest keep the average. It normalizes the branches' chances and records each protected
unit's death per branch (`plan.protected`). A kill is branched even when its enemy reaches no
protected unit: that enemy's death can free a tile for one that does
(`test_planner_plays_an_uncertain_kill_both_ways`). Admission forgives float dust (`M.admits`:
within 1e-9 of the cap), and botrun grades `over_cap` through the same `admits`. `M.plan`
returns what the call cost, over every plan it judged, a call with no plan included:
`{ phases, averaged }`, which botrun sums into `plans.phases` and `plans.averaged`, so a kill
left to the average past the bound is never silent. The suite manifest's `budgets.branch` is
8 too, and `test_montecarlo` fails when it and `M.BRANCH` differ. Plans are compared by
`M.outranks` on `plan.rank`:
admission; for plans over the cap, the chance of a game over (amended below), largest excess,
summed excess, largest death chance, then the admitted order; for admitted plans, `value` (the
judged score), standing in for (4) until PR-D; then largest death chance, summed death chance,
HP left, and the plan's acts as a key.
A plan chosen with none under the cap carries `fallback = "FALLBACK_SACRIFICE"`, which botrun
records as one `fallback_sacrifice` anomaly a turn (`plans` counts the turn's fallback plans,
`max_die` the most any of them accepted).

- **What PR-C does not do yet:** an allied green's death still costs the judged score, as
  ADR 0381 priced it; PR-D's ledger replaces that with the tie-break of (4). A game-over unit's
  death costs the judged score `W.win` (planner.lua `loss`), so among admitted plans the interim
  `value` leans toward the plan whose lord is safest; PR-D settles how the ledger counts it
  (amended below, 2026-11-02, and Built (PR-D)).
- **Measured, branching (plan T036), the pinned suite, 52 runs:** every kill branched judged
  7,020 enemy phases in 1,005 plans. `BRANCH = 2` on the same code judged 6,213 (13% fewer).
  With the bound of 8 the play was identical (7,020 phases, 1,005 plans, no kill averaged).
  CPU is the noisy figure. Two runs of that identical play read 1,925.9 and 2,175.9 CPU s,
  +2.2% and +15.5% on PR-A's baseline of 1,883.6, both inside SC-003's 20%. PR-B's three runs
  ranged 1,877-1,964. The written fallback (T037) is not built: branching only the kills whose
  enemy reaches a protected unit is unsound, because a kill frees tiles.
- **Measured, live (plan T043):** vanilla Ch3 with Seth benched (ADR 0375's case), seed 1,
  attempts 1-8: 8 of 8 won clean with no deaths (before: 1 of 8 kept every unit). Careful won
  on turn 26 and kept Franz, with no fallback plan. Vanilla Ch5 attempt 1, seed 1 (bold):
  won on turn 8, 62.6 CPU s; Natasha (0x0D) died on turn 3 at a predicted 68.4%, graded
  `over_cap` under a plan labelled `FALLBACK_SACRIFICE`, and Joshua was killed before the
  Talk (as on main). In the suite, every `over_cap` death came from a labelled fallback.
- **Not built, and why:** the review of PR #560 asked for the protected death to add the
  counter's own death. `bot.lua` refuses every attack whose counter alone can kill (every style
  but greedy), so that share is 0 for every attack the planner judges. A counter-and-phase death
  (Franz's 12.7%) is all in the phase share, which admission reads.

**Amended (Nicolas, 2026-11-01): a game over comes before the excess.** A unit whose death ends
the game (a lord's, `sight.objective.gameOver`) is not one more risk among the protected: its
death ends the chapter. So among plans over the cap, the one with the smaller chance that such a
unit dies comes first, whatever the excess. Before this, a lord's 50% was played over another
unit's sure death, because it was the smaller excess (#560). `plan.rank.game_over` is summed
per judged outcome: the chance that any such unit dies there, weighted by the outcome's chance
(two lords killed in different outcomes make a sure game over, never a product of their
chances). Chances in the rank are compared to within `M.DUST` (1e-9), so a sum taken in another
order is no difference. Admitted plans' rank is unchanged (see the 2026-11-02 amendment).

**Amended (Nicolas, 2026-11-02): no separate cap for a lord.** "A lord is still a functional
unit so over protecting it is not feasible, they need to be put in danger to win, so its a
balance really." This keeps the step 9 spec's cap and admission for a game-over unit: it is
protected (FR-009) with its style's cap (FR-010), and admission comes first (FR-011), so a plan
with a lord at the cap outranks one whose lord is safe and another unit is a hair over it. (The
order among plans over the cap is the 2026-11-01 amendment's, not FR-011's.) **Was open, for PR-D,
and answered below:** how the ledger counts a game over in an admitted plan. A branch where the
lord dies closes every open goal, and §4 takes forfeits from the worst branch, so counted that
way any chance at all would make the plan whose lord is at 0% beat every plan that puts it in
danger, which is the over-protection Nicolas ruled out. (A line #561 added, that the ledger
would count a game over as forfeiting everything, was removed in #562.)

**Amended (Nicolas, 2026-11-02): a game over is no forfeit.** Asked how the ledger counts a
branch where the lord dies, Nicolas chose "not a forfeit": admission already lets a game-over
unit's risk up to the style's cap, so the ledger counts only the closures in the branches where
the game goes on, and the risk is never charged twice. Among plans equal on forfeits, completion
and progress, the judged score and FR-013's largest death chance still prefer the safer lord.
This covers every unit whose death ends the game, so it overrides FR-012's first sentence for
an escort green: an escort green (one in `sight.objective.gameOver`) is protected, and its risk
is admission's, not a forfeit.

**Amended (Nicolas, 2026-11-02): the judged score comes after whole turns of progress.**
Under FR-011 and FR-013 as written, nothing among admitted plans counted damage dealt: the
order ran forfeits, completion, progress, then death chance and HP left. A strike that cannot
kill this turn then always lost to a wait, because the counter lowers HP left and the damage
counts nowhere (a test: bold, 20 of an enemy's 40 HP, waited). Units would stand beside an
enemy that takes two turns to kill and never chip it. Nicolas first put the judged score
(`value`: damage, kills, heals, HP taken, worth × chance) after progress. The review of PR #564
then showed progress compared exactly leaves the score only exact ties: a strike from a tile a
step back still lost to a march a step on, and a step is a fraction of a turn. Asked, Nicolas
put the score after the whole turns of progress (`behind`, below) and ahead of the progress
within the turn. This amends FR-013's tie list and ADR 0383's line above: worth × chance orders
the beam, and through the judged score it orders complete plans within a turn of the most
progress. It never outranks a forfeit, the win or a whole turn of progress.

**Built (PR-D, 2026-11-02).**
- **The ledger.** `goals.lua` `Goals.ledger` snapshots every open visit, chest and recruit with
  any chance from the decision's board (`Goals.chance`, the planner's `before`), plus each
  declared reward with the goals it needs. A goal with no chance at all is not on it: the game
  lets no unit of ours use it (a chest with no key in the army), none has a way there
  (`sight.turnsTo` reads the terrain alone, through a breach), or a looter takes it first. Kept,
  it would close with every win and forbid the win for good. A unit in the way leaves the
  chance as it was, so such a goal stays `feasible`. A reward needing a goal that is not on the
  ledger is not either. A village or chest is `unknown` when the sight has no `canExplore` or
  `closings` read. `Goals.forfeited` counts what a plan closes, conservatively: a win chance
  above 1e-9 (`Goals.DUST`, which `planner.lua`'s `DUST` now reads) closes every goal the plan
  does not take. A recruit closes when our blow, our counter or the enemy phase may kill it: a
  green recruit's death is a forfeit, an allied green's is not. A tile a looter takes after this
  phase (`closes` 1) closes when the plan does not take it, and a reward closes with any goal it
  needs. The plan carries `ledger` (what it forfeits marked `closed`), `forfeited`,
  `seizeJudged`, `seizeAdmitted` and `stuck`.
- **The rank.** `M.outranks`'s admitted order is `forfeits` ascending, `complete` (the chance the
  plan ends the chapter) descending, `behind`, `green_die`, `value`, `progress`, then FR-013's
  ties. `progress` is the turns the plan cuts from each unit's way to its assigned goal, summed:
  the recruit, village or chest it was sent to, else its way to the objective, read once at the
  decision's start, `sight.turnsTo` through the breach when cut off. `behind` is the whole turns
  a plan is short of the most progress among the plans that may be played (`M.rebase`, once
  after the finals and once after the mends). It stands for FR-012's "within one turn": "within
  a turn of each other" is no order a sort can keep (0, 0.8 and 1.6 each tie their neighbour).
  `green_die` sums allied greens' death chances, a recruit's and a game-over green's left out.
- **Reassignment (FR-016).** `Bot.candidates` sends a unit elsewhere, or to the objective, when
  it has had no step toward its goal since an earlier turn: no tile it may end on is nearer by
  the game's turns, it is not on the goal, and no tile beside a recruit standing there. One turn
  so is a unit in the way, and the unit holds that turn; sending it on at once handed a tile
  between units, which `sent` was made to stop. The record (`ctx.stuck`: the unit, the tile and
  the turn first found blocked) is carried by botrun as `opts.stuck`, tested again at every
  decision, and lifts once the way opens. A unit boxed in (no tile but its own) keeps its goal.
  Only the units whose goal changed are proposed again. After a Visit the tile is explored, so
  the unit's march heads for the objective again.
- **The advance, a search addition.** The spec defers search changes until an audit shows a
  search miss under the corrected scoring. ours ch01 showed one: the beam orders partial plans
  by the judged score, where a House worth 4.7 never paid for the lord's steps away from the
  gate (each unit's way there is worth 250), so all four plans it handed the judge had him
  waiting. One more plan is judged beside the beam's and the assault: each unit takes, of its
  acts that gain ground within the cap, the one that gains the most, falling to the next when a
  tile is still taken. A unit refused every one is tried again once the others have moved. It
  is skipped when no unit gains ground or the beam already has the plan.
- **Seize skips (FR-015).** botrun justifies a skip while a ledger goal is `feasible`, or when
  every judged plan with the Seize was over the cap. It is a fault (`unjustified_seize_skip`)
  when a Seize under the cap was judged and nothing was left to get, or when no judged plan had
  the Seize at all.
- **What changes in play.** Within the cap, a whole turn of progress now comes before HP left and
  before an allied green. Careful takes a blow that cannot kill for a whole turn of ground, and
  blocks for a green only when the block costs less than a turn. Any style keeps out of a
  recruit's reach when its counter may kill it, since that is a forfeit.
- **Measured, live (plan T055).** ours ch01 from its store (`from: 2`, `house_gifts`), attempts
  1-3: won clean turn 8, won with one death turn 8, won clean turn 8 (main, same env: stuck,
  won clean turn 8, stuck). Attempt 2 (bold) lost 0x03 on turn 7 at a predicted 51.1%, under a
  labelled fallback. Vanilla Ch2, attempts 1-2: won clean on turns 8 and 6.
- **Measured, the pinned suite (`suite --baseline`, 52 runs):** SUITE_NUMBERS
