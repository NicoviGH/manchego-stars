# Manchego Stars — Product Requirements Document

> **Version:** 1.0 — May 27, 2026
> **Author:** Nicolas (via Claude)
> **Status:** Draft — ready for review
> **Source documents:** `campaign-brief.md`, `research.md`

---

## 1. Problem Statement

Nicolas ran a multi-year D&D 5e campaign (*Rime of the Frostmaiden*) with 6 friends. The campaign is over, but the shared memories — a hermit crab barbarian smashing shackles, a mushroom druid talking down a plesiosaur, a ratfolk artificer executing a kobold at gunpoint — deserve more than a group chat. The group has no way to *replay* their story.

**This project turns that campaign into a playable GBA tactics game**, built as a ROM hack of *Fire Emblem: The Sacred Stones* (FE8). The 7 PCs become playable units. The DM's narrative beats become chapters. Combat uses **vanilla FE8's tactics rules** (hit/avoid/might/crit) so the game plays like Fire Emblem; the D&D campaign supplies the characters, classes, damage types, spells-as-tomes, and flavor on top. The result is a `.gba` file the group can play on any emulator or flash cart — their adventure, in their pocket.

**Who is affected:** The 7 players from the campaign (private distribution only).

**Impact of not solving it:** Nothing breaks — this is a passion project. But the window for this kind of thing closes as life moves on. Building it now, while the memories are fresh and the tools are good enough, is the moment.

---

## 2. Goals

1. **Ship a playable `.gba` ROM** covering the full DM-notes arc (7 chapters, from the goblin iron quest through the Eastway ambush / Revel's End cliffhanger) that runs on stock GBA emulators and flash carts.
2. **Keep Fire Emblem's combat, dress it in D&D** — preserve FE's grid tactics, hit/avoid/might resolution, permadeath toggle, weapon triangle, growth-rate leveling, and FE crit. Layer D&D *flavor* on top: D&D damage-type labels (flavor only — no resistance multiplier; the triangle stays FE-native), spells as finite-use tomes that deplete and restock with gold (decision B), and a cosmetic d20 flourish on crits. Iconic matchups use vanilla FE weapon effectiveness. The rules stay FE so it plays like FE.
3. **Faithfully represent all 7 PCs** as playable units with correct classes, abilities, progression arcs, and personality (portraits, dialogue, signature moments).
4. **Build the engine as reusable** — separate engine code (damage types, spell slots, status/hazards, UI reskin) from campaign data (PCs, chapters, maps, dialogue). A second campaign (Curse of Strahd, a homebrew, etc.) should require only a new `campaigns/` folder, zero engine changes.
5. **Keep the project tractable** — session-driven Claude Code workflow (no autonomous agent loops), one feature per session, `make` green at end of every session. Target cost: ~$60–200 for the full MVP.

---

## 3. Non-Goals

1. **Public release or distribution.** This is for 7 people. No patch hosting, no RomHack Plaza listing, no OGL/SRD compliance beyond what's needed for the codebase itself. The ROM is sent directly as a pre-patched file.
2. **Full campaign coverage beyond the DM notes.** The MVP ends at the Revel's End cliffhanger (Chapter 7). Content beyond that requires a future writing session to outline. Don't spec what doesn't exist yet.
3. **Custom engine (Lex Talionis, SRPG Studio, etc.).** The deliverable is a `.gba` file, not a standalone executable. The FE8 decomp is the foundation. Period.
4. **A generic "D&D campaign editor" or campaign DSL.** The engine is *organized* for reuse (YAML data, campaign folders), but we don't build editor tooling, a class-definition language, or a GUI campaign builder. That's scope creep. We build exactly what Frostmaiden needs, structured so a second campaign is easy.
5. **Original music composition or custom GBA audio conversion** for MVP. Ship with vanilla FE8 soundtrack. Frostmaiden album tracks and community audio are stretch goals explored post-ship.
6. **Fully AI-generated maps.** FE Infinity validated that LLMs produce bad tactical maps. Maps are hand-drawn in Tiled/FEBuilder using community Frostmaiden maps (from `frostmaiden-resources.md`) as layout references, plus the 60+ FE community map pool on FEUniverse for tileset and format guidance. The agent helps with everything *around* maps (unit placement, events, dialogue), not spatial layout.

---

## 4. Target Users & Personas

**Primary (and only) audience:** The 7 players from the Icewind Dale campaign.

- They all know D&D 5e mechanics intimately (they played for years).
- Most have at least passing familiarity with Fire Emblem or GBA tactics games.
- They care about *their* characters and *their* story moments above all. Generic Fire Emblem content is filler; campaign-specific callbacks are gold.
- They will play on emulators (mGBA, RetroArch) on desktop or mobile, or on GBA flash carts.

**Secondary:** Nicolas (the DM / developer). He needs the toolchain to be debuggable, the build to be reliable, and the agent workflow to be cost-efficient.

---

## 5. User Stories

### 5.1 Player Experience

- **As a player,** I want to select my PC from the roster in Chapter 1 and see their portrait, stats, and class so that I recognize my character immediately.
- **As a player,** I want a brief d20 flourish when I land a critical hit so that crits feel like a D&D nat-20 moment — without changing how combat is actually resolved (it stays Fire Emblem hit/avoid).
- **As a player,** I want each weapon/tome to show a D&D damage-type label and icon (the triangle itself staying FE-native: Sword/Axe/Lance, Anima/Light/Dark) so that my gear reads like 5e while the triangle plays like FE.
- **As a player,** I want spell tomes that deplete in use and are restocked with gold between chapters so that casters share the same resource economy as martials (decision B).
- **As a player,** I want to recruit NPC allies (Trex, Basil, The Mummy) as the story progresses so that the roster grows like a real Fire Emblem game.
- **As a player,** I want to choose Casual or Classic mode (FE8's existing toggle) so that permadeath is my choice, not forced.
- **As a player,** I want to see campaign-specific dialogue and story beats (the kobold execution, Messie becoming Speaker, Braulo smashing shackles) so that the game feels like *our* campaign, not a generic adventure.
- **As a player,** I want Chapter 5 (The Maer Monster) to feel like a real boss fight where I discover Marty can Talk to Messie — rewarding me for paying attention to the story, not for following a tutorial prompt.
- **As a player,** I want Chapter 7 (The Eastway Ambush) to end in a scripted defeat so that the cliffhanger landing at Revel's End hits dramatically.

### 5.2 Developer / Builder Experience

- **As the developer,** I want `make CAMPAIGN=rime-of-the-frostmaiden` to produce a `.gba` file from source so that the build is reproducible and CI-gated.
- **As the developer,** I want each PC defined in a single YAML file (stats, class, growth rates, inventory, portrait ref) so that I can iterate on balance without touching C code.
- **As the developer,** I want each chapter defined in YAML (units, objectives, dialogue, map reference) so that chapter content is separable from engine logic.
- **As the developer,** I want `tools/build-campaign.ts` to read a campaign folder and inject its data into the decomp before `make` so that the engine/content boundary is enforced automatically.
- **As the developer,** I want the mGBA MCP bridge so that Claude Code can boot the ROM, take screenshots, and read memory addresses to verify changes without manual testing.

---

## 6. Architecture

### 6.1 System Overview

The project is a **patched FE8 ROM** built from the `fireemblem8u` C decompilation, with engine modifications layered on top and campaign content injected at build time.

```
┌─────────────────────────────────────────────────────────────┐
│                     Build Pipeline                          │
│                                                             │
│  campaigns/rime-of-the-frostmaiden/                         │
│    ├── campaign.yaml                                        │
│    ├── pcs/*.yaml          ──┐                              │
│    ├── npcs/*.yaml           │                              │
│    ├── chapters/*.yaml       ├── tools/build-campaign.ts    │
│    ├── maps/*.tmx            │   reads YAML + assets,       │
│    ├── portraits/*.png       │   injects into decomp        │
│    └── events/*.ea           ──┘   data tables               │
│                                      │                      │
│  engine/                             │                      │
│    ├── combat-fx/            ──┐     │                      │
│    ├── damage-types/           │     │                      │
│    ├── spell-slots/            ├─ C patches applied to      │
│    ├── class-defs/             │  fireemblem8u/src/          │
│    └── ui/                   ──┘     │                      │
│                                      ▼                      │
│  fireemblem8u/ (submodule)  ──── agbcc ──── fireemblem8.gba │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Repository Structure

```
manchego-stars/
├── README.md
├── CLAUDE.md                  # Agent conventions, key file pointers
├── Makefile                   # `make CAMPAIGN=rime-of-the-frostmaiden`
├── .claude/
│   ├── commands/              # /build, /test-chapter, /translate-pc
│   └── settings.json          # Model picks per command
├── .mcp.json                  # MCP servers (mGBA-script, srd-cache)
│
│── ENGINE (reusable) ─────────────────────────────────────────
├── fireemblem8u/              # FE8 decomp (git submodule)
├── engine/
│   ├── combat-fx/             # cosmetic crit flourish only (combat resolution stays vanilla FE)
│   │   └── crit_anim.c        # cosmetic "d20 lands on 20" flourish on FE crit
│   ├── damage-types/          # flavor damage-type label tag (UI/descriptions only — no resistance)
│   │   └── damage_type.h      # Enum: slashing, piercing, bludgeoning, fire, cold... (labels)
│   ├── spell-slots/           # Per-unit spell slot tracker
│   │   ├── spell_slots.c      # Track tome charges; deplete + gold-restock (decision B)
│   │   └── spell_slots.h
│   ├── class-defs/            # D&D-flavored FE class table
│   │   └── dnd_classes.c      # 12 base + custom (Artificer, Metallurgist)
│   └── ui/                    # Combat preview reskin (D&D labels over FE forecast)
│       ├── combat_preview.c   # damage-type icon (triangle stays FE-native)
│       └── crit_flourish.c    # cosmetic d20-on-crit animation
│
│── CONTENT DATA (shared reference) ───────────────────────────
├── data/
│   ├── srd-snapshot.json      # Frozen pull from dnd5eapi.co
│   ├── open5e-snapshot.json   # Frozen pull from Open5e
│   └── homebrew/
│       ├── classes/
│       │   ├── artificer.yaml
│       │   └── metallurgist.yaml
│       ├── subclasses/
│       │   ├── circle-of-spores.yaml
│       │   ├── path-of-the-berserker.yaml
│       │   ├── the-fiend.yaml
│       │   ├── draconic-bloodline.yaml
│       │   ├── college-of-lore.yaml
│       │   └── school-of-the-smith.yaml
│       └── races/
│           ├── hermit-crab.yaml
│           ├── sporemaster.yaml
│           ├── vampire-tabaxi.yaml
│           ├── snowperson.yaml
│           ├── chwinga.yaml
│           ├── underfolk.yaml
│           └── mineralscale-drakeborn.yaml
│
│── CAMPAIGNS ─────────────────────────────────────────────────
├── campaigns/
│   └── rime-of-the-frostmaiden/
│       ├── campaign.yaml      # Title, chapter count, start level, level cap
│       ├── pcs/
│       │   ├── braulo.yaml
│       │   ├── marty.yaml
│       │   ├── meesmickle.yaml
│       │   ├── prof-rbg.yaml
│       │   ├── rootis.yaml
│       │   ├── sclorbo.yaml
│       │   └── wolfram.yaml
│       ├── npcs/
│       │   ├── baxby.yaml
│       │   ├── pinky.yaml
│       │   ├── trex.yaml
│       │   ├── basil.yaml
│       │   ├── the-mummy.yaml
│       │   ├── messie.yaml
│       │   └── duvessa-shane.yaml
│       ├── enemies/
│       │   ├── goblin.yaml
│       │   ├── kobold.yaml
│       │   ├── grell.yaml
│       │   ├── frost-druid.yaml
│       │   ├── dorbulgruf.yaml
│       │   ├── easthaven-guard.yaml
│       │   └── ice-troll.yaml
│       ├── chapters/
│       │   ├── ch01-the-iron-trail.yaml
│       │   ├── ch02-cold-welcome.yaml
│       │   ├── ch03-the-termalaine-mine.yaml
│       │   ├── ch04-the-elven-tomb.yaml
│       │   ├── ch05-the-maer-monster.yaml
│       │   ├── ch06-blood-in-bremen.yaml
│       │   └── ch07-the-eastway-ambush.yaml
│       ├── maps/               # .tmx (Tiled) or FEBuilder exports
│       ├── portraits/          # FE-format PNGs per character
│       └── events/             # EA buildfile scripts per chapter
│
│── TOOLS ─────────────────────────────────────────────────────
├── tools/
│   ├── pull-srd.ts            # One-shot SRD + Open5e downloader
│   ├── map-class.ts           # 5e class → FE class mapper
│   ├── build-campaign.ts      # Reads campaign folder → injects into decomp → make
│   └── build-events.ts        # YAML → EA buildfile codegen
│
│── DOCS ──────────────────────────────────────────────────────
└── docs/
    ├── decisions.md           # Human-written design decisions (no re-litigation)
    ├── combat-formulas.md     # vanilla-FE combat reference + D&D flavor layer
    ├── class-mapping.md       # 5e class → FE class table
    └── session-log.md         # What was accomplished each session
```

### 6.3 Toolchain

| Tool | Role | Notes |
|---|---|---|
| `fireemblem8u` | C decompilation of FE8 (Sacred Stones US) | Git submodule. Near-complete matching decomp. |
| `agbcc` | GCC 2.95.1 — the matching GBA compiler | Produces byte-identical ROM from decomp source. |
| `devkitARM` | GNU Arm toolchain for non-matching builds | Used alongside agbcc for new C modules. |
| `ColorzCore` (Event Assembler) | Assembles event scripts, dialogue, unit placement | Community standard for FE content scripting. |
| `lyn` | Auto-hooks C functions into vanilla code | Bridges custom C into the decomp's call sites. |
| `Png2Dmp` + `PortraitFormatter` | Graphics pipeline | Converts PNGs to GBA-compatible portrait data. |
| `mGBA` | Debug emulator with Lua scripting | Primary test environment. MCP bridge target. |
| `FEBuilder` | GUI ROM editor | Escape hatch for portrait insertion, sanity checks. |
| `Tiled` | Map editor | Hand-draw .tmx maps for each chapter. |
| `Nanobanana 2` | AI sprite editing | Modify vanilla FE8 sprites for homebrew races. |
| `Claude Code` | AI-assisted development | Session-driven, human-in-the-loop coding partner. |

### 6.4 Engine/Content Contract

The engine makes the following assumptions about any campaign folder:

**Engine provides:**
- Vanilla FE8 combat resolution (hit/avoid/might/crit/doubling — left intact)
- Damage-type *flavor* labels on weapons (13 types; UI/descriptions only — no resistance mechanic)
- Vanilla FE weapon effectiveness for iconic matchups (FE-native; e.g. fire vs ice trolls)
- Status effects beyond vanilla (`engine/status`) and hazard tiles (`engine/hazards`)
- Spell-tome charge tracking per unit (deplete + gold-restock between chapters)
- Combat-preview reskin (D&D damage-type icons; triangle stays FE-native) and a cosmetic d20 flourish on crits
- FE-native weapon triangle (Sword > Axe > Lance) with D&D damage-type labels on weapons
- FE-native magic triangle (Anima > Light > Dark) with D&D element labels on tomes
- Growth-rate leveling (vanilla FE, untouched)
- Permadeath toggle (vanilla FE8 Casual/Classic)
- Support conversations (vanilla FE8 system)

**Campaign folder must provide:**
- `campaign.yaml` — metadata (title, chapter count, starting level, level cap)
- `pcs/*.yaml` — one per playable character (5e stats, FE stats, growths, inventory, portrait ref, class mapping)
- `npcs/*.yaml` — recruitable and story NPCs
- `enemies/*.yaml` — enemy units and bosses per chapter
- `chapters/*.yaml` — chapter definition (objective, map ref, unit placement, dialogue triggers, recruitment events, win/lose conditions)
- `maps/*.tmx` — hand-drawn Tiled maps or FEBuilder exports
- `portraits/*.png` — FE-format character portraits
- `events/*.ea` — Event Assembler scripts for cutscenes and scripted events

**The boundary rule:** If a feature doesn't work without Frostmaiden-specific data, it belongs in `campaigns/`, not `engine/`. If you're about to hardcode a character name or chapter event in C, stop — it goes in YAML.

### 6.5 Combat System — Vanilla FE8 (D&D flavor on top)

> Combat *rules* are vanilla FE8 so it plays like Fire Emblem; D&D supplies flavor
> (incl. damage-type labels). Full reference: `combat-formulas.md`. The engine **does
> not** replace `bmbattle.c`.

**Attack Resolution — vanilla FE (unchanged):** FE8's hit% vs avoid (two-RN), with the
weapon-triangle hit bonus. **No d20, no Armor Class, no advantage/disadvantage.** AC
values in the PC sheets are flavor/source-of-record only.

**Damage — vanilla FE armor-subtraction (no D&D multiplier):**

```
Damage = max(0, Might − Defender.DEF/RES)     # Might = WeaponMight + STR (or MAG)
```

**No resistance/vulnerability/immunity multiplier** — it has no vanilla FE analogue and would
modify FE damage under the hood, so it is not a mechanic. Damage types are flavor labels only. Where a
matchup genuinely matters (fire vs ice trolls), flag the weapon **effective** via vanilla FE's
existing effectiveness system — FE-native, not a multiplier.

Weapon Might is **fixed FE might** (tuned from the 5e die's average), not a rolled die.

**Critical Hits — vanilla FE:** crit rate from SKL/weapon/skill; crit damage ×3 (FE's
native triple). When a crit fires, the UI may play a **cosmetic d20-lands-on-20
flourish** for D&D feel — purely visual, never gating the hit.

**Doubling (vanilla FE):**

```
If AttackSpeed_attacker − AttackSpeed_defender ≥ 4: attacker attacks twice
```

**Magic & staves — vanilla FE (no saving throws):** offensive spells resolve as FE
magic combat (MAG vs RES, FE hit/avoid). Status staves (Sleep/Silence/Berserk/Poison)
**always hit** in range; healing staves always succeed. There are **no DCs or save
rolls**; `save:` / `save_dc:` in the PC YAMLs are flavor metadata only.

### 6.6 Weapon Triangle — vanilla FE (damage-type names are flavor)

**Physical:**
```
Sword > Axe > Lance > Sword
```
Bonus: +1 ATK / +15 to-hit (vanilla FE triangle, `src/bmbattle.c`). D&D damage-type names
(slashing/bludgeoning/piercing/…) are cosmetic per-weapon labels, NOT a relabeling of the
triangle — a claw wolf and an axe bandit are both the **axe type** and read identically.

**Magic:**
```
Anima > Light > Dark > Anima
```
Our casters span it: Rootis = Anima, Marty = Light, Meesmickle = Dark.

**Iconic matchups via vanilla FE weapon effectiveness (no resistance multiplier):**

There is **no resistance/vulnerability/immunity mechanic**. The table below is
*flavor* — except the **Vulnerable** column, which is realised through vanilla FE **weapon
effectiveness** when a matchup matters to play (flag a weapon `effective` vs that enemy class, the
same way Hammers are effective vs armor). Resistances/immunities are narrative flavor only.

| Creature | Flavor (resist/immune) | Plays as: FE effectiveness |
|---|---|---|
| Skeleton | resists piercing/slashing | bludgeoning weapons **effective** vs skeletons |
| Zombie | immune poison (flavor) | bludgeoning / radiant weapons **effective** vs zombies |
| Frost Druid | resists cold (flavor) | fire weapons **effective** vs frost druids |
| Ice Troll | resists cold (flavor) | fire weapons **effective** vs ice trolls |
| Grell | immune lightning (flavor) | — (no effectiveness; pure flavor) |

### 6.7 Class System

**PC Class Mappings:**

| PC | 5e Class | FE Base Class | FE Promoted Class | Primary Stat | Unique Mechanic |
|---|---|---|---|---|---|
| Braulo | Barbarian (Berserker) | Pirate | Berserker | STR | Rage (consumable item: +might and **+DEF** while active — the 5e B/P/S "resistance" becomes an FE-native defense buff, not a multiplier). Shell Defense (command: +DEF, can't move). Hermit Crab natural armor → high FE DEF (flavor "AC 17"). |
| Marty | Druid (Circle of Spores) | Monk (custom Druid) | Summoner (custom) | MAG | Halo of Spores (innate AoE reaction: 1d10 necrotic). Symbiotic Entity (+temp HP). Fungal Infestation (summon). Moved off Shaman in 2026-05-27 audit to differentiate from Meesmickle. |
| Meesmickle | Warlock (The Fiend) | Shaman (Dark) | Dark Sage | MAG | Eldritch Blast (high-count dark tome per decision B; 1–2 beams in MVP, 4 at endgame). Dark One's Blessing (temp HP on kill). Hurl Through Hell (1/chapter nuke, post-MVP). |
| Prof. RBG | Artificer (Artillerist) | Archer | Artillerist (custom promotion) | DEX / MAG | Fonduedler (personal ranged firearm, 1d10, DEX). **Pepperjack** (deployable Eldritch Cannon — Flamethrower / Force Ballista / Protector modes; 2 simultaneous at endgame, AC 18, 100 HP each). Flash of Genius (reaction: +5 ally save). Infusions (between-chapter item crafting). |
| Rootis | Sorcerer (Draconic — White Dragon) | Mage (Ice) | Sage | MAG | Metamagic (Twinned = attack twice, Empowered = reroll damage). **Dragon Wings = Manakete-style class transform** (toggle on promotion: flier MOV, ignores terrain; consumes 1 Sorcery Point per toggle). Cold/fire affinity is **flavor** (no resistance mechanic); "heals from cold" maps to an FE-native **healing terrain** (snow/ice tiles heal him). |
| Sclorbo | Bard (College of Lore) | Dancer (custom Bard) | Lore Bishop (custom) | MAG | Bardic Inspiration (d12 buff to adjacent ally). Cutting Words (debuff reaction). Dance/Refresh action. Cleric-tier heal kit (Cure Wounds in MVP; Revivify / Mass Cure / Raise Dead are post-MVP). **Balance: Dance and Cast are mutually exclusive per turn.** |
| Wolfram | Metallurgist (Smith) | Knight | General | STR + MAG | Forge ability (upgrade ally armor/weapons between chapters). AC 26 equivalent (highest DEF in party). Feral Strike (Bite + Claws bonus attacks). Shield spell (reaction). Mystic Arcanums (Investiture of Stone, Forcecage). Spell access is a secondary role; STR-physical is primary. |

> **AC / save / "+ally save" values in this table are flavor/source-of-record.** Combat
> is vanilla FE: defense is FE `DEF`/`RES` + avoid, not Armor Class, and there are no
> saving throws. Braulo's "AC 17" and Wolfram's "AC 26" map to high FE `DEF`.

**NPC Unit Mappings:**

| NPC | Role | FE Class | Join Chapter | Notes |
|---|---|---|---|---|
| Baxby | Mount / escort | Cavalier (axe-beak variant) | Ch 1–2 | Rideable. Low combat stats, high MOV. |
| Pinky | Companion / flyer | Pegasus Knight (homunculus) | Ch 1 (with RBG) | Flying, high MOV, can Rescue. **No permadeath:** when defeated, drops a Red Ruby on his tile. If RBG picks up the Ruby, he can use it to re-summon Pinky adjacent. Unique respawn mechanic — fits homunculus lore. Fills the party's flyer gap. |
| Trex | Recruit / utility | Thief (kobold) → Rogue | Ch 3 | Lockpick, Steal, high SPD. Low combat stats, high growth. Cosmetic wings on sprite (no flight). Fills the party's thief/utility gap. Promotes to Rogue or Assassin. |
| Basil | Recruit / healer | Cleric (custom shrub) | Ch 4 | Goodberry staff (unique healing). |
| The Mummy | Recruit / tank | Sage (undead) | Ch 4 | High DEF, uses both physical and magic. |

### 6.8 Spell Slot → Tome Uses Mapping

| 5e Slot Level | Tome Uses | FE Tier Equivalent |
|---|---|---|
| Cantrip (0) | ∞ (0xFF) | Basic tome (Iron equivalent) |
| 1st | 8 | Low-tier tome |
| 2nd | 6 | Mid-tier tome |
| 3rd | 4 | High-tier tome (Bolting range) |
| 4th | 3 | Silver-tier |
| 5th | 2 | Brave-tier |
| 6th+ | 1 | Legendary / personal weapon |

All spell-slot tomes refill to max uses at the start of each chapter (equivalent to a long rest).

### 6.9 Economy & Shop System

Fire Emblem's gold-and-shop loop is a core part of the game feel — earning gold from chapter combat, buying weapons and items between chapters, managing limited inventories. This must be preserved and reskinned for D&D.

**What stays from FE (reskinned):**
- **Gold → Gold Pieces (GP).** Same mechanic, D&D label. Enemies drop GP on defeat. Chests and villages yield GP and items. Chapter completion bonuses in GP.
- **Shops between chapters.** The world-map shop system (FE8's armory/vendor) remains. Shops are themed per town: Bryn Shander (general goods, basic weapons), Targos (cold-weather gear, better armor), Termalaine (gems as trade goods, mining equipment), Bremen (water-themed items, potions — run by Messie after Ch 6), Easthaven (N/A — no friendly visit).
- **Armory = Weapon shop.** Sells swords, axes, lances, bows — reskinned with D&D names (Longsword, Warhammer, Javelin, Longbow) and organized by damage type.
- **Vendor = Item shop.** Sells consumables: Vulneraries → Healing Potions, Antitoxin → Antidote, Torches, Door Keys, etc.
- **Item management.** 5-slot inventory per unit (vanilla FE). Forces real choices about what to carry. Spell-slot tomes take inventory slots like any weapon.

**D&D-flavored additions:**
- **Magic item shops (limited).** Rare shops in later towns sell +1 weapons (Silver equivalent), scrolls (one-use spell tomes), and minor wondrous items. Expensive — rewards good gold management.
- **Wolfram's Forge.** Between chapters, Wolfram can spend GP + materials to upgrade one ally's weapon or armor (+1 might / +DEF, an `effective`-vs-class flag, etc. — all FE-native). This replaces FE's "arena grinding" as the primary way to power up outside of leveling. Materials are found in chapter chests or bought at specialty shops.
- **Potion varieties.** Healing Potion (Vulnerary equivalent, 10 HP), Greater Healing Potion (Elixir equivalent, full heal), Potion of Defense (temporary +DEF/RES for 1 chapter — FE-native), Potion of Speed (temporary SPD boost). Priced to make choices meaningful.

**What changes from vanilla FE:**
- **No arena.** The FE8 arena (pay gold, fight for XP/gold) is removed. It doesn't fit the D&D narrative pacing and is a balance headache. Wolfram's Forge fills the "spend gold to get stronger" role.
- **Spell tomes deplete and are restocked with gold (decision B).** Each spell is a finite-use tome whose charges run down in use; between chapters you restock them with GP at a shop, exactly like buying replacement weapons. There is no free refill — casting is rationed by the convoy budget. Casters first learn a spell at recruitment / via story events, but keeping it stocked costs gold.
- **Cantrip tomes are high-count, not infinite.** Class-locked high-use tomes (~30–50 uses); they deplete and restock with gold like everything else, just at a generous count so a caster can always act within a map.
- **Restock is flavored per caster** (forage / scribe / commune) but mechanically it is the FE armory/vendor buy — the whole party shares one gold-and-durability economy.

**Loot design per chapter:**
- Every chapter should yield enough GP from enemies + chests to buy 2–3 items at the next shop.
- Each chapter has 1–2 chests with unique/named items (not buyable in shops) as exploration rewards.
- Boss drops are always notable — named weapons, rare materials for Wolfram's Forge, or story items.

---

## 7. Story Arc — Chapter Breakdown

### Chapter 1: The Iron Trail
- **Narrative beat:** Party meets at The Northlook tavern in Bryn Shander. Three dwarves hire them to recover a stolen iron ingot shipment. They follow the trail to a goblin camp.
- **Introduced:** All 7 PCs (available from start), Duvessa Shane (cutscene), Velynne Harpell (brief appearance).
- **Map type:** Linear snowy trail — Bryn Shander outskirts to goblin camp.
- **Objective:** Seize the goblin camp (mirrors FE8 Ch1); recover the iron ingots.
- **Enemies:** Goblins (Brigand class, CR 1/4, level 2).
- **Post-map:** Cutscene — Duvessa Shane hires party for ongoing Ten-Towns work. Baxby purchasable.
- **Design note:** Introductory chapter. Teaches basic movement, FE combat, and the D&D reskin (damage types, the crit flourish). Keep enemy count low (8–12 goblins).

### Chapter 2: Cold Welcome
- **Narrative beat:** Party travels west to Targos. Ambushed on the road. In Targos they find a frozen body (human sacrifice to Auril) and hear rumors of the Maer Monster.
- **Introduced:** Baxby joins (if not Ch 1). Frost druids foreshadowed.
- **Map type:** Open snowy road with sled escort. Enemies from tree lines/snowdrifts.
- **Objective:** DefeatAll — clear the wilderness ambush (wolves, bandits, frost druid scout), keeping the sled alive (escort constraint).
- **Enemies:** Wolves (beast class), bandits or frost druid scouts.
- **Post-map:** Cutscene — Targos arrival, sacrifice discovery, inn scene, overheard rumors about Bremen.
- **Design note:** Introduces escort mechanic (protect the sled / Rolling Cheddar). Wider map than Ch 1.

### Chapter 3: The Termalaine Mine
- **Narrative beat:** Kobolds have taken over the gemstone mine. Miners are vanishing. Party enters to find kobolds AND Grells in the deep shaft. Prof. RBG executes a kobold during interrogation. They meet Trex.
- **Introduced:** Trex (recruited after chapter). Pinky involved in gameplay (sent to scout Grells).
- **Map type:** Multi-level mine interior. Kobolds on upper levels, Grells as bosses below.
- **Objective:** Seize — clear the mine of Grells. Optional: spare or fight kobolds.
- **Enemies:** Kobolds (Brigand, low level), Grells (custom monster class, mini-boss, CR 3).
- **Recruitment:** Trex joins post-chapter.
- **Design note:** First multi-level map. Teaches vertical navigation. Kobolds can be bypassed (optional fights). The RBG execution is a scripted cutscene mid-map.

### Chapter 4: The Elven Tomb
- **Narrative beat:** Through Lonelywood (brief inn stay) to an elven tomb. Frost druid fights to the death. Party finds Basil, solves a moonlight puzzle, awakens a mummy ally.
- **Introduced:** Basil (recruit), The Mummy (recruit).
- **Map type:** Forest path leading to tomb interior. Boss arena.
- **Objective:** DefeatAll — clear the tomb (the frost druid is the last/toughest to fall; mirrors FE8 Ch4's monster-debut). Moonlight puzzle = move units to specific tiles mid-map.
- **Enemies:** Frost Druid (boss, Druid class), nature-themed minions (wolves, vine blights).
- **Recruitment:** Basil and The Mummy join post-chapter.
- **Design note:** First real boss fight. The moonlight puzzle is a mid-map event: move 3 units to glowing tiles simultaneously to open the sarcophagus chamber. Tests positioning awareness.

### Chapter 5: The Maer Monster
- **Narrative beat:** In Bremen, Messie the plesiosaur capsizes fishing boats. Party boards a boat and confronts Messie. This is a genuine boss fight — Messie hits hard and the boats limit movement. But Marty's Talk with Animals ability opens an alternative: get Marty adjacent to Messie and use Talk to learn she was awakened by the frost druid and is afraid of losing her intelligence. Resolve peacefully or keep fighting.
- **Introduced:** Messie (non-recruitable, becomes Bremen NPC).
- **Map type:** Water map with 2 boats. Tight space, high tension.
- **Objective:** DefeatBoss OR Talk — this is a real boss fight with a hidden peaceful resolution. Messie is beatable through combat (hard but doable — think FE8 Chapter 5 difficulty), but Marty can Talk to Messie if adjacent, resolving the chapter instantly.
- **Enemies:** Messie (massive boss unit, very strong but not invincible — roughly equivalent to an early-game FE dragon boss). Supporting enemies: aggressive fish/water creatures that harass the boats and force the player to split attention.
- **Design note:** **This is the Navarre/Guy/Joshua moment.** The player is in a real fight — Messie is tough, the boats are cramped, supporting enemies are flanking. It should feel desperate but winnable. The Talk option is discoverable the way classic FE recruitment works: pre-chapter dialogue hints that Marty can speak with beasts ("I can talk to animals, remember?"), and when Marty is adjacent to Messie the Talk command appears in the menu — but the game never forces it. Players who brute-force Messie down get a different (sadder) post-chapter scene. Players who use Talk get the full payoff: Messie joins Bremen peacefully, becoming Speaker later. This mirrors the actual campaign — Marty used Talk with Animals and it changed everything. The fight itself should take 8–12 turns to win through combat, giving the player plenty of time to notice the Talk option organically.

### Chapter 6: Blood in Bremen
- **Narrative beat:** Party reports to Dorbulgruf Shalescar, who refuses to pay. Braulo swings first. After a bloody battle, the party installs Messie as Speaker.
- **Introduced:** No new recruits.
- **Map type:** Town interior / Speaker's hall. Could have civilians as "don't kill" NPC units.
- **Objective:** DefeatBoss — defeat Dorbulgruf (mirrors FE8 Ch6); civilians are don't-kill NPCs.
- **Enemies:** Dorbulgruf (boss, Warrior class — cantankerous old dwarf), Bremen guards (Soldier/Knight class).
- **Post-map:** Cutscene — Messie installed as Speaker. Mixed reception from townsfolk.
- **Design note:** Morally gray chapter — the party attacked the Speaker. Dialogue should reflect this ambiguity. Civilian NPCs on the map add complexity (ally units that can't die, or a penalty for killing them).

### Chapter 7: The Eastway Ambush
- **Narrative beat:** Party treks east toward Easthaven. Enters an ice canyon. Ambushed by 20+ guards demanding arrest for Bremen. Braulo breaks his shackles. Ice trolls in Easthaven garb swarm with boulders. Party is overwhelmed.
- **Introduced:** No new recruits.
- **Map type:** Narrow ice canyon with high walls. Guards from both sides. Ice troll reinforcements mid-chapter.
- **Objective:** Survive N turns (8–10). Scripted loss after timer — boulders block escape, reinforcements overwhelm.
- **Enemies:** Easthaven Guards (Soldier/Knight, 20+), Ice Trolls (Boss-tier, arrive as reinforcements at turn 4–5).
- **End state:** Scripted defeat cutscene — party goes unconscious, fade to black. Text: *"You wake up on the road to Revel's End..."* Cliffhanger. Credits roll.
- **Design note:** **This is an unwinnable battle by design.** The player should feel heroic for lasting the full turn count but the outcome is fixed. Fire weapons are **effective** vs ice trolls (vanilla FE effectiveness) — the party can exploit this but won't have enough firepower to clear them all. Braulo's shackle-breaking is a turn-1 scripted event that triggers his unique dialogue. The "Rolling Cheddar" (party sled) is on the map — the party tries to reach it but boulders block the exit at turn 6.

---

## 8. Art Direction

### Sprites (Map Units)
- **Baseline:** Recolored vanilla FE8 sprites for all units.
- **Customization:** Use Nanobanana 2 (AI sprite editor) to modify for homebrew races — Tortle shell for Braulo, mushroom cap for Marty, scales for Wolfram, etc.
- **Enemy sprites:** Vanilla FE8 enemy sprites, recolored. Custom creatures (Grells, Messie, ice trolls) may need community sprites from FEUniverse or Nanobanana 2 edits.

### Portraits (Dialogue / Stat Screens)
- **Source:** D&D Beyond character art (URLs in `References/PCs/portraits.json`).
- **Process:** AI-generate base portraits using D&D Beyond art as reference → manual cleanup → convert to FE pixel art specs (GBA palette constraints, correct dimensions: 80×72 main portrait, 32×32 mini portrait, 16-color palette).
- **Enemy/NPC portraits:** Mix of vanilla FE8 portraits (recolored) and custom art for key NPCs (Duvessa Shane, Trex, Messie, Dorbulgruf).

### Map Tiles
- **Primary:** Vanilla FE8 snow/ice tilesets (Tower of Valni area).
- **Community FE tilesets:** Arctic/ice tilesets from FEUniverse.
- **Frostmaiden community maps as reference:** The `frostmaiden-resources.md` file links to community-made maps for Rime of the Frostmaiden encounters and locations (Ten-Towns maps, dungeon layouts, encounter maps). These are D&D-style top-down maps — not FE-format, but excellent *reference material* for FE-ifying. Use them as layout guides when hand-drawing the FE `.tmx` versions: room shapes, corridor flow, terrain placement, encounter zones. This saves significant design time vs. inventing layouts from scratch.
- **Frostmaiden artwork as portrait/sprite reference:** The community resources also include location art, NPC illustrations, and creature art that can inform portrait generation and sprite customization.
- **Custom tilesets needed for:** Mine interiors (Ch 3), elven tomb interior (Ch 4), water/boat map (Ch 5), town interior (Ch 6). Check FEUniverse's tileset repository first — cave, temple, and water tilesets likely exist and just need palette swaps for the arctic theme.

### Cutscene Art
- **MVP:** Portrait-based dialogue only (vanilla FE8 style). No CG illustrations.
- **Stretch:** CG-style illustrations for key moments (Braulo's shackle break, Messie rising from the water, the Revel's End fade-to-black).

---

## 9. Audio Direction

- **MVP:** Vanilla FE8 (Sacred Stones) soundtrack. It has moody, epic, and atmospheric tracks suitable for arctic adventure.
- **Stretch:** Investigate Rime of the Frostmaiden Spotify album + 17 community soundtrack compilations from `frostmaiden-resources.md` for GBA conversion candidates.
- **Priority candidates for custom tracks (post-MVP):** Boss fight themes, Messie water encounter (Ch 5), Eastway ambush (Ch 7), location-specific ambience.
- **Technical constraint:** GBA audio limited to ~8 channels, specific sample rates. Converting modern tracks to GBA-compatible format (MIDI/S-file) is non-trivial.

---

## 10. Leveling & Progression

- **Starting state:** All 7 PCs begin at low FE levels (equivalent to D&D level 1–3). They met at The Northlook tavern together — no staggered recruitment for PCs.
- **End state:** the D&D Beyond sheets (level 20, except Sclorbo at 16) are **character flavor reference** — they tell us each PC's relative strengths (who's the tank, who's the glass cannon), not literal target numbers. FE stats are authored in FE terms (caps ~30), not converted from 5e scores.
- **MVP scope (7 chapters):** PCs should reach roughly FE level 10–12 unpromoted by end of Chapter 7. Promotion should be possible but not expected within MVP.
- **Growth rates:** authored in FE terms so a full-campaign playthrough lands each PC at a strong, class-appropriate FE endgame stat line — informed by the sheet's relative strengths, not tuned to match 5e numbers.
- **Sclorbo exception:** Sclorbo's player left the campaign at D&D level 16. In the hack, Sclorbo starts at the same level as everyone else but has slightly lower endgame growth caps (reflecting level 16 vs 20 ceiling). No in-story explanation — just a balance lever.
- **NPC recruits:** Join at lower levels than PCs (Trex is a "trainee" style low-level unit with high growths; Basil and The Mummy join at moderate levels).

---

## 11. Technical Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| **HP scale mismatch** — 5e spells designed for 50–200 HP; FE units have 20–60 HP | High | Keep FE's `damage − DEF` model. Don't import 5e damage values directly. Scale all damage through the weapon-dice system with FE-appropriate magnitudes. Playtest early. |
| **GBA UI real estate** — combat preview is ~96×40 px; want to add a damage-type icon (and a crit flourish) without crowding FE's existing hit%/crit% forecast | Low | The forecast box stays vanilla FE; only add a small damage-type icon. The d20 flourish reuses the battle-animation crit frames, not the forecast box. |
| **Save-file size** — adding spell-tome charges per unit may pressure FE8's ~52-byte per-character budget | Low | No AC and no resistance bitmap are stored (combat is vanilla FE), which leaves spell-tome charges as the main add (plus a 1-byte flavor damage-type label per weapon, in the item table not the unit). Use a sidecar lookup if needed. Audit in Phase 1. |
| **`agbcc` compiler limitations** — GCC 2.95.1, no C99 features | Low | Follow existing decomp code style. No VLAs, no C99 designated initializers. The decomp's own code is the style guide. |
| **Map design quality** — LLMs are bad at FE maps | Low | Use community Frostmaiden maps (from `frostmaiden-resources.md`) as layout references, then hand-draw FE versions in Tiled. FEUniverse map pool for tileset/format guidance. Agent assists with unit placement, events, and dialogue — never spatial layout. |
| **Engine/content boundary erosion** — temptation to hardcode Frostmaiden assumptions in C | Medium | `build-campaign.ts` enforces the contract. Code review rule: any C change that references a character by name, a chapter number, or a plot event gets rejected. |

---

## 12. Success Metrics

These are qualitative (audience of 7, no analytics):

1. **"It boots and plays"** — the `.gba` loads on mGBA and a real GBA flash cart, all 7 chapters are completable, no hard crashes.
2. **"That's my character!"** — each player recognizes their PC from the portrait, stats, and abilities within 30 seconds of seeing them.
3. **"It plays like Fire Emblem, reads like D&D"** — combat resolves with FE's familiar hit%/avoid forecast, while damage-type labels and the crit flourish make it read as *our* D&D campaign. A hammer is effective vs skeletons (vanilla FE effectiveness); a nat-20 flourish punctuates a crit.
4. **"I remember this"** — at least 3 campaign-specific moments per chapter that make the players laugh or say "oh yeah, that happened."
5. **"I want to keep playing"** — the Chapter 7 cliffhanger lands hard enough that at least 2 players ask when the next batch of chapters is coming.
6. **Build health** — `make` passes at the end of every work session. No sessions end with a broken build.

---

## 13. Open Questions

> These need answers before or during implementation. Tagged with who should decide.

| # | Question | Owner | Notes |
|---|---|---|---|
| 1 | **Signature moments for Marty, Meesmickle, Rootis, Sclorbo** — each PC needs at least one moment referenced in dialogue or abilities | Nicolas | Ask players if needed. These drive unique dialogue triggers and ability names. |
| 2 | **Velynne Harpell's role** — does she become important later in the published adventure? If so, foreshadow properly in MVP chapters | Nicolas + published book check | She appears in Ch 1 asking about a stolen orb. |
| 3 | **Homebrew setting overlays** — did the DM change anything about the Icewind Dale setting? | Nicolas | Default: standard Forgotten Realms with a non-standard party. |
| 4 | **Messie's Bremen function** — confirmed non-recruitable NPC. What does she *do* after Ch 6? Shop? Services? Quest-giver? | Design decision | Recommend: Messie runs a "harbor shop" selling water-themed items between chapters. |
| 5 | **Permadeath flavor** — in Casual mode, how are "retreats" explained for a party in arctic wilderness? | Design decision | Recommend: "retreated to the sled" / "carried to safety by Baxby." |
| 6 | **Stretch goal scope** — how many total chapters beyond the 7 MVP? Full campaign = how many? | Nicolas | Requires a future writing session to outline the rest of the Frostmaiden arc. |
| 7 | **Cutscene art** — portrait-based dialogue only (MVP) or CG illustrations for key moments? | Nicolas | Recommend: MVP ships portrait-only. CG art is a post-ship stretch goal. |
| 8 | **Sephek Kaltro** — appears in the designed Prologue ("A Dagger of Ice") as Hlin's quarry. Confirm his role beyond the Prologue (recurring? tie to Ch 4 frost druids?) | Nicolas | Published Ch 1 villain in Rime of the Frostmaiden; now the Prologue boss. |
| 9 | **Unit struct save budget** — does adding spell-tome charges exceed the ~52-byte per-character save limit? No AC or resistance bitmap is stored (combat is vanilla FE), which eases this. | Engineering (audit in Phase 1) | Sidecar table is the fallback. |

---

## 14. Roadmap — Phased Milestones

### Phase 0: Foundation (Milestone: "Repo Boots Clean")
**Goal:** Repository scaffolded, FE8 decomp builds clean, toolchain verified.
**Duration estimate:** 1–2 sessions (~2–4 hours)

### Phase 1: Engine Core (Milestone: "D&D Combat Layer Works")
**Goal:** Combat resolution stays vanilla FE8; the D&D *layer* on top all works — 13 damage-type flavor labels (+ vanilla FE effectiveness for iconic matchups), spell-slot tomes, the `engine/status` + `engine/hazards` modules, the combat-preview reskin, and the cosmetic d20 crit flourish. Vanilla FE8 Chapter 1 is playable with the reskinned combat.
**Duration estimate:** 6–10 sessions (~12–20 hours).

### Phase 2: Content Pipeline (Milestone: "One PC End-to-End")
**Goal:** The build-campaign tool works. One PC (Braulo recommended — simplest class mapping) is fully translated: YAML → injected into decomp → playable in mGBA with correct stats, portrait, inventory, and class.
**Duration estimate:** 3–5 sessions (~5–10 hours)

### Phase 3: MVP Content (Milestone: "7 Chapters Playable")
**Goal:** All 7 PCs, all NPCs, all 7 chapters, all maps, all dialogue, all events. The `.gba` is playable start to finish.
**Duration estimate:** 15–25 sessions (~30–50 hours)

### Phase 4: Polish & Ship (Milestone: "Ship It")
**Goal:** Playtesting, balance tuning, bug fixes, final portraits, final dialogue pass. Distribute to the group.
**Duration estimate:** 5–8 sessions (~10–15 hours)

**Total estimate:** 32–50 sessions, ~$60–200 in API spend, 60–100 hours of active work.

---

## 15. GitHub Project Setup

### Repository
- **Name:** `manchego-stars`
- **Visibility:** Private
- **Default branch:** `main`
- **Branch strategy:** Feature branches per milestone task. `main` always builds clean.

### Labels

| Label | Color | Usage |
|---|---|---|
| `engine` | Blue | Reusable engine code (damage types, spell slots, status/hazards, UI reskin) |
| `content` | Green | Campaign-specific data (PCs, chapters, dialogue, maps) |
| `tooling` | Yellow | Build pipeline, SRD pull, campaign injector |
| `art` | Purple | Sprites, portraits, map tiles |
| `audio` | Orange | Music, sound effects |
| `bug` | Red | Defects |
| `balance` | Gray | Stat tuning, hit-rate adjustments, difficulty |
| `stretch` | Brown | Post-MVP nice-to-haves |
| `blocked` | Black | Waiting on external input or decision |

### Milestones

1. **M0: Repo Boots Clean**
2. **M1: D&D Combat Layer Works**
3. **M2: One PC End-to-End**
4. **M3: 7 Chapters Playable**
5. **M4: Ship It**

---

## 16. GitHub Issues — Full Backlog

### M0: Repo Boots Clean

**#1 — Initialize repo with README and CLAUDE.md** `tooling`
Set up the GitHub repo structure per §6.2. Write `CLAUDE.md` with project conventions, key file pointers, and "what the agent should know." Include `docs/decisions.md` with initial design decisions from this PRD.

**#2 — Add fireemblem8u as git submodule** `engine`
`git submodule add` the FE8 decomp. Verify `./scripts/quickstart.sh --rom /path/to/baserom.gba` produces `fireemblem8.gba: OK`.

**#3 — Set up CI: `make` green gate** `tooling`
GitHub Actions workflow that runs `make fireemblem8.gba -j$(nproc)` on push to `main` and PRs. Fail if sha1 doesn't match. This is the build gate that prevents broken builds from landing.

**#4 — Write `tools/pull-srd.ts`** `tooling`
One-shot script that walks dnd5eapi.co endpoints (classes, races, spells, monsters, equipment, conditions, damage-types, magic-items, features) and dumps to `data/srd-snapshot.json`. Then walks Open5e v2 endpoints (spells, creatures, items, magicitems, weapons, armor) and dumps to `data/open5e-snapshot.json`. Commit both snapshots.

**#5 — Scaffold campaign folder structure** `content`
Create the `campaigns/rime-of-the-frostmaiden/` directory tree with empty YAML templates for `campaign.yaml`, one PC file, one chapter file. Include comments explaining each field. This is the "hello world" of the content pipeline.

**#6 — Write homebrew class/race YAML stubs** `content`
Create `data/homebrew/classes/artificer.yaml` and `data/homebrew/classes/metallurgist.yaml`. Create all 7 homebrew race YAMLs. These are hand-written from the D&D Beyond sheets and published PDFs (Tasha's, Metallurgist PDF, Myconid Race PDF). Fill in mechanical stats, not flavor text.

---

### M1: D&D Combat Layer Works

Combat resolution stays vanilla FE8 (`bmbattle.c` left intact). The work in this milestone is
the D&D *flavor* layer on top — there is no d20/AC/saving-throw/nat-20 engine to build, so issue
numbers #8–#11 are unused and the list picks up at #12. The weapon triangle stays FE-native
(Sword/Axe/Lance, Anima/Light/Dark); D&D damage-type names are per-weapon labels, not a relabel
of the triangle.

**#7 — Cosmetic crit-flourish RNG helper** `engine`
A tiny RNG helper over `bmRng.c` for the crit flourish's spinning-number effect, if the battle
animation wants one. No advantage/disadvantage to support. Optional — can fold into #17.

**#12 — Add damage-type *flavor* enum and weapon tagging** `engine`
Create `damage_type.h` with enum (13 types: slashing, piercing, bludgeoning, fire, cold, lightning, thunder, poison, acid, necrotic, radiant, force, psychic). Add a 1-byte **flavor** damage-type tag to each weapon (for the UI icon + descriptions). Tag all vanilla FE8 weapons. **No resistance computation** — this is a label only.

**#13 — Iconic matchups via vanilla FE weapon effectiveness** `engine`
There is no resistance/vulnerability/immunity multiplier (no vanilla FE analogue; it would modify FE damage under the hood). For the handful of iconic matchups (fire vs ice trolls/frost druids, bludgeoning vs skeletons), flag the relevant weapons **effective** vs those enemy classes using vanilla FE8's existing effectiveness mechanic. No new damage-multiplier code. Test a fire weapon doing FE-effective bonus damage to an ice troll.

**#15 — Implement the spell-economy tracker (decision B)** `engine`
Each spell/cantrip is a finite-use tome whose charges DEPLETE in use. **No free chapter refill** — between chapters the player restocks charges with gold at the armory/vendor. Decrement on tome use; gray out a depleted tome; show remaining uses on the stat screen. Cantrips are high-count (30–50 uses), spell tomes lower. Wire restock into the prep/shop flow. (Issue #14, a triangle relabel, is dropped — the triangle stays FE-native; D&D damage-type names are per-weapon labels.)

**#16 — Implement combat preview UI reskin** `engine`
Keep FE's vanilla hit%/crit% forecast box. Add only a **damage-type icon**. No AC / to-hit / dice line (those mechanics don't exist), and no triangle relabel — the triangle UI stays FE-native. Prototype in mGBA first.

**#17 — Implement cosmetic d20 crit flourish** `engine`
When an FE crit fires in the battle animation, play a brief "d20 lands on 20" flourish (3–5 frames of spinning numbers settling on 20) for D&D feel. **Cosmetic only** — it does not decide the crit (FE's crit rate does). This is the surviving "BG3 feel" moment.

**#18 — Playtest vanilla FE8 Chapter 1 with the D&D layer** `engine` `balance`
Play FE8's original Chapter 1 (Eirika's route) with the reskinned combat. Verify: vanilla FE hit/avoid/crit behave normally, the damage-type flavor label/icon shows correctly, an FE-effective weapon does its bonus damage, spell tomes deplete and restock with gold, the crit flourish plays, no crashes, save/load works. Hit-rate tuning is just vanilla FE tuning. Document findings.

---

### M2: One PC End-to-End

**#19 — Write `tools/map-class.ts`** `tooling`
5e class → FE class mapper. Reads from SRD snapshot first, Open5e second, homebrew folder last (highest precedence). Outputs the FE class ID, base stats, growth rates, and promotion options. Pure code, no LLM.

**#20 — Write `tools/build-campaign.ts`** `tooling`
Campaign injector script. Reads `campaign.yaml`, walks `pcs/`, `npcs/`, `enemies/`, `chapters/` folders. Runs the class mapper. Generates EA buildfiles. Injects unit data, item data, class data, and chapter events into the decomp's data tables. Then runs `make`. The single command: `make CAMPAIGN=rime-of-the-frostmaiden`.

**#21 — Write `tools/build-events.ts`** `tooling`
YAML → Event Assembler buildfile codegen. Reads a chapter YAML (unit placement, dialogue, events, objectives) and emits `.ea` files that ColorzCore can assemble.

**#22 — Translate Braulo end-to-end** `content`
Write `campaigns/rime-of-the-frostmaiden/pcs/braulo.yaml` with full 5e stats, FE starting stats, growth rates, inventory, class mapping (Pirate → Berserker), and unique abilities (Rage, Shell Defense). Create or source a portrait. Inject via `build-campaign.ts`. Verify Braulo appears in mGBA with correct stats, portrait, class, and inventory. Document rough edges.

**#23 — Create Braulo's portrait** `art`
Source from D&D Beyond portrait URL (`portraits.json`). AI-generate base portrait → manual cleanup → convert to FE pixel art specs (80×72 main, 32×32 mini, 16-color palette). Insert via `Png2Dmp` + `PortraitFormatter`. Verify in mGBA stat screen.

---

### M3: 7 Chapters Playable

**#24 — Translate remaining 6 PCs** `content`
Write YAML files for Marty, Meesmickle, Prof. RBG, Rootis, Sclorbo, Wolfram. Each needs: 5e stats, FE stats, growths, inventory, class, unique abilities, portrait reference.

**#25 — Create portraits for all PCs** `art`
6 remaining PC portraits (Marty, Meesmickle, Prof. RBG, Rootis, Sclorbo, Wolfram). Same pipeline as #23.

**#26 — Implement custom classes** `engine` `content`
Create FE class entries for classes with no vanilla equivalent: Artillerist promotion for RBG (Archer base → custom Artillerist with cannon deployment), Metallurgist (Wolfram), custom Bard (Sclorbo), custom Druid (Marty). Define base stats, caps, promotion gains, weapon types, animations. Reuse vanilla animations where possible (RBG uses Archer/Sniper base animations; note where custom battle animations are needed).

**#27 — Implement unique PC/NPC abilities** `engine` `content`
Per-unit unique skills: Braulo's Rage (consumable Berserk item with custom stats), Braulo's Shell Defense (command), Marty's Halo of Spores (innate AoE), Meesmickle's Eldritch Blast (∞-use dark tome), Prof. RBG's Eldritch Cannon (deployable ballista unit), Rootis's Metamagic, Sclorbo's Bardic Inspiration (Dance variant), Wolfram's Forge (between-chapter upgrade), **Pinky's Red Ruby respawn** (on defeat → drops Red Ruby item on tile; RBG uses Ruby to re-summon Pinky adjacent; requires custom death handling and item-triggered summon). Each is a separate sub-task.

**#28 — Write all NPC YAML files** `content`
Baxby, Pinky, Trex, Basil, The Mummy, Messie (non-recruitable), Duvessa Shane (cutscene only), Velynne Harpell (cutscene only). Stats, classes, inventories, join conditions.

**#29 — Create NPC portraits** `art`
Portraits for Trex, Basil, The Mummy, Dorbulgruf, Messie. Other NPCs can use recolored vanilla FE8 portraits.

**#30 — Write all enemy YAML files** `content`
Goblins, Kobolds, Grells, Frost Druid, Dorbulgruf, Easthaven Guards, Ice Trolls, wolves, bandits, vine blights. Stats, classes, inventories, AI patterns, and any vanilla-FE `effective`-vs flags (no resistance tables).

**#31 — Design and build Chapter 1 map** `art` `content`
Hand-draw "The Iron Trail" map in Tiled. Linear snowy trail, goblin camp at the end. Place terrain (snow, trees, rocks, camp structures). Export to FE-compatible format. Place units per chapter YAML.

**#32 — Implement Chapter 1 events and dialogue** `content`
Write Ch 1 event script: opening cutscene (Northlook tavern, dwarves hire party), mid-map dialogue (if any), post-map cutscene (Duvessa Shane, Baxby purchase). All dialogue in EA buildfile format.

**#33 — Design and build Chapter 2 map** `art` `content`
"Cold Welcome" — open snowy road, sled escort, tree lines for ambush spawns.

**#34 — Implement Chapter 2 events and dialogue** `content`

**#35 — Design and build Chapter 3 map** `art` `content`
"The Termalaine Mine" — multi-level mine interior. Upper kobold levels, lower Grell shaft. Vertical navigation.

**#36 — Implement Chapter 3 events and dialogue** `content`
Include mid-map cutscene: Prof. RBG's kobold execution. Trex recruitment event post-map.

**#37 — Design and build Chapter 4 map** `art` `content`
"The Elven Tomb" — forest path → tomb interior. Boss arena. Moonlight puzzle tiles.

**#38 — Implement Chapter 4 events and dialogue** `content`
Moonlight puzzle event (move 3 units to glowing tiles). Basil + Mummy recruitment post-map.

**#39 — Design and build Chapter 5 map** `art` `content`
"The Maer Monster" — water map, 2 boats, Messie as massive boss unit. Tight space.

**#40 — Implement Chapter 5 events and dialogue** `content`
Real boss fight with dual resolution: combat victory (hard, different ending) OR Talk (Marty → Messie, peaceful, better ending). Pre-chapter hint dialogue. Supporting water enemies. Two post-chapter branches. Post-map: Messie stays in Bremen.

**#41 — Design and build Chapter 6 map** `art` `content`
"Blood in Bremen" — town interior, Speaker's hall. Civilian NPC units.

**#42 — Implement Chapter 6 events and dialogue** `content`
Dorbulgruf boss fight. Civilian NPCs (don't kill). Post-map: Messie installed as Speaker cutscene.

**#43 — Design and build Chapter 7 map** `art` `content`
"The Eastway Ambush" — narrow ice canyon, high walls, two-sided ambush, boulder blockade.

**#44 — Implement Chapter 7 events and dialogue** `content`
Turn-1 scripted event: Braulo shackle break. Survive timer (8–10 turns). Turn 4–5: ice troll reinforcements. Turn 6: boulder blockade. End: scripted defeat, fade to black, Revel's End text. Credits.

**#45 — Implement world map** `content`
FE8's world map showing Ten-Towns locations. Chapters unlock sequentially (no free-roam for MVP). Post-chapter screens show the party traveling between towns.

**#46 — Write campaign.yaml** `content`
Metadata: title "Manchego Stars: Rime of the Frostmaiden," 7 chapters, start level 1, promotion threshold, level cap for MVP.

---

### M4: Ship It

**#47 — Full playthrough #1 — functionality** `bug`
Play all 7 chapters start to finish. Log every crash, soft-lock, missing dialogue, broken event, wrong stat, misplaced unit.

**#48 — Full playthrough #2 — balance** `balance`
Play again with focus on: hit rates (are they in the 65–80% sweet spot?), damage (does anything one-shot? does anything tickle?), chapter difficulty curve, is Chapter 7 survivable for N turns?, are casters balanced vs martials?

**#49 — Balance tuning pass** `balance`
Adjust: enemy ACs, PC base stats, growth rates, weapon dice, proficiency bonuses, chapter enemy counts. Goal: each chapter should be completable without losing units on a first attempt by a competent FE player on Classic mode.

**#50 — Final dialogue pass** `content`
Review all dialogue for: character voice consistency, campaign callbacks, typos, pacing. Add any missing signature moments from Nicolas's input.

**#51 — Final portrait pass** `art`
Review all portraits for: palette compliance, dimension compliance, visual consistency across the roster.

**#52 — Title screen and credits** `art` `content`
Custom title screen: "Manchego Stars" title, party silhouettes, snow particles. Credits: Nicolas (design/dev), player names, "Based on the Icewind Dale campaign." Tool credits (FEUniverse, decomp team, etc.).

**#53 — Build final ROM and distribute** `tooling`
Run final `make CAMPAIGN=rime-of-the-frostmaiden`. Verify sha1. Test on mGBA, RetroArch, and a GBA flash cart if available. Send pre-patched `.gba` directly to the 7 players.

---

## 17. MCP Server Configuration

Keep the MCP list minimal — two servers:

### mGBA Scripting Bridge (Lua → MCP)
- **Purpose:** Let Claude Code boot the ROM, take screenshots, read memory addresses, advance N frames.
- **Why it's high-leverage:** The agent can *verify changes worked* without Nicolas watching.
- **Implementation:** Lua script running inside mGBA that exposes a local HTTP/JSON-RPC endpoint. The MCP server proxies calls to this endpoint.
- **Key operations:** `boot(rom_path)`, `screenshot() → PNG`, `read_memory(addr, len) → bytes`, `advance_frames(n)`, `get_unit_stats(unit_id) → JSON`.

### SRD Cache (static file server)
- **Purpose:** Serve `data/srd-snapshot.json` and `data/open5e-snapshot.json` locally.
- **Why:** Zero network dependency during build. No API rate limits.
- **Implementation:** Simple static file server, or just direct file reads (the agent has `Read` tool access).

---

## 18. Development Workflow

### Session Pattern
1. **Plan before prompting.** Write a 2–3 sentence brief in `SESSION.md`.
2. **Start each session** with `git status` + CLAUDE.md re-read. Cheap context.
3. **One feature per session.** Don't mix engine patches with dialogue writing.
4. **End every session with `make` green.** A broken build means next session pays to find the breakage.
5. **Commit small.** Smaller diffs = cheaper agent context next time.
6. **Use `/clear` between unrelated tasks** — don't carry engine context into content work.

### Model Selection Per Task

| Task | Model | Rationale |
|---|---|---|
| Edit a single C file (~200 LOC) | Sonnet | Sweet spot for code edits |
| Cross-cutting engine change (8+ files) | Opus with extended thinking, once | Pay the premium where it counts |
| Generate dialogue, unit YAML, item descriptions | Haiku | High volume, low complexity, ~10× cheaper |
| Smoke-test ROM build / read mGBA RAM | No LLM — pure script | Don't pay tokens for `sha1sum` |
| Map a 5e statblock → FE unit YAML | Haiku, then human review | Mostly mechanical |

### Cost Estimate

| Phase | Sessions | Est. Cost |
|---|---|---|
| Phase 0: Foundation | 1–2 | $2–5 |
| Phase 1: Engine Core | 8–12 | $20–60 |
| Phase 2: Content Pipeline | 3–5 | $8–20 |
| Phase 3: MVP Content | 15–25 | $25–80 |
| Phase 4: Polish & Ship | 5–8 | $10–35 |
| **Total** | **32–52** | **$65–200** |

---

## 19. Story Beat Refinement

The chapter breakdowns in §7 are a starting framework based on the DM notes. Each chapter's story flow, dialogue, and pacing will be revisited and refined during development — likely at the start of each chapter's implementation session. The DM notes capture *what happened*; the FE adaptation needs to decide *how to pace it* for a tactics game (where to put mid-map cutscenes, how to break long sequences into player-controlled and scripted segments, when to let the player breathe vs. push tension). Expect the chapter designs to evolve.

---

## 20. Definition of Done

The MVP is **done** when:

1. `make CAMPAIGN=rime-of-the-frostmaiden` produces a `.gba` that boots on mGBA without crashes.
2. All 7 PCs are selectable from Chapter 1 with correct portraits, stats, classes, and inventories.
3. All 5 NPC allies are recruitable at their designated chapters.
4. All 7 chapters are playable start to finish with correct objectives, enemies, dialogue, and events.
5. Combat plays as vanilla FE (hit/avoid/might/crit), reskinned with D&D damage-type icons and triangle labels, and a cosmetic d20 flourish fires on crits.
6. Damage-type flavor labels display, and vanilla FE weapon effectiveness works for iconic matchups (a hammer is effective vs skeletons, fire vs ice trolls, etc.).
7. Spell-slot tomes deplete and refill correctly per chapter.
8. Chapter 5 (Messie) is resolvable via Talk command.
9. Chapter 7 ends in a scripted defeat with the Revel's End cliffhanger text.
10. Casual/Classic mode toggle works for permadeath preference.
11. The `.gba` has been playtested at least twice end-to-end (once for bugs, once for balance).
12. The ROM has been successfully sent to and loaded by at least one other player from the group.

---

## Appendix A: Key File References in the Decomp

For the implementer (or Claude Code), these are the files in `fireemblem8u/src/` most relevant to engine changes:

| System | Key Files | What to Change |
|---|---|---|
| Combat resolution | `bmbattle.c`, `bmlib.c`, `include/battle.h` | **Leave fully intact** (vanilla FE). No resistance hook. Iconic matchups use the existing `effective`-weapon path. |
| Unit struct | `include/unit.h` (`struct Unit`) | Add spell slots (sidecar). **No AC field, no resistance bitmap** (combat is vanilla FE). |
| Combat preview UI | `bmStatScreen.c`, `bmStatBars.c` | Keep Hit%/Crit% forecast; add a damage-type icon (triangle stays FE-native). |
| RNG | `bmRng.c` | Untouched for resolution. Optional tiny helper for the cosmetic crit-flourish spin. |
| Staff resolution | `bmstaff.c` | **Leave intact** (vanilla always-hit staves). No saving-throw repoint. |
| Crit calculation | `BattleGenerateCrit` function | **Leave intact** (vanilla FE crit). Add only a cosmetic d20-on-crit flourish in the battle animation. |
| Class data | `data/classes.s` | Add D&D class entries |
| Item data | `data/items.s` | Add damage-type byte per weapon |
| Chapter init | Chapter start routine | Hook spell-slot refill |
| Save/load | Save routines | Ensure new data persists |

---

## Appendix B: D&D Content Sources

| Source | URL | What It Provides | License |
|---|---|---|---|
| dnd5eapi.co | `https://www.dnd5eapi.co/api/2014/` | 12 classes, 9 races, 319 spells, ~334 monsters, equipment | CC-BY-4.0 (SRD) |
| Open5e | `https://api.open5e.com/v2/` | Same SRD + 17 third-party docs (Tome of Beasts, Deep Magic, Black Flag, Tal'Dorei, etc.) | OGL/CC-BY/ORC |
| Hand-written YAML | `data/homebrew/` | Non-SRD classes (Artificer, Metallurgist), non-SRD subclasses, homebrew races | N/A (private use) |

Non-SRD content (Artificer, Circle of Spores, Hexblade, etc.) is **not available in any public API**. Hand-write YAML stat blocks per character from your own copies of the source books. Mechanics are not copyrightable; published flavor text is. For a private ROM hack, this is standard fair-use territory.

---

## Appendix C: Reference Links

**Fire Emblem Hacking:**
- [fireemblem8u decomp (GitHub)](https://github.com/FireEmblemUniverse/fireemblem8u)
- [FEBuilder GBA (GitHub)](https://github.com/FEBuilderGBA/FEBuilderGBA)
- [FE Decomp Portal](https://laqieer.github.io/fe-decomp-portal/)
- [Stan's Event Assembler Package](https://feuniverse.us/t/stans-event-assembler-package-for-buildfiles/11201)
- [C Setup for Dummies (FEU)](https://feuniverse.us/t/c-setup-for-dummies/23830)

**AI Harnesses:**
- [Agent Oak — Claude × pokeemerald (GitHub)](https://github.com/alvarodms/agentoak)
- [FE Infinity — LLM × FE8 (FEU)](https://feuniverse.us/t/fe8-fe-infinity-ai-system-that-builds-original-rom-hacks-prototype-demo/29090)

**D&D 5e APIs:**
- [dnd5eapi.co docs](https://5e-bits.github.io/docs/)
- [Open5e API docs](https://open5e.com/api-docs)

**BG3 Dice Mechanics:**
- [bg3.wiki — Dice rolls](https://bg3.wiki/wiki/Dice_rolls)

**FE Combat Reference:**
- [Fire Emblem Wiki — Battle Formulas](https://fireemblem.fandom.com/wiki/Battle_Formulas)
- [Serenes Forest — Sacred Stones calculations](https://serenesforest.net/the-sacred-stones/miscellaneous/calculations/)
