---
id: 181
title: "A `CHAPTER_L_*` label is resolved by VALUE, never spelled from a number"
date: "2026-08-07"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A `CHAPTER_L_*` label is resolved by VALUE, never spelled from a number

`CHAPTER_L_5 = 0x06` and `CHAPTER_L_6 = 0x07` — the Ch5x insert again. Slot 6 is `CHAPTER_L_5`.
For slots 1–4 the name matches the number, which is why four injectors hardcoded the literal and were
right by accident. `chapter_label_constant(slot)` reads chapters.h. Guessing fails **silently**: a
`gDefeatTalkList` entry keyed to the wrong `.chapter` never matches, so the boss dies, no flag is
set, `DefeatBoss` never fires, and the chapter cannot be won, with nothing in the build to say why.
