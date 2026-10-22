---
id: 360
title: "Tomes carry their FE8 weapon type and sit on the magic triangle"
date: "2026-10-22"
section: "Combat System"
issues: [510]
---

# Tomes carry their FE8 weapon type and sit on the magic triangle

`fe_combat` typed every tome as one `'magic'` kind and left it off the triangle. FE8 has a
second triangle in the same table as the physical one (`sWeaponTriangleRules`, bmbattle.c):
anima > light > dark > anima, +15 hit and +1 Mt to the winner, -15 and -1 to the loser.
Nicolas found it through #519's twin Ch4 finding: vanilla Artur's Lightning against a
Mogall's Evil Eye is light against dark, and the model gave him nothing for it.

- **A weapon's `kind` is its item's `.weaponType`** in data_items.c at HEAD: `anima`,
  `light`, `dark` for tomes (Evil Eye is `ITYPE_DARK`), `monster` for claws and fangs.
  `test_difficulty` checks every modeled weapon against the decomp.
- **`TRIANGLE_RULES` is the decomp's table**, pair for pair; `test_difficulty` parses
  `sWeaponTriangleRules` and compares. `triangle` gives the Mt bonus, `triangle_hit` the hit
  bonus. A pair the table does not list is neutral, as in the engine.
- **`is_magic(kind)`** replaces `kind == 'magic'` wherever a tome resolves against Res
  (`fe_combat.damage`, `difficulty.lord_floor_delta`).

**What it moved** (`make verdict-diff`, all three modes): no verdict. Clear-load
moved by 0.01 in ch03 (all modes), ch05 Normal, ch06 Tutorial and ch07 (all modes).
On the twin's Ch4, Artur now kills a Mogall in 0.92 rounds (was 1.1); a Bonewalker takes
0.86. The strategy check still reads that as a miss, now by 0.06 rounds. What is left is
the Mogalls' Res, which is real: Lightning has no effectiveness against monsters in FE8.
