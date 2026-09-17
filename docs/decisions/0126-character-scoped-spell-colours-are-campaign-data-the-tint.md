---
id: 126
title: "Character-scoped spell colours are campaign data; the tint rides a dedicated overlay global (#165, #168)"
date: "2026-07-15"
section: "Art & Audio"
issues: [165, 168]
---

# Character-scoped spell colours are campaign data; the tint rides a dedicated overlay global (#165, #168)

Marty's `battle_anim.spell_palette_tint` declares a character + weapon-type match in YAML, so one
row covers every Dark tome he can wield without naming Marty in engine code or changing the tome's
mechanics. The generated table (`gBanimSpellPaletteTints`) is immutable ROM data. At spell dispatch,
`StartSpellAnimation` records the matching tint id in `gMSSpellTint` — a dedicated
`EWRAM_OVERLAY(banim) u8` declared beside `gEfxSpellAnimExists` in `banim-ekrbattle.c` (the enum is
honest: `BANIM_SPELL_TINT_NONE = 0`, `BANIM_SPELL_TINT_GREEN = 1`). Palette registration reads
`gMSSpellTint` and recolours saturated BG/OBJ colours while retaining neutral greys; teardown
(`EkrEfxStatusClear`) clears it alongside the vanilla `gEfxSpellAnimExists` reset.

The durable lesson: a caster-scoped tint gets its **own** overlay-banim global declared beside
`gEfxSpellAnimExists` — do **not** overload the spell-lifecycle flag. A global's storage is decided
by the compilation unit it lives in, not the abstract `EWRAM_*` macro: declared inside an unrelated
TU the linker placed it in ROM (read-only, silently ignored writes), but declared beside the proven
`EWRAM_OVERLAY(banim)` siblings in `banim-ekrbattle.c` it links writable. Overloading
`gEfxSpellAnimExists` (the earlier shipped form) worked only because every vanilla reader compared
`== 0`/`false`, an unenforced invariant that any future `= true`/`== 1` would silently break; the
dedicated global removes that landmine. The TESTCH `recordanim` capture is the visual gate; Marty
renders green Flux in mGBA while the table stays character- and `ITYPE_DARK`-scoped.
_Decided: 2026-07-15 (#165 shipped the feature; #168 replaced the `gEfxSpellAnimExists` overload with
the dedicated `gMSSpellTint` global, gated on the in-engine Marty capture)_
