---
id: 230
title: "A green recruit's TILE is load-bearing, and getting it wrong has no symptom (#25)."
date: "2026-08-08"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A green recruit's TILE is load-bearing, and getting it wrong has no symptom (#25).

ch05's Basil is LOADed GREEN and CUSA'd blue by the opening's own join beat. The obvious tile for
her is the one her vanilla twin stands on — this chapter lifts *everything* 1:1 from FE8 Ch5, so
that is the habit — but Natasha is **BLUE** in `UnitDef_Event_Ch5Ally`, meaning her tile is now one
of our **nine PREP deploy slots**. A green body parked there silently costs the player a
deployment on a map whose difficulty is priced for the full cap, and nothing anywhere reports it.
Two more failures in the same family: an impassable tile makes the recruit untalkable, and a tile
walled off from the unit she must reach kills the set-piece with no symptom but a player who never
manages the Talk. `assert_green_recruit_placement` gates all three at injection time (deploy-slot
collision, passability, and a flood-fill to the target — the same fill
`assert_scripted_move_reachable` runs). Basil sits at **(5,15)**, the row-15 corridor at the
pocket's mouth, clear of all nine slots and of the four stairs.
_Decided: 2026-08-08 (#25, the ch05 recruit wiring)._
