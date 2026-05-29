# CLAUDE.md — Manchego Stars

Manchego Stars is a GBA tactics ROM hack of *Fire Emblem: The Sacred Stones* (FE8), built from the `fireemblem8u` C decompilation. It turns a completed D&D 5e *Rime of the Frostmaiden* campaign into a playable tactics game: 7 player characters become FE units (FE8 classes, FE8 stats), and the campaign's narrative chapters become FE maps. **Combat is vanilla FE8 — FE hit/avoid/might/crit, FE stats, no conversion.** D&D is flavor layered on top; the d20 survives only as a cosmetic nat-20 animation triggered by FE's own crit math. Distribution is private — pre-patched ROM sent to the campaign players.

## Source of Truth

**`docs/PRD.md`** — read this before any session. It covers architecture (§6), combat formulas (§6.5–6.8), class mappings (§6.7), the full chapter breakdown (§7), GitHub issues (§16), and the roadmap (§14).

## Session Start Checklist

Read these at the top of every session before touching code:
1. `CLAUDE.md` (this file)
2. `HANDOFF.md` (project root, if it exists) — most recent session's state, blockers, and next steps
3. `docs/decisions.md` — settled design decisions, do not re-litigate
4. The current chapter or feature YAML/source file being worked on
5. `git status` + `git log --oneline -10`

## Key File Locations

| What | Where |
|---|---|
| Base ROM | `/Users/Yonick/Documents/Claude/Projects/Manchego Stars / Fire Emblem Game/Fire Emblem - The Sacred Stones (USA, Australia).gba` |
| Reference PDFs (Tasha's, Metallurgist, etc.) | `/Users/Yonick/Documents/Claude/Projects/Manchego Stars / Fire Emblem Game/References/` (PDFs + frostmaiden-resources.md live here in the source folder; frostmaiden-resources.md is also copied to `docs/`) |
| PC D&D Beyond JSON sheets | `data/pc-sheets/*.json` |
| PC portrait URLs | `data/pc-sheets/portraits.json` |
| FE8 decomp | `fireemblem8u/` (git submodule) |
| Engine patches | `engine/` |
| Campaign data | `campaigns/rime-of-the-frostmaiden/` |
| Planning docs | `docs/` |

## Build Command

```sh
make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba -j$(nproc)
```

The decomp's own quickstart (to verify the base ROM builds clean):
```sh
cd fireemblem8u
./scripts/quickstart.sh --rom "/Users/Yonick/Documents/Claude/Projects/Manchego Stars / Fire Emblem Game/Fire Emblem - The Sacred Stones (USA, Australia).gba"
```

**`make` must be green at the end of every session. Never commit a broken build.**

## Coding Conventions

- Follow existing decomp C style throughout — GCC 2.95.1 / `agbcc`
- No C99 features: no VLAs, no `//` comments in new C files (use `/* */`), no designated initializers (`.field = value`)
- No `stdint.h` types in engine files — use the decomp's existing typedefs (`u8`, `u16`, `u32`, `s8`, `s16`, `s32`)
- Match the existing file and function naming conventions in `fireemblem8u/src/`
- New engine modules go in `engine/`, not directly in `fireemblem8u/src/`

## Engine / Content Boundary Rule

> **If it references a character name, chapter number, or plot event, it goes in YAML, not C.**

- Engine code (`engine/`, `fireemblem8u/src/`) must be campaign-agnostic
- Campaign data (`campaigns/rime-of-the-frostmaiden/`) is injected at build time by `tools/build-campaign.ts`
- If you're about to hardcode "braulo" or "ch03" in a `.c` file — stop. It belongs in YAML.
- Code review rule: any C change that references a character by name, a chapter number, or a plot event is rejected

## Phase Status

- **Phase 0: Foundation** — current phase (repo scaffold, decomp builds clean)
- **Phase 1: Engine Core** — D&D flavor layer on vanilla FE combat: damage-type labels, the spell-tome/gold economy, a cosmetic nat-20 crit flourish (no d20 resolution engine, no AC, no saves)
- **Phase 2: Content Pipeline** — build-campaign.ts, Braulo end-to-end
- **Phase 3: MVP Content** — all 7 chapters playable
- **Phase 4: Polish & Ship** — distribute to the group

See `docs/PRD.md §14` for full roadmap and `§16` for the GitHub issue backlog.

## Model Selection Guide

| Task | Model |
|---|---|
| Single C file edit (~200 LOC) | Sonnet (default) |
| Cross-cutting engine change (8+ files) | Opus with extended thinking |
| Generate dialogue, YAML, item descriptions | Haiku |
| ROM build smoke-test / mGBA memory reads | Script, no LLM |
