---
id: 406
title: "A probe plays only the runs it names, and the leak guard lists every leak"
date: "2026-11-13"
section: "Combat System"
issues: [510]
---

# A probe plays only the runs it names, and the leak guard lists every leak

**Agreed with Nicolas on 2026-11-13** after the suite passes slowed #510 down: a probe of one run
should cost minutes, not a suite. Neither change touches how the bot plays.

**`montecarlo.py suite --only <start>[/<seed>],...`** plays just the named runs of the frozen
suite and judges nothing: no regressions, no SC-003, no snapshots, no promotion. A bare start
id means its tuning seeds (and its held-out seeds with `--held-out`); a named seed is played
from whichever set holds it. A held-out run is said only as whether it came back with a game
result, never its outcome (FR-025). A spec that names no run is refused before anything
plays. `--only` with `--freeze` is refused: a freeze needs the whole suite judged. The full
suite still runs once per PR, at the end (ADR 0395 is unchanged).

**`PT_LEAKGUARD=1` logs every leak, then fails the run at its end.** It used to raise on the
first word a nested sandbox left changed, so leaks came to light one per run. Now each such
word is logged once (with how many times it leaked), put back as if a `keep16` had held it,
and the game plays on; at the attempt's end the record lists them all (`leaks`) and the
attempt is recorded `crashed`, its `why` saying what the game ended as. A leaking run is not
a trustworthy result, so it counts as a run without a game result, as the raise did. A leak
logged outside a bot run fails the scenario's `RESULT`.

Proof (2026-11-13, vanilla, suite start `scout-ch6`, seed 1001): with the guard on, the run
ends as frozen (lost on turn 2) in 12 s. With `Sight.keepFog` turned off as a control, the same
run reports 9 leaks, each the fog bit of one enemy's state word, and plays the same 11297
frames to the same end.
