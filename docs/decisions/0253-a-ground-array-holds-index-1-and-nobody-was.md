---
id: 253
title: "A ground array holds index + 1, and nobody was reading the ground"
date: "2026-08-16"
section: "Operational Gotchas (durable)"
issues: [25, 65]
---

# A ground array holds index + 1, and nobody was reading the ground

Nicolas, on the ch05 PR: *"the platforms in combat you have are the grassy road ones."* Two
independent faults, and the second was invisible for two months because the first hid it.

**ch05 and ch02 never named a ground at all.** A hosted chapter that sets no `battleTileSet`
keeps its HOST SLOT's vanilla one, and vanilla's slots are not our world: ch05 sits on slot 6,
which ships vanilla Ch6's `battleTileSet = 6` — a table that sends `TERRAIN_ROAD` to `michi1`
and `TERRAIN_PLAINS` to `heichi1`. ch05's map is **53% road**, so a snowbound elven tomb staged
essentially every fight on a dirt track. ch02's slot 3 was wrong the same way. Both were wrong
*by omission*, which is why one line each would have been the wrong fix:
`CHAPTER_BATTLE_TILESETS` is now **required total** by the injector and by a test, so a new
chapter must state its ground rather than inherit one.

**And the snow arrays were off by one.** `GetBanimTerrainGround` ends `return ret - 1`, so a
`BanimTerrainGround_*` array holds **table index + 1**. The cave path always knew that (it
writes 21 for `siroyuka1` at index 20); the snow path wrote raw indices. Every snow chapter had
therefore been drawing the row *below* the platform it named since #65 — open ground resolved
to `mizuiumi1`, a vanilla **lake**, and chapters that asked for rough got the drift. Both paths
now go through one `_ground_value()`.

Three things worth keeping:

1. **Nothing in this repo read the ground.** Not the build, not a unit test, not a scenario. The
   first `recordch05platform` asserted *terrain*, filmed, and PASSED while the fighters stood on
   the wrong platform — terrain says which tile, and the ground is the answer to a different
   question. It now reads `gBanimFloorfx`, the engine's own resolved table index, and names the
   row. *A scenario's verdict only covers what it READS* has now cost us twice.
2. **The plausible wrong answer is the dangerous one.** Grass under snow got reported by eye in a
   day. The drift-instead-of-rough error survived two months because the wrong platform was
   still snow. Where a defect's failure mode is "looks fine", an assertion is the only detector.
3. **Verify a palette from data, never from a crop.** The first measurement that caught it
   sampled a band containing background as well as slab, which diluted the share; the honest
   test compares against colours **unique** to each candidate platform. Extends
   `feedback_verify_via_data_not_pixels` to grounds.

`TERRAIN_ROAD` then got its own slot — *"vanilla already has a road terrain right? can't you
just assign these tiles to that?"* (Nicolas). Correct, and it deflated a change we had described
as adding a category: the engine's array is flat, one entry per terrain, and `ROAD` already had
an entry that our helper was collapsing into "everything else". Its ground is the vendored
`Snow Dirt Path` ({Cynon}, F2E), chosen over a consistent-looking alternative with the tradeoff
stated and accepted: **its three distance bands are not the same material**, so a ranged
exchange reads browner than a melee one. The twilight tint is the knob if that ever grates.

_Decided: 2026-08-16 (Nicolas). Proof: `recordch05platform` PASS, ground index 118 =
`ms_snowpath`, slab 54–73% colours unique to that platform and 0% of either neighbour._

---
