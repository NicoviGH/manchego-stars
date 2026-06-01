# Handoff: Build toolchain INSTALLED & green on macOS (byte-identical vanilla ROM, reproducible `make`). NEXT = pixel-art pipeline, starting with portraits — but first prove the gbagfx round-trip so Nicolas can SEE what we're working with before committing to recolor-vs-custom.

**Date:** 2026-06-01
**Session focus:** Installed and verified the full FE8 decomp build toolchain on Apple Silicon macOS, made `make` reproducible with zero manual env, installed mGBA to view ROMs, and scoped a pixel-art backlog. All committed + pushed to main (HEAD `0f122eb`).

## Accomplished this session

- **Toolchain green end-to-end** (`0f122eb`): `make` from repo root → `fireemblem8u/fireemblem8.gba`, and `make verify` → **`fireemblem8.gba: OK`** (byte-identical to vanilla FE8). Proven in a *clean shell with no manual env vars*.
  - Installed via Homebrew: `arm-none-eabi-gcc` (binutils as/ld), `pkg-config`, `libpng`, `coreutils` (for `nproc`), `python@3.12`. Built **agbcc** from pret/agbcc into `fireemblem8u/tools/agbcc`. Installed numpy+pillow into the 3.12 interpreter. Copied `baserom.gba` into the decomp (gitignored).
  - **Three macOS gaps the decomp's quickstart.sh does NOT handle — now shimmed in the root `Makefile` (Darwin block) so plain `make` just works:**
    1. Apple **clang 21's** Command Line Tools `c++/v1` is incomplete (only 11 stale files) → `jsonproc` can't find `<cstdlib>`. Fix: Makefile exports `CPLUS_INCLUDE_PATH` from `$(xcrun --show-sdk-path)/usr/include/c++/v1` (the SDK has the full 193-file libc++).
    2. Several gfx scripts (`tsa2.py` etc.) use `match`/`case` → need **Python ≥3.10**, but system python3 is 3.9. Fix: Makefile prepends `python@3.1x/libexec/bin` to PATH.
    3. 19 scripts ship `#!/bin/python3` (absent on macOS; `/bin` is SIP-protected, can't symlink) → rewrote to `#!/usr/bin/env python3`. These live in the **submodule working tree**; reproduced by the setup script, so `fireemblem8u` stays on its upstream pin (do NOT commit a submodule pointer move for these).
  - Also fixed `make verify` target (`sha1.txt` → `checksum.sha1`).
  - **`tools/setup-toolchain.sh`** (new) codifies the whole one-time install idempotently for any fresh clone.
- **mGBA installed** (`/Applications/mGBA.app`, via `brew install --cask mgba`). View any build: `open -a /Applications/mGBA.app fireemblem8u/fireemblem8.gba`. Right now it boots **vanilla** FE8 — our campaign data isn't injected yet (that's the `build-campaign.ts` pipeline, issues #13–#15). The build proves the *engine*; content is next.
- **Pixel-art backlog scoped** (NOT yet created as issues — Nicolas to confirm). See Next Steps.
- Explained the **FEBuilder vs decomp** paradigm choice (already recorded in `decisions.md`/PRD §10): decomp is our spine (source-controlled, custom C, AI/Mac-friendly); FEBuilder is a side **escape hatch** for portrait validation + inspecting vanilla FE8, not the build system.

## Tried but didn't work (lessons for next time)

- First `make` died on `/bin/python3: bad interpreter` (Linux shebangs) → then on a 3.9 `match`/`case` SyntaxError → then on missing `<cstdlib>`. Each was a distinct macOS-vs-Linux gap; all three are now permanently shimmed, so this won't recur.
- **Could not auto-close GitHub issue #16** (toolchain) — the close was blocked by the permission classifier as an external write I didn't open this session. **#16 is DONE; Nicolas should close it manually** (or grant the gh permission).

## Current state

- **Build:** fully working + reproducible on macOS. `make` green, checksum matches vanilla. This is the Phase-0 "decomp builds clean / toolchain verified" milestone (M0) — effectively complete.
- **Content pipeline:** NOT started. `tools/build-campaign.ts` / `build-events.ts` still unbuilt (issues #13–#15). No campaign data is injected into the ROM yet.
- **Story:** all 9 MVP chapters (ch00–ch08) authored in YAML and walked through against the sources (prior sessions). Ch9–20 plot still blocked on the rest of the DM notes.

## Blockers / open

- **#16 needs manual close** (done, but classifier blocked the agent close).
- **Recolor-vs-custom portrait decision is NOT settled.** Nicolas leans recolor-first but is "not 100% sure" — wants to SEE what we're working with first. **Do Phase A (pipeline round-trip) before locking this in.**
- **Rootis & Sclorbo signature moments** still TBD (need Nicolas's recall) — carried over.
- **pepperjack/brie `fe_stats.class` = null** (FE-legal class TBD post-MVP).
- **Ch 9–20 plot** blocked on the rest of the DM notes.
- **Lingering lean candidates** (low priority): `docs/pc-spell-lists.md` / `docs/magic-items.md` → consume into YAML then delete.

## Next steps (priority order) — PIXEL ART

The plan is **recolor-first**, but Nicolas is undecided, so **step 1 is a visibility/proof step, not a commitment.** Golden rule throughout: **indexed-palette art only** (16 colors/slot, 8×8 tiles); generative tools (Nano Banana) are concept-ref only, never final assets. Tools: draw in **Aseprite** (indexed mode); validate/preview legality in **FEBuilder**; authoritative insertion is PNG → `gbagfx` → decomp.

1. **Phase A — prove the gbagfx round-trip (do this FIRST, ~throwaway).** Dump one vanilla FE8 portrait → tweak a few pixels → reinsert → see it in mGBA. This is what lets Nicolas "see what we're working with" and decide recolor-vs-custom with real constraints in front of him. Relevant scripts: `fireemblem8u/scripts/dump_portrait.py`, `gbagfx` (built at `fireemblem8u/tools/gbagfx`). Portraits are 96×80, one 16-color palette.
2. **Phase B — Portraits** (highest payoff): 7 PCs + key NPCs, recolor a matching vanilla base, one issue per PC, ordered by story appearance (**Braulo first** — he's the end-to-end test unit, issue #15). Refines existing coarse art issues #19 (PC+NPC portraits) and #35 (final pass). Portrait reference art (DDB avatars) listed in `data/pc-sheets/portraits.json`; some downloaded to `data/portraits/`.
3. **Phase C — Map sprites** (16×16 grid units): mostly *free* where a PC reuses a vanilla class; custom only where the look demands it.
4. **Phase D — Battle animations** (hardest): default to **reusing vanilla class anims** (zero art); custom anims = `stretch`/post-MVP.

**ACTION PENDING NICOLAS:** he was asked whether to (a) create the GitHub issues for this roadmap (Phase A + per-PC portrait issues under #19; C/D as `stretch`), or (b) write it into `docs/roadmap.md` first to edit the sequence. Awaiting his pick — do not create issues unprompted (external-write classifier will likely block anyway).

**Also flagged by Nicolas for "later":** an **architecture diagram** of the ROM hack (for his own learning). Not started; bring it up when he's ready.

## Key files

- `Makefile` (root) — macOS build shims live in the `ifeq ($(shell uname),Darwin)` block; `make` / `make verify` / `make clean`.
- `tools/setup-toolchain.sh` — one-time idempotent toolchain install for a fresh clone.
- `fireemblem8u/fireemblem8.gba` — the built ROM (gitignored). View: `open -a /Applications/mGBA.app <path>`.
- `fireemblem8u/scripts/dump_portrait.py`, `fireemblem8u/tools/gbagfx` — the portrait asset pipeline for Phase A.
- `data/pc-sheets/portraits.json` — PC portrait reference-art URLs; `data/portraits/*.jpeg` — downloaded refs.
- `docs/PRD.md` (§10 toolchain, §6 maps), `docs/decisions.md` — FEBuilder-vs-decomp rationale + settled decisions.

## Standing rules (how Nicolas wants this work done)

- **Stock vanilla FE8 classes/weapons only**; **element = flavor, NEVER a mechanic** (incl. effectiveness — that's keyed to enemy CLASS).
- **Ground FE claims in `fireemblem8u/`**; **ground STORY in the two PDFs** (DM notes Ch1–7 only + the published book). Read them directly when planning story.
- **Clean native doc rewrites** (no STALE/reverted banners). **Auto-push to main.** **Collaborative, chapter-by-chapter** story work. **Balance: defer to FE, lean generous.**
- **Doc source-of-truth:** per-chapter/unit facts live ONLY in YAML; `docs/CHAPTERS.md` + `CLASSES.md` are GENERATED (`ruby tools/gen-chapter-index.rb` + `gen-class-index.rb`, never hand-edit). **Lean repo**; backlog = **GitHub issues** (milestones M0–M4).
- **`make` must be green at the end of every session. Never commit a broken build.**
