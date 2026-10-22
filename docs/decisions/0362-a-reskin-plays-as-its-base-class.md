---
id: 362
title: "A reskin plays as its base class, on every list that names it"
date: "2026-10-22"
section: "Art & Audio"
issues: [21, 510]
---

# A reskin plays as its base class, on every list that names it

Nicolas, 2026-10-22: every reskinned class has a base class precisely so it is never treated
differently; the reskins are cosmetic and story-driven. A reskin clones its base's
`gClassData` entry into a new class id, so whatever FE8 reads from class DATA follows it.
Two kinds of rule read the class ID instead, and a copy cannot follow them.

- **Effectiveness lists** (`ItemEffectiveness_*`, data_itemuse.c) are lists of class ids.
  They did not name the clones, so in the built ROM a Horseslayer did x1 to a Shark Rider
  and an Armorslayer or Hammer did x1 to an Ironshell (found reviewing #521).
  `inject_reskin_effectiveness` now lists each clone right after its base, on every list
  that names the base. Checked in the ROM's bytes: the Armor list holds 0x8A, the Horse
  list 0x89 and 0x8F.
- **Code that switches on a class id** (Sure Strike, Pierce, Great Shield, the Bishop's
  slayer, Silencer's exemptions, the Entombed's EXP, Mogall monster-gen, Phantoms, Rogues,
  Dancers, Manaketes) cannot be extended by data. `inject.reskins.id_switched_classes`
  reads those ids from the gameplay sources at HEAD, and the reskin step refuses a reskin
  whose base is one of them. None is today.

The parity read already modeled a clone as its base (`inject.class_ids.vanilla_class_enum`),
so this makes the ROM match the model; no verdict moves.
