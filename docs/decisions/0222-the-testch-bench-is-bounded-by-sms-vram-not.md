---
id: 222
title: "The TESTCH bench is bounded by SMS VRAM, not by its tile row"
date: "2026-08-19"
section: "Operational Gotchas (durable)"
issues: [25]
---

# The TESTCH bench is bounded by SMS VRAM, not by its tile row

The bench ran out of seats at seven and it was briefly written down as "the bench is full",
which invites a redesign. It is not a limit FE8 imposes — it is the geometry of one row.

`SANDBOX_FOE_POSITIONS` is a single row at y=9 with **spacing 2**, and the spacing is load-bearing:
`recordenemy` places the bait unit orthogonally adjacent to its target and requires **no other foe
adjacent**, or the counter-attack it films is the wrong creature's. On a 15-wide map that yields
x=2,4,…,14 — seven. The party sits at y=4, so **a second row lifts it immediately**; a wider
`ch-test-snowfield.json` does too. (`sandbox_map_size` READS that map, because the test chapter is
repointed at it by `inject_winter_tileset` and is not vanilla Ch1's.)

**The real ceiling is SMS VRAM, and it is much higher.** `ResetUnitSprites` (`bmudisp.c`) hands out
`0x40` = **64 slots**, consumed from both ends by two counters that grow toward each other:

| counter | starts | per distinct sprite |
|---|---|---|
| `gSMS16xGfxIndexCounter` | 63, walks **down** | −1 per 16×16 |
| `gSMS32xGfxIndexCounter` | 0, walks **up** | +2 per 16×32, +4 per 32×32 |

When they **cross**, later sprites silently overwrite earlier ones — the failure `recordunitlist`
exists to catch. Two consequences worth holding on to:

- **Cost is per DISTINCT sprite, not per unit.** Twenty kobolds of one class cost one slot; the
  bench pays once per creature, and its seven spend ~10 of the 64 alongside the player party.
- **The two size classes are not interchangeable.** A 32×32 costs four times a 16×16 and eats from
  the opposite end, so a bench of monsters exhausts the pool far sooner than a bench of humans.

What actually failed before was neither ceiling: the row held a tile at x=16 on a 15-wide map, and
`_next_sandbox_tile` only ever guarded running OUT of tiles, never a tile that does not EXIST. The
seventh creature deployed off the map edge and `recordenemy` failed walking the cursor to a column
the map has not got. `assert_sandbox_bench_fits` now reads the map and fails the build instead.
