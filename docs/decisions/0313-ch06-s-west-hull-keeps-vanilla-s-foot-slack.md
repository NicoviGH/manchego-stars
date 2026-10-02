---
id: 313
title: "ch06's west hull is 28 HP, because its fuse keeps vanilla Ch6's foot slack"
date: "2026-10-02"
section: "Combat System"
issues: [26, 430]
---

# ch06's west hull is 28 HP, because its fuse keeps vanilla Ch6's foot slack

ch06's boats declared that they sink on turns 7 and 8. Those numbers were copied from vanilla
Ch6's budget (ADR 0269), and nothing measured them. In vanilla, the Bael's first hit kills a
7 HP villager on turn 7, a flier or Seth arrives on turn 4, and foot arrives on turn 6. The
promise worth keeping is the slack: **foot reaches the door before the death.**

Measured with `danger_map` (ADR 0312, calibrated against #26's two runs):

- **East** keeps the promise on CLASS_FLEET's own 19 HP. Pinky arrives on turn 3, and Braulo
  on turn 6 with the hull afloat in 96% of runs. Its median sink turn is 10, not 7.
- **West** broke it. The ice-crab's venin claw poisons as well as cuts, and at 19 HP the hull
  sank before foot arrived in 43% of runs.

| west hull HP | 19 | 24 | 26 | 27 | **28** | 30 |
|---|---|---|---|---|---|---|
| median sink turn | 6 | 7 | 7 | 7 | **8** | 8 |
| sunk before foot arrives | 43% | 23% | 15% | 11% | **8%** | 5% |

**28 HP, through a `personal:` line on the west boat's pid.** CLASS_FLEET's 19 plus 9 gives
28. Foot gets there first in 92% of runs, and the median sink turn lands on the 8 the chapter
already declared. This is a parity repair, not a balance choice: vanilla's slack was the
target all along, and 19 HP could not deliver it once the poison counts.

**How it reaches the ROM.** A rescue hull is a raw-pid unit like a boss, so its line rides
`RAW_PID_PERSONAL_SOURCES`. The pid 0xbc row in `gCharacterData` has all-zero bases and base
level 1, so the line lands exactly. `inject.raw_pids.personal_bearers` and the #284 route
guard (`check_personal_line_injection_routes`) now read `rescue_boats` as well as the enemy
roster.

**A fuse is declared as its median.** `declared_fuse:` (east 10, west 8) is the field
`check_rescue_fuse_forecast` reads against the forecast band. `ch06.lua`'s `sinks_on` is held
to it by `check_chapter_lua_facts`, as the hull tiles and doors already were. The prose in
`difficulty_note` explains it and no longer states it.

**Found on the way.** #370 moved a merfolk from (13,11) to (13,13) to uncork the thrower's
javelin cells. That cork existed only in the old tool, which had reds blocking reds. Run 2,
with the body still at (13,11), saw the thrower throw on phase 2. Either tile gives the same
east clock, so the body stays, and its comment now says why it is there.
