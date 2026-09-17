---
id: 288
title: "Review the WRITTEN surface, and price effort per PR"
date: "2026-09-17"
section: "Working Conventions (Definition of Done)"
issues: [391]
---

# Review the WRITTEN surface, and price effort per PR

`/code-review` is the default on every PR here and that does not change. What changed is *what
it is pointed at* and *what it costs*, after a session where it was run four times and became
the single most expensive thing in the session — twice hitting the limit outright.

## Effort was set globally, so every review was priced at the top

`~/.claude/settings.json` carried `"effortLevel": "high"`. That applies to **every** run, so
reviews were at the expensive end by default rather than by decision. The skill's own contract
is explicit that low/medium returns fewer, high-confidence findings while high→max buys broader
coverage and admits uncertain ones — a trade worth making sometimes, and not worth making
silently every time. Now `medium`, with `high`/`max` asked for per PR.

Worth ruling out while diagnosing this, because both are plausible and neither was true: the
four-parallel-agent `code-review` **plugin is not enabled** here (only `superpowers` is), so
that fan-out never ran; and the skill is not unusually heavy in itself. The cost is
`effort × diff size`, nothing more exotic.

## The diff size was the other half, and that was a choice too

The worst run reviewed a **290-file** PR — the `decisions.md` split, of which 283 files were
mechanically relocated prose. Reading those at high effort found nothing, and could not have:
their correctness had already been established two stronger ways, by a round-trip reassembly
diff (7,780 lines, zero differences) and a token-level corpus check.

**So: when a change is mechanical and a machine gate proves the output unchanged, review the
hand-written surface** — the generator, the guards, their tests — and not the moved bulk.

This narrows scope, never existence. The evidence says the hand-written surface is exactly
where the defects live: on that same PR, review found that the index generator's `squish()` was
stripping `_` and corrupting every identifier it cited, and that a pointer named a decision title
that had never existed. Both were in the ~5 files somebody actually wrote. Neither was in the
283 that moved.

## The general shape

A machine gate and a review answer different questions, and paying a reviewer to re-answer the
machine's question is the waste. **The gate proves the output did not change; the review judges
the code a human wrote.** Where a change has both, give each the half it is good at.

## A gate of ours was wrong about its own invariant

Landing this ADR failed `check_decision_records_wellformed`'s test suite, which asserted
decision ids are **dense** — 1..N with no gaps. They are not, and should not be: ADR 287 sat on
an unmerged branch while this one was written on another, so the correct move was to take the
next free number rather than collide. Main then saw `1..286, 288` and the gate punished exactly
the right behaviour.

Density was an invariant invented alongside the split, not one the corpus needs — the index
sorts by id and never counts. **Uniqueness is the real requirement**, because a collision costs
a decision while a gap costs nothing, so that is what the test holds now.
