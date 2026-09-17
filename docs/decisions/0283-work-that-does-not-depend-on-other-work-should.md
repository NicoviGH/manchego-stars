---
id: 283
title: "Work that does not depend on other work should not wait for it"
date: "2026-09-17"
section: "Operational Gotchas (durable)"
issues: [382]
---

# Work that does not depend on other work should not wait for it

Three schedules were wrong, in the same way: independent work run in sequence, or run at all
when nothing asked for it.

**A docs-only commit built a GBA ROM.** 98 of the last 200 commits touch only markdown, and
the workflow had no path filter, so every HANDOFF refresh checked out the submodule, installed
agbcc, injected the campaign and linked a ROM. The filter is an **allowlist of inert files**,
never `**.md`: `docs/scenes/` is a GENERATED book that `test_scene_preview.py` regenerates and
diffs, and `AGENTS.md` / `CHAPTERS.md` / `CLASSES.md` are derived or linted, so a broad glob
would skip exactly the tests that police them. The narrow list covers **96 of those 98**
commits — `HANDOFF.md` alone is 80 — and `checks.yml` keeps NO filter at all, because catching
docs that point at deleted files is most of its value and a docs-only change is when it matters.

**`make test` and `make green` were serialised inside one job** — 53s then 129s, back to back,
for two things that share nothing. They are two jobs now, so the wall clock is the ROM build.

**The test loop ran 57 files one at a time, in two places.** The Makefile had a shell `for`
and `check.py` had a Python `for`: two implementations of one decision, each the slowest thing
in a commit. `tools/run_tests.py` is now the one runner and both callers go through it, so the
gate and the target cannot drift into testing different sets.

These two changes MULTIPLY, and measuring them apart hides that. The caching of #380 removes
the I/O the loop was blocked on; parallelism then has real CPU work to spread. Measured on
this machine (8-core Apple Silicon, python 3.12.13), whole Python suite:

| tree | serial | `-j8` |
|---|---|---|
| before #380 (uncached) | 292.6s | 133.6s |
| with #380 (cached) | 134.8s | **31.9s** |

**9.2x end to end**, and the pre-commit hook -- `tools/check.py` in full -- goes from the
6-10 minutes HANDOFF documented, to 198.7s with #380 alone, to **49.9s** with both.

Threads, not processes: each unit of work is already a subprocess, so the pool waits on the
OS rather than contending for the GIL. Failures are reported in DISCOVERY order, never
completion order, so a report never depends on which worker finished first.

⚠️ **The measuring lesson, which cost a wrong number published to a PR:** `feat/382` branched
from `main`, so its first numbers were taken on a tree WITHOUT #380. They were internally
consistent and completely misleading about the destination -- they made parallelism look like
a 2.2x win over a 292.6s baseline that would not exist once #380 landed. **Measure a change on
the tree it will live in**, which means rebasing onto its dependency before quoting a figure.

**The pre-commit hook ran on a different interpreter than everything else.** Git runs hooks
with the user's environment, so a bare `python3` there resolved to the system 3.9.6 while
`make` (via the macOS PATH shim) and CI both ran 3.12 — observed live during #380's commit.
`make python-bin` is now the one place that choice is made and the hook asks for it.

⚠️ **The split also cost a red CI run, and the lesson is worth more than the fix.** The new
`tests` job was given a trimmed dependency list under a comment asserting it ran "pure logic".
It does not: `test_map_tileset` and `test_map_retile_workflow` reach `gen_map_editor`, which
builds the decomp's own `gbagfx` to turn PNGs into 4bpp, so the job needs `build-essential` and
`libpng-dev` even though it links no ROM. **Splitting a job means discovering what it actually
needed, and a comment stating what a job needs is a claim, not a fact** — this one was written
from an assumption and CI disproved it in 53 seconds. What the job legitimately skips is the
expensive half: agbcc, the ARM toolchain and the decomp build.

**The rule: a filter that skips a job must be an allowlist of things nothing derives from, and
the two copies of it must be machine-checked.** GitHub Actions has no YAML anchors, so
`build.yml` states its `paths-ignore` twice, and the failure mode is silent and backwards — if
the `pull_request` copy ignored a path the `push` copy did not, a PR would skip the ROM build
and the merge would run it, so main breaks having been green on the PR.
`check_build_workflow_filters_agree` pins that, and `tools/test_check_build_workflow.py` pins
that the guard actually goes red, because a gate only ever run against a passing tree has
never shown it can fail.
