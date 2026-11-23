---
id: 456
title: "The fog read sums the strikes of the arrivals no one has seen"
date: "2026-11-22"
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
  - **As the game makes it.** Each is built once an attempt by the game's own event loader
    (`LoadUnit_800F704` on its quiet path: LoadUnit, the difficulty's bonus levels, the last REDA
    tile), one at a time on the board as it stands. This runs in one sandbox at the top level,
    whose load puts RAM and RNG back (`s.arrivalUnits`). For a strike, its struct is written into a
    free red slot by journaled writes (`Sight.standIn`), so the sandbox empties the slot again. The
    game's AI then decides from there, as the fog read's other strike does. Botrun builds them at
    the first player phase of a fog chapter (`s.fogChapter`), before any plan's sandbox opens,
    whatever the fog hides then: a plan that moves a unit away hides tiles the phase start saw.
  - **Where it stands, and how likely.** A player knows the wave came, not where it went. On
    its load tile when it arrives this enemy phase, since it acts the phase it comes, for certain.
    Otherwise it may be on any unseen tile its moves since could reach, each alike: (turn − its
    event's turn) × its MOV from the load tile (`Bot.arrivalRegion`). It strikes from the one nearest
    the unit that no other stand-in takes, and its strike counts by the share of those tiles within
    its MOV + reach of the unit (`Bot.arrivalFrom`, `Bot.present`). The unit's own tile is not one
    of those tiles: no arrival stands there.
  - **Why the chance.** Counted in full, each arrival stood on the reachable tile nearest every
    unit. After two turns that is everywhere, so the read was high on every tile and steered
    nothing: in Ch19 Artur (0x13) read 0.66 to 0.88 on every tile a plan offered him (#713
    comment 7087475499). With the chance, his turn-4 tiles read 0.32 and 0.76 on (12,16) and 0.13
    on (15,13).
- **Two gaps of the read itself, fixed with it** (both before this ADR):
  - **The unit's own tile.** The seen kit's strike was stood on the tile the plan moves the unit to
    when the board left it empty (91 of 4,492 reads in Ch19). The edge is never the unit's tile.
  - **A green.** Every green's loss is paid as a player unit's, but only our acting units met the
    fog read; the escort Mansel (0xC8) died in fog unread. A green now meets it where the plan
    leaves it (a carried one meets none), summed into the plan's fog.

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
- Replays of vanilla Ch19 `b640e-cs-s4003` attempt 1 (one game; a lead, not a verdict), with
  `PT_LEAKGUARD=1`: no leaks; the loader ran 17 times, once per red load.
  - `fix713i`, full counts: the same as main (`fix713g`) through turn 2. From turn 3 the read
    prices the arrivals, another plan wins at the turn-3 replan, and the game is lost on turn 7
    (main: turn 12). Artur died on turn 4 on (12,16), the tile main's game also put him on. Main
    survived it on 6 HP; the dice differed (#713 comment 7087475499).
  - `fix713k`, with the chance and both gaps fixed: the read tells tiles apart (above), and the game
    is the same 21 decisions as `fix713i`. The plan that put Artur on (12,16) outranks the safer one
    on progress (1.53 against 0.53), and fog breaks ties only after progress (ADR 0400 §3). So this
    read changes a decision only between plans of equal progress and value.
