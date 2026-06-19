# CLAUDE.md — Manchego Stars

Manchego Stars is a GBA tactics ROM hack of *Fire Emblem: The Sacred Stones* (FE8), built from the `fireemblem8u` C decompilation. It turns a completed D&D 5e *Rime of the Frostmaiden* campaign into a playable tactics game: 7 player characters become FE units (FE8 classes, FE8 stats), and the campaign's narrative chapters become FE maps. **Combat is vanilla FE8 — FE hit/avoid/might/crit, FE stats, no conversion.** D&D is flavor layered on top; the d20 survives only as a cosmetic nat-20 animation triggered by FE's own crit math. Distribution is private — pre-patched ROM sent to the campaign players.

## Source of Truth

The data is the doc — facts live in exactly one place, and indexes are generated (see
`docs/decisions.md` §Documentation Model):

| For… | Look at… |
|---|---|
| Per-chapter facts (objective, recruits, enemies, rewards) | `campaigns/rime-of-the-frostmaiden/chapters/ch*.yaml` → generated `docs/CHAPTERS.md` |
| Unit class / promotion | `campaigns/.../{pcs,npcs}/*.yaml` → generated `docs/CLASSES.md` |
| Settled design decisions (combat, triangle, economy, class mapping, promotion seam) | `docs/decisions.md` |
| Generic 5e→FE engine conversion | `docs/rules-mapping.md` |
| FE8 cadence/reward grounding | `docs/fe8-pacing-reference.md` |
| Post-MVP (Act II–V) plan | `docs/roadmap.md` |
| Vision / architecture / phased roadmap | `docs/PRD.md` |
| Work backlog | **GitHub issues** (milestones M0–M4) |

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
- Campaign data (`campaigns/rime-of-the-frostmaiden/`) is injected at build time by `tools/build_campaign.py`
- If you're about to hardcode "braulo" or "ch03" in a `.c` file — stop. It belongs in YAML.
- Code review rule: any C change that references a character by name, a chapter number, or a plot event is rejected

## Tracks & the engine/content seam

Work splits into a **content** track (`campaigns/**`, `tools/build_campaign.py` + art tools) and a
**pipeline** track (`tools/difficulty.py`, `fe_combat.py`, `check.py`, `playtest/**`, `build.sh`, CI).
Shared by both: `tools/inject/**`, `docs/**`, `HANDOFF*`, `CLAUDE.md`, `Makefile`. Rationale +
enforcement: `docs/decisions.md` → Seam enforcement (#55).

**This handoff/checklist routes by where you are** (run `git rev-parse --abbrev-ref HEAD`):
- On **`main`** (the primary `manchego-stars` checkout) → the integration/solo tree. Read `HANDOFF.md`.
  **No lane is enforced here** — edit anything; you're one person doing one thing at a time.
- On **`inst/content`** / **`inst/pipeline`** (a worktree, opened as its own VS Code folder) → you ARE
  that track. Read `HANDOFF-content.md` / `HANDOFF-pipeline.md` and stay in your lane:
  `check.py check_lane_ownership` (pre-commit + CI) blocks editing the *other* lane's files
  (`--no-verify` overrides). This is only needed when both instances run **at once** (two builds in one
  tree corrupt each other), so each concurrent instance gets its own `tools/worktree-setup.sh ../ms-<track>`
  worktree = its own VS Code window. Sequential work needs none of this — just use the main window.

Never commit the `fireemblem8u` submodule pointer.

## Working Conventions (Definition of Done)

Rationale and the long form: `docs/decisions.md` → Working Conventions. Every change:
- ships its **doc + YAML updates in the same commit** (no "update docs later");
- says `Closes #N` if it completes tracked work; open/retitle the issue if scope changes;
- builds `make` green, and passes `python3 tools/verify_text.py` after any text change;
- records a new non-obvious decision in `docs/decisions.md` (dated) — not only in chat/memory;
- never commits the `fireemblem8u` submodule pointer (our decomp edits are build artifacts).

Single source of truth: don't restate a fact that lives elsewhere — link to it. Keep this
file lean (operating instructions + pointers, not a fact store).

## Current State & Backlog

- **Where things stand right now** → `HANDOFF.md` (read at session start).
- **Work backlog & milestones (M0–M4)** → GitHub issues.
- **Phased roadmap & vision** → `docs/PRD.md §13`.

## Build / Inject / Verify Tools

| Tool | Role |
|---|---|
| `tools/build_campaign.py` | Inject campaign content (portraits, names, character class/stats) into the decomp before `make`. |
| `tools/verify_text.py` | Decode message text from the built ROM (regression gate; no mGBA). |
| `tools/playtest/run.sh win\|gameover\|retreat\|titlecard` | Automated in-emulator playtest of ch00 win/lose conditions + title-card capture (mGBA Lua scripting; memory-asserted PASS/FAIL). |
| `tools/portrait_tool.py`, `tools/ref_to_bust.py` | Bust art pipeline (ref → indexed FE8 portrait). |
| `tools/setup-toolchain.sh` | One-time macOS toolchain setup (brew deps, agbcc, python numpy/pillow/pyyaml). |

## Model Selection Guide

| Task | Model |
|---|---|
| Single C file edit (~200 LOC) | Sonnet (default) |
| Cross-cutting engine change (8+ files) | Opus with extended thinking |
| Generate dialogue, YAML, item descriptions | Haiku |
| ROM build smoke-test / mGBA memory reads | Script, no LLM |
