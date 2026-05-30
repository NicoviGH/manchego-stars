# Handoff: FE8 compliance audit COMPLETE; lore/unit architecture split IN PROGRESS

**Date:** 2026-05-29
**Session focus:** Ran the full FE8 decomp-compliance audit on all 7 PCs and made them strict vanilla FE8 classes (stats, classes, promotions, weapons, no element-as-mechanic, no unique abilities). Then started a clean architecture split (mechanics vs. flavor/lore) — **this is where the next session resumes.**

## How Nicolas wants this work done (standing rules — reinforced hard this session)

- **Stock vanilla FE8 classes, nothing extra.** PCs use the decomp's class data verbatim (bases, growths, caps, MOV, CON, weapon ranks). **No custom stats, no D&D-derived tuning, no per-character abilities** (FE8 has no skill system), **no timed buffs, no special movement, no weapon procs**.
- **Element = flavor text, NEVER a mechanic.** Fire/ice/cold/necrotic/etc. are names only. No damage-type resistance/immunity/vulnerability, no element-keyed bonuses, no "ice slows / cold heals." (He had to repeat this — do not reintroduce it.)
- **Individuality comes from flavor text, portrait/sprite art, and palette** — not mechanics.
- **Ground every FE8 claim in `fireemblem8u/` decomp.** **Clean native rewrites** (no band-aids). **Auto-push to main.** **Collaborative, chapter-by-chapter** story work.

## Accomplished this session (all committed + pushed to main)

Audit commits (in order): `174058d` → `e2ec6c7` → `222326c` → `fd3abe3` → `e6cc7a6` → **`14b6000` (current HEAD)**.

- **MOV fixed to class-fixed values** (CharacterData has no MOV field; MOV is class-only). `174058d`.
- **All 7 PCs reset to verbatim vanilla FE8 class stats + growths** from `data_classes.c`; collapsed D&D STR/MAG split to FE's single Pow (STR for physical classes, MAG for magic); LCK base = 0 (ClassData defines no base luck). `e2ec6c7`.
- **Weapon types tagged** to each class's FE weapon (Pirate=Axe, Knight=Lance, Archer=Bow, Mage=Anima, Shaman=Dark, Monk/Bishop=Light, Priest=Staff).
- **Sclorbo reclassed Dancer → Priest → Bishop** (Nicolas's call): vanilla staff healer; Heal Staff legal at base, attack cantrips are Light tomes at the Bishop promotion; Rapier removed; Dance dropped. `222326c`.
- **Cross-class items resolved** (FE-strict): Marty's Heal Staff gated to Summoner promotion; Wolfram's Magic Stone → Javelin and Fire Bolt removed (fire identity = flavor on his Javelin/breath); RBG's sword = story-only, tome removed. `222326c`.
- **RBG → vanilla Archer → Sniper.** Dropped the custom "Artillerist" promotion. **Pepperjack & Brie reframed as separate RECRUITABLE units** (flavor: RBG built them), not RBG summons; stripped their non-FE turret kit. `fd3abe3`.
- **Wolfram's Breath Weapon** was a D&D cone+DEX-save+dice AoE → now mechanically just his Javelin, "fire" is flavor only. `fd3abe3`.
- **Element-as-mechanic purged everywhere** (`e6cc7a6`): Meesmickle necrotic-resistance + choose-damage-resistance → flat +DEF/RES; **Rootis** cold immunity / fire vulnerability / B-P-S resistance / cold-heals / +CHA-cold all → flavor only, Crystallize → flat +DEF, Snow Ski → ignore snow/ice move-cost; Wolfram fire-resistance → flavor, Forge tiers → flat +DEF / +Might / crit-negation.
- **ALL `unique_abilities` blocks stripped from all 7 PCs** + leftover weapon procs/dice removed (`14b6000`). PCs are now genuinely stock FE8 classes. Each PC file has a short note explaining why there are no abilities.

## Confirmed FE-legitimacy of remaining PC-file blocks (told Nicolas)
- `unique_abilities` = **NOT vanilla FE8** → removed.
- `supports` = **YES, core FE8** (C/B/A ranks + affinity bonuses) → kept.
- `signature_moment` = a scripted map event/dialogue pointer (FE-legal as event scripting) → kept.
- `companion` (RBG's Pinky) = a recruitable-unit reference → kept.
- `dnd:` block = D&D source/flavor only (does not drive mechanics) → kept for now.

## IN PROGRESS — architecture split (RESUME HERE)

**Decision (Nicolas approved "do what's best architecturally"):** separate mechanics from flavor.
- `pcs/*.yaml` + `npcs/*.yaml` = **lean unit definitions** (class, stats, growths, inventory, supports) — build-pipeline-consumable.
- `lore/*.md` = **all narrative/flavor** (concept, personality, backstory, the D&D ability *fantasies* with flavor names, relationships). Markdown.
- `data/pc-sheets/*.json` = raw D&D source (unchanged).

**Queued work (NOT yet done — blocked by a transient platform outage, see Blockers):**
1. `lore/README.md` — document the unit-vs-lore split.
2. `lore/<pc>.md` for all 7 PCs — **generate faithfully from pre-strip commit `e6cc7a6`** so stripped flavor (Market Rage, Symbiotic Entity, Shell Defense, etc.) is preserved, not lost to git. A generator was written at `/tmp/genlore.rb` (Ruby; pyyaml not installed) — recreate it: it loads `git show e6cc7a6:campaigns/.../pcs/<pc>.yaml`, pulls dnd concept + each ability's name/flavor/fe_mechanic, writes markdown. Exclude pepperjack/brie (they go to npcs lore).
3. `npcs/pepperjack.yaml` + `npcs/brie.yaml` — recruitable unit stubs (FE-legal class/stats TBD post-MVP; preserve flavor: sentient automatons, Pokémon-style speech "Pepperjack!"/"Brie!", they're dating, grey/pink chassis, portrait `data/portraits/pepperjack-and-brie.jpeg`). Plus `lore/pepperjack-and-brie.md`.
4. **Slim RBG's sheet:** replace the `pepperjack`/`brie` `recruitable_unit_ref` ability entries and the `companion` detail with lean recruit pointers (ids + how recruited), since the detail now lives in npcs/ + lore/.
5. Validate all YAML (`ruby -ryaml -e 'YAML.load_file("<path>")'`), commit, push.

## Blockers / open

- **Platform classifier outage (transient):** at end of session the tool-safety classifier was intermittently rejecting Write/Bash calls ("claude-opus-4-8 temporarily unavailable, cannot determine safety"). The lore/npcs work above never executed — **working tree is clean at `14b6000`**, nothing half-written. Just re-run the queued work when the classifier is healthy.
- **Decide on the `dnd:` block:** it duplicates `data/pc-sheets/*.json` and now that FE stats don't derive from D&D, its prose (personality/backstory) arguably belongs in `lore/`. Left in `pcs/*.yaml` for now — Nicolas may want it slimmed to structured source only (or removed) as a follow-up.
- **Ch 8–20 plot blocked on the rest of the DM notes** (DM notes cover Ch1–7 only).
- **Story walkthrough paused at Ch3** (FE8 "The Bandits of Borgo" / Termalaine Mine) — resume after the architecture split, or per Nicolas.
- **Weapon FE Might values not yet authored** — needs an FE item table (Iron/Steel/Silver tiers) that doesn't exist yet. Downstream authoring.
- **Build toolchain still NOT installed** (devkitARM/agbcc/ColorzCore/libpng).

## Key files

- PC unit YAMLs: `campaigns/rime-of-the-frostmaiden/pcs/*.yaml` (now lean-ish; `unique_abilities` removed).
- Vanilla FE8 reference: `fireemblem8u/src/data_classes.c` (class bases/caps/growths/MOV/CON/weapon ranks, indexed `[CLASS_X - 1]`); `include/bmunit.h:61` (ClassData struct), `:17` (CharacterData struct — note NO baseMov).
  - Class index lines: ARMOR_KNIGHT@477, ARCHER@1402, SNIPER@1518, MAGE@2102, BISHOP@2452, SHAMAN@2572, PRIEST@3952, PIRATE@3780, MONK@3896, DANCER@4408.
- Pre-strip flavor source: `git show e6cc7a6:campaigns/rime-of-the-frostmaiden/pcs/<pc>.yaml` (has the full `unique_abilities` flavor to migrate into `lore/`).
- To-create: `lore/` (README + 7 PC .md + pepperjack-and-brie.md), `npcs/pepperjack.yaml`, `npcs/brie.yaml`.
- Canon docs: `CLAUDE.md`, `docs/decisions.md`, `docs/rules-mapping.md §E`.
- Validate YAML: `ruby -ryaml -e 'YAML.load_file("<path>")'`
