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

**Tooling language: Python (build) + Ruby (index gen). NOT TypeScript.**
The original plan named a Node/TypeScript toolchain (`build-campaign.ts`, `build-events.ts`, `pull-srd.ts`, `map-class.ts`). Reality: the injector is `tools/build_campaign.py`, with `tools/portrait_tool.py`, `tools/ref_to_bust.py`, `tools/verify_text.py`, and the chapter index generator `tools/gen-chapter-index.rb`. No Node, no `.ts`. The build interpreter is Homebrew `python@3.12` (numpy/pillow/pyyaml; see `tools/setup-toolchain.sh`).
_Decided: 2026-06-04 (supersedes the PRD's TS toolchain plan)_

**Content injection is decomp-native — edit the decomp's own source, NOT Event Assembler.**
`build_campaign.py` writes our content directly into the `fireemblem8u` working tree at build time — `graphics/portrait/` (busts), `texts/texts.txt` (names/dialogue), `src/data_characters.c` (class/stats), and `src/events/<ch>-event*.h` (chapters) — then `make` compiles it. No Event Assembler / ColorzCore / `.ea` buildfiles. This is the "make a hack directly from the fireemblem8u decomp" path (FEU thread 17428). Generated files are reproducible artifacts: restore vanilla with `git -C fireemblem8u checkout <path>`.
_Decided: 2026-06-04 (supersedes the PRD's Event Assembler plan; retires the `tools/build-events.ts` idea)_

**No SRD/Open5e pull.** PC data is authored from the players' D&D Beyond JSON (`data/pc-sheets/`); D&D is flavor-only over vanilla FE combat (see FE-strictness below). No SRD downloader, no `srd-snapshot.json`, no homebrew engine classes — the cast use stock FE8 classes (see Class Mapping).
_Decided: 2026-06-04_

**Text injection has a terminator-parity gotcha (the reset's "Huffman corruption").**
FE8 packs text two bytes per u16; `[X]` = the 0x00 string terminator. An odd number of name bytes pairs the 0x00 into the last glyph, so the decoder runs away. Vanilla pads odd names with `[.]` (`Franz[.][X]` vs `Seth[X]`); `build_campaign.py` does the same. Always confirm text with `tools/verify_text.py` (decodes messages straight from the built ROM — no mGBA), not by eye.
_Decided: 2026-06-04_

---

## Documentation Model

**Three tiers; a per-chapter fact lives in exactly one place (the YAML)**
The doc set kept duplicating per-chapter facts across the YAML, `PRD.md §7`, a hand
table, and the pacing ref — so every story change forced a multi-file resync. The
settled model:
- **Tier 1 — Source of truth = the chapter YAML.** `campaigns/rime-of-the-frostmaiden/chapters/ch*.yaml`
  is authoritative for every per-chapter fact (objective, recruits, enemies, map,
  rewards, `unlocks_chapter`). Edit the YAML; nothing else.
- **Tier 2 — Generated index.** `docs/CHAPTERS.md` is **generated** from the YAML by
  `tools/gen-chapter-index.rb` (ruby, stdlib only). It is never hand-edited;
  regenerate after any chapter change. "The data is the doc."
- **Tier 3 — Durable "why" docs, hand-written.** `decisions.md` (settled decisions),
  `roadmap.md` (provisional post-MVP Act II–V scaffold — chapters with no YAML yet),
  `fe8-pacing-reference.md` (FE8-only cadence/reward rules), `PRD.md`
  (vision/scope/architecture/roadmap pointers). These hold rationale and
  forward-looking planning, **not** per-chapter tables.
Rule: do not re-introduce a chapter breakdown table into `PRD.md` or any hand doc —
point to `CHAPTERS.md` / the YAML instead.
_Decided: 2026-05-31 (retires the hand-maintained `chapter-outline.md`)_

**Chapter cadence taxonomy (the `cadence:` field)**
Each chapter YAML carries a `cadence:` token; the generator maps it to one of four
FE8 pacing emoji for `CHAPTERS.md`: 🟥 big-battle/boss · 🟦 breather/intro/escort/travel ·
🟨 sidequest/gimmick · 🎬 scripted set-piece. Current tokens: `tutorial`,
`full_party_intro`, `breather_defend` (🟦); `gimmick_multilevel`, `monster_debut`
(🟨); `first_boss`, `big_battle_gray` (🟥); `marquee_setpiece`, `scripted_defeat`
(🎬). Add a new token to `CADENCE` in `tools/gen-chapter-index.rb` when a new pacing
beat appears. The cadence *rules* (why this rhythm) live in `fe8-pacing-reference.md`.
_Decided: 2026-05-31_

---

## Working Conventions (Definition of Done)

**Why this section exists:** the project drifted because the plan was written up front,
then implementation pivoted (Python not TS, decomp-native not Event Assembler, stock
classes not homebrew) and the canonical docs/issues were never reconciled. The same
fact lived in CLAUDE.md, PRD.md, README, rules-mapping, decisions.md, and GitHub, so
no update ever propagated. These conventions keep a single source of truth.

**Single source of truth — link, don't restate.** Each fact lives in exactly one place:
- *Settled decisions & rationale* → this file (`decisions.md`).
- *Per-chapter facts* → chapter YAML → generated `CHAPTERS.md`. *Unit facts* → unit YAML → `CLASSES.md`.
- *Work backlog* → GitHub issues (milestones M0–M4).
- *Current session state* → `HANDOFF.md`. *Vision/pitch* → `PRD.md` (no specifics that live elsewhere).
- `CLAUDE.md` is lean **operating instructions + pointers**, not a fact store (a bloated CLAUDE.md gets ignored). If a fact belongs in two docs, one of them should link instead.

**Record decisions when made.** Any change that alters architecture, scope, tooling, or a
settled rule gets a dated entry here in the same session — ADR-style, while context is
fresh. Don't leave it in chat or agent memory only.

**Definition of Done for a change:**
1. Code/data change ships with its doc + YAML updates **in the same commit** (no "update docs later").
2. If it completes tracked work, the commit/PR says `Closes #N`; if it changes scope, open/retitle the issue.
3. `make` builds green; `tools/verify_text.py` is clean after any text change.
4. New non-obvious decision → an entry in this file.
5. Don't commit the `fireemblem8u` submodule pointer (our decomp edits are build artifacts).

**Commits:** imperative subject; reference issues (`Closes #N` / `Refs #N`). Co-author trailer per repo norm.
_Decided: 2026-06-04_

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
the weapon triangle only.
_Decided: 2026-05-28_

**Damage: vanilla FE armor-subtraction model (nothing layered under it)**
`Damage = Might − Defender.DEF/RES`, where Might = the FE weapon/tome's Might + the unit's STR
(physical) or MAG (magic) — all FE-native. Weapons are FE items; their Might comes from the FE
weapon tier (Iron/Steel/Silver…), **not** from a 5e die or any conversion. No weapon dice, no
ability modifier, no D&D multiplier (see the damage-type decision below). Do NOT import 5e HP/damage
values — FE stats and growth tables (HP caps ~60–80) are authored directly.
_Decided: 2026-05-28; sharpened 2026-05-29 (FE stats/Might only — no 5e die-to-might conversion)_

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
- **Iconic matchups use vanilla FE weapon effectiveness, keyed to the target's CLASS.**
  FE8's effectiveness system has eight class-keyed categories (`src/data_items.c`
  `ItemEffectiveness_*`): Armor, ArmorAndHorse, Horse, Flier, FlierAndMonsters, Monsters,
  Dragon, Swordsman. Effectiveness is a property of a weapon against an enemy class —
  Hammer/Armorslayer vs armored Knights, Wyrmslayer vs dragons, bows vs fliers, and the
  monster-effective weapons (the Sacred Twins + Audhulma/Shadowkiller/Fiendcleaver/Brightlance/
  Beacon Bow) vs monster-class enemies (skeletons, gargoyles, ice trolls/cyclops, …). Damage
  types stay flavor labels; effectiveness keys off class alone. Use sparingly — most weapons
  carry no effectiveness at all.
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

**Weapon triangle: vanilla FE (Sword > Axe > Lance); damage-type names are flavor**
The triangle is FE-native and driven by weapon TYPE (`src/bmbattle.c sWeaponTriangleRules`):
Sword > Axe > Lance > Sword, +1 ATK / +15 hit. D&D damage-type names (slashing,
bludgeoning, piercing, …) are **cosmetic per-weapon labels** shown in the item info — NOT
a relabeling of the triangle. A "claw" wolf and an axe bandit are both the **axe type** and
read identically on the triangle; the difference is sprite + label only.
_Decided: 2026-05-29 (supersedes the May 2026 "reskin the triangle to Slashing/Bludgeoning/Piercing," which conflicted with FE weapon types)_

**Magic triangle: vanilla FE (Anima > Light > Dark)**
FE-native: Anima > Light > Dark > Anima, +1 ATK / +15 hit (`sWeaponTriangleRules`). Caster
spread after the 2026-05-30 promotion fix: Rootis = Anima; Marty & Meesmickle = Dark (both
Shaman, differentiated at promotion — Marty→Druid, Meesmickle→Summoner); Light is covered by
Sclorbo (Priest→Bishop, attack tomes at promotion). Note: reclassing Marty off Light (to honor
his D&D Druid identity → FE Druid) means two Dark casters rather than one-each across the triangle.
_Decided: 2026-05-29; caster spread updated 2026-05-30_

**13 damage-type labels (flavor only — no resistance mechanic)**
Types: slashing, piercing, bludgeoning, fire, cold, lightning, thunder, poison, acid, necrotic, radiant, force, psychic. These are **flavor tags** on weapons/tomes for descriptions + UI. **No per-class resistance bitmap, no ×0.5/×2/×0 multiplier** (reverted 2026-05-28 — see Combat System §). Iconic matchups use vanilla FE weapon **effectiveness**, keyed to enemy class (armor/cavalry/flier/dragon/monster/sword) — see the Combat System § rule.
_Decided: 2026-05-28 (supersedes the May 2026 resistance-bitmap decision)_

**Spell economy: finite-use tomes that deplete and are restocked with gold (decision B)**
Every spell is a finite-use item with FE tome/staff durability. Charges DEPLETE in use and
are **restocked with gold between chapters at a shop** — there is no free per-chapter refill.
Cantrips are high-count items (30–50 uses) rather than truly infinite. This puts casters in
the same gold/durability economy as martial weapons, preserving FE's core resource-management
layer (the whole party shops, scavenges, rations). Flavor the restock per character (forage /
scribe / pray); mechanically these are vanilla FE tomes/staves.
_Decided: 2026-05-29 (supersedes the May 2026 "free chapter-refill, cantrips infinite, slots not buyable")_

**MVP weapons = stock FE weapons (no custom Might); personal weapons are post-MVP**
PCs carry plain vanilla FE weapons whose stats (Mt/Hit/Crit/Wt/uses) come verbatim from a stock
FE8 item, named in each inventory entry's `fe_base` field — there is **no custom Might authoring**.
Conventions:
- **Physical weapons use stock names** (Iron Axe, Hand Axe, Iron Bow, Iron Lance, Javelin, Heal).
  Visual identity rides on the **sprite/portrait art** (an Iron Axe can be drawn as an anchor).
- **Tomes keep an element-right flavor NAME but are mechanically the basic stock tome** (name-only
  reskin, stock stats): Rootis "Ray of Frost" = `Fire`; Marty "Shillelagh" / Meesmickle "Eldritch
  Blast" = `Flux`; Sclorbo "Frostsong"/"Withering Impression" = `Lightning`. This avoids a stock
  tome name (e.g. "Fire") clashing with an ice/fungal caster's element.
- **Personal/signature weapons return post-MVP** as story progression, each mapped to an FE
  equivalent (e.g. Braulo's "Nu' Shipwrecker" → Killer Axe). Their flavor names are parked in
  `lore/<pc>.md` ("Signature gear").
This resolves the old "weapon Might TBD" / "uses: null TBD" placeholders.
_Decided: 2026-05-30_

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

**MVP scope: 8 chapters (Prologue–Ch 8), ending at the Eastway scripted defeat → Revel's End cliffhanger**
The MVP runs **Prologue + Ch 1–8** (see `docs/CHAPTERS.md`). The finale, **Ch 8 (The
Eastway Ambush)**, ends in a scripted defeat — "You wake up on the road to Revel's
End…" → credits. Revel's End itself is the post-MVP **Ch 9** (`docs/roadmap.md`).
Chapters beyond the DM notes require a future writing session.
_Decided: May 2026; recount to 8 on 2026-05-31 after the old Ch 4 was split into Ch 4 (White Moose) + Ch 5 (Elven Tomb)_

---

## Art & Audio

**Maps: hand-drawn in Tiled, NOT AI-generated**
Use community Frostmaiden maps (from `docs/frostmaiden-resources.md`) as layout references. Use FEUniverse map pool for tileset/format guidance. Agents help with unit placement and events, never spatial layout.
_Decided: May 2026_

**Audio: vanilla FE8 soundtrack for MVP**
Investigate Frostmaiden Spotify album + community soundtracks as stretch-goal custom tracks post-ship.
_Decided: May 2026_

**Art: CUSTOM indexed-palette pixel art for every PC/recruit sprite part — portrait, map sprite, AND battle animation.**
Not recolored vanilla, and not reused vanilla class animations. Combat is pure vanilla FE8, so the art is the
single biggest lever for making the game feel like the actual D&D campaign — worth doing custom and taking the time.
Each piece is produced **faithfully from the character's clean Gemini/Nano-Banana bust reference** via tooling
(`tools/ref_to_bust.py` → `tools/portrait_tool.py`): the generative bust is the **pre-approved source art** and is
converted — not hand-pixeled (Nicolas is not a pixel artist) — into the final 16-color indexed asset. Nicolas supplies
one clean frameless **"<Name> Face Clean"** bust per character; Claude converts it. Specs: 16-color GBA palette, 8×8 tiles.
Per-unit design briefs (must-keep tells, expression, palette plan) live in each unit's YAML `art:` block
(`campaigns/.../{pcs,npcs}/*.yaml`).
**Sequencing — three waves:** (1) all 10 cast portraits, then (2) all map sprites (16×16 chibis), then (3) battle animations.
_Decided: May 2026; full-custom direction + Gemini-ref-to-asset pipeline proven 2026-06-01 (Braulo, then Prof. R.B. Geenius)._

**Enemy/non-cast sprites: vanilla FE8 where the look fits; community (FEUniverse) or custom only where a creature has no vanilla analogue** (Grells, Messie, ice trolls).
The full-custom rule above is for the player cast + named recruits, where identity matters most.
_Decided: May 2026_

**Cutscene art: portrait-based dialogue only for MVP**
CG-style illustrations (Braulo shackle break, Messie rising, Revel's End fade) are post-ship stretch goals.
_Decided: May 2026_

---

## Class Mapping & Promotions

All 7 PCs (and recruits) are **stock vanilla FE8 classes** — bases, growths, caps, MOV, CON, and
weapon ranks taken verbatim from `fireemblem8u/src/data_classes.c`. **No custom classes, no
per-character abilities.** Individuality comes from flavor text, sprite/portrait art, and palette.

**This does NOT mean stripping vanilla FE8 *class features*.** A stock class keeps its built-in
kit — Berserker crit, Bishop's bonus vs monsters, **Summoner's Summon command (CA_SUMMON)**,
Canto, flight, etc. We dropped the homebrew D&D ability layer, not FE mechanics.

**Base classes**
| PC | FE base | D&D source |
|---|---|---|
| Braulo | Pirate | Barbarian (Berserker) |
| Marty | Shaman | Druid (Circle of Spores) — FE8's Druid class is reachable only via Shaman |
| Meesmickle | Shaman | Warlock (The Fiend) |
| Prof. RBG | Archer | Artificer (Artillerist) |
| Rootis | Mage | Sorcerer (Draconic) |
| Sclorbo | Priest | Bard (College of Lore) |
| Wolfram | Knight (Armor Knight) | Metallurgist |

Marty & Meesmickle share the Shaman chassis but differentiate at **promotion**, not base.
_Decided: 2026-05-30 (supersedes the 2026-05-27 "Marty→Monk for sprite differentiation," which forced an illegal Monk→Summoner promotion)_

**Promotions are FE8's vanilla BRANCHED choice (the player picks at the Master Seal)**
Every promoting class has two vanilla options (`fireemblem8u/src/classchg-data.c`); each unit YAML
lists the `branch` + a thematic `default` (in **bold**):
- Braulo: Pirate → {Warrior, **Berserker**}
- Marty: Shaman → {**Druid**, Summoner} — Druid = his D&D class name; Summoner = the Summon command
- Meesmickle: Shaman → {Druid, **Summoner**}
- RBG: Archer → {**Sniper**, Ranger}
- Rootis: Mage → {**Sage**, Mage Knight}
- Sclorbo: Priest → {**Bishop**, Sage}
- Wolfram: Armor Knight → {**General**, Great Knight}
- Pinky (recruit): Pegasus Knight → {**Falcon Knight**, Wyvern Knight}
_Decided: 2026-05-30 (fixes the illegal Monk→Summoner and the non-existent "Dark Sage")_

**Sclorbo: stock Priest → Bishop (staff healer; attack tomes at promotion)**
A vanilla Priest — staff-only healer at base, Light attack from the Bishop promotion. He is the
MVP healer. The earlier "Lore Bishop" custom hybrid (Dancer chassis + retained Dance + per-turn
Dance-or-Cast lever + custom heal tiers) is gone: no Dancer, no Dance, no Rapier.
_Decided: 2026-05-29_

**Rootis: stock Mage → Sage / Mage Knight**
A plain anima caster (ice = flavor only). The earlier "Dragon Wings = Manakete-style class
transform" and "custom flier Sage" are gone with the ability strip — no transform, no dragon form,
no Sorcery Points. His draconic identity is sprite art + lore.
_Decided: 2026-05-29_

**Pepperjack & Brie are separate recruitable units, not RBG summons**
Two sentient automatons RBG builds; each joins the army as an ordinary FE8 recruit (`npcs/`), not a
deployable cannon/summon, and is a stock vanilla class (TBD post-MVP). Pokémon-style speech (each
only says its own name — "Pepperjack!" / "Brie!"); they're dating. Pinky (RBG's homunculus "son")
is a third recruit — the army's flier (Pegasus Knight). Combined portrait at
`data/portraits/pepperjack-and-brie.jpeg`. Full flavor in `lore/pepperjack-and-brie.md`, `lore/pinky.md`.
_Decided: 2026-05-29_

**FE stat column folds 5e stats to FE stats**
Class-mapping docs surface FE engine stats (STR/DEX/MAG/etc.) instead of 5e stats (WIS/INT/CHA). All magic-stat 5e classes (WIS Druid, INT Artificer, CHA Warlock/Sorcerer/Bard) use MAG in engine. Flavor distinctions stay in YAML metadata, not class mapping.
_Decided: 2026-05-27_

**Wolfram & RBG are NOT casters**
Both are stock physical classes with **no spell access**: Wolfram is a Lance Knight (STR), RBG a
Bow Archer (SKL/DEX). The earlier "hybrid caster" overlay (secondary MAG, finite-use cantrip
tomes) is gone. Their fire/forge and firearm/gadget flavor is sprite art + lore only.
_Decided: 2026-05-29_

**The promotion seam (Ch 8 → 9): foreshadow in the MVP, pay off at Revel's End**
The MVP plays entirely **unpromoted** (5e levels 1–5); promotions are post-MVP. The seam:
- **Foreshadow in MVP.** The **Ch 5 (Elven Tomb)** frost-druid boss **Ravisin** drops a
  *flavored, locked relic* — the **crest of cold iron** ("it hums, but none of you know how
  to use it yet"). It sits in the convoy, unusable, as a Chekhov's gun for promotion.
- **Pay off at the seam.** The **first Master-Seal-equivalent** is obtained in/after the
  Revel's End break (**Ch 9**, post-MVP) — diegetically looted from the prison or earned in
  the escape. This matches FE8 holding promotions until the route-split era
  (`fe8-pacing-reference.md §3`).
- **Promotions go live ~Ch 10–12** (see memory `manchego-stars-campaign-structure`); PCs reach
  5e ~L11 / first FE promotion there. Specific crests (Knight Crest, Guiding Ring) may
  *flavor-appear* for an early single promotion, but the **Master Seal is the universal
  mechanism** (avoids class-matching headaches across 7 PCs).
_Decided: May 2026; renumbered to Ch 8→9 on 2026-05-31 after the Ch 4 split (was Ch 7→8)_

---

## Open Questions (not yet decided)

See `docs/PRD.md §13` for the full list. Key unresolved items:
- Signature moments for Marty, Meesmickle, Rootis, Sclorbo (Nicolas to recall)
- Velynne Harpell's arc (check published adventure)
- Sephek Kaltro — did he appear in the campaign?
- Messie's specific Bremen function (shop? services? quest-giver?)
- Unit struct save budget for D&D fields (audit in Phase 1, issue #10)
