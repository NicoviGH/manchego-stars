# Handoff: PC PDF Cross-Reference + Party Balance Audit

**Date:** 2026-05-27
**Session Focus:** Cross-reference all 7 PC D&D Beyond PDF sheets against YAMLs, fix mechanical discrepancies, and produce an FE party balance evaluation.

---

## Accomplished

- **Cross-referenced all 7 PC PDFs** (`References/PCs/*.pdf`) against the YAMLs in `campaigns/rime-of-the-frostmaiden/pcs/*.yaml`. Findings are documented at the bottom of [docs/party-balance.md](docs/party-balance.md).
- **Applied critical mechanical corrections to all 7 PC YAMLs.** Most impactful:
  - **Wolfram** Breath Weapon was listed as unlimited per chapter; PDF p3 explicitly says **1/short rest** → corrected to 1/chapter. This was a major balance bug.
  - **Meesmickle** Pact Magic listed only 2 slots; PDF spell page confirms **4 slots at 5th level** (standard Warlock 20).
  - **Rootis** AC was claimed "flat 17"; PDF p2 says **AC = 13 + DEX mod when unarmored** (scales with DEX, not flat).
  - **Sclorbo** healer identity was missing — PDF p5 confirms he has **Cure Wounds, Revivify, Mass Cure Wounds, and Raise Dead** all prepared. Added `bard-healing-suite` progression note and `heal-staff` Ch1 inventory item.
- **Added missing features per PDF:**
  - Wolfram: Investiture of Stone (6th Arcanum), Forcecage (7th), Feral Strike Claws, Fire Bolt cantrip
  - Meesmickle: Power Word Kill (9th), Demiplane (8th), Eldritch Blast 4-beam end-state note
  - Rootis: Distant + Extended Spell metamagic, Sorcerous Restoration, Draconic Presence, Chill Touch cantrip
  - Braulo: Reckless Attack, Mindless Rage, Danger Sense, Feral Instinct (core Barbarian features)
  - RBG: Shocking Grasp cantrip; Arcane Firearm description corrected to per-spell not per-turn
- **Background/flavor fixes:** Braulo background corrected from `Merchant` to `Custom Background`; Sclorbo Ideal text corrected to match PDF; Rootis Bond confirmed blank per PDF; `languages` field added to all 7 YAMLs.
- **Wrote `docs/party-balance.md`** — comprehensive evaluation of the 7 PCs + 5 NPCs vs typical FE mid-game roster. Includes role-coverage matrix, recommended Ch1 loadouts, and 6 open questions for Phase 1 playtesting.
- **Committed and pushed** as `c98650f` to `origin/main` (also pushed the prior `f8de957` portraits commit that was stale on local).

## Tried But Didn't Work

- **Initial git push was blocked twice** by the Claude Code auto-mode classifier because it doesn't auto-approve pushes to `main`. Resolved by re-issuing the command and approving via permission prompt. If you want this to stop happening, add a `Bash(git push:*)` allow rule via `/update-config`.
- **Python yaml validation** failed (no `pyyaml` installed); used Ruby's bundled YAML library instead to confirm all 7 YAMLs parse cleanly.

## Current State

- **All 7 PC YAMLs are clean, validated, and reflect their D&D Beyond PDF sheets accurately** for mechanically relevant fields.
- **Party balance is documented** with explicit gaps identified (no PC healer until Sclorbo fills it, no PC flier at base except Rootis Dragon Wings toggle, no PC thief until Trex Ch3, no Radiant magic in PCs).
- **Repo is `origin/main`-clean**, working tree clean.
- **Phase 1 (Engine Core) is the next phase** per `docs/PRD.md §14`; starting point is issue #7: `engine/d20-combat/dice_rng.c` — Roll() wrapper around FE8's `bmRng.c`.
- **Build dependencies still NOT INSTALLED** — `devkitARM`, `agbcc`, `ColorzCore`, `libpng`. Required before `make` can produce a ROM. Per project memory: install via `cd fireemblem8u && ./scripts/quickstart.sh --rom "<base ROM path>"` but only when Nicolas is ready (don't install silently).

## Blockers

- **Build toolchain not installed** — blocks any actual engine code from being compiled/tested. Need Nicolas's go-ahead before installing.
- **6 open questions from balance analysis** (see [docs/party-balance.md](docs/party-balance.md) §"Open Questions for Phase 1 Playtesting"). These can't be answered without a working ROM build. Key examples:
  - Is Wolfram playable at SPD 3 (doubled by everything)?
  - Does Sclorbo's heal-staff suffice as primary healing pre-Basil (Ch4)?
  - Should Sclorbo's promoted class be `Valkyrie / Sage` rather than `Lore Bard`?
- **Signature moments TBD** for Marty, Meesmickle, Rootis, Sclorbo — Nicolas needs to recall (see `docs/decisions.md` Open Questions section). Currently `signature_moment.chapter: tbd` in their YAMLs.

## Next Steps

1. **Decide whether to install build deps now** (`devkitARM`, `agbcc`, ColorzCore, libpng) so Phase 1 engine code can actually compile/run. Or defer until needed.
2. **Start issue #7** — `engine/d20-combat/dice_rng.c`. Wrap FE8's `bmRng.c` (in `fireemblem8u/src/`) with a `Roll(dice, sides, advantage_state)` function. This is the foundation for the entire d20 combat system.
3. **Resolve signature moments** for Marty / Meesmickle / Rootis / Sclorbo — quick conversation with Nicolas, then update those YAMLs.
4. **Audit class-mapping.md** vs the new balance findings — particularly whether Sclorbo's promoted class should change to reflect his healer kit.
5. **Phase 1 GitHub issues #7–#13** per PRD §16 — dice RNG, AC/saving-throw stats, damage-type bitmap, etc.

## Key Files

- [docs/PRD.md](docs/PRD.md) — source of truth for architecture, combat formulas, class mapping, chapter breakdown, issue backlog (read first every session)
- [CLAUDE.md](CLAUDE.md) — session checklist, conventions, engine/content boundary rule
- [docs/decisions.md](docs/decisions.md) — settled design decisions (don't re-litigate)
- [docs/party-balance.md](docs/party-balance.md) — **NEW this session**; roster vs typical FE composition, PDF cross-reference audit table at the bottom
- [docs/class-mapping.md](docs/class-mapping.md) — 5e→FE class mappings (may need update post-balance-audit)
- [docs/combat-formulas.md](docs/combat-formulas.md) — d20/FE hybrid combat reference
- [campaigns/rime-of-the-frostmaiden/pcs/*.yaml](campaigns/rime-of-the-frostmaiden/pcs/) — 7 PC YAMLs, all updated this session
- [data/pc-sheets/*.json](data/pc-sheets/) — original D&D Beyond JSON exports (unchanged)
- `References/PCs/*.pdf` (in `/Users/Yonick/Documents/Claude/Projects/Manchego Stars / Fire Emblem Game/References/PCs/`) — source PDF sheets used for cross-reference
- [fireemblem8u/src/bmRng.c](fireemblem8u/src/bmRng.c) — FE8 RNG to wrap for Phase 1 issue #7
