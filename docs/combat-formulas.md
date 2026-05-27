# Combat Formulas — Manchego Stars

> Reference for the hybrid d20/FE combat system. See PRD §6.5 for the authoritative spec.
> Implementation lives in `engine/d20-combat/`.

## Attack Roll

```
d20Roll         = Roll(1d20, advantageState)
AttackRoll      = d20Roll + AbilityMod + ProfBonus + TriangleBonus + HighGroundBonus
Hit             if AttackRoll ≥ Defender.AC
Auto-hit        if d20Roll == 20  (crit)
Auto-miss       if d20Roll == 1
```

## Damage

```
DamageRoll      = Roll(WeaponDamageDice) + AbilityMod + TriangleDmgBonus
Damage          = max(0, DamageRoll − Defender.DamageReduction)

Resistant       → Damage × 0.5 (round down)
Immune          → Damage = 0
Vulnerable      → Damage × 2
```

## Critical Hits

```
Crit            if d20Roll == 20  (or 19 with Improved Critical)
Crit damage     = roll WeaponDamageDice TWICE (not FE's 3×)
```

## Doubling (vanilla FE, unchanged)

```
If AttackSpeed_attacker − AttackSpeed_defender ≥ 4 → attacker attacks twice
```

## Saving Throws (spells and staves)

```
SaveDC          = 8 + ProfBonus + SpellAbilityMod (caster)
DefenderSave    = 1d20 + SaveAbilityMod + SaveProf (defender)
Save ≥ DC       → half damage or no effect (per spell)
Save < DC       → full effect
No auto-pass/fail on nat 1/20 for saves (5e rule)
```

## Advantage / Disadvantage Sources

| Source | Effect |
|---|---|
| High ground (≥1 tile elevation) | Advantage on attacks |
| Low ground | Disadvantage on attacks |
| Flanking (ally on opposite side of target) | Advantage |
| Blizzard / dark terrain tiles | Disadvantage |
| Class abilities (Reckless Attack, Feral Strike) | As specified per class |
| Status: Blinded, Restrained, Frightened | Per 5e rules |
| Advantage + Disadvantage | Cancel → flat roll |

## Triangle Bonuses

**Physical:** Slashing > Bludgeoning > Piercing > Slashing
- Advantage side: +1 ATK, +15 to-hit modifier

**Magic:** Radiant > Necrotic > Elemental > Radiant
- Same bonuses

## Spell-Slot Tome Uses

| 5e Slot Level | Tome Uses |
|---|---|
| Cantrip (0) | ∞ |
| 1st | 8 |
| 2nd | 6 |
| 3rd | 4 |
| 4th | 3 |
| 5th | 2 |
| 6th+ | 1 |

All spell-slot tomes refill to max at chapter start (= long rest).
