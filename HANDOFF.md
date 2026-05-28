# Handoff: Combat reconciliation DONE → next up is the story/pacing pass

**Date:** 2026-05-28
**Session Focus:** Finished reconciling all combat docs to **vanilla FE** (committed + pushed). The
next session is a **story/pacing planning pass** — see Next Steps.

## Settled this session (do NOT re-litigate)

Combat resolution is **vanilla FE8** (hit/avoid/might/crit/doubling); **D&D is flavor only.**
Nicolas ratified these on 2026-05-28:
- **d20** = cosmetic crit flourish only (never gates a hit).
- **AC** dropped → defense is FE `DEF`/`RES` + speed/luck/terrain avoid.
- **Saving throws** dropped → status staves always-hit (vanilla FE); offensive spells use FE magic combat (MAG vs RES).
- **Advantage/disadvantage** dropped → positioning is FE terrain + triangle.
- **Weapon damage** = FE fixed **might** (not rolled dice); **crit = FE ×3**.
- **13-damage-type resistance/vulnerability/immunity multiplier** dropped → damage types are **flavor labels**; iconic matchups (fire vs ice trolls, hammer vs skeletons) use **vanilla FE weapon effectiveness** (FE-native, not a multiplier). *Status/condition* immunities (charm/fear/sleep) and crit-immunity (Hoplon) **remain** mechanical.
- Net: **there is no surviving substantive D&D combat mechanic** — the layer is flavor + FE-native effectiveness/triangle. (Memory `feedback_fe-strictness` updated with the lesson: cut even appealing D&D mechanics if they add an under-the-hood computation FE lacks.)

## Accomplished

- Swept the entire combat spine to vanilla FE across **21 files**: `decisions.md`, `combat-formulas.md`,
  `rules-mapping.md` (§A/§C/§E/§G), `PRD.md` (§6.4–§6.7, §11, §12, §13, §14, §16 issues #7–#18, §20,
  Appendix A), `fe-mechanic-map.md` + `.yaml`, `class-mapping.md`, `class-progression-tables.md`,
  `party-balance.md`, `magic-items.md`, `research.md` + `campaign-brief.md` (historical banners),
  `chapters/ch01-the-iron-trail.yaml`, and all **7 PC YAMLs** (flavor banners; d20/resistance-dependent
  abilities reflavored to FE-native stat swings / always-hit / +DEF buffs / FE effectiveness).
- All YAML re-validated (parses clean). Committed as **`b0cca7f`** and **pushed to `origin/main`**.
- **GitHub milestone #2 renamed** "M1: D20 Combat Works" → **"M1: D&D Combat Layer Works"** (live, done).

## Current State

- Working tree **clean**; `main` is at `b0cca7f`, pushed. Combat docs are fully self-consistent.
- The fe-mechanic-map (`.md` + `.yaml`) is the authoritative per-ability resolution layer and is in sync.
- **MVP scope confirmed unchanged:** Ch 1–7, unpromoted, 5e levels 1–5, ending at the Revel's End
  cliffhanger (`decisions.md`). Full game is **20 chapters** in concept, but **Ch 8–20 are NOT yet
  outlined** (no doc — only the DM notes + published book hold that material).

## Blockers / open

- **Ch 8–20 not outlined** — the back half of the 20-ch arc needs a writing/pacing pass (the next session).
- **Build toolchain still NOT installed** (`devkitARM`, `agbcc`, `ColorzCore`, `libpng`) — don't install silently.
- **Rootis bulk** — Snow Body's B/P/S "resistance" is flavor now and no longer adds durability; raise his FE `DEF` if he should stay tanky (flagged in `pcs/rootis.yaml`).
- **Signature moments still `tbd`** for Marty / Meesmickle / Rootis / Sclorbo.
- **AoE→FE tension** unsolved (`siege_single_target` compromise — confirm in playtest or design a real FE AoE).

## Next Steps (priority order)

1. **STORY / PACING PLANNING PASS — start here.** A planning/writing session, not coding. Sequence:
   1. **Read the source PDFs** (both in the References folder — paths in Key Files):
      - `DungeonMasterNotesIcewindDale.pdf` — **authoritative** for what actually happened in *this* campaign (the source of the 7-chapter MVP).
      - Targeted sections of `icewind-dale-rime-of-the-frostmaidenpdf_compress.pdf` (the published book, large — use page ranges) for region/chapter structure + key NPCs/quests to fill **Ch 8–20**.
   2. **Build an FE8 pacing + reward reference** — chapter rhythm (big-battle vs breather/sidequest), and where FE8 hands out promotion items (Knight's/Hero's Crest, Guiding Ring, Orion's Bolt, Elysian Whip, Master/Heaven Seal), treasure, villages, secret shops, Tower of Valni / Lagdou Ruins. Ground it against FE8's actual schedule, not memory alone.
   3. **Produce a 20-chapter skeleton doc** (new `docs/chapter-outline.md` or similar) — one line per chapter, tagged **big-battle / breather / sidequest**, with **reward + promotion-item placement** done diegetically (e.g. first Master-Seal-equivalent in a chest at the MVP→post-MVP seam, foreshadowed in MVP). **Reaffirm the MVP cutline at Ch 7.** Note: promotions are post-MVP (≈Ch 9–11), so promotion-item placement is mostly a full-game concern — but seed/foreshadow it in Ch 1–7.
   4. **Then reconcile PC-YAML ability/item/level gating** against that skeleton (the YAMLs already gate by chapter; pacing decisions may shift those gates — do this *after* the skeleton so we don't redo it).
2. **Map the remaining `fe_mechanic`-less abilities** (`docs/fe-mechanic-map.md` §Unmapped): `rootis.dragon-wings`→Manakete transform, `prof-rbg.nimble-escape`→`CA_CANTO`, `prof-rbg.infuse-item`→`forge_command`, etc. Goal: 100% coverage so the build can assert it.
3. **Scaffold `tools/build-campaign.ts`** to consume `fe-mechanic-map.yaml` + the PC YAMLs.
4. Re-evaluate **`docs/party-balance.md`** for MVP-only (Ch1–7, unpromoted).
5. Finalize **`docs/magic-items.md`** `[VERIFY]` rules text (combat revert already applied).
6. Decide build deps; then **Phase 1 — "D&D Combat Layer"** (damage-type flavor labels + FE effectiveness, spell slots, `engine/status` + `engine/hazards`, combat-preview reskin, cosmetic crit flourish). No d20/AC/saving-throw/resistance engine to build — Phase 1 est. ~6–10 sessions.

## Key Files

- **Source PDFs for the story pass** (in the base-ROM References folder):
  - `/Users/Yonick/Documents/Claude/Projects/Manchego Stars / Fire Emblem Game/References/DungeonMasterNotesIcewindDale.pdf`
  - `/Users/Yonick/Documents/Claude/Projects/Manchego Stars / Fire Emblem Game/References/icewind-dale-rime-of-the-frostmaidenpdf_compress.pdf`
- [docs/PRD.md](docs/PRD.md) §7 — the 7-chapter MVP breakdown (story is here); §14 roadmap.
- [docs/decisions.md](docs/decisions.md) — settled design (incl. the vanilla-FE combat decisions); MVP scope.
- [campaigns/rime-of-the-frostmaiden/chapters/](campaigns/rime-of-the-frostmaiden/chapters/) — only `ch01` exists; the pacing pass creates the rest.
- [docs/fe-mechanic-map.md](docs/fe-mechanic-map.md) + [.yaml](campaigns/rime-of-the-frostmaiden/fe-mechanic-map.yaml) — per-ability FE resolution (authoritative, in sync).
- [campaigns/rime-of-the-frostmaiden/pcs/](campaigns/rime-of-the-frostmaiden/pcs/) — 7 PC YAMLs (chapter-gated abilities; reconcile against the new chapter skeleton in step 1.4).
- Validate any campaign YAML: `ruby -ryaml -e 'YAML.load_file("<path>")'`
