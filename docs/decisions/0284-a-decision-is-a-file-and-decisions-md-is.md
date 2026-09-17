---
id: 284
title: "A decision is a FILE, and decisions.md is the index over them"
date: "2026-09-17"
section: "Documentation Model"
issues: [384]
---

# A decision is a FILE, and decisions.md is the index over them

`docs/decisions.md` was **728,013 bytes — about 196,760 tokens** — and `AGENTS.md`'s Session
Start Checklist named it item 3, to be read *before touching code*. Items 1–3 plus `CLAUDE.md`
came to ~207,670 tokens, which is a whole context window spent before any work begins.

So no session read it. **That is the actual defect: the checklist's most load-bearing line was
being skipped rather than followed, and an instruction nobody can obey is worse than none.**

It was also still growing — 21 KB on 2026-06-01, 155 KB, 294 KB, 635 KB, 728 KB by 2026-09-17.
A 35x increase in three and a half months, with no mechanism that would ever stop it.

## Why size alone understates it

Cost is **size × remaining calls**, not size. Across 37 sessions of this project's transcripts:
6.92 billion raw input tokens, **830M billed-equivalent**, of which **82% is `cache_read`** —
the context re-read on every single call. Mean context per call is 335,046 tokens; one session
peaked at 940,921.

A 197k-token file read at call 10 of a 700-call session therefore costs roughly
`197,000 × 690 × 0.1` ≈ **13.6M billed-equivalent tokens. One file. One session.**

That is the general rule worth keeping: **what matters is what enters context early and never
leaves.**

## The shape

One decision per file, `docs/decisions/` + `NNNN-slug` + `.md`, with front matter (`id`,
`title`, `date`, `section`, `issues`). `docs/decisions.md` keeps its path and becomes a
**generated index** — which is the detail that made this cheap: **160 citations across the repo
point at bare `decisions.md`**, and every one of them still resolves. Nothing had to be
rewritten.

`tools/gen_decisions_index.py` builds it, and the existing `check_generated_indexes_fresh`
holds it the way it already holds `docs/CHAPTERS.md` and `docs/CLASSES.md`.
`check_decision_records_wellformed` holds the corpus: every file parses, ids are unique, and an
id matches its filename.

**Result: 728 KB → 66 KB, an 11x reduction**, across 283 decisions averaging 2.7 KB each.

## What the migration had to survive

The document had grown **two formats**, and a split that dropped either would have silently
deleted years of reasoning:

| | count |
|---|---|
| modern — `### Title (date, #issue)` | 107 |
| early — `**Bold title**` … `_Decided: DATE_` | 176 |

The discriminator matters and took two passes to get right. A standalone `**bold**` line is an
entry when it owns a `_Decided:` line **or** its own title carries a `(YYYY-MM-DD)`. The first
attempt required `_Decided:` alone and under-captured by 7 entries — because the Operational
Gotchas section writes dated titles without a `_Decided:` line. Bold lines that satisfy neither
test are emphasis *inside* an entry (`**A check that is defined and unit-tested is still not
RUNNING.**`), and promoting those would have shredded their parents.

**The gate was a byte-for-byte round-trip, run before anything was deleted:** reassemble the
parsed pieces in document order and diff against the original. 7,780 non-blank lines, zero
differences. A migration is allowed to move prose and forbidden to change it, and the only way
to know which happened is to reconstruct the input and compare.

Four `_<slug>.md` section notes carry prose that belonged to a `##` section rather than to any
one decision — including the whole of *Open Questions*, which contains no decisions at all and
would otherwise have vanished from a decisions-only index.

## Two bugs the existing gates caught, which is the point of having them

`check_tool_refs_exist` reported a dangling `rombgpreview.py`. The real tool is
`rom_bg_preview.py` and it exists — **the index generator's `squish()` was stripping `_` along
with markdown emphasis, corrupting every identifier it cited.** An index that mangles the names
it points at is worse than no index.

`check_no_dead_concepts` fired on 17 lines. Its exemption was the single file `decisions.md`,
and the content had moved out from under it. A decision to RETIRE something must name the thing
it retired — that is the whole content of the record — so the exemption follows the content
into `docs/decisions/`, and everything outside it is still held.

## What this does not fix

The corpus is still ~760 KB in total, and nothing here stops it growing. What changed is that
growth is now **paid for only by the sessions that open a given decision**, instead of by every
session at startup.
