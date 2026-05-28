# Handoff: Combat-Resolution Reconciliation — docs swept to "vanilla FE, d20 = flavor"

**Date:** 2026-05-28
**Session Focus:** Executed prior-handoff **Next Step #1** — reconciled every combat-system doc
(and the d20-dependent content) from the old "Hybrid d20/FE" design to **vanilla FE rules, d20 as
flavor only**. Nicolas ratified the four substantive sub-questions at the top of session.

---

## The ratified decision (carry forward)

Combat **rules stay vanilla FE8** (hit/avoid/might/crit/doubling); **D&D is flavor only.** The four
sub-questions the prior handoff said must NOT be silently decided — Nicolas answered them this
session (2026-05-28):

1. **d20 → cosmetic crit flourish only.** A brief "d20 lands on 20" animation may play when an FE
   crit fires. It never gates/alters the hit. It's the only place the die appears.
2. **Saving throws → dropped.** No DCs/save rolls. Status staves (Sleep/Silence/Berserk/Poison)
   always-hit per vanilla FE; offensive spells use FE magic combat (MAG vs RES, FE hit/avoid).
3. **AC → dropped.** Defense is FE `DEF`/`RES` + speed/luck/terrain avoid. No to-hit target.
4. **Advantage/disadvantage → dropped entirely.** Positioning matters via FE terrain + triangle.

**Derived calls (both ratified by Nicolas):**
- Weapon damage = **FE fixed might** (not rolled dice; tune from the 5e die's average); crit = vanilla FE **×3**. ✔ confirmed.
- **Damage-type resistance/vulnerability/immunity DROPPED as a mechanic** (Nicolas, 2026-05-28: "not part of the FE combat system… should not conflict with vanilla FE under the hood"). The 13 damage types are now **flavor labels only**; iconic matchups (fire vs ice trolls, hammer vs skeletons) use **vanilla FE weapon effectiveness** (FE-native, not a multiplier). *Status/condition* immunities (charm/fear/sleep) and crit-immunity (Hoplon) **remain** mechanical — they're not damage-type resistance. **So there is no surviving substantive D&D combat mechanic** — the layer is purely flavor + FE-native effectiveness.

## Accomplished — full doc + content sweep (all internally consistent, all YAML re-validated)

- **docs/decisions.md** §Combat System — rewritten: dated supersede note + new vanilla-FE decisions
  (d20 cosmetic-crit, AC dropped, saves dropped, advantage dropped, FE might damage, FE ×3 crit,
  resistance layer kept, hit-rate tuning = vanilla FE).
- **docs/combat-formulas.md** — fully rewritten to a vanilla-FE reference (was the hybrid formula doc).
- **docs/rules-mapping.md** — §A combat table reworked (DROP→FE rows), §C spell-save row dropped,
  §E prof-bonus/ability-mod rows fixed, KEEP-philosophy line corrected, saving-throw open-item struck.
- **docs/PRD.md** — swept everywhere: L14 pitch, Goal 2 & 4, the d20 user story, §6.2 engine tree
  (dir kept, files relabeled), §6.4 contract, **§6.5 full rewrite**, §11 risks (d20-variance moot,
  UI, save-budget), §12 metric #3, §13 Q9/Q10, **§14 milestone renamed** "D&D Combat Layer Works",
  §15 milestone list, **§16 M1 issues #7–#18 re-scoped/dropped** with a banner, §20 DoD #5,
  Appendix A decomp table, + a PC-class-table footnote that AC/save values are flavor.
- **docs/fe-mechanic-map.md** — ⚠ OPEN section → **RESOLVED** with a per-feature reflavor table
  (advantage/AC/save features → FE stat swings / always-hit). Backlog lines updated; `guard_stance`
  fixed; `ac_buff_reaction` renamed `def_buff_reaction`.
- **campaigns/.../fe-mechanic-map.yaml** — header revert note; removed 3 dangling `base: advantage_state`;
  renamed `ac_buff_reaction`→`def_buff_reaction` (×2). **Parses clean.**
- **7 PC YAMLs** — "FLAVOR ONLY" banner above each `d20_fields` block (AC/prof_bonus/`save:`/`advantage*`
  are source-of-record, NOT read by resolution; `spell_slots` IS still live). sclorbo magic-missile
  `fe_mechanic` "skips the d20 roll" → "always hits". **All 7 parse.**
- **docs/research.md** — top-of-doc HISTORICAL/NOT-ADOPTED banner + a §6.3 banner (kept as the
  research record; combat approach superseded).
- **docs/magic-items.md** — Rod of the Pact Keeper "+DC" → "+might (no save DCs)".
- **campaigns/.../chapters/ch01-the-iron-trail.yaml** — combat-doc pointer, "advantage" terrain note,
  AC/d20 difficulty + design notes all reworded to vanilla FE.

### Second pass — damage-type resistance dropped (Nicolas's follow-up, same day)
- **decisions.md / combat-formulas.md / rules-mapping.md §A+§G / PRD (§6.4–§6.7, §11, §12, §16 #12–#13,
  §20, Appendix A)** — resistance/vuln/immunity multiplier removed; damage types = flavor labels;
  iconic matchups → vanilla FE weapon **effectiveness**.
- **fe-mechanic-map .md + .yaml** — `damage_resistance`→`none` (wolfram.fire-resistance is flavor);
  `grant_resistance_choice`→`def_buff_timed` in engine/status (meesmickle.fiendish-resilience);
  `rage_self_buff` ×0.5→+DEF; engine-module header notes updated. **Parses clean.**
- **class-mapping.md / class-progression-tables.md / campaign-brief.md / party-balance.md** — banners +
  reflavored the explicit "resist"/"phys resist"/"cold resist" FE-conversion cells to +DEF/RES.
- **PC YAMLs** — damage-type-resistance note added to braulo/marty/meesmickle/wolfram/rootis banners
  (Rootis also flagged: bulk must come from FE DEF now); ×0.5 `fe_mechanic` strings reflavored. All parse.

## Current State

- **Nothing committed yet this session** (about to commit per Nicolas's "yes"). ~18 modified files.
  Prior work is at `b15f337` on `origin/main`.

## Blockers / awaiting Nicolas

- ✅ **GitHub milestone #2 renamed** to "M1: D&D Combat Layer Works" (done this session). The M1
  issues #7–#18 are **not** live on GitHub yet — only #1–#6 (M0) exist — so they'll be created from
  the corrected PRD §16 when M1 starts.
- **Build toolchain still NOT installed** (`devkitARM`, `agbcc`, `ColorzCore`, `libpng`).
- **AoE→FE tension** still unsolved (`siege_single_target` compromise).
- **Signature moments still `tbd`** for Marty/Meesmickle/Rootis/Sclorbo.
- **Rootis bulk** — his Snow Body B/P/S "resistance" no longer adds durability; raise his FE `DEF`
  if he should stay tanky (flagged in `pcs/rootis.yaml`).
- **Story/MVP deep-dive (NEW ask, 2026-05-28):** Nicolas wants to (a) study how FE8 distributes
  promotion items / treasure / paced combat-vs-sidequest and fold that into the story (e.g. find a
  promotion item in a chest), (b) confirm/refresh the **MVP chapter scope** (full game extended to
  20 ch; MVP may need updating), and (c) use the **PDF reader** on the Frostmaiden campaign book +
  FE8 chapter pacing as references. This is a planning/story session — see "Next Steps".

## Next Steps (priority order — #1 from last handoff is now DONE)

1. **STORY / MVP DEEP-DIVE (Nicolas's new ask — likely the next session).** A planning session, not
   coding. Three threads: (a) **FE8 pacing & rewards study** — how FE8 spaces big battles vs lighter
   chapters, when promotion items / Knight's Crest etc. appear, how treasure/villages are distributed
   — then fold that into our chapter structure (e.g. promotion item found in a Ch-N chest, a sidequest
   chapter for breathing room). (b) **Re-confirm MVP scope** — full game is now 20 chapters; verify
   what the MVP slice is (was Ch1–7) and whether it still holds. (c) **PDF reader on the Frostmaiden
   campaign book** to fill story gaps + cross-ref FE8 chapter cadence. *Do this BEFORE deep item/level
   work in the PC YAMLs, since pacing decisions reshape where things unlock.*
2. **Map the remaining `fe_mechanic`-less abilities** (docs/fe-mechanic-map.md §Unmapped):
   `rootis.dragon-wings`→Manakete transform, `prof-rbg.nimble-escape`→`CA_CANTO`,
   `prof-rbg.infuse-item`→`forge_command`, etc. Goal: 100% coverage so the build can assert it.
3. **Scaffold `tools/build-campaign.ts`** to consume `fe-mechanic-map.yaml` + the PC YAMLs.
4. Re-evaluate **docs/party-balance.md** for MVP-only (Ch1–7, unpromoted).
5. Finalize **docs/magic-items.md** `[VERIFY]` rules text (combat revert already applied).
6. Decide build deps; then **Phase 1 — now "D&D Combat Layer"** (damage-type flavor labels + FE
   effectiveness, spell slots, `engine/status` + `engine/hazards`, combat-preview reskin, cosmetic
   crit flourish). No d20/AC/saving-throw/resistance engine to build — Phase 1 est. dropped to 6–10 sessions.

## Key Files (combat spine — now all vanilla-FE-consistent)

- [docs/decisions.md](docs/decisions.md) §Combat System — the ratified vanilla-FE decisions.
- [docs/combat-formulas.md](docs/combat-formulas.md) — vanilla-FE combat reference.
- [docs/rules-mapping.md](docs/rules-mapping.md) §A — D&D→FE combat conversion.
- [docs/fe-mechanic-map.md](docs/fe-mechanic-map.md) — resolution table for reflavored features.
- [campaigns/rime-of-the-frostmaiden/fe-mechanic-map.yaml](campaigns/rime-of-the-frostmaiden/fe-mechanic-map.yaml)
- Validate the map: `ruby -ryaml -e 'YAML.load_file("campaigns/rime-of-the-frostmaiden/fe-mechanic-map.yaml")'`
