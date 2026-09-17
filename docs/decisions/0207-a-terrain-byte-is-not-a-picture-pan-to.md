---
id: 207
title: "A terrain byte is not a picture: pan to the thing before you shoot"
date: "2026-08-14"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A terrain byte is not a picture: pan to the thing before you shoot

`ch05raid` asserted the desecrated tile read `0x25` and PASSED, while the screenshot it shipped
showed the wrong side of the map — the camera sits wherever the fight is, not wherever the
assertion is. A proof that reads memory and a proof that shows a picture are two different
proofs, and only one of them is what a human reviews.

Pan to the subject, `wait()` for the scroll to settle, and only then shoot. The frame now carries
the engine's own tile panel reading "Ruins", which is the engine agreeing with the byte rather
than a byte agreeing with itself.

_Recorded: 2026-08-14 (migrated out of HANDOFF 2026-08-20)._
