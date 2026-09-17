---
id: 139
title: "Map-sprite EDITING surface + geometry/animation read from the decomp (2026-06-05)."
date: "2026-06-05"
section: "Art & Audio"
issues: []
---

# Map-sprite EDITING surface + geometry/animation read from the decomp (2026-06-05).

The creative pixel pass is done in a local, offline, stdlib-only browser editor — `tools/map_sprite_editor.py
--campaign <name>` — an Aseprite-style canvas (tool column, palette locked to `cast_palette.png`, checkerboard
transparency, zoom, onion skin, donor reference / A-B overlay, motion map) with a live idle preview, a frame
timeline, a per-character picker, **Save** (writes exact cast indices back to `<id>.png`) and **Reset** (reverts to
the clean-recolour snapshot in `map_sprites/.base/`, gitignored). It supersedes the LibreSprite fallback. Companion
batch ops are in `tools/map_sprite_tool.py`: `recolour` (donor → cast palette, nearest-colour + `d:c` overrides),
`preview`, `grid`, `palette`, `setpx`. Two things are READ FROM THE DECOMP, never guessed (a 16×96 sheet is ambiguous,
6×16×16 vs 3×16×32): **(a) frame size** per donor from `UNIT_ICON_SIZE_*` in `src/unit_icon_wait_data.c` via
`map_sprite_tool.donor_sms_geometry(base)` — Cyclops/Berserker/Mauthedoog/Manakete_Myrrh are **16×32**, the rest 16×16;
used by both the editor and `inject_map_sprites`; **(b) idle timing** from `bmudisp.c` (`GetGameClock() % 72` →
frames 0,1,2 held 32/4/32/4 ticks @60fps), which also drives the editor's "follow motion" (an edit rides the bob
across frames, offsets measured per-row from each character's own donor). _Guessing the size from PNG dims cost real
time once; the rule is read it from the decomp._

**Enemy/non-cast sprites: vanilla FE8 where the look fits; community (FEUniverse) or custom only where a creature has no vanilla analogue** (Grells, Messie, ice trolls).
The full-custom rule above is for the player cast + named recruits, where identity matters most.
_Decided: May 2026_
