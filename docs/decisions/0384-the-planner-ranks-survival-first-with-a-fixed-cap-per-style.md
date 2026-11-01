---
id: 384
title: "The planner ranks plans by survival first: a fixed risk cap per style, then what a plan forfeits, then progress; prices only order candidates"
date: "2026-11-01"
section: "Combat System"
issues: [510]
---

# The planner ranks plans by survival first: a fixed risk cap per style, then what a plan forfeits, then progress; prices only order candidates

**Decided (Nicolas, 2026-11-01), #510 step 9.** Taken from the step 9 spec (FR-009 to FR-016),
which an advisory panel drafted (research record 0023). The plan is on #510. Supersedes ADR
0375 and amends ADRs 0381, 0382 and 0383. **Not built yet:** until PR-C and PR-D of the plan land,
`planner.lua` still ranks plans by the weighted score those ADRs describe.

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
  beam, frozen like every candidate-ordering heuristic (spec FR-013). It no longer decides between
  complete plans, and the per-style points per gold stop mattering once the rank decides. The
  panel's draft deleted it outright; the final spec keeps it because the beam still needs an order
  to choose which partial plans reach the judge, and an order cannot buy risk once admission
  decides.
