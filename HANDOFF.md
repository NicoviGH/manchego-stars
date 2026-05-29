# Handoff: FE8-stats-only cleanup done; FE8 compliance audit IN PROGRESS

**Date:** 2026-05-29
**Session focus:** (1) Reworked Ch2 to the FE8 "The Protected" model + full docs/YAML cleanup to vanilla-FE + decision B (prior commits). (2) Sharpened to **FE8 stats AND mechanics only** and stripped the 5e combat-math apparatus everywhere. (3) STARTED an FE8 decomp-compliance audit of the PC files — **this is where the next session resumes.**

## How Nicolas wants this work done (standing rules)

- **FE8 mechanics AND FE8 stats only.** Combat = FE hit/avoid/might/FE crit. The d20 is **only** a cosmetic nat-20 animation triggered by FE crit math — nothing else. **No weapon dice, no 5e→FE stat conversion** (no STR→might, no DEX→SKL/SPD split, no ability-mod damage, no "tune from the 5e die's average"). PCs use FE8-class stats authored directly; the 5e `dnd:` sheet block is character flavor/source only. (Memory: `manchego-stars-combat-resolution`.)
- **Always ground FE8 claims in the `fireemblem8u/` decomp** (Memory: `manchego-stars-use-decomp`).
- **Collaborative, chapter-by-chapter** story work; **clean native doc rewrites** (no banners/strikethrough); **auto-push to main**.
- **Proactive handoffs / context hygiene** — run `/handoff` at task boundaries and long sessions; suggest `/clear` on task switches (Memory: `proactive-handoff-context-hygiene`, new this session). I can't see a live token counter, so this is best-effort; a `PreCompact` hook is the only true-automation backstop (offered, not yet set up).

## Accomplished this session (all committed + pushed)

- **`e6d18e3` — FE8 stats/mechanics only.** Stripped from all 7 PC YAMLs: every `weapon_dice`, per-weapon `ability_mod`, and the whole `d20_fields:` block (AC/prof_bonus/ability_mod_atk/spell_slots). The `dnd:` block stays as character source. Infinite-cantrip `uses` normalized (FE has no infinite weapons). Reframed **CLAUDE.md** (combat is vanilla FE8, not "d20 replaces hit-rate"; Phase 1 has no d20 engine), **rules-mapping.md §E** (author FE8 stats directly — no conversion formula), **§A damage** / **decisions.md** / **combat-formulas.md** / **research.md** (Might = FE weapon tier, never a 5e die), **PRD §10** (D&D sheets are flavor reference, not literal FE stat targets). All YAMLs validate.
- **`3914b05` / `196c0c9` (earlier):** Ch2 reworked to FE8 "The Protected"; `fe8_base_map` added to all 8 chapters; decision B (spell tomes deplete + gold-restock); FE-native triangle; army cross-ref + DEF/RES-mix rule in party-balance.md; all band-aid scar tissue + hybrid-d20 language purged; `engine/d20-combat` → `engine/combat-fx`; "Rout" → correct FE8 verbs.

## IN PROGRESS — FE8 compliance audit (resume here)

**Goal (Nicolas's ask):** use the decomp to compare each PC's FE stats/class to vanilla FE8 units and ensure compliance, so playtest doesn't break later.

**Done so far:** located the decomp data and learned the data layout —
- **`fireemblem8u/src/data_classes.c`** = class bases/caps/growths/MOV/CON/weapon-ranks, indexed `[CLASS_X - 1]`. Line numbers found: Knight (promotes→General, ~470), General `[CLASS_GENERAL-1]` @590, Archer @1402, Mage @2102, Sage @2214, Shaman @2572, Summoner @2808, Pirate @3780, Berserker @3837, Monk @3896. (Still need Dancer + Knight's own index line.)
- **`fireemblem8u/include/bmunit.h:61`** = `struct ClassData`. Field order: baseHP/Pow/Skl/Spd/Def/Res/Con/Mov (offsets 0B–12), then maxHP…maxCon (caps, 13–19), then growthHP/Pow/Skl/Spd/Def/Res/Lck (1B–21), promotion gains (22–27), `attributes` (28), `baseRanks[8]` (2C). Note FE uses **Pow** = our STR/MAG split; FE class data has one Pow (physical) — magic classes use the magic anim/rank, MAG is the unit's Pow-equivalent for tomes.
- **`fireemblem8u/src/data_characters.c`** = per-character bases/growths/affinity (the FE *unit* layer on top of class).

**Next steps for the audit (priority order):**
1. Read each MVP **base class** block in `data_classes.c` (Pirate, Knight, Archer, Mage, Shaman, Monk, Dancer) — record vanilla baseHP/Pow/Skl/Spd/Def/Res/Con/Mov, caps, growths.
2. Pull each PC's `fe_stats:` + `growth_rates:` from `campaigns/.../pcs/*.yaml` (Braulo=Pirate, Wolfram=Knight, RBG=Archer, Rootis=Mage(Ice), Meesmickle=Shaman, Marty=Monk, Sclorbo=Dancer).
3. Compare & flag: base class is a real FE8 class? base stats ≥ class bases and ≤ caps? MOV matches class (Knight 4, Mage/Archer 5, etc.)? CON sane? growths in FE-plausible range? weapon type matches class (Mage=Anima tome, Shaman=Dark, Monk=Light, Archer=Bow, Pirate=Axe, Knight=Lance)?
4. **MVP plays unpromoted**, so focus on base classes. Note: several *promoted* classes are intentionally CUSTOM (Artillerist for RBG, Lore Bishop for Sclorbo, "Dark Sage" for Meesmickle, custom Druid/Summoner for Marty) — flag them as custom (post-MVP), don't treat as vanilla.
5. Report findings; fix clear violations; bring judgment calls to Nicolas.

## Blockers / open

- **Ch 8–20 plot blocked on the rest of the DM notes** (the #1 unblock).
- **Story walkthrough is paused at Ch3** (FE8 Ch3 "The Bandits of Borgo", Seize big-battle / Termalaine Mine) — resume after the compliance audit, or per Nicolas.
- **`weapon_dice` → FE Might values not yet authored:** weapons need FE Might from FE item tiers (Iron/Steel/Silver) in an item table that doesn't exist yet — downstream authoring, not cleanup.
- Build toolchain still NOT installed (devkitARM/agbcc/ColorzCore/libpng).

## Key files

- PC YAMLs: `campaigns/rime-of-the-frostmaiden/pcs/*.yaml` (`fe_stats:` + `growth_rates:` blocks).
- Vanilla FE8: `fireemblem8u/src/data_classes.c`, `src/data_characters.c`, `include/bmunit.h:61` (ClassData struct).
- `docs/decisions.md` §Combat/§Weapon&Magic, `docs/rules-mapping.md` §E, `CLAUDE.md` — the FE8-stats-only canon.
- Validate campaign YAML: `ruby -ryaml -e 'YAML.load_file("<path>")'`
