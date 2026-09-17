---
id: 285
title: "Context is the budget, and the expensive thing is what enters it early"
date: "2026-09-17"
section: "Working Conventions (Definition of Done)"
issues: [386]
---

# Context is the budget, and the expensive thing is what enters it early

Measured across 37 sessions of this project's own transcripts, rather than reasoned about:

| | raw | billed-equivalent |
|---|---|---|
| `cache_read` — context re-read on every call | 6,819,956,870 | 682M — **82.1%** |
| `cache_creation` — re-caching at 1.25x | 101,882,755 | 127M — **15.3%** |
| output | 21,039,360 | 21M — 2.5% |
| **total** | **6.92 billion** | **830M** |

The cache hit rate is **98.5%**. There is nothing left to win on caching efficiency — it
already works. The cost is structural, and it has two parts.

## 1. Context size, which is 82% of everything

Mean context per call is **335,046 tokens**; one session peaked at **940,921**. Growth in that
session ran at about **+719 tokens of permanent context per call**.

Because every call re-reads the whole context, **cost is `size × remaining calls`, not size** —
the 2,000th call bills roughly 24x what the 1st did for identical work.

No single file dominates. It is accretion: 9,172 Bash calls at **314 tokens** average. What
makes a thing expensive is not being big, it is **entering context early and never leaving**.
That is the whole argument for
[A decision is a FILE, and decisions.md is the index over them](0284-a-decision-is-a-file-and-decisions-md-is.md): a
197k-token file read at call 10 of a 700-call session costs ~13.6M billed-equivalent tokens.

## 2. Cache misses, which are 15.3% from 1.5% of the tokens

A full re-cache rewrites the prefix at 1.25x instead of reading it at 0.1x — **a 12.5x
penalty**. 175 such events were measured. The worst re-paid **433,984 tokens in one call**
while the context did not grow at all.

The trigger correlates cleanly with idle time:

| | n | median gap before | gap > 1h |
|---|---|---|---|
| re-cache events | 175 | 4.7s | **37%** |
| normal cached calls | 20,461 | 5.4s | **0%** |

The prompt cache has a 1-hour TTL. Roughly 40% of these are a session left sitting past it.
**Hand off and start fresh rather than leaving a session idle.**

## What this licenses, and what it does not

It does **not** license rationing tool calls. Bash results average 314 tokens and are cheap;
9,172 of them is not the problem. Two habits already in this repo are measurably right and
should stay:

- **`sed -n`/`grep` over reading a file whole** — 314 vs 18,808 tokens average.
- **Redirect big output to a file and grep it.** `make matrix SUITE=all` run with `> file` and
  `run_in_background` returned a **392-character** tool result for a job that would otherwise
  have put ~450k tokens into context permanently.

What it licenses is ending sessions earlier, and being deliberate about what gets read at the
top of one. The operational form of both lives in `AGENTS.md`.

## Searching

`rg --files` counts 7,423 files here and **6,361 of them (86%) are the `fireemblem8u`
submodule**. Unscoped searches are fast but return decomp matches that then sit in context —
`unit` matches 17,556 times repo-wide against 3,738 scoped. A blanket ignore would be wrong,
because grounding an FE8 claim in the decomp is required; the rule is to scope by default and
reach into the decomp deliberately.

## A pointer that names nothing, and why #384 made it checkable

A review of this change caught it adding `decisions.md` → *"Always use the decomp"* — a title
that has never existed anywhere in this repo. Two more pointers were broken the same way
(`decisions.md` → *"stacked PRs"*, and a `harness.lua` comment naming a rule that lives in
`AGENTS.md`), and a fourth **paraphrased** its target: `ch05.lua` cited *"box count is no longer
a witness"* against a record that says *"box count is **not** a witness"*.

Nothing could have caught any of them before, because the target was a sentence somewhere
inside a 728 KB file. Records with front matter make the legal set enumerable, so
`check_decision_citations_resolve` now holds all 29 of the repo's title-style pointers.

**Getting it to converge took four attempts, and the failures are the lesson.** Matching titles
only called 9 good pointers broken. Adding headings and bold spans still missed prose. Structural
matching anywhere-in-target was so loose the gate could not fail its own test. What works is a
full-text search over the records plus the section names, with two rules: **a probe must be 16+
characters** (which suppresses regex artifacts like `"the 2026-07-23"`), and **a pointer too short
to probe is not reported at all** — "Two arms of one" is a real title truncated by the capture,
and a gate that cannot check something must not claim it is broken. That is #372's rule again:
a check that could not RUN is not a check that failed, either.
