# Party Balance Analysis — Manchego Stars vs Typical FE Roster

> Evaluates the 7 PCs (plus 5 NPC recruits) against a typical Fire Emblem mid-game
> roster. Produced 2026-05-27 after cross-referencing all 7 PC PDF sheets vs
> `data/pc-sheets/*.json` and `campaigns/rime-of-the-frostmaiden/pcs/*.yaml`.
> See also: [class-mapping.md](class-mapping.md), [combat-formulas.md](combat-formulas.md), PRD §6.7 / §7.

---

## TL;DR

- **Heavily caster-skewed:** 5 of 7 PCs cast spells (Marty WIS, Meesmickle CHA, RBG INT, Rootis CHA, Sclorbo CHA).
- **Only 2 frontliners:** Braulo (Berserker) and Wolfram (General). Both are walls — Braulo has Hermit Crab natural armor (flat AC 17, 285 HP, 75% HP growth + 50% DEF growth) and Shell Defense; Wolfram has AC 26 General-tier defenses. The party has no glass-cannon frontliner.
- **No dedicated healer in the PC roster.** Sclorbo (Bard 16) is the de-facto primary healer — Cure Wounds, Revivify, Mass Cure Wounds, Raise Dead all on his prepared list.
- **No flier in the PCs at base** — Pinky NPC fills from Ch1; Rootis has Dragon Wings as a toggle from level 1 (Sorcerer 14 feature, end-state already reached).
- **No thief / no cavalry in the PCs.** Trex (Ch3) and Baxby (Ch1–2) NPCs fill those slots.
- **Radiant damage is absent from the PC roster.** Basil (Cleric NPC, Ch4) must carry the Radiant identity.
- **The full roster (7 PCs + 5 NPCs = 12 units by Ch5)** is balanced overall; the PC-only roster is not — Chapters 1–3 are the danger zone.

---

## Reference: Typical FE8 Mid-Game Roster (Ch5–8)

Eirika route mid-game gives you ~12 deployable units across these archetypes:

| Archetype | FE8 examples |
|---|---|
| Lord (sword) | Eirika |
| Cavalier (sword+lance) | Franz, Forde, Kyle |
| Axe infantry | Garcia, Ross, Gilliam (after promo) |
| Sword infantry | Joshua, Marisa |
| Healer | Moulder, Natasha, L'Arachel |
| Mage | Lute, Saleh |
| Archer | Neimi, Innes |
| Pegasus Knight | Vanessa, Tana |
| Knight | Gilliam, Amelia |
| Thief | Colm, Rennac |
| Shaman / Dark | Knoll |
| Monk / Light | Artur |

Role coverage is the design target: **sword + axe + lance frontliners, ranged via archer + mage, mobility via cavalry + flier, support via healer + thief.**

---

## Manchego Stars Roster

### PCs (7, all available Ch1)

| PC | Base / Promoted | Stat | Damage types | Role |
|---|---|---|---|---|
| **Braulo** | Pirate → Berserker | STR | Slashing (claws), Piercing (Nu', Trident) | Melee strike / DPS |
| **Wolfram** | Knight → General | STR + INT | Bludgeoning, Fire (Breath, Fire Bolt), Force | Tank + secondary caster |
| **RBG** | Archer → Artillerist | INT + DEX | Piercing (Fonduedler), Lightning (Shocking Grasp), Force (cannon) | Ranged DPS + buffer |
| **Sclorbo** | Dancer → Lore Bard | CHA | Piercing (Rapier), Cold (Ray of Frost), Psychic (Vicious Mockery) | Dancer + healer |
| **Marty** | Shaman (Druid) → Summoner | WIS | Bludgeoning (Shillelagh), Necrotic (Halo, Chill Touch) | Necrotic AoE + summoner |
| **Meesmickle** | Shaman (Dark) → Dark Sage | CHA | Force (EB ×4 beams), Bludgeoning (Magic Stone), Psychic (HtH) | Ranged DPS + nuke |
| **Rootis** | Mage (Ice) → Sage | CHA | Cold (RoF), Necrotic (Chill Touch) | Cold mage + flier toggle |

### NPCs (5, joining over Ch1–Ch4 per PRD §6.7, §7)

| NPC | Class | Join | Fills |
|---|---|---|---|
| **Pinky** | Pegasus Knight (homunculus) | Ch1 (with RBG) | Flier — also has respawn-on-death (drops Red Ruby for RBG to resummon) |
| **Baxby** | Cavalier (axe-beak) | Ch1–2 purchasable | Cavalry mount |
| **Trex** | Thief → Rogue (kobold) | Ch3 post-chapter | Thief utility (lockpick / steal) |
| **Basil** | Cleric (custom shrub) | Ch4 post-chapter | Dedicated healer + Radiant magic |
| **The Mummy** | Sage (undead) | Ch4 post-chapter | Mage tank + secondary healer |

**Full roster by Ch5: 12 units.** Pre-Ch4 (Chapters 1–3) is only 7–10 units, no dedicated healer.

---

## Role Coverage Matrix

| Role | PC fill | NPC fill | Status |
|---|---|---|---|
| **Sword / Slashing** | Braulo claws (minor), Wolfram Feral Strike Claws (1d6 bonus action) | — | ⚠️ Light coverage |
| **Axe / Bludgeoning** | Wolfram Warhammer, Marty Shillelagh | — | ✓ |
| **Lance / Piercing** | Braulo Nu'/Trident, Sclorbo Rapier, RBG Fonduedler | — | ✓ |
| **Ranged physical** | RBG (Fonduedler 3 tiles) | — | ✓ via RBG only |
| **Ranged magic** | Marty, Meesmickle, RBG, Rootis, Sclorbo, Wolfram | The Mummy | ✓ Saturated |
| **Healer** | Sclorbo (primary), Marty (heal staff), RBG (cure wounds) | Basil (Ch4+) | ⚠️ Pre-Ch4 thin |
| **Cavalry** | — | Baxby (Ch1–2) | ✓ via NPC |
| **Flier** | Rootis (Dragon Wings toggle, available Ch1) | Pinky (Ch1) | ✓ |
| **Thief** | RBG Nimble Escape (partial — disengage only, no steal/lockpick) | Trex (Ch3) | ⚠️ Pre-Ch3 no utility |
| **Knight / Tank** | Wolfram | — | ✓ |
| **Dancer** | Sclorbo | — | ✓ |

---

## Key Balance Findings

### 1. Sclorbo is the primary healer, not a pure dancer

PDF p5 confirms Sclorbo has **Cure Wounds, Revivify, Mass Cure Wounds, Raise Dead** all prepared on his Bard 16 spell list. Mechanically, this makes him the strongest healer/reviver in the party — stronger than Marty (Druid). The "Dancer (Bard)" class mapping is accurate for the *Dance refresh* mechanic, but his ability load actually mirrors a **Cleric/Bishop more than a pure FE Dancer**.

**Action taken (sclorbo.yaml):** Added `heal-staff` to Chapter 1 inventory and a `bard-healing-suite` progression note covering Revivify (Ch4), Mass Cure Wounds (Ch6), Raise Dead (Ch7).

**Open question:** Should Sclorbo's promoted class be `Lore Bard` (current YAML) or something closer to `Valkyrie / Sage` to reflect his healer + caster identity? Decision deferred to Phase 1 playtesting.

### 2. Wolfram's Breath Weapon was wildly overscoped

Previous YAML listed `uses_per_chapter: null` (unlimited). The PDF p3 explicitly says **"Once per short rest as an action"** — that's 1/chapter in FE terms. With that fix applied, Wolfram's ranged identity drops sharply.

**Action taken (wolfram.yaml):** Breath Weapon corrected to 1/chapter; added Fire Bolt cantrip (4d10 at level 20) to inventory so Wolfram retains a reliable ranged fire option for flyers and distant enemies. Also added the missing Mystic Arcanums (Investiture of Stone 6th, Forcecage 7th).

### 3. Caster overload — but stat diversity saves it

5 of 7 PCs cast spells. In FE you'd typically have 1–2 mages. However:
- **Stat split** prevents item competition: WIS (Marty), INT (RBG, Wolfram), CHA (Meesmickle, Rootis, Sclorbo).
- **Cantrips are infinite-use** — the spell-slot economy only kicks in for high-level spells.
- **Marty as Druid** mixes melee (Shillelagh+WIS) with caster identity, taking some pressure off the slot pool.

**Concern:** Three CHA-based casters (Meesmickle, Rootis, Sclorbo) compete for any CHA-boosting items.

### 4. Damage-type & magic-triangle coverage

**Physical triangle:**
- Slashing: light (Braulo claws 1d4, Wolfram Feral Strike Claws 1d6 bonus action)
- Piercing: strong (Nu', Trident, Rapier, Fonduedler)
- Bludgeoning: strong (Warhammer, Magic Stone, Shillelagh)

**Magic triangle (Radiant > Necrotic > Elemental):**
- Radiant: **NONE in PC roster** — Basil NPC (Ch4) must carry this
- Necrotic: Marty (signature — Halo of Spores, Chill Touch). Meesmickle has resistance, not damage.
- Elemental: Wolfram (fire), Rootis (cold), RBG (lightning)

Since most of the party deals Elemental damage, **enemy mix should feature Radiant casters only sparingly** in Ch1–3, or Marty becomes a liability vs them while everyone else gets a triangle bonus. Save Radiant enemy density for Ch5+.

### 5. Speed / doubling distribution is healthy

SPD growth: Meesmickle 60, Sclorbo 60, Rootis 50, Marty 45, RBG 40, Braulo 40, Wolfram 15.

Standard FE design: one slow tank, several fast casters/dancers. Wolfram will be doubled by everything (intentional for General archetype). No tuning needed.

### 6. Movement on arctic maps

PCs MOV: 4 (Marty, Wolfram) — 6 (Braulo, RBG, Sclorbo). No fast cavalry. Maps are mostly arctic (snow / ice = difficult terrain in vanilla FE8).

**Mitigations available:**
- Rootis **Snow Ski** (passive): double MOV on snow/ice
- Rootis **Dragon Wings** (toggle): flier movement, ignores terrain
- Baxby NPC: high MOV
- Marty **Spreading Spores**: places hazard zone (offensive use of slowness)

The party can handle arctic maps, but only because Rootis covers movement so heavily. If Rootis dies in classic mode, mobility collapses.

### 7. Chapter 1–3 fragility

Until Basil joins (Ch4), the party has:
- No dedicated healer (Sclorbo's heal-staff is the lifeline)
- No thief until Trex (Ch3)
- Only Pinky for flying utility

**Recommendation:**
- Issue 3+ Vulneraries per PC in Ch1
- Heavy use of Sclorbo Dance to refresh frontliners
- Pinky's Rescue ability for emergency extraction
- Cap enemy density at 8–12 per map (already in PRD §7)

---

## Recommended Chapter 1 PC Loadouts

| PC | Slot 1 | Slot 2 | Slot 3 |
|---|---|---|---|
| Braulo | Nu' Shipwrecker (locked) | Trident (thrown, 2 range) | Vulnerary ×3 |
| Wolfram | Warhammer | Magic Stone (cantrip, INT) OR Fire Bolt (cantrip, INT) | Vulnerary ×2 |
| Marty | Shillelagh-Staff (locked, cantrip WIS) | Chill Touch (cantrip WIS) | Heal Staff |
| Meesmickle | Eldritch Blast (locked, cantrip CHA) | Magic Stone (Pact of Tome) | Blood Vial ×3 |
| RBG | Fonduedler (firearm DEX) | Shocking Grasp (cantrip INT) | Vulnerary ×2 |
| Rootis | Ray of Frost (cantrip CHA) | Chill Touch (cantrip CHA) | Vulnerary ×2 |
| Sclorbo | Rapier (DEX) | Ray of Frost (cantrip CHA) | Heal Staff ×8 |

Most of these are now reflected in the YAMLs after the cross-reference pass.

---

## Open Questions for Phase 1 Playtesting

1. Is Wolfram playable at SPD 3 with no SPD-boost items in the early chapters? (He'll be doubled by every enemy and may take massive damage despite AC 26.)
2. Does Sclorbo's heal-staff (8 uses/chapter) suffice as primary healing pre-Basil, or does Marty need a buff to his heal output?
3. Is the 5-caster cantrip economy too easy (infinite ranged spam) or too tedious (5 different cast animations per turn)?
4. Does Rootis's Snow Ski (double MOV on snow) trivialize arctic maps for him? Should it be promotion-locked?
5. Are 4 Pact slots (Meesmickle) + 4 Spell + 4 Pact slots (Wolfram) too many endgame slots? Should we reduce to half-caster-equivalent?
6. Should Sclorbo's promoted class be `Valkyrie / Sage` rather than `Lore Bard` to better reflect his healer identity?

---

## Cross-Reference Audit Notes (PDF vs YAML, 2026-05-27)

Critical mechanical findings applied to YAMLs:

| PC | Finding | Status |
|---|---|---|
| Wolfram | Breath Weapon was unlimited; PDF says 1/short rest | ✅ Fixed |
| Wolfram | Missing Mystic Arcanums (Investiture of Stone 6th, Forcecage 7th) | ✅ Added |
| Wolfram | Missing Feral Strike Claws (PDF p3) | ✅ Added |
| Wolfram | Missing Fire Bolt cantrip (PDF p1) | ✅ Added |
| Meesmickle | Pact slots said "2"; PDF shows 4 at 5th level (Warlock 20 standard) | ✅ Fixed |
| Meesmickle | Missing 9th Mystic Arcanum: Power Word Kill (PDF p5) | ✅ Added |
| Meesmickle | Missing 8th Mystic Arcanum: Demiplane (PDF p5) | ✅ Added |
| Meesmickle | EB 4 beams at level 20 not noted (PDF p1 "Count: 4") | ✅ Added |
| Rootis | AC claimed "flat 17"; PDF says "13 + DEX" (lands at 17 but scales) | ✅ Fixed |
| Rootis | Missing Distant Spell + Extended Spell metamagic options | ✅ Added |
| Rootis | Missing Draconic Presence (level 18 feature) + Sorcerous Restoration | ✅ Added |
| Rootis | Missing Chill Touch cantrip (PDF p1) | ✅ Added |
| Sclorbo | Ideal text wrong: PDF says "Sincerity. There's no good in pretending..." not "People deserve..." | ✅ Fixed |
| Sclorbo | Healing role (Cure Wounds, Revivify, Mass Cure Wounds, Raise Dead) was not reflected | ✅ Added |
| Sclorbo | No heal-staff in inventory | ✅ Added |
| Braulo | Missing Reckless Attack, Mindless Rage, Danger Sense, Feral Instinct (core Barbarian features) | ✅ Added |
| Braulo | Background was "Merchant"; PDF says "Custom Background" | ✅ Fixed |
| RBG | Arcane Firearm description was wrong (PDF: per-spell, not per-turn) | ✅ Fixed |
| RBG | Missing Shocking Grasp cantrip (PDF p1, 4d8 at level 20) | ✅ Added |
| All 7 PCs | Missing `languages` field | ✅ Added |

**Not applied** (low priority — flavor / detailed inventory):
- Inventory deep-dive (PDF magic items: Braulo's Deck of Many Things; Meesmickle's Belt of Frost Giant Strength; RBG's huge magic-item kit; Sclorbo's Cape of the Mountebank). These are end-state campaign items, not FE Ch1 starting equipment.
- Personality/backstory minor text variations.
- Skill proficiency lists (not mechanically relevant for FE conversion).
