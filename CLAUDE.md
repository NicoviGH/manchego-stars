# CLAUDE.md — Manchego Stars

Manchego Stars is a GBA tactics ROM hack of *Fire Emblem: The Sacred Stones* (FE8), built from the `fireemblem8u` C decompilation. It turns a completed D&D 5e *Rime of the Frostmaiden* campaign into a playable tactics game: 8 player characters become FE units (FE8 classes, FE8 stats), and the campaign's narrative chapters become FE maps. **Combat is vanilla FE8 — FE hit/avoid/might/crit, FE stats, no conversion.** D&D is flavor layered on top; the d20 survives only as a cosmetic nat-20 animation triggered by FE's own crit math. Distribution is private — pre-patched ROM sent to the campaign players.

## Source of Truth

The data is the doc — facts live in exactly one place, and indexes are generated (see
`docs/decisions.md` §Documentation Model):

| For… | Look at… |
|---|---|
| Per-chapter facts (objective, recruits, enemies, rewards) | `campaigns/rime-of-the-frostmaiden/chapters/ch*.yaml` → generated `docs/CHAPTERS.md` |
| Unit class / promotion | `campaigns/.../{pcs,npcs}/*.yaml` → generated `docs/CLASSES.md` |
| Settled design decisions (combat, triangle, economy, class mapping, promotion seam) | `docs/decisions.md` |
| Generic 5e→FE engine conversion | `docs/rules-mapping.md` |
| Adding a unit's art / battle anim / platform | the **`inject_battle_anims` / `inject_battle_platforms` docstrings** (how) + `decisions.md` Art & Audio (why) + the **`custom_unit` issue template** (checklist) |
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
| Engine hooks (decomp string-patches) | `tools/inject/engine_hooks.py` (+ `tools/inject/decomp.py`) |
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
- New engine behavior ships as string-patch hooks in `tools/inject/engine_hooks.py` — never hand-edits
  to `fireemblem8u/src/` (our decomp edits are build artifacts, restored on every build)

## Engine / Content Boundary Rule

> **If it references a character name, chapter number, or plot event, it goes in YAML, not C.**

- Engine code (`engine/`, `fireemblem8u/src/`) must be campaign-agnostic
- Campaign data (`campaigns/rime-of-the-frostmaiden/`) is injected at build time by `tools/build_campaign.py`
- If you're about to hardcode "braulo" or "ch03" in a `.c` file — stop. It belongs in YAML.
- Enforced: `check.py check_engine_campaign_agnostic` (CI + pre-commit) scans the hand-written engine sources (`engine/**`, `tools/inject/engine_hooks.py`, `decomp.py`) for any campaign character id and rejects it. (Chapter-number / plot-event references stay a review-judgment call.)

## Coordination: feature-flow (one feature, one branch, one PR)

Rationale + long form: `docs/decisions.md` → Coordination model. The operating rules:
- A task = a GitHub issue → short-lived `feat/<n>-slug` branch off `main` → PR → CI + `/code-review`
  → squash-merge → delete the branch. A feature may span engine + content — ownership lives on the
  PR + issue, not a file glob.
- **Concurrent agents each get their own worktree** (two ROM builds in one tree corrupt each other;
  a single writer may work the provisioned main tree — see `HANDOFF.md`).
- **Engine/content invariant is a HARD gate** (the Boundary Rule above + the 5 engine hooks in
  `tools/inject/`, guarded by `check.py check_engine_guards_present`). Desk ownership is a review
  judgment (`check_lane_ownership` is advisory).
- Never commit the `fireemblem8u` submodule pointer.

## Design placement test ("not my job" / "no need to know")

Long form + examples: `docs/decisions.md` → Coordination model. In brief (Cockburn): push each line
to the desk that owns it; talk over interfaces, never reach into another module's private state; judge
a boundary by which *named* future changes it makes cheap (don't refactor for futures you can't name —
e.g. `harness.lua` stays whole; its only likely change is "add a scenario").
**Code-review rule:** a change that reaches into another desk's cabinet or scatters one decision
across desks is rejected; localize the decision first.

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
