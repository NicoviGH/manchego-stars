---
id: 20
title: "Definition of Done for a change:"
date: "2026-06-04"
section: "Working Conventions (Definition of Done)"
issues: []
---

# Definition of Done for a change:

1. Code/data change ships with its doc + YAML updates **in the same commit** (no "update docs later").
2. If it completes tracked work, the commit/PR says `Closes #N`; if it changes scope, open/retitle the issue.
3. `make` builds green; `tools/verify_text.py` is clean after any text change.
4. New non-obvious decision → an entry in this file.
5. Don't commit the `fireemblem8u` submodule pointer (our decomp edits are build artifacts).

**Commits:** imperative subject; reference issues (`Closes #N` / `Refs #N`). Co-author trailer per repo norm.

**Discipline is mechanized, not remembered.** As much of the above as can be is enforced
by machine, at the moment work happens, so it doesn't rely on anyone remembering:
- **`tools/check.py`** is the ONE drift guard (tooling compiles, campaign YAML parses, no doc
  references a missing tool, no resurrected dead concept — denylist, with `decisions.md` exempt
  as the ADR log). Run it with **`make check`**.
- A **git pre-commit hook** (`tools/hooks/pre-commit`, enabled via `core.hooksPath` by
  `setup-toolchain.sh`) runs `check.py` on every commit — **drift literally can't be committed**
  (bypass a genuine exception with `git commit --no-verify`).
- **CI** (`.github/workflows/checks.yml`) runs the same `check.py` plus the real make-green build
  (mock baserom) — the backstop.
- **Known limit:** none of this catches arbitrary prose that contradicts the code without a
  denylisted term. That residue is covered by *single source of truth* (the less a fact is
  restated, the less can drift) and by the agent running `make check` and reporting the result
  when asked "is it clean?" — not eyeballing. When a concept is retired, add its term to
  `DEAD_CONCEPTS` in `check.py` so it can't come back.
_Decided: 2026-06-04_
