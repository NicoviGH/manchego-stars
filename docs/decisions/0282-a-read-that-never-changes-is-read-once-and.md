---
id: 282
title: "A read that never changes is read ONCE, and ours was read 114 times"
date: "2026-09-17"
section: "Operational Gotchas (durable)"
issues: [380]
---

# A read that never changes is read ONCE, and ours was read 114 times

`build_campaign.vanilla_decomp_text` shells out to `git -C fireemblem8u show HEAD:<file>` because
the working tree is injected and only HEAD is vanilla. That part was right. What was wrong is that
it did so on **every call**, and HEAD does not move inside a process.

One `difficulty.curve_report` made **148 of those calls against 9 unique files** — `src/events_udefs.c`
(1.78 MB) **114 times** — **199 MB of subprocess I/O to obtain 2.1 MB of content**. In
`tools/test_difficulty.py` that was 1,862 calls, ~50s of a 151s run.

Two more instances of the same shape sat beside it:

- `difficulty.vanilla_unit_defs` called `vanilla_redas(text)` for every UnitDefinition array it
  parsed — a whole-file `re.finditer` over that same 1.78 MB, **5,507 times**, 27.4s of pure CPU
  for an answer that cannot differ.
- 400 `yaml.load` calls ran on the pure-Python scanner while libyaml was installed. The injector
  had already learned this once and written `_yaml_load` — **and being private is precisely why
  the lesson did not travel**: `difficulty.py` reached past it to `bc.yaml.safe_load` and paid 25s.

**~102s of a 151s run was work that had already been done.** The visible symptom was in HANDOFF,
recorded as an operating instruction rather than as a bug: *"A commit takes 6-10 MINUTES here and
is not hung… CPU stays near zero while it does."* Near-zero CPU over ten minutes is not a slow
test suite. It is a blocked one, and the pre-commit hook runs every test file.

**Measured, python 3.12.13:**

| | before | after |
|---|---|---|
| `tools/test_difficulty.py` | 125.3s | **15.6s** (8.1x) |
| `tools/test_chapter_status.py` | 32.8s | **16.2s** (2.0x) |
| `make test` (whole suite) | — | **136s** |

The fix is three memos and one deletion: `lru_cache` on `vanilla_decomp_text` (which also makes it
return the SAME str object, so keying `vanilla_redas` on the text is O(1)), `lru_cache` on
`vanilla_redas`, and the loader moved to `tools/yaml_loader.py` where both the injector and the
Pillow-free CI job import the one copy.

**The memo is BOUNDED (`maxsize=64`), and the precondition is checked rather than assumed.** It is
sound only because HEAD does not move inside a process: the two `git checkout` calls in
`build_campaign` both restore the WORKING TREE from HEAD (`checkout HEAD -- <paths>`), and nothing
in-tree does a `reset` or a branch checkout on the submodule. `cache_clear()` is the escape hatch
if that ever changes. The bound exists because today's readers touch ~9-22 files, but #365 proposes
a `ROMChapterData` census — and a census is exactly the caller that would walk a big slice of a
6,361-file decomp and pin it all in memory.

**What was weighed against it**, once the remaining cost was measured at 2.7% of a 31.3s run
(`vanilla_decomp_text` 1,862 calls -> 22, 69.2s -> 0.80s):

| alternative | ceiling | why not |
|---|---|---|
| `git cat-file --batch` | 24 spawns -> 1; spawn overhead ~28ms (32ms `git show` vs 4ms plain read) | ~0.6s of 31.3s, against a process lifecycle to own |
| cross-process disk cache on (HEAD sha, relpath) | ~12s aggregate CPU, ~1.5s wall under `-j8` | the only option that beats the memo, and still ~5% — for a stale-cache failure mode |
| thread the text through call sites | same result, no retention | ~30 call sites; `class_base_stats(classes_text=...)` already shows the shape |
| read the working tree | — | that is the bug this function exists to prevent |

The deletion matters as much: **`_vanilla_decomp_text_at_head` was a byte-for-byte duplicate of
`vanilla_decomp_text`**, with four call sites — including the `events/*-eventudefs.h` reads the
profile caught repeating 18 and 10 times. A second copy is a second thing to forget to cache, and
it had been forgotten. Same lesson as *"A map's tileset has one home"* and *"Three routes to one
sidecar"*: the duplicate is not a style problem, it is where the bug lives.

**The rule that outlives this: a pure read of an immutable source is memoised at its one home, and
a helper that other desks need is PUBLIC.** A private fast path is a fast path exactly one caller
gets. `tools/test_decomp_read_cache.py` pins all of it — including that the memo is per-relpath, so
caching can never collapse two distinct files.
