---
id: 25
title: "Bot decision logic that generalises scores outcomes and keeps a hard no for what the game forbids: utility AI, GOAP/HTN, chance-constrained planning, and how Fire Emblem players reason"
date: "2026-11-08"
section: "Playtesting bots"
issues: [510]
tags: [planner, style, utility-ai, goap, htn, chance-constraint, risk-cap, rules]
---

# Bot decision logic that generalises scores outcomes and keeps a hard no for what the game forbids

**What this is.** On 2026-11-08 Nicolas asked for research on how to write the playtest bot's
decision rules so that they stop arriving as narrow bans after each witnessed death. A read-only
subagent read the repo's own notes and searched outside practice. ADR 0396 is the decision taken
from it. The outside sources below were read through search summaries, not in full, so take their
characterisations as secondary.

**Findings.**
- **Utility AI** (Dave Mark's Infinite Axis Utility System; Kevin Dill's dual utility; Mike Lewis,
  "Choosing Effective Utility-Based Considerations", Guild Wars 2). Every option is scored by
  several considerations, each a curve over a measured input, and the scores multiplied. Dill sets
  this against yes/no logic (state machines, behaviour trees) for the nuance it keeps. Hard vetoes
  are rare and kept for what is impossible.
  https://en.wikipedia.org/wiki/Utility_system ·
  https://gameai.com/iaus.php ·
  https://www.oreilly.com/library/view/game-ai-pro/9781482254792/K23980_C003.xhtml ·
  https://www.taylorfrancis.com/chapters/edit/10.4324/9781315151700-13/choosing-effective-utility-based-considerations-mike-lewis
- **GOAP** (Jeff Orkin, F.E.A.R., GDC 2006) **and HTN planning** (Troy Humphreys). An action
  states its preconditions, its effects and a cost, and the planner finds the sequence. A
  precondition means the act is possible in the game, never a matter of taste.
  https://pages.cs.wisc.edu/~dyer/cs540/handouts/gdc2006_orkin_jeff_fear.pdf ·
  https://www.taylorfrancis.com/chapters/edit/10.1201/9780429055058-9/exploring-htn-planners-example-troy-humphreys
- **Reinforcement learning's reward design** (Sutton and Barto, through course slides; the book's
  wording was not checked). A goal says what is to be achieved, not how. Advice on how belongs in
  the search's order, never in the goal.
  https://cs.brynmawr.edu/Courses/cs380/spring2011/lectures/RL.pdf
- **Chance-constrained planning**, the formal name for a risk cap. A cap on the chance of failure
  is the standard way to state a risk limit. Its usual relaxation, a Lagrangian, turns the cap into
  a price that rises with how far a plan goes over, which fits "the cap is a preference" better than
  a wall with exceptions.
  https://arxiv.org/pdf/1512.01629 · https://arxiv.org/pdf/2204.04780
- **How strong Fire Emblem players reason** (community guides). In quantities, not bans: turns,
  threat ranges, which enemy can strike whom, baiting one enemy to pull its group, and chokepoints
  that cap how many strike at once.
  https://feuniverse.us/t/randomwizards-enemy-placement-guide/14888 ·
  https://gameranx.com/features/id/430966/article/fire-emblem-engage-complete-combat-guide/
- **In the repo.** Research record 0021 already frames the planner as a portfolio search: units
  propose acts, the search assigns them, and the game's enemy phase judges. The notes on bot rules
  said the same thing in pieces. None of them said how to write a decision.
