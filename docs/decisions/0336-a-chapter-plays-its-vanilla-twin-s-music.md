---
id: 336
title: "A chapter plays its vanilla twin's music"
date: "2026-10-09"
section: "Art & Audio"
issues: [26]
---

# A chapter plays its vanilla twin's music

Nicolas, 2026-10-09, choosing ch06's hall music: "let's go with vanilla's music, and apply that
rule across the chapters." The twin is the chapter's `parity_reference`, the same vanilla
chapter its force is measured against.

**Map music** is the twin's whole `bgm` block (player, enemy and green phase, plus the
alternates), written by `apply_chapter_music`: a total pass beside fog and difficulty, read from
the vanilla decomp. Before it, no pass wrote the field, so every hosted chapter played its HOST
slot's music. That was right by accident for ch05 and ch06, which sit on their twins' own rows,
and wrong for ch04 (on Ch5x's row: Follow Me where vanilla Ch4 plays Distant Roads) and the
prologue's green phase (Ch1's). The twin's row comes from the decomp's chapter enum, never from
its number: row 5 is Ch5x, so from Ch5 on chapter N is row N+1, and a number guess put ch05 on
Ch5x's music in this change's first draft. `chapter_bgm(chap)` is the one lookup; anything that
names "the chapter's theme" (ch06's Messie scene) reads it.

**Scene music** follows the twin's cues beat for beat where our beat has a vanilla
counterpart: the same song for the same kind of moment (the opening backdrop scene, the enemy's
first appearance on the map, the victory sting, the closing reflection). ch06's opening is the
first: Solve the Riddle over the hall, silence as it ends, Raid! as the merfolk surface. A beat
with no vanilla counterpart keeps the staging Nicolas set for it (Messie's silent entrance).

ch00-ch05 follow it beat for beat (#26); the twin's cue sits beside each beat in the
injectors, tagged ADR 0336. Two placement rules came out of that pass:

- **A cue on a player-phase event is scoped with `MUSS`/`MURE(0x2)`.** Vanilla's turn-1 cues
  mostly fire on the enemy or green phase, where `MUSC` lasts only that phase; on ours it
  would play through the player's whole turn. Two cues in one event take two pairs: a second
  `MUSS` saves the first cue as the song `MURE` restores (`OverrideBgm`, soundwrapper.c).
- **A beat that happens behind Preparations moves to the nearest beat the player hears.**
  Our enemies LOAD on a black screen before prep, so ch02's Defense rides its turn-1 scene and
  ch03's Shadow of the Enemy rides the cut to the mine. Vanilla's closing Distant Roads in Ch4
  and Ch5 needs no cue where the map theme is already Distant Roads.

Ch4's mid-map Laughter has a beat of ours (Lupin's pack bursting from the fog) and Nicolas
kept Tension there: a menace reveal outranks the twin's song. The unnamed ids the twins use
are named in `sound/song_table.s`: 0x4A is night ambience (`y_yoru_3`), 0x52 forest ambience
(`y_mori_3`), 0x54 a second Comrades. None of the three is in the Sound Room.

A twin past the route split has no row yet: `twin_settings_index` refuses it, so the first
such chapter has to name its row and does not inherit a guess.
_Decided: 2026-10-09 (Nicolas)._
