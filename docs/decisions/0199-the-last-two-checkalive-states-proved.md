---
id: 199
title: "The last two `CHECK_ALIVE` states, proved"
date: "2026-08-21"
section: "Operational Gotchas (durable)"
issues: [25]
---

# The last two `CHECK_ALIVE` states, proved

The four states vanilla distinguishes are now all four run, not three run and one read. The two
that were owed were settled on the `ch05lupinboot` ROM by putting the wolf in each state at the map
and reading which message the Talk played:

| Roster state | Poked | Arm played | |
|---|---|---|---|
| recruited, alive, **BENCHED** | `US_NOT_DEPLOYED`, off the tile grid, `xPos = -1` | the wolf's | ✅ `ch05lupinbenched` |
| recruited, then **KILLED** | `US_DEAD` | the no-Lupin one | ✅ `ch05lupinkilled` |

**The benched run is the one that matters**, and it is why "test whether Lupin is on the ch05 field"
was recorded as *actively wrong* rather than merely inelegant: ch05 deploys 9 of a 10-unit pool, so
a field test passes every other gate in this chapter and then tells a player who WON the wolf that
he does not exist. The run says our build reads the roster, not the map — which is what
`eventscr.c:3212` says, now with a run behind it.

**Both rode the existing scenario rather than new ones.** `ch05recruit` is parameterised over the
wolf's roster state and the expected arm; the two states are four-line callers. That also keeps
`harness.lua` off the 200-local ceiling that, hit, stops the whole chunk loading — a margin
`check.py` MEASURES on every run rather than one anybody writes down, which is the rule this
sentence used to break by naming a number. `INSPECT.activeMsg` went on `INSPECT` for exactly that reason.

Not covered, and not pretended otherwise: the poke reproduces the STATE a benched unit is in, not
the route by which a player gets there. The real ch04 → ch05 chain remains the only thing that
exercises `ReadGameSave` filling the array.

_Recorded: 2026-08-21 (Nicolas: "Run them")._
