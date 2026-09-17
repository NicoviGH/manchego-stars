---
id: 91
title: "Arena presentation: winter is campaign-wide; attendants remain chapter-owned."
date: "2026-08-11"
section: "Economy"
issues: [265]
---

# Arena presentation: winter is campaign-wide; attendants remain chapter-owned.

The arena stays mechanically and structurally vanilla, and the winter reads through palette only —
never through replaced graphics or TSA. **Both arena views are expressed as a DELTA over the base
ROM's own words, and that is the decision.** Each view names only the entries that change; every
other word is copied from vanilla at build time.

Both views were first authored as complete 64-word replacements, and both were rejected on sight
for the same reason — so the shape of the data now makes that failure unrepresentable.

- The **welcome screen** (the coliseum exterior) changes 16 words of 64: the sky drops to a flat
  overcast, and the stall awnings take the same blue the banners fly inside. **The sandstone is
  deliberately untouched.** The rejected pass cooled the entire building; it held luminance
  faithfully (range 159 → 175) while crushing the masonry's saturation from 0.29–0.74 down to
  0.10–0.20, and the stone stopped reading as a material. Warm stone under cold weather is what
  sells the cold — a uniformly cool frame just reads as fog.
- The **in-combat coliseum** changes 11 words: the fighting floor turns snow-white and the red
  hanging banners turn blue, over vanilla's own stone, wood, gold, crowd and combatants. Its
  rejected pass was the same mistake: a cold ramp across all 64 entries of each
  `Pal_ArenaBattleBg_A/B/C` phase. Only 3 of those 64 entries animate (the crowd's gold flicker
  and one stone tone), so a delta preserves the ten-frame cycle for free where a regenerated ramp
  has to reproduce it by hand.

Both edits are provably local: an isolation mask over the real TSA showed the sky, the awnings, the
floor and the banners each own palette indices nothing else uses, so palette-only was possible with
no tile remap. `tools/rom_bg_preview.py` is what answered that, offline, in milliseconds. Before and
after: `docs/demo/ch05-arena-{welcome,combat}.png`, with the rejected pass kept as
`ch05-arena-combat-REJECTED.png`.

**The general lesson, and the reason both passes shipped past their tests:** a wash-out is a
*chroma* failure, and every check we had measured luminance. Palette work must assert what stayed
vanilla, not only what changed — the `ch05arena` proof now anchors three untouched vanilla words in
each view alongside the ones it expects to move.

The special Arena image owns the visible floor as well as the stands, and Arena mode explicitly
skips the normal `battle_terrain_tougijou1` platform path (`EfxClearScreenFx` clears BG2 when
`GetBattleAnimArenaFlag()` is true) — so that terrain asset is dead data here and stays untouched.

The default attendant remains FE8's human Arena Master; ch05 alone overrides him with Generic
Pretsel's armored skeleton, a courteous dead elven functionary still operating the tomb's ancient
arena. Every selection is data-driven at two levels (campaign palette, chapter face), additive
rather than a shared-asset overwrite, and falls back to the vanilla palette/face when a setting is
absent. Implementation scope and acceptance criteria live in issue #265.
_Decided: 2026-08-11; combat treatment settled 2026-08-12 (Nicolas; #265)._
