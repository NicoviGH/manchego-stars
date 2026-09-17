---
id: 80
title: "Weapon triangle: vanilla FE (Sword > Axe > Lance); damage-type names are flavor"
date: "2026-05-29"
section: "Weapon & Magic Systems"
issues: []
---

# Weapon triangle: vanilla FE (Sword > Axe > Lance); damage-type names are flavor

The triangle is FE-native and driven by weapon TYPE (`src/bmbattle.c sWeaponTriangleRules`):
Sword > Axe > Lance > Sword, +1 ATK / +15 hit. D&D damage-type names (slashing,
bludgeoning, piercing, …) are **cosmetic per-weapon labels** shown in the item info — NOT
a relabeling of the triangle. A "claw" wolf and an axe bandit are both the **axe type** and
read identically on the triangle; the difference is sprite + label only.
_Decided: 2026-05-29 (supersedes the May 2026 "reskin the triangle to Slashing/Bludgeoning/Piercing," which conflicted with FE weapon types)_
