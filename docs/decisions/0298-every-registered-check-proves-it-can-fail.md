---
id: 298
title: "Every registered check proves it can FAIL, against the real tree with one input doctored"
date: "2026-09-30"
section: "Working Conventions (Definition of Done)"
issues: [407]
---

# Every registered check proves it can FAIL, against the real tree with one input doctored

A guard that passes by checking nothing looks exactly like a guard that passes because the
tree is clean. It is the most repeated bug in this repo: #405's camera-bounds check read a
key no layout carries and never found a map; #401's reachability walk skipped every `MS_*`
scene; `injection_fingerprint`'s first cut passed in 1.1 seconds by doing nothing (ADR
0287); ADR 0296 is the long form. ADR 0170 named the shape. Every instance was caught by a
reviewer, one at a time, because "watch it fail" was a habit and not a gate.

## The rule

Every entry in `check.CHECKS` has a **canary** in `tools/test_check_canaries.py`: the real
check, run against the real tree with ONE input doctored into a known-bad state, which must
report a named failure. `check_every_gate_has_a_canary` reads the registry by AST, so a new
check without a canary fails the build, on the lean CI job too.

## Doctored at the READ, not fed to a helper

The canary serves a changed text for one path through `open()` and leaves everything else
real. That is the point of it. Nearly every check here is a thin reader around a pure,
already-tested helper, and every vacuous pass on record was in the READER: the wrong key,
the wrong glob, the wrong file. A canary that handed the helper a bad string would have
passed #405. This one could not.

Where the input is not a file read, the canary doctors the narrowest seam that still leaves
the check's own logic running: `check_lua_chunks_load` gets a broken chunk through its path
global (Lua reads the file itself), `check_handoff_only_on_main` gets fake answers from its
`_git` probe so the branch-state logic runs, `check_verdict_scenarios_are_guarded` has its
allowlist emptied. `UNCANARIED` holds any check that cannot be canaried at all, with the
reason; it is empty, and every entry would be a claim a reviewer can challenge.

Each canary names the fault it planted (`expect`), and fails if the check reports something
else: a check that fires on the wrong thing has not proved it sees the right one. Advisory
checks that only print (`check_lane_ownership`, `check_rescue_fuse_forecast`) are held to
their printed output.

## What building it found

All 48 checks fired on the first real run; four canaries needed fixing, and the one that
stayed silent (`check_wrap_widths_are_pixels`) was the canary's own mistake: it planted a
positional `29` in a function whose width is its sixth parameter, so the value bound to
`slot`. That is the check working. It binds arguments by signature, not by position, which
is why it exists.

Three harness details a later canary will meet:

- `inject.source` memoises by file mtime, and a doctored read changes no mtime, so
  `doctored()` clears those caches on entry and exit.
- **`doctored()` asserts on EXIT that every target was read and actually changed**, never
  inside `open()`. The first version raised from `open()` when an anchor had moved, and
  several checks swallow a read error (`_chapters()` skips a file it cannot parse), so the
  error came back as "the check stayed silent" -- blaming a working check for a stale canary
  (review of #414).
- "Was read" is the other half of the proof: a canary also fails when the check never opens
  the file it doctored, which is a check that stopped reading its own input.
