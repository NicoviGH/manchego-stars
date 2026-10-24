---
id: 214
title: "A scenario is DECLARED by the chapter it tests"
date: "2026-08-24"
section: "Operational Gotchas (durable)"
issues: [314]
---

# A scenario is DECLARED by the chapter it tests

A chapter YAML declares what its scenarios PROVE; everything mechanical is derived. The ROM comes
from the chapter's `boot`, `PT_HOST_CHAPTER` from `inject/hosts.py`, the `matrix.yaml` row and the
chapter suite from `tools/playtest/declared.py`. A name declared in both a chapter YAML and
`matrix.yaml` **raises** — letting one copy win would recreate the hand-sync this replaced, with the
added twist that which body ran would depend on merge order.

**A case is EITHER declared or `lua:`, never both and never neither.** Both means two descriptions of
one scenario. Neither means a row that dispatches to the driver, finds no steps and **passes
vacuously** — a green scenario that asserts nothing is worse than a missing one, because it reports
coverage. The driver refuses an empty `then` for the same reason.

**Only the BODY opts out.** A `lua:` case still derives its row and its suite membership from the
chapter, so a chapter declares everything it owns. That is the DECORATE lesson kept intact: code is
the exception you NAME, not the default you copy.

**`lua:` names the function that runs, not a copy of the case's name** (2026-10-24, #531). A
chapter-generic probe (`INSPECT.redStats`, `scenarios.mapfull`) is bound to a chapter's ROM by
`lua: INSPECT.redStats`, never by a one-line `scenarios.ch04redstats` wrapper. Six such wrappers
existed only because the verdict cache keyed on the scenario's own function; it now keys on the
row's `entry` (`lua:`, else the name), and so do the #238 gate and the runner (`MX_ENTRY` ->
`PLAYTEST_ENTRY`). The runner searches `scenarios` and `INSPECT` only and calls what it finds with
no arguments, so a bound `INSPECT` probe takes none (a chosen scope: `INSPECT` is where generic
probes live). `check_playtest_matrix` refuses any other binding, from a chapter case or a
`matrix.yaml` row, and a leftover same-named scenario the binding would shadow. A wrapper survives
only where it passes an argument (none does since #538 archived the last one, `recordch05joinlupin`).

Four things paid for while building it:

**`kind` is declared and never inferred from the name, even though timing still globs on it.**
`matrix.yaml`'s classes match `record*`/`smoke*` to set fps and deadlines, and that is fine — timing
may be guessed from a name. What a scenario ASSERTS may not: `recordsupply` and `recordunitlist` are
verdict scenarios despite the prefix, and `kind` drives both the headless split and
`check_verdict_scenarios_are_guarded`.

**An assertion lives where its subject does, and getting this wrong cost two drafts.** The first
draft interleaved `then` with `when`, pairing each assertion to a step *by index* — so inserting a
step silently re-targets every assertion after it. The fix for that made assertions order-free and
whole-case, and **that was worse**: `ch05reliquaries` stopped asserting that each door hands over
*its own* gift and only checked that four ids arrived. Rotating the four gifts passed. That is
exactly the defect the scenario exists to catch — the gifts are per-tile on purpose, richest where
the eruption races — and it was caught in review, not by the suite.

So: an assertion about ONE STEP rides that step (`visit: {x, y, gains}`), and `then` holds only
assertions about the WHOLE case (`spoke`, `event_flag`). Not positional, and not detached from its
subject. **The general lesson is that weakening an assertion is invisible to every gate we have** —
the scenario still passes, the diff looks like a simplification, and the coverage is gone.

`declared.py subsumed` depends on this placement directly: it compares `when` and `then` as
independent multisets, which is sound *only* because a per-step assertion cannot be in `then`. Move
one back and A silently "covers" B while asserting nothing about what B pinned.

**A gift assertion counts copies; it does not check presence.** A presence check passes on a
reliquary that hands over nothing whenever anyone in the party already happens to be carrying one —
exactly the blind spot `ch04village` was written to close (#205).

**A `visit` step's tile is checked against the chapter's own `villages:` block.** The coordinates
were a third copy: the chapter YAML declares `reliquary-south tile=[12,19]`, the Lua had `12, 19`,
and `matrix.yaml` had the row. `check_declared_cases` proves a case only visits tiles the chapter
declares a village at. Resolving the tile FROM the village id is the obvious next step and was not
taken here: item ids resolve through `build_campaign.py`, which imports Pillow, and CI's lightweight
`checks` job cannot import it. That wants an item-id registry that does not drag the art pipeline.

**A raid names its sites by village id** (2026-10-24, #531). `ch02raid` and `ch05raid` became
declared cases: `when: idle: {phases, hold, until: raided}` gives the enemy phases back, and
`then: raided: [village id, ...]` asserts one of those sites fell (terrain RUINS, its gift absent,
its event id unset). The id resolves at RUN time, through `CAMPAIGN.VILLAGES` (gen_symbols: the
chapter's tile, the injector's `CHnn_VILLAGE_FLAGS`, the gift through `ITEM_ENUM`), so the case
copies no tile, flag or gift and CI's `checks` job still imports nothing heavy. `declared.py`
refuses an id the chapter does not declare and a `raided` with no `idle` to pass a turn.
`ch05.lua`'s reliquaries read the same table. A site is watched from right after `given`, and
one that is not a village then FAILs as that, not as "nothing fell".

**How the port was gated**, and both gates were required. First, free: all **111 scenario rows
resolved byte-identical** before and after, so the derivation reproduces the hand-written table
rather than merely resembling it. Second, real: the three ported scenarios ran in mGBA and **every
guarded input was identical** — 26, 92 and 155 actions, same input, result, state and cursor tile,
in the same order. A matching PASS would not have been evidence; a matching input sequence is.

_Recorded: 2026-08-24 (#314)._
