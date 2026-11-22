---
id: 456
title: "The fog read sums the strikes of the arrivals no one has seen"
date: "2026-11-23"
section: "Combat System"
issues: [713, 699, 510]
---

# The fog read sums the strikes of the arrivals no one has seen

**Decided (Nicolas, 2026-11-22, "Oh yeah I approve your recommendations": #713 fix 3, comment
7078468840; its input settled in 7082062860).** Extends ADR 0400 §3's fog read. The read stays a
tie-break where ADR 0400 places it: the sum is no new weight; only what the read takes in changes.

**The gap.** In vanilla Ch19 (`b640e-cs-s4003` attempt 1) every killer was an arrival of the
chapter's turn events, and 13 of the #699 measurement's 14 fog deaths were to enemies never seen
before they struck. The fog read priced one strike: the strongest kit **seen so far** this attempt,
stood at the fog's edge. A wave no one had seen yet read 0, and two hidden strikes that kill only
together read as the one that does not. The reinforcement claims (`difficulty.arrival_waves`)
cover Prologue to Ch8 and Ch13 only, so they could not be the input.

**The call.** A unit's fog read is the chance that these strikes **together** kill it
(`sight.odds` over their damage):
- the strongest seen kit's one strike, as ADR 0400 had it;
- one strike from **each arrival no one has seen** (`Bot.unseenArrivals`):
  - **Which arrivals.** Each red LOAD1-3 load of the chapter's turn events (`s.scriptedUnits`,
    ADR 0446), whose event runs by this turn's enemy phase. One already on the board is matched by
    character and the turn botrun stamped it (ADR 0449). It counts while it lives unseen: not
    sighted this attempt, and not remembered by a retry (those are the judged phase's, ADR 0399
    and 0455). An unmatched one counts only when it arrives in the coming enemy phase; one that
    should be on the board and is not was held by its event's guard, or is gone.
  - **As the game makes it.** Each is built once a chapter by the game's own event loader
    (`LoadUnit_800F704` on its quiet path: LoadUnit, the difficulty's bonus levels, the last REDA
    tile), one at a time on the board as it stands. This runs in one sandbox at the top level,
    whose load puts RAM and RNG back (`s.arrivalUnits`). For a strike, its struct is written into a
    free red slot by journaled writes (`Sight.standIn`), so the sandbox empties the slot again. The
    game's AI then decides from there, as the fog read's other strike does.
  - **Where it stands.** On its load tile when it arrives this enemy phase, since it acts the phase
    it comes. Otherwise, on the unseen tile nearest the unit that its moves since could reach:
    (turn − its event's turn) × its MOV from the load tile (`Bot.arrivalFrom`). Each stand-in
    takes its own tile.

**Estimates, said where they are made.**
- A stand-in's stats are one draw of the game's RNG (`GetAutoleveledStatIncrease`), not the draw
  it will make.
- The reach is Manhattan, with no terrain, so it over-reads.
- A single spawn (`LOADSINGLEUNIT`) has no definition and is not built; nor is a load that finds
  no free red slot, or one whose load tile another unit holds when it arrives (the loader would
  move it).

**The risk ADR 0400 records.** Priced inside the cap, fog froze the bot on Ch6. This read never
enters the cap; it breaks ties only.

**Proof.**
- Unit tests, each failing on the code before this change (run against it: 4 failures):
  `test_bot.lua` (two unseen arrivals kill together, one alone does not; a seen one is the seen
  kit's only; one too far is not asked; this phase's arrival strikes from its load tile; a later
  turn's brings none) and `test_sight.lua` (a load's definition and side, an arrival's event turn,
  `arrivalOf`/`standIn` round trip and the journal emptying the slot).
- One replay, `fix713i`, of vanilla Ch19 `b640e-cs-s4003` attempt 1, with `PT_LEAKGUARD=1`: no
  leaks; the loader ran 17 times, once per red load. Against main (`fix713g`) the game is the same
  through turn 2. From turn 3 the read prices the arrivals (the played plan's fog sum 0.69 against
  0.24), another plan wins, and the game is **lost on turn 7** (main: turn 12). The turn-4 death
  (Artur 0x13) was to unit 148, on the field from the start, not an arrival. The turn-7 loss is the
  escort Mansel (0xC8) to arrival 145: the fog read prices only our acting units, never a green,
  on main as here. One game: a lead, not a verdict. CPU 345 s against 432 s (another game).
