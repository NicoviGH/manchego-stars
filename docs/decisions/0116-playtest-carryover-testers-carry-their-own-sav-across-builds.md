---
id: 116
title: "Playtest carryover: testers carry their own `.sav` across builds; a per-release starter save is the fallback"
date: "2026-06-20"
section: "Distribution & Scope"
issues: [59]
---

# Playtest carryover: testers carry their own `.sav` across builds; a per-release starter save is the fallback

FE8 validates a save by a **fixed** magic (`SAVEMAGIC32`/`SAVEMAGIC16`) + a checksum over the save
block (`fireemblem8u/src/bmsave-lib.c`, `ReadGlobalSaveInfo`/`ReadSaveBlockInfo`); `EraseSramDataIfInvalid`
wipes anything that fails on boot. Those magics are compile-time constants, so a **rebuild alone never
invalidates a save** — the only thing that can is the save-block *layout* shifting, which moves the old
bytes to wrong offsets and fails the checksum. Manchego Stars reskins **within FE8's fixed chapter/
character slots** and never touches the save structs, the array dims that size `struct GameSaveBlock`
(`BWL_ARRAY_NUM` roster, `WIN_ARRAY_NUM` chapters), or the magics — so the layout is stable across our
drops and an old `.sav` stays valid. Default is therefore **carry-forward**: testers keep their battery
`.sav` (in-game Save — **not** emulator save-*states*, which are ROM-version-specific and break every
build) and move it onto the new build; per-emulator steps (Pizza Boy / Delta) live in
`docs/playtesters.md`. `tools/check.py check_save_layout_stable` pins those constants and fails the
build if a future submodule bump ever shifts the layout — **that** drop, and only that, gets a
per-release starter `.sav` (the fallback) plus a save-version note. Build/dist stamps the private
`.gba`: `tools/build.sh dist` (#37).
_Decided: 2026-06-20 (revises the 2026-06-19 starter-save-first call from #59 after verifying the layout is stable)_

---
