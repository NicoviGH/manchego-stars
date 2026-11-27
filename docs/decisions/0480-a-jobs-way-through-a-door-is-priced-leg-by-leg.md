---
id: 480
title: "A job's way through a door is priced leg by leg"
date: "2026-11-26"
section: "Combat System"
issues: [688, 711, 764, 766, 510]
---

# A job's way through a door is priced leg by leg

**Decided (#764's "After R4" item 4, the route-loss lead on #688, 2026-11-26).** A job's
expected loss (`routeLoss`, ADR 0473's price) walks the way the job's turns count. When that way
goes through doors or walls, the loss is read leg by leg along it.

**Why.** `routeLoss` walked the goal's own field from the unit's tile. A goal behind a shut door
has a field only inside its room, so the unit's tile was off it, and the loss read 0: a chest
behind a door was safe from anywhere. Vanilla Ch21 s4009 a1 on main (`c688m`): every unit's job
to the (2,18) chest, behind the (4,18) door, read loss 0 on all 30 turns (90 rows). Eirika's
way passes a Draco Zombie that kills her in one blow. The other chest's rows did carry losses.

## The rule

- **The legs** (`wayLegs`) come from the march's own chain (`chainTo`, which now takes a start,
  as `breachFor` does; its memo key now carries the start). This is the walk alone when that is
  as short as the way through obstacles. Otherwise it is a walk to each obstacle in turn, then on
  from the tile where the next leg's field is joined past it. That tile is where `stepsThrough`
  already counts its steps (now returned beside the count, and cached in `stepsOnto`). The march
  and the price read one way.
- **Each leg** (`legLive`) is the old walk: a turn of MOV a stop, each stop's strikes from the
  game's forecast, u at its HP now. Each leg starts a fresh turn, because the march stops at a
  door to open it.
- **Left as an estimate:**
  - A locked door or chest that turnsFor reaches through its key's way (`keyWay`: the walk to the
    enemy or teammate holding the key) is read as walked to directly. On Ch21, Eirika holds her
    own Chest Key, so her way is the plain one.
  - The few tiles walked inside an opened change are not read.
  - A leg with no join tile ends the read. `viaObstacle` priced that way through the same
    `stepsOnto`, so this happens only if a field goes missing in between.

## Proof

- Unit test `test_a_job_behind_a_door_is_priced_on_its_way_there`. It fails on the old code.
- Replay `r688a` (Ch21 s4009 a1, bold) against `c688m`: Eirika's (2,18) job now reads about 400
  gold of loss, which is bold's price of a sure death (W.death 60 / W.gold 0.15). Play is
  main's to turn 21. There the stalled chest went to Syrene (loss 101) and not to Gerik (main's
  pick), and the game ran on: won, 38 turns, 0 deaths (main: 30 turns, 0 deaths). **(2,18) is
  still missed.** Under bold's weights a sure death (400 gold) is smaller than the chest
  (about 5,500 gold at its chance), so the job stays Eirika's, and the death cap, not the job
  read, holds her at (12,18). The second cause on #688 (`goalQuiet` counts only event-free
  phases, so the chest stalls only on turn 21) is unchanged.
