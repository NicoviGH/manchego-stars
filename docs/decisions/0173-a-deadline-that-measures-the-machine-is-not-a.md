---
id: 173
title: "A deadline that measures the MACHINE is not a deadline"
date: "2026-09-02"
section: "Operational Gotchas (durable)"
issues: [345]
---

# A deadline that measures the MACHINE is not a deadline

A `SUITE=all` sweep tabled **eight chapters as FAIL**. Nothing had failed. `SUITE=all` puts nearly
every long scenario in the repo in one `canonical` block, so four multi-minute mGBA processes ran
concurrently against `-j8` ROM builds at roughly **15fps against a 240fps target** -- 16x slower
than solo. Every deadline in `matrix.yaml` was WALL-CLOCK, so scenarios that pass alone in 25-70s
blew 300-600s walls, and the tier meant to be the pre-playtest safety net was the one that broke.
All eight passed under `--jobs 1`.

**The work is frame-bound, so the budget is frames.** `deadline` is now read as what it always
meant -- how much WORK a scenario may do -- in frames rather than seconds. Under contention a run
takes longer in wall time and its verdict does not change.

**The rate is FLOORED at the declared target, not fixed to it.** The emulator outruns its own
target: `titlecard` measures 877fps against a 240 target, so a flat `deadline * target` would have
been ~3.6x stingier than the wall deadline it replaces -- and `llm`, whose own comment says *"at
240fps a frame budget would be 4x too impatient"*, would have started failing. The budget therefore
uses the best rate the run has actually achieved, floored at the declared one: that reproduces the
old allowance on an idle machine, while contention can only make the budget LARGER. **The bad
direction is the one that cannot happen.** It is sized on the DECLARED rate too, never on a `PT_FPS`
override -- watching a run at 60fps must not quarter its work allowance.

**A frame budget alone would hang forever**, because a wedged emulator emits no frames and so never
reaches any budget. Two kill paths, and both name a real fault rather than a busy laptop:
**OVERRUN** (more frames than budgeted -- genuinely not finishing) and **STALL** (the frame counter
stopped -- mGBA is wedged). `PT_MAX_WALL_S` stays as a last-resort net for neither.

**STALL is the one piece that is still a wall clock, and the first cut set it wrong.** Progress is
read from stamped log lines, but the harness goes deliberately silent inside long waits -- the
largest is 9000 frames, which at the ~15fps contention floor is **600 SECONDS**. A 180s default
would have killed healthy contended runs as "wedged", recreating the exact bug this entry is about,
one layer down. The default is 1800s, and a test pins it against the largest `waitFor` in
`harness.lua` so the two cannot drift apart.

Every run now prints `throughput: N frames in Ns = Nfps (target Nfps)`. The harness already stamped
every line with its frame, so measured fps was free the whole time; printing it is what makes a
contended run legible instead of a mystery. **The fix and the diagnosis are the same number.**

Two bugs found while proving it, both worth naming. **`set -euo pipefail` turns an empty `grep`
into a dead script:** before the first stamped line exists the frame scan found nothing, grep exited
1, and run.sh died silently right after its "running" banner -- while the scenario itself went on to
PASS in its own log. And **bash reads a leading-zero number as OCTAL in `$(( ))`**: the stamps are
zero-padded, so frame 3425 evaluated as 3425 octal = 1813 and the throughput line under-reported by
a third. `10#` forces base ten. A number that is confidently wrong is worse than no number, which is
the whole point of the feature.

**ch01 is the only hosted chapter whose opening runs a MENU, and that is what a debug boot has
to strip (2026-09-02, #353)**
Every hosted chapter but ch01 had a fast boot; confirming #347 by eye therefore cost a canonical
build plus a full prologue playthrough (~24,000 frames) to look at a map ch03 would have shown in
twenty seconds. The boot itself was the easy half -- `_configure_boot(CH01_HOST_INDEX)`, the same
call ch03/ch04/ch05 make.

**Two things made ch01 different, and only one was predictable.** ch01 needs **no armed seed
table**: it is the chapter that FOUNDS the party, so its own opening LOADs the company at the
Northlook and runs PREP, where ch03/ch04/ch05 boot into a party that must be conjured from nothing
(`CH03_BOOT_SEED_SYMBOL` and friends). The unpredictable half was **lord select (#42)**. The first
cut kept ch01's opening intact and the run died with `fail:nil ... never reached the map` on an
8-item `generic_menu` -- the lord-select menu, which no other boot has ever met because no other
chapter opens with one. **A debug boot is a MAP load-test: it must strip every screen between New
Game and the map, and a MENU is such a screen even though it is not a cutscene.** The boot branch
drops the Northlook beats, lord select and Preparations, and LOMAs straight to the trail.

Measured: New Game -> `player_map_idle` on chapter 2, player faction, turn 1, at **frame 2,856**
against ~24,000 for the honest route. `PT_HOST_CHAPTER=2 tools/playtest/run.sh mapshot` PASSes;
going through `matrix.py` instead does not, because `mapshot` is chapter-generic
(`host_chapter: null`) and resolves to host 1 while the ROM boots chapter 2 -- the run then waits
for a map that never matches and reports `boot-timeout`. That is scenario wiring, not a boot fault,
and it is why the invocation is documented rather than left to be rediscovered.

Also from this change: **a rom_config env var the Makefile does not translate builds CANONICAL**,
so the scenario's verdict is about a different ROM than the one it names -- silence in both
directions. `check_rom_configs_reach_the_build` now pins every `rom_configs` var to a `$(VAR)` arm
in the Makefile.
