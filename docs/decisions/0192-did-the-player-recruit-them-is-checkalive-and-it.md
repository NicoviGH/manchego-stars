---
id: 192
title: "\"Did the player recruit them?\" is `CHECK_ALIVE`, and it needs no flag"
date: "2026-08-13"
section: "Operational Gotchas (durable)"
issues: [25]
---

# "Did the player recruit them?" is `CHECK_ALIVE`, and it needs no flag

ch05's `no_lupin_fallback:` arms need to know whether ch04's optional parley happened — three of
them today; the two ENDINGS were unbranched 2026-08-19, see below. Two
answers were proposed here before anyone read the decomp — carry a persistent flag out of ch04, or
test whether Lupin is standing on the ch05 field — and **both are wrong**. Vanilla has shipped the
answer since 2005.

`CHECK_ALIVE(pid)` (`EvtCheckUnitNotDead`, `EVSUBCMD_CHECK_ALIVE`) leaves `1`/`0` in `EVT_SLOT_C`,
and `BEQ(label, EVT_SLOT_C, EVT_SLOT_0)` jumps to the absent arm on `0`. `eventscr.c` is explicit
about what `0` means: **the unit was not found at all, OR it carries `US_DEAD`.** Never recruited
and recruited-then-killed collapse into one arm — and that is the behaviour we want, not a wart to
work around. A dead Lupin should no more be described as "out there now, with travelers" than one
who was never won.

**The precedent is our own scene's ancestor.** `ch14a-eventscript.h` branches its ending on
`CHECK_ALIVE(CHARACTER_JOSHUA)` three separate times — Joshua being vanilla Ch5's optional Talk
recruit, and Sahnar's exact donor. Vanilla re-checks inline at each branch point rather than
caching a result, so the idiom is cheap and repeatable.

**Why the field test would have been actively wrong here:** ch05 deploys **9 of a 10-unit pool**,
so Lupin can be recruited, alive, and simply benched — and a field-presence test sends that player
down the no-Lupin arm, having earned the wolf. `CHECK_ALIVE` reads the ROSTER, not the map, so it
gets the benched case right. FE8 draws this distinction itself: `EVSUBCMD_CHECK_DEPLOYED` is a
separate subcommand, and vanilla uses ALIVE for dialogue branches and DEPLOYED for map logic.

**And no flag is involved**, so the open question about whether `EVFLAG_TMP(9)` survives a chapter
boundary is moot rather than unanswered — we never needed it to.

Reuse, don't add a mechanism: `branch_on_flag()` already emits this exact skeleton
(`CHECK_EVENTID` → `BEQ` → arm → `GOTO`/`LABEL`), and `convert_survivors_green()` already emits
`CHECK_ALIVE` in ch04's pack parley, so the macro is proven in our build. The sibling is the same
function with the check swapped.
