---
id: 183
title: "A host block is not the whole id budget — sweep the neighbourhood"
date: "2026-08-13"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A host block is not the whole id budget — sweep the neighbourhood

Counted while moving the Basil→Sahnar Talk off vanilla's `0x9CC` into ch05's own block, because
the placeholder pattern above has a bill and it comes due here.

ch05 hosts on slot 6, so its block is vanilla **Ch6's** `0x9E4`–`0x9F5` — 18 ids. Seven are spent
(the eruption warning, Ravisin's death quote, the two arena tutorial boxes, the two goal strings,
the Talk), leaving **eleven**. Eleven scenes are still owed: the opening's seven, both endings,
Basil's chapter-specific death quote, and Ravisin's battle taunt — which is wired *nowhere*
(`gBattleTalkList` carries a ch01 row for Izobai and none for her). Read off the block alone that
is exactly zero slack, and the `no_lupin_fallback:` branches would have nowhere to go.

**The block is not the budget.** Sweeping `0x9C6`–`0x9E3` against the post-injection tree by the
`USE` criterion (`decisions.md` → "A dead message id is proven by USE") finds **six** more free
ids: `0x9C9` `0x9CA` `0x9CB` `0x9CC` `0x9D1` `0x9D2`. Vanilla Ch5's two endings, its coda and its
Talk are reachable only from `ch5-eventscript.h`, which `inject_ch04` rewrites — the same shape
that made `0x9CD`–`0x9D0` safe for the reliquary lines. **Seventeen ids against sixteen owed.**

Two things the sweep has to be run correctly to see, both easy to get wrong:

- **Sweep the POST-INJECTION tree, not `HEAD`.** At `HEAD` all four of `0x9C9`–`0x9CC` are live in
  `ch5-eventscript.h`; after `inject_ch04` rewrites that file, none of them is. The tree that
  ships is the one that answers the question.
- **Validate the sweep against a known-LIVE id before trusting a "free" verdict.** A regex that
  misses `TEXTSHOW`/`Text_BG`/`.msg` in any of their spellings reports everything free. Run it
  against `0x9E4` and `0x9CD` first and require them to come back USED.

`0x9C6`/`0x9C7`/`0x9C8` come back **USED** and that is correct — they are live rows in
`data_battlequotes.c` keyed to `CHAPTER_L_5`, ch04's host slot. Do not talk yourself past them on
the grounds that ch04 fields neither Natasha nor Saar: that is an argument about our roster, which
can change, not about our wiring.

**A `no_lupin_fallback:` costs ONE extra id, not four.** The branch mechanism is already built and
ch04 uses it: `variant_beat()` splices the substitute boxes over the locked beat, the whole variant
scene is written to a **second** message id, and `branch_on_flag()` picks between the two at
runtime — so a branched scene is 2 ids rather than 1. Splitting a scene into prefix/arm/arm/suffix
around the differing box would cost four, and is the wrong instinct: duplicating the text is free,
ids are what is scarce. Note `variant_beat` reads `boxes:`/`replaces:` as **lists** while ch05's
blocks are authored with singular `box:`/`replaces:` — normalize the YAML, do not write a
second mechanism.

⚠️ **The "ids are what is scarce" half of that is retired** (2026-08-15, and again on the ch05
endings 2026-08-19). `gMsgTable[]` self-sizes, and a split scene costs SEAMS — see "A conditional
block inside a scene is a WHOLE second copy" below. The 2-ids-per-branched-scene shape is still
right; the reason given for it was not.
