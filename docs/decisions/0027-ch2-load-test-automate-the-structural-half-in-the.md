---
id: 27
title: "Ch2 load-test: automate the STRUCTURAL half in the harness; the PACING half stays human."
date: "2026-06-25"
section: "Working Conventions (Definition of Done)"
issues: []
---

# Ch2 load-test: automate the STRUCTURAL half in the harness; the PACING half stays human.

The only open #22 item was the in-emulator load-test. It splits in two: *structural* (does ch02
LOAD off the real `MNC2(0x3)` chain, not soft-lock, and is it winnable — chwinga load green, the
archer present, surviving chwinga deliver charms) and *pacing* (judging the 5 cutscenes in motion).
The structural half is now machine-verified by the playtest harness; the pacing half is left a
human-at-mGBA pass. **Reached via the REAL chain, not a ch02 sandbox** — a `TESTCH=2`-style boot
would skip the `MNC2(0x3)` transition the load-test most needs to prove, so `reachCh02Map` clears
ch00 + ch01 with the clear-bot and observes the ending→opening→prep chain onto the ch02 map through
the state-driven controller. That
deep chain is paid **once** into a `ch02start` save-state checkpoint (`ckpt_ch02start`, like
`rbgch01`); `ch02` (entry assertions), `smoke_ch02` (soft-lock net), and `clear_ch02` load it. The
3 green chwinga are kept alive during `clear_ch02` (direct HP/def poke) so the charm-gift path
(`CHECK_ALIVE → GIVEITEMTO`) runs deterministically — whether they survive under real play is a
balance question for the human pass, not the wiring test. Charm delivery is verified by scanning
all blue inventories + the convoy (`gConvoyItemArray`) for the three charm ids; the pure membership
core is unit-tested in `test_ch02check.lua`. `clearDrive` was split into a non-terminating
`clearUntilAdvance` (the loop) + a verdict wrapper so the chain helper can keep driving past a win.
_Decided: 2026-06-25 (CLAUDE; brainstormed-then-TDD; assert depth "Core + charm delivery" — Nicolas)_

---
