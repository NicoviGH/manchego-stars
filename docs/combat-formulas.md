# Combat Formulas — Manchego Stars

> **Combat resolution is vanilla FE8.** The rules stay FE so the game plays like FE;
> D&D is flavor. This doc is a short reference for what the engine computes and what the
> D&D layer is allowed to touch (UI / flavor only).
>
> Authoritative engine behaviour is whatever vanilla `fireemblem8u/src/bmbattle.c`
> already does — we are **not replacing it**, and nothing is layered under it. Damage
> types are flavor labels only; iconic matchups use vanilla FE weapon effectiveness
> (no resistance multiplier).

## Attack Resolution — VANILLA FE (unchanged)

```
Hit%      = WeaponHit + (SKL × a) + (LCK × b) + TriangleHit + SupportHit + TerrainHit
Avoid     = (SPD × c) + LCK + TerrainAvoid
DisplayHit = clamp(Hit% − Defender.Avoid, 0, 100)
```

No d20 roll. No Armor Class. No advantage/disadvantage. This is FE8's native two-RN
hit system, left intact.

## Damage — VANILLA FE armor-subtraction (no D&D multiplier)

```
Might     = WeaponMight + (STR if physical | MAG if magic) + TriangleAtk
Damage    = max(0, Might − Defender.DEF | Defender.RES)
```

**No resistance/vulnerability/immunity multiplier** — that ×0.5/×2/×0 system was dropped
(2026-05-28); it has no vanilla FE analogue. Damage types are flavor labels only. Where a
matchup genuinely matters (e.g. fire vs ice trolls), use **vanilla FE weapon effectiveness**
(an `effective`-flag on the weapon, FE-native), not a damage multiplier.

Weapon damage is **fixed FE might**, not a rolled die. A weapon/tome is an FE item; its Might comes
from the FE weapon tier (Iron/Steel/Silver…), authored directly in FE terms. There is no weapon dice,
no ability modifier, and no 5e-die-to-might conversion. Never import raw 5e HP/damage numbers.

## Critical Hits — VANILLA FE (skill-based)

```
Crit%     = WeaponCrit + (SKL × d) + CritBonus(class/skill) + SupportCrit
Crit dmg  = Damage × 3        (FE's native triple, NOT roll-dice-twice)
```

**d20 flourish (flavor only):** when an FE crit fires, the battle UI *may* play a brief
"d20 lands on 20" animation for D&D feel. It is cosmetic — it never gates or changes
the crit, which is decided entirely by FE's crit rate.

## Doubling — VANILLA FE (unchanged)

```
If AttackSpeed_attacker − AttackSpeed_defender ≥ 4 → attacker attacks twice
```

## Magic, Staves & "Saves" — VANILLA FE

There are **no saving throws / DCs**. Magic resolves through FE combat:

- **Offensive spells (tomes):** FE magic combat — Might (MAG) vs RES, normal FE
  hit/avoid. Anima/Light/Dark behave as their vanilla item analogues.
- **Status staves (Sleep / Silence / Berserk / Poison):** vanilla FE staves —
  **always hit** when in range (no save). Effect/duration per the staff.
- **Healing staves (Heal / Physic / Recover):** vanilla FE staves, always succeed.

The `save:` / `save_dc:` fields in the PC YAMLs are flavor metadata only.

## Triangle Bonuses — VANILLA FE

**Physical:** Sword > Axe > Lance > Sword (+1 ATK, +15 hit — vanilla values).
**Magic:** Anima > Light > Dark > Anima (same vanilla bonuses).
Damage-type names (slashing, fire, …) are cosmetic per-weapon labels, not a relabel of the triangle.

Mechanics identical to vanilla FE8; only the labels change.

## Spell-Slot Tome Uses (unchanged by the combat revert)

| 5e Slot Level | Tome Uses |
|---|---|
| Cantrip (0) | ∞ (high finite per rules-mapping) |
| 1st | 8 |
| 2nd | 6 |
| 3rd | 4 |
| 4th | 3 |
| 5th | 2 |
| 6th+ | 1 |

All spell tomes deplete in use and are restocked with gold between chapters (decision B) — no free chapter refill. Innate per-rest class abilities (Rage, breath weapons) do refill free at chapter start.

## What the D&D flavor layer is allowed to touch (flavor/UI only)

- A cosmetic d20 flourish on crits.
- D&D damage-type **labels** on individual weapons/tomes (the triangle stays FE-native: Sword/Axe/Lance, Anima/Light/Dark).
- Flavor text in dialogue, item descriptions, and the stat/preview screens.

It must **not** touch hit, avoid, might, crit rate, or doubling — those are FE's.
