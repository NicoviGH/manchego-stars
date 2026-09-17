---
id: 195
title: "The alive arm needed a LEVER, and the boot seed was a second reason it had none"
date: "2026-08-14"
section: "Operational Gotchas (durable)"
issues: [25]
---

# The alive arm needed a LEVER, and the boot seed was a second reason it had none

`--ch05-lupin` (with `--ch05-boot`) `LOAD1`s a one-unit table holding Lupin **before** the opening
runs, which is what makes scene 4's ALIVE arm reachable from a cold boot at all. Nicolas asked for
both paths on film; only one of them could be made.

**There were two independent reasons, either fatal on its own** — the second only surfaced when the
first was being fixed, which is why it is written down:
  1. the branch runs before `LOMA` while the boot party seed is `LOAD1`ed after it, so
     `gUnitArrayBlue` is empty when `CHECK_ALIVE` asks (the ADR above);
  2. **Lupin is not in that seed.** It zips the cast against 9 deploy slots and he is last, so he
     falls off the end. Even hoisting the seed above the branch would still have played the
     no-Lupin arm — and would have looked like the fix working.

Loading pre-`LOMA` is safe, and that was checked rather than assumed: `RestartBattleMap`
(`bmio.c:1043`) rebuilds map, BGs, sprites and traps and **never touches the unit arrays**, so the
unit survives as a roster entry, which is all `CHECK_ALIVE` reads.

**What the two films do and do not prove.** Measured: they agree through scenes 1-3 (bar 2-4 frame
emulator timing jitter) and diverge from scene 4's FIRST BOX to the end — the tail is not four
scenes of difference, it is the two box 1s being different lengths and time-shifting everything
after, so no frame lines up again. "They differ only in box 1" is therefore **not testable by frame
equality**, and the harness comment no longer claims it is. Compare by eye.

Against #25's four states this settles **two**: *never recruited* (the plain boot film) and
*recruited, alive, on the roster* (the proof ROM). **Benched** and **recruited-then-killed** are
still only a decomp reading — `CHECK_ALIVE` ignores `US_NOT_DEPLOYED` and treats `US_DEAD` as
absent — and a reading is not a run.
