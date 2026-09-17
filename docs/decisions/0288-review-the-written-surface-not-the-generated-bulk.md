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

## Effort was set globally, and the per-review lever was never used

`~/.claude/settings.json` carried `"effortLevel": "high"` — the model's **global** reasoning
effort, which applies to every session in every project and so to every review run here. Reviews
were therefore at the expensive end by default rather than by decision. It is now `medium`.

The lever that belongs to a review is the level the skill takes as an **argument**:
`/code-review <PR> high`. Its contract is explicit that low/medium returns fewer, high-confidence
findings while high→max buys broader coverage and admits uncertain ones — a trade worth making
sometimes, and not worth making silently every time. **The two must not be confused.** Raising
`effortLevel` to buy one deep review raises the price of everything that comes after it, in this
repo and outside it, which is the failure this record exists to stop; asking `/code-review` for
`high` on the one PR that earns it costs only that run.

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

This narrows scope, never existence. Every defect these mechanical changes actually produced sat
in the handful of files somebody wrote. On the split PR the gate `check_tool_refs_exist` caught
the index generator's `squish()` stripping `_` and corrupting every identifier it cited, and
`check_no_dead_concepts` fired on 17 lines whose exemption the move had invalidated (both in ADR
0284). On its sibling #386, review caught a pointer naming a decision title that had never
existed, three more broken the same way, and a fourth that paraphrased its target (ADR 0285).

Note what that does *not* say: on the split PR itself, the finds were the gates' and not the
reviewer's. That is the same argument from the other side — the machine checks are cheap and ran
over everything, while the expensive attention was spent on 283 files that had already been
proven byte-for-byte. **Not one defect, from either source, was in the bulk that moved.**

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
sorts by id, and the header counts RECORDS (`len(found)`), never the id range, so a gap changes
nothing it prints. **Uniqueness is the real requirement**, because a collision costs a decision
while a gap costs nothing, so that is what the test holds now.
