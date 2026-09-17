---
id: 93
title: "A verdict scenario needs no pixels, so it runs HEADLESS"
date: "2026-08-22"
section: "Distribution & Scope"
issues: [302, 308]
---

# A verdict scenario needs no pixels, so it runs HEADLESS

**The measurement that reordered the epic.** #302 began by counting `CH0N_*` constants (37 -> 48 ->
78 across ch03/ch04/ch05) and concluded the injector was the problem. Then we counted where ch05's
**102 first-parent commits** actually went: **50 of them (49%) touched only `docs/` or
`HANDOFF.md`**. By lines added, injector + tests + playtest scaffolding was 69%, against 3.4% for
the chapter YAML. Only 4 commits were rework -- ch05 was not bug-plagued, it was SLOW.

The cadence is visible in the log with no interpretation: `docs: point the next session at ch05's
scene 5` -> `Wire ch05's scene 5 (#280)` -> `docs: point the next session at ch05's scene 6` -> ...
Fifteen scenes, one per session, a handoff commit on each side.

The cause is upstream of all of it:

```
verification is a watched GUI run  ->  batch size = 1 scene per session
                                   ->  ~15 changeovers
                                   ->  50 handoff commits (49% of ch05)
```

Theory of Constraints: every system has one constraint, and optimising a non-constraint adds
nothing to throughput. **The constraint is verification cost measured in Nicolas's attention.**
`inject_ch05` was never the constraint; it was the visible thing.

**So: a `kind: verdict` scenario runs headless.** It asserts on MEMORY -- `INSPECT.units`,
`activeMsg()`, flags -- and needs no pixels at all. `kind: record` and `diagnostic` stay HEADED on
purpose: their output IS the picture, and eyes-on is how presentation defects get caught (#279's
letterbox bar and Sahnar's exit were both eyes-on finds). `matrix.yaml` already typed every
scenario with exactly that field, so the switch keys off data that already existed.

Measured on the ch03boot ROM: `ch03prep` 14s, `ch03chest` 14s, `ch03talk` 21s, `ch03midmap` 21s,
all PASS, no window. (The headed comparison for the same scenarios was deliberately NOT run --
re-running green scenes to obtain a number is exactly the cost this ADR exists to remove.)

**Three traps, each of which cost a step:**

1. **Nobody ships a macOS binary that has both headless AND Lua.** mGBA's own nightly DMG contains
   only `mGBA.app`, the Qt GUI frontend, whose `--help` has no headless option. pokeemerald-
   expansion vendors a prebuilt `tools/mgba/mgba-rom-test-mac` which advertises `--script` in its
   option parser and **has no Lua compiled in** -- their tests are C in the ROM, so they never
   needed it, and a three-line `hello.lua` fails to load with `Failed to load script`. Upstream
   `BUILD_HEADLESS` defaults to OFF. `tools/build_mgba_headless.sh` builds it; the script verifies
   Lua actually loads afterwards, because a Lua-less binary builds fine and still takes `--script`.

2. **`emu:screenshot()` segfaults headless, and `pcall` cannot catch it.** No video renderer is
   attached, so `mCore_screenshot` -> `PNGWritePixels` -> `KERN_INVALID_ADDRESS at 0x0`. That is a C
   segfault, not a Lua error, so `shot()`'s existing `pcall` wrapper is no protection whatsoever --
   the call has to not happen. `harness.lua` skips it on `PLAYTEST_HEADLESS=1` and logs the
   intent. A guard rejecting `shot()` inside verdict scenarios was drafted and **dropped as wrong**:
   the skip degrades gracefully, and `ch03prep` calls `shot()` three times and passes.

3. **The symbols must come from the ELF that built the ROM you are running.** `gen_symbols.py`
   hardcodes `fireemblem8u/fireemblem8.elf`, so pointing the harness at a `.matrix-romcache` ROM
   from a different build reads shifted addresses and hangs at `boot stuck` with procs that never
   change -- which looks exactly like an input failure and is not one. Input was verified
   independently: `emu:addKey`/`clearKey` round-trip correctly headless (START = 8) and IWRAM
   advances. Run the tree's ROM, or regenerate symbols against the ROM you mean to run.

4. **`emu:saveStateFile()` is broken headless, and it fails in the worst possible shape.**
   It returns `false` and writes an all-zeros file (measured: 397312 bytes of zeros), while
   `saveStateBuffer`/`loadStateBuffer` and `loadStateFile` on a valid file all work. Every
   `saveState()` call site in `harness.lua` DISCARDED that return, so a checkpoint builder run
   headless would have minted a dead state, PASSed on its own assertions, and had `run.sh` stamp
   its `.romhash` VALID -- after which the scenario that needs it fails forever, because the
   stamp looks fresh. Four scenarios sat on this (`ch02`, `ch02baxby`, `clear_ch02`, `smoke_ch02`,
   all on `ch02start`) with an empty `states/` dir. Two fixes, deliberately overlapping: the
   engine is chosen PER `run_mgba` INVOCATION and the checkpoint builder passes `headed` as a
   literal, and `saveState()` now raises `controllerFault` so a build that writes nothing reports
   FAIL. **The general rule: when a capability degrades under a new execution mode, check what
   IGNORES its return value, not just what calls it.**

5. **`headless` is DECLARED in `matrix.yaml`, not inferred from `kind`.** The first version derived
   it (`verdict` -> headless), which silently stripped the frames from `recordsupply` and
   `recordunitlist` -- both verdict scenarios BY WHAT THEY ASSERT, both feeding `make_gif.py`. And
   a missing binary must REFUSE, never fall back to headed: which engine ran is not in the verdict
   key, so a silent fallback serves a headed PASS for a headless run.

6. **A verdict glob on the bare word matched a FAIL, and that is how the stamp got written.**
   `run.sh` classified every verdict with `case "$VERDICT" in *PASS*)`, and `VERDICT` is the whole
   `RESULT: ...` LINE -- reason text included. The first guard message said "refusing to let a
   checkpoint build report PASS with no state written", so the FAIL it produced *matched the PASS
   arm*: run.sh stamped `prep.romhash` valid off a build that had written 397312 bytes of zeros.
   Four globs were fragile, and the last one is the EXIT CODE line, so a failure could have exited
   0. All four now match `*"RESULT: PASS"*`, and the guard message no longer contains the word.
   **This was found only by RUNNING the negative case** -- forcing a checkpoint builder headless
   and watching what it wrote. Reading the code proved the guard fired; it did not prove what the
   caller then did with that verdict. A failed build now also deletes its partial `.ss`, because a
   397KB file in `states/` reads as a real checkpoint to whoever looks next.

   Proof, both directions, on the canonical ROM (2026-08-23):

   ```
   builder forced headless:  engine: headless -> saveState prep -> false
                             RESULT: FAIL ... -> checkpoint build FAILED -- aborting
                             states/: no .romhash written, partial .ss removed
   normal (ch02, headless):  engine: headed (mGBA)      -> saveState ch02start -> true  -> PASS
                             engine: headless           -> ch02 PASS
   ```

   A real state is ~105-129KB at 99.4-99.5% non-zero; the broken one is exactly 397312 bytes of
   zeros. That size is the tell.

7. **Classify a verdict in ONE place.** The glob above was four copies, so when it was wrong it
   was wrong four times -- including on the exit-code line. It is now a single `verdict_passed()`
   helper. The instance was the bug; the duplication was the class.

8. **A failed rebuild must not delete a checkpoint it did not write.** Most builder failures never
   reach `saveState()` at all -- the builder gives up, the deadline expires, mGBA exits early -- so
   an unconditional cleanup would destroy the good state belonging to the PREVIOUS stamp whenever a
   rebuild was triggered by a stamp change alone (`PT_DIFFICULTY=difficult` and back). run.sh
   compares the state's mtime across the build and removes it only if THIS run wrote it. Proved
   both ways: a 5s builder deadline leaves the good state byte-identical, while a headless builder
   (which really does overwrite it with zeros before failing) removes it.

9. **The checkpoint abort has to evict the verdict cache too.** `exit 1` in the checkpoint block
   skipped the eviction at the foot of `run.sh`, so a direct `run.sh <scenario>` whose checkpoint
   build failed left a stored green that the next `make matrix` would serve without running
   anything -- while the same failure UNDER matrix.py did evict. Proved by planting a fake cache
   entry and watching the abort path remove it.

**Not a licence to re-run green scenes.** Headless removes the ATTENTION cost, not the time cost,
and "never run anything after a merge" still stands. What it buys is that a run no longer has to be
watched -- which is what makes batching scene work possible at all (#311).
