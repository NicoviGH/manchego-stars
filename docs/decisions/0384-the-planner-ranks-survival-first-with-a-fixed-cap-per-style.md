---
id: 384
title: "The planner ranks plans by survival first: a fixed risk cap per style, then what a plan forfeits, then progress; prices only order candidates"
date: "2026-11-01"
section: "Combat System"
issues: [510]
---

# The planner ranks plans by survival first: a fixed risk cap per style, then what a plan forfeits, then progress; prices only order candidates

**Decided (Nicolas, 2026-11-01), #510 step 9.** Taken from the step 9 spec (FR-009 to FR-016),
which an advisory panel drafted (research record 0023): spec #510 comment 6563384018, plan and tasks #510 comment 6563384310. Supersedes ADR
0375 and amends ADRs 0381, 0382 and 0383. **Built in part (PR-C):** the caps, admission, the
fallback and branch-summed death are built (below); the completion ledger, forfeits and
progress (4) wait for PR-D, and until then the weighted score orders the admitted plans.

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
- **Among plans over the cap** (only when no plan is admitted): smallest largest excess first,
  then smallest summed excess, then lowest largest death chance, then the admitted plans' order
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
green's death has no `cap` and no `over_cap`. `judge()` plays every uncertain kill both ways
(`M.BRANCH = math.huge`), normalizes the branches' chances, and records each protected unit's
death per branch (`plan.protected`). Plans are compared by `M.outranks` on `plan.rank`:
admission; for plans over the cap, largest excess, summed excess, largest death chance, then
the admitted order; for admitted plans, `value` (the judged score), standing in for (4) until
PR-D; then largest death chance, summed death chance, HP left, and the plan's acts as a key.
A plan chosen with none under the cap carries `fallback = "FALLBACK_SACRIFICE"`, which botrun
records as a `fallback_sacrifice` anomaly.

- **What PR-C does not do yet:** an allied green's death still costs the judged score, as
  ADR 0381 priced it; PR-D's ledger replaces that with the tie-break of (4). The cap does not
  weigh a game-over unit's death above another's: with every plan over the cap, a lord's even
  chance is played over another unit's sure death, because it is the smaller excess.
- **Measured, branching (plan T036), the pinned suite, 52 runs:** every kill branched judged
  7,020 enemy phases in 1,005 plans, at 1,925.9 CPU s (PR-A's baseline 1,883.6: +2.2%, inside
  SC-003's 20%). `BRANCH = 2` on the same code judged 6,213 phases. Its CPU (2,120.9 s) is not
  comparable, because another process shared the machine during that run. Full branching is kept, and
  the written fallback (T037) is not needed.
- **Measured, live (plan T043):** vanilla Ch3 with Seth benched (ADR 0375's case), seed 1,
  attempts 1-8: 8 of 8 won clean with no deaths (before: 1 of 8 kept every unit). Careful won
  on turn 26 and kept Franz, with no fallback plan. Vanilla Ch5 attempt 1, seed 1 (bold):
  won on turn 8, 62.6 CPU s; Natasha (0x0D) died on turn 3 at a predicted 68.4%, graded
  `over_cap` under a plan labelled `FALLBACK_SACRIFICE`, and Joshua was killed before the
  Talk (as on main). In the suite, every `over_cap` death came from a labelled fallback.
