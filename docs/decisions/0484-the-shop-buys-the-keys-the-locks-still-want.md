---
id: 484
title: "The shop buys the keys a chapter's locks still want, after the arms"
date: "2026-11-27"
section: "Economy"
issues: [711, 764, 693, 510]
---

# The shop buys the keys a chapter's locks still want, after the arms

**Decided (2026-11-27, #711 item 2, #764's fix order: Ch16's (20,1)).** Before a chapter, the
prep step already counts each chests or doors demand's lock tiles against the openers the
fielded bags hold, then takes what is missing from the convoy (`takeKeys`, #699, #711
item 1). What the convoy cannot give either is now returned by `Bot.supply` as `short`
(kind -> lock uses still wanted), and `Bot.shop` buys it. It buys last, after the Vulneraries and
weapons, so a key never takes the gold or the bag slot that arms a unit. Per kind it buys the
cheapest stock item the game says opens that lock for the buyer (`api.stock`'s `opens`,
`Sight.keyOpens`, the read `api.convoy` uses), by the unit with the most room. It buys until the
items' uses cover the want or nothing more can be bought. The record carries `short` beside
`supply` and `buys`.

**Why.** The shop bought only Vulneraries and weapons, so the army's openers were whatever earlier
chapters left. Vanilla Ch16 s4005 (replays `l764e`/`l764f`): two Chest Keys and a Lockpick with
two uses, spent on the (3,9) door and (3,12), against four chests. (20,1) was missed for want of
an opener. The Port Kiris and Bethroen vendors sell the Chest Key (`worldmap_shop_data.c`). A
player short of keys for the chests ahead buys them.

**Proof.** Unit tests (`test_bot.lua` "keys:", "supply: one chest still wants a key") fail
without it. Replay `k711a` (Ch16 s4005 a1-2) against main's `l764f`:

| Attempt | Run | Turns | Deaths | Chests we opened | Not clean for |
|---|---|---|---|---|---|
| 1 | main | 18 | 0 | 3; (20,1) missed | (20,1): no opener |
| 1 | k711a | 21 | 0 | 2: (20,1), (20,3) | the east thief looted (20,5); (3,12) never offered |
| 2 | main | 21 | 2 | 2 | 2 deaths, (20,1) |
| 2 | k711a | 27 | 0 | 4 | the thief stole item 0x65 from Marisa, turn 14 |

The prep bought one Chest Key (for charId 22), the one the count said was short. Both tries opened
(20,1). What spoils them now is thefts: a1's west thief robbed Colm early, so (3,12) was never
offered, and its east thief looted (20,5); a2 lost an item to a thief. Those are #764's thief
items, not this record's.

**Limits.** With no convoy (`HasConvoyAccess` false) `Bot.supply` does not run, so no shortfall
is read and no key is bought. A doors shortfall buys Door Keys only where a shop sells them.
