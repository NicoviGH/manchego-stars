---
id: 272
title: "A reach number measured on an EMPTY MAP is a claim about terrain, not about the chapter"
date: "2026-09-04"
section: "Operational Gotchas (durable)"
issues: [26]
---

# A reach number measured on an EMPTY MAP is a claim about terrain, not about the chapter

ch06's `reached_on:` block — *"foot reaches either door on turn 6, exactly as vanilla's does"* — is
the number its entire rescue clock is tuned against. Nothing read it, nothing checked it, and it
was measured by a Dijkstra (`map_placement_preview.foot_reach`) that did not know units exist.

In FE a unit cannot move through an enemy body. Walking the same map with the line standing on it:

| | foot | cavalry | flier | braulo | trex |
|---|---|---|---|---|---|
| **east door**, empty map | 6 | 5 | 3 | 5 | 5 |
| **east door**, contested | **--** | **--** | 3 | 6 | **--** |
| **west door**, empty map | 6 | 5 | 3 | 5 | 5 |
| **west door**, contested | **11** | 8 | 3 | 6 | 9 |

**Only the flier and Braulo can honour any clock.** Foot, cavalry and Trex cannot reach the east
boat at all while the line stands, and reach the west one on turn 11 against a turn-8 fuse.

**The channels are narrow enough that ONE body corks a route.** Removing `shark-rider-halberd` at
(15,16) alone turns the east door from unreachable into turn 12; removing `merfolk-trident` at
(2,14) takes the west door from turn 11 back to the declared 6. That is not a placement anyone
would have predicted by eye, and it is why this is derived rather than reasoned about.

`reached_on_contested:` now carries it, derived and pinned by a test, beside the empty-map row that
is kept because it is what the clock was designed against — the two disagreeing IS the finding.

**Stated limit.** The contested walk is a turn-1 SNAPSHOT: strikers step into the route on later
phases, and the player kills bodies out of it. So it is a floor, a tighter one than the empty map,
not the truth. What it cannot model is the cost of fighting, which depends on play — that stays a
human playtest question, and a scenario that pretended to answer it would be measuring its own
bot.

**The vanilla parallel, and where it breaks.** Vanilla Ch6 also has classes that simply cannot make
the rescue — MOUNTAIN is `--` for Cavalier and Armour, which is the guide's "send Seth"
(*"Vanilla Ch6's urgency is TRAVEL TIME"*). So a rescue only some of the party can attempt is
faithful. The difference is legibility: vanilla's restriction is TERRAIN, which the player reads
off the map before committing, and ours is ENEMY BODIES, which are dynamic, invisible as a
constraint, and dissolve as you kill them.
