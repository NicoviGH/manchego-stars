---
id: 247
title: "A skip guard must key on a symbol only WE write"
date: "2026-08-16"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A skip guard must key on a symbol only WE write

`test_the_live_ch05_group_deploys_our_table` asserts against the INJECTED decomp, and it
correctly carried a skip for a clean checkout — keyed on `struct ChapterEventGroup Ch6Events`.
**That is vanilla's own symbol.** It is present in a pristine tree, so the guard never fired, and
on CI — which runs `make test` before any injection — the assertion ran against vanilla data and
duly reported our roster pointer missing.

**Three separate things had to be true for this to stay hidden, and all three were.** The class
sat below `unittest.main()` and had never run (see "A test below `unittest.main()` is not a
test"), so the broken guard was never exercised. The symbol it tested was plausible — it names
the very structure the test is about. And **it could not fail on a developer machine**: any tree
that has run a build is injected, so the guard's flaw is invisible exactly where the tests get
run most. Waking 88 dormant tests and watching them all pass locally was not the evidence it
looked like.
