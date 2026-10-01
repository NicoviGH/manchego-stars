---
id: 306
title: "A new message is a name; the build numbers it past vanilla's table"
date: "2026-10-01"
section: "Operational Gotchas (durable)"
issues: [411]
---

# A new message is a name; the build numbers it past vanilla's table

Every hosted chapter picked literal message ids out of a dead vanilla block
(`HOSTED_CHAPTER_MESSAGE_BLOCKS`). ch05 spent all 18 of `0x9E4`–`0x9F5`, so its next scene meant
another sweep of the neighbourhood for dead ids (ADR 0183) or a new range from the never-shipped
pool. A chapter now names the messages it needs in `inject/message_alloc.py` `APPENDED_MESSAGES`,
and the build numbers them. This is pokeemerald's `map_event_ids.h` move.

- **Ids are appended past `MSG_D4B`.** `gMsgTable[]` is generated from `texts.txt` and sizes
  itself to it, so the table has no budget to run out of. ADR 0242 already appended the moose's
  name this way. The allocator generalises it.
- **The ledger decides the numbering.** Chapters allocate in campaign order, each as one
  contiguous run in the order it lists its names. A message added to ch05 renumbers ch06's. That
  is safe because nothing outside the build names an appended id. Read one through
  `appended_message_id(chapter, name)` and never write the number down.
- **One step reserves every header** (`reserve_appended_messages`, right after the vanilla
  restore), so any later pass can write any allocated id in any order. Before this, each writer
  appended its own header with `set_message_body(create=True)`, and two writers had to run in id
  order. ch06's boats once tried to append `0xD4D` before ch05's moose had `0xD4C`, and a
  `ch05-messages` step fact existed only to pin that order. Both are gone. `set_message_body`
  now always fails on a missing header.
- **Allocated ids are claimed automatically.** `HOSTED_CHAPTER_MESSAGE_IDS` folds them in, so
  `assert_message_ids_unique` and `make chapter` see them without anyone copying them out.
- **Shipped block ids stay put.** Moving a vanilla-range id would change the ROM for no gain.
  The blocks now hold only what already shipped, and none needs to grow. `make chapter` no
  longer reports a full block as a loose end.
- **`verify_text` sweeps the real table.** It read only vanilla's `0xD4C` ids, so it had never
  decoded an appended message. It now reads `MSG_COUNT` from the build's generated
  `include/constants/msg.h`: 3407 messages, 0 runaway.

Gate: `injection_fingerprint` on the default configuration, IDENTICAL (975 files). The moose
and the boats still land at `0xD4C`/`0xD4D`/`0xD4E`, and a test pins that. The change runs the
same way under every flag, so the other configurations add nothing (#424).
