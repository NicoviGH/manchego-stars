---
id: 198
title: "Two arms of one branch can be the same LENGTH — so box count is not a witness"
date: "2026-08-21"
section: "Operational Gotchas (durable)"
issues: [25]
---

# Two arms of one branch can be the same LENGTH — so box count is not a witness

Every ch05 scene is gated in-engine by counting A-presses: a scene of the wrong length is a scene
from the wrong place, and that is what caught the Talk recruit pointing at vanilla's 32-box `0x9CC`
for months. Building the Talk's no-Lupin arm broke the technique, and it broke it **silently**.

The locked box 8 (*"A wolf. Him and his whole pack. They're out there now, with travelers."*) is 70
characters against the bubble's 29, so the wrapper pages it in **two**. The substitute is **two
authored boxes**. Both arms therefore render to **21 presses exactly**, and `ch05recruit` — which
asserts 21 — passes on either one. A gate that can only fail when the length changes cannot see a
branch that took the wrong arm, which is the one thing a branch can get wrong.

**The witness is `sActiveMsg` (`src/msg.c`).** `GetStringFromIndex` caches the index it last decoded
(`if (index == sActiveMsg) return sMsgString.buffer1;`), so reading that int names the message on
screen. Two rules for using it:

- **Sample it WHILE A BOX IS UP.** Unit names, menus and item descriptions all decode through the
  same buffer, so by the verdict at the bottom of a scenario it is long overwritten. `ch05recruit`
  latches it on the first `dialogue_wait` of the scene.
- **It names the id, not the prose.** It cannot tell you the text is right — only which id played.
  The prose is the build tests' job; this is the runtime half.

Generalises past this scene: **the box count is a shape check and the message id is an identity
check, and #25 wanted identity all along** ("Assert *which* message id played … not merely that a
scene ran"). Box counts were standing in for identity only because two ids had always differed in
length. Prefer `INSPECT.activeMsg()` for any new dialogue gate.

**POSTSCRIPT, same day: the collision is gone, and the rule stands anyway.** Retiring the
29-character wrap (see the ADR above) gave this scene's every box room to fit in two lines, so
nothing in *it* pages: the two arms are 16 and 17 presses and a count *could* tell them apart
again. That is a happy accident of one scene's arithmetic, not a property anyone should lean
on — the next branch whose arms are the same length brings the blindness straight back, and a
turn long enough to page brings the wrap back into the count. The gate keeps reading
`sActiveMsg`.

_Recorded: 2026-08-21, found while wiring the Talk recruit's fallback (#25)._
