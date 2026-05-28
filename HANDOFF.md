# Handoff: `fe_mechanic` → FE8 Reference Map + Combat-Resolution Doc Conflict Flagged

**Date:** 2026-05-28
**Session Focus:** Executed prior-handoff next-step #1 — turned the 93 human-readable `fe_mechanic`
anchors in the 7 PC YAMLs into concrete, machine-resolvable FE8 references (real `ITEM_*`/`CA_*`
enums or named custom engine features) for `tools/build-campaign.ts`. Mid-session Nicolas flagged
that the **combat-system docs are outdated** and must be reconciled (captured below, not yet actioned).

---

## Big Decisions Made This Session (carry these forward)

1. **CENTRAL map, not inline `fe_ref`.** The FE8 references live in one indexed file
   [`campaigns/rime-of-the-frostmaiden/fe-mechanic-map.yaml`](campaigns/rime-of-the-frostmaiden/fe-mechanic-map.yaml),
   keyed by `<pc_id>.<ability_id>`, rather than adding a `fe_ref:` field to all 93 abilities.
   Reasoning: one reviewable artifact, curated PC YAMLs stay untouched, single lookup for the build,
   and the custom-engine backlog falls out of it directly. The schema is identical if we later
   decide to inline it. `build-campaign.ts` must assert every `fe_mechanic` ability has exactly one
   map entry and no key is orphaned (both verified clean this session).
2. **Four `fe_ref` kinds:** `item` (vanilla `ITEM_*` delivers it), `class_ability` (vanilla `CA_*`
   delivers it), `custom_engine` (needs new code; `base:` points at the closest vanilla code to
   reuse), `none` (dropped / baked into stats / narrative-only). Full schema + legend in
   [docs/fe-mechanic-map.md](docs/fe-mechanic-map.md).
3. **Two PROPOSED-NEW engine modules** surfaced by the mapping: `engine/status` (status flags
   beyond the vanilla Sleep/Berserk/Silence/Poison staves) and `engine/hazards` (persistent/drifting
   hazard tiles + barrier walls). The 5 existing scaffold dirs don't cover these.
4. **⚠ COMBAT RULES STAY VANILLA FE (Nicolas, this session).** D&D is **flavor text only**; for
   playability the combat **rules** stay vanilla FE (hit%/avoid/might, FE crit). The d20 is at most
   a **cosmetic animation** (e.g. on a crit), **NOT** the resolution system — "the rules need to
   stay FE or the game won't play the same." This **contradicts** the currently-documented "Hybrid
   d20/FE" engine. **NOT actioned this session** (Nicolas: "maybe not for taking action right now");
   it's queued in Next Steps with the full conflict list.

## Accomplished

- **`fe-mechanic-map.yaml` — 93/93 `fe_mechanic` abilities mapped.** Validated: parses (ruby/psych),
  every key matches a real ability `id`, zero orphans, and all 23 `ITEM_*` + 6 `CA_*` enums
  referenced were confirmed to exist in the decomp headers.
- **`docs/fe-mechanic-map.md`** — schema, FE8 ID legend (hex + purpose), the **custom-engine backlog
  grouped by engine module** (this IS the Phase 1 work list, MVP-flagged per feature), the
  unmapped-ability gap list, and a ⚠ note on the combat-resolution dependency.
- **Notable clean vanilla mappings found:** Sleep→`ITEM_STAFF_SLEEP`, Nosferatu→`ITEM_DARK_NOSFERATU`,
  thunder-siege (Shatter/Call Lightning)→`ITEM_ANIMA_BOLTING`, summons→`CA_SUMMON`, Dance→`CA_REFRESHER`,
  crit-immunity→`ITEM_HOPLON_SHIELD`, hazard tiles→`ITEM_MINE`, walls→`ITEM_LIGHTRUNE`.

## Combat-Resolution Conflict — the concrete "list to update" (per Nicolas)

Everywhere that currently says combat is **hybrid d20** and that **d20 replaces FE hit math**:

- **docs/decisions.md** §Combat System (~L24–47): "Hybrid d20/FE combat replaces vanilla FE
  hit-rate math"; "Vanilla FE hit% and avoid stats are retired"; save DCs; crit = roll-twice;
  target hit rates 65–80%.
- **docs/PRD.md**: L14 (BG3 pitch, "d20 ... replace FE's vanilla hit-rate math"); L25 (goal:
  "visible d20 rolls against AC, advantage, saving throws"); **§6.5 L268–307** (full hybrid formula,
  "Attack Resolution (replaces FE's Hit%/Avoid)"); risks L525–527; **§14 Phase 1 milestone literally
  named "D20 Combat Works"**; GitHub issues **#7/#8/#10/#16/#17** (replace `BattleGenerateHitTriangle`,
  saving throws, d20 battle-anim UI).
- **docs/combat-formulas.md**: the **entire doc** is the hybrid d20/FE formula reference.
- **docs/rules-mapping.md §A**: "1d20 ... Replaces FE hit%/avoid entirely"; advantage; saves;
  crit-roll-twice. (NOTE: the rest of rules-mapping — bonus-action folding, summons, statuses,
  triangle, damage types — is unaffected and still good.)
- **PC YAMLs (×7)**: `d20_fields` (AC, prof_bonus), `save`/`save_dc`, advantage references — become
  flavor/no-ops if rules revert to vanilla FE.
- **fe-mechanic-map** d20-dependent features (`advantage_state`, saves, `auto_hit_multi_dart`,
  `reroll_self`, `ally_save_bonus_proc`) — already flagged in docs/fe-mechanic-map.md ⚠ section.

**Substantive questions the eventual rewrite must answer** (do NOT silently pick): does the d20
survive only as a crit animation? Do spell/staff **saves** keep an FE form (always-hit staves /
magic-vs-RES) or get dropped? Does **AC** vanish (back to FE hit/avoid) or stay as a renamed defense
stat? Do **advantage/disadvantage** drop or reflavor as FE support/terrain bonuses?

## Current State

- The PC roster is MVP-gated, dual-structured (`fe_mechanic`+`flavor`), and now has a concrete FE8
  reference layer. **Nothing committed yet this session** — working tree has 2 new files
  (`fe-mechanic-map.yaml`, `docs/fe-mechanic-map.md`) + this HANDOFF. Prior work is at `c28a9d6` on
  `origin/main`.

## Blockers

- **Combat-resolution direction must be ratified before Phase 1 engine work** — the entire Phase 1
  milestone is "D20 Combat Works" and issues #7–#17 build the d20 engine. If rules stay vanilla FE,
  that milestone + those issues need re-scoping. This is now the gating decision for engine code.
- **Build toolchain still NOT installed** (`devkitARM`, `agbcc`, `ColorzCore`, `libpng`). Don't
  install silently; confirm with Nicolas.
- **AoE→FE tension** still unsolved — D&D AoE compromised to "siege-range single-target"
  (`feature: siege_single_target` in the map). Confirm in playtesting or design a real FE AoE.
- **Signature moments still `tbd`** for Marty/Meesmickle/Rootis/Sclorbo (Nicolas to recall).

## Next Steps (priority order)

1. **Reconcile the combat-resolution docs** (the list above) to "vanilla FE rules, d20 as flavor
   only." Answer the 4 substantive questions first, then sweep decisions.md → PRD §6.5/§14/issues →
   combat-formulas.md → rules-mapping.md §A → strip/flag d20 fields in PC YAMLs.
2. **Map the remaining `fe_mechanic`-less abilities** (see docs/fe-mechanic-map.md §Unmapped):
   `rootis.dragon-wings`→Manakete transform, `prof-rbg.nimble-escape`→`CA_CANTO`,
   `prof-rbg.infuse-item`→`forge_command`, etc. Goal: 100 % ability coverage so the build can assert it.
3. **Scaffold `tools/build-campaign.ts`** to consume `fe-mechanic-map.yaml` + the PC YAMLs.
4. Re-evaluate [docs/party-balance.md](docs/party-balance.md) for MVP-only (Ch1–7, unpromoted).
5. Finalize magic items (`docs/magic-items.md` `[VERIFY]` rules text).
6. Brainstorm post-MVP Ch 8–20 outline.
7. Decide build deps; then Phase 1 (re-scoped per step 1).

## Key Files

- [campaigns/rime-of-the-frostmaiden/fe-mechanic-map.yaml](campaigns/rime-of-the-frostmaiden/fe-mechanic-map.yaml)
  — **NEW this session**; 93 `fe_mechanic` → FE8 reference entries, keyed `<pc>.<ability>`.
- [docs/fe-mechanic-map.md](docs/fe-mechanic-map.md) — **NEW**; schema, FE8 ID legend, custom-engine
  backlog (Phase 1 work list), unmapped gap, combat-resolution dependency note.
- [campaigns/rime-of-the-frostmaiden/pcs/*.yaml](campaigns/rime-of-the-frostmaiden/pcs/) — the 7
  curated PCs (dual structure + `unlock_chapter`); source of the `fe_mechanic` anchors.
- [docs/rules-mapping.md](docs/rules-mapping.md) — D&D→FE conversion spine (§A combat is now in conflict).
- [docs/decisions.md](docs/decisions.md) — settled decisions (§Combat System now outdated — see above).
- [docs/PRD.md](docs/PRD.md) — §6.5 combat formula + §14 roadmap/issues (both reference d20 combat).
- Decomp enums: `fireemblem8u/include/constants/items.h` (`ITEM_*`), `fireemblem8u/include/bmunit.h` (`CA_*`).
- Validate the map: `ruby -ryaml -e 'YAML.load_file("campaigns/rime-of-the-frostmaiden/fe-mechanic-map.yaml")'`
