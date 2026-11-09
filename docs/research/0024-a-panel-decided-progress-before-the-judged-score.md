---
id: 24
title: "A model-simulated panel, on Nicolas's instruction, decided admitted plans rank progress before the judged score: 14 deaths to 18 on the pinned suite, wins and clean clears tied"
date: "2026-11-02"
section: "Playtesting bots"
issues: [510, 564, 565]
tags: [panel, planner, rank, value, progress, fallback-sacrifice, paired-comparison]
---

# A model-simulated panel, on Nicolas's instruction, decided admitted plans rank progress before the judged score: 14 deaths to 18 on the pinned suite, wins and clean clears tied

**What this is.** On 2026-11-02 Nicolas delegated one call to the step-9 advisory panel of
record 0023: "convene the panel again with sidecar and have them make a decision". The six
roles were played by models again. **These are opinions from simulated personas, not
evidence.** Unlike record 0023, this one is a decision, because Nicolas handed it over. It is
recorded in ADR 0384's amendment of 2026-11-02, "progress before the judged score".

**The question.** Among plans within the risk cap, after forfeits, the win, whole turns behind
and allied greens, which comes first?
- `value`, the judged score: damage, kills, heals and HP taken, worth × chance.
- `progress`, the turns gained toward each unit's goal.

The two orders differ by one line in `planner.lua`'s `ADMITTED`:
- **A** (value, then progress): what #564 was built with. A strike from a tile a step back beats
  a march a step on.
- **B** (progress, then value): a unit chips only from a tile as far forward as its march.

**The measurement.** Both orders were played on #564's head (7bd05c6a) with only that line
changed (the whole suite, tuning and held-out seeds, 52 runs), and only the tuning seeds were
read (26 runs):

| | PR-C (main) | B | A |
|---|---|---|---|
| clean clears | 10 | 14 | 14 |
| wins | 22 | 23 | 23 |
| protected deaths | 12 | 14 | 18 |
| over-cap deaths, all on labelled `FALLBACK_SACRIFICE` turns | 6 | 8 | 13 |
| turns | 245 | 249 | 242 |

- **Where they differ:**
  - vanilla Ch5 seed 1002: B clean; A three deaths.
  - scout-ch10, both seeds: B no deaths; A one death on turn 3 in each.
  - Manchego Stars ch01 seed 1001: A one death fewer.
  - Manchego Stars ch03: one death in each order, on opposite seeds.
  - vanilla Ch4 seed 1002: B skipped a village.
- **On the run endpoint (ADR 0385):** 5 runs differ, 4-1 against A.
- **CPU** is not comparable across days, so the cost was timed again on one quiet machine,
  PR-A's code and B back to back, in both orders: +34% and +20%, +26% pooled. That is over
  SC-003's 20%. Nicolas merged it anyway and opened #566 to bring it back.

**The panel.** The sidecar served the cheaper models only intermittently; its frontier models
all returned HTTP 402. On Nicolas's instruction ("keep trying or use anthropic models"), seats
it could not serve went to Anthropic models as subagents. Each re-seated seat got its round-1
answer as a recap.
- **Round 1:**
  - Reyes (game-AI search): GPT-6 Luna Pro.
  - Brandt (RL/ML): MiniMax M3.1 Flash.
  - Hale (engineering): DeepSeek V4.1 Flash.
  - Mori (Fire Emblem design): Qwen 3.8 Flash.
  - Nair (playtesting): Claude Sonnet.
  - Wójcik (statistics): Claude Opus.
- **Round 2:** all six seats were Anthropic models. Reyes and Hale were on Opus, Mori on Sonnet
  and Brandt on Haiku; Nair and Wójcik kept their round-1 subagents.

**The decision: B, 6-0 in both rounds.** Where the seats converged:
- **The endpoint decides.** It is any protected unit's death on attempt 1. On it, B leads and
  ties on everything else that matters. A's seven fewer turns are on a column nobody chose.
- **The evidence is a direction, not a proof.** The sign test on the 5 differing runs gives
  p = 0.375, and P(B better) is about 0.8 to 0.9 under a flat prior. B itself moved from 12 to
  14 deaths across unrelated fixes, about the size of the gap. Brandt withdrew calling it a
  "textbook proxy failure". The owner delegated a decision, so the panel took the arm whose
  point estimate wins on the endpoint.
- **The mechanism is a hypothesis.** A chip from a step back may leave units placed so that one
  or two turns later every plan is over the cap. A never breaks the cap: it exploits its
  one-turn horizon (Hale).
- **Validity.** Every fallback death the bot's own positioning causes is the instrument's error,
  and it biases a chapter's reading toward "too hard" (Wójcik).
- **B keeps Nicolas's ruling that value is in the rank.** It still breaks progress ties, and a
  chip from a tile as forward as the march is taken.

**What shipped with it, and what did not:**
- **Rename the test that pins A: NOW, 6-0.** It is renamed AND inverted: it pinned A's strike
  (`attack@1,0`) and now pins B's march (`wait@2,0`) as `test_a_march_beats_a_chip_a_step_back`.
  The reviews of that commit added tests beside it:
  - a heal and a kill a step back lose to the march too (each fails under A's order);
  - the chip is played from the march's own tile, though HP left favours the wait there (fails
    with the score out of the rank);
  - the score still breaks a progress tie within float dust.
- **Deferred to #565, in order:**
  1. **A counterfactual flip log:** 5-1 LATER, its own author included. It is logging only, off
     by default, with a byte-identical guard.
  2. **A larger paired run:** about 8 tuning seeds per start.
  3. **A two-ply feasibility tie-break:** 6-0 LATER. It must define which enemy-phase branches
     count, bound its cost and pass pre-registered checks.
  4. **A progress tie band:** 4-2 LATER. It is measured from the best plan, since a pairwise band
     is no order a sort can keep.
- **Rejected as a separate key:** Hale's position-potential key. It duplicates `progress`
  (Wójcik, Nair, Reyes, Mori).

**Full transcript:**
[`transcripts/0024-value-vs-progress-panel.md`](transcripts/0024-value-vs-progress-panel.md),
every turn with its prompt and model, in the order they finished, with the dossier.
