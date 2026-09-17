---
id: 101
title: "The asset table is addressed by a u8, so ch06 RECLAIMS a slot rather than appending"
date: "2026-09-03"
section: "Distribution & Scope"
issues: [26]
---

# The asset table is addressed by a u8, so ch06 RECLAIMS a slot rather than appending

`gChapterDataAssetTable` is reached through **nine `u8` fields** of `struct ROMChapterData` — the
eight `map.*Id`s plus `mapEventDataId` (chapterdata.h; `chapterdata.c`, `bmmap.c` and `bmio.c` are
the only readers and all nine go through those fields). **Index 255 is the last one the engine can
address.** An entry appended past it is written, assembled, linked and shipped, and unreachable.

Vanilla ships 236 entries and ch00-ch05 had appended 19 — **255 exactly.** The campaign had been
sitting on the last addressable slot for a chapter without anyone knowing. ch06 registers four
more (its own tileset's three pieces plus its layout), the prologue's layout follows, and the
table ran to 260.

**Only `-Werror` caught it**, as `chapter_settings.h:993: warning: large integer implicitly
truncated to unsigned type`. Nothing in our own gates would have: every id is DERIVED per build
and written into `chapter_settings.json` by the injector that registered it, so the numbers are
self-consistent right up to the truncation. The ROM would have built clean and ch06 would have
drawn whatever asset lived at `258 & 0xFF`.

**There is no slack in vanilla's own table, and the obvious read says there is.** A first pass
looked at the eight `map.*` fields, found 60 entries no chapter referenced, and concluded the
problem was easy. Every one of those 60 is a **ChapterEventGroup**, reached through
`mapEventDataId` — the ninth field. Counting all nine, vanilla's 236 entries are referenced
**without exception**. A partial read of which fields index a table is worse than no read: it
produces a free list that is entirely wrong and looks authoritative.

So a campaign asset now **claims a slot belonging to a vanilla chapter our ROM can never load.**
Our chapter chain runs ch00 -> ch08 on host slots 1..9 and there is no world map, so a vanilla
chapter at slot 26 or beyond is unreachable and the assets only IT names are dead weight. That is
the same argument that already lets us strip a host slot's event lists, squat its dead message
block, repurpose its unreferenced scripts, and take unnamed `gCharacterData` gaps — this is that
rule reaching the one table where APPENDING was never an option.

The mechanism, in `_claim_asm_table_words`:

* **append while the next index is still below 256**, and only reclaim past it. That is what keeps
  the blast radius to the assets that could not fit at all. Every chapter map registered before
  the ceiling keeps its id exactly; the ONE thing that moves is the prologue's layout, because
  `inject_prologue` runs after `inject_ch06` in `main()` and so is the last to register. Harmless
  -- every id is derived per build and written into `chapter_settings.json` by the injector that
  claimed it -- but "nothing before ch06 moves" would be a slightly false invariant to state;
* the pool is derived from **vanilla's chapter table at HEAD**, never the built tree, so the
  answer does not depend on how far through a build you are;
* everything vanilla slots **0..25** touch is reserved. We host on 1..9, so 26 is a wide margin
  rather than a fitted bound, and it still leaves **118** reclaimable entries — more than ch07,
  ch08 and any tileset they bring can spend several times over;
* a pooled slot counts as free iff its word still equals HEAD's. The decomp is restored from HEAD
  every build, so "already claimed this build" needs no bookkeeping of its own and cannot go stale;
* running out is a **hard error that names the ceiling**, not a silent truncation.

`_register_tileset` stopped returning `base, base+1, base+2` in the same change: past the ceiling
its three pieces land wherever the pool has room, so contiguity was an assumption with no owner.
`_asm_table_word_index` learned to ignore a reclaimed slot's `/* reclaimed: ... */` note, or it
would find every appended asset and miss exactly the reclaimed ones.

**What it picked is the entry's own footnote.** ch06's palette, tile configuration and layout took
indices 118-120 — vanilla's `Ch13EphraimMap`, `Ch13EphraimMapChanges` and `Ch13EphraimEventData`.
ch06's geometry is a retile of Ch13 Ephraim and its deploy tiles are lifted from that group's own
unit table, so the chapter now occupies its donor's runtime slots as well as its shape. The
build-time derivation is untouched: those SYMBOLS still exist in the decomp source, and only the
table's pointers to them moved.

_Decided: 2026-09-03 (Claude, hosting ch06) — flagged to Nicolas as a campaign-wide call._
