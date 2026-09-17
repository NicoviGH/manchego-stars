---
id: 179
title: "Campaign rosters live in campaign-named symbols"
date: "2026-08-07"
section: "Operational Gotchas (durable)"
issues: [25]
---

# Campaign rosters live in campaign-named symbols

**A chapter's unit tables are ours and are named `MS_ChNN*`** (`declare_unit_table`), appended to
`events_udefs.c` with an extern in `eventcall.h` — both already restored from HEAD each build. We no
longer block-overwrite whichever vanilla table the host slot's stripped cutscenes left unreferenced.

Two reasons, and the second is what forced it:

1. **The name lied.** ch04's moose rides a symbol our own source calls "dead Ch5 unit table". Reading
   an injector meant carrying two unrelated offsets at once: *ours* (chapter N hosts on slot N+1,
   because the prologue occupies a real, unnumbered slot — not renumberable, and invisible in play
   since the prep header reads `prepScreenNumber`) and *FE8's* (it inserted Ch5x at slot 5, so from
   slot 6 on the slot index and the vanilla symbol name disagree **in the base game**: slot 6 ships
   `Ch5EventData`, slot 7 ships `Ch6Events`). Both offsets are now stated once, in the `CH05_*`
   constant block, and nowhere else.
2. **Squatting rations you to what the slot happens to free.** Slot 5 freed seven tables; slot 6
   frees three, and ch05 needs seven. The alternative was borrowing Ch6's world-map *encounter*
   rosters — storage from a system we merely hope never runs.

Only the event-list symbols stay vanilla-named: `chapter_settings.json` resolves the
`ChapterEventGroup` from them, so they are structural. They are named in one per-chapter dict.
