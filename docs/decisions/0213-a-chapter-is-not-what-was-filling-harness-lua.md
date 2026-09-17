---
id: 213
title: "A CHAPTER is not what was filling harness.lua"
date: "2026-08-24"
section: "Operational Gotchas (durable)"
issues: [327]
---

# A CHAPTER is not what was filling harness.lua

#314 recorded that a chapter costs ~6–7 top-level local slots and concluded the harness would run
out during ch06. The deadline was right; **the cause was not.** Of the 83 locals added between the
end of June and 2026-08-24:

| | |
|---|---|
| chapter/cast-scoped | **10** |
| infrastructure | **73** |

The controller contract, headless runs, the verdict cache, guarded input — each capability brought
its own helpers. So the per-chapter chunk discipline that #314 shipped addresses about **12%** of
the flow. It was worth doing on its own merits (it deletes real duplication) and it is not the fix
for the ceiling.

**Adding a scenario is free.** `scenarios.foo = function()` is a table field. The 7,726 lines of
scenario bodies are 84% of the file and cost **zero** slots, so splitting them out — the obvious
move, and the one a fresh reader reaches for — buys nothing at all. The mass and the constraint
are in different places.

**So the count is RATCHETED rather than the file refactored.** `HARNESS_TOP_LEVEL_LOCALS` freezes
it at 198 and `check_harness_local_ratchet` fails in **both** directions: growth is the
regression, and a reduction that does not land in the constant loosens the ratchet to whatever the
file last happened to reach. Frozen, the next helper goes into a module — the pattern harness.lua
already uses for ten of them — and **module count has no ceiling**. That is what makes this scale.
Thinning the ≤5-reference tail (111 locals, ~253 call sites) only makes it comfortable, and is
deliberately a separate change: a mechanical sweep that size is the shape that shipped three bugs
in one day here, and freezing first is what makes attempting it safe.

The ratchet constant is a POLICY threshold, not a fact about the code, so it does not break "if a
number about our own code can be computed, compute it". The computed number is checked against it
on every run, which is precisely why it cannot drift.

**The tail thinning is DECIDED AND NOT BUILT.** #327's fourth item — moving the 111 locals
referenced ≤5 times into cohesive modules, taking `harness.lua` to ~87 with ~113 free — is not
happening, and the issue is closed rather than left open against it. The ratchet already removes the
failure: the ceiling is measured honestly in every chunk, the count cannot grow, and new
infrastructure goes into modules, which expand by adding files and so have no ceiling. Thinning
would buy **slack**, not safety, at the cost of a ~253-call-site mechanical sweep — the exact shape
that shipped three bugs in one day here and passed all 546 tests, where what caught them was an
output diff rather than the suite.

Two events would reopen it: the ratchet starting to **block real work** (someone needing a
top-level local in `harness.lua` and having no reasonable module to put it in), or the module split
scattering one decision across so many chunks that following the code costs more than the slack
saved. Neither is speculative to detect — the first shows up as a failing `check_harness_local_ratchet`
that nobody can satisfy cleanly.

_Recorded: 2026-08-24 (#327)._
