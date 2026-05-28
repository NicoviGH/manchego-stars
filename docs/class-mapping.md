# Class Mapping — 5e → Fire Emblem

> See PRD §6.7 for the authoritative table. Updated 2026-05-27 after class-mapping audit (see decisions.md).

## Approach

Map each PC to a vanilla FE8 chassis (sprite + animations) and layer 5e mechanics as **unique skills / item overlays**. This minimizes new sprite work while preserving each PC's identity. The "FE Stat" column shows the FE stat the unit leans on in engine — flavor stats (CHA/WIS/INT in 5e) all fold to MAG for casters.

## PC Class Mappings

| PC | 5e Class | FE Base Class | FE Promoted Class | FE Stat | Unique Mechanic |
|---|---|---|---|---|---|
| Braulo | Barbarian (Berserker) | Pirate | Berserker | STR | Rage (consumable item: +4 dmg, B/P/S resistance). Shell Defense (command: +4 DEF, can't move). Hermit Crab natural armor → flat AC 17. |
| Marty | Druid (Circle of Spores) | **Monk** (custom Druid) | Summoner (custom) | MAG | Halo of Spores (AoE reaction, necrotic). Symbiotic Entity (+temp HP). Fungal Infestation (summon zombie from corpse). |
| Meesmickle | Warlock (The Fiend) | Shaman (Dark) | Dark Sage | MAG | Eldritch Blast (∞-use dark tome, 4 beams at cap). Dark One's Blessing (temp HP on kill). Hurl Through Hell (1/chapter nuke). |
| Prof. RBG | Artificer (Artillerist) | Archer | Artillerist (custom) | DEX (Fonduedler) / MAG (cannon, spells) | Fonduedler (1d10 firearm). **Pepperjack** (Ch1, first Eldritch Cannon) and **Brie** (later chapter, second cannon — Pepperjack's girlfriend). Both are Pokemon-style automatons that only say their own names. Modes: Flamethrower / Force Ballista / Protector; AC 18, 100 HP each. Flash of Genius (reaction: +5 ally save). Infusions (between-chapter item crafting). |
| Rootis | Sorcerer (Draconic — White Dragon) | Mage (Ice) | Sage | MAG | Metamagic (Twinned = attack twice, Empowered = reroll damage). **Dragon Wings = Manakete-style transform** (toggle on promotion: flier MOV, ignores terrain; toggles back to foot Mage form). Cold immunity, fire vulnerability, heals from cold attacks. |
| Sclorbo | Bard (College of Lore) | Dancer (custom Bard) | **Lore Bishop** (custom) | MAG | Bardic Inspiration (d12 ally buff). Cutting Words (debuff reaction). Dance/Refresh. Cleric-tier heal kit (Cure Wounds Ch1 → Revivify Ch4 → Mass Cure Wounds Ch6 → Raise Dead Ch7). **Balance: Dance and Cast are mutually exclusive per turn** — Sclorbo picks one role each round. |
| Wolfram | Metallurgist (Smith) | Knight | General | STR + MAG | Forge (between-chapter ally gear upgrades). AC 26 equivalent (highest DEF in party). Feral Strike (Bite + Claws bonus attacks). Breath Weapon (1/chapter fire AoE). Shield spell (reaction). Mystic Arcanums (Investiture of Stone, Forcecage). |

## NPC Unit Mappings

| NPC | Role | FE Class | Join Chapter |
|---|---|---|---|
| Baxby | Mount / escort | Cavalier (axe-beak) | Ch 1–2 |
| Pinky | Flyer / companion | Pegasus Knight (homunculus) | Ch 1 (with RBG) |
| Trex | Thief / utility | Thief (kobold) → Rogue | Ch 3 (post-chapter) |
| Basil | Healer | Cleric (custom shrub) | Ch 4 (post-chapter) |
| The Mummy | Tank / magic | Sage (undead) | Ch 4 (post-chapter) |

## Notes on Specific Mappings

### Marty: Monk base (not Shaman)
Moved off Shaman in the 2026-05-27 audit because Meesmickle is also Shaman → identical sprites. Monk (FE8's male Light-magic base, Saleh-line) gives visual differentiation. Reflavor: Monk chassis becomes Druid; promoted Summoner inherits the standard FE8 Summoner sprite (Knoll-line). Some palette work needed for the Light→Necrotic visual transition on promotion.

### Sclorbo: Lore Bishop (not Lore Bard)
Promoted form changed in the 2026-05-27 audit. PDF audit revealed Sclorbo has Cure Wounds, Revivify, Mass Cure Wounds, and Raise Dead all prepared — he is the party's primary healer/reviver, not just a buffer. Lore Bishop is a custom hybrid: Dancer chassis at base, Bishop-tier healer at promotion, with Dance retained as a unique skill.

**Balance lever:** Per turn, Sclorbo can EITHER Dance/Refresh OR Cast (heal/buff/attack), not both. Combined with chapter-gated heal spells and finite spell slots, this prevents him from being a one-man support engine.

### Rootis: Manakete-style Dragon Wings transform
Dragon Wings is the level-14 Draconic Sorcerer feature — he gets it permanently by 5e level 14 (end-state). In FE terms, it's a class-transform toggle (Myrrh-style):
- **Foot form (Mage Ice):** Standard caster movement, ~5 MOV
- **Dragon form (custom flier Sage):** Flier movement, ignores terrain
- Toggle is an in-combat command (mirrors 5e bonus action)
- Unique cost: each transform consumes 1 Sorcery Point (gates spam)

Implementation reuses the FE8 Manakete transform code (Myrrh / Dragonstone path).

### Pepperjack and Brie (RBG's cannons)
RBG's Eldritch Cannons are two named, sentient automatons:
- **Pepperjack** — first cannon, available from Ch 1. Grey chassis, red star, chili-pepper mustache, fierce single eye.
- **Brie** — second cannon, unlocked at a later chapter (TBD; likely Ch 4–5 to mirror the Artificer 9+ "Arcane Jolt" / second-cannon feature). Pink chassis, cyan star, glamorous eye with eyeshadow, ribbon-curled horn. **Pepperjack's girlfriend.**

Both speak **Pokemon-style** — Pepperjack can only say "Pepperjack!" and Brie can only say "Brie!" All combat barks, deployment dialogue, and adjacency support conversations between the two use this convention.

Modes (both cannons): Flamethrower (fire AoE), Force Ballista (ranged force), Protector (defensive aura). At endgame, both deployable simultaneously (AC 18, 100 HP each).

Portrait: `data/portraits/pepperjack-and-brie.jpeg` (combined image with both cannons). Source: `References/PCs/Pepperjack and Brie Portrait.jpeg`.

### Wolfram and RBG have spell access — design compensates
Both PCs are class-mapped as physical-chassis units (Knight, Archer) but have caster abilities layered on. Game tuning compensates:
- Spell slots are tight (chapter-refresh, no purchasing)
- Cantrips are infinite-use but lower damage tier than dedicated casters
- Their primary identity stat is physical (STR for Wolfram, DEX for RBG) — magic is a secondary role, not their main DPS path
