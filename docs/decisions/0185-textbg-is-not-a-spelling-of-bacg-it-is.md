---
id: 185
title: "`Text_BG` is not a spelling of `BACG` — it is a CALL with a fade cycle on both ends"
date: "2026-08-13"
section: "Operational Gotchas (durable)"
issues: []
---

# `Text_BG` is not a spelling of `BACG` — it is a CALL with a fade cycle on both ends

(`Convo_Helpers.h` → `Event_TextWithBG`: `FADI` if the screen is up → `REMOVEPORTRAITS` → `BACG`
→ `FADU` → text → `EventScr_TextShowWithFadeIn`, which does `CLEAN` then `FADU` back onto the
**map**). That last step is why ch03/ch04/ch05 hand-roll the sequence instead of calling it: our
openings run BEFORE `LOMA`, so the map it fades up onto is still the host slot's. The macro is
right for a village visit (`village_script` uses it) and wrong for a pre-`LOMA` opening.

Ours therefore holds ONE `BACG` across the three tomb scenes and fades through black between
them — vanilla's separation without vanilla's return-to-map. The BG is not re-issued at each
fade, and that is deliberate rather than lazy: `EventShowTextBgDirect` only decompresses while
`activeTextType` is `REMOVEPORTRAITS`/`_1A22`, and each `Text()` leaves it at `TEXTSTART`, so a
second `BACG` would be the no-op that already bit ch03 and ch04. **Filmed rather than asserted**
(`recordch05opening`), because "still in VRAM" is a decomp reading and the screen is the witness.

_Decided: 2026-08-13 (Nicolas: "does vanilla use a background in its opening scenes? lets have a
plan before jumping into assigning a BG")._
