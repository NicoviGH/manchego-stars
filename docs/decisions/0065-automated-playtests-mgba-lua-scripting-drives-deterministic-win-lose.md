---
id: 65
title: "Automated playtests: mGBA Lua scripting drives deterministic win/lose checks."
date: "2026-06-09"
section: "Combat System"
issues: []
---

# Automated playtests: mGBA Lua scripting drives deterministic win/lose checks.

`tools/playtest/run.sh win|gameover|retreat|titlecard` runs a scripted ch00 playtest in the mGBA
0.11 nightly (`--script`; auto-downloaded to `tools/emulator/`, gitignored): a Lua
coroutine injects buttons closed-loop against real memory (cursor `gBmSt`, phase/turn
`gPlaySt`, units `gUnitArray*`, menus + game-over via `sProcArray` proc scans, pathing
via the game's own `gBmMapMovement`), with symbol addresses regenerated from the ELF
each run (`gen_symbols.py`). Deaths are engineered by HP-poking units then letting real
combat resolve, so the event engine is exercised end-to-end; verdicts are memory
asserts (chapter index change / game-over proc), not pixels. Exit 0 = PASS; artifacts
(log + milestone screenshots) in `/tmp/playtest-<scenario>/`. Synthetic macOS
keypresses still don't reach mGBA — in-emulator scripting is the supported path.
Art/feel checks stay human (Nicolas).
_Decided: 2026-06-09 (titlecard scenario added 2026-06-09: opens the map-menu Status
screen — which decompresses the title card — and screenshots it, so recomposed titles
get eyeballed without a manual run)_
