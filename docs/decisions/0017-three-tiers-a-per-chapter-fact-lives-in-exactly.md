---
id: 17
title: "Three tiers; a per-chapter fact lives in exactly one place (the YAML)"
date: "2026-05-31"
section: "Documentation Model"
issues: []
---

# Three tiers; a per-chapter fact lives in exactly one place (the YAML)

The doc set kept duplicating per-chapter facts across the YAML, `PRD.md §7`, a hand
table, and the pacing ref — so every story change forced a multi-file resync. The
settled model:
- **Tier 1 — Source of truth = the chapter YAML.** `campaigns/rime-of-the-frostmaiden/chapters/ch*.yaml`
  is authoritative for every per-chapter fact (objective, recruits, enemies, map,
  rewards, `unlocks_chapter`). Edit the YAML; nothing else.
- **Tier 2 — Generated index.** `docs/CHAPTERS.md` is **generated** from the YAML by
  `tools/gen_chapter_index.py`. It is never hand-edited; regenerate after any chapter
  change — `tools/check.py` fails (pre-commit + CI) if the committed index is stale.
  "The data is the doc."
- **Tier 3 — Durable "why" docs, hand-written.** `decisions.md` (settled decisions),
  `roadmap.md` (provisional post-MVP Act II–V scaffold — chapters with no YAML yet),
  `fe8-pacing-reference.md` (FE8-only cadence/reward rules), `PRD.md`
  (vision/scope/architecture/roadmap pointers). These hold rationale and
  forward-looking planning, **not** per-chapter tables.
Rule: do not re-introduce a chapter breakdown table into `PRD.md` or any hand doc —
point to `CHAPTERS.md` / the YAML instead.
_Decided: 2026-05-31 (retires the hand-maintained `chapter-outline.md`)_
