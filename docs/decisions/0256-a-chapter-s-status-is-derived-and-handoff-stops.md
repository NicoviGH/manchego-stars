---
id: 256
title: "A chapter's status is DERIVED, and HANDOFF stops carrying it"
date: "2026-08-23"
section: "Operational Gotchas (durable)"
issues: [312]
---

# A chapter's status is DERIVED, and HANDOFF stops carrying it

**50 of ch05's 102 commits touched only `docs/` or `HANDOFF.md`** — the session-boundary tax,
and mostly a human writing down state the repo already knew. `make chapter CH=ch06` answers
it instead: `terraform plan` pointed at a chapter.

Every row is derived at the moment you ask, from the one place that fact lives — scenes from
the chapter YAML's `events[]`, headroom from the id-ownership registry, art from the asset
directories, verdicts from the matrix's own verdict cache. Nothing is kept up to date because
nothing is written down.
