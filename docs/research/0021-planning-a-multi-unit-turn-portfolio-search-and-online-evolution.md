---
id: 21
title: "Planning a turn of many units: portfolio search and online evolution are the known methods; emulator save-state pools are unpublished"
date: "2026-10-27"
section: "Playtesting bots"
issues: [510]
tags: [planner, search, beam, portfolio, evolution, mcts, enemy-phase, parallel, save-states]
---

# Planning a turn of many units: portfolio search and online evolution are the known methods; emulator save-state pools are unpublished

Asked by Nicolas (2026-10-27) while the #510 step 9 planner and PR F's run pool were being
built: is there prior art to borrow? The plan's own prior-art note (2026-10-23) covered bot
reuse (none for FE GBA), PyGBA, and the Monte Carlo playtesting papers (record 0001); this
record covers what it did not: how to search one player phase where every unit acts.

- **A turn of many acts is its own problem, and these are the methods for it.** Each unit's act
  multiplies the turn's branching, so a tree over whole turns does not scale. Justesen,
  Mahlmann & Togelius 2016, "Online Evolution for Multi-Action Adversarial Games" (Hero Academy,
  five acts a turn; <https://pure.itu.dk/en/publications/online-evolution-for-multi-action-adversarial-games/>):
  an evolutionary search over the sequence of acts that makes up one turn, scored by a state
  evaluation, clearly beat MCTS and two greedy searches.
- **Portfolio search: units choose among a few scripts, the search assigns them.** Churchill &
  Buro's Portfolio Greedy Search (StarCraft combat, up to 50 vs 50 units in 40 ms;
  <https://ojs.aaai.org/index.php/AIIDE/article/view/12962>) gives each unit a small portfolio of
  scripted behaviours and hill-climbs over which unit runs which, judged by playouts. Follow-ups
  replace the hill climb with evolution (Portfolio Online Evolution) or stack it (Hierarchical
  Portfolio Search, Prismata). MicroRTS ships an implementation
  (<https://github.com/Farama-Foundation/MicroRTS/wiki/Artificial-Intelligence>).
- **What this says about ours.** The planner (#510 plan comment, "The planner") is already a
  portfolio search: `Bot.candidates` is each unit's portfolio (attack, breach, Talk, heal,
  march, hold, retreat, Seize), the beam assigns acts across units, and the judge's playout is
  the game's own enemy phase run in the sandbox. The literature's one stronger move, if the
  beam keeps cornering units, is to evolve whole-turn plans (mutate one unit's act, cross two
  plans) rather than grow them unit by unit, so a late unit's need can change an early unit's
  act. Not adopted; recorded as the next option.
- **FE's enemy order is fixed by the game.** A complexity analysis of Fire Emblem-style games
  (<https://arxiv.org/abs/1909.07816>) distinguishes enemies that attack whatever is in range
  from those that wait, and fixes the enemy move order by creation order. Ours runs the game's
  own order (`BuildAiUnitList`, `SortAiUnitList`) and each enemy's own decision, so neither is
  modelled.
- **Learned FE enemies exist; they are not for us.** "Mirror Mode in Fire Emblem"
  (<https://arxiv.org/abs/2512.11902>, Dec 2025) trains an enemy by imitation and reinforcement
  learning on a 6x8 Heroes-like grid. Our enemy is vanilla FE8's AI by rule (Nicolas,
  2026-10-26).
- **Cost is the known limit of search-based playtesting.** Playtesting work notes that MCTS needs
  no training but its runtime limits how widely it can test (Roohi et al. 2021,
  <https://arxiv.org/abs/2107.12061>). That is why the planner's cost is measured on every
  change.
- **No published pool runs an emulator from save states.** Searches for automated playtesting
  with parallel emulator rollouts from saved states found difficulty measurement from agent
  telemetry (EA SEED, <https://arxiv.org/abs/1903.10545>; patents) and RL playtest agents, but no
  pool like PR F's. There is nothing to reuse; the pool's correctness argument (every attempt
  loads one start state, RNG included) is our own, and was checked in the ROM: ch03 attempt 1
  alone played exactly as the sequential loop's attempt 1.
