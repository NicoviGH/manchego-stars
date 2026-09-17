---
id: 156
title: "Tutorial-parity is a standing guardrail, not a one-time map."
date: "2026-06-21"
section: "Story & Dialogue"
issues: []
---

# Tutorial-parity is a standing guardrail, not a one-time map.

Combat is vanilla-strict (no new mechanics), but rewriting cutscenes and reordering content can
silently strip the onboarding a vanilla player gets — and vanilla delivers it through BOTH
`PLAY_FLAG_TUTORIAL`-gated boxes AND mandatory story dialogue (a veteran who declines the tutorial
still sees the dialogue half; e.g. Tirado narrating that Ephraim "uses the terrain wisely",
`texts.txt`). Since our chapters are authored as-we-go, any static "lesson → chapter" map rots the
moment a debut moves. So the system is three parts: (1) a **stable catalog** of what vanilla
teaches + channel + decomp citation — `campaigns/.../onboarding-catalog.yaml`; (2) a **living
ledger** in each chapter YAML — an `introduces:` list of the concepts making their first campaign
appearance there and how we cover them (`coverage`: tutorial box vs in-voice dialogue, per the
C-hybrid — boxes for dry systemic lessons, dialogue for threats/narrative); (3) a **dialogue-pass
reflex** (skill step) that cross-checks new firsts against the catalog + prior ledger at
beat-planning and flags the owed heads-up. `tools/gen_onboarding_index.py` rolls up coverage →
`docs/ONBOARDING.md`; `tools/test_onboarding.py` gates integrity (orphan / double-debut concepts)
+ doc freshness. Each concept debuts once. (Catalog citations + precise vanilla trigger chapters
are a living decomp sweep; entries marked "decomp sweep TBD" are grounded as authoring proceeds.)
Follow-up: the ONBOARDING.md freshness check lives in `test_onboarding.py` rather than
`check.py`'s `check_generated_indexes_fresh` because `check.py` is pipeline-lane-owned — fold it in
there via the pipeline lane when convenient (issue/coordination, not a content-lane edit).
_Decided: 2026-06-21 (Nicolas; "build this in as the guardrail so we create freely without dropping vanilla things")_
