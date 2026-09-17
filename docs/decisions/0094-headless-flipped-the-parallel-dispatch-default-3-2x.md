---
id: 94
title: "Headless flipped the parallel-dispatch default — 3.2x"
date: "2026-08-23"
section: "Distribution & Scope"
issues: [302, 310]
---

# Headless flipped the parallel-dispatch default — 3.2x

`--jobs` had been off since 2026-08-09, and for a good reason: 444s serial against 439s at
`jobs=4`, with four scenarios blowing their WALL-CLOCK deadlines and reporting ERROR/FAIL. That
measurement was never wrong. It was **conditional on being HEADED** — four Qt mGBA windows
contending for one compositor, each still rendering every frame, which is exactly what a 1.01x
with deadline blowouts looks like. #308 deleted the rendering, so the condition changed and the
number had to be re-taken rather than respected or assumed away (`decisions.md` → inherited leads
are hypotheses).

Re-taken on the same Mac (8 logical / 4 performance cores), same four ch03boot verdict scenarios,
one build, `--no-verdict-cache`:

| | wall | per-scenario |
|---|---|---|
| `--jobs 1` | **71s** | 15s / 14s / 20s / 20s |
| `--jobs 4` | **22s** | 15s / 15s / 21s / 21s |

**3.2x, all four PASS, zero deadline blowouts.** The interesting column is the second one: the
per-scenario times are essentially IDENTICAL serial and parallel. There is no contention left to
find — which is what you would expect once no process is rendering.

**Parallelism is gated on `headless`, per SCENARIO, not per group.** `scenario_lanes` now pulls a
headed scenario into the serial lane the same way a checkpointed one has always been pulled
(`states/<name>.ss` is a shared file two scenarios would race to mint). A MIXED group is therefore
not forced serial whole: its headless scenarios still run concurrently and the headed ones run
afterwards, alone, on the caller's thread — so a headed run never overlaps anything and the
2026-08-09 measurement stays the live one for exactly the runs it was taken on.

**The default is derived from the machine, capped at what was measured.** `resolve_jobs` is
`--jobs`, else `MX_JOBS`, else `cpus // 2` floored at 1 and capped at `MEASURED_JOBS = 4`. Half
the logical cores is the performance-core count on the Mac this was measured on; an unthrottled
mGBA at `fps: 240` is CPU-bound enough that a box without spare cores would only divide the same
throughput, which is the 2026-08-09 result restated for small machines. The cap is there because 4
is what somebody actually ran: a 32-core machine may claim more only once it has been measured
there.

Proved end to end with the default and no flag — three canonical verdict scenarios, 15s + 18s +
18s of scenario time, **18s wall**, all PASS, cached ROM, no build.

**This does not license re-running green scenes.** It makes the runs that must happen cheaper; it
does not make a run free, and "never run the full gate locally, never after a merge" still stands.
The other half of the gate's 24m51s is the five BUILDS, which is #309's problem, not this one's.
