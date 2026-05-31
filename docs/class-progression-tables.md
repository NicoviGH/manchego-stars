# Class Progression Tables — 5e Level → FE Chapter Unlock

> **Purpose:** Map each 5e class's level-by-level features to the FE chapter where they
> unlock, so the YAMLs can gate abilities to MVP vs post-MVP. Two layers per the engine/
> content split:
> - **Generic base-class tables** (engine, reusable) — Barbarian, Bard, Sorcerer, Warlock,
>   Druid, Artificer. Any campaign inherits these.
> - **Campaign subclass + PC build paths** (content, this campaign) — the specific
>   subclasses, homebrew races, and reconstructed per-PC builds for Rime of the Frostmaiden.
>
> **Sources (verified 2026-05-28):**
> - SRD base classes + SRD subclasses (Berserker, Lore, Draconic, Fiend): live pull from
>   `https://www.dnd5eapi.co/api/2014/` (CC-BY-4.0). Eventually frozen to `data/srd-snapshot.json` (PRD issue #4).
> - Artificer + Artillerist, Circle of Spores: `Tasha's Cauldron of Everything` PDF.
> - Metallurgist (Smith): `Class_The_Metallurgist.pdf` (homebrew).
> - End-state PC builds: `data/pc-sheets/*.json` + `campaigns/rime-of-the-frostmaiden/pcs/*.yaml`.
>
> **See also:** [rules-mapping.md](rules-mapping.md) (how each mechanic converts to FE),
> `docs/CLASSES.md` (the generated roster: which 5e class → which FE class) + `docs/decisions.md` §Class Mapping.
>
> **Reading the FE-conversion column:** combat is vanilla FE (decisions.md §Combat System). Where a
> cell mentions "resist" / "damage resistance," there is **no ×0.5 multiplier** — it resolves to an
> **FE-native +DEF/RES buff** (or pure flavor), with iconic vulnerabilities handled by vanilla FE weapon
> **effectiveness**. AC, saves, and advantage are flavor only. *Status/condition* immunities
> (charm/fear/sleep) and crit-immunity are real and FE-native. Spell tomes/slots follow the decision-B
> gold economy (deplete + restock, no free refill); innate per-rest pools refill free at chapter start.

---

## Chapter → 5e Level Curve (PROPOSAL — confirm before YAML retier)

Full game = **20 chapters** (FE8 cadence). All 7 PCs reach **5e level 20** in-game (Sclorbo's
real-life L16 is flavor only — he levels to 20 with the party). Simplest readable curve is
**~1 chapter per 5e level**:

| Chapter | 5e Level | Milestone |
|---|---|---|
| 1 | 1 | Start. Cantrips + 1st-level spells. |
| 2 | 2 | |
| 3 | 3 | Subclass features begin (Frenzy, Cutting Words, Metamagic, Pact Boon, Eldritch Cannon). |
| 4 | 4 | First ASI/feat. 2nd-level spells. |
| 5 | 5 | Extra Attack (martials). 3rd-level spells. Arcane Firearm. |
| 6 | 6 | Subclass tier-2 (Elemental Affinity, Additional Magical Secrets, Fungal Infestation, Mindless Rage). |
| **7** | **7** | **MVP CLIFFHANGER.** 4th-level spells. Feral Instinct, Forge Expert, Flash of Genius. |
| — POST-MVP — | | |
| 8 | 8 | |
| 9 | 9–10 | Explosive Cannon, Spreading Spores. 5th-level spells. |
| 10 | 11 | **FE promotion era** (FE8 first-promo cadence). Mystic Arcanum 6th. |
| 11 | 12 | Blade Forge. |
| 12–13 | 13–14 | **Dragon Wings, Hurl Through Hell, Fungal Body, Retaliation.** Mystic Arcanum 7th. |
| 14 | 15 | **Brie (2nd cannon), Fortified Position.** Mystic Arcanum 8th. |
| 15–17 | 16–18 | Draconic Presence, Master of the Forge. Mystic Arcanum 9th (L17). |
| 18–20 | 19–20 | Capstones (Primal Champion, Eldritch Master, Soul of Artifice, Archdruid). Endgame. |

**MVP scope (Ch 1–7) = 5e levels 1–7.** This is richer than the earlier "levels 1–5"
estimate — it now includes 4th-level spells and all subclass tier-1/tier-2 features, but
still **excludes** everything at 5e level 9+: no Mystic Arcanums, no Dragon Wings transform,
no Spreading Spores, no Fungal Body, no Brie, no Blade Forge, no 5th-level spells.

> ⚠️ **Confirm this curve.** If you want MVP to feel more/less powerful, we shift the
> chapter↔level mapping (e.g. front-load so Ch 7 = level 9). Everything below assumes 1:1.

---

# PART 1 — Generic Base-Class Tables (engine, reusable)

Bold = a feature that becomes an FE-visible mechanic. ASIs become FE stat-ups / personal
feats. "MVP?" = available by Ch 7 under the 1:1 curve.

## Barbarian (Braulo)
| 5e Lvl | Feature | FE form | Ch | MVP? |
|---|---|---|---|---|
| 1 | **Rage**, **Unarmored Defense** | Rage = consumable/command (+might, +DEF — phys "resist" → FE +DEF); UD → high FE DEF (flavor, no AC) | 1 | ✓ |
| 2 | Reckless Attack, Danger Sense | Reckless = toggle: +hit/+crit this turn, −avoid until your next turn (FE-native risk trade, no advantage); Danger Sense = +avoid vs AoE | 2 | ✓ |
| 3 | Primal Path (→ Berserker) | Subclass unlock | 3 | ✓ |
| 5 | **Extra Attack**, Fast Movement | Extra Attack = brave-weapon-style 2nd hit; +MOV | 5 | ✓ |
| 7 | Feral Instinct | +initiative flavor / can't be surprised | 7 | ✓ |
| 9/13/17 | Brutal Critical (1/2/3 dice) | +crit damage dice | 9/12/17 | — |
| 11 | Relentless Rage | survive-at-1-HP proc (Classic-mode safety) | 11 | — |
| 15 | Persistent Rage | rage doesn't end early | 15 | — |
| 20 | Primal Champion | +STR/+CON cap | 20 | — |

## Bard (Sclorbo)
| 5e Lvl | Feature | FE form | Ch | MVP? |
|---|---|---|---|---|
| 1 | **Spellcasting**, **Bardic Inspiration (d6)** | Tome casting; BI = ally buff item/command | 1 | ✓ |
| 2 | Jack of All Trades, Song of Rest (d6) | minor universal +hit; between-chapter HP recovery | 2 | ✓ |
| 3 | Expertise, Bard College (→ Lore) | Subclass unlock | 3 | ✓ |
| 5 | **Bardic Inspiration (d8)**, Font of Inspiration | BI die up; BI refills each chapter | 5 | ✓ |
| 6 | Countercharm | aura vs fear/charm | 6 | ✓ |
| 10 | **BI (d10)**, **Magical Secrets** | BI up; learns off-list spells (where heal kit deepens) | 9 | — |
| 14 | Magical Secrets | more off-list spells | 13 | — |
| 15 | **BI (d12)** | BI die cap | 14 | — |
| 18 | Magical Secrets | more off-list spells | 18 | — |
| 20 | Superior Inspiration | always keep ≥1 BI | 20 | — |
> **Sclorbo reached level 16 in the real-life campaign, but in-game he progresses to level 20
> with the rest of the party** (treat his table identically to the others). His real-life L16
> is kept only as flavor metadata in the YAML (`dnd.level_end_state: 16`); the FE progression
> ignores it. His Magical Secrets picks (L10, L14, **L18**) are where Revivify / Mass Cure
> Wounds / Raise Dead come from — all **post-MVP**.

## Sorcerer (Rootis)
| 5e Lvl | Feature | FE form | Ch | MVP? |
|---|---|---|---|---|
| 1 | **Spellcasting**, Sorcerous Origin (→ Draconic) | Tome casting; subclass | 1 | ✓ |
| 2 | **Font of Magic** (Sorcery Points) | SP = per-chapter resource pool | 2 | ✓ |
| 3 | **Metamagic** (2 options) | Twinned/Empowered/etc. as SP-spend toggles | 3 | ✓ |
| 10 | Metamagic (+1) | another option | 9 | — |
| 17 | Metamagic (+1) | another option | 17 | — |
| 20 | Sorcerous Restoration | refill some SP mid-map | 19 | — |

## Warlock (Meesmickle)
| 5e Lvl | Feature | FE form | Ch | MVP? |
|---|---|---|---|---|
| 1 | **Pact Magic**, Patron (→ Fiend) | Pact slots = finite-use tomes (deplete + gold-restock, decision B); subclass | 1 | ✓ |
| 2 | **Eldritch Invocations** | passive/utility upgrades (e.g. Agonizing Blast = +CHA to EB) | 2 | ✓ |
| 3 | **Pact Boon** (→ Tome) | grants extra cantrips / ritual book | 3 | ✓ |
| 11 | **Mystic Arcanum (6th)** | 1/chapter big spell | 10 | — |
| 13 | Mystic Arcanum (7th) | 1/chapter big spell (Forcecage-tier) | 12 | — |
| 15 | Mystic Arcanum (8th) | 1/chapter (Demiplane-tier) | 14 | — |
| 17 | **Mystic Arcanum (9th)** | 1/chapter (Power Word Kill) | 17 | — |
| 20 | Eldritch Master | refill Pact slots 1/chapter | 19 | — |

## Druid (Marty)
| 5e Lvl | Feature | FE form | Ch | MVP? |
|---|---|---|---|---|
| 1 | **Spellcasting**, Druidic | Tome casting | 1 | ✓ |
| 2 | **Wild Shape**, Druid Circle (→ Spores) | Wild Shape = the resource Symbiotic Entity consumes; subclass | 2 | ✓ |
| 4 | Wild Shape up, ASI | — | 4 | ✓ |
| 8 | Wild Shape up, ASI | — | 8 | — |
| 18 | Timeless Body, Beast Spells | flavor | 18 | — |
| 20 | Archdruid | unlimited Wild Shape → Symbiotic Entity free | 20 | — |

## Artificer (Prof. RBG) — *Tasha's, not SRD*
| 5e Lvl | Feature | FE form | Ch | MVP? |
|---|---|---|---|---|
| 1 | **Magical Tinkering**, **Spellcasting** (half-caster) | minor utility; tome casting | 1 | ✓ |
| 2 | **Infuse Item** (4 infusions, 2 items) | between-chapter gear crafting | 2 | ✓ |
| 3 | Artificer Specialist (→ Artillerist), Right Tool for the Job | subclass | 3 | ✓ |
| 6 | Tool Expertise | flavor | 6 | ✓ |
| 7 | **Flash of Genius** | reaction → +INT to nearby ally save (auto-proc, capped uses) | 7 | ✓ |
| 10 | Magic Item Adept | crafting | 9 | — |
| 11 | Spell-Storing Item | 10-use stored spell item | 11 | — |
| 14 | Magic Item Savant | crafting | 13 | — |
| 18 | Magic Item Master | crafting | 18 | — |
| 20 | Soul of Artifice | survive-at-1-HP proc | 20 | — |
> Half-caster: spell slots top out at **5th level** (5e L19+). Cantrips 2→3 (L10)→4 (L14).

---

# PART 2 — Campaign Subclass Layer (content)

## Berserker — Barbarian path (Braulo) *(SRD)*
| 5e Lvl | Feature | FE form | Ch | MVP? |
|---|---|---|---|---|
| 3 | **Frenzy** | extra attack while raging (exhaustion cost dropped per rules-mapping §F) | 3 | ✓ |
| 6 | Mindless Rage | immune to charm/fear while raging | 6 | ✓ |
| 10 | Intimidating Presence | fear-aura command | 9 | — |
| 14 | **Retaliation** | counterattack proc when hit in melee | 13 | — |

## College of Lore — Bard path (Sclorbo) *(SRD)*
| 5e Lvl | Feature | FE form | Ch | MVP? |
|---|---|---|---|---|
| 3 | Bonus Proficiencies, **Cutting Words** | Cutting Words = debuff-enemy-roll reaction (auto-proc) | 3 | ✓ |
| 6 | **Additional Magical Secrets** | learns 2 off-list spells (e.g. Ray of Frost cantrip already noted) | 6 | ✓ |
| 14 | Peerless Skill | add BI die to own check | 13 | — |

## Draconic Bloodline (White Dragon) — Sorcerer path (Rootis) *(SRD)*
| 5e Lvl | Feature | FE form | Ch | MVP? |
|---|---|---|---|---|
| 1 | **Dragon Ancestor**, **Draconic Resilience** | cold affinity; +HP & AC=13+DEX (unarmored) | 1 | ✓ |
| 6 | **Elemental Affinity** | +MAG to cold damage; spend SP for a timed +RES buff (cold "resist" = flavor, no multiplier) | 6 | ✓ |
| 14 | **Dragon Wings** | **Manakete-style transform** (see decisions.md) | 13 | — |
| 18 | Draconic Presence | fear/charm aura (SP cost) | 17 | — |
> Confirms: the Manakete transform is **post-MVP** (Ch 13). Through MVP, Rootis is a foot
> Mage (Ice). The party-balance.md claim of "Dragon Wings from level 1" was based on the
> end-state sheet and is wrong for gameplay — corrected here.

## The Fiend — Warlock path (Meesmickle) *(SRD)*
| 5e Lvl | Feature | FE form | Ch | MVP? |
|---|---|---|---|---|
| 1 | **Dark One's Blessing** | temp HP on kill | 1 | ✓ |
| 6 | Dark One's Own Luck | 1/chapter reroll save/check | 6 | ✓ |
| 10 | Fiendish Resilience | timed +DEF/RES self-buff, 1/chapter (was "pick a damage resistance"; no multiplier) | 9 | — |
| 14 | **Hurl Through Hell** | 1/chapter nuke (the signature) | 13 | — |
> Confirms: **Hurl Through Hell is post-MVP** (Ch 13). Eldritch Blast beam count scales with
> *character* level (1 beam <L5, 2 @L5, 3 @L11, 4 @L17): MVP = 1–2 beams; 4 beams is endgame.

## Circle of Spores — Druid path (Marty) *(Tasha's)*
| 5e Lvl | Feature | FE form | Ch | MVP? |
|---|---|---|---|---|
| 2 | **Halo of Spores** (1d4, scales), **Symbiotic Entity** (4 tempHP/lvl), Circle Spells (chill touch) | reaction AoE; consumable buff | 2 | ✓ |
| 6 | **Fungal Infestation** | reaction → animate corpse as zombie ally (WIS-mod uses) | 6 | ✓ |
| 10 | **Spreading Spores** | bonus-action hazard zone → fold to main action (rules-mapping §B) | 9 | — |
| 14 | **Fungal Body** | immune blind/deaf/fright/poison; crits→normal | 13 | — |
> Halo scaling: 1d4 (L2) → 1d6 (L6) → 1d8 (L10) → 1d10 (L14). Symbiotic temp HP = 4×druid
> level → +28 at MVP end (Ch7/L7), +80 only at L20 (endgame). Earlier YAML's +80 is endgame.

## Smith — Metallurgist path (Wolfram) *(homebrew PDF)*
Base Metallurgist + Smith school. Wolfram's "Forge" mechanic = the smithing line.
| 5e Lvl | Feature | FE form | Ch | MVP? |
|---|---|---|---|---|
| 1 | **Upgrade Armor** (+1 AC), Tinkerer's Whit (INT for atk) | between-chapter armor buff | 1 | ✓ |
| 2 | Alloy Mending | repair/+AC buff | 2 | ✓ |
| 3 | **Improved Upgrade** (Smith: +1 more AC, half time) | **Forge** ability core | 3 | ✓ |
| 5 | Metal Sense, Magnetism, **Arcane Charges** (=2×prof) | charges power armor "spells" | 5 | ✓ |
| 7 | **Forge Expert** (smith armor for +DEF), Mobile Metal | +DEF-granting forge (B/P/S "resistance" → FE +DEF) | 7 | ✓ |
| 11 | **Blade Forge** (upgrade weapons +1 die) | weapon-forge | 11 | — |
| 13 | Armor Summon | conjure armor (flavor) | 12 | — |
| 15 | Armor Master (fly 2× in upgraded armor, +3 AC) | flight (note: ≠ FE flier class) | 14 | — |
| 16 | **Master of the Forge** (Adamantine/Resist/Mithral armor) | top-tier forge | 15 | — |
| 20 | Mobile Fortress (DEX-to-AC any armor; 1/day 6d6 AoE pulse) | capstone | 19 | — |

**Armor abilities** (cast via Arcane Charges; Wolfram picks 4, +1 at L7/11/16):
- **Flamethrower** (1 charge → *burning hands*) = Wolfram's **Breath Weapon** (fire AoE). 1/chapter per rules-mapping §D.
- **Armor Lock** (1 charge → *shield*) = his **Shield reaction**.
- **Recharge** (2 charges → *cure wounds*) = minor self-heal.
- **Explosive Burst** (L7, 2 charges → *fireball*) = post-MVP AoE.
> The "Mystic Arcanums" attributed to Wolfram in earlier YAMLs (Investiture of Stone,
> Forcecage) are **not** Metallurgist features — they were a mis-port. Wolfram's high-end
> magic is the armor-ability list above. **Flag to fix in the YAML.**

---

# PART 3 — Reconstructed Per-PC Build Paths

Because we have the end-state sheets **and** the class tables, we can back-infer each
player's level-up choices (spells, ASIs/feats, metamagic, invocations, infusions) and place
them on the chapter timeline. Below: the MVP-relevant choices + the headline post-MVP unlock.

### Braulo — Barbarian (Berserker), Hermit Crab
- **MVP arc (Ch1–7):** Rage (Ch1) → Reckless Attack (Ch2) → Frenzy (Ch3) → ASI likely STR (Ch4) → Extra Attack (Ch5) → Mindless Rage (Ch6) → Feral Instinct (Ch7). A clean, front-loaded bruiser; almost his whole identity is online by MVP end.
- **Post-MVP headline:** Brutal Critical + Relentless Rage (Classic-mode safety net).

### Sclorbo — Bard (Lore), Chwinga
- **Note:** real-life campaign stopped at L16; **in-game he progresses to L20 with the party.**
- **MVP arc:** Spellcasting + BI d6 (Ch1) → Cutting Words (Ch3) → BI d8 (Ch5) → Additional Magical Secrets picks (Ch6, where Ray of Frost / utility come in). Only **Cure Wounds** for healing in MVP.
- **Post-MVP headline:** Magical Secrets at L10/L14/L18 → **Revivify, Mass Cure Wounds, Raise Dead** (his whole reviver identity is post-MVP). BI d10→d12; Superior Inspiration at L20.

### Rootis — Sorcerer (Draconic White), Snowperson
- **MVP arc:** Draconic Resilience (Ch1) → Font of Magic/SP (Ch2) → Metamagic ×2 [Twinned, Empowered] (Ch3) → Elemental Affinity cold (Ch6). Foot Ice-mage all of MVP.
- **Post-MVP headline:** **Dragon Wings transform (Ch13)**, Draconic Presence (Ch17).

### Meesmickle — Warlock (Fiend), homebrew race
- **MVP arc:** Pact Magic + Dark One's Blessing (Ch1) → Invocations [Agonizing Blast → +CHA to EB] (Ch2) → Pact of the Tome (Ch3) → Dark One's Own Luck (Ch6). EB at 1–2 beams.
- **Post-MVP headline:** Mystic Arcanums (Ch10+), **Hurl Through Hell (Ch13)**, EB 4 beams (endgame).

### Marty — Druid (Spores), Myconid
- **MVP arc:** Spellcasting (Ch1) → Wild Shape + **Halo of Spores + Symbiotic Entity** (Ch2) → ASI (Ch4) → **Fungal Infestation** summon (Ch6). Halo at 1d4→1d6; Symbiotic +28 tempHP at Ch7.
- **Post-MVP headline:** Spreading Spores (Ch9), **Fungal Body** crit-immunity (Ch13), Archdruid (endgame).

### Prof. RBG — Artificer (Artillerist), homebrew race
- **MVP arc:** Spellcasting + Magical Tinkering (Ch1) → Infuse Item (Ch2) → **Pepperjack** Eldritch Cannon (Ch3) → Arcane Firearm +d8 (Ch5) → **Flash of Genius** (Ch7). One cannon all MVP.
- **Post-MVP headline:** Explosive Cannon (Ch9), Spell-Storing Item (Ch11), **Brie 2nd cannon (Ch14)**.

### Wolfram — Metallurgist (Smith), homebrew race
- **MVP arc:** Upgrade Armor (Ch1) → Improved Upgrade [Forge] (Ch3) → Arcane Charges + Flamethrower **Breath Weapon** (Ch5) → Forge Expert +DEF-smithing (Ch7). FE DEF climbs via Upgrade Armor stacking.
- **Post-MVP headline:** **Blade Forge** weapon-upgrades (Ch11), Master of the Forge (Ch15), Mobile Fortress (endgame).

---

## Action Items Surfaced by This Audit

1. **Confirm the chapter→level curve** (1:1 proposed). Everything else keys off it.
2. **Wolfram YAML fix:** remove "Investiture of Stone / Forcecage Mystic Arcanums" (not Metallurgist features); replace with the armor-ability list (Flamethrower/Armor Lock/Recharge/Explosive Burst).
3. **Rootis YAML fix:** Dragon Wings transform → gate to Ch13 (post-MVP), not always-on.
4. **Meesmickle YAML fix:** Hurl Through Hell → Ch13; Mystic Arcanums → Ch10+; EB beams scale with chapter.
5. **Sclorbo YAML fix:** only Cure Wounds in MVP; Revivify/Mass Cure/Raise Dead → post-MVP.
6. **Marty YAML fix:** Symbiotic Entity temp HP = 4×level (Ch-scaled), +80 only at endgame; Halo dice scale 1d4→1d10; Spreading Spores/Fungal Body → post-MVP.
7. **RBG YAML fix:** Brie → Ch14 (was "tbd"); Explosive Cannon → Ch9.
8. **party-balance.md fix:** re-evaluate roster for the **MVP-only** (Ch1–7, unpromoted, 5e L1–7) state — the current analysis assumes end-state level 20.
