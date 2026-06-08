# Handoff: Building the **Prologue (ch00) map**. The winter tileset (#41) is DONE and the decomp-native map pipeline (#40) works — we can author a layout in code and render/compile it. **NOW: iterating the Prologue map design with Nicolas** (draft 2 is in `map-review/`, awaiting his feedback). Then wire it into the chapter + add units/events/dialogue (#20). Map sprites (#38) done; battle anims (#39) deferred.

**Date:** 2026-06-08
**Session Focus:** (1) Shipped #41 + #40 task 1 — Snowy Bern tileset is a **byte-identical decomp drop-in** (no grit), registered via `build_campaign.inject_winter_tileset()`, snow renders in-engine (e4372cc). (2) Built `tools/map_tileset_tool.py` — metatile **atlas renderer** + `compile_layout()` (grid → decomp `.bin`), committed (d7b5b41). (3) Gathered map references and **started the Prologue map drafting loop**: rendered the vanilla FE8 Prologue (complexity yardstick), pulled the Bryn Shander map (book + community top-down), produced **draft 2** (gate-slice), all in `map-review/` for Nicolas to review.

**Scope of this file:** HANDOFF = the NOW. Long-term plan = GitHub issues (M0–M4) + `docs/PRD.md` + `docs/roadmap.md`. Settled decisions = `docs/decisions.md`. Durable facts = memory.

## ACTIVE WORKSTREAM — Prologue chapter (#20) + finishing the map pipeline (#40)
Goal: turn ch00 ("A Dagger of Ice") into a real, playable chapter (real map + units + cutscene/dialogue + DefeatBoss), then repeat for Ch1+.

### Where the Prologue MAP stands (live — pick up here)
- **Drafting loop is open.** `map-review/` (gitignored) holds the renders + `REVIEW.md`. **Draft 2 = `map-review/prologue-draft2.png`** is the current proposal, **awaiting Nicolas's feedback**.
- **Draft 2 design:** a slice of Bryn Shander's **gate** — gate (top) = the chokepoint with **Sephek** holding it; **cliffs frame the right** (the hill); a **house block + plaza with a frozen well**; a **winding street** down to the **south deploy zone**; forest cover. 15×10.
- **Open questions for Nicolas** (in `REVIEW.md`): (1) do the stacked house tiles read as real buildings or broken? (2) cliffs+wall frame vs. fully-enclosed town? (3) Sephek at the gate vs. deeper in the plaza? (4) keep 15×10 or go ~18×12? (5) ~3–4 caravan guards + Sephek — OK?
- **Grounding (do NOT re-derive):**
  - **Complexity/difficulty yardstick = the vanilla FE8 Prologue** (`map-review/vanilla-prologue-map.png`): **15×10**, ONE chokepoint (bridge), framing terrain (mountains), open center, **~3 enemies + 1 boss**. Keep ch00 gentle and terrain-driven.
  - **Look = Bryn Shander** (circular walled hill-town, N/E/SW gates, central plaza): book map (`map-review/bryn-shander-reference.png`) + **community top-down** `references/References/Ten-Towns-Maps/Bryn-Shander-Large.jpg` (the **Light-Versions** one; crop to the town — it's a small circle in a big snowfield).
  - **Story = book p.21–23** ("Cold-Hearted Killer"): **Hlin Trollbane** (dwarf bounty hunter, unarmored veteran, battleaxe/handaxe → **Warrior**, ally) hires the party to kill **Sephek Kaltro** (Torg's caravan bodyguard, undead, Ice Longsword/Dagger, cold-regen + fire-vuln = FLAVOR only → **Myrmidon boss**).

### How to author a map (the working method this session)
- **Render the atlas / terrain sampler** with `tools/map_tileset_tool.py` to see metatiles by index. **Layout `.bin` value = `metatile_index × 4`.**
- **Terrain IDs** (decomp `constants/terrains.h`, read off the config's terrain byte) map the snow tileset's tiles: PLAINS 0x01 (snow ground; clean tile = **idx 6**), ROAD 0x02 (idx 861), HOUSE 0x05 (832/395), FORT 0x0a (396), GATE_CASTLE 0x0b (938 = arch), FOREST 0x0c (192), SEA 0x15 (155), FLOOR 0x17, WALL 0x1a (146/182), DOOR/facade 0x1e (878/879/921/922), CLIFF 0x26 (20–29).
- **Compose the grid in code → `compile_layout()` → `.bin/.json`**, then either render a PNG preview (offline, fast) or build into the ROM. (The "Tiled `.tmx`" path in #40 is now optional — authoring-by-index + offline render is the loop.)

### Showing Nicolas visuals (IMPORTANT workflow — see [[feedback_sharing_visual_drafts]])
- He **cannot see my inline image renders**, and late in a long session the image API rejects new images even for me. So: **save PNGs to `map-review/`** and **`open` them in macOS Preview/Finder** for him. Sanity-check layouts with an **ASCII dump** when I can't view the PNG.
- **Two source trees, now bridged:** the repo is `/Users/Yonick/Projects/manchego-stars`; the copyrighted assets (ROM, PDFs, `Ten-Towns-Maps`) live in `/Users/Yonick/Documents/Claude/Projects/Manchego Stars / Fire Emblem Game`. A gitignored **`references` symlink** in the repo root now points there, so the repo is the single entry point.

### The chapter machinery (already understood — no need to re-derive)
- Prologue has a **native slot** `src/events/prologue-event*.h`; `EventListScr_Prologue_Misc` is already `DefeatBoss(EndingScene)` + `CauseGameOverIfLordDies` → ch00 win/lose for free. `PrologueEvents` wires units → scenes → map.
- **Dialogue** = `Text(msgId)` → `## MSG_<id>` in `texts/texts.txt`; `build_campaign.set_message_body`/`inject_names` overwrite vanilla slots (proven).
- **`inject_test_chapter`** is the plumbing template (strip cutscenes, redirect to a chapter). Real-chapter injection (#14) reuses it on the **Prologue** slot. Map **Sephek → boss-flagged enemy slot** (e.g. `CHARACTER_ONEILL`); **Hlin → a spare slot**, name-injected.

## Next Steps (priority)
1. **Get Nicolas's draft-2 feedback → re-render in `map-review/`** until he signs off (answer the 5 open questions above).
2. **Finalize the map:** `compile_layout()` → register the layout (like `inject_winter_tileset` does the test layout) → point the **Prologue** chapter at it → `make` green → load-test in mGBA.
3. **#20 Prologue content:** `npcs/hlin-trollbane.yaml` + `npcs/sephek-kaltro.yaml`; place units (Hlin ally, Sephek boss, ~3–4 guards); beginning/ending cutscene + dialogue (co-written, book p.21–23); DefeatBoss + lose-if-Hlin-dies.
4. Then Ch1+ (#21–#28) repeat. Battle-anim spike (#39) post-MVP.

**Dialogue is collaborative** ([[feedback_collaborative_story_planning]]): draft from the book + get Nicolas's line-by-line OK; don't commit final script solo.

## Done / what works
- `make CAMPAIGN=rime-of-the-frostmaiden` green; New Game → **test chapter = a snow field** (winter tileset) with all 8 cast in custom colours, standing + moving.
- **Winter tileset (#41) done; map pipeline proven (#40):** `inject_winter_tileset()` (drop-in, no recompile). Sources in `campaigns/.../maps/tilesets/snowy-bern/`; workflow in `campaigns/.../maps/README.md`.
- **`tools/map_tileset_tool.py`** (atlas/terrain-sampler renderer + `compile_layout`) committed.
- Reference renders + map drafts staged in `map-review/`. Commits pushed to main; drift clean; submodule pointer untouched. Editor scratch (`*-action`, `*-tiger`, …) left uncommitted by design.

## Blockers
- **Prologue map is gated on Nicolas's design feedback** (draft 2). Not a hard blocker — just the collaborative loop.
- **Reddit is firewalled in this environment** (domain + `.json` + mirrors all 403; harness fetch refuses `reddit.com`). Community art must come from **local files**, a **direct `i.redd.it`/imgur URL**, or **Google Drive** — not a reddit post link.
- Battle anims (#39) need the unbuilt decomp-native anim inserter — post-MVP/M4.

## Build / Run Hygiene
- **Build:** `make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba -j$(sysctl -n hw.ncpu)`. **Checks:** `make check` (drift) · `make verify` (ROM text). Never commit the `fireemblem8u` submodule pointer.
- **mGBA:** `pkill -9 -i mgba; rm -f fireemblem8u/fireemblem8.sav; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &` then New Game.
- **Commit msgs with body:** write to a temp file / heredoc + `git commit -F`.
- **Images:** keep renders ≤2000px if I need to view them; save full-size to `map-review/` and `open` for Nicolas.

## Key Files
- **Map tooling:** `tools/map_tileset_tool.py` (atlas renderer + `compile_layout`) · `tools/build_campaign.py` `inject_winter_tileset` + `_append_asm_table_words` · `campaigns/.../maps/README.md` (workflow) · `campaigns/.../maps/tilesets/snowy-bern/` (tileset sources) · `campaigns/.../maps/ch-test-snowfield.{mar,json}` (test layout).
- **Decomp map wiring:** `data/data_8B363C.s` (`gChapterDataAssetTable`) · `data/const_data_chapter_maps.s` (incbin) · `src/data/chapter_settings.json` (chapter→asset indices; jsonproc → `chapter_settings.h`) · `graphics/map/layout/` · `src/events/prologue-event{info,script,udefs}.h`.
- **Review scratch:** `map-review/` (gitignored: draft PNGs + `REVIEW.md`) · `references/` (gitignored symlink → source assets).
- **Issues:** #40 (map pipeline; task1+register done, finishing real maps) · #41 (winter tileset, CLOSED) · #14 (event injection) · #20 (Prologue) · #21–#28 (Ch1–8).
- **Docs:** `docs/decisions.md` → Art & Audio (maps decision) · `CREDITS.md` (Snowy Bern authors).

## Memory
- [[manchego-stars-project]] · [[manchego-stars-fe-repo]] · [[manchego-stars-use-decomp]] · [[feedback_story_sources_of_truth]] · [[feedback_collaborative_story_planning]] · [[feedback_show_before_committing_art]] · [[feedback_sharing_visual_drafts]] · [[feedback_handoff_vs_memory]]

## Standing Rules
Custom art for the named cast; enemies vanilla (FE8 classes). Combat = pure vanilla FE. **Maps = community winter tileset, decomp-native (#40/#41); no ROM hex.** Ground FE/map/event mechanics in the decomp, never guess. Story from DM notes (text) + book (scan), reconciled; dialogue co-written with Nicolas. Show art/maps → `open` for Nicolas → wait for OK → then commit. Auto-push to main once approved. Don't commit the `fireemblem8u` submodule pointer. **`gCastMapPalette` is intentionally rotated +1 — don't "fix" it.**
