---
id: 333
title: "Custom sound effects append to gSongTable, and ch06's Messie cries with Kyogre's voice"
date: "2026-10-09"
section: "Art & Audio"
issues: [26]
---

# Custom sound effects append to gSongTable, and ch06's Messie cries with Kyogre's voice

ADR 0133 keeps the vanilla FE8 soundtrack for MVP. A **sound effect** is a separate question, and
Nicolas answered it for ch06 (2026-10-09): Messie surfaces the way Kyogre wakes in Pokemon
Sapphire's Cave of Origin, and he cries with Kyogre's cry.

**Why it is cheap.** FE8 and the GBA Pokemon games run the same m4a (MP2K) sound engine, so a cry
from `pret/pokeemerald` (`sound/direct_sound_samples/cries/kyogre.wav`: mono, 8-bit, 10512 Hz,
1.68s) is already in the format FE8 plays. `tools/wav_to_aif.py` turns it into the AIFF the
decomp's `aif2pcm` rule eats; nothing is resampled.

**How a sound is added** (`tools/inject/sounds.py`, one row in `CAMPAIGN_SOUNDS`). Four appended
pieces, none of which edits a vanilla row: the sample copied into `sound/direct_sound_samples/`,
its `DirectSoundData_*` label plus a one-voice voicegroup and a one-note song appended to
`direct_sound_data.s`, a row appended to `gSongTable` (so the first campaign id is `0x3E8`, the
vanilla table's length), and a `SONG_MS_*` name in `songs.h`. Everything rides objects the
linker script already lists, so no new object needs placing. The voice sits at base key 60 and
the song plays Cn3, so the sample sounds at its recorded rate. It plays on player 6, where
vanilla's monster cries sit, so it neither stops the chapter's music nor gets cut by a menu blip.

**Staging** (`ch06_messie_block`), in Sapphire's order (pokeruby `CaveOfOrigin_B4F`): the music
ducks, the ice cracks under a map shake with its rumble, the rumble ENDS (EARTHQUAKE_END fades
the SE channel, and ch05's moose showed a rumble and a cry cannot overlap), Messie surfaces in
open water and hauls himself two tiles onto Nerra's tile at a quarter of walking speed, a held
second, the cry, then the scene. His route is checked against the Gwyllgi's own movement-cost
row at build time, because an unwalkable event MOVE hangs the chapter.

| Element | Source |
|---|---|
| The cry | Game Freak, Pokemon Ruby/Sapphire/Emerald, via `pret/pokeemerald` |
| The staging order | `pret/pokeruby`, `data/maps/CaveOfOrigin_B4F/scripts.inc` |
