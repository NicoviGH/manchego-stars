# Handoff: RESET POINT — Milestone B (content pipeline) to be REDONE from scratch. Milestone A (portrait injection) is committed and good. This session attempted B (names/stats/test-chapter), hit two real bugs (Huffman text corruption + malformed event script), and is being rolled back to a clean Milestone-A baseline. Below: what works, what broke + root causes, the validated decomp injection points, and the careful fresh-start plan.

**Date:** 2026-06-04
**Decision (Nicolas):** undo the Milestone B work done while on Sonnet; re-scope against the plan + decomp; start fresh, incrementally, verifying each step in mGBA before adding the next.

## WHAT WORKS — keep (committed)
- **Milestone A portrait injection** (`tools/build_campaign.py` portrait path) — 10 busts → vanilla portrait slots, STATIC, facing-correct, flat refs. Committed (`95d46c9`, `8fc46cb`, `d50fa35`, `b5b48e6`). `make` shows the right faces in mGBA. **This is the baseline to build on.**
- **portraitId mapping (validated this session):** the engine resolves `portrait_data[portraitId-1]`, and the table has DUPLICATE blink entries, so `portraitId` in `gCharacterData` must be the VANILLA character's value, NOT the raw `portrait_data` index. Vanilla values for our slots: Eirika 0x2, Seth 0x4, Gilliam 0x5, Franz 0x6, Moulder 0x7, Vanessa 0x8, Ross 0x9, Neimi 0xa, Colm 0xc, Garcia 0xe. With these, portraits line up perfectly in-game (verified at ROM level AND on screen).
- **gCharacterData patching (stats/class) worked in-game** — units showed correct class + stats. Only the NAME (text) was broken (see below). The `[CHARACTER_X - 1] = {…}` brace-counting replacement in `patch_character_data` is sound.

## WHAT BROKE — root causes (the reason for the reset)
1. **Huffman TEXT corruption (the big one).** Injecting unit names by editing `texts/texts.txt` and letting the decomp recompress is producing a **Huffman tree ↔ compressed-data mismatch**: every custom message decodes to runaway garbage in-game ("Wolfram as e", "oi. ee?", black boxes). Confirmed by decoding the ROM's `gMsgTable`/`gMsgHuffmanTable` directly — messages never hit their terminator. `scripts/texttools/textprocess.py` rebuilds the tree from `GenerateFreqTable` every run and writes BOTH tree + data into `src/msg_data.c`; in principle consistent, but in practice our edit+rebuild path yields a mismatch **even on a full `make clean` build**. `texts.txt` itself is structurally perfect (verified: each `## MSG_xxx` → `Name[X]` 1:1), so the corruption is in the recompression/build, not the source. **THIS MUST BE SOLVED FIRST in the redo — in isolation, before any chapter work.**
2. **Malformed test-chapter event script (B3).** The hand-written prologue beginning-scene (`generate_test_chapter`) used event opcodes (TEXTSHOW/FlashCursor/FADU/etc.) that misbehaved — gibberish cutscene text + black text windows — and may have compounded the text corruption. Hand-authoring FE8 event bytecode from scratch is error-prone. Also: **the Prologue is a bad test bed** (heavy tutorial special-casing, forced lord, auto-suspend to `.sav`).
3. **Process pain (not code bugs, but cost hours):** (a) incremental builds desync the decomp's dep tracking when `build_campaign.py` rewrites source each build — stale `.o`/`.dep`/text; (b) `open -a mGBA <rom>` does NOT swap the ROM on a running instance — you keep seeing the OLD build. See Build Hygiene below.

## VALIDATED DECOMP INJECTION POINTS (re-confirmed this session)
| Data | File(s) | Notes |
|---|---|---|
| Character stats/class/growth/portraitId/affinity | `src/data_characters.c` `gCharacterData[]` | Works. portraitId = vanilla value (see above). affinity is cosmetic; default Anima. |
| Portrait graphics | `graphics/portrait/portrait_<Slot>_*` (+ `src/portrait_data.c`, `data/data_portrait.s`) | Milestone A. Works. `portrait_tool.generate(static_portrait=True)`. |
| **Unit names / dialogue text** | `texts/texts.txt` → `scripts/texttools/textprocess.py` → `src/msg_data.c` (gMsgTable + gMsgHuffmanTable) | **FRAGILE — current corruption source.** |
| Chapter: units/placement/events | `src/events/<ch>-event{udefs,script,info}.h` (`ChapterEventGroup`, `REDA`/`UnitDefinition`, `EventListScr`) → included by `events_script.c`/`events_info.c`/`events_udefs.c` | Hand-writing scripts = error-prone. Prefer copying a known-good chapter and minimally editing. |

## FRESH-START PLAN (do in this order; verify EACH in mGBA before the next)
0. **Clean baseline:** repo is rolled back to Milestone-A-only (this handoff commit). `make` builds the portraits-only ROM, faces correct, vanilla everything else. Confirm that still works first.
1. **SOLVE TEXT IN ISOLATION.** Change ONE vanilla name (e.g. Eirika→"Braulo") via the smallest possible mechanism, `make clean`, launch, and confirm it renders cleanly on the **stock prologue**. Do not move on until a single name is reliably clean across rebuilds. Investigate `textprocess.py` determinism / whether the tree+data in `msg_data.c` actually match (decode `gMsgTable[id]` with `gMsgHuffmanTable`). If the standard path can't be made reliable, consider alternatives (shorter custom text, or a different name-storage hook). Names must be ≤12 chars — use the `fe_name` concept (see memory).
2. **Characters:** re-apply `gCharacterData` patching (stats/class/portraitId-vanilla/affinity-Anima). Verify class+stats+portrait+NAME all correct for a stock-prologue unit.
3. **Test chapter:** use a NORMAL chapter (ch1), and build its event data by COPYING the vanilla chapter's `-event*.h` and minimally editing unit defs — do not hand-write the beginning scene from scratch. Spawn the cast, verify all 10 line up.

## BUILD HYGIENE (learned the hard way)
- **Always clean-build the campaign** until deps are made robust: `make clean && make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba`. Incremental builds desync (stale `.dep` referencing deleted generated files; text not recompressing in step). A future improvement: have the Makefile/`build_campaign.py` force-remove the objects it regenerates.
- **Load the ROM properly:** `pkill -9 -i mgba; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &`. `open -a mGBA` refocuses the old instance without reloading.
- **Fresh New Game:** `rm fireemblem8u/fireemblem8.sav` (FE8 auto-suspends; stale saves load old unit data).
- **Verify which build is running:** decode `gCharacterData`/`gMsgTable` from the ROM via the `.map`, or drop a marker via a YAML field (NOT a manual `texts.txt` edit — `make` runs `build_campaign.py` first and overwrites manual decomp edits).
- **`make` no longer matches vanilla sha1** (we diverge on purpose) — build the decomp `fireemblem8.gba` target, not its `compare` goal. Restore vanilla: `git -C fireemblem8u checkout <path>`.

## KEY FILES
- `tools/build_campaign.py` — rolled back to Milestone A (portrait injection only) at this reset. Milestone B logic to be re-added per the plan.
- `tools/portrait_tool.py` — `generate(static_portrait=True)`, `--static`. Unchanged, good.
- `tools/ref_to_bust.py` — `--flip-h` for facing. Good.
- `campaigns/.../{pcs,npcs}/*.yaml` — unit data (stats, class, `art.render`, facing). Long names need an `fe_name` (≤12).
- decomp (`fireemblem8u/`) — submodule; our edits are uncommitted build artifacts. Don't commit the submodule pointer.

## MEMORY (read these — they encode this session's hard-won lessons)
- [[feedback_fe_name_truncation]] — proactively short `fe_name` for long names.
- [[project_manchego_stars_portrait_pipeline]] — portraitId-1 gotcha, mGBA loading gotcha, static portraits, facing.
- [[feedback_portrait_static_no_animation]] — static busts.

## STANDING RULES (unchanged)
Custom art for the 10 named cast; enemies vanilla. Stock FE8 classes/weapons; combat = vanilla FE; element = flavor. `make` green at session end. Auto-push to main once approved. Don't commit the fireemblem8u submodule pointer.
