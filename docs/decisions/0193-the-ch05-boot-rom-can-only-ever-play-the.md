---
id: 193
title: "The `--ch05-boot` ROM can only ever play the NO-Lupin arm"
date: "2026-08-13"
section: "Operational Gotchas (durable)"
issues: [25]
---

# The `--ch05-boot` ROM can only ever play the NO-Lupin arm

Built at ch05 scene 4, the first scene with a `no_lupin_fallback`. Recorded here because it is the
trap that would make the owed four-state proof **vacuous**: a scenario that always walks one arm
passes just as green as one that walks the right arm.

`CH05_BEGINNING_SCRIPT` asks `CHECK_ALIVE` **before `LOMA`** — that is forced, because scene 4 is a
pre-map backdrop scene and its channel is inherited (see "A cutscene's CHANNEL is inherited"). The
`--ch05-boot` party seed (`MS_Ch05BootSeed`) is `LOAD1`ed **after** `LOMA`, several lines further
down, because its whole job is to give PREP a party from a COLD New Game. So at the instant the
branch runs on a boot ROM, `gUnitArrayBlue` holds nothing, `GetUnitFromCharId` returns NULL, slot C
is 0, and the fallback plays — **every time, for every unit, no matter what the seed contains.**
Filmed and confirmed 2026-08-13: `recordch05opening` on `ch05boot` opens scene 4 on Pinky's *"The
tracks stop here, Father"*, never Lupin's *"The trail leads here"*.

So: **the boot ROMs prove the fallback arm and are structurally blind to the other three states.**
Proving "recruited, alive, deployed" and "recruited, alive, BENCHED" needs the REAL chain
(ch04 → ch05) where `ReadGameSave` has filled `gUnitArrayBlue` before the chapter's events run.
Do not "fix" this by moving the seed load above the branch — it sits after `LOMA` because `LOMA`
rebuilds the map, and units loaded before it are placed on the outgoing one.

**The placement itself is vanilla's, and was checked rather than assumed.** `EventScr_Ch7_Beginning`
`Scene` branches its own opening dialogue on `CHECK_ALIVE(CHARACTER_FRANZ)`, then `GILLIAM`,
`MOULDER` and `VANESSA` — four optional units, asked inside a beginning scene. Asking that early is
a thing vanilla does. (Vanilla asks after its ally `LOAD3` rather than before, which is exactly why
the boot-ROM blindness above is a real difference and not a quibble.)
