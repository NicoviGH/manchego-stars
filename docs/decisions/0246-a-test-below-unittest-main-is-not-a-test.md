---
id: 246
title: "A test below `unittest.main()` is not a test"
date: "2026-08-15"
section: "Operational Gotchas (durable)"
issues: []
---

# A test below `unittest.main()` is not a test

`make test` — what CI runs — executes each file as a **script**, so `unittest.main()` collects
only what is defined by the time it is reached and then exits. In `tools/test_build_campaign.py`
that call sat at line ~4776 of a 5723-line file, and the **twelve TestCase classes below it — 88
tests, including all 26 of `Ch04Stage4Scenes` — had never run.**

**Nothing could have told us.** The file passed. The suite was green. `python3 -m unittest` still
collected all 490, so the two ways of running the suite disagreed in silence, and the only visible
symptom was a test count nobody had reason to compare. Every one of the 88 passed once enabled,
which is the point: this was not latent rot, it was 88 assertions we believed we had and did not.

The runner now lives at the end of the file, and `check.py check_every_test_actually_runs` fails
the build for any TestCase defined after it. Same family as
`check_verdict_scenarios_are_guarded`: **a green suite that is not measuring what it claims.**

Found while reviewing #25's branch for merge, from a 402-vs-490 discrepancy between `make test`
and `-m unittest` that was worth one command to chase.

_Decided: 2026-08-15._
