---
id: 205
title: "A unit's LOAD tile is not its POST, and the difference cost us the arena"
date: "2026-08-14"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A unit's LOAD tile is not its POST, and the difference cost us the arena

Vanilla Ch5 `LOAD1`s Joshua on **(12,6)** and, as the very next command, walks him off it:
`MOVE(0x0, CHARACTER_JOSHUA, 9, 7)`. ch05 lifted the load tile and dropped the MOVE, on the
reasoning that our Sahnar simply fights where she lands.

That is a bug wearing a decision's clothes. **(12,6) is `TERRAIN_ARENA_REGULAR` and the arena
tutorial's own trigger is `AREA(..., 12, 6, 12, 6)`** — a hostile parked there makes the arena
unenterable for the entire chapter and silently kills the `arena-wager` debut (#264/#265, still
`status: active`). The chapter YAML said *"which is the ARENA tile (12,6)"* two lines from the
placement the whole time.

So the walk-off is chapter data, not flourish: **`walks_to: [9, 7]`** (vanilla's tile —
`TERRAIN_ROAD`, no defensive bonus, clear of the arena mouth), and `ch05_sahnar_station` refuses
to build without it. The escort distance `assert_green_recruit_placement` measures is to the
POST, because that is where the Talk happens.

**Generalise it:** when a retile lifts a vanilla unit's coordinates, lift what the event script
does to that unit NEXT. A tile that a vanilla unit leaves immediately is usually a tile something
else needs. `ch05arena` is the witness — it asserts the tile is empty, and it was failing its
first check on every run.
