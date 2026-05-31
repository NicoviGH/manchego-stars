# Party Balance Analysis — Manchego Stars vs Typical FE Roster

> Evaluates the 7 PCs (plus 5 NPC recruits) against a typical Fire Emblem mid-game
> roster. Produced 2026-05-27 after cross-referencing all 7 PC PDF sheets vs
> `data/pc-sheets/*.json` and `campaigns/rime-of-the-frostmaiden/pcs/*.yaml`.
> See also: `docs/CLASSES.md` (roster), `docs/decisions.md` (class mapping), [combat-formulas.md](combat-formulas.md), `docs/CHAPTERS.md`.
>
> **Combat is vanilla FE.** Hits/damage use FE math; AC, saves, advantage, and the
> damage-type resistance multiplier are dropped (damage-type names are flavor labels).
> Casting is rationed by the **decision-B economy** — spells are finite-use items
> restocked with gold between chapters (no free refill); see decisions.md §Combat.
>
> **MVP = Prologue + Ch 1–8, played UNPROMOTED** (FE terms — there is no 5e-level scope;
> progression is FE class levels + FE promotions, and 5e features are flavor only). The big
> D&D-flavor headliners (Mystic Arcanums, 5th-level+ spells, the 4-beam Eldritch Blast, RBG's
> second cannon Brie, Dragon Wings) belong to the **post-MVP / promotion** era and appear below
> only as end-state reference — ignore them when judging MVP balance.

---

## TL;DR

- **Heavily caster-skewed:** 5 of 7 PCs cast spells. Their 5e flavor stats (WIS/INT/CHA) all fold to a single **MAG** stat in engine (see docs/decisions.md §Class Mapping), so they share one magic stat — what keeps them distinct is the **magic triangle** spread + role, not the stat.
- **Only 2 frontliners:** Braulo (Berserker) and Wolfram (General). Both are walls — Braulo has Hermit Crab natural armor (high FE DEF, big HP pool, 75% HP / 50% DEF growths) and Shell Defense; Wolfram has the party's highest DEF (General-tier). The party has no glass-cannon frontliner.
- **No dedicated healer in the PC roster.** Sclorbo (Bard 16) is the de-facto primary healer — Cure Wounds, Revivify, Mass Cure Wounds, Raise Dead all on his prepared list.
- **No flier in the PC roster** — Pinky (NPC) fills the flier slot from Ch1. (Rootis's old "Dragon Wings" flight-transform was **dropped** with the FE-strict ability purge — he's a stock Mage with no flight; his draconic identity is sprite/lore only.)
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

Rows are FE **weapon type / role** (not D&D damage type — damage types are flavor labels).

| Role | PC fill | NPC fill | Status |
|---|---|---|---|
| **Sword (physical)** | — | Trex (Thief), Baxby (Cavalier sword option) | ⚠️ NPC-only — the one triangle gap |
| **Axe (physical)** | Braulo (Berserker) | — | ✓ |
| **Lance (physical)** | Wolfram (General) | Baxby (Cavalier lance option) | ✓ |
| **Bow (ranged physical)** | RBG (Archer) | — | ✓ via RBG only |
| **Magic — full triangle** | Rootis (Anima), Marty (Light), Meesmickle (Dark); secondary Wolfram + RBG | The Mummy (Sage) | ✓ saturated, all 3 types |
| **Healer** | Sclorbo (primary), Marty (heal staff), RBG (cure wounds) | Basil (Ch4+) | ⚠️ Pre-Ch4 thin |
| **Cavalry** | — | Baxby (Ch1–2) | ✓ via NPC |
| **Flier** | Rootis (Dragon Wings — **post-MVP** unlock only) | Pinky (Ch1) | ✓ via NPC in MVP |
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

### 3. Caster overload — managed by triangle spread + the gold/durability economy

5 of 7 PCs cast spells; in FE you'd typically have 1–2 mages. What keeps it from breaking:
- **Magic-triangle spread, not stat spread.** All caster flavor stats fold to **MAG** (see docs/decisions.md §Class Mapping), so the casters do *not* have independent stats — they compete for the same MAG / magic-boost items. The real differentiator is the triangle: Rootis = Anima, Sclorbo = Light, Marty & Meesmickle = Dark (differentiated at promotion — Marty→Druid, Meesmickle→Summoner). See docs/decisions.md §Weapon & Magic Systems.
- **The decision-B economy is the limiter.** Spells are finite-use items restocked with **gold** between chapters (no free refill); cantrips are high-count (30–50 uses) rather than infinite. Casting is rationed by the convoy budget exactly like every FE weapon.
- **Marty as Druid** keeps a 1-range melee option (Shillelagh, a Dark tome); two Dark casters (Marty + Meesmickle) share that triangle slot, while Sclorbo covers Light and Rootis covers Anima.

**Concern:** because every caster's stat folds to MAG, all of them compete for the same magic-boosting rewards — schedule MAG boosters/items with that contention in mind.

### 4. Weapon-triangle coverage & the DEF/RES-mix rule

Damage types (slashing / necrotic / cold / fire…) are **flavor labels only** — there is no
resistance/vuln/immunity mechanic. What matters mechanically is the FE **weapon type** each unit
wields, which drives the vanilla weapon triangle (decomp `src/bmbattle.c sWeaponTriangleRules`):

- **Physical triangle:** Sword > Axe > Lance > Sword (±15 hit, ±1 atk)
- **Magic triangle:** Anima > Light > Dark > Anima (±15 hit, ±1 atk)

**How the 7 PCs map onto the triangles (army cross-reference):**

| PC | FE chassis | Weapon type | Triangle role |
|---|---|---|---|
| Braulo | Pirate → Berserker | **Axe** | physical |
| Wolfram | Knight → General | **Lance** | physical (+ armor) |
| Prof. RBG | Archer → Artillerist | **Bow** | ranged (triangle-neutral) |
| Marty | Monk → Summoner | **Light** | magic |
| Meesmickle | Shaman → Dark Sage | **Dark** | magic |
| Rootis | Mage → Sage | **Anima** | magic |
| Sclorbo | Dancer → Lore Bishop | support/heal | — |

Takeaways:
- The party already spans **both triangles**: Axe (Braulo) + Lance (Wolfram) physical; the **entire
  magic triangle** — Anima (Rootis) / Light (Marty) / Dark (Meesmickle). The only physical gap is
  **Sword**, filled by NPCs (Trex the Thief; Baxby the cavalier). **So we tune enemies, not reclass PCs.**
- Internal magic triangle: Rootis (Anima) beats Marty (Light) beats Meesmickle (Dark) beats Rootis
  (Anima). Relevant only against enemy casters, which are rare before ~Ch5.

**The DEF/RES-mix rule (enemy design).** The party fields **three offensive casters** (Marty,
Meesmickle, Rootis), all hitting **RES**. An all-brigand map (low RES) is a turkey-shoot for them; an
all-armor map starves them while the martials carry. So **every map's enemy roster should mix
DEF-targets and RES-targets** — physical bruisers/armor so the casters' RES-shred feels earned, plus
enough sturdier or RES-relevant bodies that the martials (Braulo / Wolfram / RBG) pull their weight.
This is standard vanilla-FE composition; it matters *more* for us than for FE8 because our player
roster skews more magical than FE8's early army (which hands you only Moulder the healer).

### 5. Speed / doubling distribution is healthy

SPD growth: Meesmickle 60, Sclorbo 60, Rootis 50, Marty 45, RBG 40, Braulo 40, Wolfram 15.

Standard FE design: one slow tank, several fast casters/dancers. Wolfram will be doubled by everything (intentional for General archetype). No tuning needed.

### 6. Movement on arctic maps

PCs MOV: 4 (Marty, Wolfram) — 6 (Braulo, RBG, Sclorbo). No fast cavalry. Maps are mostly arctic (snow / ice = difficult terrain in vanilla FE8).

**Mitigations available (FE-native only — no custom passives):**
- **Pinky** (NPC Pegasus Knight): flight ignores terrain; can Rescue/ferry a stranded unit.
- **Baxby** (NPC): high MOV mount.
- Vanilla FE tools: Restore/terrain play, chokepoint positioning, and the convoy sled framing.

The party has no fast cavalry and two MOV-4 units (Marty, Wolfram) on snow/ice (difficult
terrain). With the FE-strict purge there are **no custom mobility abilities** (the old "Snow
Ski," "Spreading Spores," and Rootis "Dragon Wings" are gone) — so arctic mobility leans on
Pinky + Baxby and on map/terrain design. Tune this via enemy placement and map openness rather
than per-unit movement buffs (memory [[manchego-stars-fe-level-design]]).

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
