---
id: 128
title: "Per-caster charge flash: pulse the actor's OWN palette, armed from an EXISTING banim command (#183)"
date: "2026-07-18"
section: "Art & Audio"
issues: [183]
---

# Per-caster charge flash: pulse the actor's OWN palette, armed from an EXISTING banim command (#183)

Each custom caster's sprite pulses its signature colour on the wind-up beat (Rootis blue, Marty green,
Meesmickle purple) — a "gathering power" tell the faked 3-pose magic cadence otherwise lacks. The
reusable pattern (`_patch_banim_charge_flash`, hook + `battle_charge_flashes` data):
- **Adding a caster = one YAML block** (`charge_flash: {color}` on `battle_anim`); the weapon type is
  auto-derived from the caster's donor, so nothing else is needed. **A new colour = one line** in
  `build_campaign.CHARGE_FLASH_RGB` (name → RGB); `charge_flash_target` packs it to BGR555. The table
  (`gMSChargeFlashes`, `{character, weapon_type, BGR555}`) rides `data_banimconfunk.c`; the engine names
  no character. Same character+weapon scoping as the spell tint (`gMSSpellTint`).
- **The reusable engine kernel (copy this for any per-caster actor-visual effect):** (1) *arm from an
  existing banim script command* — hook the interpreter switch in `banim-main.c` on a command ALREADY
  in the faked body, so the donor-matched animation script is never edited. We use **start-attack
  (`case 0x07`)** — it fires one settle beat before the wind-up arm-raise, and a raised-cosine LUT that
  ramps from 0 makes the pulse *bloom* exactly on the arm-raise (the elec-charge marker, `case 0x28`,
  fires ~18 ticks too late). (2) *Identify the attacker* via `GetAnimPosition(anim)` →
  `gpEkrBattleUnitLeft/Right` + `GetItemType(bu->weaponBefore)` (the spell-tint pattern). (3) *Pulse the
  actor OBJ palette* `PAL_OBJ(0x7)` (L) / `PAL_OBJ(0x9)` (R): a `PROC_REPEAT` proc snapshots the 16
  colours, blends toward the target by the LUT each frame, and restores + `Proc_Break`s at the end
  (bleeding into the cast). *Timing is engine-only* — start point and throb count/speed are the
  `case`-choice + `_CHARGE_FLASH_FRAMES`/`_THROBS` constants; never lengthen the animation to fit it.
- **A flash is a WASH toward a bright colour, not a hue-transform.** A palette-transform (like the
  spell tint's `BanimSpellTintBlue`) does nothing on a caster already near the target hue — Rootis's
  white-blue snowman only flipped its nose. Blend toward a saturated target so it reads on any base.
- **Two build-system gotchas that cost a rebuild each (so the next hook author skips them):**
  (a) **A new hook-target file MUST be added to `build_campaign.PATCHED_DECOMP_FILES`** — else
  `restore_vanilla_sources` doesn't reset it, the injection's `if not already patched` guard skips
  re-injection, and a *stale* prior injection persists silently (old symbols, or a no-op edit).
  (b) **No `.bss` statics in banim TUs** — the decomp linker discards `.bss` there (`` `.bss'
  referenced in ... discarded section``). Put mutable per-effect state in the **proc struct** (pool-
  allocated), not a `static` uninitialised global. The `const` LUT is fine (`.rodata`).
_Decided: 2026-07-18 (Marty/Rootis/Meesmickle charge flash, `feat/183-charge-flash`; TDD + in-engine
`recordanim` gate; validated the arm-raise sync + multi-throb feel with Nicolas)_
