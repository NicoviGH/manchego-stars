---
id: 182
title: "A dead message id is proven by USE, not by an empty body"
date: "2026-08-08"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A dead message id is proven by USE, not by an empty body

Two death-quote ids were owed (Basil, Sahnar) and `PC_DEATH_QUOTE_MSGS` carried a TODO to
auto-allocate them "from a free pool". There is no such pool, and the two obvious audits both give
the wrong answer:

- **"The body is empty"** finds nothing. Every id in FE8's range has vanilla text. A reusable slot
  is one whose *text still exists* but that no code reaches — Lupin's `0x974` is the vanilla line
  "Place the cursor on Vanessa", alive in `texts.txt` and referenced by nothing.
- **"The id appears nowhere in the sources"** finds nothing either, for two separate reasons:
  `include/constants/msg.h` `#define`s **every** id (a declaration, not a use), and a bare-hex
  search for `0x974` collides with unrelated addresses and offsets.

The criterion that works is the one Lupin's comment already stated: no `TEXTSHOW(id)`, `.msg`, or
`.msgId` reaching it, searched over the decomp at `HEAD` with `msg.h` excluded and bare hex ignored.
Run it against `0x974` first — a method that calls Lupin's shipped slot "used" is a broken method.
**Keep the ids explicit in the table rather than auto-allocating**: a floating id would move
`verify_text` baselines under us and break the id-claiming discipline `HOSTED_CHAPTER_MESSAGE_IDS`
depends on. The TODO's premise was wrong; what was missing was the audit, not the automation.
