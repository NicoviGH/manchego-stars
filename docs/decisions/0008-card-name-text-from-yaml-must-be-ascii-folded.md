---
id: 8
title: "Card/name text from YAML must be ASCII-folded before FE8 encoding — `name_message_body` does it centrally."
date: "2026-06-25"
section: "Engine & Tech Stack"
issues: []
---

# Card/name text from YAML must be ASCII-folded before FE8 encoding — `name_message_body` does it centrally.

Dialogue routed through `_script_to_message` already gets `_fe_dialogue_text` (em-dash→`--`, smart-quotes→ASCII, etc.), but location-card/title/name text bypassed that path and went straight to `name_message_body` — so a literal em-dash in a YAML `location_card` ("Bryn Shander — West Gate") reached the encoder as a non-charset byte and **garbled the ch02 opening card** (#22). Fix: `name_message_body` now `_fe_dialogue_text`-normalizes first, so every card/title/name is charset-safe and the terminator-parity count sees the bytes the encoder will actually emit. Keep authored unicode in the YAML; the encoding boundary folds it.
**Companion gotcha — location-card nameplates cap at ~96px.** `BROWNBOXTEXT`/`StartBrownTextBox` draws the card text as exactly **3×32px sprites** (`popup.c` `BrownTextBox_Loop`, `for (i=0;i<3;i++)`); the brown *border* grows with the string but the *text* region is fixed, so anything past ~12-14 chars clips silently (the in-engine capture caught "Bryn Shander — West Gate" rendering "Bryn Shander -- We"). Keep `location_card:` values to short place names (vanilla does: "Targos", "Bryn Shander"); push locational detail into the scene/dialogue, not the plate. Don't widen the shared widget (it's a vanilla popup — "additive, never global").
_Decided: 2026-06-25_
