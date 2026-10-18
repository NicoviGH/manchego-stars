---
id: 352
title: "A chapter names its generics, on a pid of its own"
date: "2026-10-18"
section: "Distribution & Scope"
issues: [493]
---

# A chapter names its generics, on a pid of its own

The map hover box and the unit window print a unit's pid name (`pCharacterData->nameTextId`,
`player_interface.c:872`, `unitinfowindow.c:165`), never its class. Vanilla gives each faction one
name of its own: Soldier, Bandit, Remnant, Monster. Our generics borrowed vanilla's pids, so they
carried vanilla's labels: goblins, merfolk, the undead of the Elven Tomb and Bremen's townsfolk all
read **Soldier**, ch02's raiders **Cutthroat**. R on the name read the donor row's description: "The
army of Grado" under a goblin.

**Each chapter's YAML names its generics** (`generic_name:`, at most 12 characters) **and writes
what R on that name reads** (`generic_help:`, two lines in the help box). Nicolas chose the names on
2026-10-18: Mercenary (ch00), Goblin, Raider, Kobold, Risen, Merfolk, Militia (ch07). **ch04 keeps
vanilla's Monster**, as vanilla's own monsters share it, so it keeps its shared monster pids.

A name is one global row per pid (ADR 0098), so a chapter that names its generics takes a pid of
its own: `chapter_ids.GENERIC_PIDS`, from 0x92–0xa6, vanilla's unused "Enemy" rows (no unit
definition and no `CHARACTER_` constant places them). **The build clones the vanilla generic each
pid replaced into it** (`GENERIC_PID_DONORS`, `inject.raw_pids.clone_generic_rows`), so only the
name and the description change. Autolevel reads class growths (`bmunit.c:778`) and every clone
keeps its donor's baseLevel 1, so the move changes no stat; `make difficulty-gate` holds at parity.

The prologue's guards join the shared pid table (`CHAPTER_ENEMY_PIDS['ch00']`, one pid per body),
which retires the prologue's own pid function. A new chapter adds its pid, its donor and its two
YAML lines; `ch02generichelp` proves R on a Raider's name in game, through the `help:` step any
chapter can declare.

The help lines follow vanilla's shape, an allegiance and one fact about where the faction stands
("A member of Bazba's Bandits, who roam this region"; "A knight of Frelia, sworn in service of
Hayden"), and say only what our own story tells the player: ch03's are the wild kobolds that broke
from Trex's warren, never the warren itself. A line covers every generic in its chapter, so a
roster entry must fit it: ch07's fishers and sellswords are re-dressed as the Speaker's dock and
hired guards (stats, kit and tiles unchanged).

_Decided: 2026-10-18 (Nicolas: the names, Monster for ch04, the help lines and ch07's renames;
Claude: the pid move)._
