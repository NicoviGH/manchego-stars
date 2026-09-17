---
id: 257
title: "Three things it found on the day it was built:"
date: "2026-08-23"
section: "Operational Gotchas (durable)"
issues: []
---

# Three things it found on the day it was built:

- **ch05's host block is FULL** — `0x9E4-0x9F5`, all eighteen spent. The next ch05 scene costs
  a redesign, not an id. Nobody had computed that, because until now nothing could.
- **ch04 lends two ids to ch05** (`0x9C9`, `0x9CA`, for the ending it mines), so "free" has to
  mean *claimed by nobody* rather than *not claimed by the owner*. Counting the owner's own
  claims would have reported four free ids that are not.
- **ch01 declares five events and has written two.**

**A block range must be DECLARED, never inferred.** The ranges lived in prose beside each
chapter's constants and are now data (`HOSTED_CHAPTER_MESSAGE_BLOCKS`). The temptation is to
derive the block from the ids a chapter claims — and that is circular: a range computed from
its own contents can only ever report itself as full, which is precisely the question it
exists to answer. A chapter with no declared entry (ch01, ch02, which predate the registry)
reports **unknown**, because "0 free" would read as *full* when the truth is *nobody wrote it
down*. `assert_message_blocks_disjoint` now refuses overlapping declarations at build time —
`assert_message_ids_unique` catches two chapters writing one id; this catches the setup that
makes that inevitable.

**Reporting has its own correctness.** A `record` scenario produces FRAMES — its output IS the
picture — so it never stores a verdict, and printing "never run" beside twelve of ch05's read
as a chapter in trouble when nothing was wrong. Likewise an unrun scenario is not a failing
one: blurring the two pushes someone into a playtest run to find out which, which is the exact
cost this command exists to save. And whether a stored PASS still applies to the tree as it
stands is `matrix.py run --dry-run`'s question — deliberately not re-answered here, because
two answers to one question is the drift this replaces.

**One reader for the chapter YAML** (`campaign_chapters.py`). `docs/CHAPTERS.md` and this
answer different questions off the same facts, and two readers is two chances to disagree
about what a chapter says. The refactor was gated on `docs/CHAPTERS.md` coming out
byte-identical (`ade831f6…` before and after), not on the suite passing.

**What is NOT in it, and why.** #312's sixth scope item — which `ChapterEventGroup` fields are
WRITTEN vs INHERITED — says in the issue that it *"shares the census guard's data"*. That guard
is **#313**, which is not built. The report names the gap and points at #313 rather than
growing a second census: two censuses would be two answers, which is the failure mode this
whole change is against.

_Decided: 2026-08-23. Proof: 21 unit tests; `docs/CHAPTERS.md` byte-identical across the
shared-reader refactor; the report renders for all nine chapters including the unbuilt ones._

---
