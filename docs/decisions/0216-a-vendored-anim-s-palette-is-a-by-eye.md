---
id: 216
title: "A vendored anim's palette is a BY-EYE call, so it gets an editor, not a function"
date: "2026-08-17"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A vendored anim's palette is a BY-EYE call, so it gets an editor, not a function

A community battle animation arrives on its author's own colours, and for a named unit those are
often wrong on faction while being right on everything else. The enemy-reskin path answers this
with `recolor:` naming a **function** (`enemy_red_recolor`: blue-dominant clothing → a red ramp at
the same brightness). That works for a generic class, where the question is only "which side is it
on". It does not work for a character, and Ravisin is why.

**A ramp cannot be inferred from RGB.** The author shipped an index-aligned "enemy" swatch, so
swapping it looked free — and it turned her **hair teal**, because the art does not use those
indices the way the swatch suggests. Auburn hair matching her bust was the entire reason that
animation was chosen over the hooded finalists. No rule over colour values would have known that;
the ramp had to be *looked at*.

So a character's palette is hand-edited: **`tools/banim_palette.py`**, a local browser editor for
an imported anim's own 15 colours, with the animation playing at the `.txt`'s real cadence while
they change. Neither existing tool could do it, and the reason is worth keeping — `map_sprite_swapper`
remaps **indices** against the locked cast palette and `map_sprite_editor` paints **pixels** against
a palette it holds still. Both move pixels and hold colours fixed. Here the colours are the variable,
and the target colour is not in the sprite's set to begin with. Its `👁 isolate` is the load-bearing
control: it answers "which index owns the hair" before anything moves, which is precisely what the
rejected swatch got wrong.

The edit lands as `palette_edit:` on the unit's `import:` block and is applied as
`build_import(recolor=...)` — **the agbpal only**. Every sheet index is byte-identical, so an edit
is reversible, re-runnable, and never a silent re-import. Swatch ORDER comes from
`feditor_to_banim._palette` itself rather than a local derivation: edit index N in the tool, index N
in the ROM. A missing `palette_edit:` file **raises** — a typo must fail the build, because the whole
premise is that native was wrong for this unit.

**And a ramp must stay a ramp.** The first hand edit set the robe's three entries to one flat black
and the skin's two to one flat white. It rendered as a silhouette: fold shading gone, and the cast
FX — indices 2/3 draw the spell fan as well as cloth — became a solid void. This is the rejected
Arena palettes' failure one axis over. **Those crushed CHROMA, this crushed VALUE**; merging distinct
ramp entries into a single colour destroys form either way. Ship the intent with the steps intact
(`docs/demo/ch05-ravisin-palette.png`). Judge it offline first — this whole loop cost seconds and no
ROM build, the same reason `rom_bg_preview.py` exists.
