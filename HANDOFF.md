# Handoff: Engine-Level Rules/Class Mapping + PC Sheet Audit

**Date:** 2026-05-28
**Session Focus:** Revisit the 5e→FE class mapping; reframe it as an engine-level (reusable) system; harden it toward strict FE8 playability; audit all 7 PC sheets against their real D&D Beyond PDFs; set up the chapter-by-chapter progression gating for a 20-chapter game.

---

## Big Decisions Made This Session (carry these forward)

1. **FE8 is the spine; D&D is flavor overlay.** When a D&D mechanic has no FE analogue, drop it or convert to FE-native form. (Also saved to auto-memory.) Codified in [docs/rules-mapping.md](docs/rules-mapping.md).
2. **Engine/content split applies to the rules layer too.** Generic 5e classes + conversion rules = reusable engine layer. Custom races (Hermit Crab, Snowperson, Myconid, Chwinga, Drakeborn, Underfolk, Vampire Tabaxi) and custom subclasses (Circle of Spores, Metallurgist, Artillerist flavor) stay campaign content — character uniqueness preserved.
3. **Full game = 20 chapters** (FE8 cadence). **MVP = Ch 1–7** (first third), ends at Revel's End cliffhanger. Post-MVP = Ch 8–20 (not yet outlined).
4. **Chapter→5e-level curve = 1:1 linear** (Ch N ≈ 5e level N). So MVP = 5e levels 1–7. Promotions happen post-MVP (~Ch 10 / 5e L11, FE8 cadence). PCs play MVP entirely unpromoted.
5. **All 7 PCs reach 5e level 20 in-game**, including Sclorbo (his real-life L16 is flavor only).
6. **Class-mapping refinements:** Marty Shaman→**Monk** (differentiate from Meesmickle's Shaman); Sclorbo Lore Bard→**Lore Bishop** hybrid (Dance + healing; balance lever = Dance OR Cast per turn, not both); Rootis Dragon Wings = **Manakete-style transform**, post-MVP (5e L14); RBG's cannons are **Pepperjack** (Ch1) + **Brie** (post-MVP, Artificer L15) — Pokémon-style automatons that say their own names, Brie is Pepperjack's girlfriend; folded 5e stats (WIS/INT/CHA) to **MAG**. Braulo is a **Hermit Crab** = a wall, not a glass cannon (party-balance.md corrected).

## Accomplished

- **poppler installed** (`brew install poppler`) — PDF reading now works (`pdftotext`, `pdfinfo`). Unblocks all reference PDFs.
- **Verified every class progression against sources:** Tasha's PDF (Artificer/Artillerist, Circle of Spores), Metallurgist homebrew PDF (Smith school), and the **dnd5eapi.co SRD API** for Barbarian/Bard/Sorcerer/Warlock/Druid + subclasses Berserker/Lore/Draconic/Fiend. Hard confirmations: Dragon Wings = Sorcerer L14, Hurl Through Hell = Warlock L14, Brie/2nd-cannon = Artificer L15, Cutting Words = Bard L3.
- **Wrote 4 new docs:**
  - [docs/rules-mapping.md](docs/rules-mapping.md) — generic D&D→FE mechanic conversion rules (KEEP/CONVERT/DROP across 9 categories). Engine-level, reusable.
  - [docs/class-progression-tables.md](docs/class-progression-tables.md) — per-class level→feature→FE-chapter tables + reconstructed per-PC build paths. Has an **Action Items** list at the bottom.
  - [docs/magic-items.md](docs/magic-items.md) — first-pass catalog of each PC's magic-item kit with FE conversion ideas (homebrew items flagged `[VERIFY]`).
  - [docs/pc-spell-lists.md](docs/pc-spell-lists.md) — every caster's **complete** spell list, the picking menu for next session.
- **Audited all 7 PC sheets vs YAMLs.** Fixed Wolfram's mis-port (removed invented Investiture of Stone/Forcecage; added his real Conjure Elemental/Creation/Imprisonment; reframed Devil's Sight as racial darkvision; Breath Weapon is racial Drakeborn, not a Metallurgist Flamethrower).
- **Updated docs/class-mapping.md, docs/PRD.md §6.7, docs/decisions.md, docs/party-balance.md** for the decisions above.
- **Committed locally** as `ae47736` (14 files, +781/−79). **NOT pushed** — pushing to `main` needs Nicolas's go-ahead.

## Tried But Didn't Work

- **PDF reading was initially blocked** — no poppler/pypdf/pdfplumber/Quartz on the machine. Nicolas approved installing poppler, which fixed it. (`pdftoppm` is what the Read tool's PDF support needs.)
- **`${c^^}` bash uppercase** failed — macOS default bash is 3.2. Use lowercase loops.
- **JSON exports (`data/pc-sheets/*.json`) are only curated summaries** — `notable_spells` omits most of each sheet. The PDFs are the complete source; use those.

## Current State

- **The mapping is now well-specified at the engine level** and verified against real sources. The two audit docs (rules-mapping, class-progression-tables) are the new design spine alongside the PRD.
- **PC YAMLs are PARTIALLY retiered.** Only **Wolfram** got the chapter-gating + mis-port fix this session. The other 6 are unchanged from the prior session and still reflect end-state (level-20) content without chapter gating.
- **Key finding:** every caster's real sheet has dozens of spells (Marty 100+) plus a magic-item kit the YAMLs don't capture. This is mostly intentional curation — DO NOT port everything (rules-mapping §C). The plan is to curate a tight signature kit (~6–10) per PC.
- Working tree clean; HEAD = `ae47736` (local only).

## Blockers

- **Per-PC spell curation needs Nicolas's picks.** Agreed workflow: Nicolas hand-picks from [docs/pc-spell-lists.md](docs/pc-spell-lists.md) which spells become FE abilities; then Claude converts + gates them. This is the gate for finishing the YAML retier.
- **Magic items: several homebrew ones need rules text** (Luck E. Cheese w/ 2 Wish charges, Masque Charm, Sneezedrum, Paper birds) — flagged `[VERIFY]` in magic-items.md. Luck E. Cheese's Wish needs deliberate FE design.
- **Build toolchain still NOT installed** (`devkitARM`, `agbcc`, `ColorzCore`, `libpng`) — blocks compiling any engine code. Don't install silently; confirm with Nicolas.
- **Signature moments TBD** for Marty/Meesmickle/Rootis/Sclorbo (still `signature_moment.chapter: tbd`).

## Next Steps (priority order)

1. **Per-PC spell curation (the main deferred task).** Walk Nicolas through [docs/pc-spell-lists.md](docs/pc-spell-lists.md) per character; he picks the signature kit; convert each pick per rules-mapping.md and gate by the 1:1 chapter curve. Then retier the remaining 6 YAMLs (rootis, meesmickle, sclorbo, marty, prof-rbg, braulo) the way Wolfram was done.
2. **Work the Action Items list** at the bottom of [docs/class-progression-tables.md](docs/class-progression-tables.md) (Rootis Dragon Wings→Ch13, Meesmickle arcanums→Ch10+/HtH→Ch13, Sclorbo heal kit→post-MVP, Marty Symbiotic temp HP = 4×level + Spreading/Fungal Body post-MVP, RBG Brie→Ch14).
3. **Finalize magic items** — get `[VERIFY]` rules text, then slot chosen items into YAMLs as post-MVP inventory.
4. **Update PRD §7/§14/§16** for the 20-chapter total + post-MVP promotion cadence (the chapter breakdown still assumes the old scope).
5. **Re-evaluate party-balance.md for the MVP-only state** (Ch1–7, unpromoted, 5e L1–7) — current analysis assumes level-20 end-state.
6. **Brainstorm the post-MVP Ch 8–20 outline** (requires the rest of the Frostmaiden arc — a writing session).
7. Decide on build deps; then Phase 1 issue #7 (`engine/d20-combat/dice_rng.c`).

## Key Files

- [docs/rules-mapping.md](docs/rules-mapping.md) — **NEW**; generic D&D→FE conversion rules (engine-level, the strictness spine)
- [docs/class-progression-tables.md](docs/class-progression-tables.md) — **NEW**; per-class level→chapter tables + per-PC build paths + Action Items
- [docs/pc-spell-lists.md](docs/pc-spell-lists.md) — **NEW**; full per-PC spell menus for curation
- [docs/magic-items.md](docs/magic-items.md) — **NEW**; per-PC magic-item catalog (first pass)
- [docs/class-mapping.md](docs/class-mapping.md) — updated 5e→FE class table
- [docs/decisions.md](docs/decisions.md) — settled decisions (incl. this session's class-mapping refinements)
- [docs/PRD.md](docs/PRD.md) — source of truth; §6.7 updated, §7/§14/§16 still need 20-chapter update
- [docs/party-balance.md](docs/party-balance.md) — needs MVP-only re-evaluation
- [campaigns/rime-of-the-frostmaiden/pcs/*.yaml](campaigns/rime-of-the-frostmaiden/pcs/) — only wolfram.yaml retiered; other 6 pending
- Reference PDFs: `/Users/Yonick/Documents/Claude/Projects/Manchego Stars / Fire Emblem Game/References/` (Tasha's, Metallurgist) and `References/PCs/*.pdf` (character sheets) — read with `pdftotext -layout`
- SRD API: `https://www.dnd5eapi.co/api/2014/classes/<class>/levels` and `/subclasses/<sub>/levels`
