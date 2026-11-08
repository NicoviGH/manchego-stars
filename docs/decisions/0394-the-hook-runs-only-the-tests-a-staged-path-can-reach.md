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
imported (an import served from bytecode is recorded by its code object's source file, since
Apple's python3 keeps the `.pyc` outside the repo), every directory it listed, every glob it
matched (`build/test-reads/`, gitignored). Under the hook (`MS_PRECOMMIT=1`),
`check_tests_pass` runs only the files whose record reaches a staged path; the staged list is
taken with `--no-renames`, so a rename's old path counts too. A record is derived from a run,
never a list someone maintains, but a test the hook skips keeps its old record, and a pull or
branch switch changes files with no run at all. So each record keeps the (mtime, size) of
every file it read, and a record whose reads moved since it was written counts as none.
What it cannot know always runs: a test with no record or a stale one, one that failed (a
failing test keeps none), and one that ran a process the tracer cannot see into (20 of 130
today: lua, nm, pngquant, `git apply`, a child python, a multiprocessing worker, `os.fork`).
A read-only git command (`show`, `grep`, `ls-files`, ...) on the decomp submodule or its build
tree is the one process counted as inert, because neither is ever staged; one that names
another repo path is not. `make check`, `make test` and CI still run every test.

**Sharding.** `test_difficulty.py` is dealt across three files by TestCase class, with its five
slow classes placed by hand (`HEAVY`). The shards run in 15, 15 and 11 s, against 32 s whole.

Measured after (2026-11-07, with the review fixes): choosing the tests takes 0.07 s. A
HANDOFF-only commit runs 22 test files; a `difficulty.py` change runs 53, and a chapter YAML
change 87, bounded by the largest shard (about 22 s alone) instead of 43 s.
