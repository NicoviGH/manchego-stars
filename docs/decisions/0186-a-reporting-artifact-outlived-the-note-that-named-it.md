---
id: 186
title: "A reporting artifact outlived the note that named it: the ch05 endings"
date: "2026-08-19"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A reporting artifact outlived the note that named it: the ch05 endings

The section above records that `vanilla_scene.py` prints `0x9BB` as `"map"` and calls it *a
reporting artifact, not a channel*. It fixed the READING and left the TOOL, so the artifact was
mined a second time — and this time nobody caught it. The ch05 YAML's anatomy table, issue #25's
per-scene notes and `HANDOFF.md` all carried **"the endings are ON-MAP at 29"** for three weeks,
and the wiring was about to be built against it.

`EventScr_Ch5_EndingScene` opens `FADI(16)` — the map goes **down** — then
`SetBackground(BG_SERAFEW_VILLAGE)`, then three bare `TEXTSHOW`s. There is no `TEXTSTART` in it.
Vanilla's ch5 ending is a **backdrop scene at ~42**, and by the rule above ours inherits that.

**The tool now tracks the backdrop as scene STATE rather than classifying by the text call**,
which is what it should always have done: `TEXTSHOW` prints into whatever surface is up.
Set by `SetBackground` / `BACG` / `Text_BG`; taken down by `CLEAN` and by
`CALL(EventScr_TextShowWithFadeIn)` (which is `FADI` + `TEXTSTART` + `CLEAN` + `FADU` back onto
the map, `events_script_utils.c:211`). **`REMA` does not take a backdrop down** — it ends the
TEXT, which is why vanilla's `0x9BF` is still `BG_TOWN` with a `REMA` in front of it and no
`SetBackground` of its own. `tools/test_vanilla_scene.py` pins all three ending ids, both
`SetBackground` + bare-`TEXTSHOW` scenes, and `0x9CC` as genuinely on-map — the Talk recruit
sits forty lines from the ending in one file and takes the *other* channel, so scene 14 stays
at 29 while scenes 16 and 17 take 42.

Three things fell out, and two of them were problems the on-map reading would have shipped:

- **Six speakers, and a bubble anchors to a UNIT.** `PutTalkBubble` needs a staged speaker
  (which is why `ch05_basil_join_block` carries a `CUMO_CHAR` and the ending cannot). ch05
  deploys 9 of a 10-unit pool, so on-map Marty, Wolfram, Braulo and RBG can each be talking
  from a tile nobody is standing on. **ch04's ending had already made this exact argument for
  itself** and its comment says so; ch05's note was written without reading it.
- **The two ending fallbacks needed no re-boxing.** Both overrun 29 and were on the owed list
  for it; at 42 they fit as authored. What is still owed is the *Talk recruit's* fallback,
  which really is on-map.
- The endings cost **three** message ids, from the swept neighbourhood and ch05's host block:
  scene 16 twice (Sahnar recruited or not) and scene 17 once. It was briefly six, until the
  Lupin branch came out — see "Neither ch05 ending branches on Lupin" below.

**The lesson is the one the ch04 comment already carried: when a tool is found lying, fix the
tool.** A note that records "this output is wrong" protects only the person who read that note.

_Decided: 2026-08-19 (Nicolas: "I have no idea where that came from ... you shouldn't have to
rediscover anything")._
