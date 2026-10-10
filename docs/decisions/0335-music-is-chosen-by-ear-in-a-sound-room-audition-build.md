---
id: 335
title: "Music is chosen by ear, in a Sound Room audition build"
date: "2026-10-09"
section: "Art & Audio"
issues: [26]
---

# Music is chosen by ear, in a Sound Room audition build

Choosing a scene's music means hearing the candidates, and none of our tools could play one:
`sfx_preview` renders samples, not songs, and the playtest harness buzzes under audio sync
(`tools/playtest/run.sh`, beside `PT_SOUND`). FE8 already ships a player: Extras -> Sound Room,
always enabled, with every track named. It lists only songs the save has heard, though, and
nothing without a verified save.

`make CAMPAIGN=rime-of-the-frostmaiden SOUNDROOM=1 fireemblem8.gba` applies the optional
engine patch `sound-room-audition`, which lists every entry, secret ones included, whatever the
save says. Open the ROM in plain mGBA, go to Extras -> Sound Room, and play. It is a DEBUG build:
`src/soundroom.c` is on the restore-every-build list, so the next plain `make` is vanilla there.

First use: the Speaker's hall in ch06's opening, where the candidates are Distant Roads (entry
9), Laughter (42), Lights in the Dark (49), Comrades (50) and Bonds (57), against today's
Tension (37).
_Decided: 2026-10-09 (Nicolas: he has to hear the candidates before choosing)._
