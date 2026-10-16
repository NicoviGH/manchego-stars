---
id: 346
title: "A cast member's help text is its own"
date: "2026-10-15"
section: "Story & Dialogue"
issues: [493]
---

# A cast member's help text is its own

Nicolas, 2026-10-15, on the wiki's character pages: "some things still read their slot".

Every unit that rides a vanilla character slot carries a `help_text:`, the line R shows on its
name, written over the slot's own description message (`descTextId`), so no unit shows its vanilla
slot's line again (Braulo had read "The princess of the kingdom of Renais"). A classed cast member
carries it in its unit file (`inject.names.inject_names`). A guest or a boss on a borrowed slot
(Hlin on Natasha's, Halvar on Bazba's) carries it on its entry in the chapter YAML, and
`inject.text.write_nameplate` writes it with the name. The build stops on any map unit without
one; a slot only a scene shows (Glimmerfrost in her hut) is exempt. The box holds what
vanilla's 83 descriptions do: two lines, 175px at the widest (`fe8_talk_font.HELP_TEXT_BUDGET_PX`).
The wiki reads the same line through `inject.text.slot_help_text`.

How a terminator is padded follows the encoder, not a byte count. `textencode` packs a printable
byte with the byte after it and a control byte alone, starting afresh after each control code, so
an odd printable run swallows whatever follows it. Braulo's two lines are even in total and his
second run is odd: it ate the `[X]`, and his help text read on into Marty's. `inject.text._eats_end`
walks the stream as the encoder does. `tools/verify_text.py` now also fails a message that decodes
past the start of the next one; its length bound alone had passed all four that ran on.

_Decided: 2026-10-15._
