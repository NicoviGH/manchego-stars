---
id: 176
title: "Generated art is CONVERTED by the injector, never left for make"
date: "2026-08-07"
section: "Operational Gotchas (durable)"
issues: [245]
---

# Generated art is CONVERTED by the injector, never left for make

**GNU Make 3.81 — what Apple ships and what this repo builds with — drops the incbin
dependency**, so an injector must run the `gbagfx` conversions itself and drop the consuming
`.o`. It must not delete the intermediates and trust make to re-derive them.

The chain that fails: `data/data_chap_title.o` reaches its `.4bpp.lz` files through
`$$(data_dep)`, a `$(shell scaninc …)` target-specific variable resolved by `.SECONDEXPANSION`,
which 3.81 does not handle. Verified directly — with the `.lz` deleted, `make -n fireemblem8.gba`
plans **no** rule that rebuilds it.

Two consequences, and the quiet one is worse:

1. When `data_chap_title.o` needs reassembling, the build dies on `Error: file not found:
   graphics/chap_title/chap_title_N.4bpp.lz`.
2. When it does not — the common case, since its `.s` never changes — **the build succeeds and
   the ROM silently keeps the previous card.** A retitled chapter simply never lands.

This is the real root cause of **#245**, which was filed as "the `TESTCH` build race". It is not a
race and it is not `TESTCH`'s: it looked intermittent only because whether it fires depends on
whether the file survived an earlier build. `_write_chapter_title_card` now converts and drops the
`.o`, and the gate went from a standing `BLOCKED` to 15/15.

**The general rule: if an injector generates art, it owns the conversion.** Deleting an
intermediate is not a way to ask make for anything on this toolchain.

Both title-card sites are fixed — `inject_prologue` had an inline copy of
`_write_chapter_title_card` carrying the same bug, and now calls the helper. **Three more sites
have the same delete-and-hope shape and are NOT verified**, all in the montage path, which is why
they are named here rather than quietly assumed fine: the opening subtitle cards
(`.feimg2`/`.fetsa2`), `MontageMural.4bpp{,.lz}`, and the drawn world-map `.lz` copies. They may be
harmless if their consuming `.s` changes on every build (which would force the reassemble this bug
needs) — that is exactly what someone should check before trusting them.
