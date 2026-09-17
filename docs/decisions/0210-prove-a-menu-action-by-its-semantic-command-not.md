---
id: 210
title: "Prove a menu action by its SEMANTIC command, not by resemblance"
date: "2026-08-11"
section: "Operational Gotchas (durable)"
issues: [25]
---

# Prove a menu action by its SEMANTIC command, not by resemblance

The Arena's accepted flow was "proved" by the sprite looking right and by `CH05_*` names being
present in the source. Neither is proof. The action menu's Arena id is `0x62`; the accepted flow
reaches inline `gProcScr_TalkChoice`, mutates gold, and generates an opponent in `gArenaState` —
those are the things that distinguish "the Arena ran" from "something that looks like the Arena
is on screen".

The same rule one level up: a live-wiring test must inspect the GENERATED builder output and the
`inject_ch05` consumer, not grep the repo for a constant's name. A name proves an author's
intent; only the generated artifact proves the wiring.

_Recorded: 2026-08-11 (migrated out of HANDOFF 2026-08-20)._
