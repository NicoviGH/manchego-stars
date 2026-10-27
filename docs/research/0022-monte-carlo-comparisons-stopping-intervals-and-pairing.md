---
id: 22
title: "Monte Carlo comparisons: stopping when the interval excludes 0 inflates false findings; binary rates need Wilson or McNemar, not a normal interval"
date: "2026-10-27"
section: "Playtesting bots"
issues: [510]
tags: [monte-carlo, stopping-rule, sequential-testing, confidence-interval, wilson, mcnemar, common-random-numbers, pairing]
---

# Monte Carlo comparisons: stopping when the interval excludes 0 inflates false findings; binary rates need Wilson or McNemar, not a normal interval

Asked by Nicolas (2026-10-27): what general Monte Carlo practice says about PR F's runner. It
is measured against the #510 plan's F2 rule: pairs `(ours_all_alive, vanilla_all_alive)`
matched by `(seed, style index)`, a 95% normal-approximation interval on the mean paired
difference, settled when `n >= 30` and the interval excludes 0, or at `n = 300`. The rule was
settled in the plan's amendment, so these are findings for Nicolas, not changes.

- **Stopping at the first interval that excludes 0 is "optional stopping".** Checking a
  fixed-n interval after every run and stopping once it excludes 0 pushes the false-positive
  rate well above the nominal 5%. Stopping for a reason unrelated to the observed difference
  does not cause this. There are two standard fixes:
  - **Group-sequential looks:** a few looks planned in advance, with the 5% spent across
    them by an alpha-spending function.
  - **Always-valid confidence sequences:** intervals valid at every n at once, built on
    e-values, at some cost in power.

  Sources: Ramdas, Grünwald, Vovk & Shafer, "Game-theoretic statistics and safe anytime-valid
  inference" (<https://pure.royalholloway.ac.uk/files/58243214/Game_Theoretic_Statistics_and_Safe_Anytime_Valid_Inference_SAVI_.pdf>);
  Spotify's experimentation glossary on optional stopping and always-valid inference
  (<https://confidence.spotify.com/glossary/optional-stopping>).
- **A normal interval misbehaves on a rate near 0 or 1, and pass rates live there.** The Wald
  (normal) interval's coverage can fall far below 95% near the boundary, even at large n. It
  gives bounds outside [0, 1], and zero width at 0/n or n/n (Brown, Cai & DasGupta 2001,
  <https://projecteuclid.org/download/pdf_1/euclid.ss/1009213286>; summary in
  <https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval>). Wilson's interval
  stays in [0, 1] with near-nominal coverage; Clopper-Pearson never under-covers but is
  conservative. A chapter's all-alive rate is often near 1 (an easy chapter) or near 0 (a
  wall), so this is the usual case here, not an edge.
- **Paired binary outcomes are McNemar's case.** With d_i in {-1, 0, +1}, only the DISCORDANT
  pairs carry information: one side cleared and the other did not. Concordant pairs add
  nothing. Power and sample size depend on how often pairs disagree; with few expected
  discordant pairs (under about 10), the exact conditional binomial test is preferred over
  the normal approximation (SAS PROC POWER's McNemar default,
  <https://support.sas.com/documentation/cdl/en/statug/67523/HTML/default/statug_power_syntax49.htm>).
  A normal interval on the mean of d_i with mostly zeros is the setting where it is least
  reliable.
- **Pairing is "common random numbers", and it pays only when the pair is positively
  correlated.** Driving both systems with the same random inputs shrinks the variance of their
  difference by the covariance; the paired interval beats the two-sample one when the
  within-pair correlation is positive (Georgia Tech ISyE 6644, "Comparing Systems",
  <https://www2.isye.gatech.edu/~sman/courses/6644/Module10-ComparingSystems-201128.pdf>;
  Glasserman & Yao on when CRN is guaranteed to help,
  <https://business.columbia.edu/sites/default/files-efs/pubfiles/4261/glasserman_yao_guidelines.pdf>).
  CRN needs a separate random stream per system so the two stay in step (Haas, UMass CS590M,
  <https://people.cs.umass.edu/~phaas/CS590M/slides/slecture11a.pdf>). A 2025 paper casts
  paired-seed evaluation of agent simulators the same way (<https://arxiv.org/abs/2512.24145>).
  Ours pairs two different games (ours vs the vanilla twin) by seed and style index. The
  style is common to both; the game's RNG stream is not (different maps consume it
  differently). So how much the pairing buys is an empirical question: the measured
  correlation of the pairs says.
- **Multiple chapters x modes are multiple comparisons.** Each settled cell is one test at 5%,
  so over ch00-ch07 x three modes (24 cells) about one cell is expected to show a "difference"
  by chance alone. Nelson 1993 on comparisons with the best under CRN
  (<https://ideas.repec.org/a/inm/ormnsc/v39y1993i8p989-1001.html>) is the simulation-side
  treatment.
