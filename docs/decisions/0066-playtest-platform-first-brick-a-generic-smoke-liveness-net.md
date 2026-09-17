---
id: 66
title: "Playtest platform first brick = a generic SMOKE LIVENESS net, not more hand-scripted scenarios (#49)."
date: "2026-06-19"
section: "Combat System"
issues: [49]
---

# Playtest platform first brick = a generic SMOKE LIVENESS net, not more hand-scripted scenarios (#49).

The #49 spine is `I/O harness → stability fuzzer → LLM-player`. The first brick is a generic driver that
boots any reachable chapter, **idles every player unit and just ends the turn each phase**, and asserts the
chapter reaches a clean terminal **with no crash/soft-lock/hang** — most chapters terminate in a *loss*
(idle party overwhelmed), which for a *stability* net is a fine clean terminal. The point is to exercise
load + every phase/event path to a clean end as content lands (#20–#28), catching the boot/soft-lock/text-
decoder-runaway class — not to win (winning is the next brick, a greedy clear-bot). **Two outcomes:** PASS
(exit 0) = no crash/soft-lock over the run, whether it reached a clean terminal OR just survived the turn
budget still cycling; FAIL (exit 1) = soft-lock (or a crash, caught by run.sh). An idle party usually *can't*
force a terminal (verified: both prologue and ch01 survive 30 idle turns), so budget-survival is the normal
healthy outcome and counts as PASS — an earlier INCONCLUSIVE+WARN bucket was dropped because a warning that
fires on every healthy run is noise. Completability ("can it be *won*") is the clear-bot's job, not this
net's. The stability verdict is a **pure function over
state snapshots** (`tools/playtest/liveness.lua`: `{frame,turn,faction,hpsum,procfp,chapter_advanced,
gameover}` series → `LIVE|TERMINAL_WIN|TERMINAL_LOSS|SOFTLOCK`) so it is **unit-tested without an emulator**
(`test_liveness.lua`, run by `make test`) — soft-lock = no change in `{turn,faction,hpsum,procfp}` for
`softlock_frames` while input is being fed; budget-exhaustion and a wedged emulator live outside the pure
verdict (driver → INCONCLUSIVE; run.sh wall-clock → ERROR). This makes `lua` a **dev dependency** (macOS:
`brew install lua`; `make test` skips the Lua tests with a notice when it's absent). The smoke **driver**
is just another scenario in `harness.lua` (`scenarios.smoke*`) reusing the primitives already in scope —
`harness.lua` is the I/O harness (primitives + scenario registry + per-frame coroutine runner) in one file,
so a scenario already shares everything: no `io_core` extraction, one file = single source of truth. Only
the pure verdict is a separate module (`liveness.lua`). Extracting an `io_core` for a future non-coroutine
consumer (the fuzzer's external driver / LLM-player) is deferred until one actually exists (YAGNI).
_Decided: 2026-06-19 (CLAUDE; pipeline track. liveness.lua + tests landed TDD; smoke driver scenario + run.sh wiring follow)_
