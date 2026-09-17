---
id: 96
title: "A blanket `pkill` is a serial-world habit, and parallel dispatch turned it into a saboteur"
date: "2026-08-23"
section: "Distribution & Scope"
issues: [310]
---

# A blanket `pkill` is a serial-world habit, and parallel dispatch turned it into a saboteur

The first FULL gate run after `--jobs` went parallel by default failed three scenarios — `ch01`,
`ch04moose`, `ch04packmath` — each with `RESULT: ERROR -- mGBA exited early`, each after 6s or
21s, and each with `Killed: 9` in its log. Nothing was wrong with the ROM.

`run.sh` opened every run with **`pkill -9 -i mgba`**, to clear a leftover emulator from an
interrupted run. In a serial world that is correct and invisible. With four scenarios in flight it
means **every newly dispatched scenario SIGKILLs the siblings already running** — which is why the
three deaths land at exactly the second the pool started the next scenario, and why the first wave
of four always survived. The kill is now scoped to the scenario's own `/tmp/playtest-<name>/`
(and its `ckpt_` builder), proved on real processes: it kills `ch01` and `ckpt_ch01` and leaves
`ch04moose` alive.

**The measurement missed it because the measurement was exactly four scenarios**, dispatched in
one wave, so no second dispatch ever happened — 71s vs 22s, all four PASS, and the defect sat
underneath. The gate has seven in its canonical group. **A fan-out change has to be measured
ABOVE its own concurrency, not at it**: the first dispatch is the easy case, and the interesting
one is the FIFTH scenario.

`gen_symbols.py` had the same shape of problem one level quieter: every `run.sh` regenerates
`symbols.lua`, `procscr.lua` and `symbols.json`, so four runs rewrite three shared files while
siblings read them. Those writes now go through a temp file and a rename — a reader sees the old
table or the new one, never half of either. No failure was ever traced to it, which is the point:
it would have produced scenarios dying for reasons nobody could reproduce.

`check.py` cannot see a shell race, so the guard is a test: `run.sh` may not kill by program name,
and any kill it does make must name a scenario (`test_playtest_harness.py`).
