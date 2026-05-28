# Design Decisions — Manchego Stars

> These decisions are **settled**. Do not re-open them without a strong reason.
> Add new decisions here when they are made. Date each entry.

---

## Engine & Tech Stack

**Base game: FE8 Sacred Stones (US) decomp (`fireemblem8u`)**
Using the near-complete matching decompilation from FireEmblemUniverse. The deliverable is a `.gba` file — no custom engine, no SRPG Studio, no Lex Talionis.
_Decided: May 2026_

**Compiler: agbcc (GCC 2.95.1)**
The decomp uses the original GBA compiler to produce byte-identical output. New engine modules also use agbcc. No C99 features, no VLAs, no designated initializers.
_Decided: May 2026_

**Engine/content split: engine in C (reusable), campaign data in YAML (swappable)**
All campaign-specific data (character names, chapter events, unit stats, maps, dialogue) lives in `campaigns/rime-of-the-frostmaiden/` and is injected at build time. Engine C code must be campaign-agnostic. A second campaign requires only a new `campaigns/` folder.
_Decided: May 2026_

---

## Combat System

> **2026-05-28 — Combat resolution reverted to vanilla FE.** The earlier "Hybrid
> d20/FE" decision (May 2026) is **superseded**. For playability the combat *rules*
> stay vanilla FE8 (hit%/avoid/might, FE crit, FE doubling); **D&D is flavor only**.
> The d20 survives at most as a **cosmetic flourish on a crit**, never as the
> resolution system. **AC, saving throws, and advantage/disadvantage are dropped**
> as mechanics (see below). Rationale (Nicolas): "the rules need to stay FE or the
> game won't play the same" — the FE-strictness spine. The four implementation
> sub-questions were ratified by Nicolas on 2026-05-28: d20 = cosmetic-crit-only,
> saves dropped, AC dropped, advantage dropped.

**Combat resolution: vanilla FE8 hit / avoid / might**
Hit, avoid, might, and crit are computed exactly as vanilla FE8 (`bmbattle.c`,
left intact). No d20 attack roll; no Armor Class. The D&D reskins below are
flavor/UI only and never change the math.
_Decided: 2026-05-28 (supersedes the May 2026 hybrid-d20 decision)_

**d20: cosmetic crit flourish only**
When an FE crit fires, the battle UI may play a brief "d20 lands on 20" flourish
for D&D feel. It does not gate or alter the hit — resolution is pure FE. This is
the only place the die appears.
_Decided: 2026-05-28_

**AC (Armor Class): dropped as a mechanic**
Defense is FE's `DEF` (vs physical) and `RES` (vs magic), plus speed/luck/terrain
avoid — exactly as vanilla FE. There is no separate to-hit target. The `ac:` source
values and `d20_fields` blocks in the PC YAMLs are retained only as
flavor/source-of-record; nothing in resolution reads them.
_Decided: 2026-05-28_

**Saving throws: dropped → vanilla FE magic**
No DCs, no save rolls. Status staves (Sleep/Silence/Berserk/Poison) always-hit per
vanilla FE; offensive spells resolve through FE magic combat (MAG vs RES, FE
hit/avoid). The `save:` / `save_dc:` fields throughout the PC YAMLs are flavor only.
_Decided: 2026-05-28_

**Advantage / disadvantage: dropped**
No advantage concept. Positioning matters through standard FE terrain bonuses and
the weapon triangle only. Abilities previously written as granting "advantage"
either reflavor onto an FE-native effect or drop (see `fe-mechanic-map.md` ⚠ section).
_Decided: 2026-05-28_

**Damage: vanilla FE armor-subtraction model (nothing layered under it)**
`Damage = Might − Defender.DEF/RES`. With the d20 layer gone, weapon damage uses
**FE fixed might** (not rolled `WeaponDice`); tune might from the 5e die's average.
No D&D multiplier is applied — see the damage-type decision below. Do NOT import 5e
HP values — FE growth tables cap HP ~60–80.
_Decided: 2026-05-28 (supersedes the May 2026 rolled-dice damage)_

**Critical hits: vanilla FE (skill-based rate, ×3 damage)**
FE's native crit — crit rate from SKL/weapon, triple damage. The earlier "roll
weapon dice twice on nat 20" is dropped with the d20 resolution. Killer/high-crit
units use vanilla FE crit-rate bonuses.
_Decided: 2026-05-28 (supersedes the May 2026 roll-twice crit)_

**Doubling: vanilla FE (unchanged)**
`AttackSpeed_attacker − AttackSpeed_defender ≥ 4` → attacker attacks twice.
_Decided: May 2026 (still current)_

**Damage-type resistance/vulnerability/immunity: DROPPED as a mechanic**
The 13-damage-type resistance multiplier (×0.5 / ×2 / ×0) has **no vanilla FE analogue**
and would modify FE damage under the hood — exactly the kind of D&D bolt-on we're avoiding
(Nicolas, 2026-05-28: "that's not part of the FE combat system… it should not conflict with
vanilla FE under the hood"). So:
- **Damage types are flavor labels only** — a weapon/tome carries a D&D damage-type name + icon
  for descriptions and UI. No resistance/vuln/immunity computation runs in damage resolution.
- **Iconic matchups use vanilla FE weapon effectiveness.** FE8 already has effective weapons
  (Hammer vs armor, Wyrmslayer vs dragons, etc.). When a vulnerability genuinely matters to
  play — e.g. "fire melts ice trolls" — flag the relevant weapon **effective** vs that enemy
  class. That's vanilla-FE-native, not a new multiplier. Use sparingly; most damage types stay
  pure flavor.
- **No `resistance_table.c` / resistance bitmap.** The `engine/damage-types/` module reduces to
  a flavor-label tag (for UI) — no resistance engine.
_Decided: 2026-05-28 (supersedes the May 2026 "13 damage types with resistance per class")_

**Hit-rate tuning: vanilla FE, no special floor needed**
With vanilla FE hit/avoid restored, FE8's native 70–95% hit norms apply directly —
the old d20-variance problem and the "skill floor" mitigation are moot. Tune
per-chapter via enemy stats/terrain as in any FE hack.
_Decided: 2026-05-28 (supersedes Option A d20 hit-rate tuning)_

---

## Weapon & Magic Systems

**Weapon triangle: Slashing > Bludgeoning > Piercing (reskinned, same mechanics)**
Swords → Slashing, Axes/Hammers → Bludgeoning, Lances/Spears → Piercing. Bonus identical to vanilla: +1 ATK, +15 to-hit modifier. Triangle advantage = mechanical bonus, not a new system.
_Decided: May 2026_

**Magic trinity: Radiant > Necrotic > Elemental (reskinned)**
Replaces Light > Dark > Anima. Same triangle mechanics, new labels.
_Decided: May 2026_

**13 damage-type labels (flavor only — no resistance mechanic)**
Types: slashing, piercing, bludgeoning, fire, cold, lightning, thunder, poison, acid, necrotic, radiant, force, psychic. These are **flavor tags** on weapons/tomes for descriptions + UI. **No per-class resistance bitmap, no ×0.5/×2/×0 multiplier** (reverted 2026-05-28 — see Combat System §). Iconic vulnerabilities use vanilla FE weapon **effectiveness** instead.
_Decided: 2026-05-28 (supersedes the May 2026 resistance-bitmap decision)_

**Spell-slot tomes: not buyable, refill at chapter start (= long rest)**
Casters receive tomes at recruitment or through story events. Cannot purchase more. Cantrip tomes (0th level) are infinite-use and cannot be bought either. Mundane tomes are buyable.
_Decided: May 2026_

---

## Economy

**Gold Pieces (GP) replace FE gold (same mechanic, D&D label)**
Armory = weapon shop. Vendor = item shop. FE8 world-map shop system preserved.
_Decided: May 2026_

**No arena**
FE8's arena is removed. Wolfram's Forge fills the "spend gold to get stronger" role.
_Decided: May 2026_

---

## Distribution & Scope

**Distribution: private, pre-patched ROM sent directly to 7 players**
No patch file, no RomHack Plaza listing, no public hosting. Non-SRD content (Artificer, Circle of Spores, homebrew races) can be used freely for this private distribution.
_Decided: May 2026_

**Permadeath: player choice via FE8's Casual/Classic toggle**
The toggle ships as-is from vanilla FE8. In-fiction flavor for Casual retreats: "retreated to the sled" / "carried to safety by Baxby."
_Decided: May 2026_

**MVP scope: 7 chapters, ending at the Revel's End cliffhanger**
Chapter 7 ends in a scripted defeat. Text: "You wake up on the road to Revel's End..." Credits roll. Chapters beyond the DM notes require a future writing session.
_Decided: May 2026_

---

## Art & Audio

**Maps: hand-drawn in Tiled, NOT AI-generated**
Use community Frostmaiden maps (from `docs/frostmaiden-resources.md`) as layout references. Use FEUniverse map pool for tileset/format guidance. Agents help with unit placement and events, never spatial layout.
_Decided: May 2026_

**Audio: vanilla FE8 soundtrack for MVP**
Investigate Frostmaiden Spotify album + community soundtracks as stretch-goal custom tracks post-ship.
_Decided: May 2026_

**Portraits: AI-generated base from D&D Beyond art → manual cleanup → FE pixel art conversion**
Specs: 80×72 main portrait, 32×32 mini portrait, 16-color GBA palette.
_Decided: May 2026_

**Sprites: recolored vanilla FE8 sprites, modified via Nanobanana 2 for homebrew races**
Custom sprites (Grells, Messie, ice trolls) sourced from FEUniverse community or Nanobanana 2 edits.
_Decided: May 2026_

**Cutscene art: portrait-based dialogue only for MVP**
CG-style illustrations (Braulo shackle break, Messie rising, Revel's End fade) are post-ship stretch goals.
_Decided: May 2026_

---

## Class Mapping Refinements (2026-05-27 audit)

**Marty: base class is Monk, not Shaman**
Original mapping had both Marty (Druid/Spores) and Meesmickle (Warlock/Fiend) on the FE8 Shaman chassis — identical sprites. Moved Marty to Monk (FE8 Light-magic male caster, Saleh-line) for visual differentiation. Promoted form remains Summoner. Some palette reflavor needed for the Light→Necrotic visual transition.
_Decided: 2026-05-27_

**Sclorbo: promoted class is Lore Bishop, not Lore Bard**
PDF audit (2026-05-27) confirmed Cure Wounds, Revivify, Mass Cure Wounds, and Raise Dead all prepared on Sclorbo's Bard 16 list. He is the party's primary healer/reviver. Lore Bishop is a custom hybrid: Dancer chassis at base, Bishop-tier healing at promotion, Dance retained as a unique skill. **Balance lever:** per turn, Sclorbo can either Dance/Refresh OR Cast, not both. Combined with chapter-gated heal tiers and finite spell slots, prevents one-man support engine.
_Decided: 2026-05-27_

**Rootis: Dragon Wings is a Manakete-style class transform**
Dragon Wings (Sorcerer 14 feature, end-state) is implemented as a toggleable class transform reusing FE8's Manakete/Myrrh code path. Foot form = Mage (Ice), Dragon form = custom flier Sage with terrain-ignoring movement. Each toggle consumes 1 Sorcery Point to prevent spam.
_Decided: 2026-05-27_

**RBG fields two sentient cannons: Pepperjack (Ch 1) and Brie (later)**
RBG's deployable summons are two named automatons:
- **Pepperjack** — first cannon, available from Ch 1
- **Brie** — second cannon, unlocked at a later chapter (TBD). Pepperjack's girlfriend.

Both speak Pokemon-style — they can only say their own names ("Pepperjack!" / "Brie!"). Adjacency / support dialogue between them uses this convention. Combined portrait at `data/portraits/pepperjack-and-brie.jpeg`. Source: `References/PCs/Pepperjack and Brie Portrait.jpeg`.
_Decided: 2026-05-27_

**FE stat column folds 5e stats to FE stats**
Class-mapping docs surface FE engine stats (STR/DEX/MAG/etc.) instead of 5e stats (WIS/INT/CHA). All magic-stat 5e classes (WIS Druid, INT Artificer, CHA Warlock/Sorcerer/Bard) use MAG in engine. Flavor distinctions stay in YAML metadata, not class mapping.
_Decided: 2026-05-27_

**Wolfram & RBG hybrid casters: physical chassis primary, spells secondary**
Both PCs keep their physical-class chassis (Knight, Archer). Spell access is a layered overlay tuned by:
- Tight spell-slot economy (chapter-refresh, no purchasing)
- Cantrips are infinite but lower damage tier than dedicated casters
- Primary identity stat is physical (STR Wolfram, DEX RBG); MAG is secondary
_Decided: 2026-05-27_

---

## Open Questions (not yet decided)

See `docs/PRD.md §13` for the full list. Key unresolved items:
- Signature moments for Marty, Meesmickle, Rootis, Sclorbo (Nicolas to recall)
- Velynne Harpell's arc (check published adventure)
- Sephek Kaltro — did he appear in the campaign?
- Messie's specific Bremen function (shop? services? quest-giver?)
- Unit struct save budget for D&D fields (audit in Phase 1, issue #10)
