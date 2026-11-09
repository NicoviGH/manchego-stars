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
- each tuning run (`<start>/<seed>`): whether its invariant held, which units it answers for
  died (blue, or an escort green), how many stalls;
- the held-out losses, as hashed run names only, so reading the file does not tell whoever
  tunes the bot which held-out run lost (FR-025). The hash keeps honest people honest; it
  hides nothing from someone who hashes every start and seed on purpose;
- the AiDecideMain calls, CPU and wall time of each seed set.

A test (`test_the_shipped_manifest_loads`) fails when the manifest's tuning runs and the
baseline's differ, so a start added or a seed moved is a refreeze, never a silent gap.

**A regression** (FR-022, judged on the tuning runs) is any of:
- an invariant that held when frozen and fails now;
- a death of a unit the frozen run kept alive (blue, or an escort green), unless a replay
  witnessed why (`audit`'s primary label, from the store's `diag.jsonl`). A witnessed new
  death is said and does not block. A fresh run has a new trace, so a witness counts only
  through `suite --kept`, which judges the runs already played instead of playing them again;
- more stalls than the frozen run had. A stall always blocks: a replay witnesses a death, and
  nothing witnesses a stall, so "unexplained" is all a new stall can be;
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
`--held-out` the held-out seeds never play, and `replay` already refuses a held-out run. The
first freeze has no baseline to regress from, but an unlabelled fallback or a missing result
still refuses it: nothing a promotion would refuse is frozen as the reference.

**A refused candidate is frozen only on Nicolas's word** (2026-11-09): `suite --freeze
--override WHY` writes the baseline anyway and keeps WHY in the file as `override`, so the
refusal and who accepted it stay on the record. A regression or the cost can be his call to
accept; a run with no game result or a snapshot off its board never is, and `freeze_record`
refuses those whatever the override says. The tool never decides this on its own.

**A held-out failure becomes a fixture only after its seed is replaced** (AS 2): `load_suite`
refuses a start or snapshot whose provenance seed is still some start's held-out seed, whatever
its `set` label says, and one labelled `set: held_out` while `held_out_frozen_at` is unset.
`held_out_frozen_at` is the commit that last froze the held-out seeds: `1168f72d`, PR-A (#558),
which set 2001 and 2002; no tuning run has played them since. The seed check is the guard that
does the work; the field is the record of when the seeds were frozen, and a commit that replaces
any start's held-out seeds sets it to itself (`git log -1` of that change), so a fixture from the
old seeds is admitted only once the replacement is on record.

**The snapshots** (FR-021, T084) are the states ADR 0392's replays pinned at a failing
decision, each with the board that decision read kept beside it (`.json`, written by the pin
since PR-G). The manifest pins both files by hash (`state_sha1`, `board_sha1`), so a later replay that
writes over either is caught before the suite plays. Their invariant, `pinned_board`, is
checked from outside the run, all at once, one emulator each: `PT_PINNED`
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
- `suite --freeze --kept` (15 s with the snapshot checks one after another, 6.3 s with them
  at once, after the review): each snapshot loaded in a fresh emulator to its board, and the
  baseline was written. After the review the baseline was refrozen from the same kept runs,
  so its death lists leave out the non-escort greens; the only change is ours-ch02's two green
  deaths (0xC9, 0xCA). `suite --held-out --kept` against it: no regressions, SC-003 +0.0%,
  no new held-out loss, **PROMOTED**.
- **Refrozen on an override, 2026-11-09 (#510, T100b and the replan's rest of the plan in
  hand; instrument `4385f97ef0f3+v2`).** `suite --held-out` refused: vanilla-ch5/1001 Lute
  (0x0C) dies, a fog death the bot read at 0.0% (`unrevealed_killer`; Eirika now lives there);
  vanilla-ch5/1002 Natasha (0x0D) dies, honest risk the frozen bot survived on a 93% roll
  (ADR 0384's over-cap order puts game over first); SC-003 2,487,135 calls against 681,154,
  all T100b's counter branches, a cost Nicolas accepts because the suite is rarely re-run.
  Held-out: 4 of 28 lost, none new. Tuning: 3 of 28 lost and 13 protected deaths, both as
  frozen. Nicolas: "refreeze anyway"; written with `suite --freeze --kept --override`. The
  new SC-003 baseline is 2,487,135 calls.
