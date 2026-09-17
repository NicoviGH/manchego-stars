---
id: 136
title: "Green NPC chwinga: per-CHARACTER override of a derived cast sprite, tinted by the green faction palette (#38, 2026-06-24)."
date: "2026-07-30"
section: "Art & Audio"
issues: [38]
---

# Green NPC chwinga: per-CHARACTER override of a derived cast sprite, tinted by the green faction palette (#38, 2026-06-24).

The ch02 chwinga are the green-faction mirror of the enemy reskin. Unlike enemy grunts they ride **distinct NPC slots**
(`DARA`/`KLIMT`/`MANSEL`) — so the cast's per-CHARACTER `gMapSpriteOverride` IS the right tool (their class,
`CLASS_PEGASUS_KNIGHT`, is a balance chassis shared with player flier Pinky, so a class-level reskin would turn Pinky into
a chwinga). They are kept OUT of `gMapPaletteOverride`, so `GetUnitSpritePalette` falls through to the faction switch and
the **green NPC bank** tints them automatically (no bespoke palette). Sprite source: Sclorbo's map sprite — he is a
chwinga (Nicolas, 2026-06-24: "use his sprite, apply the green ally palette"; identical green triplets, blue glow kept).
His **cast-palette** sheet is remapped onto his SMS base's (`Civilian_F1`) standard role layout at build time
(`map_sprite_tool.remap_sms_palette`), so the single source of truth stays `sclorbo.png` (no committed derived asset);
one shared SMS slot + glide MU sheet serve all three identical NPC slots. Injected by
`build_campaign._inject_ch02_chwinga_sprites` (inside `inject_map_sprites`, which owns the override tables).

**A cast member that CHANGES faction colour (green NPC → blue player on recruit) is faction-tinted, not
cast-palette-pinned (`FACTION_TINTED_CAST`, #23, 2026-07-10).** Trex is a Colm-style talk recruit: he stands GREEN,
then a `CUSA` flips his faction to blue on Talk. He shipped with a custom cast map sprite, so his charId landed in
`gMapPaletteOverride` — and `GetUnitSpritePalette` honours that override **unconditionally**, pinning his one bespoke
(blue player) cast palette regardless of faction. Result: a green-faction Trex still drew blue (Nicolas caught it in
the recruit GIF). A charId-keyed cast override simply cannot follow a faction change. Fix = generalise the chwinga /
enemy-reskin logic to a cast member: the `FACTION_TINTED_CAST` set (`build_campaign`) routes his sheet through
`remap_sms_palette` onto his donor class's (`Thief`) standard SMS **role layout** and keeps his charId **OUT of**
`gMapPaletteOverride`, so `GetUnitSpritePalette` falls through to the faction switch. His custom winged-kobold **shape**
still ships — the SMS + MU overrides (`gMapSpriteOverride`) are retained — only the palette is now side-driven: green
as an NPC, then the standard blue player bank once recruited. Idle + committed walk are both remapped with the donor
WAIT palette so they share role indices (no derived asset: temp dir; single source stays `map_sprites/trex.png`).
Trade-off accepted (Nicolas, 2026-07-10: "reads more blue than green, but I'll take it"): faction tinting gives the
class's standard green/blue ramps, not a hand-tuned green — the bespoke cast palette and faction tinting are mutually
exclusive for one sheet (a role-layout sheet is what lets *either* faction palette land correctly). If a role reads
wrong, `remap_sms_palette`'s `overrides={src_idx: std_idx}` knob corrects it. This is the pattern for **any** future
recruit with a custom sprite (talk or green-start): add its uid to `FACTION_TINTED_CAST`.

**When the RECRUITED look is the bespoke sheet, faction-tinting is the wrong tool — give the unit a
PRE-RECRUIT variant instead (`pre_recruit_roles`, #24, 2026-07-30).** Lupin is the same shape of problem as
Trex (placed RED as the wolf pack's leader, `CUSA`'d over by Marty's parley) but the opposite requirement:
Nicolas's call is **red while hostile, the finalized grey once recruited** — "only his colours change upon
recruitment". `FACTION_TINTED_CAST` can't do that; it trades the bespoke palette away, so he'd join as
standard **blue**. Leaving him in `gMapPaletteOverride` can't either: that override is unconditional, so a
hostile Lupin renders grey — and FE reads grey as *already acted*. A single sheet can't serve both, because
the cast palette's index roles are not the standard palette's (his grey ramp lands on cast 1/2/3/4/11, which
under the enemy palette gives dark maroon, pink-grey, near-white and **bright green** at 11), and there is no
spare cast-palette entry to redefine — all 16 are in use across the cast sheets. So the unit gets **two
sheets**: the committed cast one, and a standard-palette one **derived at build time** by remapping cast
indices to SMS roles (`art.map_sprite.pre_recruit_roles`, `_remap_indices`) — no committed derived asset, so
every pixel edit to the cast sheet flows into the pre-recruit look automatically. `gPreRecruitVariant`
(charId → SMS id + MU sheet) is consulted by all three per-character override hooks **only while
`UNIT_FACTION != FACTION_BLUE`**: sprite and walk return the variant, and the palette hook *skips* the purple
bank so `GetUnitSpritePalette` falls through to the faction switch. Empty table == exactly vanilla. Note an
explicit ROLE map is required, not `remap_sms_palette`'s nearest-RGB: a grey ramp nearest-matched against a
coloured palette collapses onto the constant entries and the unit barely changes colour by side. One
limitation, accepted: an index serving two roles can't be split (Lupin's cast 2 is body shadow *and* the
glasses pupil, so the pupil goes dark-red with the shading — invisible at 32×32). This is the pattern for a
recruit whose joined look is its bespoke art; `FACTION_TINTED_CAST` remains right when the joined look may be
the side's standard blue.
_Decided: 2026-07-30_
