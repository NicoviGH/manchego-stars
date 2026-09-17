---
id: 269
title: "Vanilla Ch6's urgency is TRAVEL TIME, not a fuse"
date: "2026-09-03"
section: "Operational Gotchas (durable)"
issues: [26]
---

# Vanilla Ch6's urgency is TRAVEL TIME, not a fuse

Measured off `Ch6Map` and `events_udefs.c` rather than remembered, because the design was being
tuned against a model of vanilla that turned out to be wrong in both halves:

- A `CLASS_CIVILIAN_F1` is **7 HP at Def 0**. The Bael's venin claw does 12. **Contact is death** —
  there is no grind, and no fuse to tune.
- **Not one Ch6 unit can hit a villager on turn 1.** The nearest static is an Armour four tiles
  away that never moves. The entire clock is one pursuing Bael walking 32 move points — **turn 7**.
  It targets the villagers rather than the party because they are 32 MP away and the party is 50.
- The villagers sit in a mountain-ringed pocket. Reading the engine's own cost tables, MOUNTAIN is
  `--` for Cavalier and Armour, 6 for Paladin, 4 for foot, 3 for the Bael, 1 for a flier. **Franz
  and Gilliam cannot reach them at all.** That table *is* the guide's "send Seth".
- So vanilla's budget is: **death turn 7, fast answer turn 4, foot turn 6** — slack of 3 and 1.

ch06 reproduces the *outcome*, not the mechanism. A boat is tougher than a child, so the clock is a
fuse rather than one bite; and our map cannot host vanilla's long walk, because vanilla's villagers
have a dead corner behind them and ours are already in the two far corners — searching every tile,
a turn-7 contact leaves the pursuer nearer the party than the boat, so it simply retargets. What
transfers is the budget: **our foot reaches either door on turn 6, exactly as vanilla's does, and
both hulls sink on turn 7 and 8.** Same slack, arrived at from the other direction.

The lesson that outlives ch06: a parity claim about a vanilla chapter's *feel* is a measurement,
not a memory. Both halves of this one had been asserted in a chapter YAML for weeks.
