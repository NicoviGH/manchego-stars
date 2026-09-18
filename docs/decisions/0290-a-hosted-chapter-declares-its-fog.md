---
id: 290
title: "A hosted chapter DECLARES its fog, and that was the last field it could inherit"
date: "2026-09-17"
section: "Operational Gotchas (durable)"
issues: [365]
---

# A hosted chapter DECLARES its fog, and that was the last field it could inherit

A hosted chapter squats a vanilla chapter slot, so every `chapter_settings` field it does not
write, it **keeps** — tuned for a different chapter. Four fields in that class were each fixed
after something went wrong once: goal window/status text ids (#207), the battle ground
(`CHAPTER_BATTLE_TILESETS`), the difficulty triple (#303), and `.traps` (#302, found the day
before it nearly shipped ch06 a pair of vanilla Ch7's ballistae at Ch7's coordinates).

`initialFogLevel` was the fifth and last. `apply_chapter_fog` closes it, and like its siblings
the pass is **total**: it mentions every hosted chapter, so "no injector wrote a line for this
one" stops being a reachable state.

## Why total, and not just a guard on inheritance

Only one chapter was actually inheriting something: ch06 hosts on **slot 7, one of vanilla's
five fogged slots** (`initialFogLevel: 3`; the others are 19, 32, 61, 62 — vanilla uses 0 on
the remaining 74). ch06's design is a route puzzle across concentric water with eight
crossings, so three-tile vision would have hidden the whole map, failed nothing, and shipped.

A guard on inheritance alone would have caught that and stopped there. It would have missed the
other half of the problem, which is **ch04**. ch04 *wants* fog and got it from a literal `3`
inside `inject_ch04` — so the fact that ch04 is a **fogged chapter**, the gimmick the whole
"tone shift to monsters" cadence rests on, was recorded nowhere a reader of ch04 would look. It
is now `fog: 3` in ch04's own YAML, where its rationale already lived in prose.

## The same fact in two vocabularies is not a declaration

ch04 also carried `map.fog_of_war: true`. Nothing read it, and it could not carry the level —
so the chapter declared fog twice, in two spellings, and the number that actually reached the
cartridge came from neither. It is retired in favour of the one top-level `fog:`, the spelling
ch06 already used.

That placement is the chapter's own argument: ch04's header says *"fog is a config flag, not a
map feature"*, which is exactly why it does not belong under `map:` — the same shape as
*"A map's tileset has one home, and it is the one the BUILD reads"*.

## The vocabulary

`fog: none` or `fog: <radius>`. `none` rather than `0` or a blank, so a chapter cannot declare
fog by leaving something empty. The bound is the engine's: `initialFogLevel` is a `u8`
(`chapterdata.h:36`), not a bitfield like the difficulty maluses, and **256 truncates to 0** —
which reads as "no fog" and looks deliberate, so it is refused by name.

Two of the five `none` declarations were not judgement calls at all: ch03 and ch05 had both
already written "no fog" into their prose, ch03 because its grell is *visible at (14,1) from
turn 1, Bazba-style*, and ch05 because *the tension is the escort plus the eruption race*. The
declaration just moves what the chapter already said into the field the build reads.

## What this change is worth: nothing, measured

Every declared value equals what the build already wrote or inherited, so the injected decomp
is **byte-identical** across this change — verified with `tools/injection_fingerprint.py` over
975 files. That is the point. The behaviour is unchanged and the *reachability of a mistake* is
what moved: five chapters that were right by inheritance are now right by declaration, and the
sixth can no longer be wrong in silence.
