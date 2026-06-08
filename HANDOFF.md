# Handoff: **Wiring the Prologue (ch00) into the ROM.** The Prologue is fully DESIGNED + its winter MAP is built and committed; next session is the **engine/build wire-up** (#40 register map + #14 inject units/events) to get a playable New Game → ch00 load-test in mGBA. A detailed, decomp-grounded plan is below — execute it.

**Date:** 2026-06-08
**Session Focus:** Designed the whole Prologue ("A Dagger of Ice") with Nicolas and built its map. (1) Locked the chapter: a 2-unit NPC cold-open mirroring FE8's Prologue — **Scramsax** (strong Jagen) protects frail **Hlin** (must-survive lead) vs **Sephek** (Myrmidon boss) + 2 guards; **DefeatBoss, but Sephek escapes in the ending cutscene** (recurring villain). (2) Discovered the **winter-reskin trick** (render any vanilla map's layout through snowy-bern) and used it to make the Prologue map a snow-skinned vanilla Prologue, hand-tuned in a new **browser tile editor**, compiled to `ch00-prologue.mar`. (3) Placed units (vanilla-mirrored staging). (4) Scoped the ROM wire-up from the decomp; filed the player-chosen-lord feature (#42).

**Scope of this file:** HANDOFF = the NOW. Long-term plan = GitHub issues (M0–M4) + `docs/PRD.md`. Settled decisions = `docs/decisions.md`. Durable facts = memory.

## ACTIVE WORKSTREAM — Prologue vertical slice (#20). Live checklist = **GitHub issue #20**.
Goal: New Game → play ch00 end-to-end → win → Sephek-escapes cutscene → hand to Ch1.
Done: design locked, map built, units placed. **Next: wire it into the ROM, then co-write dialogue.**

### NEXT SESSION — write `inject_prologue()` in `tools/build_campaign.py` (the wire-up)
Model it on the two proven injectors in that file: **`inject_winter_tileset`** (map/asset registration, ~L1096) and **`inject_test_chapter`** (unit-def rewrite + cutscene strip + boot cuts, ~L524). Concrete plan (all decomp-grounded this session):

1. **Map** — register `campaigns/.../maps/ch00-prologue.mar` (+`.json`) like the winter test layout: copy into `graphics/map/layout/`, incbin in `data/const_data_chapter_maps.s`, append to `gChapterDataAssetTable` (`data/data_8B363C.s`) via `_append_asm_table_words`. Then repoint **chapter 0** in `src/data/chapter_settings.json` (`chapters[0].map`) to the **snow tileset** (ObjectTypeSnow/MapPaletteSnow/TileConfigurationSnow asset indices — already registered by `inject_winter_tileset`; look them up in the asset table) + `mainLayerId` = our layout. (Snow tileset shares vanilla's metatile indices, so our `.mar` renders correctly — see [[manchego-stars-winter-reskin]].)
2. **Units** — rewrite two arrays in `src/events/prologue-eventudefs.h`:
   - `UnitDef_Event_PrologueAlly[]` → **Scramsax** (strong, FACTION_BLUE) + **Hlin** (frail lead).
   - `UnitDef_Event_PrologueEnemy[]` → **Sephek** (`CHARACTER_ONEILL` slot, boss) + **2 guards** (generic slots `0x80`/`0x82`, like vanilla).
   - Positions/classes/levels/items come from `chapters/ch00-prologue-a-dagger-of-ice.yaml` (x,y are 0-indexed): Hlin `[8,5]` Warrior; Scramsax `[13,9]` Hero; Sephek `[14,8]` Myrmidon; guards `[14,7]`,`[13,7]` Fighter. Hlin/Scramsax need **free vanilla character slots NOT in `PORTRAIT_MAP`** (our 7 PCs already use Eirika/Seth/Franz/Gilliam/Moulder/Vanessa/Ross/Neimi/Garcia/Colm) — pick two unused ones; their vanilla portraits are placeholders for now (see [[feedback_nicolas_not_an_artist]] / closest-match note).
3. **Events** (`prologue-eventinfo.h` + `prologue-eventscript.h`) — empty `EventListScr_Prologue_Turn`/`_Tutorial` (they script the vanilla Eirika/Seth/Valter cutscene); **keep `EventListScr_Prologue_Misc` = `DefeatBoss(EndingScene)` + `CauseGameOverIfLordDies`**. Replace `EventScr_Prologue_BeginningScene` with a minimal deploy: `LOAD1(1, UnitDef_Event_PrologueAlly)` / `ENUN` / `LOAD1(1, UnitDef_Event_PrologueEnemy)` / `ENUN` / `ENDA`. (Vanilla loads enemies later at `prologue-eventscript.h:225`; we load both up front.)
4. **Lord-death = lose-if-Hlin** (RESOLVED — Nicolas's point; I was wrong it needed a class attribute): add a **battle-quote entry** in `src/data_battlequotes.c` `{ .pid = <Hlin's slot>, .chapter = CHAPTER_PROLOGUE, .flag = EVFLAG_GAMEOVER, .msg = <Hlin death line> }`. The `CauseGameOverIfLordDies` watcher fires on that flag. This is exactly vanilla's Eirika/Duessel mechanism — per-character, per-chapter. (#42 generalizes it to the player's chosen unit.)
5. **Boot flow** — `inject_test_chapter` currently redirects New Game prologue→Ch1 (`bmio.c StartBattleMap`, `gPlaySt.chapterIndex == 0 → 1`). For our prologue to be the New Game target, **don't redirect** (and `inject_prologue` should likely REPLACE `inject_test_chapter` in `main()`). Keep its boot cuts: drop `ProcScr_OpAnim` attract, skip `StartIntroMonologue`, gut `EventScrWM_Prologue_Beginning` (world-map Magvel tour) — same edits, minus the 0→1 redirect.
6. **Names** — inject "Hlin"/"Scramsax"/"Sephek" onto their slots (extend `inject_names`/`set_message_body`). **Truncation:** "Hlin Trollbane"(14) & "Sephek Kaltro"(13) overflow FE8's name buffer → use short `fe_name` ≤12 ([[manchego-stars-fe-name-truncation]]). "Scramsax"(8) is fine.
7. Wire `inject_prologue` into `main()`; `make` green; `pkill mgba; rm fireemblem8.sav;` boot → New Game → should land on the winter ch00 with our 5 units; defeat Sephek → ending.

Then **#2: co-write the cutscene/dialogue** (cold open + Sephek's escape + hand-off to The Northlook) — collaborative, book pp.20–24 ([[feedback_collaborative_story_planning]]).

### The MAP authoring loop (works, reusable for every chapter)
- **Winter-reskin any vanilla map:** render its `graphics/map/layout/<Name>Map.bin` (uncompressed source exists) through the snowy-bern tileset — instant natural winter version (shared metatile indices; 78/95 agree, the rest patch by neighbour-copy). See [[manchego-stars-winter-reskin]].
- **Visual editor (no token-by-token tile dictation):** `python3 tools/gen_map_editor.py` → `open map-review/editor.html` → Nicolas paints (palette w/ terrain filter, walkability borders, "replace-all-matching" global mode) → **Export** downloads `~/Downloads/prologue-layout.json` → `python3 tools/import_map_layout.py` compiles to `ch00-prologue.mar` + renders. Closes the loop.
- Editor starting grid = base reskin + manual/remap layers (`map-review/_manual.json`, `_remap.json`, gitignored). Atlas/terrain helpers: scratch in `/tmp` this session (vanilla_terrain.py, inventory.py, etc.) — promote a `render_layout()` + terrain-overlay into `tools/map_tileset_tool.py` if useful.
- **Tile palette budget** (snowy-bern, 1024 metatiles): Peak 175, Wall 170, Floor 144, Plains 90, Cliff 71, River 45, Forest 27; sparse: Bridge **2**, House 2, Door 6, Gate 3. Wilderness rich, towns thin — why the Prologue became a snowy mountain pass, not a town street.

## Done / what works
- **Prologue fully designed** — `chapters/ch00-prologue-a-dagger-of-ice.yaml`: 2-unit cold open, flipped roles (Scramsax Jagen / Hlin frail lead), DefeatBoss-but-Sephek-escapes, recurring-villain hook, vanilla-mirrored placements, lord-death note. Grounded in book "Cold-Hearted Killer" (pp.21–24) + the vanilla Prologue roster/objective (read from the decomp).
- **Prologue MAP built + committed** — winter reskin of "The Fall of Renais", hand-tuned in the editor → `campaigns/.../maps/ch00-prologue.mar` (15×10). NOT yet registered/wired into the ROM (that's next session).
- **Map editor tooling committed** — `tools/gen_map_editor.py` + `tools/import_map_layout.py`.
- Winter tileset (#41) + map pipeline (#40 task1/2) from prior sessions still green; map sprites (#38) done; `make CAMPAIGN=rime-of-the-frostmaiden` green.
- **Ch1 ("The Iron Trail")** identified as the book's **"Foaming Mugs"** quest (pp.34–35) — enrichment (Izobai, polar-bear wagon, yeti/Oobok, named dwarves) parked as a TODO in `chapters/ch01-the-iron-trail.yaml` (complement the DM-notes beats, don't replace).

## Tried but didn't work (lessons)
- **Town-street dead-end-alley draft** — abandoned: snowy-bern has only 2 house tiles, so dense towns look bad; pivoted to the wilderness winter-reskin (gorgeous + nearly free).
- **Pixel-matching vanilla→winter art** to find tile equivalents — unreliable (matched a tan mountain to tan floor/brick tiles). The index mapping is the better signal; mis-mapped slots are fixed by eyeball + the editor's global replace.
- **Reskin "iron-out": nearest-color match** popped bright cyan blocks → switched to **neighbour-copy** (a divergent cell copies a same-terrain neighbour) — blends cleanly.
- **Lord-death "needs a class attribute"** — WRONG (corrected): it's a per-character battle-quote `EVFLAG_GAMEOVER` entry. So lose-if-Hlin works in Ch0 directly (plan step 4).

## Blockers
- None hard. The wire-up is well-scoped; just execution + slow build/test cycles. Optional decision already made: Ch0 lose-condition = lose-if-Hlin (via the battle-quote flag), not "all allies dead".

## Build / Run Hygiene
- **Build:** `make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba -j$(sysctl -n hw.ncpu)`. **Checks:** `make check` (drift) · `make verify` (ROM text). Never commit the `fireemblem8u` submodule pointer.
- **mGBA:** `pkill -9 -i mgba; rm -f fireemblem8u/fireemblem8.sav; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &` then New Game.
- **build_campaign edits the decomp idempotently** (`restore_vanilla_sources` resets each build) — safe to iterate on `inject_prologue`.
- **Commit msgs with body** via `git commit -F`. Auto-push to main once green ([[feedback_proactive-push]]).
- **Showing Nicolas visuals:** he can't see inline renders late in a session — save PNGs to `map-review/` and `open` them ([[feedback_sharing_visual_drafts]]). `references` symlink bridges the copyrighted assets.

## Key Files
- **Prologue chapter:** `campaigns/rime-of-the-frostmaiden/chapters/ch00-prologue-a-dagger-of-ice.yaml` (the design source of truth).
- **Prologue map:** `campaigns/.../maps/ch00-prologue.mar` + `.json` (compiled layout).
- **Map tooling:** `tools/gen_map_editor.py` · `tools/import_map_layout.py` · `tools/map_tileset_tool.py` (atlas/`compile_layout`) · `map-review/editor.html` (gitignored, regen-able).
- **Wire-up targets (next session):** `tools/build_campaign.py` (`inject_winter_tileset`/`inject_test_chapter` = templates; add `inject_prologue`) · `fireemblem8u/src/events/prologue-event{info,script,udefs}.h` · `data/data_8B363C.s` · `data/const_data_chapter_maps.s` · `src/data/chapter_settings.json` · `src/data_battlequotes.c` (lord-death) · `src/bmio.c` + `gamecontrol.c` (boot flow).
- **Review scratch:** `map-review/` (gitignored: editor.html, layout JSONs, all the review PNGs) · `references/` (gitignored symlink → source assets).
- **Issues:** #20 (Prologue, has the live slice checklist) · #40 (map pipeline) · #14 (event injection) · #42 (player-chosen lord) · #21–#28 (Ch1–8).

## Memory
- [[manchego-stars-winter-reskin]] · [[manchego-stars-project]] · [[feedback-chapter-vertical-slice]] · [[manchego-stars-fe-name-truncation]] · [[feedback_story_sources_of_truth]] · [[feedback_collaborative_map_design]] · [[feedback_collaborative_story_planning]] · [[feedback_sharing_visual_drafts]] · [[feedback_handoff_vs_memory]]

## Standing Rules
Custom art for the named cast; enemies vanilla (FE8 classes). Combat = pure vanilla FE. **Maps = winter reskin of vanilla layouts via snowy-bern, decomp-native (#40/#41); no ROM hex.** Ground FE/map/event mechanics in the decomp, never guess. Story from DM notes (text) + book (scan), reconciled, COMPLEMENT don't replace; dialogue co-written with Nicolas. Show maps/art → `open` for Nicolas → wait for OK → then commit. Auto-push to main once green. Don't commit the `fireemblem8u` submodule pointer. **`gCastMapPalette` is intentionally rotated +1 — don't "fix" it.**
