---
id: 394
title: "The pre-commit hook runs only the unit tests a staged path can reach"
date: "2026-11-07"
section: "Operational Gotchas (durable)"
issues: [579]
---

# The pre-commit hook runs only the unit tests a staged path can reach

Measured 2026-11-07: the hook (`tools/check.py`) took 62 s, and 47 s of it was
`check_tests_pass` running all 127 Python test files whatever was staged, so a HANDOFF-only
commit paid for the whole suite. `tools/test_difficulty.py` alone took 43 s under that load,
the floor of every run.

**Selection.** `tools/run_tests.py` runs each test file under an audit hook
(`sys.addaudithook`) and records, on a pass, what it read: every repo file it opened or
imported, every directory it listed, every glob it matched (`build/test-reads/`, gitignored).
Under the hook (`MS_PRECOMMIT=1`), `check_tests_pass` runs only the files whose record
reaches a staged path. A record is derived from the run, never a list someone maintains, so
it cannot go stale: every run rewrites it. What it cannot know always runs: a test with no
record, one that failed (a failing test keeps none), and one that ran a subprocess the
tracer cannot see into (17 of 127 today: lua, nm, pngquant, `git apply`, a child python).
Git reading the decomp submodule or its build tree is the one subprocess counted as inert,
because neither is ever staged. `make check`, `make test` and CI still run every test.

**Sharding.** `test_difficulty.py` is dealt across three files by TestCase class, with its five
slow classes placed by hand (`HEAVY`). The shards run in 15, 15 and 11 s, against 32 s whole.

Measured after: a HANDOFF-only commit runs 19 test files in 13.5 s; a planner or montecarlo
change runs 53, and a chapter YAML change 83, bounded by the largest shard instead of 43 s.
