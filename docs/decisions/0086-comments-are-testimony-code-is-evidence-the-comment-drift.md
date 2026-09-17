---
id: 86
title: "Comments are testimony, code is evidence — the comment-drift guard (post-mortem of the \"zeroed growths\" incident)."
date: "2026-07-02"
section: "Weapon & Magic Systems"
issues: []
---

# Comments are testimony, code is evidence — the comment-drift guard (post-mortem of the "zeroed growths" incident).

A stale `build_campaign.py` section header claimed "zeroed personal growths / pure class rate" long after
donor-parity replaced that mechanism; an ADR then cited the comment as fact and had to be corrected twice
(PRs #120/#121) — while the *tests* pinning the real donor behavior were green the whole time. Root cause:
comments restating WHAT code does are unverified duplication (a single-source-of-truth violation), and the
existing dead-concepts lint scanned docs only, with patterns too narrow for the comment's phrasing. Settled:
- **The dead-concepts lint scans hand-written CODE comments too** (`check.py` `CODE_GLOBS`: tools py/lua/sh,
  engine C, Makefile — decomp submodule, generated files, `check.py` itself, and `test_*` fixtures exempt),
  and `check_tool_refs_exist` now also catches dangling `tools/…`/`docs/…` pointers in code comments
  (gitignored targets = declared build artifacts, not rot). Regression-pinned by
  `tools/test_check_comment_drift.py`, including the exact incident line.
- **Registry discipline:** a change that RETIRES a mechanism or term registers its key phrases in
  `DEAD_CONCEPTS` in the same commit — that registration is what makes the lint effective; the incident's
  phrases were registered but too narrowly (now broadened). This joins the Definition of Done.
- **Write rules:** a comment says WHY; the WHAT belongs to the code and its tests. An ADR asserting a
  mechanical fact must be verified against the implementing symbol (cite it), never against nearby prose.
  Semantic drift the lint can't see is caught by the same rule in review: header comments of touched
  sections are in scope for every diff review.
- A full 7-agent comment-vs-code sweep of the hand-written tree ran with this change; findings fixed in the
  same PR.
_Decided: 2026-07-02 (CLAUDE after Nicolas caught the propagated stale comment; guard + sweep in one PR)_
