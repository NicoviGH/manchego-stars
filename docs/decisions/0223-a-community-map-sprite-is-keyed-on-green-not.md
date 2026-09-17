---
id: 223
title: "A community map sprite is keyed on GREEN, not on index 0"
date: "2026-08-17"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A community map sprite is keyed on GREEN, not on index 0

Every map sprite this repo had vendored until now came from the decomp, where transparency is
palette **index 0**. `map_sprite_tool.recolour` was written against that and assumed it. FE-Repo
community sheets do not follow the convention: they ship on a green key, **`#80a080`**, and
their index 0 is an ordinary colour. Ravisin's donor is exactly that — index 0 is a cream used
by **12** pixels, and the backdrop is **253** pixels of green at index 5.

Converting one as though index 0 were transparent turns the BACKDROP into a real cast colour,
and **nothing downstream notices**: geometry passes, the ≤16-colour check passes, the preview
looks correct because a preview paints index 0 as the page background whether or not the sheet
means it. It renders in game as a solid frame-sized block with the art inside it. Nicolas did a
full palette pass against that broken baseline before anyone spotted it.

Two closures, because detection and prevention are different failures:
- **`_transparent_index` detects the key** — a sheet carrying `#80a080` is a community sheet and
  that colour is never part of the art; otherwise index 0, unchanged for every vanilla donor.
- **`sheet_info` rejects a finished sheet with no index-0 pixel at all.** Always wrong, invisible
  to every other check, and one line to catch.
- **`recolour` asserts transparency lands EXACTLY on the donor's key pixels** — the set, not the
  count. This is the guard that matters, and the weak version above is why: the first shipped
  sheets passed "has any index-0 pixel?" with 265 legitimate background pixels while carrying
  **holes punched clean through Ravisin's face**. Recovering the palette work after the green-key
  discovery re-derived the donor→cast map by voting on surviving pixels, and the 12 cream
  face-highlight pixels — already wrongly zeroed by the botched first repair — had no votes left,
  so they fell through a `.get(v, 0)` default straight back to transparent. **A colour may map to
  0 only if it IS the key.** A default of "transparent" for an unmapped colour turns every
  recovery mistake into a hole; the fallback is now nearest-cast-colour, and the invariant is
  checked rather than trusted.

Also fixed, because it is what forced the conversion to be hand-rolled twice: `recolour`
validated its output against a donor resolved from the INPUT FILENAME. That works for a vanilla
sheet and is impossible for a vendored one — `Druid Hoodless (F) {Ultra-Fenix, Velvet Kitsune}`
is in no wait table, so the tool exited on every community sheet it was handed. It now takes an
explicit `donor=` and falls through to inference when there is no decomp row to check against.

**A donor is read for FRAME SIZE only — and `pattern` is not a frame count.** The wait row's
first field is `pattern`, which `unit_icon_data.h` itself calls unused. It was briefly read here
as a frame count, which is the very misreading this ADR warns about one paragraph up: Eirika Lord
carries `0`, the Druid `2`, the Bonewalker `3`, and **all three sheets are 16x48** — three frames.
The count comes from the sheet HEIGHT and from nothing else.

That correction matters, because the conclusion drawn from the misreading ("frame count doesn't
matter") is **unsafe**. `ApplyUnitSpriteImage16x16` (`bmudisp.c`) loops `for (i = 0; i < 3; i++)`
unconditionally, so a 2-frame 16x16 sheet is read past its end — and `sheet_info` used to accept
one. `_assert_frame_count` now rejects it. Ravisin's `base: Druid` is correct, and it is correct
because both sheets are three frames, not despite a difference that never existed.
