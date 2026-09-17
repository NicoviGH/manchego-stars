---
id: 184
title: "A cutscene's CHANNEL is inherited from the twin, not chosen"
date: "2026-08-13"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A cutscene's CHANNEL is inherited from the twin, not chosen

ch05's scene table left "on-map bubble vs `Text_BG`" as a per-scene decision, and the id-budget
work priced it as an open question. It was never open: `EventScr_Ch5_BeginningScene` at HEAD
answers it for all seven of ch05's opening scenes, because ours are its scenes one for one.

| vanilla | who | how it is played |
|---|---|---|
| `0x9BA` | Joshua's cold open | `Text_BG(BG_SERAFEW_VILLAGE)` |
| `0x9BB` | the Joshua/Natasha meet-cute | `SetBackground(BG_SERAFEW_VILLAGE)` + bare `TEXTSHOW` |
| `0x9BC` `0x9BD` | Glen's orders; Glen and Cormag after | `Text_BG(BG_SERAFEW_VILLAGE)` |
| `0x9BE` `0x9BF` | the party arrives | `SetBackground(BG_TOWN)` + bare `TEXTSHOW` |
| `0x9C0`–`0x9C2` | on the street, party staged | `TEXTSTART` — on-map bubbles |
| — | | **`CALL(EventScr_08591FD8)` — prep** |
| `0x9C3` `0x9C4` | Joshua alone; Natasha alone | `FADU(16)`, then on-map bubbles |

**`vanilla_scene.py` prints `0x9BB` as "map" and that is a reporting artifact, not a channel.**
It classifies by the text call, and `0x9BB` is a bare `TEXTSHOW`; the `SetBackground` two lines
above it is what the scene actually plays over. Reading the tool instead of the script is how
"does vanilla use a background in its opening?" stayed open — it does, for the entire first half.

Three things fall out, none of which needed an argument:

- **Two backdrops, reused.** Vanilla spends `BG_SERAFEW_VILLAGE` on four consecutive scenes and
  only cuts to `BG_TOWN` when the party physically arrives. So ch05 wants ONE tomb backdrop for
  its three pre-arrival scenes and a second for the arrival — not a mood image per scene.
- **Where PREP sits is settled**: vanilla puts two full scenes AFTER the prep `CALL` and re-opens
  with `FADU(16)`. Our scenes 6 and 7 are those scenes' twins.
- **The map half cannot start early.** `PutTalkBubble` anchors to a speaking UNIT, and vanilla
  reaches `TEXTSTART` only once the party is staged. Nothing is on ch05's field before `LOMA`,
  so scenes 1–4 could not have been bubbles whatever we preferred.
