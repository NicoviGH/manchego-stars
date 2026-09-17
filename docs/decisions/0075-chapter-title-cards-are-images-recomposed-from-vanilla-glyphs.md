---
id: 75
title: "Chapter title cards are IMAGES, recomposed from vanilla glyphs."
date: "2026-06-09"
section: "Combat System"
issues: []
---

# Chapter title cards are IMAGES, recomposed from vanilla glyphs.

FE8's intro/Status title banner is a 4bpp graphic (`chap_title_data[chapTitleId]`,
`src/chapter_title.c`), not text — text ids (`chapTitleTextId`, 0x160+) only feed the
save-select/Status *strings*. `tools/gen_chapter_title.py` rebuilds the card for a
custom chapter by cutting verified glyphs out of the vanilla cards (atlas of hand-read
cut columns; unknown glyph = hard error) and recomposing at vanilla's optical center
(x≈99), so letterforms, outline, shadow, and palette indices stay pixel-identical to
the runtime palette. `inject_prologue` writes it over the host slot's PNG (a restored
build artifact; stale `.4bpp`/`.lz` removed so make re-converts) and sets both
`chapTitleTextId` and the copied goal block's `statusObjectiveTextId` (else the Status
screen keeps vanilla's "Defeat O'Neill") from the chapter YAML. Extend the glyph atlas
per new chapter title.
_Decided: 2026-06-09_
