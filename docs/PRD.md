# Manchego Stars — Product Requirements Document

> **Version:** 1.0 — May 27, 2026
> **Author:** Nicolas (via Claude)
> **Status:** Draft — ready for review

---

## 1. Problem Statement

Nicolas ran a multi-year D&D 5e campaign (*Rime of the Frostmaiden*) with 6 friends. The campaign is over, but the shared memories — a hermit crab barbarian smashing shackles, a mushroom druid talking down a plesiosaur, a ratfolk artificer executing a kobold at gunpoint — deserve more than a group chat. The group has no way to *replay* their story.

**This project turns that campaign into a playable GBA tactics game**, built as a ROM hack of *Fire Emblem: The Sacred Stones* (FE8). The 7 PCs become playable units. The DM's narrative beats become chapters. Combat uses **vanilla FE8's tactics rules** (hit/avoid/might/crit) so the game plays like Fire Emblem; the D&D campaign supplies the characters, classes, damage types, spells-as-tomes, and flavor on top. The result is a `.gba` file the group can play on any emulator or flash cart — their adventure, in their pocket.

**Who is affected:** The 7 players from the campaign (private distribution only).

**Impact of not solving it:** Nothing breaks — this is a passion project. But the window for this kind of thing closes as life moves on. Building it now, while the memories are fresh and the tools are good enough, is the moment.

---

## 2. Goals

1. **Ship a playable `.gba` ROM** covering the full DM-notes arc (Prologue + 8 chapters, from the goblin iron quest through the Eastway ambush / Revel's End cliffhanger) that runs on stock GBA emulators and flash carts.
2. **Keep Fire Emblem's combat, dress it in D&D** — preserve FE's grid tactics, hit/avoid/might resolution, permadeath toggle, weapon triangle, growth-rate leveling, and FE crit. Layer D&D *flavor* on top: D&D damage-type labels (flavor only — no resistance multiplier; the triangle stays FE-native), spells as finite-use tomes that deplete and restock with gold (decision B), and a cosmetic d20 flourish on crits. Iconic matchups use vanilla FE weapon effectiveness, keyed to enemy class (armor/cavalry/flier/dragon/monster). The rules stay FE so it plays like FE.
3. **Faithfully represent all 7 PCs** as playable units with correct classes, abilities, progression arcs, and personality (portraits, dialogue, signature moments).
4. **Build the engine as reusable** — separate engine code (damage types, spell slots, status/hazards, UI reskin) from campaign data (PCs, chapters, maps, dialogue). A second campaign (Curse of Strahd, a homebrew, etc.) should require only a new `campaigns/` folder, zero engine changes.
5. **Keep the project tractable** — session-driven Claude Code workflow (no autonomous agent loops), one feature per session, `make` green at end of every session. Target cost: ~$60–200 for the full MVP.

---

## 3. Non-Goals

1. **Public release or distribution.** This is for 7 people. No patch hosting, no RomHack Plaza listing, no OGL/SRD compliance beyond what's needed for the codebase itself. The ROM is sent directly as a pre-patched file.
2. **Full campaign coverage beyond the DM notes.** The MVP ends at the Revel's End cliffhanger (Chapter 8). Content beyond that requires a future writing session to outline. Don't spec what doesn't exist yet.
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
- **As a player,** I want Chapter 6 (The Maer Monster) to feel like a real boss fight where I discover Marty can Talk to Messie — rewarding me for paying attention to the story, not for following a tutorial prompt.
- **As a player,** I want Chapter 8 (The Eastway Ambush) to end in a scripted defeat so that the cliffhanger landing at Revel's End hits dramatically.

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
    ├── CHAPTERS.md            # GENERATED chapter index; see gen-chapter-index.rb
    ├── CLASSES.md             # GENERATED roster (5e class → FE class); see gen-class-index.rb
    └── roadmap.md             # Post-MVP Act II–V scaffold (forward planning)
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
- Vanilla FE weapon effectiveness for iconic matchups, keyed to enemy class (FE-native; e.g. monster-effective weapons vs ice trolls/skeletons, armorslayer vs knights)
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

### 6.5 Combat, Triangle & Spells — vanilla FE8 (D&D flavor on top)

> **Settled elsewhere — do not duplicate here.** Combat resolution, the weapon/magic triangle,
> crit/doubling, the no-AC/no-saves rules, the damage-type-labels-only model, and the spell-tome
> economy live in **`decisions.md`** (§Combat System / §Weapon & Magic Systems / §Economy), with
> the generic 5e→FE conversion in **`rules-mapping.md`**.

Summary: rules are **vanilla FE8** (`bmbattle.c` left intact); D&D damage-type names are
**cosmetic per-weapon labels** (no resistance multiplier — iconic matchups like fire-vs-ice-troll
use FE's native weapon `effective` flags); the triangle stays FE-native (Sword/Axe/Lance,
Anima/Light/Dark); the d20 survives only as a **cosmetic crit flourish**. The engine does **not**
replace `bmbattle.c`.

### 6.7 Class System

> **Moved.** The PC + NPC class/promotion roster is no longer maintained here. The
> source of truth is the per-unit YAML (`campaigns/rime-of-the-frostmaiden/pcs/*.yaml`,
> `npcs/*.yaml` — `fe_stats.class`, `promotion.branch`/`default`). The generated
> roster table is **`docs/CLASSES.md`** (`ruby tools/gen-class-index.rb`); the mapping
> *rationale* (why each PC → its FE class, all stock vanilla) and the promotion seam
> are in **`docs/decisions.md` §Class Mapping & Promotions**.

### 6.8 Spell Slot → Tome Uses Mapping

| 5e Slot Level | Tome Uses | FE Tier Equivalent |
|---|---|---|
| Cantrip (0) | ~30–50 (high-count, **not** infinite) | Basic tome (Iron equivalent) |
| 1st | 8 | Low-tier tome |
| 2nd | 6 | Mid-tier tome |
| 3rd | 4 | High-tier tome (Bolting range) |
| 4th | 3 | Silver-tier |
| 5th | 2 | Brave-tier |
| 6th+ | 1 | Legendary / personal weapon |

**Tomes deplete in use and are restocked with gold at a shop between chapters** —
this is the decision-B economy (see §6.9 and `docs/decisions.md` §Weapon & Magic
Systems). There is **no** free per-chapter refill, and cantrips are high-count
items, not infinite. (This replaces the earlier "refill to max each chapter / long
rest" model.)

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

> **Moved.** The per-chapter breakdown is no longer maintained here. The single
> source of truth for every chapter (objective, recruits, enemies, map, rewards,
> cadence, narrative) is the YAML in
> `campaigns/rime-of-the-frostmaiden/chapters/ch*.yaml`. A generated overview table
> lives in **`docs/CHAPTERS.md`** (run `ruby tools/gen-chapter-index.rb` to refresh).
> Forward-looking design — the post-MVP Act II–V scaffold — is in
> `docs/roadmap.md`; settled rationale (cadence taxonomy, the promotion seam, the
> doc source-of-truth model) is in `docs/decisions.md`. See `docs/fe8-pacing-reference.md`
> for the FE8 cadence/reward rules this campaign applies.

---

## 8. Art Direction

> **Art direction (set 2026-06-01, portrait walkthrough):** the player cast + named recruits get **fully custom**
> indexed-palette art for **every** sprite part — portrait, map sprite, AND battle animation. Not recolored vanilla,
> not reused vanilla class animations. Since combat is pure vanilla FE8, the art is the biggest lever for campaign
> feel, so it's worth doing custom. Each piece is produced **faithfully from the character's clean Gemini/Nano-Banana
> bust reference** via tooling (`tools/ref_to_bust.py` → `tools/portrait_tool.py`) — the generative bust is the
> pre-approved source and is converted, not hand-pixeled, into the final indexed asset. **Delivered in three waves:**
> (1) all 10 cast portraits, then (2) map sprites, then (3) battle animations. See `docs/decisions.md` and each
> unit's YAML `art:` block for the per-character briefs.

### Sprites (Map Units)
- **Cast + named recruits:** custom map sprites drawn from each character's concept ref — Braulo's crab claws/shell/basket-hat, Marty's mushroom cap, Wolfram's mineral scales, Meesmickle's caped cat, Rootis's snowman, the cannon-golems Pepperjack & Brie, etc. Custom battle animations too (no vanilla-anim reuse).
- **Enemy sprites:** vanilla FE8 enemy sprites where the look fits; community (FEUniverse) or custom only for creatures with no vanilla analogue (Grells, Messie, ice trolls).

### Portraits (Dialogue / Stat Screens)
- **Source:** a clean frameless **"<Name> Face Clean"** bust per character, generated by Nicolas (Gemini/Nano-Banana) and dropped in the project References folder one at a time. These are the pre-approved source art.
- **Process:** Claude converts each bust into the final 96×80 16-color indexed portrait via `tools/ref_to_bust.py` (→ `tools/portrait_tool.py` to pack the FE8 sheet) — no hand-pixeling. Per-unit briefs (must-keep tells, expression, palette plan) live in each unit's YAML `art:` block.
- **Enemy/NPC portraits:** mix of vanilla FE8 portraits and custom art for key NPCs (Duvessa Shane, Trex, Messie, Dorbulgruf).

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
- **MVP scope (Prologue + 8 chapters):** PCs should reach roughly FE level 10–12 unpromoted by end of Chapter 8. Promotion should be possible but not expected within MVP.
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

1. **"It boots and plays"** — the `.gba` loads on mGBA and a real GBA flash cart, all 8 chapters are completable, no hard crashes.
2. **"That's my character!"** — each player recognizes their PC from the portrait, stats, and abilities within 30 seconds of seeing them.
3. **"It plays like Fire Emblem, reads like D&D"** — combat resolves with FE's familiar hit%/avoid forecast, while damage-type labels and the crit flourish make it read as *our* D&D campaign. A monster-effective weapon tears through skeletons and an armorslayer punches through knights (vanilla FE effectiveness, by class); a nat-20 flourish punctuates a crit.
4. **"I remember this"** — at least 3 campaign-specific moments per chapter that make the players laugh or say "oh yeah, that happened."
5. **"I want to keep playing"** — the Chapter 8 cliffhanger lands hard enough that at least 2 players ask when the next batch of chapters is coming.
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

### Phase 3: MVP Content (Milestone: "8 Chapters Playable")
**Goal:** All 7 PCs, all NPCs, all 8 chapters, all maps, all dialogue, all events. The `.gba` is playable start to finish.
**Duration estimate:** 15–25 sessions (~30–50 hours)

### Phase 4: Polish & Ship (Milestone: "Ship It")
**Goal:** Playtesting, balance tuning, bug fixes, final portraits, final dialogue pass. Distribute to the group.
**Duration estimate:** 5–8 sessions (~10–15 hours)

**Total estimate:** 32–50 sessions, ~$60–200 in API spend, 60–100 hours of active work.

---

## 15. Work Tracking

Work is tracked as **GitHub issues** (labels: `engine` / `content` / `tooling` / `art` /
`audio` / `bug` / `balance` / `stretch` / `blocked`; milestones **M0–M4**). The current,
maintained backlog lives in the issue tracker — not in this doc. `main` always builds clean;
feature branches per task. See the phased roadmap in §14.

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
4. All 8 chapters are playable start to finish with correct objectives, enemies, dialogue, and events.
5. Combat plays as vanilla FE (hit/avoid/might/crit), reskinned with D&D damage-type icons and triangle labels, and a cosmetic d20 flourish fires on crits.
6. Damage-type flavor labels display, and vanilla FE weapon effectiveness works for iconic matchups, keyed to enemy class (armorslayer/hammer vs armored knights, monster-effective weapons vs skeletons and ice trolls, etc.).
7. Spell-slot tomes deplete and refill correctly per chapter.
8. Chapter 6 (Messie) is resolvable via Talk command.
9. Chapter 8 ends in a scripted defeat with the Revel's End cliffhanger text.
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
