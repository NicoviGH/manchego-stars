---
id: 177
title: "Vanilla prose is a legitimate PLACEHOLDER; vanilla wiring is not"
date: "2026-08-07"
section: "Operational Gotchas (durable)"
issues: [25]
---

# Vanilla prose is a legitimate PLACEHOLDER; vanilla wiring is not

**A chapter is wired end-to-end first, and only its PROSE waits for the dialogue pass** (Nicolas).
ch05's four reliquary visits point at vanilla Ch5's own message ids (`0x9CD`–`0x9D0`) and we never
*write* them, so the ROM keeps vanilla's text, the ids stay unclaimed in
`HOSTED_CHAPTER_MESSAGE_IDS`, and the dialogue pass later writes our body **at the same id** — one
line per site, not a rewire. ch05's authored dialogue skips that range exactly (`0x9BE`–`0x9CC`,
then `0x9D5`), so nothing collides.

What is *not* placeholder is everything else, and that is the point: the `SVAL(EVT_SLOT_3, <item>)`
+ `GIVEITEMTO` half is the real wiring, already gated by `assert_village_gifts_match_vanilla`, so
the rewards are obtainable and correct now rather than twice. **Shops are not placeholders at all**
— `Armory`/`Vendor` take their stock directly and run no script and show no text, so listing the
tile finishes them.

The alternative — leaving the `Location` list empty until the prose lands — is what shipped ch04's
unreachable Iron Axe and left ch05 with four villages, an armory and a vendor sitting on intact
tiles that nothing pointed at. A finished-looking map with unobtainable rewards is the failure
mode; borrowed prose is not.
