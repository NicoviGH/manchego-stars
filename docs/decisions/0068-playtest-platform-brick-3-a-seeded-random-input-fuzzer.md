---
id: 68
title: "Playtest platform brick 3 = a SEEDED random-input fuzzer (\"smart monkey\") over the same I/O layer (#49)."
date: "2026-06-19"
section: "Combat System"
issues: [49]
---

# Playtest platform brick 3 = a SEEDED random-input fuzzer ("smart monkey") over the same I/O layer (#49).

The directed smoke/clear bots only ever drive clean, scripted input orderings; the fuzzer injects *random*
inputs to surface the crashes/soft-locks those miss. Decisions:
- **Reproducibility is the contract** — a crash is worthless if it can't replay. So the fuzzer uses our **own**
  LCG PRNG (`fuzzrng.lua`, not host `math.random`, which differs between the CI `lua` and mGBA's embedded
  Lua), giving an identical input sequence for a given seed on any Lua ≥ 5.3. Seed comes from `PT_SEED`
  (default 1), is logged, and a FAIL prints `PT_SEED=N run.sh fuzz` to replay. The PRNG + weighted input
  policy are the **pure** core, unit-tested without an emulator (`test_fuzzrng.lua`, in `make test`).
- **Broad in-chapter surface + a B-mash unstick watchdog**, not a restricted key set (Nicolas deferred the
  call; this is what mature game-QA soak-bots do). All keys incl. START/SELECT (so menus get coverage),
  weighted toward the productive map keys. The watchdog handles the false-positive risk: liveness gets a
  second, shorter `nudge_frames` stall threshold → state `NUDGE` → the driver mashes **B** to back out of a
  benign menu. If even a full softlock-window of B can't escape, that **is** the bug (a screen with no exit).
- **Soft-lock = UNRESPONSIVENESS, not lack-of-progress.** Two false positives surfaced and were fixed in the
  *driver* (liveness.lua stayed pure): **(1)** a random Suspend drops to the title screen — a legit non-crash
  state where the progress key is frozen and B can't escape; the driver detects "not on a live map"
  (`liveOnMap` = a blue unit loaded and not on the title proc; deliberately *not* `inChapter`, which is false
  during a legit enemy phase) and treats leaving the map as a clean fuzz terminal instead of judging
  liveness or injecting recovery inputs into an unrelated screen.
  **(2)** the bot roams the cursor without ending a turn, so the smoke bot's progress key
  `{turn,faction,hpsum,procfp}` sits still on a *responsive* map; the fuzz driver instead feeds a
  **responsiveness fingerprint** (`fuzzFingerprint` folds the map cursor into the `procfp` field) so "no
  change" means the game stopped *responding*, not that the random bot hasn't progressed. Verdicts: clean
  terminal (win/loss) or surviving the frame budget = PASS; a genuine freeze = FAIL. Boot/title/prep fuzzing
  is a separate, noisier surface, deferred. Verified on a built ROM: 5 seeds clean (1 win, 4 budget-survival),
  no false positives. The remaining #49 spine after this is the LLM-player (swap the rule-based policy).
_Decided: 2026-06-19 (CLAUDE; pipeline track. fuzzrng + liveness NUDGE TDD; scenarios.fuzz + fuzz_ch01 verified across seeds on a built ROM)_
