---
id: 318
title: "A zone-triggered wave arrives on the party's earliest entry into its zone"
date: "2026-10-02"
section: "Combat System"
issues: [430]
---

# A zone-triggered wave arrives on the party's earliest entry into its zone

#430 step 3. Some twins hold a wave back until the party walks into a zone. An `AREA` entry
fires when a player unit ends its move inside its box (`EvCheck0B_AREA`, bounds inclusive).
Its script either loads the wave itself, which then acts that enemy phase, or clears the temp
flag that a gated `TURN` event waits on, which then loads the wave on the next player phase.
A flagged `TURN` event fires only while its flag is clear. The twins set the flag in the
opening scene, so the wave stays dormant until the zone clears it.

**The arrival turn is the party's earliest entry, walking at full pace.**
`difficulty._zone_entry_turn` walks each unit of the twin's `playerUnitsInNormal` table turn by
turn from its deploy tile, at its class's Mov and cost table, on the twin's own terrain. It
walks only the named unit when the script guards on one (`EventScr_UnTriggerIfNotUnit`). The
map is empty: no enemy body blocks, so this is the earliest the wave can come, a floor like
every other `foot_reach` reading.

- **FE8 Ch1:** the wave waits on `EVFLAG_TMP(11)`, which only Eirika clears, in (0,0)-(7,9).
  From (12,9) at Mov 5 she gets no further west than x=8 on turn 1. She can enter on turn 2,
  so the wave loads on turn 3.
- **FE8 Ch4:** the Revenants wait on flag 8, which any blue unit clears in (0,9)-(14,14). They
  load on turn 3.

**What it replaced.** ADR 0051 modelled every zone wave as a flat turn 2, `_ZONE_ENTRY_TURN`,
because the parity split only asked whether a unit arrives on turn 1. The timeline (ADR 0317)
then read that placeholder as vanilla's real turn. That is how ch01's `spawn_turn: 3` came to
read as a turn late. It is vanilla's turn, and ch01's wave and first contact now track the
twin's.

**A flag holds a wave back only when the opening scene sets it.** Otherwise the flag just marks
the event fired, as in Ch3, and the event runs on its own turns: ch13a's ending scene now reads
as its turn 12, not a turn-2 wave. `0x0` is no flag at all. A dormant wave never loads before
its own `TURN` start turn. A wave whose trigger the walk cannot place keeps the old reading,
`_UNPLACED_TURN` (2): a zone nobody in the deploy table can set off, a flag an `AFEV` or `CHAR`
script clears, or an `AFEV` script that loads it. It is late by an unknown amount, but it is
never on the opening board.

The twin's layout, terrain and deploy table moved from `timeline.py` into `difficulty.py`, so
the arrival turn and the timeline read one source.
