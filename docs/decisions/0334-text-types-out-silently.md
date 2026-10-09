---
id: 334
title: "Text types out silently: no typing sound anywhere"
date: "2026-10-09"
section: "Art & Audio"
issues: [26]
---

# Text types out silently: no typing sound anywhere

Vanilla FE8 plays a blip for every character a text box types out. Nicolas, 2026-10-09: "the
text noise is super annoying, what if we removed it? not just here but throughout? I don't see
what purpose it serves." Engine patch `0017-patch-silent-text` removes every typing-sound call:
`SONG_6E` in talk bubbles (`scene.c`), backdrop-scene text (`cgtext.c`) and help boxes
(`helpbox.c`), plus the two variants vanilla swaps in on special boxes (`SONG_7A` on
`TALK_FLAG_7`, `SONG_2E5` on dialogue-box config 0x10). Only the calls go; every branch, flag
and print delay around them stays, so text speed and skipping are unchanged.
