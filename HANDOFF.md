# Handoff: Architecture split + weapon/promotion cleanup DONE; resume Ch3 story walkthrough

**Date:** 2026-05-30
**Session focus:** Finished the mechanics-vs-flavor architecture split, then resolved a cascade of FE-strictness cleanups (weapons → stock FE, promotions → vanilla branched, purged the leftover custom-ability/custom-class layer). Agreed an FE-community-driven balance philosophy. **Next session: resume the collaborative story walkthrough at Ch3.**

## Standing rules (how Nicolas wants this work done)

- **Stock vanilla FE8 classes, nothing extra.** Verbatim decomp class data (bases, growths, caps, MOV, CON, weapon ranks). No custom stats/abilities/procs/timed-buffs/special-movement.
- **Element = flavor text, NEVER a mechanic.** No damage-type resistance/immunity/vulnerability/keyed bonuses.
- **Individuality via flavor text + sprite/portrait art + palette**, not mechanics.
- **Ground every FE claim in `fireemblem8u/` decomp.** **Clean native doc rewrites** (no "STALE/reverted" banners). **Auto-push to main.** **Collaborative, chapter-by-chapter** story work.
- **Level design & balance: defer to FE-community convention** (Nicolas is not an FE expert). Balance via enemy/map design + recruits + the vanilla EXP curve — NOT per-unit stat parity. Lean generous (audience = the D&D friend group). See memory `feedback_fe-level-design`.

## Accomplished this session (all committed + pushed to main)

Commits: `39ed17e` → `7170d2c` → `17eb3f8` → `5d86cbb` → `91ccee5` → `9db125e` → `18d0819` → **`2668fc8` (HEAD)**.

- **Architecture split (`39ed17e`).** `lore/README.md` + `lore/<pc>.md` for all 7 PCs (generated from pre-strip `e6cc7a6` so the ability *fantasies* are preserved as flavor, with a "does not drive gameplay" banner). `npcs/pepperjack.yaml` + `npcs/brie.yaml` (recruitable stubs) + `lore/pepperjack-and-brie.md`. Slimmed RBG: `companion` block → lean `recruits:` pointers.
- **Pinky added (`7170d2c`).** `npcs/pinky.yaml` — RBG's homunculus "son" = the army's **flier**: stock vanilla **Pegasus Knight** (stats from `data_classes.c [CLASS_PEGASUS_KNIGHT]`). Plus `lore/pinky.md` (incl. the finale Wish beat).
- **`dnd:` block slimmed (`17eb3f8`).** All 7 PCs: the big `dnd:` block → a ~4-line pointer (race/class/subclass + links to the json source and lore file). FE stats don't derive from D&D, so the duplication is gone.
- **Promotions fixed to vanilla FE8 branched (`5d86cbb`).** The audit never re-checked `promoted_class`. Two were illegal: **Marty Monk→Summoner** (reclassed to **Shaman**, vanilla stats — his D&D Druid maps to FE8's real Druid class) and **Meesmickle Shaman→"Dark Sage"** ("Dark Sage" isn't an FE8 class). Every unit now has a `promotion: { branch: [A, B], default: X }` block (player chooses at the Master Seal), grounded in `classchg-data.c`. **Key clarification recorded:** stripping CUSTOM abilities ≠ dropping vanilla FE mechanics — vanilla class features (Berserker crit, **Summoner's Summon / CA_SUMMON**, Canto, flight) are KEPT.
- **MVP weapons → stock FE (`91ccee5` + `9db125e`).** Every weapon now has an `fe_base:` pointing at a vanilla FE8 item; **no custom Might anywhere** (resolves the old "Might TBD"). Physical weapons use stock names (Iron Axe, etc.); tomes keep an element-right flavor NAME but are mechanically the basic stock tome (Rootis "Ray of Frost"=Fire; Marty "Shillelagh"/Meesmickle "Eldritch Blast"=Flux; Sclorbo "Frostsong"/"Withering Impression"=Lightning). Personal/signature weapons deferred to post-MVP (e.g. Shipwrecker=Killer Axe), flavor parked in `lore/*.md` "Signature gear". `decisions.md` synced + its stale "Class Mapping" section rewritten natively.
- **Purged the custom-ability/custom-class layer (`18d0819` + `2668fc8`).** Deleted `fe-mechanic-map.yaml` + `docs/fe-mechanic-map.md` (they mapped the now-stripped abilities to custom_engine features). Remapped all `custom-*` enemy/boss classes to real FE8 monster classes: **Grell→Mogall, Vine Blight→Revenant, Messie→Draco Zombie, harrier fish→Gargoyle, Ice Troll→Cyclops.** Fixed the dangling doc pointers.

## Current state

- All 7 PC YAMLs + `npcs/` (pepperjack, brie, pinky) are **lean, stock-vanilla, valid YAML**. `dnd:` is a pointer; inventories are stock FE weapons with `fe_base`; promotions are branched.
- `lore/` holds all narrative/flavor (8 PC/automaton files + README + pinky), each marked flavor-only.
- Enemies across chapters use FE8 monster classes (no `custom-*` left).
- `decisions.md` is current (stock-weapon rule, branched promotions, custom-vs-vanilla clarification, magic-triangle caster spread). Balance philosophy saved to memory.

## Blockers / open

- **Story walkthrough paused at Ch3** (FE8 "The Bandits of Borgo" / Termalaine Mine) — **THIS IS THE NEXT TASK.** Resume collaboratively (FE8 parallel + our version), now also choosing each map's enemy mix per the FE level-design lens. Ch3 YAML is already richly drafted (kobolds=brigand, Grells=Mogall mini-bosses, RBG+Wolfram signature beats, first stat-booster behind the Grells, recruit Trex post-map).
- **PRD.md §6.7 class-mapping table is STALE** — still lists removed per-PC abilities (Forge, Feral Strike, Shield spell, Mystic Arcanums, AC values, "spell access secondary"). Needs a native rewrite like the `decisions.md` section got (deferred this session to avoid scope creep; flagged verbally to Nicolas). PRD/research may have other custom-ability remnants worth a sweep.
- **Signature moments TBD** for Marty, Meesmickle, Rootis, Sclorbo (Nicolas to recall; not in DM notes).
- **pepperjack/brie `fe_stats.class` = null** (FE-legal class TBD post-MVP). Pinky is fully statted.
- **Ch 8–20 plot blocked on the rest of the DM notes** (cover Ch1–7 only) — fine, it's post-MVP.
- **Build toolchain still NOT installed** (devkitARM/agbcc/ColorzCore/libpng) — gates any actual ROM build/test.

## Next steps (priority order)

1. **Resume the Ch3 story walkthrough** (collaborative, FE8 parallel + our version), choosing the enemy mix/objective/pacing through the FE level-design lens. Then continue Ch4→Ch7.
2. (Opportunistic) Native rewrite of the **PRD.md §6.7** class-mapping table to current stock-vanilla reality.
3. (When recalled) Fill in **signature moments** for Marty/Meesmickle/Rootis/Sclorbo.

## Key files

- PC unit YAMLs: `campaigns/rime-of-the-frostmaiden/pcs/*.yaml` (lean: pointer `dnd:`, `fe_base` inventories, branched `promotion:`).
- Recruit units: `campaigns/rime-of-the-frostmaiden/npcs/{pepperjack,brie,pinky}.yaml`.
- Flavor: `campaigns/rime-of-the-frostmaiden/lore/*.md` (8 files + README).
- Chapters: `campaigns/rime-of-the-frostmaiden/chapters/ch0X-*.yaml` (enemies use FE8 monster classes).
- Vanilla FE8 reference: `fireemblem8u/src/data_classes.c` (class data, `[CLASS_X - 1]`); `fireemblem8u/src/classchg-data.c` (promotion branches); `fireemblem8u/src/data_items.c` (weapon Mt/Hit/uses); `fireemblem8u/texts/texts.txt` (item/class names).
- Canon docs: `CLAUDE.md`, `docs/decisions.md`, `docs/chapter-outline.md`, `docs/fe8-pacing-reference.md`, `docs/PRD.md` (§6.7 table stale), `docs/rules-mapping.md`.
- Validate YAML: `ruby -ryaml -e 'YAML.load_file("<path>")'` (pyyaml not installed; use Ruby).
