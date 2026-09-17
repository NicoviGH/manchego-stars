---
id: 118
title: "Faked battle anims: per-CHARACTER (`_u25`), not per-class clones (#65 M-A → M-B)"
date: "2026-06-26"
section: "Art & Audio"
issues: [65]
---

# Faked battle anims: per-CHARACTER (`_u25`), not per-class clones (#65 M-A → M-B)

Milestone A (RBG) gave a unit its custom anim by cloning a stat-identical **class** (`clone_into`)
and repointing the clone's `AnimConf`. That does **not scale**: FE8 has only ~3 unused class slots
(`CLASS_BLST_*_EMPTY`), and the goblin map-sprite reskins (#21) already take two. So M-B moves the
PCs to FE8's dormant **per-character** path: an engine hook (`_patch_banim_character_unique`, in
`engine_hooks.py`) swaps the four combat anim lookups in `banim-ekrbattleintro.c` from
`GetBattleAnimationId` → `GetBattleAnimationId_WithUnique`, which reads `pCharacterData->_u25` →
`gUnitSpecificBanimConfigs[]`. Per PC, `inject_battle_anims` appends the unit's `AnimConf` to that
table and sets the character's `_u25` index; **no class slot, ever** — the unit deploys as its plain
vanilla class. Scales to all 8 PCs + any **named boss** (anything with a unique character id).
- **Generic enemies stay class-bound.** A horde of goblins shares one character id (0), so `_u25`
  can't address them; their custom asset is a class-bound **map sprite** anyway. A goblin *battle*
  anim (#90) would attach as a class-level `.pBattleAnimDef` on their existing reskin clone class.
- **RBG migrated** off its clone (freed `CLASS_BLST_KILLER_EMPTY`). Pure text transforms are TDD'd
  (`test_build_campaign.CharacterUniqueBanim`); the hook is guarded by `check_engine_guards_present`.
- **Melee cadence** is studied per donor from the decomp (`ref_to_battleframe._melee_mode_body`,
  from the vanilla Pirate axe `motion.s`): lunge-in, wind-up held longest, `hit_normal` on the
  swing-through, backward dodge, no projectile. FE frames built by `tools/descale_battleframe.py`
  (flip → uniform scale → shared feet anchor → sharpen → curated family palette → 1px outline).
- Verified in-engine (TESTCH sandbox `recordanim`): **braulo** (deploys Pirate 0x42) and **RBG**
  (deploys Archer 0x19) both animate custom via `_u25`; braulo's 96-tile sprite fits VRAM.
_Decided: 2026-06-26_
