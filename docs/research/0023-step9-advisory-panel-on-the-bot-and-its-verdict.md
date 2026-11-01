---
id: 23
title: "A model-simulated expert panel reviewed step 9's bot and verdict: keep the ROM sandbox, rank survival first, measure deaths on attempt 1, calibrate against humans"
date: "2026-11-01"
section: "Playtesting bots"
issues: [510]
tags: [panel, review, planner, risk-cap, verdict, endpoint, equivalence, human-calibration, retry-memory]
---

# A model-simulated expert panel reviewed step 9's bot and verdict: keep the ROM sandbox, rank survival first, measure deaths on attempt 1, calibrate against humans

**What this is.** On 2026-11-01 Nicolas asked for an adversarial review of #510 step 9 from
outside the project. Six expert roles were played by different frontier models through an
advisory tool. **These are opinions from simulated personas, not evidence**: nothing here is a
source in the sense of the other records, and nothing here is a decision. What Nicolas decided
from it is in ADRs 0384, 0385 and 0386. The plan built from it is on #510.

**The panel.** Each role was played by one model, re-seated on another (with a recap) when a
provider failed:
- a game-AI search researcher;
- a playtesting lead;
- a Fire Emblem designer;
- an engineering lead;
- a simulation statistician;
- an RL/ML engineer.

The models were OpenAI GPT-6.1 (Sol Pro, Terra Pro, Sol), Google Gemini (4 Argon, 3.8 Flash),
xAI Grok (4.7, 4.6), Qwen (3.8 Max Prime, 3.7 Plus, 3.8 Flash) and GLM 5.3 Prime.

**What they read.** A dossier covering the HANDOFF, all of #510 with its commits and PRs, the
step 9 ADRs, and research records 0001, 0021 and 0022. It also carried three web-research
summaries on bot playtesting, multi-unit planning and Monte Carlo statistics. The dossier is
appendix A of the transcript.

**The rounds.**
1. Each role critiqued the work so far.
2. They cross-examined each other.
3. Under a shared brief (appendix B) they drafted a job to be done and a spec, then revised it
   over two more rounds of challenges.
4. They signed off on version 3 (appendix C).

**Where they converged:**
- **Keep the real-ROM sandbox.** Running FE8's own functions is the project's strongest asset.
- **Replace death pricing with a survival-first rank and per-style risk caps.** A weighted score
  lets loot buy risk (the Ch3 Franz strike, ADR 0375). → ADR 0384.
- **Drop the whole-route bar as a gate and measure graded outcomes.** Clean clear becomes one
  derived column, and the endpoint is any player death on attempt 1. → ADR 0385.
- **Freeze the bot behind a pinned regression suite with held-out seeds.**
- **Measure pairing before relying on it.** Run a 50-seed pilot before any confirmatory run.
- **Calibrate against humans by failure mode, not by rate.** → ADR 0385.
- **No per-chapter scoring rules**, and the ROM stays the only source of outcomes.

**Where they disagreed, and how it was settled:**
- **Proposed:** a hard kill rule tying the bot to a community difficulty ranking. Rejected:
  13 chapters are too few, and it invites gaming the metric.
- **Proposed:** a full search bake-off. Too early. They settled on a second enemy phase only
  at commit points (doors, boss range, known arrivals), plus two diagnostic probes.
- **Risk-cap values and the equivalence margin:** left open. Nicolas set them. The panel's ±5
  margin turned out to be unreachable at 200 pairs (ADR 0385).

**Full transcript:** [`transcripts/0023-step9-advisory-panel.md`](transcripts/0023-step9-advisory-panel.md),
every turn with its prompt, in the order they finished. Read it only to revisit an argument; it
is about 225 KB.
