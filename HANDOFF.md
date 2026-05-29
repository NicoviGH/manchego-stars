# Handoff: Ch2 reworked to FE8 model + full doc-cleanup sweep

**Date:** 2026-05-29
**Session focus:** Continued the collaborative story/pacing walkthrough at **Ch2 "Cold Welcome"**, grounding the design in the **actual FE8 Ch2 "The Protected"** structure read from the decomp. Then made two cross-cutting decisions (the spell economy; the weapon triangle) and ran a **full docs/YAML cleanup** to remove every stale combat-system reference and band-aid scar.

## How Nicolas wants this work done (unchanged, important)

- **Story/pacing = collaborative, chapter by chapter** — lead with what FE8 does in that slot (read from the decomp, not memory), then our take, then discuss. (Memory: `feedback_collaborative_story_planning`.)
- **Always ground FE8 claims in the `fireemblem8u/` decomp**, never memory/community lore. (Memory: `manchego-stars-use-decomp`, new this session.)
- **Clean doc rewrites — no banners / "reverted on DATE" / strikethrough scar tissue.** Rewrite natively. (Memory: `feedback_clean_doc_rewrites`.)
- **Auto-push to main**; no need to ask. (Memory: `feedback_proactive-push`.)

## Settled this session (do NOT re-litigate)

- **Ch2 = FE8 "The Protected" model.** DefeatAll + **defend-in-place** (parked Rolling Cheddar sled = the protected objective the raid converges on; sled loss is a SOFT fail — forfeits the reward, not the chapter). Roster mirrors FE8's: ~6 trash + 1 named miniboss (Grukk) + 1 Steel-Axe boss (Halvar) + a turn-3 reinforcement pair from the **edge opposite the boss** (flank). The frost druid is a **cutscene seed only** (FE8 fields no enemy casters until ~Ch5–6; our first enemy caster is the Ch4 boss). `ch02-cold-welcome.yaml` fully rewritten.
- **Wolves = bandits = axe-brigand chassis** (same under the hood; sprite + flavor differ). Confirmed via decomp that the triangle is driven by weapon TYPE (`bmbattle.c sWeaponTriangleRules`) and monster claw/fang weapons are triangle-EXEMPT — so to keep the triangle arrow working, reskinned enemies use real FE weapon types (claws = axe), not monster weapons.
- **Decision B — the spell economy.** Every spell/cantrip is a finite-use FE tome that **depletes and is restocked with gold between chapters** (no free refill); cantrips are high-count (~30–50), not infinite. Casters share the FE gold/durability economy with martials → preserves FE's resource-management pillar. Innate per-rest pools (Rage, breath, Channel Divinity) still refill free; Pact slots = spell slots → decision B.
- **Weapon triangle stays FE-native** (Sword>Axe>Lance, Anima>Light>Dark). D&D damage-type names are **cosmetic per-weapon labels**, NOT a relabel of the triangle. The old "Slashing>Bludgeoning>Piercing / Radiant>Necrotic>Elemental" reskin is dropped.
- **Army composition is already FE-shaped** — don't reclass PCs; **tune enemies.** Cross-ref table + the **DEF/RES-mix rule** (every map mixes DEF-targets and RES-targets so our 3 offensive casters aren't a turkey-shoot vs low-RES mobs) are now in `party-balance.md §4`. Marty is the army's **Light** caster (corrected from an earlier "melee" error); Braulo=Axe, Wolfram=Lance, RBG=Bow, Meesmickle=Dark, Rootis=Anima, Sclorbo=support; Sword gap filled by NPCs (Trex/Baxby).
- **`fe8_base_map` field added to all 8 chapter YAMLs** — the FE8 map each chapter reskins (keep FE8's tuned layout/terrain/spawns, repaint to arctic). Ch1–6 align 1:1 with FE8 Ch1–6; **Ch7 uses FE8 Ch13 "Hamill Canyon"** (the FE8 Survive/terrain map) since our Ch7 is a Survive→scripted-loss. Confirmed by Nicolas (2026-05-29).

## Doc cleanup done this session (the "no stale docs" pass)

Swept clean across `docs/` + `campaigns/`:
- **Decision B propagated** (decisions.md, rules-mapping.md, class-progression-tables.md, PRD, combat-formulas.md, class-mapping.md, party-balance.md, PC YAMLs).
- **All hybrid-d20 language removed**, incl. `research.md` **fully de-d20'd** (§1, §2, §6.1–6.3, §6.8, §6.9, risks, next-steps) — it now presents vanilla FE as the approach.
- **Band-aid scar tissue removed** (dated "reverted/dropped 2026-05-28", strikethroughs, "(reverted)" parentheticals) — native rewrites everywhere. decisions.md keeps its dated `_Decided:` changelog footers (that's the doc's format, not scar tissue).
- **Engine module renamed** `engine/d20-combat/` → `engine/combat-fx/` everywhere (docs, fe-mechanic-map.yaml's ~30 refs, memory). No engine dir exists yet — doc-only.
- **"Rout" → correct FE8 objective** (FE8 has no Rout verb): campaign-brief Ch1/2/6 objectives + a ch06 prose comment.
- All 8 chapter YAMLs + edited PC YAMLs validate clean.

## Blockers / open

- **Ch3 is next** in the walkthrough (FE8 Ch3 "The Bandits of Borgo" = Seize big-battle; our Termalaine Mine multi-level gimmick).
- **Ch 8–20 plot still blocked on the rest of the DM notes** (the #1 unblock).
- **`weapon_dice` in PC YAMLs — intentionally left as source-of-record (reasoning settled 2026-05-29).** It's the 5e source die, treated like the `ac:`/`save_dc:` fields decisions.md keeps as source-of-record; the build pipeline (`build-campaign.ts`, not written) converts it to **fixed FE might** ("tuned from the die's average"). There is NO live contradiction — no doc claims rolled damage, and no `might:` field asserts a value yet. Assigning concrete might values is **downstream balance tuning** (Phase 1/2, needs enemy stat blocks + the build tool), not cleanup. Optional small clarity add still open: a one-line convention note ("weapon_dice = 5e source die → fixed might at build time") so it can't be misread as rolled damage.
- **GitHub is already clean** — milestone M1 is "D&D Combat Layer Works"; issues #7–#13 referenced in the PRD were never created (only #1–#6 exist). No GitHub action needed.
- Build toolchain still NOT installed (devkitARM/agbcc/ColorzCore/libpng).
- Open design Qs (chapter-outline.md §Open questions): main-lord PC (Braulo the pick), finale tone, Act II chapter budget, post-MVP Tower-of-Valni equivalent.

## Key files

- [campaigns/.../chapters/ch02-cold-welcome.yaml](campaigns/rime-of-the-frostmaiden/chapters/ch02-cold-welcome.yaml) — reworked to FE8 "The Protected".
- [docs/decisions.md](docs/decisions.md) §Combat / §Weapon & Magic — decision B + FE-native triangle.
- [docs/party-balance.md](docs/party-balance.md) §4 — army cross-ref + DEF/RES-mix rule.
- [docs/fe8-pacing-reference.md](docs/fe8-pacing-reference.md), [docs/chapter-outline.md](docs/chapter-outline.md) — cadence + 20-ch skeleton.
- FE8 ground truth: `fireemblem8u/src/events/<ch>-eventinfo.h` (objectives/villages), `src/events_udefs.c` (rosters), `src/bmbattle.c` (triangle), `include/bmitem.h` (`maxUses`).
- Validate campaign YAML: `ruby -ryaml -e 'YAML.load_file("<path>")'`
