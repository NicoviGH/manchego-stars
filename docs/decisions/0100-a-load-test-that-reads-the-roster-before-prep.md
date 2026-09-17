---
id: 100
title: "A load-test that reads the roster before PREP settles is a diagnostic that LIES"
date: "2026-09-04"
section: "Distribution & Scope"
issues: [26]
---

# A load-test that reads the roster before PREP settles is a diagnostic that LIES

`mapshot` is the chapter-generic load test every new host runs, and `docs/adding-a-chapter.md`
tells you in bold to **verify placement from `INSPECT.units`, never from a screenshot** -- because
FE8 draws a map sprite offset upward, so a unit reads a row high. That instruction is right. What
was wrong is that the dump could be read too early.

`INSPECT.units` walks `gUnitArrayBlue` directly. `bootToMap` returns on `player_map_idle`, which
can be true while the chapter's beginning script is still running -- and on a chapter whose
opening is a bare `LOMA` / `LOAD1` / `CALL(prep)` spine there is almost nothing between the Fight
press and that state. ch06 dumped **2 blue of a cap of 10**, while its own screenshots 120 frames
later showed the lord standing on the map with full HP.

**Every chapter before ch06 hid this**, and hid it in the way that makes a latent bug expensive:
ch05's opening plays four backdrop scenes, a join and a monologue AFTER prep, so its dump lands
~15,000 frames in, long settled. The bug was therefore invisible on exactly the chapters that had
scenes, and would have fired on exactly the chapters that do not -- new hosts, which is what this
scenario is FOR. ch07 and ch08 would have inherited it.

Cost when it bit: a full A/B against ch05 to decide whether ch06 or the harness was at fault, and
a confident, wrong report that ch06 shipped a broken deploy. The screenshot is what disproved the
dump -- which inverts the runbook's advice in the one case the runbook does not cover, and is why
the fix is to make the dump trustworthy rather than to soften the advice.

`mapshot` now waits on the same predicate `mapfull` already waited on (player phase, no menu, no
std/battle event engine) before reading. **The general rule: a probe that reads engine state must
wait for the state to settle, and "the controller handed back input" is not that.** A diagnostic
that reports a partial truth is worse than one that fails, because it gets believed.

_Decided: 2026-09-04 (Claude, hosting ch06)._
