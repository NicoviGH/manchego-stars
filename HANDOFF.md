# Handoff: Per-PC Spell Curation + Full YAML Retier

**Date:** 2026-05-28
**Session Focus:** Execute the deferred #1 next-step — curate each PC's signature kit, convert per
[docs/rules-mapping.md](docs/rules-mapping.md), gate by the 1:1 chapter curve, and retier ALL 7 PC
YAMLs (only Wolfram was partially done before). Adopted a new dual structure and discovered the
PDFs preserve prepared-spell data.

---

## Big Decisions Made This Session (carry these forward)

1. **DUAL STRUCTURE for every spell/ability.** Each YAML ability now carries `fe_mechanic` (the
   vanilla FE8 anchor that makes it play cleanly) + `flavor` (the character-specific reskin name +
   in-world text, so the D&D flavor is *visible in-game*). Spine = FE; overlay = D&D flavor.
   (Nicolas's call: "select the clean FE ability, then give it character-specific flavor text.")
2. **PREPARED-SPELL FINDING.** The D&D Beyond PDFs preserve a `PREP` column (`P`=prepared,
   `O`=known-unprepared). Only matters for *prepared-casters*: **Marty (Druid)** and **RBG
   (Artificer)**. Both players' prepared lists turned out to be entirely their subclass "Always
   Prepared" spells — so the subclass list IS the authentic kit. Known-casters (Rootis/Meesmickle/
   Sclorbo) don't prepare; their full known list is the kit. Re-extract:
   `pdftotext -layout "<PC> Character Sheet.pdf" - | grep -E "^P[[:space:]]"`
3. **RBG is an ARTILLERY BLASTER, not a healer.** His prepared list = the Artillerist bonus spells
   (Shield, Thunderwave, Scorching Ray, Shatter, Fireball, Wind Wall, Ice Storm, Wall of Fire,
   Cone of Cold, Wall of Force). The earlier Cure-Wounds-centric guess was wrong; corrected.
4. **Marty's prepared = Circle of Spores list** (Blindness/Deafness, Gentle Repose, Animate Dead,
   Gaseous Form, Blight, Confusion, Cloudkill, Contagion + Chill Touch). Fully reskinned as visible
   spore abilities (Witherspore / Blinding Bloom / Corpse Bloom / Rot / Maddening Spores / etc.).
5. **Three forks resolved (also in [docs/pc-spell-lists.md](docs/pc-spell-lists.md)):**
   - **Rootis fire spells — KEEP AS-IS.** Immolation + Incendiary Cloud stay as fire despite his
     White-Dragon cold identity + ×2 fire vulnerability. Intentional irony. Both post-MVP.
   - **Sclorbo reviver — POST-MVP.** Revivify is *mechanically* reachable Ch6 (3rd-level via Lore's
     Additional Magical Secrets — the docs' "5th-level" reasoning was wrong), but we gate ALL
     raise-dead healing to Ch9+ to preserve Classic-mode permadeath tension. MVP heal = Cure Wounds.
   - **RBG's Wish — STORY-ONLY, NO PLAY MECHANIC.** Fires once as a scripted finale beat: RBG wishes
     **Pinky** (his homunculus "son", the Pegasus Knight companion) into a true living being.

## Accomplished

- **All 7 PC YAMLs retiered** with `unlock_chapter` on every ability + `fe_mechanic`/`flavor`:
  - **rootis** — Dragon Wings fixed from "always available" → Ch13; added full ice kit + kept-fire
    spells; flying gate corrected.
  - **marty** — swapped to prepared spore kit; Halo dice + Symbiotic temp HP now chapter-scaled
    (was hard-coded endgame values); Spreading Spores/Fungal Body gated post-MVP.
  - **prof-rbg** — swapped to prepared Artillerist blaster kit; Wish → story-only; Brie tbd→Ch14;
    Pepperjack→Ch3; Explosive Cannon→Ch9.
  - **meesmickle** — added Eyebite/Finger of Death/Dark One's Own Luck + MVP tomes; Demiplane
    mechanic DROPPED (narrative-only); EB beam count chapter-scaled; Hurl Through Hell→Ch13.
  - **sclorbo** — reviver kit re-gated to Ch9/Ch9/Ch11 (was Ch4/Ch6/Ch7); added MVP signature
    spells; BI die chapter-scaled.
  - **braulo** — gated full Berserker line; **added missing Frenzy (Ch3) + Extra Attack (Ch5)**.
  - **wolfram** — added missing armor abilities (Recharge Ch5, Explosive Burst Ch7) + Forge line
    (Forge Expert Ch7, Blade Forge Ch11, Master of the Forge Ch15).
- **Updated [docs/pc-spell-lists.md](docs/pc-spell-lists.md)** with confirmed kits, the prepared
  finding, dual structure, and the 3 forks.
- **Validated all 7 YAMLs parse** (Ruby/psych) and printed an MVP-vs-post-MVP gate audit — clean.

## Tried But Didn't Work

- **PyYAML not installed** (`ModuleNotFoundError: yaml`). Used macOS Ruby (`ruby -ryaml`) instead.
- **JSON sheets have no prepared data** — `data/pc-sheets/*.json` are curated summaries. The PDFs'
  PREP column is the only source for prepared spells.

## Current State

- The full PC roster is now MVP-gated and dual-structured. The YAMLs are the gated, machine-readable
  output that `tools/build-campaign.ts` will consume. Working tree has uncommitted changes (8 files:
  7 YAMLs + pc-spell-lists.md + this HANDOFF).
- `fe_mechanic` strings are human-readable anchors (e.g. "Nosferatu", "Sleep staff", "Summoner
  phantom"), not yet mapped to concrete FE8 item/skill IDs — that mapping is a later pipeline task.

## Blockers

- **AoE→FE tension noted, not solved.** D&D AoE (Fireball, Cone of Cold, Ice Storm) has no clean FE
  tome analogue; currently compromised to "siege-range single-target." Confirm this feels right in
  Phase 1 playtesting, or design a real FE AoE mechanic.
- **Signature moments still `tbd`** for Marty/Meesmickle/Rootis/Sclorbo (Nicolas to recall).
- **Build toolchain still NOT installed** (`devkitARM`, `agbcc`, `ColorzCore`, `libpng`) — blocks
  compiling. Don't install silently; confirm with Nicolas.
- **Magic items** (`docs/magic-items.md`) still have `[VERIFY]` homebrew rules text outstanding.

## Next Steps (priority order)

1. **Map `fe_mechanic` strings → concrete FE8 item/skill IDs** (the next layer of the spec — turn
   "Nosferatu"/"Sleep staff" into real engine references for build-campaign.ts).
2. **Update PRD §7/§14/§16** for the 20-chapter total + post-MVP promotion cadence (still old scope).
3. **Re-evaluate [docs/party-balance.md](docs/party-balance.md)** for the MVP-only state (Ch1–7,
   unpromoted, 5e L1–7) — current analysis assumes level-20 end-state.
4. **Finalize magic items** — get `[VERIFY]` rules text, slot chosen items into YAMLs.
5. **Resolve the AoE→FE design tension** with playtesting.
6. **Brainstorm post-MVP Ch 8–20 outline** (writing session).
7. Decide on build deps; then Phase 1 issue #7 (`engine/d20-combat/dice_rng.c`).

## Key Files

- [campaigns/rime-of-the-frostmaiden/pcs/*.yaml](campaigns/rime-of-the-frostmaiden/pcs/) — **all 7
  retiered this session**; dual structure (`fe_mechanic` + `flavor`) + `unlock_chapter` throughout
- [docs/pc-spell-lists.md](docs/pc-spell-lists.md) — confirmed kits + prepared finding + forks
- [docs/rules-mapping.md](docs/rules-mapping.md) — D&D→FE conversion rules (the strictness spine)
- [docs/class-progression-tables.md](docs/class-progression-tables.md) — level→chapter gate tables
- [docs/decisions.md](docs/decisions.md) — settled decisions
- Reference PDFs: `/Users/Yonick/Documents/Claude/Projects/Manchego Stars / Fire Emblem Game/References/PCs/*.pdf`
  (read with `pdftotext -layout`; PREP column = prepared spells)
- Validate YAMLs: `for f in campaigns/rime-of-the-frostmaiden/pcs/*.yaml; do ruby -ryaml -e 'YAML.load_file(ARGV[0])' "$f"; done`
