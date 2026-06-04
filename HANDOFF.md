# Handoff: TEXT PATH PROVEN — the Milestone B "Huffman corruption" was a stale-build ghost, not a pipeline bug. A single name change clean-builds and decodes perfectly out of the ROM. Next: re-add gCharacterData injection (stats/class/name from YAML), then a copied test chapter.

**Date:** 2026-06-04
**This session:** Re-investigated the text blocker from the reset. Proved — at the ROM level — that the FE8 Huffman text pipeline is correct. Changed one vanilla name (Eirika→Braulo), `make clean && make`, decoded the built ROM: `MSG_212` → `Braulo`, and a full sweep of all 3404 messages shows **0 runaway / 0 corruption**. Added `tools/verify_text.py` so text can be verified without mGBA. Reverted the throwaway name edit (real names come from YAML, per the boundary rule).

## WHAT WORKS — keep (committed)
- **Milestone A portrait injection** (`tools/build_campaign.py`, portraits-only) — 10 busts → vanilla slots, static, facing-correct. Baseline. `make` builds, faces correct.
- **portraitId = vanilla character value** (engine resolves `portrait_data[portraitId-1]`, table has dup blink entries). Slots: Eirika 0x2, Seth 0x4, Gilliam 0x5, Franz 0x6, Moulder 0x7, Vanessa 0x8, Ross 0x9, Neimi 0xa, Colm 0xc, Garcia 0xe.
- **TEXT PATH (proven this session).** `texts/texts.txt` → `scripts/texttools/textprocess.py` → `src/msg_data.c` (gMsgTable + gMsgHuffmanTable) → ROM. Edit a message, `make clean && make`, and it decodes cleanly in the ROM. **This is no longer a blocker.**

## THE "HUFFMAN CORRUPTION" WAS A BUILD-HYGIENE GHOST
The reset blamed a Huffman tree↔data mismatch. It is not a pipeline bug:
- A pure-Python round-trip of `textprocess.py` + `huffman.py` (compress with `build_code_table`, decode with the emitted `gMsgHuffmanTable` using the game's own algorithm from `textdecoder.py`) is **0 fails / 3404** on stock text AND with Eirika→Braulo.
- A real `make clean && make` with the name change, then decoding the built ROM by `.map` symbol address: `MSG_212` = `Braulo`, terminates correctly; **full-ROM sweep = 0 runaway / 3404**.
- Root cause of the earlier garbage: stale/partial builds (incremental dep desync; the `open -a mGBA` reload trap loading an old ROM). The pipeline writes tree+data in one pass, so a *clean* build is always internally consistent.
- The `all_nodes.index()` value-equality concern (`HuffNode.__eq__` overridden) is harmless in practice — if it produced wrong indices the round-trip would fail, and it doesn't.

## REGRESSION TOOL (new this session)
- **`tools/verify_text.py`** — decodes message text straight out of the built ROM (reads `gMsgHuffmanTable`/`gMsgTable`/`gMsgHuffmanTableRoot` by `.map` symbol, reproduces the game's Huffman decoder). No mGBA needed.
  - `tools/verify_text.py` → sweep all messages, nonzero exit if any runs away.
  - `tools/verify_text.py 0x212 0x004` → decode specific message indices.
  - **Make this the gate after any text change**: build, then `verify_text.py`. Clean sweep = text is good.

## VALIDATED DECOMP INJECTION POINTS
| Data | File(s) | Notes |
|---|---|---|
| Character stats/class/growth/portraitId/affinity | `src/data_characters.c` `gCharacterData[]` | portraitId = vanilla value. affinity cosmetic; default Anima. Brace-counting `patch_character_data` was sound last session. |
| Portrait graphics | `graphics/portrait/portrait_<Slot>_*` (+ `src/portrait_data.c`, `data/data_portrait.s`) | Milestone A. `portrait_tool.generate(static_portrait=True)`. |
| Unit names / dialogue | `texts/texts.txt` → `textprocess.py` → `src/msg_data.c` | **PROVEN GOOD.** Names ≤12 chars (`fe_name`). Verify with `verify_text.py`. |
| Chapter: units/placement/events | `src/events/<ch>-event{udefs,script,info}.h` → `events_*.c` | Prefer COPYING a known-good chapter and minimally editing — do not hand-author the beginning scene from scratch. |

## NEXT STEPS (do in order; build clean + verify each before the next)
1. **Name injection from YAML.** Wire `build_campaign.py` to write each cast unit's `fe_name` into `texts/texts.txt` at the unit's `nameTextId` message (names live in YAML, never hardcoded in decomp source). Clean build → `verify_text.py <those indices>` shows the new names → confirm in mGBA once.
2. **gCharacterData injection.** Re-add `patch_character_data` (stats/class/growth/portraitId-vanilla/affinity-Anima) driven by YAML. Verify a stock-prologue unit shows correct class + stats + portrait + NAME together.
3. **Test chapter.** Use a NORMAL chapter (ch1, NOT the tutorial-special Prologue). COPY the vanilla `-event*.h` and minimally edit unit defs to spawn the 10 cast; verify placement.

## BUILD HYGIENE (still the rule)
- **Clean-build the campaign:** `make clean && make CAMPAIGN=rime-of-the-frostmaiden`. Incremental builds desync the decomp dep tracking when `build_campaign.py` rewrites generated source. (Future nicety: have the build force-remove the objects it regenerates so incrementals are safe.)
- **Verify text from the ROM, not by eye:** `python3 tools/verify_text.py`. To eyeball in mGBA, load the ROM properly — `pkill -9 -i mgba; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &`. `open -a mGBA` does NOT reload a running instance (this caused half the "corruption" confusion).
- **Fresh New Game:** `rm fireemblem8u/fireemblem8.sav` (FE8 auto-suspends; stale saves load old unit data).
- **`make` no longer matches vanilla sha1** (we diverge on purpose). Build the decomp `fireemblem8.gba` target. Restore vanilla source: `git -C fireemblem8u checkout <path>`.

## KEY FILES
- `tools/build_campaign.py` — Milestone A (portraits only). Add name+character injection per Next Steps.
- `tools/verify_text.py` — ROM text decoder / regression gate (new).
- `tools/portrait_tool.py`, `tools/ref_to_bust.py` — portrait pipeline. Good.
- `campaigns/.../{pcs,npcs}/*.yaml` — unit data. Long names need `fe_name` (≤12).
- decomp (`fireemblem8u/`) — submodule; our edits are uncommitted build artifacts. Don't commit the submodule pointer.

## MEMORY
- [[feedback_fe_name_truncation]] — short `fe_name` for long names.
- [[project_manchego_stars_portrait_pipeline]] — portraitId-1, mGBA reload trap, static portraits, facing.
- [[feedback_portrait_static_no_animation]] — static busts.

## STANDING RULES
Custom art for the 10 named cast; enemies vanilla. Stock FE8 classes/weapons; combat = vanilla FE; element = flavor. `make` green at session end. Auto-push to main once approved. Don't commit the fireemblem8u submodule pointer.
