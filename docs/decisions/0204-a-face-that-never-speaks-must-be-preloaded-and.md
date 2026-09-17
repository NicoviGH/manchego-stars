---
id: 204
title: "A face that never speaks must be PRELOADED, and podium rungs overlap"
date: "2026-08-14"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A face that never speaks must be PRELOADED, and podium rungs overlap

ch05's scene 3 stages Ravisin raising Sahnar with **no dialogue at all** — Nicolas's call
(*"you don't need to even add lines... just add sahnars portrait to the scene"*), which keeps the
seven locked boxes and protects the beat the scene exists for. Getting a silent face on screen
taught two engine facts, both found **by filming**, neither visible to any static check: every id,
box count, wrap and podium assertion passed while the scene played wrong.

**1. A silent face cannot arrive mid-scene.** `TalkPrepNextChar` (`scene.c:626`) reopens the talk
bubble whenever the ACTIVE face slot differs from the SPEAKING one — `ClearTalkBubble()` then
`StartTalkOpen()` for the active face. A `[LoadFace]` for someone who does not speak next
therefore opens a bubble of its own, and the scene plays with **two stacked bubbles**. Vanilla
never does it: every mid-message `[LoadFace]` in the corpus has that face speak immediately
(MSG_904, MSG_092C, MSG_095A), and its silent loads are always **preloads before the first box**
(MSG_0954, MSG_095D, MSG_095E). So the directive is `present:` — *"on screen for this scene,
never speaks"* — rendering through `_script_to_message`'s existing `preload` path. It was first
built as `enters:`, and that name was a lie: position is not expressible, so a directive implying
it invites the bug back.

Two false trails, recorded because both looked right: `[SendToBack]` is **portrait z-order**
(`SetTalkFaceLayer` via `TALK_FLAG_4`), not a window close; and `[OpenX]` is only
`SetActiveTalkFace`, so nothing "leaves a window open".

**2. Podium rungs overlap, and the SPEAKER is drawn on top.** The tags are a ladder
(`msg_list.txt`: Right 11, MidRight 12, FarRight 13). For a scene of speakers that is harmless
and vanilla leans on it — ch05's own scene 4 seats four across adjacent rungs and each is drawn
over the others when its turn comes. **A silent face never gets a turn**, so on a neighbouring
rung it is buried for the whole scene (Sahnar played hers as a hood behind Ravisin's shoulder),
and on the SAME rung it is `[ClearFace]`d outright before the first box. Vanilla's stable
two-face right side leaves a rung empty — Right + FarRight, never MidRight + FarRight (MSG_904,
MSG_092C, MSG_0937, MSG_0954) — reached in three of those by sliding the incumbent out with
`[MoveRight]`. Ours reseats statically instead, which is free across the fade between scenes.
`assert_silent_faces_have_elbow_room` enforces it at distance 0 **and** 1.

**The first version of that guard banned adjacency outright and immediately rejected scene 4**,
which is shipped and accepted. The rule is about SILENCE, not adjacency; a test pins that
speakers on adjacent rungs stay legal so it cannot creep back.
