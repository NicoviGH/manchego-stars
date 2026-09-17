---
id: 21
title: "Process: the superpowers workflow layers ON TOP of this knowledge architecture (not a replacement)."
date: "2026-06-19"
section: "Working Conventions (Definition of Done)"
issues: []
---

# Process: the superpowers workflow layers ON TOP of this knowledge architecture (not a replacement).

The repo predates the superpowers plugin; the two are orthogonal. Superpowers is a per-task *process*
(brainstorm → spec → TDD → verify → review → finish-branch); the conventions above are the *knowledge
architecture* (single source of truth, ADRs here, issues-as-backlog, docs generated from YAML, the
`check.py` drift guard). We adopt the superpowers process habits where additive and keep this knowledge
architecture authoritative — it is the more drift-resistant half (a standalone `docs/superpowers/specs/`
design doc would be a fourth place a spec can rot, invisible to the drift guard). **Override:** the
brainstorming skill's spec lands as an ADR here (the decision) + a GitHub issue (design + execution
checklist), NOT a `docs/superpowers/specs/` file — don't reintroduce that path.
_Decided: 2026-06-19 (Nicolas)_
