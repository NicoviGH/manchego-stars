---
id: 304
title: "Injection steps declare what they write and need; the build holds them to it"
date: "2026-10-01"
section: "Operational Gotchas (durable)"
issues: [409]
---

# Injection steps declare what they write and need; the build holds them to it

`build_campaign.main()` ran ~60 statements whose order was load-bearing. Three mechanisms
recovered the facts from outside: `check.py`'s `INJECTION_ORDER` regexed main()'s text for
hand-pinned MUST-precede pairs, `check_cached_steps_are_config_invariant` regexed it for
boot-flag readers above the cached steps, and `build_scopes.scope_of_step` parsed a chapter out
of each function's name. All three are retired. `tools/inject/steps.py` holds the steps, in the
order they run, each declaring:

- **`writes`**: decomp globs. Every path the injection wrote must match the globs of a step
  that ran, or the build fails (`check_footprint`, on the walk `record_injected` already
  does). With `INJECT_STRICT=1`, which CI's build and the fingerprint gate set, each step's
  writes are checked as it runs, by a walk of the whole tree around it, naming the step.
- **`needs` / `provides`**: named facts, each with its why in `FACTS`. Every provider must be
  listed before every step that needs the fact, or the build fails before writing anything.
- **`flags`**: the boot flags a step reads. A step and its `when` get an args view holding
  `campaign` and those flags; reading any other flag raises.
- **`cached`**: every cached step must be listed before every step with flags (#309).
- **`scope`**: where the playtest matrix charges its writes (#255).

## Why validated, not sorted

The issue proposed a topological sort. File-level reads cannot carry the dependency:
`chapter_settings.json` is read by ch01 while slot 1 is still vanilla (the prologue
overwrites it after) and by ch04 after ch02 has hosted its slot. Those two reads want opposite
states. Named facts say which. A sort would also be free to reorder appends (message ids, SMS
ids), which moves the ROM. So the listed order is the execution order, and the declarations
validate it.

## Why the step cache keeps its coarse key

A key built from a step's declared inputs is only as sound as its read declarations, and
nothing observes reads. The ROM-input hash costs hit rate. A per-step key that under-declares
costs a stale ROM.

## Why strict is opt-in

The whole tree is ~19k files, two thirds of them build outputs. Walking it around each of the
~60 steps took a default injection from 53s to 69s on the Mac. The end-of-build check costs
nothing and catches any write no step declares. What only strict catches is a write declared
by a different step than the one that made it. CI and the refactor gate run strict, and an
ordinary build stays at 54s. Chapter steps are watched in every build, over the source roots,
because the playtest matrix needs their scopes.

## Gate

`injection_fingerprint` identical before and after on twelve configurations: the ten of
ADR 0300 plus `--ch05-lupin` and `--ch05-moose`. The first strict run failed three of them on
writes the declarations missed (the montage's assets, the test chapter's event files), each
named by step and path.
