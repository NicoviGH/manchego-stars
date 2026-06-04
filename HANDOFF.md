# Handoff: Milestone B — NAMES + CHARACTER DATA (class/stats) both DONE & verified in the ROM. 8 cast units carry the right class, level, Anima affinity, pure-class stats, and class weapon rank; names render+terminate (sweep 0 runaway). Next: a copied test chapter to spawn all 10 and eyeball them in mGBA.

**Date:** 2026-06-04
**This session:** Proved the text path; implemented YAML-driven name injection (fixing the real "Huffman corruption" = a string-terminator parity bug); then implemented gCharacterData class/stat injection. Added `tools/verify_text.py` (ROM text regression gate). Two clean-build + ROM-decode checkpoints, both green.

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
| Character class/stats/level/affinity/ranks/growths | `src/data_characters.c` `gCharacterData[]` | **DONE.** `patch_character_data`. See below. |
| Portrait graphics | `graphics/portrait/portrait_<Slot>_*` | Milestone A, done. |
| Chapter: units/placement/events | `src/events/<ch>-event{udefs,script,info}.h` → `events_*.c` | NEXT. COPY a known-good chapter; don't hand-author the beginning scene. |

## CHARACTER INJECTION — how it works (this session)
`build_campaign.py patch_character_data` rewrites each cast slot's `gCharacterData[]` entry:
- **defaultClass** ← YAML `fe_stats.class` via `CLASS_MAP` (decisions.md Class Mapping; e.g. Pirate→CLASS_PIRATE, Shaman→CLASS_SHAMAN, Knight→CLASS_ARMOR_KNIGHT, "Mage (Ice)"→CLASS_MAGE).
- **affinity** = `UNIT_AFFIN_ANIMA` (cosmetic). **baseLevel** ← YAML level.
- **personal base stats** = YAML stat − class base (read from `data_classes.c`). FE8 has one Pow stat shown as STR or MAG; both map to `basePow`. Luck is character-only (class base 0). Since every unit's `fe_stats` == its class base, deltas come out 0 → displayed stats = pure class base = YAML.
- **baseRanks** ← replaced with the class's weapon type (`CLASS_WEAPON`) at `WPN_EXP_E` (the slot's old SWORD/etc rank is wrong for the new class).
- **personal growths** ← zeroed, so the unit grows at its pure **class** rate (total growth = class + character; we don't want Braulo inheriting Eirika's growths).
- Verified in the ROM: 8 classed slots show correct class/affinity=7/L1/bases=0; brie+pepperjack (no class yet) left vanilla.

**Deliberately NOT yet handled (follow-ups):**
- **Weapon-rank level** is a flat E for everyone — a balance pass should set real ranks (vanilla L1 casters start ~C). Likely belongs in YAML.
- **Gender / `attributes` / `pSupportData`** are still the vanilla slot's (CA_FEMALE leaks onto Braulo/Rootis/Pinky slots; no dangerous flags like CA_LORD/CA_SUMMON though). Needs a YAML-driven gender pass (incl. `_F` class variants where they exist) + supports rework. Note Pinky is male but rides the Neimi(F) slot + Pegasus Knight (female-anim class) — pure flavor handwave for now.
- **brie + pepperjack** have `class: null` (TBD post-MVP) → name-only until classes are chosen.

## NEXT STEPS (clean-build + `verify_text.py`/mGBA each before the next)
1. **Test chapter.** Use a NORMAL chapter (ch1, NOT the tutorial Prologue). COPY the vanilla `-event*.h` and minimally edit unit defs to spawn the 8 classed cast; verify placement + that each shows correct name/class/stats/portrait in mGBA. This is the first real end-to-end visual confirmation of names+stats+portraits together.
2. After that: the Braulo end-to-end slice (#15) is effectively complete → start real maps (Prologue, Ch1), and pick up the gender/ranks/growths follow-ups above.

## BUILD HYGIENE
- **Clean-build:** `make clean && make CAMPAIGN=rime-of-the-frostmaiden`. `build_campaign.py` re-injects (idempotent) into the submodule working tree each build; `make clean` does NOT restore vanilla texts.txt — to reset decomp source: `git -C fireemblem8u checkout <path>`.
- **Verify text from the ROM:** `python3 tools/verify_text.py`. To eyeball in mGBA: `pkill -9 -i mgba; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &` (`open -a mGBA` does NOT reload a running instance).
- **Fresh New Game:** `rm fireemblem8u/fireemblem8.sav`.
- **`make` no longer matches vanilla sha1** (we diverge on purpose). Don't commit the fireemblem8u submodule pointer.

## KEY FILES
- `tools/build_campaign.py` — portraits + names + character class/stats (`patch_character_data`). Chapter/event injection next.
- `tools/verify_text.py` — ROM text decoder / regression gate.
- `tools/portrait_tool.py`, `tools/ref_to_bust.py` — portrait pipeline.
- `campaigns/.../{pcs,npcs}/*.yaml` — unit data. Long names carry `fe_name` (≤12); marty + prof-rbg now do.

## MEMORY
- [[feedback_fe_name_truncation]] — short `fe_name` for long names (≤12).
- [[manchego-stars-text-terminator-parity]] — the odd-length `[.]` terminator gotcha (this session).
- [[project_manchego_stars_portrait_pipeline]] — portraitId-1, mGBA reload trap, static portraits, facing.

## STANDING RULES
Custom art for the 10 named cast; enemies vanilla. Stock FE8 classes/weapons; combat = vanilla FE; element = flavor. `make` green at session end. Auto-push to main once approved. Don't commit the fireemblem8u submodule pointer.
