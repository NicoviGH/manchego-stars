---
id: 391
title: "A passing playtest run leaves no dir behind; failing ones are kept, the newest 20"
date: "2026-11-04"
section: "Operational Gotchas (durable)"
issues: [574]
---

# A passing playtest run leaves no dir behind; failing ones are kept, the newest 20

Every tagged run (`run.sh` with `PT_RUN_TAG`, set by `montecarlo.py`'s Pool) made
`/tmp/playtest-<scenario>@<tag>/` with a full copy of the ROM, and nothing deleted it. Nov 1-4
2026 left 1,559 of them, 22.5 GB, and nearly filled the disk (260-640 runs a day).

- **A passing run's dir is deleted once its records are in the runs file and its trace is filed**
  (`settle_run_dir`, on the Pool's main thread, so a kill before the append keeps the dir), and
  its records stop naming a `run_dir`. Passing is an allowlist (`passing`): every BOTRUN record
  `won` or `lost` with a clean `env_status`, and the campaign ended `done` or `played`.
- **Every other run keeps its dir**, marked `FAILED`: a crash, a stall, a fault, a campaign that
  stopped short. Its record names `run_dir` as the evidence. **A COUNT, not an
  age, bounds them: the newest 20** (`KEEP_FAILED`, ~15 MB of logs each at most). An age limit
  would not bound the disk: 640 failing runs in one day is 9.6 GB under a one-day rule. Pruning
  runs at the start of every Pool and after each failure, so old ones go on the next run. A
  cleanup error (a full disk) is printed and dropped: it never costs a run's records.
- **An unmarked dir is a live run or a dead process's**, and only one with nothing in it
  written for 24 hours goes
  (`STALE_S`): a count would race a second Pool's live runs.
- **The ROM is an APFS clone (`cp -c`), not a symlink or hard link.** A clone costs no disk and is
  a file of its own; a link shares the build tree's ROM, which the next `make` rewrites under a
  live emulator. `cp` is the fallback where the disk cannot clone.
- **The matrix**: a passing `verdict` scenario's `/tmp/playtest-<name>` goes once its log is in
  the verdict cache slot, which the outcome then names (`discard_passing_run`). With the cache
  off there is no slot, and the dir is the run's only log, so it stays. A `record` or
  `diagnostic` run keeps its dir (its frames are the product, read by `make_gif.py`), and a red
  keeps its dir until the scenario's next run overwrites it: at most one dir per scenario.
