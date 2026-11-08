---
id: 395
title: "The instrument is frozen on a pinned suite with held-out seeds; promotion rules"
date: "2026-11-07"
section: "Combat System"
issues: [510]
---

# The instrument is frozen on a pinned suite with held-out seeds; promotion rules

#510 step 9 PR-G (T081-T087, US5). The difficulty instrument (a bot that plays the real ROM)
is now frozen. Every later change to it is judged against a record of what it did at the
freeze, and the held-out seeds stay unseen while the bot is tuned.

**The frozen baseline** is `tools/playtest/suite-frozen.json`, written by
`montecarlo.py suite --freeze` and committed. It keeps, under the instrument that played it
and the manifest version:
- each tuning run (`<start>/<seed>`): whether its invariant held, who died, how many stalls;
- the held-out losses, as hashed run names only, so reading the file does not tell whoever
  tunes the bot which held-out run lost (FR-025). The hash keeps honest people honest; it
  hides nothing from someone who hashes every start and seed on purpose;
- the AiDecideMain calls, CPU and wall time of each seed set.

A test (`test_the_shipped_manifest_loads`) fails when the manifest's tuning runs and the
baseline's differ, so a start added or a seed moved is a refreeze, never a silent gap.

**A regression** (FR-022, judged on the tuning runs) is any of:
- an invariant that held when frozen and fails now;
- a death of a unit the frozen run kept alive, or more stalls than it had, unless a replay
  witnessed why (`audit`'s primary label, from the store's `diag.jsonl`). A witnessed new
  death is said and does not block. A fresh run has a new trace, so a witness counts only
  through `suite --kept`, which judges the runs already played instead of playing them again;
- SC-003: the AiDecideMain calls of the seed sets played more than 20% over the frozen calls
  of the same sets. The tuning seeds alone are judged against the tuning seeds' frozen
  count, never the whole suite's;
- a snapshot that no longer loads to its board (below).

An **unlabelled fallback** is a death over the cap of a unit the bot protects (blue, or an
escort green) on a turn no `fallback_sacrifice` anomaly names. A green the bot does not escort
is not its to keep alive: in the stores every over-cap blue death carries the label, and every
unlabelled over-cap death is a non-escort green (counted 2026-11-07).

**Promotion** (`suite --held-out`) needs every run back with a game result, no blocking
regression (each is deterministic: a seed plays the same every time), no unlabelled fallback
and no reproducible held-out loss. The held-out seeds are said only as counts, never as a
start or seed. A held-out loss the frozen baseline did not have is played once more; one that
loses again is reproducible, and one that does not is reported as non-determinism. Without
`--held-out` the held-out seeds never play, and `replay` already refuses a held-out run.

**A held-out failure becomes a fixture only after its seed is replaced** (AS 2): `load_suite`
refuses a start or snapshot whose provenance is a held-out run (`set: held_out`) while
`held_out_frozen_at` is unset or the seed is still some start's held-out seed.

**The snapshots** (FR-021, T084) are the states ADR 0392's replays pinned at a failing
decision, each with the board that decision read kept beside it (`.json`, written by the pin
since PR-G). Their invariant, `pinned_board`, is checked from outside the run: `PT_PINNED`
boots the start's own task, loads the state in that fresh emulator, prints one
`PINNED <json>` line with the board, and plays nothing. This is the fresh-emulator load ADR
0392 left to PR-G. A snapshot pins the fixture, not the bot's behaviour: a change that avoids
the death it came from is not a regression.

**The two items PR-F left** (ADR 0392):
- **A fog start is in the suite**: `scout-ch6`, vanilla Ch6 (chapter 7), the scout's state.
  The manifest is version 2, 14 starts, 56 runs (SC-001 amended from 52). The real `replay`
  command now reaches a fog map: the Eirika replay below ran through it.
- **A normal surprise replan still breaks a deep or full_info replay**, even where the original
  replanned at the same point. Unchanged: in the only case seen (Meesmickle, ours-ch03 seed
  1002, decision 45) the cut cost nothing, since the plan was the baseline's, and ADR 0392
  says to change it with the evidence of a case where it matters. There is still none. No bot
  change, so the instrument stays as frozen.

`suite --baseline` is retired (`DEAD_CONCEPTS`): `--held-out` and `--freeze` replace it.

**Built (2026-11-07, instrument `e6fc3854f2a3+v2`).**
- `suite --held-out --jobs 8`: 56 runs, every one with a game result, in **642.6 wall
  seconds** (SC-001's frozen wall time), 4,413.5 wall s and 3,086.6 CPU s of work.
  **567,629 AiDecideMain calls** (tuning 210,261; held-out 357,368), the re-frozen SC-003
  baseline (R-10), budget 681,154. The 52 runs that were in the suite before play exactly as
  before PR-G: 566,389 calls, the count at #571; the fog start adds 1,240. 4 of the 28
  held-out runs lost.
- The three T079 deaths replayed on the fresh runs, each answer as ADR 0392 recorded it:
  Klimt (ours-ch02 seed 1002, `deep` at decision 1) lived; Meesmickle (ours-ch03 seed 1002,
  `deep` at 45) broke at `4>wait@14,4>nil` on the same surprise replan; Eirika (scout-ch6 seed
  1001, `full_info` at 4) lived. Each pinned state reloaded to its board in the run.
- `suite --freeze --kept` (15 s): each snapshot loaded in a fresh emulator to its board, and
  the baseline was written. `suite --held-out --kept` against it: no regressions, SC-003 +0.0%,
  no new held-out loss, **PROMOTED**.
