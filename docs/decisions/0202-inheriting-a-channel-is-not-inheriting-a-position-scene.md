---
id: 202
title: "Inheriting a channel is not inheriting a POSITION: scene 5 plays after PREP"
date: "2026-08-14"
section: "Operational Gotchas (durable)"
issues: [25]
---

# Inheriting a channel is not inheriting a POSITION: scene 5 plays after PREP

"A cutscene's CHANNEL is inherited from the twin" (above) reads vanilla Ch5's own beginning scene
and gets ch05's seven openers right — three tomb backdrops, the ridge, an on-map bubble, then two
scenes after the prep `CALL`. It also implies scene 5 sits where its twin sits, **before** that
`CALL`. It cannot, and the reason is ours, not vanilla's.

**Vanilla stages its speaking party; we don't have one yet.** `EventScr_Ch5_BeginningScene`
`LOAD1`s `UnitDef_088B59C8` and `UnitDef_088B56F8` — Eirika's group — and only *then* plays
`0x9C0`–`0x9C2` as on-map bubbles; the ally table `UnitDef_Event_Ch4Ally` goes in right before
prep, as the deploy template. Our party arrives **through prep**: on a prep chapter the ally table
is never `LOAD`ed and the roster is placed by Pick Units (see "How the deploy cap + prep screen
are actually wired"). So at the point vanilla's twin plays, ch05's field holds sixteen risen dead,
Ravisin, and one green shrub — and Basil's *"Oh! Tourists. In the tomb."* would be addressed to an
empty pocket, in **both** arms.

So the beat moves after `CALL(CH05_PREP_SCRIPT)`, and takes vanilla's own after-prep shape, which
is what `0x9C3`/`0x9C4` already are: **`FADU(16)`** — the shared prep prologue fades to black and
leaves it there, so anything visible afterwards brings its own fade-up — then `CUMO_CHAR` +
`STAL(60)` + `CURE` to put the camera on the speaker, then `TEXTSTART`. `PutTalkBubble` anchors to
a unit, so the camera move is load-bearing and not decoration.

Two things fall out, both good:
- **The ask and the flip are one beat.** The `CUSA` was already after prep, for an unrelated
  reason (Basil is green across the prep screen so Pick Units never sees her and she costs no
  slot). Box 3 is *"...Take me to her?"*; the next command is the green→blue flip that answers it.
  Before this the CUSA was silent and the join simply happened.
- **Two branches now share one event list**, so `branch_on_check_alive` gets its `label_base`
  used in anger for the first time: the arrival keeps 0/1, the join takes 2/3. `BEQ`/`GOTO` scan
  the list for a matching `LABEL`, so a second branch left at the default would have jumped into
  the arrival's arms.

**The general rule.** The twin answers *how a scene is played* — backdrop or bubble, and how wide.
It answers *where the scene sits* only where the surrounding machinery is also vanilla's. Ours
diverges at exactly one place, prep, and that is the seam to check every time.
