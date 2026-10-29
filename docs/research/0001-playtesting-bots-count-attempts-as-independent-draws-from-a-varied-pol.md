---
id: 1
title: "Playtesting bots count attempts as independent draws from a varied policy; none learns between attempts"
date: "2026-10-27"
section: "Playtesting bots"
issues: [510]
tags: [retries, attempts, pass-rate, reinforcement-learning, personas, fairness]
---

# Playtesting bots count attempts as independent draws from a varied policy; none learns between attempts

- **Attempts are independent draws, not learning.** Roohi et al. 2021 (CHI PLAY,
  <https://arxiv.org/abs/2107.12061>; Angry Birds Dream Blast, ~95k players) take human
  difficulty as pass rate = 1/attempts and model agent "attempts" as independent stochastic
  runs (MCTS and DRL agents), with a separate population model for skill and persistence. The
  agent's pass rate over ALL runs predicted human pass rate best; margin features (moves
  left) were best taken from the top ~15% of runs. Kristensen, Valdivia & Burelli 2020
  (<https://arxiv.org/abs/2306.14626>, Lily's Garden): moves needed in the agent's best ~5% of
  runs predicted human completion best, and the agent ranked levels like humans even while
  playing worse than them.
- **Personas, not learners.** Holmgård et al.'s procedural personas
  (<https://ojs.aaai.org/index.php/AIIDE/article/view/12849>; evolved follow-up
  <https://arxiv.org/abs/1802.06881>) are agents that differ by hand-set utility weights per
  play style. None models learning between attempts. Isaksen & Nealen 2015
  (<https://ojs.aaai.org/index.php/AIIDE/article/view/12846>) model learning statistically
  (Flappy Bird, 175M sessions). No published playtest agent carrying a "memory of what killed
  it" was found.
- **Full RL is a poor fit here.** RL difficulty estimation exists for single-level puzzle
  games, not long tactics campaigns; training takes days (Roohi); deep RL rarely transfers
  between games (EA SEED, <https://arxiv.org/abs/1903.10545>); and agents memorise
  deterministic environments (Zhang et al., <https://arxiv.org/abs/1804.06893>; Machado et
  al.'s sticky actions, <https://jair.org/index.php/jair/article/view/11182>). A save state
  with a fixed RNG is the worst case.
- **Learning short of RL**, if ever wanted: N-Tuple Bandit EA over discrete parameters
  (<https://arxiv.org/abs/1705.01080>, <https://arxiv.org/abs/1802.05991>), or Bayesian
  optimisation (<https://arxiv.org/abs/2005.07677>).
- **Fairness between versions:** no study controls for roster size directly. Closest practice:
  the same number of runs and the same search per version, and the whole pass-rate-vs-runs
  curve reported (RAPP, <https://www.kmjn.org/publications/GVGprofiles_Evostar15.pdf>).
