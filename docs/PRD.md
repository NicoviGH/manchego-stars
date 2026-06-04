# Manchego Stars — Product Requirements Document

> **Version:** 2.0 — 2026-06-04 (pruned to vision + durable design; tooling/architecture specifics now live in `decisions.md` and the repo)
> **Author:** Nicolas (via Claude)
> **Status:** Living
>
> **Scope of this doc:** the *why* and *what* — problem, goals, audience, design direction,
> success criteria, open questions. It is **not** the source of truth for tools, file
> layout, class/chapter tables, or settled mechanics — those live where the data lives:
> - Settled decisions & tech stack → `docs/decisions.md`
> - Per-chapter facts → chapter YAML → `docs/CHAPTERS.md` · Unit facts → unit YAML → `docs/CLASSES.md`
> - Backlog → GitHub issues (M0–M4) · Current state → `HANDOFF.md` · Repo layout → the repo itself
> Do not restate those here (see `decisions.md` → Working Conventions).

---

## 1. Problem Statement

Nicolas ran a multi-year D&D 5e campaign (*Rime of the Frostmaiden*) with 6 friends. The campaign is over, but the shared memories — a hermit crab barbarian smashing shackles, a mushroom druid talking down a plesiosaur, a ratfolk artificer executing a kobold at gunpoint — deserve more than a group chat. The group has no way to *replay* their story.

**This project turns that campaign into a playable GBA tactics game**, built as a ROM hack of *Fire Emblem: The Sacred Stones* (FE8). The PCs become playable units; the DM's narrative beats become chapters. Combat uses **vanilla FE8's tactics rules** (hit/avoid/might/crit) so the game plays like Fire Emblem; the D&D campaign supplies the characters, their classes, spells-as-tomes, and flavor on top. The result is a `.gba` file the group can play on any emulator or flash cart — their adventure, in their pocket.

**Who is affected:** the players from the Icewind Dale campaign (private distribution only).

**Impact of not solving it:** nothing breaks — this is a passion project. But the window closes as life moves on. Building it now, while the memories are fresh and the tools are good enough, is the moment.

---

## 2. Goals

1. **Ship a playable `.gba` ROM** covering the DM-notes arc (Prologue + 8 chapters, from the goblin iron quest through the Eastway ambush / Revel's End cliffhanger) that runs on stock GBA emulators and flash carts.
2. **Keep Fire Emblem's combat, dress it in D&D.** Preserve FE's grid tactics, hit/avoid/might resolution, permadeath toggle, weapon triangle, growth-rate leveling, and FE crit. Layer D&D *flavor* on top: damage-type labels (no resistance multiplier — the triangle stays FE-native), spells as finite-use tomes that deplete and restock with gold, and a cosmetic d20 flourish on crits. Iconic matchups reuse vanilla FE weapon effectiveness, keyed to enemy class. The rules stay FE so it plays like FE. *(Settled mechanics: `decisions.md` §Combat / §Weapon & Magic / §Economy.)*
3. **Faithfully represent the cast** as playable units with correct classes, stats, progression, and personality — custom portraits, map sprites, battle anims, dialogue, and signature moments.
4. **Build the engine as reusable.** Campaign-specific data lives in `campaigns/`; engine C stays campaign-agnostic. A second campaign should need only a new `campaigns/` folder. *(See `decisions.md` Engine & Tech Stack.)*
5. **Keep the project tractable** — session-driven Claude Code workflow, one feature per session, `make` green at the end of every session.

---

## 3. Non-Goals

1. **Public release or distribution.** This is for the group. No patch hosting, no listings. The ROM is sent directly as a pre-patched file.
2. **Full campaign coverage beyond the DM notes.** The MVP ends at the Revel's End cliffhanger (Ch 8). Don't spec what doesn't exist yet (post-MVP scaffold lives in `docs/roadmap.md`).
3. **Custom engine** (Lex Talionis, SRPG Studio). The deliverable is a `.gba` built from the FE8 decomp. Period.
4. **A generic D&D-campaign editor or DSL.** The engine is *organized* for reuse, but we don't build editor tooling or a GUI campaign builder. Build exactly what Frostmaiden needs, structured so a second campaign is easy.
5. **Original music / custom GBA audio** for MVP. Ship with the vanilla FE8 soundtrack; custom audio is a post-ship stretch.
6. **Fully AI-generated maps.** LLMs produce bad tactical maps. Maps are hand-drawn using community Frostmaiden maps as layout references; the agent helps with everything *around* maps (unit placement, events, dialogue), not spatial layout.

---

## 4. Target Users

**Primary (and only) audience:** the players from the Icewind Dale campaign.
- They know D&D 5e intimately and care about *their* characters and *their* story moments above all — campaign-specific callbacks are the whole point; generic FE content is filler.
- They'll play on emulators (mGBA, RetroArch) or GBA flash carts.

**Secondary:** Nicolas (DM / developer) — needs a debuggable toolchain and a reliable, cost-efficient build.

---

## 5. Player User Stories

- **Select my PC** from the roster and see their portrait, stats, and class so I recognize my character immediately.
- **A brief d20 flourish on a critical hit** so crits feel like a nat-20 — without changing how combat resolves (it stays FE hit/avoid).
- **Gear reads like D&D** via flavored names + art (Rootis's ice tome, Braulo's anchor-axe) while stats and the triangle stay FE-native — no damage-type mechanic or label.
- **Spell tomes that deplete and restock with gold** between chapters so casters share the martials' resource economy.
- **Recruit NPC allies** (Trex, Basil, the Mummy, …) as the story progresses so the roster grows like a real FE game.
- **Casual or Classic mode** (FE8's toggle) so permadeath is my choice.
- **Campaign-specific dialogue and story beats** (the kobold execution, Messie becoming Speaker, Braulo smashing shackles) so it feels like *our* campaign.
- **Discover Marty can Talk to Messie in Ch 6** — rewarded for paying attention to the story, not a tutorial prompt.
- **Ch 8 ends in a scripted defeat** so the Revel's End cliffhanger lands hard.

---

## 6. Architecture (summary — details in `decisions.md` + the repo)

A patched FE8 ROM built from the `fireemblem8u` C decompilation. Campaign content is **injected at build time** into the decomp's own source by `tools/build_campaign.py` (portraits → `graphics/portrait/`, names/dialogue → `texts/texts.txt`, class/stats → `src/data_characters.c`, chapters → `src/events/`), then `make` compiles `fireemblem8.gba`. Reusable engine C lives in `engine/`. This is the decomp-native path — no Event Assembler, no custom engine. *(Tooling, language, and injection approach: `decisions.md` Engine & Tech Stack. The repo tree is the structure of record — don't duplicate it here.)*

**The boundary rule (durable):** if a feature references a character name, chapter number, or plot event, it lives in `campaigns/` YAML, not engine C. Any C change that hardcodes a Frostmaiden assumption is rejected in review. `build_campaign.py` enforces the split by being the only thing that writes campaign data into the decomp.

**Combat / triangle / spells / economy:** settled in `decisions.md` (§Combat System, §Weapon & Magic Systems, §Economy) with the generic 5e→FE conversion in `rules-mapping.md`. In brief: rules are vanilla FE8 (`bmbattle.c` untouched); damage-type names are cosmetic labels; the triangle stays FE-native; the d20 is a cosmetic crit flourish; spell tomes deplete and restock with gold.

---

## 7. Art Direction

The player cast + named recruits get **fully custom** indexed-palette art for **every** sprite part — portrait, map sprite, AND battle animation. Not recolored vanilla, not reused class anims. Since combat is pure vanilla FE8, the art is the biggest lever for campaign feel. Each piece is produced **faithfully from the character's clean Gemini/Nano-Banana bust reference** via tooling (`tools/ref_to_bust.py` → `tools/portrait_tool.py`) — converted, not hand-pixeled. Delivered in three waves: (1) portraits [done], (2) map sprites [#38], (3) battle animations [#39]. Per-character briefs live in each unit's YAML `art:` block; render → show Nicolas → wait for OK → commit.

- **Enemy sprites/portraits:** vanilla FE8 where the look fits; community/custom only for creatures with no vanilla analogue (Grells, Messie, ice trolls) and key NPCs (Duvessa Shane, Trex, Messie, Dorbulgruf).
- **Map tiles:** vanilla FE8 snow/ice + community arctic tilesets; community Frostmaiden maps as *layout reference* for hand-drawn FE maps. Custom interiors likely needed for the mine, tomb, water/boat, and town maps.
- **Cutscene art:** MVP is portrait-based dialogue only; CG illustrations for marquee moments are a post-ship stretch.

---

## 8. Audio Direction

- **MVP:** vanilla FE8 (Sacred Stones) soundtrack — moody/atmospheric, fits an arctic adventure.
- **Stretch (post-ship):** investigate the Frostmaiden album + community soundtrack compilations for GBA conversion (boss themes, Messie's water encounter, the Eastway ambush, location ambience). GBA audio is constrained (~8 channels, specific sample rates); conversion is non-trivial.

---

## 9. Leveling & Progression

- **Start:** the cast begins at low FE levels (≈ D&D level 1–3); they met at The Northlook together — no staggered PC recruitment.
- **Flavor reference, not targets:** the D&D Beyond sheets (level ~20) tell us relative strengths (tank vs glass cannon), not literal numbers. FE stats are authored in FE terms (caps ~30), not converted from 5e.
- **MVP scope (Prologue + 8 chapters):** plays entirely **unpromoted**; promotions are post-MVP. Cast should reach ≈ FE level 10–12 by Ch 8.
- **Growths** are authored in FE terms toward a strong, class-appropriate endgame line. *(Current injection sets pure-class growths as a neutral baseline; per-unit growth tuning is a tracked follow-up — see `decisions.md`/`HANDOFF.md`.)*
- **Sclorbo exception:** his player left at D&D level 16 — slightly lower endgame caps, no in-story explanation (a balance lever).
- **NPC recruits** join at lower levels than PCs.

---

## 10. Technical Risks & Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| **HP scale mismatch** — 5e spells assume 50–200 HP; FE units have 20–60 | High | Keep FE's `damage − DEF` model; don't import 5e damage values. Scale through FE-magnitude weapon dice. Playtest early. |
| **GBA UI real estate** — combat preview is tiny | Low | Forecast box stays vanilla FE — no added icons. The cosmetic d20 flourish reuses crit animation frames, not the forecast box. |
| **Save-file size** — spell-tome charges per unit pressure FE8's per-character budget | Low | No AC/resistance stored (combat is vanilla FE). Tome charges are the main add; sidecar table if needed. Audit in engine phase. |
| **agbcc limits** (GCC 2.95.1, no C99) | Low | Follow decomp code style — no VLAs, no designated initializers. |
| **Map design quality** — LLMs are bad at FE maps | Low | Community Frostmaiden maps as references; hand-draw FE versions. Agent does placement/events/dialogue, never spatial layout. |
| **Engine/content boundary erosion** | Medium | `build_campaign.py` enforces the contract; review rejects any C that references a character/chapter/plot event. |
| **Plan/reality drift** | Medium | Single source of truth + Definition of Done (`decisions.md` → Working Conventions): docs/issues updated in the same change; decisions recorded when made. |

---

## 11. Success Metrics

Qualitative (audience of a handful, no analytics):
1. **"It boots and plays"** — loads on mGBA and a real flash cart; all chapters completable; no hard crashes.
2. **"That's my character!"** — each player recognizes their PC from portrait/stats/abilities within seconds.
3. **"Plays like Fire Emblem, reads like D&D"** — FE's hit/avoid forecast, with D&D-flavored characters/classes/names/art + a crit flourish making it read as *our* campaign.
4. **"I remember this"** — ≥3 campaign-specific moments per chapter that land.
5. **"I want to keep playing"** — the Ch 8 cliffhanger makes players ask for the next batch.
6. **Build health** — `make` green at the end of every session.

---

## 12. Open Questions

> Need answers before/during implementation. (Canonical list; `decisions.md` Open Questions points here.)

| # | Question | Owner | Notes |
|---|---|---|---|
| 1 | **Signature moments for Marty, Meesmickle, Rootis, Sclorbo** | Nicolas | Drive unique dialogue triggers / ability names. |
| 2 | **Velynne Harpell's role** later in the published adventure | Nicolas + book | Appears in Ch 1 asking about a stolen orb. |
| 3 | **Homebrew setting overlays** — did the DM change Icewind Dale? | Nicolas | Default: standard Realms, non-standard party. |
| 4 | **Messie's Bremen function** after Ch 6 (shop? services? quests?) | Design | Recommend: a "harbor shop" of water-themed items. |
| 5 | **Permadeath flavor** in Casual mode for an arctic party | Design | Recommend: "retreated to the sled." |
| 6 | **Total chapter count** beyond the MVP | Nicolas | Needs a future writing session. |
| 7 | **Cutscene art** — portrait-only (MVP) or CG for key moments | Nicolas | Recommend: MVP portrait-only; CG post-ship. |
| 8 | **Sephek Kaltro** — role beyond the Prologue (recurring? tie to Ch 5 frost druids?) | Nicolas | Published Ch 1 villain; now the Prologue boss. |
| 9 | **Cast-data follow-ups** — weapon-rank levels, gender/`attributes`/supports, brie/pepperjack classes | Nicolas + eng | Deferred from character injection; see `HANDOFF.md`. |

---

## 13. Roadmap — Phased Milestones

Tracked as GitHub issues (milestones **M0–M4**); the live backlog is the issue tracker, not this doc.

- **M0 — Repo Boots Clean:** scaffold + decomp builds clean + toolchain verified. *(done)*
- **M1 — D&D Combat Layer Works:** the D&D flavor layer on vanilla FE combat — damage-type labels, weapon-effectiveness matchups, spell-tome economy, combat-preview icon, cosmetic d20 crit flourish. *(not started)*
- **M2 — One PC End-to-End:** the injector + Braulo fully translated (portrait + name + class/stats + verify). *(done — the pipeline now covers all 10 cast)*
- **M3 — 8 Chapters Playable:** all cast, NPCs, enemies, 8 chapters, maps, dialogue, events; map sprites; world map. *(in progress)*
- **M4 — Ship It:** playtest, balance, final art/dialogue, battle anims, title/credits, distribute.

## 14. Story Beat Refinement

DM notes capture *what happened*; the FE adaptation decides *how to pace it* (mid-map cutscenes, player vs scripted segments, tension vs breather). Chapter designs are revisited at the start of each chapter's implementation session, collaboratively (FE8 parallel + our version), not dumped solo. Expect them to evolve. DM notes cover Ch 1–7 only — don't invent Ch 8+ from the published book.

## 15. Definition of Done (MVP product)

The MVP is **done** when:
1. `make CAMPAIGN=rime-of-the-frostmaiden` produces a `.gba` that boots on mGBA without crashes.
2. The full cast is selectable with correct portraits, stats, classes, inventories.
3. All recruit NPCs are recruitable at their chapters.
4. All 8 chapters are playable start-to-finish with correct objectives, enemies, dialogue, events.
5. Combat plays as vanilla FE, reskinned with D&D-flavored names/art + a cosmetic d20 crit flourish (no damage-type mechanic).
6. Damage-type labels display; vanilla FE weapon effectiveness works for iconic matchups (armorslayer vs knights, monster-effective vs skeletons/ice trolls).
7. Spell-tome charges deplete and restock correctly.
8. Ch 6 (Messie) is resolvable via Talk.
9. Ch 8 ends in a scripted defeat with the Revel's End cliffhanger text.
10. Casual/Classic toggle works.
11. Playtested end-to-end at least twice (bugs, then balance).
12. Successfully loaded by at least one other player.

> Per-change Definition of Done (the engineering workflow contract) is in `decisions.md` → Working Conventions. Agent workflow (session pattern, model selection, build/verify commands) is in `CLAUDE.md`.

---

## Appendix A: Reference Links

**Fire Emblem hacking**
- [fireemblem8u decomp](https://github.com/FireEmblemUniverse/fireemblem8u) · [FEBuilder GBA](https://github.com/FEBuilderGBA/FEBuilderGBA) · [FE Decomp Portal](https://laqieer.github.io/fe-decomp-portal/)
- [Make a hack directly from the fireemblem8u decomp (FEU)](https://feuniverse.us/t/make-hack-directly-from-fireemblem8u-decomp-source-code/17428) — our approach
- [C Setup for Dummies (FEU)](https://feuniverse.us/t/c-setup-for-dummies/23830)

**AI harnesses**
- [Agent Oak — Claude × pokeemerald](https://github.com/alvarodms/agentoak)
- [FE Infinity — LLM × FE8 (FEU)](https://feuniverse.us/t/fe8-fe-infinity-ai-system-that-builds-original-rom-hacks-prototype-demo/29090)

**FE combat reference**
- [Serenes Forest — Sacred Stones calculations](https://serenesforest.net/the-sacred-stones/miscellaneous/calculations/) · [FE Wiki — Battle Formulas](https://fireemblem.fandom.com/wiki/Battle_Formulas)

**D&D source:** PC sheets are authored from the players' D&D Beyond exports in `data/pc-sheets/` (flavor only; FE stats are authored in FE terms). No SRD/API pull.
