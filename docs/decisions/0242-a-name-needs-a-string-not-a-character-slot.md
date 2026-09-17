---
id: 242
title: "A name needs a STRING, not a character slot"
date: "2026-08-15"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A name needs a STRING, not a character slot

ch05's white moose read **"Monster"** in combat, because a raw-pid gap's `nameTextId` points at
the generic monster message every `0xB0`-range gap shares — so it can never be retitled for one
creature. The reflex was the campaign's usual identity move: pick a collision-free vanilla
character and retitle ITS name message, the way Ravisin rides Riev. The obvious beast donor was
Morva, FE8's own Great Dragon.

**Nicolas stopped that, and the reason generalizes.** The roadmap has two dragons coming —
Arveiaturace in ch10 and the **Chardalyn Dragon** as a ch13–14 marquee boss — and Morva is the
best dragon identity in the game. Spending it on a moose would burn a named future for a string.
Worse, the fix he'd already rejected one step earlier was the same shape: renaming
`ITEM_MONSTER_HELLFANG` to "Antlers" would have cost every future Gwyllgi its weapon name,
because FE8 stores one name message per item id.

**The rule was already settled — for classes, in #90.** `campaign.yaml` says it outright: the
kobolds ride their OWN appended class ids "not a scarce vanilla ballista-empty… so
`CLASS_BLST_KILLER_EMPTY` stays free". The goblins took vanilla's dead ballista-empties; the
kobolds appended. Message ids are the same shape of resource: `gMsgTable[]` is generated from
`texts.txt`, `GetStringFromIndex` has no bounds check and there is no count constant, so a new
trailing header EXTENDS the table. The moose's name is `MSG_D4C`, appended past vanilla's last
id (`MSG_D4B`) and claimed in `HOSTED_CHAPTER_MESSAGE_IDS` like any other id ch05 writes. No
donor spent, and it generalizes: Messie and both dragons get names without paying a slot.

**So a donor slot is for BUSTS, and only for busts.** `RAW_PID_PORTRAITS`'s second element is
now either a donor slot name (Ravisin → Riev, dressed) or an int id we own (the moose, named and
undressed), and `portrait_id` may be None. `dressed_guest_slots` skips name-only units so a PNG
sitting in `portraits/` cannot silently dress a slot — which is exactly how the moose would have
picked up the retired full-body Wyrdeer bust. **An asset on disk is not a decision to ship it.**

**And the weapon was a real defect, spotted off a combat frame.** The moose deploys as
`CLASS_GWYLLGI` but carried `ITEM_MONSTER_ROTTENCLW` — the REVENANT's claw, which is why ch04's
three Revenants hold it: a different creature's gear entirely. The first fix was `HELLFANG`, the
Gwyllgi's own, and it was class-correct but cost too much (see the parity ADR below). It now
carries `FIREFANG` — the Mauthe Doog's, and the Mauthe Doog is this creature's own unpromoted
tier (`data_classes.c`: `CLASS_MAUTHEDOOG.promotion = CLASS_GWYLLGI`). Same beast line, lower
tier: it answers the Revenant problem as fully as HellFang did, at 11.8 threat instead of 24.6.

**The correction worth keeping: "not currently wired" is not "never will be".** Twice in one
session an unused thing was treated as free to consume — an unreferenced item name, then an
unused character slot. The test is not "does anything use this today", it is "can I name a
future that wants it".

_Decided: 2026-08-15 (Nicolas; Claude wired it, #25)._
