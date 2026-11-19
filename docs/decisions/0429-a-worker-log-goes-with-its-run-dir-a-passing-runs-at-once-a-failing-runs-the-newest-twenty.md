---
id: 429
title: "A worker log goes with its run dir: a passing run's at once, a failing run's the newest twenty"
date: "2026-11-19"
section: "Operational Gotchas (durable)"
issues: [667, 574, 510]
---
# A worker log goes with its run dir: a passing run's at once, a failing run's the newest twenty

**Decided 2026-11-19 (#667).** It extends #574's run-dir rule (`prune_runs`, `KEEP_FAILED`) to
the worker logs.

**The problem.** The disk filled up (5.0 GB free of 228). `montecarlo.py`'s pool writes one
worker log per run into the store's `workers/` folder. Each log is run.sh's stdout, which `cat`s
the emulator's whole log, so it holds tens to hundreds of MB. Nothing ever deleted one: 5,085 of
them, 11.5 GB, that no record named were deleted by hand. A record names its log (`log`) only
for a run with no result, and copies the log's last lines into itself (`log_tail`). Only people
read the path.

**The rules (`montecarlo.py`).**
1. **A passing run's log is deleted as the run ends**, with its run dir (`settle_run_dir`). Its
   records say everything it said.
2. **A failing run's log is kept, marked ended, but only the newest `KEEP_FAILED` (20)**, like
   its dir. Settling a failing run makes its log read-only (`ENDED_MODE`). `prune_logs` runs
   when a pool starts and after each failing run, sharing the newest-N bound (`surplus`) and
   one listing of the run dirs with `prune_runs`.
3. **A log whose run may still be playing is neither counted nor touched** (`log_ended`). A log
   has ended when it is marked read-only, or when it is dead: written `STALE_S` (24 h) ago with
   no tagged run dir left (a killed pool never settles its runs, and `prune_runs` reaps their
   dirs once idle that long). Neither the log's age nor its dir can tell a live run alone:
   run.sh writes nothing to the log while a run plays, and makes the run dir only once the
   emulator starts, after any checkpoint build (up to 900s). A launch that dies before its dir
   exists still settles, so its log is marked and bounded too.
4. **The launches outside a pool** (a snapshot's check, a diagnostic replay: `launch_tagged`)
   settle their log the same way.
5. **Records (`*.jsonl`), `traces/` and `states/` are never pruned.** They are the data. A
   record's `log` path may outlive its file, and its `log_tail` stays.

`KEEP_FAILED`'s comment now states the real size: a campaign's dir and its log are ~160 MB each,
so each is bounded at ~3 GB, not "~15 MB each".
