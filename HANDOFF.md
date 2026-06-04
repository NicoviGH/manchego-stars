# Handoff: Milestone B — NAME INJECTION DONE & verified. All 10 cast names render+terminate in the ROM (sweep 0 runaway). The real text bug was a terminator-parity gotcha (odd-length names need a `[.]` pad), now handled. Next: gCharacterData (stats/class) injection, then a copied test chapter.

**Date:** 2026-06-04
**This session:** Proved the text path, then implemented YAML-driven unit-name injection. Found and fixed the actual bug behind the reset's "Huffman corruption" — it was NOT a textprocess/huffman bug, but a **string-terminator parity** issue in how names are formatted. Added `tools/verify_text.py` (ROM text decoder / regression gate) which caught it immediately.

## WHAT WORKS — keep (committed)
- **Milestone A portraits** — 10 busts → vanilla slots, static, facing-correct. `make` builds, faces correct.
- **portraitId = vanilla character value** (Eirika 0x2, Seth 0x4, Gilliam 0x5, Franz 0x6, Moulder 0x7, Vanessa 0x8, Ross 0x9, Neimi 0xa, Colm 0xc, Garcia 0xe).
- **Unit NAME injection (this session).** `tools/build_campaign.py inject_names`: reads each cast `fe_name`/`name` from YAML, finds the vanilla slot's `.nameTextId` from `src/data_characters.c` (not hardcoded), and rewrites that message in `texts/texts.txt`. Default `make` injects portraits + names; `--portraits-only` skips names. **Verified: all 10 names decode+terminate in the ROM, full sweep 0 runaway.**

## THE REAL TEXT BUG (root cause of the reset's "corruption")
Not Huffman. **String-terminator parity.** FE8 packs printable text two bytes per u16 (`textprocess.py text_to_utf8_u16_array`). `[X]` = the 0x00 terminator. If an **odd** number of name bytes precede it, the 0x00 pairs into the last glyph's high byte instead of standing alone as 0x0000 — so the in-game decoder never hits its terminator and **runs away into the next message** (exactly the garbage the reset saw: "Wolfram as e...oi. ee?"). Vanilla pads odd names with `[.]` (0x1F, absorbed into the last glyph) so the byte count stays even: `Seth[X]` (even) vs `Franz[.][X]` (odd). `build_campaign.py:name_message_body()` now does the same.
- Why the first test missed it: a single even-length name ("Braulo") happens to terminate fine; the bug only shows on odd-length names (Marty, Wolfram, Prof. RBG, Sclorbo, Pinky). The earlier "stale-build ghost" read was incomplete — there was a genuine bug, just not in the Huffman codec.

## REGRESSION TOOL — use it after EVERY text change
- **`tools/verify_text.py`** decodes message text straight from the built ROM by `.map` symbol (reproduces the game's Huffman decoder); no mGBA needed.
  - `tools/verify_text.py` → sweep all 3404 messages, nonzero exit on any runaway.
  - `tools/verify_text.py 0x212 0x213 …` → decode specific indices (odd names show a harmless trailing `[1F]` = the `[.]` pad, same as vanilla Franz).

## TOOLCHAIN NOTE
`build_campaign.py` now needs **PyYAML** in the build interpreter (brew python@3.12). Installed, and added to `tools/setup-toolchain.sh` (alongside numpy/pillow) so a fresh clone reproduces.

## VALIDATED DECOMP INJECTION POINTS
| Data | File(s) | Status |
|---|---|---|
| Unit names | `texts/texts.txt` (msg at slot's `.nameTextId`) → `textprocess.py` → `src/msg_data.c` | **DONE.** Parity-padded. Verify with `verify_text.py`. |
| Character stats/class/growth/portraitId/affinity | `src/data_characters.c` `gCharacterData[]` | NEXT. portraitId = vanilla value; affinity cosmetic (default Anima). Brace-counting `patch_character_data` was sound last session. |
| Portrait graphics | `graphics/portrait/portrait_<Slot>_*` | Milestone A, done. |
| Chapter: units/placement/events | `src/events/<ch>-event{udefs,script,info}.h` → `events_*.c` | LATER. COPY a known-good chapter; don't hand-author the beginning scene. |

## NEXT STEPS (in order; clean-build + `verify_text.py`/mGBA each before the next)
1. **gCharacterData injection.** Add `patch_character_data` to `build_campaign.py`: write each cast unit's `fe_stats` (class/level/HP/STR/SKL/SPD/DEF/RES/LCK/MOV/CON) + portraitId(=vanilla) + affinity(=Anima) into the slot's `gCharacterData[]` entry in `src/data_characters.c`. The YAML already carries `fe_stats` (see `pcs/braulo.yaml`). Verify a stock-prologue unit shows correct class+stats+portrait+NAME together.
2. **Test chapter.** Use a NORMAL chapter (ch1, NOT the tutorial Prologue). COPY the vanilla `-event*.h` and minimally edit unit defs to spawn all 10 cast; verify placement in mGBA.
3. After both: the Braulo end-to-end slice (#15) is effectively complete → start real maps (Prologue, Ch1).

## BUILD HYGIENE
- **Clean-build:** `make clean && make CAMPAIGN=rime-of-the-frostmaiden`. `build_campaign.py` re-injects (idempotent) into the submodule working tree each build; `make clean` does NOT restore vanilla texts.txt — to reset decomp source: `git -C fireemblem8u checkout <path>`.
- **Verify text from the ROM:** `python3 tools/verify_text.py`. To eyeball in mGBA: `pkill -9 -i mgba; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &` (`open -a mGBA` does NOT reload a running instance).
- **Fresh New Game:** `rm fireemblem8u/fireemblem8.sav`.
- **`make` no longer matches vanilla sha1** (we diverge on purpose). Don't commit the fireemblem8u submodule pointer.

## KEY FILES
- `tools/build_campaign.py` — portraits + names. Add `patch_character_data` next.
- `tools/verify_text.py` — ROM text decoder / regression gate.
- `tools/portrait_tool.py`, `tools/ref_to_bust.py` — portrait pipeline.
- `campaigns/.../{pcs,npcs}/*.yaml` — unit data. Long names carry `fe_name` (≤12); marty + prof-rbg now do.

## MEMORY
- [[feedback_fe_name_truncation]] — short `fe_name` for long names (≤12).
- [[manchego-stars-text-terminator-parity]] — the odd-length `[.]` terminator gotcha (this session).
- [[project_manchego_stars_portrait_pipeline]] — portraitId-1, mGBA reload trap, static portraits, facing.

## STANDING RULES
Custom art for the 10 named cast; enemies vanilla. Stock FE8 classes/weapons; combat = vanilla FE; element = flavor. `make` green at session end. Auto-push to main once approved. Don't commit the fireemblem8u submodule pointer.
