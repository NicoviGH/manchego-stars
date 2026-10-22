---
id: 361
title: "A class's combat tags are read from the decomp, never kept by hand"
date: "2026-10-22"
section: "Combat System"
issues: [510]
---

# A class's combat tags are read from the decomp, never kept by hand

The audit of #510 steps 3-6 against the decomp found `difficulty.CLASS_TAGS`, a hand-kept
table of eight classes, short of what FE8 does. `IsItemEffectiveAgainst` (bmitem.c) is exact
class-id membership in the item's `ItemEffectiveness_*` list, and the table left the Ranger
and the Troubadour (both on the Horse list, both met by the read) without `cav`, every
female variant without anything, and the Wyvern Lord line, Gargoyles and Mage Knights out.

- **`difficulty.class_tags(class_enum)`** derives the tags from data_itemuse.c at HEAD:
  `armor`, `cav`, `flier`, `monster` are the Armor, Horse, Flier and Monsters lists. A
  weapon's `effective` tags then pick out its own list exactly (a Rapier's `{armor, cav}`
  is ArmorAndHorse); `test_difficulty` checks that over every class for every modeled
  weapon.
- **Two attacker facts the math skipped are now modeled:** `critbonus` (CA_CRITBONUS in
  data_classes.c: Swordmaster, Berserker, the trainees' third tier; +15 crit,
  `ComputeBattleUnitCritRate`) and `slayer` (a Bishop's x3 against a monster,
  `IsUnitEffectiveAgainst`'s hard-coded class ids).

**Scope: vanilla HEAD, not the built ROM.** A reskin is a clone class with a new id
(`campaign.yaml` `enemy_class_reskins`: the Shark Rider on CLASS_CAVALIER, the Ironshell on
CLASS_ARMOR_KNIGHT), and no injector adds a clone to the `ItemEffectiveness_*` lists. The
read maps a clone to its base class (`inject.class_ids.vanilla_class_enum`), so it tags a
Shark Rider `cav`, while in game a Horseslayer does x1 against it. Open on #510: put clones
on their base class's lists, or read them as the ROM does.

**What it moved:** nothing (`make verdict-diff`, all three modes). No modeled effective
weapon meets a Ranger or Troubadour in ch00-ch07, and no crit-bonus class or Bishop fights
there yet. It is a guard for the chapters after ch07.

The rest of the audit matched the decomp: every modeled weapon's Mt, hit, crit, weight,
range and effectiveness (data_items.c), the stat formulas of `ComputeBattleUnitStats`, and
`ai_target`'s port of `AiComputeCombatScore` term by term, including a target that cannot
counter keeping its weapon type for the triangle (`SetBattleUnitWeapon`). What is still not
modeled is on #510.
