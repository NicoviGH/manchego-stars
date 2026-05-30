# Fire Emblem × D&D ROM Hack — Research Document

**Prepared for:** Nicolas
**Date:** 2026-05-26
**Purpose:** Background research to hand to the PRD agent. Covers (1) how to ship a `.gba` Fire Emblem ROM hack, (2) what Claude / agent harnesses can plausibly accelerate the work, (3) what's in the D&D 5e API and how it's shaped, and (4) a concrete plan for translating 5e characters and combat into Fire Emblem.

> **Combat approach:** an early version of this research proposed a hybrid d20 combat system
> (visible d20 vs Armor Class, advantage/disadvantage, spell save DCs). That was **not adopted** —
> combat resolution stays **vanilla FE8** (hit/avoid/might/crit), D&D is flavor, and the d20 survives
> only as a cosmetic crit flourish. The combat sections below (§6) reflect the adopted vanilla-FE
> approach; the authoritative spec is `decisions.md` §Combat System + `combat-formulas.md`. The
> non-combat research (tooling, decomp, 5e API, class mapping) is original.

---

## 1. Executive summary

- **Target platform:** Game Boy Advance (`.gba`). Fire Emblem was never released on GBC, so `.gba` is the right pick. The hack will run on any GBA emulator (mGBA recommended) and on flash carts.
- **Recommended base game:** **Fire Emblem: The Sacred Stones (FE8U)**. It has the most mature tooling, the most active decompilation project (FE8U is "very near completion"), branching promotions and a world map — which map nicely onto D&D-style class choices and party-driven adventuring.
- **Recommended build path:** Work in the **fireemblem8u decompilation** (C source that recompiles into the original ROM), driven by **Claude Code in interactive sessions** — *not* an autonomous loop. The session-driven model keeps the workflow token-efficient and human-in-the-loop. Look at **Agent Oak** (Claude × `pokeemerald`) and **FE Infinity** (LLM × FE8 buildfiles) for inspiration on *patterns* — CLAUDE.md design, MCP wiring, build-as-gate — but skip the GitHub-Actions overnight cycles unless and until token budget makes it cheap. Fall back to FEBuilder for surgical GUI tweaks the agent shouldn't touch.
- **Combat translation philosophy (FE-strict):** Keep Fire Emblem's grid, permadeath, turn flow, triangle, **and its hit/avoid/might/crit resolution** fully intact. D&D rides on top as flavor: damage-type *names* as cosmetic per-weapon labels (the triangle stays FE-native — Sword/Axe/Lance, Anima/Light/Dark), spells reskinned as FE tomes, and a single cosmetic d20 flourish on an FE crit. No d20-vs-AC, no advantage, no saving throws, no resistance multiplier — those break FE's tuned curve (see §6).
- **5e content:** Two sources cover most needs. [**dnd5eapi.co**](https://www.dnd5eapi.co/) is the clean REST one — 12 SRD classes, 9 races, 319 spells, ~334 monsters. [**Open5e**](https://api.open5e.com/) (v1 + v2) covers the same SRD classes *plus* 17 third-party OGL/CC-BY documents — Tome of Beasts 1/2/3, Creature Codex, Deep Magic, Vault of Magic, Black Flag SRD, Level Up Advanced 5e, Critical Role's Tal'Dorei. Use Open5e for *broader monster/spell/item content*. **Non-SRD classes and subclasses (Artificer, Hexblade, Circle of Spores, Bladesinger, etc.) are not legally available in any public API** — they have to be hand-rolled per character. Strategy: snapshot dnd5eapi + Open5e once into local JSON; hand-write YAML stat blocks for the campaign's specific non-SRD characters.

---

## 2. Goals and constraints

**Goals**

- Ship a playable `.gba` ROM that runs on stock GBA emulators and hardware.
- Inspired by Nicolas's D&D 5e campaign — the PCs and key NPCs from that campaign appear as Fire Emblem units.
- Combat should *read* like D&D (themed classes, damage-type labels, a crit flourish) while **playing like Fire Emblem** (grid tactics, permadeath, weapon triangle, FE hit/avoid/might resolution).
- Be agent-friendly enough that Claude Code (or similar) can do a meaningful share of the implementation work.
- **Reusable across campaigns.** The engine modifications (the cosmetic crit flourish, damage-type *labels*, the spell-tome/gold economy, custom FE-native skill procs, the combat-preview icon) are built once. Campaign content (PCs, NPCs, chapters, maps, portraits, dialogue) is data-driven and swappable. Building a second game for a different campaign (Curse of Strahd, a homebrew, etc.) should require only a new `content/campaigns/<name>/` folder — zero engine changes. Think of it as a "D&D-on-GBA engine" that ships with one campaign, not a one-shot hack.

**Constraints**

- GBA hardware ceiling: 32 MB cart, 256 KB EWRAM, 32 KB IWRAM, tile-based PPU. Most fancy modern UI ideas (3D dice, particle storms) are off the table.
- Legal: you must own a copy of the original ROM. Distribute only the patch (`.ups` / `.bps`) or the source — never a pre-patched ROM.
- 5e SRD content is open under the OGL/CC-BY; non-SRD content (subclasses outside the SRD, named monsters from supplements, etc.) is not.

---

## 3. Build approach — choosing a foundation

### 3.1 Why Fire Emblem 8: Sacred Stones

Three GBA Fire Emblems are commonly used as hack bases. FE8 wins on every relevant axis for this project:

| Dimension | FE6 (Binding Blade, JP) | FE7 (Blazing Blade, US) | **FE8 (Sacred Stones, US)** |
|---|---|---|---|
| Decompilation status | ~50% (code), early on data | Reference-only disassembly | **Very near completion** (US version) |
| FEBuilder support | Yes | Yes | **Yes, primary target** |
| Buildfile tutorials | Sparse | Mature | **Mature, most examples** |
| Promotion system | Linear | Linear | **Branched (2 paths per class)** — maps to D&D subclasses |
| Trainee units | No | No | **Yes** — Ross/Amelia/Ewan map to multiclassing |
| World map / free chapter order | No | No | **Yes** — supports D&D-style "side quest" pacing |
| Community size (hacks shipped) | Smaller | Large | **Largest** |
| Localization | JP only (needs translation patch) | US | US |

The FEUniverse decomp portal lists the four active projects: `FireEmblemUniverse/fireemblem8u` (FE8U, near-complete), `FireEmblemUniverse/fireemblem6j` (~half), `MokhaLeee/FireEmblem7J` (early), `StanHash/fe7_us` (reference disassembly only).

**Decision:** Base everything on FE8U.

### 3.2 The four ways people hack Fire Emblem

There are four real workflows. They're not mutually exclusive — most serious hacks use a mix.

1. **FEBuilder (GUI)** — `FEBuilderGBA` is a Windows-first GUI editor that opens a `.gba` and lets you point-and-click at every data table, portrait, map, animation, and patch. Great for surgical tweaks and for non-programmers. Hard to version-control (it edits the ROM directly), and not particularly agent-friendly.

2. **Buildfiles + Event Assembler** — Source-controlled text files (event scripts, dialogue, unit definitions) that get assembled by `ColorzCore` (the modern Event Assembler) into the final ROM. The community standard for serious hacks. Auto-hooking via `lyn` lets you patch C functions in. This is what **FE Infinity** generates.

3. **Decompilation (C source)** — The `fireemblem8u` project is a *matching* decompilation: you build it with the original `agbcc` compiler and it produces a byte-identical `fireemblem8.gba`. Once it builds clean, you can edit C source files (e.g., `src/bmunit.c`) and add new features in C rather than ASM. **This is the best workflow for an AI agent**, because the entire game is now legible source code rather than hex.

4. **Custom engines (not our pick)** — Lex Talionis (Python/Pygame), SRPG Studio (Windows), Tactile, etc. These produce standalone executables, **not** `.gba` files, so they're disqualified by the user's requirement. Worth knowing they exist if scope ever changes.

### 3.3 Recommended toolchain

```
fireemblem8u (decomp, C)
        │
        ├── agbcc (matching compiler)
        ├── devkitARM / GNU Arm Embedded Toolchain
        ├── Event Assembler (ColorzCore) for events/dialogue
        ├── lyn  (auto-hook C functions into vanilla code)
        ├── Png2Dmp + PortraitFormatter (graphics)
        └── mGBA  (debug emulator with scripting)

FEBuilder (GUI) — kept as escape hatch for:
        • portrait insertion sanity-check
        • last-mile tweaks before release
        • diff-checking that buildfile output matches expectations

Claude Code — driving the C-edit loop
GitHub Actions — autonomous cycles (Agent Oak pattern)
```

Build command (canonical, from the fireemblem8u README):

```
./scripts/quickstart.sh --rom /path/to/baserom.gba
# or, after first setup:
make fireemblem8.gba -j$(nproc)
```

Success looks like the line `fireemblem8.gba: OK` (sha1 match).

---

## 4. Agent / Claude harnesses

Two pieces of prior art are directly relevant — but **neither is the right literal template if you don't have unlimited tokens to burn**. Read them as design references, then jump to §4.3 for the recommended workflow.

### 4.1 Agent Oak — Claude × Pokémon Emerald decomp (reference, not template)

`alvarodms/agentoak` is "an AI agent whose mission is to autonomously explore, modify, and eventually build a Pokémon ROM hack over many iterative cycles." It runs Claude Code on the `pokeemerald` decompilation in a loop:

1. Reviews persistent memory and journal from prior cycles.
2. Plans the next change.
3. Reads/edits C source, JSON, assembly, map data.
4. Runs `make` to verify the ROM compiles.
5. Reflects, writes findings back to memory.
6. Publishes a new `.gba` to GitHub Releases.

It runs unattended on GitHub Actions on a schedule, and the community files GitHub Issues that the agent triages. **116 release tags** at time of writing. The repo structure is the template worth stealing:

```
agentoak/
├── .claude/         # CLAUDE.md and agent config
├── .mcp.json        # MCP server configuration
├── memory/          # persistent agent memory across cycles
├── journal/         # per-cycle activity log
├── docs/            # human-curated reference
├── pokeemerald/     # the decomp itself
├── src/             # TypeScript harness code
└── personality.json # voice / decision rules
```

**The catch:** Agent Oak runs *unattended* and *constantly*. 116 cycles is a lot of Claude API spend. The structure is worth stealing; the "let it run forever" loop is not, unless you want a recurring monthly bill. For a personal project, use Agent Oak's CLAUDE.md and repo layout, but drive the loop manually (see §4.3).

### 4.2 FE Infinity — LLM × FE8 buildfiles

`i-am-neon/fe-infinity` (Neon, Dec 2024) chains LLM calls to produce a complete short FE8 hack — story, characters, unit placement, dialogue — and emits buildfiles that assemble into a `.gba`. Generates "a 3-chapter game in 100 seconds for less than a penny." Honest about limits: LLMs are bad at spatial map design and at maintaining narrative coherence across chapters, so it picks maps from a curated pool of 60 community maps rather than generating them.

**What's useful from FE Infinity for us:**
- Validation that the buildfiles route can be driven entirely by an agent.
- Patterns for representing FE data (units, chapters, dialogue) as LLM-friendly JSON.
- The "AI picks from a curated pool" pattern for things LLMs are bad at (maps, sprites).

**What we'd do differently:**
- Anchor on the C decomp, not just buildfiles, so the agent can change *systems* (e.g., insert the combat-flavor layer + custom skill procs) and not just *content*.
- Put a human in the loop on map design and pacing.

### 4.3 Recommended harness — session-driven, token-aware

The right model for a personal project on a finite token budget is **Claude Code running interactively, in scoped sessions, with humans gating cost-heavy decisions.** No GitHub Actions cron, no overnight autonomous runs. You sit down, work for 30–90 minutes with the agent, commit, and stop.

```
fe8-dnd-hack/
├── CLAUDE.md                  # project conventions, key file pointers, "what the agent should know"
├── .claude/
│   ├── commands/              # /build, /test-chapter, /translate-pc – the actions you repeat
│   └── settings.json          # model picks per command (Haiku for content, Sonnet for code, Opus rare)
├── .mcp.json                  # MCP servers (mGBA-script, srd-cache) – keep this short
│
│   ── ENGINE (reusable across all campaigns) ──────────────────────
├── fireemblem8u/              # the decomp as a submodule
├── engine/                    # our C diffs / new modules layered on the decomp
│   ├── combat-fx/             # cosmetic crit flourish + custom FE-native skill procs
│   ├── damage-types/          # weapon damage-type flavor labels (UI/descriptions only)
│   ├── spell-slots/           # per-tome charge tracker; deplete + gold-restock (decision B)
│   ├── class-defs/            # the D&D-flavored FE class table (shared across campaigns)
│   └── ui/                    # combat-preview reskin (vanilla Hit/Crit box + damage-type icon)
│
│   ── CONTENT DATA (shared reference, not campaign-specific) ─────
├── data/
│   ├── srd-snapshot.json      # frozen pull from dnd5eapi.co
│   ├── open5e-snapshot.json   # frozen pull from Open5e (monsters/spells/items)
│   └── homebrew/              # hand-rolled YAML for non-SRD classes (Artificer, Metallurgist…)
│
│   ── CAMPAIGNS (one folder per adventure — swap to build a different .gba) ──
├── campaigns/
│   ├── rime-of-the-frostmaiden/       # ← the first and MVP campaign
│   │   ├── campaign.yaml              # metadata: title, chapter count, start level, level cap
│   │   ├── pcs/                       # YAML for each PC (stats, class, growth rates, inventory)
│   │   ├── npcs/                      # YAML for key NPCs + enemies
│   │   ├── chapters/                  # one YAML per chapter (units, map ref, objectives, dialogue)
│   │   ├── maps/                      # .tmx or FEBuilder map exports
│   │   ├── portraits/                 # character portraits (FE-format PNGs)
│   │   └── events/                    # EA buildfile scripts per chapter (if needed beyond YAML)
│   └── [future-campaign]/             # same structure; zero engine changes needed
│
│   ── TOOLS (build pipeline) ─────────────────────────────────────
├── tools/
│   ├── pull-srd.ts            # one-shot SRD + Open5e downloader
│   ├── map-class.ts           # 5e class → FE class mapper (pure code, no LLM)
│   ├── build-campaign.ts      # reads a campaign folder → injects into decomp → runs make
│   └── build-events.ts        # YAML → EA buildfile codegen
└── Makefile                   # `make CAMPAIGN=rime-of-the-frostmaiden` builds the .gba
```

**The key separation:** `engine/` contains C code that patches the FE8 decomp — it ships with every campaign. `campaigns/<name>/` contains pure data (YAML, PNGs, map files, event scripts). The `Makefile` takes a `CAMPAIGN=` argument, copies that campaign's data into the decomp's data tables, applies the engine patches, and runs `make`. Two campaigns, two `.gba` files, one engine.

**What this means in practice:**
- Building a new campaign = creating a new `campaigns/curse-of-strahd/` folder and filling in the YAMLs. No C code, no recompiling the engine.
- The `tools/build-campaign.ts` script is the glue: it reads `campaign.yaml`, walks the `pcs/` and `chapters/` folders, runs the class mapper, generates EA buildfiles, and injects everything into the decomp's data tables before the final `make`.
- Shared resources (the SRD snapshot, Open5e snapshot, homebrew class definitions) live in `data/` and are available to every campaign. A Metallurgist PC in campaign A and campaign B reads the same `data/homebrew/classes/metallurgist.yaml`.
- Engine improvements (say, adding a "concentration" mechanic later) benefit every campaign automatically.

Notice what's **not** there: `memory/` (no autonomous state to remember between sessions — git history is the memory), `journal/` (you don't need an agent narrating its own work), `personality.json`, `.github/workflows/agent-cycle.yml`.

**MCP servers — keep this list small**
- `mGBA` scripting bridge (Lua → MCP) — let Claude boot the ROM, take a screenshot, read a memory address, advance N frames. The single highest-leverage MCP for this project, because it lets the agent *verify changes worked* without you watching.
- `srd-cache` — local-only static-file server that serves `content/srd-snapshot.json` and `content/open5e-snapshot.json`. Free of API rate limits and zero network during build.
- That's it. Skip `gh` (you don't need agent-driven issue triage), skip browser MCPs (the agent has WebFetch already).

**Cost discipline — explicit model choices per task type**

| Task | Model | Why |
|---|---|---|
| Edit a single C file (~200 LOC scope) | Sonnet | Sweet spot for code edits |
| Implement a cross-cutting change (e.g. d20 patch touching 8 files) | Opus with extended thinking, **once per change** | Pay the premium where it counts |
| Generate dialogue, unit-block YAML, item descriptions | Haiku | High volume, low complexity, ~10× cheaper |
| Smoke-test "did the ROM build" / read mGBA RAM | No LLM — pure script | Don't pay tokens for `sha1sum` |
| Map a 5e statblock → FE unit YAML | Haiku, then human eyeball | The mapper is mostly mechanical |

**Session pattern that minimizes spend**

1. **Plan before prompting.** Write a 2–3 sentence brief of what this session will accomplish. Keep it in a `SESSION.md` at the repo root and update it.
2. **Start each session with `git status` + a CLAUDE.md re-read.** Cheap, prevents the agent from re-deriving project context.
3. **One feature per session.** Don't ask the agent to "make chapter 2 *and* refine the d20 UI *and* add three NPCs." That triples token cost via re-loading context.
4. **Always end with `make` green.** A broken build at session end means next session pays to rediscover the breakage.
5. **Commit small.** Smaller diffs are cheaper for the agent to re-read next time.
6. **Use `/clear` between unrelated tasks** — don't carry the d20-patch context into a dialogue-writing task.

**What to do *like* Agent Oak even in session mode**
- A `CLAUDE.md` that points at the 10–15 most-edited files in the decomp.
- A "memory" file (`docs/decisions.md`) where *you* (not the agent) write down decisions you don't want to re-litigate.
- A build gate (`make` must pass) at the end of every change.
- The agent should always read `docs/decisions.md` and the current chapter's YAML before making changes — those are cheap (~1k tokens) compared to re-reading C source.

**Rough cost estimate, session-driven**
- A typical 60-minute session that lands one feature: ~$2–8 in API spend depending on model mix.
- One full chapter (5–10 sessions for design + content + playtest fixes): ~$20–60.
- A 3-chapter MVP: ~$60–200. Compared to Agent Oak's "always running" pattern: orders of magnitude less.

**Build time numbers** — `fireemblem8u` clean build ~2–4 min on a modern laptop, incremental ~5–15 sec. That's fast enough that you don't need the agent to "wait for CI" — it can run `make` directly and react.

---

## 5. D&D content sources — what's reachable, what isn't

There is no single "complete D&D 5e API." There are several overlapping sources, each with different content scopes and licensing constraints. The user's specific ask — *Artificer, Druid Circle of Spores, and similar* — runs straight into the hardest part: **the most-loved subclasses are not in any open API**. Below is the honest landscape, then a strategy.

### 5.1 The four real options

| Source | Scope | License | Use it for |
|---|---|---|---|
| **dnd5eapi.co** | SRD 5.1 — 12 classes, 9 races, 319 spells, ~334 monsters, equipment, conditions | CC-BY-4.0 (via WotC SRD) | Clean REST shape, primary "core mechanics" reference |
| **Open5e** (`api.open5e.com` v1 + v2) | Same 12 SRD classes, but *much* more for monsters/spells/items via 17 third-party docs (Tome of Beasts 1/2/3, Creature Codex, Deep Magic, Vault of Magic, Black Flag SRD, Level Up Advanced 5e, Tal'Dorei, etc.) | OGL / CC-BY / ORC depending on doc | Broader monster bestiary, more spells, more magic items |
| **D&D Beyond's SRD 5.2.1 page** | SRD 5.2 (2024 update) — same 12 classes, modernized rules | CC-BY-4.0 | Reference for 2024 rules changes if you want them |
| **5e.tools / Plutonium / community JSON dumps** | Everything in published WotC books — Artificer, Hexblade, Spore Druid, Bladesinger, every monster | Legally gray — community treats as "respect copyright, only use content you own" | Personal reference only; do not redistribute |

### 5.2 The Artificer problem (and the answer)

**Hard truth:** Artificer, Hexblade, Circle of Spores, Bloodhunter, and the long tail of beloved subclasses are *not* in the SRD (5.1 or 5.2) — WotC explicitly excludes them for brand-identity reasons. Open5e's `classes` endpoint mirrors the SRD list and returns the same 12 classes. There is no legitimate public API that ships their mechanical text.

**What that means in practice:** if a PC in the campaign is an Artificer (Battle Smith), the build pipeline can't auto-pull "Artificer level 7 features" from a feed. You — or the agent — read the published class description (from your own copy of Tasha's Cauldron of Everything) and **hand-write the YAML stat block**. This is fine, because:

1. The hack only needs *the specific characters that exist in your campaign*, not every subclass ever published. If you have one Artificer PC, you write one Artificer YAML.
2. Mechanics are not copyrightable; the published text is. "Level 5 Battle Smith Artificer with these stats and a Steel Defender" is fair to translate; copying Tasha's flavor text verbatim is not.
3. For a personal ROM hack distributed only as a patch (not a pre-patched ROM), this is normal fair-use territory.

**Recommended directory layout** (already in §4.3):

```
content/
├── srd-snapshot.json         # auto-pulled; the 12 SRD classes, monsters, etc.
├── open5e-snapshot.json      # auto-pulled; broader monsters/spells/items
└── homebrew/
    ├── classes/
    │   ├── artificer.yaml          # hand-written, based on your campaign PC
    │   └── bloodhunter.yaml
    ├── subclasses/
    │   ├── circle-of-spores.yaml
    │   └── hexblade.yaml
    └── spells/
        └── any-non-SRD-spells.yaml
```

The `tools/map-class.ts` mapper reads from all three sources transparently — SRD first, Open5e second, homebrew folder last (highest precedence). Agent never sees the difference.

### 5.3 dnd5eapi.co — base shape (recommended primary)

**Base URL:** `https://www.dnd5eapi.co/api/2014/` (the `/2014` prefix pins to 2014 SRD; an unversioned `/api/` redirects there. A 2024 SRD endpoint may follow.)

**Coverage (verified by direct fetches on 2026-05-26):**

| Resource | Endpoint | Count | Notes |
|---|---|---|---|
| Classes | `/classes` | 12 | Barbarian, Bard, Cleric, Druid, Fighter, Monk, Paladin, Ranger, Rogue, Sorcerer, Warlock, Wizard |
| Races | `/races` | 9 | Dragonborn, Dwarf, Elf, Gnome, Half-Elf, Half-Orc, Halfling, Human, Tiefling |
| Subclasses | `/subclasses` | varies | Limited to SRD subclasses (e.g., Fighter only has Champion) |
| Spells | `/spells` | 319 | Levels 0–9, full descriptions, damage tables, components, save DCs |
| Monsters | `/monsters` | ~334 | Full statblocks with actions, abilities, CR |
| Equipment | `/equipment` | ~237 | Weapons, armor, gear, with cost/weight/damage |
| Conditions | `/conditions` | 15 | Blinded, Charmed, Frightened, etc. |
| Damage types | `/damage-types` | 13 | Fire, Cold, Slashing, etc. |
| Magic items | `/magic-items` | ~362 | |
| Features | `/features` | many | Class features by level |

**Example payloads** (abridged; full ones in §10 references)

```json
// /classes/fighter
{
  "index": "fighter", "name": "Fighter", "hit_die": 10,
  "saving_throws": [{"index": "str"}, {"index": "con"}],
  "proficiencies": [{"index": "all-armor"}, {"index": "martial-weapons"}, ...],
  "subclasses": [{"index": "champion"}]
}

// /spells/fireball
{
  "name": "Fireball", "level": 3, "casting_time": "1 action",
  "range": "150 feet", "area_of_effect": {"type": "sphere", "size": 20},
  "damage": {
    "damage_type": {"index": "fire"},
    "damage_at_slot_level": {"3": "8d6", "4": "9d6", "5": "10d6", ...}
  },
  "dc": {"dc_type": {"index": "dex"}, "dc_success": "half"},
  "classes": [{"index": "sorcerer"}, {"index": "wizard"}]
}

// /monsters/goblin
{
  "name": "Goblin", "size": "Small", "type": "humanoid",
  "armor_class": [{"type": "armor", "value": 15}],
  "hit_points": 7, "hit_dice": "2d6",
  "speed": {"walk": "30 ft."},
  "strength": 8, "dexterity": 14, ...,
  "challenge_rating": 0.25, "proficiency_bonus": 2, "xp": 50,
  "special_abilities": [{"name": "Nimble Escape", "desc": "..."}],
  "actions": [
    {"name": "Scimitar", "attack_bonus": 4,
     "damage": [{"damage_dice": "1d6+2", "damage_type": {"index": "slashing"}}]}
  ]
}

// /equipment/longsword
{
  "name": "Longsword", "weapon_category": "Martial", "weapon_range": "Melee",
  "damage": {"damage_dice": "1d8", "damage_type": {"index": "slashing"}},
  "two_handed_damage": {"damage_dice": "1d10"},
  "properties": [{"index": "versatile"}]
}

// /races/elf
{
  "name": "Elf", "speed": 30,
  "ability_bonuses": [{"ability_score": {"index": "dex"}, "bonus": 2}],
  "traits": [{"index": "darkvision"}, {"index": "fey-ancestry"}, ...],
  "subraces": [{"index": "high-elf"}]
}
```

**Recommended pull strategy:** Write `tools/pull-srd.ts` that walks each `/{resource}/` index and recursively fetches each item by `url`, dumping the result to `content/srd-snapshot.json`. Run it once, commit the snapshot, and treat it as the source of truth. Don't make the build depend on the live API.

### 5.4 Open5e — broader content via OGL/CC-BY third parties

**Base URLs:** `https://api.open5e.com/v1/` (legacy, still works) and `https://api.open5e.com/v2/` (current).

Open5e mirrors the SRD class list (same 12 — no Artificer here either) but its real value is in *content*: spells, monsters, magic items, and equipment pulled from 17 OGL/CC-BY/ORC-licensed documents. The `/v1/documents/` endpoint enumerates them — at the time of this writing:

| Slug | Source | What it adds |
|---|---|---|
| `wotc-srd` | WotC SRD 5.1 | The baseline |
| `tob`, `tob2`, `tob3`, `tob-2023` | Kobold Press *Tome of Beasts* 1/2/3 | Hundreds of additional monsters |
| `cc` | Kobold Press *Creature Codex* | More monsters |
| `dmag`, `dmag-e` | Kobold Press *Deep Magic* + Extended | Hundreds of new spells |
| `vom` | Kobold Press *Vault of Magic* | Magic items |
| `toh` | Kobold Press *Tome of Heroes* | Player options |
| `warlock` | Kobold Press *Warlock* periodical | Extras |
| `menagerie`, `a5e` | EN Publishing *Level Up Advanced 5e* | Alt-system monsters + classes |
| `tdcs` | Green Ronin *Critical Role: Tal'Dorei Campaign Setting* | Setting content |
| `blackflag` | Kobold Press *Black Flag SRD* | Full system (ORC license) |
| `o5e` | Open5e original homebrew | Community content |

**Endpoint quick reference (v2 is the current API):**

```
/v2/spells/        – broader spell library
/v2/creatures/     – broader bestiary (was /monsters/ in v1)
/v2/items/         – mundane equipment
/v2/magicitems/    – magic items
/v2/weapons/       – weapons with damage type, properties
/v2/armor/         – armor with AC, properties
/v2/species/       – races (v2 calls them species, per 2024 rules)
/v2/classes/       – classes (still the SRD 12)
/v2/feats/         – feats
/v2/backgrounds/   – backgrounds
/v2/damagetypes/   – damage types
/v2/conditions/    – conditions
```

**Filter by document** with `?document__slug=tob` to pull only Tome of Beasts content, etc. Use `?fields=name,slug,...` to project only the columns you need (smaller payload).

**Recommended pull strategy:** A second pass after the dnd5eapi pull — walk Open5e's v2 endpoints with explicit document filters, dump to `content/open5e-snapshot.json`. The deduper in `tools/map-class.ts` should prefer SRD items by slug when they overlap.

---

## 6. Translation plan: D&D 5e → Fire Emblem

### 6.1 Design philosophy — what to keep from each

Keep from **Fire Emblem**: grid movement, turn-by-turn unit activation, permadeath, weapon triangle (Sword > Axe > Lance > Sword), magic trinity (Anima > Light > Dark > Anima), growth-rate-based level-ups, support conversations, character permadeath, recruitment.

Keep from **D&D 5e** as **flavor on top** (never as resolution): the characters, classes, and subclasses; damage-type *names* (slashing, fire, necrotic…) as cosmetic labels; spells reskinned as FE tomes/staves; ability-score identity folded to FE stats; and a single **cosmetic d20 flourish** when an FE crit fires, for the nat-20 feel. AC, saving throws, advantage/disadvantage, and the damage-type resistance multiplier are **not** mechanics (see `decisions.md` §Combat System).

Drop or simplify: 5e action economy (action / bonus / reaction) collapses into FE's "one action per turn unless Speed-doubled." 5e movement-in-feet collapses into FE's "Move stat in tiles." 5e exhaustion, inspiration, and short-rest mechanics drop unless they earn their keep.

### 6.2 The D&D *feel* on an FE chassis

The goal is a game that **reads** like D&D while **playing** like Fire Emblem. The D&D flavor surfaces through presentation, not resolution:

- **Named, themed weapons/tomes** carry a D&D damage-type icon + description; the stat block stays vanilla FE (Mt / Hit / Crit / Rng / Uses).
- **Reskinned class identities** (a Berserker that's a hermit-crab barbarian; a Summoner that's a spore druid).
- **A cosmetic d20 crit flourish** — when an FE crit fires, a brief "d20 lands on 20" animation plays. It is the one visible die in the game, and it is purely decorative; FE's SKL-based crit rate decides the crit.

> **Rejected alternative.** An earlier exploration proposed a BG3-style *resolution* layer (visible d20 vs AC, advantage/disadvantage, spell save DCs, damage-type resistance). It was not adopted — that layer changes FE8's tight, readable, well-tuned difficulty curve, and FE-strictness is the project's spine. The die is flavor, not resolution.

### 6.3 Combat formula — vanilla FE8

Combat uses FE8's native math unchanged (`fireemblem8u/src/bmbattle.c`; full reference in `combat-formulas.md`):

```
Hit%   = Attacker_HitRate − Defender_Avoid + TriangleHitBonus       (clamped 0–100)
Crit%  = Attacker_CritRate − Defender_CritEvade                     (clamped 0–100)
Damage = Attacker_Attack − Defender_Defense                          (floored at 0)
AttackSpeed = Speed − max(0, WeaponWeight − Constitution)
If AttackSpeed_attacker − AttackSpeed_defender ≥ 4, attacker doubles
Crit damage = Damage × 3
```

**Why vanilla FE (not a d20 hybrid):**
- FE's hit/avoid/might is what makes the game readable and well-tuned. A d20-vs-AC layer at FE's HP scale (~20–60) swings far more wildly and breaks the curve.
- Weapon Might is **fixed FE might** (tuned from the 5e die's average), not a rolled die — pure 5e damage-vs-HP at FE's HP scale would make everything two-shot.
- The whole party — martials and casters — shares one FE economy (gold, durability, the triangle). D&D supplies identity, not arithmetic.
- The combat preview box stays vanilla ("Hit 78  Crit 5"), optionally with a small damage-type icon; the only added motion is the crit flourish.

### 6.4 Class mapping (12 classes → FE base classes)

Each PC has a 5e class and (often) a subclass. Below is a default mapping; PCs may override.

| 5e Class | FE base class | Primary ability | Map to FE STR/MAG | Notes / promotion options |
|---|---|---|---|---|
| Fighter | **Fighter** (axes) or **Mercenary** (swords) | STR (rarely DEX) | Physical | → Warrior / Hero / Great Knight |
| Barbarian | **Pirate** or **Brigand** | STR | Physical | → Berserker. Rage = consumable "Berserk" status item. |
| Paladin | **Cavalier** | STR + CHA | Physical | → Paladin (mounted) / Great Knight. Smite = activated skill. |
| Ranger | **Archer** or **Nomad** | DEX | Physical | → Sniper / Ranger / Nomadic Trooper |
| Rogue | **Thief** | DEX | Physical | → Assassin / Rogue. Sneak Attack = innate crit bonus when flanking. |
| Monk | **Myrmidon** (sword) or unarmed-only **Brawler** custom | DEX + WIS | Physical | → Swordmaster. Ki points = "Stamina" resource. |
| Cleric | **Cleric** / **Priest** | WIS | Magical | → Bishop / Valkyrie. Has both staff (heal) and Light magic (smite). |
| Druid | **Shaman** (Dark) or custom **Druid** class | WIS | Magical | → Summoner (Sacred Stones unique class). Wild Shape ≈ class swap item. |
| Wizard | **Mage** | INT | Magical | → Sage / Mage Knight. Anima magic. |
| Sorcerer | **Mage** (Fire/Tana variant) | CHA | Magical | → Sage. Mark sorcerers with red hair / unique tomes. |
| Warlock | **Shaman** (Dark) | CHA | Magical | → Druid (Dark Sage promotion). Eldritch Blast = a cantrip-tier dark tome. |
| Bard | **Dancer** (Sacred Stones uses Dancer) or **Troubadour** | CHA | Mixed | → Valkyrie or custom. Inspiration = Dancer's refresh action. |

**Subclasses → branched promotions**, e.g. Fighter/Champion → Warrior (axe focus); Cleric/Light Domain → Bishop; Wizard/Evocation → Sage; Rogue/Assassin → Assassin (FE's class name maps 1:1). Where the SRD only ships one subclass, treat that as the default and design custom subclasses for the rest as the campaign demands.

### 6.5 Race mapping (9 races → unit flavor + stat mods)

FE doesn't have a "race" data field on units, but it has portraits, names, and base stats — which is the same expressive surface. Apply ability bonuses as **base stat modifiers** at recruitment.

| 5e Race | FE flavor | Stat mods (applied to base) | Notes |
|---|---|---|---|
| Human | No special art treatment | +1 to all (FE: +1 to two stats player picks) | Variant Human = pick a class skill |
| Elf | Elongated ears in portrait, "Frelian" naming | +2 DEX → +2 SPD | Subraces: High Elf (+1 INT), Wood Elf (+1 WIS, +5 MOV) |
| Dwarf | Stocky portrait, beards, "Jehannan" naming | +2 CON → +2 HP/CON, slower SPD | Hill (+1 WIS), Mountain (+2 STR) |
| Halfling | Small-frame sprite, child-coded portrait | +2 DEX → +2 SPD | Lightfoot (+1 CHA), Stout (+1 CON) |
| Gnome | Same portrait scale as halfling | +2 INT → +2 MAG | Rock (+1 CON), Forest (+1 DEX) |
| Half-Elf | Mixed art cues | +2 CHA + 2 of player's choice | |
| Half-Orc | Tusks in portrait, "Grado" naming | +2 STR, +1 CON | Savage Attacks: crit threshold lowered by 1 |
| Dragonborn | Custom Manakete-style portrait (FE has draconic units) | +2 STR, +1 CHA | Breath weapon = innate cantrip tome by chromatic color |
| Tiefling | Horned portrait, "Carcino" naming | +2 CHA, +1 INT | Infernal Legacy = innate dark cantrips |

### 6.6 Spell mapping

The 319 5e spells need a coherent home in FE's two magic systems (tomes and staves).

**Mapping rules:**

| 5e spell type | FE equivalent | Implementation |
|---|---|---|
| Cantrip (level 0) attack spell (e.g. Fire Bolt, Eldritch Blast) | **High-count tome (decision B)** | A high-use tome (~30–50 uses) that depletes and restocks with gold — generous, not truly infinite. |
| Cantrip utility (Light, Mage Hand, Guidance) | **Out-of-combat skill** or **support effect** | Most don't need to appear in combat at all. |
| Leveled damage spell single target (Magic Missile, Witch Bolt) | **Limited-use tome** | Uses = number of spell slots of that level. |
| Leveled damage spell AoE (Fireball, Lightning Bolt) | **Existing FE AoE tome** (Bolting, Eclipse, Purge) | Or new AoE tome with the spell's exact AoE shape — FE supports "shape data" for AoE attacks. |
| Save-or-suck (Sleep, Hold Person, Banishment) | **Staff** | FE's status staves (Sleep, Berserk, Silence) are exactly this. Save DC = staff hit rate. |
| Healing (Cure Wounds, Healing Word, Mass Cure Wounds) | **Healing staff** (Heal, Mend, Recover, Physic) | Healing amount scales with caster's MAG and spell level. |
| Buffs (Bless, Haste, Shield of Faith) | **Status effect on adjacent ally** | Implement as Dance-like action with effect persisting N turns. |
| Summons (Conjure Animals, Find Familiar) | **Summoner class skill** (FE8 has this!) | Sacred Stones literally has a Summoner class that creates Phantom units. Repurpose. |
| Utility / non-combat (Detect Magic, Knock, Find the Path) | **Out-of-combat** | Either a passive class trait or skip. |

**Spell slot → uses mapping (suggested table):**

| 5e slot level | Tome uses for a single-target damage spell |
|---|---|
| 1 | 8 uses (matches FE's typical low-tier tome) |
| 2 | 6 |
| 3 | 4 |
| 4 | 3 |
| 5 | 2 |
| 6+ | 1 use (legendary tomes) |

### 6.7 Monster mapping (D&D CR → FE enemy)

| CR range | FE enemy class to spawn | Approx level | Notes |
|---|---|---|---|
| 0 – 1/8 | Bandit, Soldier | 1–3 | Trash mobs |
| 1/4 – 1/2 | Fighter, Brigand, Archer | 3–5 | Standard enemy phase |
| 1 – 2 | Cavalier, Knight, Mage | 5–8 | Mid-chapter waves |
| 3 – 5 | Hero, Sniper, Sage, Druid | 8–12 | Mini-bosses |
| 6 – 8 | Promoted classes at high level | 13–17 | Boss-tier |
| 9 – 12 | Boss + reinforcements | 18–20 | Final-chapter bosses |
| 13+ | Custom boss class | 20 | Save for the Big Bad |

**Mapping rule of thumb:** CR ≈ FE enemy level / 2. Never import 5e HP verbatim — divide by ~3 (5e CR-5 has ~85 HP; FE expects ~25–35), and set FE DEF/RES from the creature's armor/toughness feel (no AC).

**Worked example — Goblin (CR 1/4):**

```
5e:  HP 7, STR 8 (-1), DEX 14 (+2), Scimitar +4 (1d6+2), Shortbow +4 (1d6+2)   ← source data only
FE:  Class = Brigand
     Level = 2
     HP = 18, STR = 5, MAG = 0, SKL = 7, SPD = 8, LCK = 2, DEF = 4, RES = 1
     Inventory = Iron Axe or Iron Bow (fixed FE might)
     Skill = "Nimble Escape" (Disengage ≈ FE +1 MOV after attack)
```

### 6.8 The weapon triangle and damage-type labels

Keep FE's triangle **mechanically intact and FE-native** — it is the soul of FE combat:

```
        Sword
          ▲     ╲
          │      ╲
          │       ▼
       Lance ◄── Axe
```

- **Physical:** Sword > Axe > Lance > Sword — the "+1 ATK / +15 hit" bonus is exactly vanilla FE8.
- **Magic:** Anima > Light > Dark > Anima (same bonus).
- Keep the existing sprites; the player learns the loop by icon.

D&D **damage-type names** (slashing, bludgeoning, piercing, fire, cold, necrotic, radiant…) ride on top
as **cosmetic per-weapon labels** — an icon + description for flavor. They are *not* a relabel of the
triangle: a hermit-crab's claw and a bandit's axe are both the **axe type** and read identically. (An
earlier exploration renamed the triangle to Slashing/Bludgeoning/Piercing + Radiant/Necrotic/Elemental
and grouped axes as "bludgeoning"; dropped — it fought FE's weapon types and asset pipeline for no gain.)

**No resistance / vulnerability / immunity multiplier.** A ×0.5 / ×2 / ×0 damage-type multiplier has no
vanilla FE analogue and would modify FE damage under the hood, so it is not a mechanic. Where a matchup
genuinely matters to play, use **vanilla FE weapon effectiveness** — flag the weapon `effective` vs that
enemy class, the same way Hammers are effective vs armor:

| Iconic matchup | FE-native handling |
|---|---|
| Fire vs ice trolls / frost druids | fire weapon flagged `effective` vs that class |
| Bludgeoning vs skeletons | a bludgeon-type weapon flagged `effective` vs skeletons |
| Radiant vs undead | a light-type weapon flagged `effective` vs undead |

Everything else (a skeleton "resisting" piercing, a fiend "immune" to fire) is **narrative flavor only** —
the damage-type label sets the vibe; no multiplier runs. One flavor byte per weapon (the damage-type
label), no resistance bitmap.

**Mapping 5e weapons to FE slots** (the damage-type name rides on top as a label):

| 5e weapon | FE slot |
|---|---|
| Scimitar, shortsword, longsword, greatsword, rapier, falchion | Sword |
| Battleaxe, handaxe, greataxe, club, mace, warhammer, maul, flail | Axe |
| Spear, javelin, trident, pike, lance, halberd, glaive | Lance |
| Dagger | Sword (or Lance for thrown — pick by use) |
| Shortbow, longbow, crossbow, sling | Bow (outside the triangle, as in vanilla FE) |

**Weapon tiers** map onto FE's Iron/Steel/Silver ladder; damage is **fixed FE might** authored per FE
tier (no 5e-die conversion), never a rolled die:

| FE tier | 5e equivalent |
|---|---|
| Iron | Mundane / no bonus |
| Steel | Mundane, larger (a die step up) |
| Silver | +1 magic weapon |
| Brave (double-attack) | Same might, two attacks |
| Killer (high crit) | "Vicious" / Improved Critical variant |
| Reaver (anti-triangle) | Reverses the triangle |
| Legendary / personal | Named magic items (Vorpal Sword, Holy Avenger) |

### 6.9 Where the flavor layer patches into the decomp

Combat **resolution is left intact** — `bmbattle.c` / `BattleGenerateHitTriangle` / `BattleGenerateCrit`
are not touched. The work is the flavor layer on top:

| System | Files (in `fireemblem8u/src/`) | What changes |
|---|---|---|
| Combat resolution | `bmbattle.c`, `include/battle.h` | **No change** — vanilla FE hit / avoid / might / crit. |
| Damage-type label | `data/items.s` + new `damage_type.h` | One flavor byte per weapon (a damage-type enum) for the UI icon + description. No computation. |
| Iconic matchups | existing FE effectiveness data | Flag a few weapons `effective` vs an enemy class (fire vs ice troll, bludgeoning vs skeleton). Vanilla mechanic, no new code. |
| Combat preview UI | battle-forecast text rendering | Keep the vanilla "Hit / Crit" box; add only a small damage-type icon. |
| Crit flourish | new `engine/combat-fx/crit_anim.c` | Cosmetic "d20 lands on 20" animation when an FE crit fires (RNG helper wraps `bmRng.c`). |
| Spell-tome economy | new tracker (sidecar or `Unit` field) | Per-tome charges that deplete in use and restock with gold between chapters (decision B). |
| Class data | `data/classes.s` | Stock vanilla FE8 classes only (PCs, recruits, and enemies reuse FE8 chassis incl. monster classes) — no custom class entries. |

**Caveats**
- `agbcc` is GCC 2.95.1 — avoid C99 features (VLAs, some designated initializers). The decomp's existing code is the style guide.
- The `Unit` struct is referenced from hundreds of places; adding fields touches every save/load path. A sidecar lookup (keyed by unit ID) for spell-tome charges is the safer first pass. No AC and no resistance bitmap are stored — combat is vanilla FE — so the save budget stays small.

---

## 7. Per-character translation worksheet

Use this template per PC and per recurring NPC. Filling these in before the PRD is the main blocker.

```yaml
# content/pcs/your-pc-here.yaml
name: "Aelar Sunblade"
campaign_role: "Party tank"
five_e:
  race: "Half-Elf"
  class: "Paladin"
  subclass: "Oath of Devotion"
  level: 7
  ability_scores: {STR: 16, DEX: 10, CON: 14, INT: 8, WIS: 12, CHA: 16}
  ac: 18
  hp: 58
  proficiency_bonus: 3
  notable_features: ["Divine Smite", "Aura of Protection", "Channel Divinity"]
  spell_slots: {1: 4, 2: 2}
  signature_spells: ["Bless", "Cure Wounds", "Shield of Faith"]
  signature_weapon: "Longsword +1 and shield"
fire_emblem:
  base_class: "Cavalier"
  promoted_class: "Paladin"   # or "Great Knight" branch
  starting_level: 5
  starting_stats: {HP: 24, STR: 9, MAG: 4, SKL: 8, SPD: 7, LCK: 6, DEF: 9, RES: 5}
  growth_rates: {HP: 80, STR: 50, MAG: 25, SKL: 45, SPD: 40, LCK: 50, DEF: 45, RES: 30}
  inventory:
    - "Steel Sword"            # ≈ Longsword +1
    - "Iron Lance"
    - "Vulnerary"
    - "Bless tome (3 uses)"    # ≈ 1st-level slot, used as buff staff
  unique_skill: "Divine Smite — once per chapter, +10 dmg holy"
  portrait_ref: "see /content/portraits/aelar.png"
notes:
  - "PC was the moral anchor of the campaign — should be recruited early."
```

NPC template (lighter):

```yaml
# content/npcs/the-villain.yaml
name: "Vraxis the Pale"
campaign_role: "Big Bad of Arc 2"
five_e:
  type: "Lich"
  cr: 21
fire_emblem:
  class: "Druid"                 # FE's Dark Sage promoted
  level: 20
  stats: {HP: 60, STR: 0, MAG: 28, SKL: 22, SPD: 18, LCK: 0, DEF: 14, RES: 26}
  ac_equivalent: 17
  inventory: ["Eclipse", "Nosferatu", "Berserk Staff"]
  ai_pattern: "stationary boss, prioritizes high-INT units"
  defeat_quote: "...the silence I sought."
```

---

## 8. Risks and open questions

- **HP scale mismatch.** 5e spells are tuned for 50–200 HP. FE units have 20–60 HP. Direct damage import would one-shot everything. Mitigation in §6.3 (keep FE's `damage − DEF` model), but it needs playtesting; the agent should be told to keep an eye on this.
- **GBA UI real estate.** Combat preview window is ~96×40 px. Keep the vanilla Hit/Crit box and add only a small damage-type icon (reuse weapon-icon space). There's no AC/to-hit/dice line to fit.
- **Save-file size.** The FE save format reserves ~52 bytes per character slot. Combat is vanilla FE, so no AC or resistance bitmap is stored; the main add is per-tome charge counts. A sidecar lookup (keyed by unit ID) is the safe first pass. Audit early.
- **5e licensing scope.** SRD covers the basics but most published subclasses, monsters, and adventures are not SRD. If a PC was a Hexblade Warlock, you can call it that but not reproduce the official subclass text. Either rewrite or rename.
- **Map design.** FE Infinity validated that LLMs are bad at FE maps. Plan to pull from a curated map pool (60+ exist in the FE Repo) or draw maps by hand in Tiled / FEBuilder, then feed coordinates to the agent.
- **Permadeath vs D&D revival.** D&D PCs come back via Raise Dead. FE PCs do not. Decision: keep permadeath, treat in-fiction revivals as Casual Mode or as plot-mandated revivals between chapters.
- **Agent loop discipline.** Agent Oak only works because every cycle ends with `make` + a deterministic ROM-hash check. Build that gate into CI from day one.
- **Engine/content boundary discipline.** The engine/content split is powerful but easy to erode. Every time you hardcode a Frostmaiden-specific assumption into C code instead of reading it from YAML, the second campaign gets harder. The PRD should define the contract: "what does a campaign folder contain?" and "what can the engine assume?" Enforce the boundary from day one — if a feature doesn't work without Frostmaiden data, it belongs in `campaigns/`, not `engine/`.
- **Scope creep from extensibility.** "Making it reusable" can balloon scope if taken too far. Recommendation: build exactly what Frostmaiden needs, but *organize* it as reusable. Don't build a generic campaign editor or a class-definition DSL upfront — just make sure the data lives in YAML files, not hardcoded C arrays. That's enough to swap campaigns later without having designed a framework.

---

## 9. Recommended next steps (hand-off to PRD agent)

The order below reflects the engine/content split — build the reusable engine first, then fill in the Frostmaiden campaign as the first content pack.

**Phase 0 — Foundation (before the PRD)**
1. **Lock the base game decision.** FE8U recommended; confirm.
2. **Run the campaign-brief interview** (separate chat instance). Produce `campaign-brief.md` from the Frostmaiden PDFs and Nicolas's memory.
3. **Hand research.md + campaign-brief.md to the PRD agent** (third chat). Get a scoped, chapter-by-chapter feature spec.

**Phase 1 — Engine (reusable; this work benefits every future campaign)**
4. **Stand up the scaffolding repo** per §4.3. CI green, vanilla FE8 ROM builds clean from the decomp.
5. **Snapshot the SRD + Open5e** via `tools/pull-srd.ts`. Commit `data/srd-snapshot.json` + `data/open5e-snapshot.json`.
6. **Implement the combat-flavor layer** (`engine/combat-fx/`). Combat resolution stays vanilla FE — this is the cosmetic crit flourish + custom FE-native skill procs. Validate by playing vanilla FE8 chapter 1 with the layer on.
7. **Implement damage-type tagging** (`engine/damage-types/`). Tag every vanilla weapon with a flavor damage-type label (UI/icon only). Flag the few iconic matchups (fire vs ice troll, bludgeoning vs skeleton) via vanilla FE weapon effectiveness — no resistance multiplier.
8. **Implement the spell-tome economy** (`engine/spell-slots/`). Finite-use tomes that deplete and restock with gold between chapters (decision B) — no free refill.
9. **Implement the combat-preview reskin** (`engine/ui/`). Keep the vanilla Hit/Crit box; add a damage-type icon and the crit flourish.
10. **Write `tools/build-campaign.ts`** — the campaign-injector that reads a `campaigns/<name>/` folder and wires it into the decomp.

**Phase 2 — Content: Rime of the Frostmaiden (first campaign)**
11. **Translate one PC end-to-end** before scaling — find the rough edges in the mapper before doing the whole party.
12. **Build MVP chapter set** (3 chapters recommended). One YAML per chapter, one per PC, one per boss.
13. **Decide on map sourcing** — hand-drawn (Tiled) vs curated community pool. Recommend hand-drawn for 3 chapters, pool for stretch goals.
14. **Playtest, iterate, ship.** Distribute as a `.ups` patch.

**Phase 3 — Next campaign (future)**
15. `mkdir campaigns/curse-of-strahd/` and start filling YAMLs. Engine stays untouched.

---

## 10. References

**Fire Emblem hacking — tooling and decomp**
- [Fire Emblem GBA Decompilations — FE Universe (Eebit, 2024-09-13)](https://feuniverse.us/t/fire-emblem-gba-decompilations/27225)
- [FireEmblemUniverse/fireemblem8u (GitHub)](https://github.com/FireEmblemUniverse/fireemblem8u) — Sacred Stones decomp, near complete
- [FireEmblemUniverse/fireemblem6j (GitHub)](https://github.com/FireEmblemUniverse/fireemblem6j) — Binding Blade decomp, ~50%
- [StanHash/fe7_us (GitHub)](https://github.com/StanHash/fe7_us) — Blazing Blade disassembly (reference)
- [FE Decomp Portal (laqieer)](https://laqieer.github.io/fe-decomp-portal/) — index of all FE decomp projects
- [FEBuilder GBA (GitHub)](https://github.com/FEBuilderGBA/FEBuilderGBA) — the GUI editor
- [FEBuilder on RomHack Plaza](https://romhackplaza.org/utilities/febuildergba-utility/) — download + feature list
- [Stan's Event Assembler Package for Buildfiles (FEU)](https://feuniverse.us/t/stans-event-assembler-package-for-buildfiles/11201) — modern ColorzCore + lyn toolchain
- [Romhacking, Lex Talionis, Tactile, and SRPG Studio: engine comparison (FEU)](https://feuniverse.us/t/romhacking-lex-talionis-tactile-and-srpg-studio-an-engine-comparison-post-which-game-creation-engine-will-best-suit-your-needs/17559)
- [Contro's Buildfile Tutorial (FEU)](https://feuniverse.us/t/contros-buildfile-tutorial/14088)
- [C Setup for Dummies (FEU, Vesly)](https://feuniverse.us/t/c-setup-for-dummies/23830) — getting started with decomp + EA
- [The Ultimate Tutorial (feshrine.net)](https://www.feshrine.net/ultimatetutorial/) — long-form beginner walkthrough

**AI / Claude harnesses for ROM hacking**
- [alvarodms/agentoak (GitHub)](https://github.com/alvarodms/agentoak) — Claude × `pokeemerald` autonomous ROM-hack agent
- [FE Infinity — AI System That Builds Original ROM Hacks (FEU, neon)](https://feuniverse.us/t/fe8-fe-infinity-ai-system-that-builds-original-rom-hacks-prototype-demo/29090)
- [i-am-neon/fe-infinity (GitHub)](https://github.com/i-am-neon/fe-infinity) — FE Infinity source
- [Claude Code documentation](https://code.claude.com/docs/en/overview)

**D&D 5e API**
- [D&D 5e SRD API home (5e-bits.github.io/docs)](https://5e-bits.github.io/docs/)
- [API: Classes index](https://www.dnd5eapi.co/api/2014/classes) — 12 classes
- [API: Races index](https://www.dnd5eapi.co/api/2014/races) — 9 races
- [API: Spells index](https://www.dnd5eapi.co/api/2014/spells) — 319 spells
- [API: Fighter (sample class)](https://www.dnd5eapi.co/api/2014/classes/fighter)
- [API: Fireball (sample spell)](https://www.dnd5eapi.co/api/2014/spells/fireball)
- [API: Goblin (sample monster)](https://www.dnd5eapi.co/api/2014/monsters/goblin)
- [API: Longsword (sample equipment)](https://www.dnd5eapi.co/api/2014/equipment/longsword)
- [API: Elf (sample race)](https://www.dnd5eapi.co/api/2014/races/elf)
- [5e-bits/5e-srd-api (GitHub)](https://github.com/5e-bits/5e-srd-api) — API source / self-host option
- [Open5e — root](https://open5e.com/) — community-maintained 5e content site
- [Open5e API v1 root (`api.open5e.com/v1/`)](https://api.open5e.com/v1/) — legacy but still works; class data here
- [Open5e API v2 root (`api.open5e.com/v2/`)](https://api.open5e.com/v2/) — current; broader monsters/spells/items
- [Open5e API documents endpoint](https://api.open5e.com/v1/documents/) — enumerates the 17 source documents (Tome of Beasts, Deep Magic, Black Flag SRD, Tal'Dorei, etc.)
- [Open5e API Docs](https://open5e.com/api-docs) — usage and query params
- [open5e/open5e-api (GitHub)](https://github.com/open5e/open5e-api) — API source / self-host option
- [SRD 5.2 on D&D Beyond](https://www.dndbeyond.com/srd) — official 2024 SRD under CC-BY-4.0
- [Tribality — SRD v5.2 overview](https://www.tribality.com/2025/04/23/dd-system-reference-document-v5-2/) — explains what 5.2 added and what's still excluded (Artificer, Aasimar, Beholder, …)

**Baldur's Gate 3 — dice mechanics**
- [bg3.wiki — Dice rolls](https://bg3.wiki/wiki/Dice_rolls)
- [bg3.wiki — D&D 5e rule changes in BG3](https://bg3.wiki/wiki/D&D_5e_rule_changes)
- [Gamerant — BG3 Complete Dice Rolls Guide](https://gamerant.com/baldurs-gate-3-bg3-dice-rolls-critical-success-karmic-guide/)
- [Dot Esports — BG3 dice roll system explained](https://dotesports.com/baldurs-gate/news/baldurs-gate-3-dice-roll-system-explained)
- [RPGBOT — BG3 for 5e players: what's different?](https://rpgbot.net/video-games/baldurs-gate-3/for-5e-players-whats-different/)
- [CBR — 10 D&D rules changed in BG3](https://www.cbr.com/bg3-dnd-5e-rules-changes/)

**Fire Emblem combat / class reference**
- [Fire Emblem Wiki — Battle Formulas](https://fireemblem.fandom.com/wiki/Battle_Formulas)
- [Triangle Attack — FE7 combat calculations](https://fe7.triangleattack.com/guides/calculations)
- [Fire Emblem Wiki — Weapon triangle](https://fireemblemwiki.org/wiki/Weapon_triangle)
- [Fire Emblem Wiki — Trinity of Magic (Anima/Light/Dark)](https://fireemblem.fandom.com/wiki/Trinity_of_Magic)
- [Serenes Forest — Sacred Stones calculations](https://serenesforest.net/the-sacred-stones/miscellaneous/calculations/)
- [Triangle Attack — FE8 classes](https://fe8.triangleattack.com/classes)
- [Serenes Forest — Sacred Stones promotion gains](https://serenesforest.net/the-sacred-stones/classes/promotion-gains/)
