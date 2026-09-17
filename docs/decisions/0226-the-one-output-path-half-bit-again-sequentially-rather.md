---
id: 226
title: "The \"one output path\" half bit again, sequentially rather than concurrently (2026-08-19, #25)."
date: "2026-08-19"
section: "Operational Gotchas (durable)"
issues: [25]
---

# The "one output path" half bit again, sequentially rather than concurrently (2026-08-19, #25).

Every `recordenemy` run writes `/tmp/playtest-recordenemy`, **cleared at the start of each run**.
Filming Ravisin and then filming the moose before building her GIF destroyed the first run's
frames, and cost a re-run of a scene Nicolas had already watched — the most expensive thing in
this repo. **Build the artifact before starting the next run**, and treat a shared scratch path as
a resource with one owner at a time. It does not take two jobs racing; two jobs in sequence will
do it.

**And the third case, which the same rule covers: a REPAIR must be verified against the ORIGINAL,
never against the state the previous repair left.** Ravisin's map sprite shipped with holes through
her face because a recovery pass re-derived its colour map by voting on surviving pixels — and the
pixels it needed had already been zeroed by an earlier bad fix, so they had no votes and fell to a
`.get(v, 0)` default. Each fix was checked against its predecessor's damage and looked correct.
