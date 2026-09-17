---
id: 146
title: "A reskin is resolved by its SLOT, never by the class it clones"
date: "2026-09-02"
section: "Class Mapping & Promotions"
issues: [347]
---

# A reskin is resolved by its SLOT, never by the class it clones

A reskin clones a vanilla class into its own otherwise-unused class slot, and BOTH the map
sprite (`SMSId`) and the battle animation (`pBattleAnimDef`) are fields of that slot's class
entry. So the slot IS the creature's identity, and the base class is only the chassis it was
copied from — **many creatures legitimately clone one chassis.** Four bases are claimed twice
today: goblin-soldier and ch05's risen-spear both clone `CLASS_SOLDIER`; goblin-fighter and
tomb-reaver both clone `CLASS_FIGHTER`; kobold-grunt/kobold-brute share `CLASS_BRIGAND`;
kobold-blade/crypt-blade share `CLASS_MERCENARY`.

`inject_ch01` used to look a skin up from the base class through a `{base: slot}` dict. Being
a dict, it kept the LAST claim — so ch05's undead quietly took ch01's Fire Imps, and the
goblins shipped with the skeleton map sprite *and* the skeleton battle anim, because both ride
the class. It went twelve days unnoticed: `#48` measures stats, the playtest scenarios assert
memory state, and nothing anywhere reads which sprite a unit wears.

Every chapter therefore **names the slot** in its `CHnn_CLASS_IDS` (ch05: `'soldier' ->
CLASS_SOL_SKELEBERDIER`; ch01: `'soldier' -> CLASS_BLST_REGULAR_EMPTY`). ch03/ch04/ch05 always
did; ch01 was the sole exception and is now fixed. Naming a *vanilla* class stays correct where
the chapter genuinely wants vanilla — ch02's raiders are human `CLASS_BRIGAND` even though two
kobolds clone that chassis.

The guarded invariant is **slot uniqueness**, not base uniqueness: two creatures in one slot
lose art, whereas two creatures on one base is the normal case. `reskin_by_base` is registered
in `DEAD_CONCEPTS` so the pattern cannot return by name.

**This is a precondition for ch06.** Its roster reskins `soldier` (mermaids), `fighter` (shark
riders), `mercenary` (crab-blades) and `archer` (merfolk-bow) — four already-contested bases.
Wired under the old resolution it would have taken `CLASS_SOLDIER` from ch05 exactly as ch05
took it from ch01.

All 8 PCs (and recruits) are **stock vanilla FE8 classes** — class bases, caps, MOV, and CON come
from the class (`fireemblem8u/src/data_classes.c`). **No custom classes, no per-character
abilities.** Individuality comes from flavor text, sprite/portrait art, and palette.
