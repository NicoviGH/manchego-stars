---
id: 362
title: "A reskin plays as its base class"
date: "2026-10-22"
section: "Art & Audio"
issues: [21, 510]
---

# A reskin plays as its base class

Nicolas, 2026-10-22: every reskinned class has a base class precisely so it is never treated
differently; the reskins are cosmetic and story-driven. A reskin clones its base's
`gClassData` entry into a new class id, so whatever FE8 reads from class DATA follows it.
Two kinds of rule read the class ID instead, and a copy cannot follow them.

- **Effectiveness lists** (`ItemEffectiveness_*`, data_itemuse.c) are lists of class ids.
  They did not name the clones (found reviewing #521). `inject_reskin_effectiveness` now
  lists each clone right after its base on every effectiveness list that names the base,
  written from vanilla HEAD (and data_itemuse.c is restored every build), so a rebuild adds
  nothing. Checked in the ROM's bytes: the Armor list holds 0x8A, the Horse list 0x89 and
  0x8F. What changes in game:
  - Shark Rider (Cavalier): Horse, ArmorAndHorse and the 088ADEB0 list (Horseslayer,
    Halberd, Zanbato, Rapier...).
  - Ironshell (Armor Knight): Armor, ArmorAndHorse (Armorslayer, Hammer, Rapier).
  - Lamia mender (Troubadour): Horse, ArmorAndHorse.
  - Crypt Blade and the kobold blade (Mercenary): Swordsman (Swordslayer).
  - Tentacruel (Bael) and the Lycanroc pack (Mauthe Doog): Monsters, FlierAndMonsters.
  Other class-id data lists are not extended, because a clone never meets them: the
  promotion-item lists (`gItemUseJidList_*`, player promotion) and the Arena's class lists
  (`bmarena.c`, which picks vanilla opponents).
- **Code that tests a class id** (Sure Strike, Pierce, Great Shield, the Bishop's slayer,
  Silencer's exemptions, the Entombed's EXP, Mogall monster-gen, Phantoms, Rogues) cannot
  be extended by data. `inject.reskins.id_switched_classes` reads those ids from the
  gameplay sources at HEAD, and the reskin step refuses a reskin whose base is one of them.
  None is today. Every decomp source and engine patch that tests a class id is classified
  as gameplay or as presentation (battle anims, map sprites and animations, info windows,
  promotion screens), and `test_inject_reskins` fails on one that is neither.

The parity read already modeled a clone as its base (`inject.class_ids.vanilla_class_enum`),
so this makes the ROM match the model; no verdict moves.
