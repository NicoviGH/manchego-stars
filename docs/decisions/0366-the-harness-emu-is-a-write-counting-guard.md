---
id: 366
title: "The harness's `emu` is a write-counting guard, so a per-frame read memo cannot go stale"
date: "2026-10-23"
section: "Operational Gotchas (durable)"
issues: [531]
---

# The harness's `emu` is a write-counting guard, so a per-frame read memo cannot go stale

#531 (PR #533). `harness.lua` used to find a proc by scanning all 64 slots of `sProcArray`,
and a single controller observation asked about 30 times. That was roughly 2,000 emulator
reads per observation, with several observations per frame. `tools/playtest/procmemo.lua`
now reads the pool once and answers from a `{script -> addr}` map. On `clear_ch01`
(headless), the CPU time spent observing fell from 28.3 s to 2.8 s and the scenario from
40 s to 16 s. The run took the same frame count and wrote a byte-identical log.

**The decision is about when the map is still true.** The harness runs inside mGBA's frame
callback, and the GBA CPU does not execute during that callback. A key press, or a poke
that will start an event, therefore changes nothing in the pool until the next frame, and
the next frame is a new key. Inside one callback, only the harness itself can change the
pool: a write into it, or a state load, which replaces all of memory without the frame
moving. So the memo key is **(frame, harness write count)**.

The write count comes from a guard. `ProcMemo.install` replaces the global `emu` with a
proxy that forwards every call. Any call that is not a read (`read*`, `get*`,
`currentFrame`) bumps the count: `write*`, `addKey`/`clearKey`, `loadStateFile`, `reset`,
and any method mGBA adds later. Objects reached through `emu` (`emu.memory.<domain>`) are
guarded the same way, recursively. The hot reads (`ru8`/`ru16`/`ru32`) bind to the real
emulator through `PROCS.raw` and skip the guard, because a read cannot change the pool.

**Why a guard rather than explicit invalidation at the write sites.** There are over a
hundred `emu:write*` calls in harness.lua. With explicit invalidation, each of them, and
every new one, would have to remember to drop the memo. The one that forgets fails
silently: a proc map from before the write, read as a wrong verdict. With the guard, a new
write site is counted by construction, and the price of being conservative is a 64-read
rescan.

**The guard is the only path, and it fails loudly if it stops being one.** If anything
rebinds the global `emu` (a script, or an mGBA frontend), writes would bypass the count.
`refresh()` checks that the global is still the guard and raises an error rather than
answer.

**Proven on both frontends.** mgba-headless: the gate scenarios plus `clear` and
`clear_ch01`, 11/11 PASS (PR #533). Qt, headed: `ch06clock` with `PT_HEADED=1` PASSES, so
the Qt frontend leaves the guard in place.

Any future per-frame memo of emulator memory keys on the same `(frame, write count)` and
gets correctness from this guard; it should not build its own invalidation.
