# Design Decisions — Manchego Stars

> These decisions are **settled**. Do not re-open them without a strong reason.
> Add new decisions here when they are made. Date each entry.

**Contents:**
[Engine & Tech Stack](#engine--tech-stack) ·
[Documentation Model](#documentation-model) ·
[Working Conventions](#working-conventions-definition-of-done) ·
[Combat System](#combat-system) ·
[Weapon & Magic Systems](#weapon--magic-systems) ·
[Economy](#economy) ·
[Distribution & Scope](#distribution--scope) ·
[Art & Audio](#art--audio) ·
[Class Mapping & Promotions](#class-mapping--promotions) ·
[Story & Dialogue](#story--dialogue) ·
[Operational Gotchas](#operational-gotchas-durable) ·
[Open Questions](#open-questions-not-yet-decided)

---

## Engine & Tech Stack

**Base game: FE8 Sacred Stones (US) decomp (`fireemblem8u`)**
Using the near-complete matching decompilation from FireEmblemUniverse. The deliverable is a `.gba` file — no custom engine, no SRPG Studio, no Lex Talionis.
_Decided: May 2026_

**Compiler: agbcc (GCC 2.95.1)**
The decomp uses the original GBA compiler to produce byte-identical output. New engine modules also use agbcc. No C99 features, no VLAs, no designated initializers.
_Decided: May 2026_

**Engine/content split: engine in C (reusable), campaign data in YAML (swappable)**
All campaign-specific data (character names, chapter events, unit stats, maps, dialogue) lives in `campaigns/rime-of-the-frostmaiden/` and is injected at build time. Engine C code must be campaign-agnostic. A second campaign requires only a new `campaigns/` folder.
_Decided: May 2026_

**Tooling language: Python everywhere. NOT TypeScript.**
The original plan named a Node/TypeScript toolchain (`build-campaign.ts`, `build-events.ts`, `pull-srd.ts`, `map-class.ts`). Reality: the injector is `tools/build_campaign.py`, with `tools/portrait_tool.py`, `tools/ref_to_bust.py`, `tools/verify_text.py`, and the index generators `tools/gen_chapter_index.py` / `tools/gen_class_index.py`. No Node, no `.ts`, and (since 2026-06-09) no Ruby — the index generators were ported to Python so `tools/check.py` can import them for the freshness gate and CI needs one runtime. The build interpreter is Homebrew `python@3.12` (numpy/pillow/pyyaml; see `tools/setup-toolchain.sh`).
_Decided: 2026-06-04 (supersedes the PRD's TS toolchain plan); 2026-06-09 (Ruby index generators ported to Python)_

**Content injection is decomp-native — edit the decomp's own source, NOT Event Assembler.**
`build_campaign.py` writes our content directly into the `fireemblem8u` working tree at build time — `graphics/portrait/` (busts), `texts/texts.txt` (names/dialogue), `src/data_characters.c` (class/stats), and `src/events/<ch>-event*.h` (chapters) — then `make` compiles it. No Event Assembler / ColorzCore / `.ea` buildfiles. This is the "make a hack directly from the fireemblem8u decomp" path (FEU thread 17428). Generated files are reproducible artifacts: restore vanilla with `git -C fireemblem8u checkout <path>`.
_Decided: 2026-06-04 (supersedes the PRD's Event Assembler plan; retires the `tools/build-events.ts` idea)_

**Injection is idempotent: a byte-identical re-emit rewinds the file's mtime, so `make` skips it.**
Because injection rewrites the decomp's own sources every build (above), and `restore_vanilla_sources`
re-`git checkout`s them, every touched file's mtime moved on every build — and `make` keys off mtime, not
content. A no-change rebuild therefore paid the full ~354-TU cascade from restored widely-included headers
plus the serial `data_banim.o` link over 1752 assets. `build_campaign` now snapshots the previous build's
injection footprint (content sha1 + `mtime_ns`) before injecting and rewinds the mtime of every file whose
bytes come out **identical**. Only mtime is written, and only on unchanged content, so the ROM cannot move.
**Measured on the ch04 branch (CH04BOOT, `-j`):** warm rebuild **188s → 28s** (6.7×); clean build 232s
without vs 236s with, and all of {clean-without, warm-without, warm-with ×2, clean-with} produced the same
ROM `sha256 dc1c56bf…`. The risk this design carries is that a wrong content-check would be invisible to
`make` (stale objects, silently), so it is also proved from the other side: changing one line of real
content (a `death_quote`) moved the ROM sha and left that file un-rewound (482 → 481), and reverting it
returned the ROM to `dc1c56bf…` exactly. Re-run those two gates if the footprint logic is ever touched.
_Decided: 2026-07-30 (#24; written 2026-07-21, merged only once the ROM gates could run on the Mac)_

**No SRD/Open5e pull.** PC data is authored from the players' D&D Beyond JSON (`data/pc-sheets/`); D&D is flavor-only over vanilla FE combat (see FE-strictness below). No SRD downloader, no `srd-snapshot.json`, no homebrew engine classes — the cast use stock FE8 classes (see Class Mapping).
_Decided: 2026-06-04_

**Text injection has a terminator-parity gotcha (the reset's "Huffman corruption").**
FE8 packs text two bytes per u16; `[X]` = the 0x00 string terminator. The packer (`textprocess.py`) pairs printable bytes two-at-a-time but emits each control byte (`[LF]`=0x01, `[X]`=0x00, the `[.]` pad=0x1F) as its own u16, which realigns the pairing — so each *run* of printables between control codes pairs independently. A run with an **odd** length makes its last char swallow the *following* byte; when that byte is the `[X]` terminator, the decoder runs past it into the next message (garbage + bleed-through). Vanilla pads odd names with `[.]` (`Franz[.][X]` vs `Seth[X]`); `build_campaign.py`'s `_term_pad` does the same — but the parity that matters is the **final run** (the printables after the last control code), **not** the whole message: a multi-line body whose earlier `[LF]` runs are odd can sum to an even total yet still have an odd final run that eats `[X]` (Pinky's pitch: 16+19+13 = 48 even, final run 13 odd → runaway). Note `verify_text.py` only flags *length* runaways (>~2133 vals), so a short bleed into the very next message passes its sweep — decode the specific ids (`verify_text.py 0xNNN`) and read the tail when authoring multi-line messages.
_Decided: 2026-06-04; refined 2026-06-25 (final-run parity — multi-line lord-select pitches, #46)_

**Card/name text from YAML must be ASCII-folded before FE8 encoding — `name_message_body` does it centrally.**
Dialogue routed through `_script_to_message` already gets `_fe_dialogue_text` (em-dash→`--`, smart-quotes→ASCII, etc.), but location-card/title/name text bypassed that path and went straight to `name_message_body` — so a literal em-dash in a YAML `location_card` ("Bryn Shander — West Gate") reached the encoder as a non-charset byte and **garbled the ch02 opening card** (#22). Fix: `name_message_body` now `_fe_dialogue_text`-normalizes first, so every card/title/name is charset-safe and the terminator-parity count sees the bytes the encoder will actually emit. Keep authored unicode in the YAML; the encoding boundary folds it.
**Companion gotcha — location-card nameplates cap at ~96px.** `BROWNBOXTEXT`/`StartBrownTextBox` draws the card text as exactly **3×32px sprites** (`popup.c` `BrownTextBox_Loop`, `for (i=0;i<3;i++)`); the brown *border* grows with the string but the *text* region is fixed, so anything past ~12-14 chars clips silently (the in-engine capture caught "Bryn Shander — West Gate" rendering "Bryn Shander -- We"). Keep `location_card:` values to short place names (vanilla does: "Targos", "Bryn Shander"); push locational detail into the scene/dialogue, not the plate. Don't widen the shared widget (it's a vanilla popup — "additive, never global").
_Decided: 2026-06-25_

**Test-chapter spawn = vanilla Ch1 map stripped to a sandbox (not a hand-authored chapter).**
The first in-engine check that names + portraits + classes + stats land together (Milestone B step 3) keeps vanilla Ch1's **map** but guts its scripting, via `build_campaign.py:inject_test_chapter`:
- rewrites the player roster (`UnitDef_Event_Ch1Ally`) to our 8 classed cast (each rides its `PORTRAIT_MAP` slot's `CHARACTER_` id, so its injected name/portrait/class/stats show; `redaCount = 0` places it statically at `xPosition/yPosition`, per `eventscr.c:sub_800F8A8`);
- replaces the **beginning scene** with a minimal `LOAD1`/`ENUN`/`ENDA` (deploy the cast, hand over control). The vanilla scene ran a scripted Breguet fight + forced moves that *deleted our units mid-cutscene* → instant lord-death game over;
- empties every per-chapter event list (turn/character/location/misc/tutorial) so nothing references removed units or fires a win/lose condition.

**Boot straight to the map (four cuts, each at the source that plays it).** A single early hook does *not* work: setting `chapterIndex` at `gamecontrol.c:GameControl_RememberChapterId` gets reset before the world-map wrapper, so the Magvel tour still ran. Each pre-map sequence is therefore cut at its own source:
1. `gamecontrol.c` drops `PROC_START_CHILD_BLOCKING(ProcScr_OpAnim)` — the boot character-flash attract reel;
2. `gamecontrol.c:GameCtrlStartIntroMonologue` early-returns — the "long ago…" lore crawl;
3. `bmio.c:StartBattleMap` redirects `if (chapterIndex == 0) chapterIndex = 1` — the authoritative map load (feeds `InitChapterMap`/fog/weather); `chapterIndex == 0` here can only be a fresh game's prologue (skirmishes use `PLAY_FLAG`s; later chapters nonzero);
4. `prologue-wm.h` guts `EventScrWM_Prologue_Beginning` (it runs `WM_TEXT(0x8DB)`, the nation-by-nation "continent of Magvel" world tour) to a `SKIPWN` no-op — the world-map wrapper runs this *before* (3), so (3) alone can't stop it. Dead ends ruled out: `bmsave.c`'s save field only feeds the title card; `gamecontrol.c:sub_8009C5C` is unreferenced.

Net result: New Game → Ch1 map with the 8 cast, no cutscene, no game over — a pure look-test (no enemies, no objective; reset when done). Test loadouts are stock vanilla weapons by class (`CLASS_LOADOUT`); per-unit YAML inventory is a later pass. All edited decomp files are restorable build artifacts (`PATCHED_DECOMP_FILES`). Authored chapters (real maps/events/objectives from YAML) supersede this whole step.
_Decided: 2026-06-04_

**Static custom portraits need the mouth baked into the engine's mouth tiles + uniform mouth/eye geometry.** Custom busts are non-animated ([[feedback_portrait_static_no_animation]]), but "bake the full face, emit transparent mouth frames" alone leaves a **mouth cutout** (a transparent hole over the mouth) on every portrait. Two decomp facts, both in `face.c`: (a) the status-screen face reader `PutFace80x72_Standard` always draws the 32×16 mouth window from tileset tiles `0x1C–0x1F`/`0x3C–0x3F` (sheet cols 28–31), which `portrait_tool.encode()`'s `OBJECTS` never fill → blank → hole; (b) it draws that window at the slot's `FaceData.xMouth/yMouth`, which varies per vanilla slot. Fixes: `portrait_tool.generate(static_portrait)` now pastes the neutral mouth into tiles `0x1C–0x1F`/`0x3C–0x3F` (and into all sprite frames for dialogue); and `build_campaign.py:patch_portrait_geometry` normalizes every dressed slot's `FaceData` mouth/eye window to our single bust framing (`xMouth 2, yMouth 6, xEyes 3, yEyes 4` — the coords the Eirika/Franz/Vanessa/Neimi slots already used). Without the geometry pass, slots at row 5 (Seth/Gilliam/Moulder/Garcia) or shifted column (Ross/Colm) painted the mouth one tile off → a doubled mouth.
_Decided: 2026-06-04_

**Non-LORD-class lords need engine guards (the prologue "garbage-band" crash).**
Our cast ride ordinary vanilla character slots (`PORTRAIT_MAP`); none are FE8 LORD-class. FE8's chapter start assumes the player *leader* is a deployed LORD-class unit, and that assumption, violated, crashed the prologue. The failure chain (debugger-confirmed, not guessed):
1. `bmcamadjust.c:GetPlayerStartCursorPosition` centers the cursor on `GetUnitFromCharId(GetPlayerLeaderPid())`. With no LORD deployed that returns **NULL**, and the vanilla code dereferences it (`unit->xPos`) → reads BIOS garbage → cursor parked **off-map** (e.g. y=32 on a 10-tall map).
2. The terrain-display window then reads `gBmMapTerrain[cursor.y][cursor.x]` out of bounds → a garbage terrain id (e.g. 330).
3. `bmmap.c:GetTerrainName` indexes its 65-entry name table with that id → a garbage `gMsgTable[]` pointer → the **Huffman text decoder runs away** (same decoder-runaway class as the terminator-parity gotcha above), spewing `0x73 0x20` across IWRAM and overrunning `gBmSt` (camera/cursor/render state) → corrupted tiles ("garbage band") + soft-lock, and eventually a wild jump (`Jumped to invalid address`).
The map data, tileset, dimensions, and pointers were all **correct** — a runtime NULL-deref, not a build/asset defect. Two campaign-agnostic guards in `build_campaign.py` (applied every build; the build fails if the decomp source form drifts via each patch's `if orig not in text`, and `tools/check.py:check_engine_guards_present` fails if they're removed):
- `_patch_player_start_cursor_guard` — `GetPlayerStartCursorPosition` falls back to the first valid player unit when the leader isn't deployed, and never derefs NULL (the real fix).
- `_patch_terrain_name_guard` — `GetTerrainName` clamps out-of-range terrain ids to 0 (defensive; an invalid terrain must render, never crash).

Method that cracked it after env-gated bisection went nowhere: **`mGBA -g` + `arm-none-eabi-gdb`** (`brew install arm-none-eabi-gdb`); a **hardware watchpoint** on `gBmSt.playerCursor.y` caught the exact write sequence (CAMERA set it on the lord → `ProcFun_ResetCursorPosition` reset it off-map → decoder runaway). Symbols live in `fireemblem8u/fireemblem8.elf`. For map/render corruption, reach for the watchpoint early.
_Decided: 2026-06-09_

**Chapter injection rides shared module-level helpers, not per-chapter nested copies (#104/#105).**
`inject_ch01`/`inject_ch02` grew as copy-paste siblings (the 2026-07-02 audit's top scaling risk
before ch03--ch08). The truly-twin nested helpers are hoisted to module level in
`tools/build_campaign.py` (just above `inject_ch01`): `_split_script_beats`, `_cutscene_fid`,
`_stage_beat`, `_register_chapter_map`, `_retarget_host_chapter`, `_ally_unit_entry`,
`_enemy_unit_entry`, `_prepend_defeat_quote`, `_write_chapter_title_card` -- everything
chapter-specific rides in as arguments. **New chapter injectors (ch03+) MUST build on these
seams instead of copying `inject_ch02`.** Genuinely divergent logic (cast loops, event/scene
wiring, per-beat text overrides) stays per-chapter -- where a "twin" differed at all it was
parameterized or left duplicated, never silently unified. Verified byte-identical: a one-off CI
gate built main's ROM and the refactor's ROM against the same mock base ROM -- equal SHA-1
(`0c374bc5`, PR #105 `rom-diff` run). Follow-ups deliberately out of scope: deployment-schema
normalization across chapter YAML + a generic YAML-driven `inject_chapter()` entry point.
_Decided: 2026-07-02_

**Chapter deployment schema: ONE shape, gated (#107).**
All deployment data lives inside the chapter YAML's `deployment:` block -- `deploy_limit`,
`deploy_slots`, prose `note`, `green_allies`. `player_units:` is the single alternative,
only for a fixed-roster chapter with no prep screen (the prologue). Kills the audit-2.2 drift
(four incompatible shapes across 9 files; three different access paths in code). ch01/ch02
migrated; consumers (`inject_ch01`/`inject_ch02`, `difficulty.py chapter_deploy_limit`) read
only the block. Gate: `check.py check_chapter_deployment_schema` (CI + pre-commit) --
top-level `deploy_limit`/`deploy_slots` are rejected, slots must match the limit (the slot
list IS the cap template), an `active` chapter needs a machine-readable `deploy_limit`
(prose caps are for `planned` seeds), `green_allies` entries need id/class/level/position.
The #105 hoist also finished here: `_split_event_beats`, `_require_beat_count`, `_make_fid`,
`_emit_scene_beats`, `_classed_cast`, `_deploy_cap_entries`, and `_ally_unit_entry`
parameterized over allegiance/autolevel/ai (ch02's `green_entry` copy retired). Verified:
old-vs-new injection into a clean submodule against the same mock base ROM diffs empty
(byte-identical generated sources), full test suite + drift guard green.
_Decided: 2026-07-02 (CLAUDE; audit 2.1/2.2 follow-through)_

**A retile inherits vanilla's terrain; the tileset's terrain table is ours to author (#25).**
A chapter that repaints a vanilla layout changes ART ONLY. Every cell keeps the terrain vanilla
gave it, because terrain is what the map MEANS: move cost, avoid, defence, and which menu the
engine offers. When a painted tile carries the wrong role, the fix is to author that metatile's
terrain byte in OUR vendored copy of the tileset -- never to swap the tile, which silently
overrides the map author's eye to chase a data problem. ch05 needed exactly three bytes
(`port-or-town-winter` metatiles 943/976/1010, `WALL` -> `FENCE`).
Enforced by `import_map_layout.validate_terrain_matches_vanilla`, which runs for EVERY tileset
and fails the import naming the cells. Its predecessor `validate_vanilla_retile` only ever ran
for `snowy-bern`, which is how ch05 drifted 11 cells `FENCE` -> `WALL` unnoticed: those two are
identical in every table except `TerrainTable_MovCost_Fly*` (a fence is flyable, a wall is not),
so the map would have quietly walled out Pinky, our only flier -- the ch04 unobtainable-village
failure class exactly. A blank canvas driven from `--vanilla` now stamps `vanilla_layout` so the
check has something to compare against.
_Decided: 2026-08-07 (Nicolas: "we're re-tiling so just copy vanilla's terrains")_

**A vanilla layout's tileset is resolved, never inferred from asset-table position (#25).**
`gChapterDataAssetTable` groups a tileset's `ObjectType`/`MapPalette`/`TileConfiguration` before
the layouts that ride it -- but only usually. FE8 inserts Ch5x at slot 5, so `Ch5Map` sits after
tileset 3's group while riding tileset 2. A backward scan mis-resolves **54 of the vanilla
layouts** (`Ch4Map` and `Ch5Map` among them) and renders correct geometry through the wrong art:
authoritative-looking, and worse than no reference when a retile is being painted against it.
Resolve through `chapter_settings.json` via `map_tileset_tool.vanilla_layout_tileset_assets`.
Why this surfaced only at ch05: every earlier reskin (Prologue/Ch1/Ch2/Ch4) rides tileset 1, and
ch03's `Ch3Map` sits immediately after tileset 2's group, so the scan happened to be right.
_Decided: 2026-08-07 (CLAUDE; found painting ch05, fixed with 4 guard tests)_

**A tileset's unused slots are declared by `TERRAIN_NONE`, not by a filler colour (#25).**
The editor palette filtered unpaintable slots by probing for solid ORANGE, which is one
tileset's convention: `port-or-town-winter` marks its 144 unused slots solid TEAL, so every one
appeared as a brush. Terrain `0x00` is the tileset's own declaration and generalises
(snowy-bern 96, snowy-fields 172, cave-interior 5). Verified no committed map paints one.
_Decided: 2026-08-07 (CLAUDE)_

**Tileset vendoring is a one-command import; Ch3's cave tileset is `cave-interior` (#40).**
FEBuilder/FE-Repo tilesets need NO toolchain (no grit / Map Hacking Suite): the
`.mapchip_config` is byte-identical to the decomp tile config (verified twice: Snowy Bern #41,
Cynon's Mineshaft #40) and the 256x256 mode-P object-palette PNG is 4-bit local indices over a
banked 256-color palette, packing straight to `.4bpp` + `.gbapal` (first 10 banks). So
`map_tileset_tool.py import <config> <png> tilesets/<name>` is the whole pipeline, with a
TSA palette-bank guard (rejects banks >= 10 the FE8 map BG palette can't carry). Proof
standard for an import: assemble the asset's own Tiled test map (`render-tmx`) and pin it
against a reviewed render -- `cave-interior` (Cynon's Mineshaft, Gray; CC, cross-engine use
endorsed in its CREDITS) reproduces `docs/demo/ch03-mineshaft-tileset-demo.png` pixel-exact,
gated in `tools/test_map_tileset.py`. Engine seam: `_register_tileset(campaign, name, Stem,
comment)` registers any vendored tileset's asset-table entries (winter now rides it);
`_register_chapter_map(maps_dir, layout, comment)` points a chapter map at whichever registered
tileset the layout's own `.json` `tileset` stamp names (resolved via `TILESET_STEMS` -- no
per-call tileset argument).
Layout JSONs (editor export + compiled `<map>.json`) now stamp their `tileset`, so
`import_map_layout.py` compiles + previews on the right one. The map editor gained the
custom-canvas mode for non-reskin chapters: `gen_map_editor.py --tileset=cave-interior
--blank=WxH [--fill=N] [--ref=<image>]` (the `--ref` pane is for painting against the book's
Gem-Mine blockout, per the Ch3 layout pivot). `cave-interior` itself registers when the ch03
injector lands (#23) -- registering it with no consumer would be dead ROM bytes.
_Decided: 2026-07-02 (CLAUDE; #40 tasks 1-2 -- the "small converter, not a toolchain" call
from the 2026-06-29 session held)_

---

## Documentation Model

**Three tiers; a per-chapter fact lives in exactly one place (the YAML)**
The doc set kept duplicating per-chapter facts across the YAML, `PRD.md §7`, a hand
table, and the pacing ref — so every story change forced a multi-file resync. The
settled model:
- **Tier 1 — Source of truth = the chapter YAML.** `campaigns/rime-of-the-frostmaiden/chapters/ch*.yaml`
  is authoritative for every per-chapter fact (objective, recruits, enemies, map,
  rewards, `unlocks_chapter`). Edit the YAML; nothing else.
- **Tier 2 — Generated index.** `docs/CHAPTERS.md` is **generated** from the YAML by
  `tools/gen_chapter_index.py`. It is never hand-edited; regenerate after any chapter
  change — `tools/check.py` fails (pre-commit + CI) if the committed index is stale.
  "The data is the doc."
- **Tier 3 — Durable "why" docs, hand-written.** `decisions.md` (settled decisions),
  `roadmap.md` (provisional post-MVP Act II–V scaffold — chapters with no YAML yet),
  `fe8-pacing-reference.md` (FE8-only cadence/reward rules), `PRD.md`
  (vision/scope/architecture/roadmap pointers). These hold rationale and
  forward-looking planning, **not** per-chapter tables.
Rule: do not re-introduce a chapter breakdown table into `PRD.md` or any hand doc —
point to `CHAPTERS.md` / the YAML instead.
_Decided: 2026-05-31 (retires the hand-maintained `chapter-outline.md`)_

**Chapter cadence taxonomy (the `cadence:` field)**
Each chapter YAML carries a `cadence:` token; the generator maps it to one of four
FE8 pacing emoji for `CHAPTERS.md`: 🟥 big-battle/boss · 🟦 breather/intro/escort/travel ·
🟨 sidequest/gimmick · 🎬 scripted set-piece. Current tokens: `tutorial`,
`full_party_intro`, `breather_defend` (🟦); `gimmick_multilevel`, `monster_debut`
(🟨); `first_boss`, `big_battle_gray` (🟥); `marquee_setpiece`, `scripted_defeat`
(🎬). Add a new token to `CADENCE` in `tools/gen_chapter_index.py` when a new pacing
beat appears. The cadence *rules* (why this rhythm) live in `fe8-pacing-reference.md`.
_Decided: 2026-05-31_

**Playtest test-chapter build (`make TESTCH=1`)**
`build_campaign.py --test-chapter` re-activates the dormant `inject_test_chapter`:
New Game boots **straight into a Ch1 sandbox** (vanilla Border Mulan map, hosted at
chapter slot 1 *in place of the prologue*) with the whole classed cast deployed and
the (reskinned) foes loaded, all cutscenes/objectives stripped. It skips the ~5-min
prologue grind for fast in-engine spot-checks (art, battle anims, balance). Mutually
exclusive with the prologue (both host slot 1); the real "Iron Trail" Ch1 at slot 2 is
untouched, and the default `make` (no `TESTCH`) still builds the full prologue→Ch1
campaign. Pairs with the playtest harness as the no-grind path into a fightable chapter.
_Decided: 2026-06-23_

---

## Working Conventions (Definition of Done)

**Why this section exists:** the project drifted because the plan was written up front,
then implementation pivoted (Python not TS, decomp-native not Event Assembler, stock
classes not homebrew) and the canonical docs/issues were never reconciled. The same
fact lived in CLAUDE.md, PRD.md, README, rules-mapping, decisions.md, and GitHub, so
no update ever propagated. These conventions keep a single source of truth.

**Single source of truth — link, don't restate.** Each fact lives in exactly one place:
- *Settled decisions & rationale* → this file (`decisions.md`).
- *Per-chapter facts* → chapter YAML → generated `CHAPTERS.md`. *Unit facts* → unit YAML → `CLASSES.md`.
- *Work backlog* → GitHub issues (milestones M0–M4).

**HANDOFF.md is authored on `main` only (2026-07-30).** Gated by
`check.py check_handoff_only_on_main`; a branch may leave it untouched or sync it to main's
tip, but may not author its own. Refresh it on main *after* a merge, never on the branch.

*Why it needed a gate rather than a habit.* HANDOFF describes **global** live state, but it
is a tracked repo-root file — so every branch and worktree gets a private copy that quietly
stops describing the project and starts describing *the project as that branch last saw it*.
Merge the branch and the stale copy overwrites main's. With one short-lived branch at a time
this never surfaced: every HANDOFF commit before 2026-07-21 landed on main. Two long-lived
parallel branches (ch04 and ch05, nine days) made divergence certain, and the last merge won
regardless of which copy was newer. The ch05 merge put ch04 back to a "WIP checkpoint" four
committed stages out of date; it was only caught because `git pull` refused to clobber an
unrelated local edit.

This is the same root cause as *"feature-flow only works if each feature LANDS before the
next starts"* (below), showing up in a file instead of a rebase — and it had **already been
caught once**, on 2026-07-21, with the mitigation "keep the copies in sync". That is a
memory, not a control, and it failed nine days later. Hence a check: the guard passes the
two states that are actually safe (untouched — git's 3-way merge keeps main's version; or
byte-identical to main's tip, the ideal state for a worktree people read HANDOFF in) and
fails only a branch carrying live state it does not own. It reports *skipped* rather than
*violated* when it cannot see a base, because a guard that cries wolf gets bypassed.
- *Live state* → the single **`HANDOFF.md`** (one trunk, feature-flow — the per-track handoffs were retired 2026-06-24); `/handoff` refreshes it in place. Keep it lean: live Now/Next + gotchas + pointers, no per-session history (that's `git log` + closed issues). *Vision/pitch* → `PRD.md` (no specifics that live elsewhere).
- `CLAUDE.md` is lean **operating instructions + pointers**, not a fact store (a bloated CLAUDE.md gets ignored). If a fact belongs in two docs, one of them should link instead.

**Record decisions when made.** Any change that alters architecture, scope, tooling, or a
settled rule gets a dated entry here in the same session — ADR-style, while context is
fresh. Don't leave it in chat or agent memory only.

**Definition of Done for a change:**
1. Code/data change ships with its doc + YAML updates **in the same commit** (no "update docs later").
2. If it completes tracked work, the commit/PR says `Closes #N`; if it changes scope, open/retitle the issue.
3. `make` builds green; `tools/verify_text.py` is clean after any text change.
4. New non-obvious decision → an entry in this file.
5. Don't commit the `fireemblem8u` submodule pointer (our decomp edits are build artifacts).

**Commits:** imperative subject; reference issues (`Closes #N` / `Refs #N`). Co-author trailer per repo norm.

**Discipline is mechanized, not remembered.** As much of the above as can be is enforced
by machine, at the moment work happens, so it doesn't rely on anyone remembering:
- **`tools/check.py`** is the ONE drift guard (tooling compiles, campaign YAML parses, no doc
  references a missing tool, no resurrected dead concept — denylist, with `decisions.md` exempt
  as the ADR log). Run it with **`make check`**.
- A **git pre-commit hook** (`tools/hooks/pre-commit`, enabled via `core.hooksPath` by
  `setup-toolchain.sh`) runs `check.py` on every commit — **drift literally can't be committed**
  (bypass a genuine exception with `git commit --no-verify`).
- **CI** (`.github/workflows/checks.yml`) runs the same `check.py` plus the real make-green build
  (mock baserom) — the backstop.
- **Known limit:** none of this catches arbitrary prose that contradicts the code without a
  denylisted term. That residue is covered by *single source of truth* (the less a fact is
  restated, the less can drift) and by the agent running `make check` and reporting the result
  when asked "is it clean?" — not eyeballing. When a concept is retired, add its term to
  `DEAD_CONCEPTS` in `check.py` so it can't come back.
_Decided: 2026-06-04_

**Process: the superpowers workflow layers ON TOP of this knowledge architecture (not a replacement).**
The repo predates the superpowers plugin; the two are orthogonal. Superpowers is a per-task *process*
(brainstorm → spec → TDD → verify → review → finish-branch); the conventions above are the *knowledge
architecture* (single source of truth, ADRs here, issues-as-backlog, docs generated from YAML, the
`check.py` drift guard). We adopt the superpowers process habits where additive and keep this knowledge
architecture authoritative — it is the more drift-resistant half (a standalone `docs/superpowers/specs/`
design doc would be a fourth place a spec can rot, invisible to the drift guard). **Override:** the
brainstorming skill's spec lands as an ADR here (the decision) + a GitHub issue (design + execution
checklist), NOT a `docs/superpowers/specs/` file — don't reintroduce that path.
_Decided: 2026-06-19 (Nicolas)_

**Delivery model: chapters ship as vertical slices through a CD pipeline.**
The unit of delivery is a *playable* chapter slice (map + events + enemies + cast-at-parity + portraits +
draft dialogue), shipped to the friend group; polish (custom battle anims, final portraits, final
dialogue) is a later layer applied to an already-playable slice, so gameplay is testable before the art
exists. Every slice passes the same gates before friends see it: the drift guard (`check.py`), balance
parity (`make difficulty CH=chNN`), and stability (boots + completes crash-free). Two parallel tracks: the
**content track** (author each slice — sequential, needs Nicolas / voice bibles / DM notes, un-swarmable)
and the **pipeline track** (the CI gates + injection tooling — parallelizable, the part agents accelerate),
which meet at the gate. The same machine feeds the post-MVP back half (Ch9–21) as the DM notes land.
_Decided: 2026-06-19 (Nicolas)_

**Parallel work model: per-instance git worktrees for build isolation, not branch-per-track.**
The two tracks above run as two Claude instances against trunk. The load-bearing requirement is
**build isolation**: `make` mutates the `fireemblem8u` submodule working tree, so two instances in
one checkout would race and corrupt each other's build. Each instance therefore gets its own
**git worktree** on a short-lived `inst/*` branch (git 2.50 gives each worktree its own submodule
gitdir under `.git/worktrees/<wt>/modules/` — verified isolated). Trunk-based discipline holds:
small frequent commits, integrate to `main` often, no long-lived branches (the earlier
branch-per-track idea was dropped as brittle). Bootstrap a worktree with `tools/worktree-setup.sh`,
which inits the submodule from the local object store (no re-clone) and **symlinks** the gitignored
toolchain (`agbcc` + native binaries + `baserom.gba`) from the primary checkout — the compilers are
static and read-only during a build, so sharing them is safe and instant; isolation is only needed
for the source/build tree. Worktrees are work tracker #50. The file-level engine/content seam (below)
is preventative polish on top of isolation, not a prerequisite for it.
_Decided: 2026-06-19_

**Engine/content file seam: the 5 campaign-agnostic engine hooks live in `tools/inject/`, not `build_campaign.py`.**
So the pipeline track never has to open the content track's file. `tools/inject/decomp.py` holds the
shared decomp-patch primitives (`_find_brace_block`, `_replace_brace_block`) + the decomp paths both
sides patch; `tools/inject/engine_hooks.py` holds the 5 hooks (player-start-cursor guard, terrain-name
guard, battle-map-kind fallback, lord-select, lord-floor) + their engine-only path/flag constants.
`build_campaign.py` imports from `decomp` and orchestrates `engine_hooks.*`. The 6 sprite/palette
injection hooks **stay** in `build_campaign.py` (content-owned): new chapters bring new cast art, so
that machinery belongs with content — which is why this is the *narrow* (5-hook) split, not all 11.
Done **preventatively** rather than "when it bites": the seam is already known (waiting for a merge
conflict teaches us nothing new) and a silently mis-resolved conflict could drop an engine hook — the
exact failure `check.py check_engine_guards_present` exists to catch. That guard is rewritten to assert,
per hook, that it is *defined* in `engine_hooks.py` AND *called* (`engine_hooks.<fn>(...)`) from
`build_campaign.py`; both arms verified to bite. The refactor is behavior-preserving — proven by a
byte-identical ROM (md5 unchanged) plus `lordfloor`/`ch01win` playtests. Work tracker #50.
_Decided: 2026-06-19_

**Coordination model: feature-flow over fixed lanes.** We first split work into two fixed lanes
(content = `campaigns/**` + `build_campaign.py` + art tools; pipeline = `difficulty.py`/`fe_combat.py`/
`check.py`/`playtest/**`/`build.sh`/CI) and **enforced** them with a file-glob ownership guard
(`check.py check_lane_ownership`, keyed off the `inst/<track>` branch; #55) because the seam was
honor-system and got crossed. The guard worked, but the lanes were the wrong *shape*: real features
routinely **span** the glob seam — the per-chapter parity gate (gate + `balance_locked`), adding a weapon
(combat-model map + `WEAPON_ITEM_ENUM`), lord-select UX (bounced engine→content over *file paths*), and
capturing a unit's battle anim (the `record*` scenario **and** the sandbox build it fires on). A fixed
partition doesn't *prevent* collisions on a spanning feature; it **saws the feature in half** so neither
lane can finish-and-verify it. We already patched around it once (the 2026-06-22 "content `record*` are
content spot-checks" carve-out — queued, never landed) and hit the same wall again with `recordrbgtest`
(capture = pipeline scenario, sandbox = content build → un-verifiable from either lane).

The root error was **conflating build-isolation with ownership**. Isolation (two ROM builds corrupt one
tree) is physical and is solved by *a* worktree — any worktree. Ownership (who may change what) is logical
and got welded onto the same `inst/<track>` worktree, forcing work to partition by file type. Unwelded:

- **Feature-flow.** A task = issue → short-lived `feat/<n>-slug` branch off `main` → an **ephemeral**
  worktree (isolation only) → a **PR** → CI + `/code-review` → squash-merge → drop the branch + worktree.
  Concurrency = N feature worktrees, not two fixed slots. A PR may span the old seam; that is the point.
- **The "not my job" propagation test runs at PR review** — push the change through the desks and watch
  the reactions (my job / I can help / no impact / no need to know). Review is where ownership is decided,
  replacing the pre-commit glob block.
- **Engine/content stays a HARD invariant.** The Engine/Content Boundary Rule (no character/chapter/plot
  in `.c`/`.s`) + the engine hooks in `tools/inject/` (`check_engine_guards_present`; its guarded tuple
  is the authoritative list — the count here read "5" long after it grew) are genuine
  decision-hiding and remain gates. The character-name half is now mechanized
  (`check_engine_campaign_agnostic` scans the hand-written engine sources for any campaign id);
  chapter-number / plot-event references stay a review-judgment call.
- **`check_lane_ownership` is demoted to an advisory** desk-span note (no longer a block). The glob map it
  carries is the seed of the **desk map**: each desk = a responsibility + its phone (interface) + its
  cabinet (private files), the design vocabulary enforced at review.
- **Design placement** follows the three reflexes (`CLAUDE.md` → Design placement test): *not my job*
  (push each line to its owner), *no need to know* (no desk reaches into another's cabinet), *futures*
  (judge boundaries by the changes they make cheap; localize decisions likely to change — but don't split
  what has no expensive future, e.g. `harness.lua`).

Supersedes the fixed-lane ADRs (Seam enforcement #55; the 2026-06-22 `record*` refinement; "track work
always in that track's worktree"). The two ADRs above — worktree isolation and the 5-hook engine/content
file seam — **stand**: worktrees are now ephemeral-per-feature, and the file seam is the hard invariant
feature-flow keeps.
_Decided: 2026-06-24 (Nicolas — chose feature-flow + PRs; codified from the "not my job" design review)_

**Feature-flow only works if each feature LANDS before the next starts — parallel unmerged lines on
shared files are what force a rebase every time you come back.** Symptom (2026-07-21): two sibling
branches off `main` — #193 (winter forest fidelity) and the ch04 map slice — were open at once, one a
committed-but-PR-less branch, the other **uncommitted WIP left in its worktree**. Both edited the same
cross-cutting "hot" files (`tools/gen_map_editor.py`, `tools/map_tileset_tool.py`,
`campaigns/.../maps/reskin-learned.json`, and `docs/decisions.md` — every ADR appends near the same
line), and both **independently re-derived** the same vanilla-layout `.bin`→`.mar` reader under
different function names. `main` then moved underneath the stale WIP, and integrating them cost a full
conflict-resolving rebase. The rebase is the *symptom*; the discipline that prevents it:

- **Land each feature end-to-end before starting or resuming the next** (commit → PR → CI → squash-merge
  → delete branch), especially anything touching shared tooling / JSON / `decisions.md`.
- **Never leave a worktree dirty across a session boundary** — at minimum commit a checkpoint on the
  feature branch so `main` can't strand it. Long `HANDOFF.md` "do not lose or revert" lists are the smell
  that this rule is being broken.
- **Reuse, don't re-derive** — grep for an existing helper before writing a new one; two branches solving
  one problem two ways guarantees both wasted work and a merge conflict.
- **Append new ADRs at the END of their section**, not mid-file, so two branches don't insert at the same
  line and collide.

This is the operational half of the feature-flow ADR above (which settled the *structure*); this settles
how it must be *practiced* by any agent (Claude or Codex) picking work up across sessions.
_Decided: 2026-07-21 (post-mortem of the #193 / ch04 parallel-branch rebase)._

**Boot decision localized; bows need a min-range in playtest targeting (the first feature-flow feature).**
The boot cut + New-Game redirect were decided in BOTH `inject_prologue` and `inject_test_chapter` (the
duplication the Coordination ADR cites). Localized to one `_configure_boot(target, montage)` owner called
once from `build_campaign.main()`; the two target injectors no longer re-decide it. This — plus two
playtest fixes — unblocks `recordrbgtest` (capture RBG's bow anim on the `make TESTCH=1` sandbox)
end-to-end: (a) `clearbot.pickTarget` takes a **`min_range`** so a 2-range-only bow isn't parked
adjacent (range 1), where there is no Attack command; (b) `captureAttack`'s target confirm is
**feedback-driven** (press A, cycle targets, until `gProc_ekrBattle` animates) because with several foes
in range the BKSEL select cursor can start off a target. Verified end-to-end on the sandbox AND on
`recordrbg` (no regression). The "menu just opened, settle before the first A" hypothesis was wrong — the
menu was responsive throughout; positioning + multi-target confirm were the real causes.
_Decided: 2026-06-24_

---

**Ch2 load-test: automate the STRUCTURAL half in the harness; the PACING half stays human.**
The only open #22 item was the in-emulator load-test. It splits in two: *structural* (does ch02
LOAD off the real `MNC2(0x3)` chain, not soft-lock, and is it winnable — chwinga load green, the
archer present, surviving chwinga deliver charms) and *pacing* (judging the 5 cutscenes in motion).
The structural half is now machine-verified by the playtest harness; the pacing half is left a
human-at-mGBA pass. **Reached via the REAL chain, not a ch02 sandbox** — a `TESTCH=2`-style boot
would skip the `MNC2(0x3)` transition the load-test most needs to prove, so `reachCh02Map` clears
ch00 + ch01 with the clear-bot and observes the ending→opening→prep chain onto the ch02 map through
the state-driven controller. That
deep chain is paid **once** into a `ch02start` save-state checkpoint (`ckpt_ch02start`, like
`rbgch01`); `ch02` (entry assertions), `smoke_ch02` (soft-lock net), and `clear_ch02` load it. The
3 green chwinga are kept alive during `clear_ch02` (direct HP/def poke) so the charm-gift path
(`CHECK_ALIVE → GIVEITEMTO`) runs deterministically — whether they survive under real play is a
balance question for the human pass, not the wiring test. Charm delivery is verified by scanning
all blue inventories + the convoy (`gConvoyItemArray`) for the three charm ids; the pure membership
core is unit-tested in `test_ch02check.lua`. `clearDrive` was split into a non-terminating
`clearUntilAdvance` (the loop) + a verdict wrapper so the chain helper can keep driving past a win.
_Decided: 2026-06-25 (CLAUDE; brainstormed-then-TDD; assert depth "Core + charm delivery" — Nicolas)_

---

**Clear-bot pathing: BFS march + multi-range + stall watchdog landed; #60 still open on boss-breach.**
The #22 work exposed that the greedy clear-bot (#60) can't complete ch01/ch02 unaided. Reworked it
toward a real fair-play completability gate: (a) a **BFS distance-field march** (pure `pathing.lua`,
unit-tested in `test_pathing.lua`) over a walkable map from `gBmMapTerrain` — units route *around*
walls/water toward the boss instead of greedy-Manhattan stranding; (b) **multi-range targeting**
(`clearUnitAct` reads each unit's real `unitAttackRange` instead of hardcoding range 1); (c) a **stall
watchdog** (no-progress turns → `B`-unstick, then a clean `stuck` FAIL); (d) a **bug fix** — a title
screen without a chapter advance is now a game-over, not a false win (old `clearDrive` could PASS a
loss). `clear` (prologue) now passes fair-play. **Not fully closed:** on ch01 the bot marches to the
walled boss-camp (gate at a `TERRAIN_GATE_CASTLE` ringed by walls) but jams ~8 tiles out with a thin
2-unit deploy — the open work is last-mile **breach/unjam** logic (field more units; slip around a
chokepoint; focus-fire the nearest reachable straggler), tracked on #60. Until then `reachCh02Map`
keeps its directed ch01-seize helper (it can't ride the fair-play bot yet). Passability uses a
conservative impassable-terrain set (walls/peaks/water/fence/snag/cliff); high-cost-but-passable
terrain stays passable because the per-turn `selectAndReach` still enforces true reach.
_Decided: 2026-06-25 (CLAUDE; brainstormed-then-TDD; scope "full gate" — Nicolas; landed partial + kept #60 open after the breach proved deeper)_

---

**A stack of PRs lands with MERGE COMMITS, and every child retargets to `main` BEFORE its parent's
branch is deleted.** Squash-merge stays the default for the normal case (one feature, one branch off
`main`). It is the wrong tool for a stack — each PR based on the one below it — because a squash
collapses the parent into a *new* commit that is not in the child's history, so GitHub re-shows the
parent's diff on the child and a rebase + force-push is owed between every merge. Merging with a
merge commit keeps the parent's commits in history, so each child merges clean with no rebase at all
(verified 2026-08-06 landing #237 → #239 → #240 back to back).

The trap that is not obvious: **`gh pr merge --delete-branch` on the parent CLOSES any PR whose base
is that branch.** GitHub does not retarget it, and a closed PR cannot be retargeted afterward
(`Cannot change the base branch of a closed pull request`). The order that works:

```sh
gh pr edit <child> --base main     # retarget every child FIRST
gh pr merge <parent> --merge --delete-branch
```

Recovery if a child is already closed this way: re-push the deleted base ref from its recorded tip
(`git push origin <oldtip>:refs/heads/<branch>`), `gh pr reopen <child>`, retarget it to `main`,
merge, then delete the restored ref. This is why the handoff records each branch tip.
_Decided: 2026-08-06 (Nicolas — merge commits for the stack; the retarget-before-delete rule is from landing #237/#239/#240)_

---

**A lint may not import `build_campaign`, and a limit may not be written down.** Two rules with one
root, both from the code review of the #237/#239/#240 stack (#241).

**(a) `tools/check.py` runs in CI's `checks` job, which installs pyyaml and nothing else.**
`check_hosted_chapters_declared` imported `build_campaign` to reach the host-slot constants, and
`build_campaign` imports Pillow at module scope — so the gate would have failed *every* push with
`build_campaign does not import: No module named 'PIL'`: a red check that names the wrong problem
and teaches everyone to ignore it. The fix is structural, not a `pip install`: the host-slot
registry moved to **`tools/inject/hosts.py`**, stdlib-only like `inject/decomp.py` beside it, and
`build_campaign` re-exports it so every call site still reads `bc.CH04_HOST_INDEX`. The rule
generalises — **a lint imports the smallest module that owns the fact, or reads the source with
`ast`; it never imports the build.** `check_purple_bank_blankers_known` already said so for its own
constants; this makes it the standing rule.

Two more defects fell out of moving it. Discovery matched `CH(\d+)_HOST_INDEX`, so the **prologue
was invisible** — `PROLOGUE_HOST_INDEX = 1` was not in the collision map, and a later
`CH05_HOST_INDEX = 1` would have passed the guard and quietly overwritten the prologue's events.
And enrolment was a *convention*: `inject_ch05` with a typo'd constant is simply not discovered, and
every guard built on the registry then passes with one chapter fewer and no complaint — the exact
ch04 failure class #138 set out to close. `undeclared_injectors()` now reads `build_campaign`'s
source with `ast` and fails the build on an injector that enrols nothing.

**(b) A limit that kills everything at once must be MEASURED, not documented.** `harness.lua` sits
at Lua's 200-local ceiling, and the remaining margin was written as prose — "two free slots" — in
`harness.lua`, `check.py` and `HANDOFF.md` simultaneously. It was wrong in all three within one PR
of being written: #240 spent a slot and updated no comment. Measured, the margin was **one**.
`check_lua_local_headroom` now appends probe locals until the chunk stops compiling, prints the real
number on every `make check`, and fails at zero. Same reasoning retired the hand-written
`LUA_CHUNKS` tuple, which listed 4 of the 9 chunks `harness.lua` loads — a syntax error in
`recorder.lua` or `liveness.lua` killed every scenario with the gate green. **If a number about our
own code can be computed, compute it; a hand-maintained one is a comment that lies eventually.**
_Decided: 2026-08-06 (code review of #237/#239/#240; #241)_

---

**The controller's rule order is load-bearing, and its stall detector belongs where it can be
tested.** Three corrections to the #236/#238 contract, all from the same review (#241).

**Order: the more SPECIFIC state outranks the more general one.** `yes_no_choice` was placed above
the passive `std_event` rule (that was #232's fix) but *below* `dialogue_wait` — and that pairing is
the same bug wearing a disguise: `dialogue_wait` answers "press A", `YesNoChoice_Loop_KeyHandler`
CONSUMES that A, and the prompt is answered by accident with the run green. A live `YesNoChoice` in
its key handler owns the A button whatever else is on screen. The order is now pinned by tests
(`talk_wait`+`yes_no`, `menu`+`std_event`, `map_fade`+`std_event`), because rule order is the one
property of this design that no single rule's tests can protect.

**Liveness: `PROC_REPEAT` is how every long-running FE8 proc works, so a constant `scrCur`/`idleCb`/
`lockCnt` is not evidence of a stall.** `ProcScr_StdEventEngine`, `gProcScr_TalkWaitForInput`,
`sProcScr_BMXFADE` and `gProcScr_YesNoChoice` are all `PROC_REPEAT`, holding those three fields
constant for an entire scene; the signature can only see churn. It now includes `sleepTime` (a proc
counting down a timed wait IS progressing — and `INSPECT.snapshot`'s own `frozen` field already
compared it, so the feature held two contradictory definitions of "not moving") and the pool count.

**Placement: the thing that decides FAIL cannot live where nothing can load it.** `INSPECT.watch`
was in `harness.lua`, which only runs inside mGBA, so the most flake-prone component in the stack
had zero tests. The decision moved to `controller.lua` as `stallWatch()`/`procSignature()` — pure,
unit-tested — and the harness kept only the logging. As a bonus it calls `explain()` once per hold
instead of once per frame of a 36000-iteration loop. **General rule: pure decisions live in
controller.lua (unit-tested, no ceiling); harness.lua drives the emulator.**
_Decided: 2026-08-06 (code review of #237/#238/#240; #241)_

---

## Combat System

> **2026-05-28 — Combat resolution reverted to vanilla FE.** The earlier "Hybrid
> d20/FE" decision (May 2026) is **superseded**. For playability the combat *rules*
> stay vanilla FE8 (hit%/avoid/might, FE crit, FE doubling); **D&D is flavor only**.
> The d20 survives at most as a **cosmetic flourish on a crit**, never as the
> resolution system. **AC, saving throws, and advantage/disadvantage are dropped**
> as mechanics (see below). Rationale (Nicolas): "the rules need to stay FE or the
> game won't play the same" — the FE-strictness spine. The four implementation
> sub-questions were ratified by Nicolas on 2026-05-28: d20 = cosmetic-crit-only,
> saves dropped, AC dropped, advantage dropped.

**Combat resolution: vanilla FE8 hit / avoid / might**
Hit, avoid, might, and crit are computed exactly as vanilla FE8 (`bmbattle.c`,
left intact). No d20 attack roll; no Armor Class. The D&D reskins below are
flavor/UI only and never change the math.
_Decided: 2026-05-28 (supersedes the May 2026 hybrid-d20 decision)_

**d20: cosmetic crit flourish only**
When an FE crit fires, the battle UI may play a brief "d20 lands on 20" flourish
for D&D feel. It does not gate or alter the hit — resolution is pure FE. This is
the only place the die appears.
_Decided: 2026-05-28_

**The d20 flourish SHIPS (#11): a gold nat-20 pops at the crit flash's teardown.**
Implementation seam (decomp-traced): FE8 rules a round a crit in `banim-battleparse.c`
(BATTLE_HIT_ATTR_CRIT → the crit anim modes); the C08 anim command fires the white
crit flash (`ProcScr_efxCriricalEffect*`, `banim-efxhit.c`) and never blocks the script,
and the flash's BG proc tears BG1 down after 17 frames. The hook
(`engine_hooks._inject_crit_d20_flourish`, guarded in `check_engine_guards_present`)
draws the die AT that teardown — **proc-less by design** (review-hardened): registered
once, then the vanilla effect lifecycle owns BG1 (a successor effect — a brave second
hit, a magic counter's spell background — draws over it; the scene exit resets it), so
nothing of ours can blank a newcomer's tilemap later. Covers BOTH crit-flash teardowns
(plain + pierce); Silencer is deliberately excluded — it has its own distinctive Chill
flourish, and no MVP cast member can Silencer. Neither the flash nor combat pacing
changes; FE crit math stays the sole trigger. The die is a centered HUD overlay copied
through the non-mirrored tilemap path (attacker side never mirrors the "20").
**Engine/content split:** the hook is campaign-
agnostic; the ART is the campaign's (`battle_anims/d20-crit.png`, PIL-authored gold d20)
— no asset, no flourish, pure vanilla crits. Asset pipeline: PNG → 4bpp sheet (tile 0
blank) + 16-color pal + 30×20 TSA, wrapped in stored-form GBA LZ77 (literal-only blocks
— always-valid input for `LZ77UnCompWram`, no compressor to vendor), incbin'd into
`data/data_banim.s`. `test_crit_flourish.py` decodes the injected bytes back and pins
them pixel-exact against the source PNG; the static preview Nicolas reviews is
`docs/demo/d20-crit-flourish-preview.png` (rendered FROM the injected bytes). Deferred:
map-battle (no-anim) crits — a different rendering path (`mapanim_spellassoc.c` MU
flash); and in-emulator motion review (`recordanim` on a crit) at the next capture
session.
_Decided: 2026-07-02 (CLAUDE; decomp-traced; closes #11's anim-mode scope)_

**AC (Armor Class): dropped as a mechanic**
Defense is FE's `DEF` (vs physical) and `RES` (vs magic), plus speed/luck/terrain
avoid — exactly as vanilla FE. There is no separate to-hit target. The `ac:` source
values and `d20_fields` blocks in the PC YAMLs are retained only as
flavor/source-of-record; nothing in resolution reads them.
_Decided: 2026-05-28_

**Saving throws: dropped → vanilla FE magic**
No DCs, no save rolls. Status staves (Sleep/Silence/Berserk/Poison) always-hit per
vanilla FE; offensive spells resolve through FE magic combat (MAG vs RES, FE
hit/avoid). The `save:` / `save_dc:` fields throughout the PC YAMLs are flavor only.
_Decided: 2026-05-28_

**Advantage / disadvantage: dropped**
No advantage concept. Positioning matters through standard FE terrain bonuses and
the weapon triangle only.
_Decided: 2026-05-28_

**Damage: vanilla FE armor-subtraction model (nothing layered under it)**
`Damage = Might − Defender.DEF/RES`, where Might = the FE weapon/tome's Might + the unit's STR
(physical) or MAG (magic) — all FE-native. Weapons are FE items; their Might comes from the FE
weapon tier (Iron/Steel/Silver…), **not** from a 5e die or any conversion. No weapon dice, no
ability modifier, no D&D multiplier (see the damage-type decision below). Do NOT import 5e HP/damage
values — FE stats and growth tables (HP caps ~60–80) are authored directly.
_Decided: 2026-05-28; sharpened 2026-05-29 (FE stats/Might only — no 5e die-to-might conversion)_

**Critical hits: vanilla FE (skill-based rate, ×3 damage)**
FE's native crit — crit rate from SKL/weapon, triple damage. The earlier "roll
weapon dice twice on nat 20" is dropped with the d20 resolution. Killer/high-crit
units use vanilla FE crit-rate bonuses.
_Decided: 2026-05-28 (supersedes the May 2026 roll-twice crit)_

**Doubling: vanilla FE (unchanged)**
`AttackSpeed_attacker − AttackSpeed_defender ≥ 4` → attacker attacks twice.
_Decided: May 2026 (still current)_

**Damage-type resistance/vulnerability/immunity: DROPPED as a mechanic**
The 13-damage-type resistance multiplier (×0.5 / ×2 / ×0) has **no vanilla FE analogue**
and would modify FE damage under the hood — exactly the kind of D&D bolt-on we're avoiding
(Nicolas, 2026-05-28: "that's not part of the FE combat system… it should not conflict with
vanilla FE under the hood"). So:
- **Damage types are not a game feature.** No resistance/vuln/immunity, and (2026-06-04) no
  damage-type label, enum, or UI icon either — the whole apparatus was a vestige of the old
  "D&D combat layer." Combat and item data are pure vanilla FE8.
- **Iconic matchups use vanilla FE weapon effectiveness, keyed to the target's CLASS.**
  *(SUPERSEDED 2026-07-02 — Nicolas: even data-level effectiveness additions violate the
  vanilla-combat principle; the #8 fire-vs-ice implementation was reverted. See "Iconic
  matchups are OUT" in the dated decisions below.)*
  FE8's effectiveness system has eight class-keyed categories (`src/data_items.c`
  `ItemEffectiveness_*`): Armor, ArmorAndHorse, Horse, Flier, FlierAndMonsters, Monsters,
  Dragon, Swordsman. Effectiveness is a property of a weapon against an enemy class —
  Hammer/Armorslayer vs armored Knights, Wyrmslayer vs dragons, bows vs fliers, and the
  monster-effective weapons (the Sacred Twins + Audhulma/Shadowkiller/Fiendcleaver/Brightlance/
  Beacon Bow) vs monster-class enemies (skeletons, gargoyles, ice trolls/cyclops, …). Damage
  types stay flavor labels; effectiveness keys off class alone. Use sparingly — most weapons
  carry no effectiveness at all.
- **No `engine/damage-types/` module at all** — no resistance table and no flavor-label tag.
  Elemental/damage flavor is deferred to the **battle-animation art** (a spell's visual can evoke
  its D&D inspiration); see Weapon & Magic §.
_Decided: 2026-05-28 (resistance dropped); 2026-06-04 (labels/enum/icon dropped too — vestigial)_

**Hit-rate tuning: vanilla FE, no special floor needed**
With vanilla FE hit/avoid restored, FE8's native 70–95% hit norms apply directly —
the old d20-variance problem and the "skill floor" mitigation are moot. Tune
per-chapter via enemy stats/terrain as in any FE hack.
_Decided: 2026-05-28 (supersedes Option A d20 hit-rate tuning)_

**Field parity: our chapter N fields what vanilla FE8 chapter N fields — both sides.**
Difficulty progression is inherited, not re-derived: each chapter YAML carries a
`deploy_limit` equal to vanilla chapter N's player deploy-slot count, and its enemy
roster mirrors vanilla chapter N's counts/levels/AI postures (classes goblin-/monster-
skinned to our fiction). The whole cast being *recruited* early (the Northlook intro)
doesn't widen the field — Pick Units chooses who takes it, the chosen lord (#42) is
force-deployed. Reference table: `docs/fe8-pacing-reference.md` §1b ([decomp]-sourced:
ally array sizes in `events_udefs.s`; per-chapter enemy tables decoded as each slice
begins). Map *layouts* may be borrowed from any vanilla chapter (ch01 rides Ch13a's
geometry); the **cadence anchor is always the same-numbered vanilla chapter**.
Sanctioned deviations are recorded per-chapter in the YAML (ch01: 4-at-start instead
of vanilla's 2+2 staggered arrival — staggering doesn't survive a player-picked party).
_Decided: 2026-06-10 (Nicolas; "1:1 alignment to the units on the field, chapter by chapter")_

**Party-side parity: donor personal lines + a per-lord survivability floor — never enemy or stat inflation.**
"Field parity" (above) mirrors vanilla's enemies and deploy cap; this is the party half. Each PC
inherits its class-matched vanilla donor's **personal base stats** (`build_campaign.py` →
`BASE_DONOR`; the build already inherits that donor's growths + ranks via `STAT_DONOR`, so base
inheritance extends the same path). Shamans take **Ewan (Ch1-appropriate) bases** (Knoll's lv9 bases are too hot
for Ch1), with **growths split toward their promotions** — Marty → Knoll → Druid, Meesmickle →
Ewan → Summoner (#45). This lifts the cast off its "naked class" lines — personal bases were all 0, i.e.
generic-enemy frailty plus a Spd-0 doubling cliff — to **vanilla parity on both durability and
kill-throughput** (`tools/difficulty.py`). The player-chosen lord (#42), who must survive,
additionally gets a runtime per-lord **HP/Def top-up to a ~5-enemy-hits-to-down floor** (0 for
tanky picks, +7/+4 for the glass shamans) so no lord choice is a trap; it is **one-time** (fades as
the party levels — Jagen-style). Campaign-long strength scales by matching **vanilla's recruit
cadence** (bodies + promotions), not stat inflation; enemies stay vanilla; and there is no
Seth-tier god-unit — the cast are all player characters, all eight (**Pinky included**), and must
all matter. The per-chapter **difficulty engine** is `tools/difficulty.py` (`make difficulty
CH=chNN`), built on the tested combat core `tools/fe_combat.py` (the decomp's own formulas);
execution plan + full spec: issue #45.
_Decided: 2026-06-18 (Nicolas; difficulty analysis session — supersedes the open "Ch1 difficulty" item)_

**Difficulty is checked in fidelity tiers, and the roster↔map loop is bidirectional — a chapter is not "difficulty-verified" until it has actually been played.**
`make difficulty` is **aspatial by construction**: it sums per-unit offense/durability as if every fight were 1-on-1 on open ground, all at once. That makes its *relative-to-vanilla* read trustworthy (both sides share the same crude proxy, so the bias cancels) but leaves it **blind to terrain, unit placement, AI behavior, fog, and the weapon triangle** — the factors that actually set FE difficulty, all of which are *map-layer* properties that don't exist until units are placed. So difficulty is verified in tiers, not one shot:
1. **Roster ballpark (aspatial):** `make difficulty` — total force ≈ the `parity_reference` twin. Fast, needs no map. The force-magnitude gate.
2. **Author map + placement**, guided by the parity twin's own spatial structure (below).
3. **Spatial check (map-aware):** read the placed positions/AI/terrain for where the pressure *actually* lands (crossfire pockets, chokepoints, reinforcement timing) — the layer tier 1 can't see. **This can push back on the roster, not just the map** (if the terrain makes N ranged units an unfair crossfire, the fix may be "fewer units," so the roster is not frozen once the map starts).
4. **Runtime validation:** build + play (harness or human). *This* is the ground-truth gate. Tiers 1–3 exist to reach tier 4 fewer times with fewer surprises; they inform, they do not certify (see §Operational Gotchas — don't claim difficulty from reasoning).
5. **Lock:** flip `status: planned` → active; the roster enters the parity gate.

**The tier-3 spatial check = deterministic facts fed to an LLM *analyst* — NOT an LLM *playing* the game.** LLMs are weak at exact grid-tactical *execution* (tile-counting, threat-range math, turn-order) — so an LLM playing the chapter to measure difficulty produces noisy numbers that measure "how badly the bot plays," not the chapter. But an LLM reading *pre-computed* spatial facts and producing a *qualitative* read (where's the danger, what's the trap, is the terrain fair) is in its wheelhouse. Division of labor: **code computes the hard facts; the LLM reads them.** Use the analyst for structure, never for hard numbers (it can't simulate — in validation it self-contradicted on turn-count). Validated 2026-07-17: a **Haiku** analyst, given only vanilla Ch4's placements/AI/stats (chapter name withheld), independently reproduced `make difficulty`'s verdict (ranged-magic-on-squishies is the sharp edge), *found the Mogall crossfire cluster the aspatial tool can't see*, and correctly flagged terrain as the #1 missing input. **YAGNI:** the analyst reads raw coordinates well enough that we are **not** building a reachability/threat-per-turn metric extractor until we feel its absence during real map authoring.
_Decided: 2026-07-17 (Nicolas + CLAUDE; ch04 roster-grounding session — Nicolas pushed on "the model ignores terrain/AI/positioning," validated by the Ch4 analyst experiment)_

**Per-unit ROLES are checked separately from force parity — the per-slot averages hide a monstrous outlier and a boss that folds.**
`threat/slot` sums the whole force and divides by the deploy cap, so a single terrifying unit dissolves into the average and the boss's own durability never appears at all. ch05 passed "PARITY (within band)" while the White Moose out-threatened the boss **1.7×** and sat **2.2× above the vanilla twin's scariest unit** — invisible to every number we printed, because we only ever compared *force to force*, never unit to unit. `difficulty.py role_findings()` now compares the **extremes** against the twin (threat outliers >1.25× its ceiling; a boss out-threatened by a line unit; a boss whose rounds-to-kill is <½ the twin's tankiest; >1 `is_boss`), and prints them under PER-UNIT ROLE CHECK. A `convertible` is exempt from the inversion check — it's neutralized rather than ground down, so out-hitting the boss is a deliberate "avoid me" hazard. **ch04 verified clean** against this (its extremes track vanilla Ch4: 5.0 vs 5.5 threat, and like its twin it fields no boss at all).
Two class facts came out of the ch05 fix and generalise: **(1) a caster boss can never be an armour wall** — vanilla Saar's 12.9 rounds-to-kill comes from Def 11 (2 damage a hit); a Druid has Def 5 and can't reach that at *any* level or terrain (L11 on +30 avoid is still 4.8), so the wall must be **distributed into armoured bodyguards** the party chews through to reach her; **(2) some classes can't be tuned down** — `gwyllgi` is Spd 14 and doubles the yardstick, so the moose is ~2× the vanilla ceiling even at L2. When stats can't fix it, fix the **role**: the moose became a named miniboss + convertible (killing Ravisin breaks her hold), which keeps it terrifying and makes avoiding it the tactical reward for pushing the objective.
Also learned: **for a 1:1 retile the spatial layer is NOT gated on the ROM.** Vanilla `.xPosition`/`.yPosition`/`.ai` (Saar is `GuardTileAI`) live in the decomp and are readable ROM-free. **Terrain is now wired** (`difficulty.py` §Terrain): FE8's own `TerrainTable_Avo_Common`/`_Def_Common` and the terrain enum are parsed from HEAD, and `map_tileset_tool.vanilla_layout_data()` gives tile→terrain for any vanilla layout, so `terrain_at(x,y)` is a decomp read. A chapter unit declares `tile_terrain:` and the role check fights it on that tile (`battleAvoidRate = spd*2 + terrainAvoid + lck`, `battleDefense = terrainDefense + def`; the Common/foot tables, since the yardstick is a foot unit). Note `.xPosition` is a SPAWN point — a unit's `.redas` may walk it to its real post (Saar spawns (13,0), posts (13,1)); read the REDA destination, not the spawn.
**Match the twin's CLASS MIX, not just its totals — the weapon triangle is invisible to the per-slot averages.**
Hitting `threat/slot` and `clear-load/slot` says nothing about *what the player is actually fighting*. ch05 passed parity while fielding **zero** axe units against vanilla Ch5's **eleven** (6 Brigands + 5 Fighters, ~48% of its force) — so the triangle maths a player experiences was completely different from the twin's, and no printed number could see it. Worse, the divergence came from tuning *counts* to recover a metric: two Armor-Knight "frost sentinels" invented to fix clear-load (vanilla Ch5's only Armor Knight **is the boss** — it fields no armour grunts), and then, after removing them, a Mercenary bumped 2→4 (vanilla fields **one**). Both were "what moves the number," not "what does the twin field." The rule: **derive composition from the twin's class breakdown first, then tune levels/weapons to land the metrics** — never invent units the twin doesn't field to close a gap. ch05 now matches Ch5 exactly on Soldier 6 / Archer 3 / Mercenary 1 / Myrmidon 1 with the axe block at 10 of 23 (~43%), and parity *improved* doing it (x1.11 / x0.84). Fighters carry the whole axe block rather than splitting Brigand/Fighter — the ch01 precedent (Fighters so nothing pathfinds over peaks).
_Decided: 2026-07-23 (Nicolas + CLAUDE; "were the sentinels based on Ch5's enemy count?" — they were not)_

**A boss is class base PLUS a personal stat line — that, not the class, is why FE8 bosses are walls.**
`CHARACTER_SAAR` is an Armor Knight *plus* HP+13/Pow+6/Skl+5/Spd+3/Def+2/Res+3/Lck+4. This retires the whole "find a tanky mage class" search: **FE8 has none** (best magic Def is 5 — Sage/Mage-Knight/Gorgon, all 10% Def growth), and the FE-Repo shares *art*, not portable class definitions (a class is just a table row each hack sets itself; our own pipeline already clones and rewrites classes). So Ravisin stays a Druid with Flux and her existing art and simply gets a `personal:` line (HP+15/Def+5 → ~13.4 rounds, Saar's bar). **Zero art cost, no custom class.**
Scope matters: personal lines are modeled **only in the role check, on both sides** — putting them in the AGGREGATE parity metric shifted every curated baseline (ch02 fell out of band) and made a Def-13 boss undentable, so the aggregate deliberately stays class-base-only on both sides. Two traps found while wiring it: **(1) personal Def and terrain STACK** — HP+15/Def+5 on a throne makes her undentable (`inf`), so it's one lever, not two (the throne is dropped, and the armour bodyguards with it — with a real boss line they were redundant scaffolding, so `frost-sentinel` was removed and `crypt-blade` 2→4 carries the clear-load); **(2) the yardstick's attack is exactly 13, so Saar-with-line takes 0 damage** — the bar therefore falls back to his class-base 12.92 **per boss**, never all-or-nothing (an undentable Saar must not hand the "bar" to Ch5's weaker dentable bandit). That undentability says more about the yardstick being a weak average unit than about the boss — the chapter hands the player an Armorslayer for exactly this.
_Decided: 2026-07-23 (Nicolas + CLAUDE; "why can't Ravisin just be a different class?")_

**Two assumptions this killed, both checked instead of guessed:** (1) **`GuardTileAI` does not mean "on a throne"** — it means "don't chase." Saar's post is plain `TERRAIN_ROAD`, so his 12.9-round wall is **100% class Defense, zero terrain**; the earlier claim that terrain widened the boss gap was wrong. (2) Terrain can't rescue a caster: a throne (+30 avo/+3 def) takes Ravisin from 2.9 → 6.8 rounds — past "folds instantly," still about half of Saar. Hence the split fix: throne **plus** distributed armour (two Armor-Knight bodyguards ≈ 11.7 rounds on the approach). This deliberately gives our boss *more* terrain help than vanilla's boss gets, compensating for Druid Def 5 vs Armor Def 11 — a documented departure, not a mirror. (Anchor regressions pin both reads: Ch5 Joshua stands on `TERRAIN_ARENA_REGULAR` — canon — and Saar on `TERRAIN_ROAD`.)
_Decided: 2026-07-23 (Nicolas + CLAUDE; ch05 boss-role post-mortem — "how did this slip past us?")_

**Corollary — our undead reskins read GLASSY against the parity yardstick, so match clear-load with high-Spd beasts + armored walls, not more fodder or more levels.**
The parity yardstick doubles any enemy with Spd ≤ 4 (Spd 8, iron-sword), which halves its clear-load. Our tomb-flavored undead lean on the slowest FE8 monster classes — `mogall` (Spd ~0–4) and `revenant` (Spd ~1–2) — which get doubled and die in ~1 round no matter their HP/Def, so a force built from them lands high on *threat* but far under vanilla's *clear-load* (the living-soldier twins aren't doubled). Adding levels barely helps (those classes' Spd never clears the threshold) and adding armor (`entoumbed`, Spd ~2) helps only via lower threat, not durability. The lever that actually raises clear-load is composition: the durability spine must be the **fast beasts** (`mauthedoog`/`gwyllgi`, Spd ≥ 10 — never doubled, real rounds-to-kill) plus a few **armored walls** (`entoumbed`, low-threat), with the doubled `mogall`/`revenant` fodder thinned to a garnish. Applied to ch05 (16 undead line + 6 eruption reinf + 1 convertible) this reached PARITY at threat x1.19 · clear-load x0.81 (band's low edge). Expect the same recomposition on the undead-heavy chapters ahead (ch06 Messie, ch08). The static bar is still just a proxy — playtest is the arbiter.
_Decided: 2026-07-22 (CLAUDE; ch05 roster-grounding, #25 — tier-1 of the flow above, ROM-free web session)_

**Refinement (2026-07-23) — the RIGHT fix for the glassy problem is a SKIN divorce, not a composition fight: put undead skins on vanilla INFANTRY classes (the ch01 pattern), and reserve beasts for chapters where beasts are on-story.**
The corollary above is correct physics but its *recommendation* (lean the spine on beasts) was a crutch. The clean fix — adopted for ch05 rev.2 — is the one Nicolas pushed: keep the vanilla FE8 twin's **living-class stats** (Soldier/Fighter/Mercenary/Archer/Armor-Knight/Myrmidon) and **reskin them undead** via `enemy_class_reskins` (exactly how ch01 ships "Vanilla Ch1 enemy table, goblin-skinned"). Then clear-load parity is *free* (living classes aren't doubled; the Armor-Knight is the Def-sink the monster palette couldn't produce) and there is no glassy fight. ch05 rev.2 (risen elven guardians on infantry classes + the lone White-Moose boss) landed threat x1.21 · **clear-load x0.97** — better-centered than rev.1's x0.81. Two further reasons this beats the beast-spine crutch: (1) **narrative variety** — ch04 IS the beast/wolf chapter (the hunt, Marty's parley); reusing wolves in ch05 makes it "ch04 indoors," so ch05's dead-tomb identity requires *not* leaning on beasts (wolves CUT; the moose stays as the ch04-quarry payoff); (2) it generalises — ch06 (Messie) and ch08 get their own on-story skins over vanilla-parity classes rather than a monster-class recomposition each time. Asset note (FE-Repo, all [U]): undead **sword/bow** skeleton anims exist off-the-shelf (Bonewalker/Specter/Stalfos, Wight Sniper); **lance/axe/armored** undead humanoids do not → those slots use frost/pale palette-swaps of the vanilla frame (an ice-locked sentinel reads better than a bone-knight anyway). The static bar is still a proxy — playtest is the arbiter.
_Decided: 2026-07-23 (Nicolas + CLAUDE; ch05 roster rev.2, #25 — "divorce skin from class; don't refight parity per chapter")_

**Recruit budget: the roster tracks vanilla's field-growth curve to a ~16–18 pool — NOT capped at Ch5.**
The binding *field* size is `deploy_limit` = vanilla chapter N's deploy-slot count (§Field parity;
table in `fe8-pacing-reference.md` §1b). That curve, [decomp]-verified through Ch14a, **climbs and
then plateaus — it never stops**: `2 → 4 → 5 → 9 → 9 → 9 → (5x:4) → 10 → 10 → 9 → 11 → 12 → 11 → 12 →
12`, holding **~12 from Ch10a through the back half** (exact Ch15–Final pin deferred, same honesty
tier as §1b — the late ally arrays are raw-address blobs; the plateau is the load-bearing fact).
Because our model **recruits the whole cast and Pick-Units deploys `deploy_limit` of them**
(§Field parity), the *roster* must sit **above** the peak field, or Pick Units is a formality and a
single permadeath drops you under the cap. Vanilla always carries a bench above the deploy cap; we
should too.
**The math that kills the old "stops at Ch5" cap:** 8 PCs + the locked Ch2–5 recruits
(Baxby/Trex/Lupin/Sahnar/Basil) = **13** — which only *barely fills* the Ch9→endgame field cap of
11–12 (bench ≈ 1). That is a forced-deploy roster with no choice and no permadeath slack. **Budget:
grow the roster to ≈ peak field + a ~4–6 bench = ~16–18 units**, i.e. **~3–5 more permanent recruits
across Ch6–21**, added as the DM notes supply bodies (which/where stays DM-notes-gated — see
`roadmap.md`). This governs **roster size, not field size** (per-chapter field stays vanilla via
`deploy_limit`), and recruits still earn their slot by **filling a role gap** (the by-role method in
`roadmap.md`) — the budget says *how many*, the role principle says *which*.
_Reconstructed: 2026-06-22 (CLAUDE, from the decomp field-growth curve at Nicolas's direction) —
superseded the then-stale `roadmap.md` "roster stops growing at Ch5" line (roadmap since fixed); the
original budget sweep was done in-session and never recorded, which this ADR fixes._

**Recruit wiring: a recruit is a classed cast member + a `recruit.chapter`; availability is data-driven; each join uses vanilla primitives per its own method — NO generic recruit engine.**
A recruitable unit is a full classed cast member — a `PORTRAIT_MAP` slot (a free vanilla character
whose files it overwrites), a `STAT_DONOR`, a `death_quote` + a dead-slot-2 msg id, its class in
`CLASS_MAP`/`CLASS_LOADOUT`, and a spawn tile per hosted chapter — exactly like a founding PC. The
**only** thing that marks it a recruit is a `recruit.chapter:` in its YAML.
**Prep availability is one shared, data-driven filter:** `build_campaign.cast_available_at(N)` =
the founding party (no `recruit:` block) + every recruit whose `recruit.chapter` is *before* chapter
N. So a recruit rides the prep/deploy roster from the chapter **after** it is recruited — which is the
whole of the "recruits the whole cast; Pick Units deploys `deploy_limit`" model (§Recruit budget).
`inject_ch0N` calls `_classed_cast(available_at=N)`; `available_at=None` (map sprites, death quotes,
stat patching) still covers every recruit.
**Each recruit's JOIN uses vanilla FE8 primitives, wired per its own method — do NOT generalize:**
- **Baxby (ch01)** — an **off-map CUTSCENE recruit**: won over in the **ch01-ending cutscene** (Marty
  wins him over) with no on-map unit. The availability filter puts him on the ch02+ prep roster, but the
  filter only **sizes the deploy cap template** (which is never LOADed) — so it alone does NOT put him in
  the saved party. He therefore gets an explicit **between-chapter join-LOAD**: `inject_ch02` LOADs him
  (a free vanilla-Ch3 UnitDef symbol, blue, on a walkable tile) in the beginning scene **before the PREP
  CALL**, so Pick Units lists him and he persists forward like any deployed unit. This is the general rule
  for any off-map recruit — `build_campaign.offmap_join_recruits(N)` returns the recruits newly available
  at chapter N whose `recruit.via` is **not** an on-map talk (`story`/`talk`); each gets a join-LOAD its
  first chapter on the roster (empirically verified: `run.sh ch02baxby` — Baxby at `blue[8]=0x10`,
  deployable and fighting on the ch02 map). His YAML `via: market` / `cost_gp: 200` is **cutscene flavor,
  not a purchase mechanic** (there is no buy-a-unit UI; §Recruit budget: the cast is recruited by story,
  Pick Units deploys). Rides the vanilla **Forde** slot (donor Franz/Cavalier); his hand-painted axe-beak
  map sprite injects on the standard 32x32 cast pattern (`base: Gargoyle` geometry token + synth MU, like
  braulo/wolfram/meesmickle).
- **Trex (ch03)** — a **Colm-style on-map TALK recruit**: placed GREEN, joins via `CUSA` when talked to
  (the vanilla `EventScr_Ch3_Talk_NeimiColm → CUSA(COLM)` pattern; `CHAR(flag, script, talker, target)`).
  Rides **Rennac** (donor Colm/Thief). He is the army's ONLY thief, so recruitment must be **non-missable**
  and telegraphed **Joshua-style** (a hint line + FE8's auto Talk prompt). Talker = any core party member
  (below). WIRED (#23 item 2, 2026-07-09): `inject_ch03` emits the `CHAR`-per-candidate list + the shared
  `CUSA(CHARACTER_RENNAC)` script; the hint line rides the Cutscenes item. The availability filter gives
  him ch04+ prep, and the `CUSA` join makes him persist naturally (no off-map join-LOAD).
- **Lupin/Sahnar/Basil (ch04/ch05)** — wired per their YAML method when those slices land (not now).
**A generic "recruit engine" that auto-registers a unit from its YAML was explicitly rejected** (Nicolas,
2026-07-08): unit identity (slot/donor/portrait) is genuinely per-unit — vanilla has per-character tables
too — and each recruit's join method differs, so a one-size engine is over-engineering. The reusable
pieces are the availability filter + the vanilla `CUSA`/`CHAR` primitives, nothing more.
**Talker for Trex = ANY core party member** (RESOLVED — the only thief must be non-missable, and a static
`CHAR` can't name the *chosen* lord). Implemented (`build_campaign.talk_recruiters`) as one
`CHAR(flag, script, <candidate>, CHARACTER_RENNAC)` per field candidate — the ch03 blue roster
(`cast_available_at(3)`) — all pointing at ONE shared recruit script (`talk_recruit_char_entries` +
`talk_recruit_script`): completing any one talk runs `CUSA(CHARACTER_RENNAC)` (green→blue) and the shared
flag disables the rest. FE8's own multi-recruiter idiom (cf. vanilla ch14a Rennac's two `CHAR` entries).
Verified in-engine: `PT_HOST_CHAPTER=4 run.sh ch03talk` — park a candidate adjacent to green Trex, drive
Talk → Trex leaves the green array and lands in blue (`blue[09]=0x1C`).

**Entrance + recruit are DECOUPLED from the RBG-execution beat** (the vanilla Colm shape). Colm's on-map
appearance is a LIGHT turn-1 green-NPC beat (one line); ALL his substance rides the Talk
(`EventScr_Ch3_Talk_NeimiColm`) — there is no second cutscene that re-introduces him. We now match that:
the ch03 RBG-execution beat is RBG's alone (+ Wolfram), and Trex's disavowal/boast/deal MOVED to the talk.
**Why (the bug this fixes):** a freely-timed talk recruit and a fixed Brute-defeat cutscene fire in either
order, so bolting Trex's introduction onto the execution beat let a player who talked to green Trex first
recruit him *before* the cutscene "introduced" him — his line even thanked RBG for an execution that hadn't
happened. The talk line is reframed to "the wild ones — the ones your bounty names" so it is accurate from
turn 1 with zero kills (the bounty, not a kill count, is the town-trust thread). The light entrance beat
(Pinky's telegraph + RBG's "little dragon") rides the #23 Cutscenes item with the other scripted beats.
_Decided: 2026-07-08 (recruit model; Baxby + Trex the first two consumers) + 2026-07-09 (Nicolas + CLAUDE;
#23 item 2 — talker=any-core-member RESOLVED, Colm-style decouple, talk-recruit wired + verified in-engine)._

**Reward/item budget: a chapter's loot mirrors its `parity_reference` vanilla chapter — same as its enemies.**
Just as `deploy_limit` and the enemy roster track the parity-reference chapter (§Field parity), so does
the REWARD footprint — by **channel** (village / chest / shop / boss-drop) and **tier** (consumable →
gem/gold → basic weapon → stat-booster → promotion item → Silver → Sacred/legendary). The
decomp-pinned curve is `fe8-pacing-reference.md §3`. **Hard caps read off that curve:** no
**stat-boosters** and no **promotion items** until a chapter whose `parity_reference` is ≥ **FE8 Ch5**;
no **Silver** weapon until ≥ **Ch8**; no **Master Seal / Secret Shop / Sacred weapon** until ≥ **Ch14a**.
Placement follows the **parity_reference, not our chapter number** — our 8-chapter MVP maps to
*non-consecutive* FE8 chapters (e.g. ch08 → FE8 Ch13), so a chapter's reward tier is its reference's,
not "chapter N's." This is the item analogue of the recruit budget; per-chapter loot is authored in the
chapter YAML (the data is the doc). Consistent with the promotion seam (Ch8→9): our MVP chapters
(parity ≤ Ch13) sit below the Master-Seal threshold (Ch15a), so promotions stay deferred to Revel's End.

**ch04 and ch05 each map 1:1 to their numeric FE8 twin (map AND parity); theme is layered, not borrowed.**
ch04 = our FE8 Ch4 (Ancient Horrors); ch05 = our FE8 Ch5 (The Empire's Reach). Each retiles its twin's
map and takes that twin as its `parity_reference`, so terrain, difficulty, and economy all track one
vanilla chapter. We considered borrowing the FE8 **Ch11 pair** (Creeping Darkness / Phantom Ship) as
`fe8_base_map` for their fog + monster theme, and **rejected it**: fog is a per-chapter config flag
(`chapterVisionRange`), the dark/monster look is our own custom tileset + injected roster, and ch05's
eruption is an injectable event (`EARTHQUAKE`/`TILECHANGE`) — none of which live in a map's *layout*.
Borrowing Ch11's layout would cost the one thing a base map actually gives (the terrain), and Phantom
Ship's enclosed corridor in particular fights FE8 Ch5's defining feature: villages spread to the corners
that force a two-front race. So we keep the twins' maps and layer the theme on top.

- **ch04 (Ancient Horrors twin)** — Rout; retiled snowy forest; **fog ON** (`chapterVisionRange`) as the
  White-Moose hunt (our added mechanic — vanilla Ch4 isn't fog); lean **~270g** economy (Ch4 = 2 villages,
  one Iron Axe, 0 chests — verified from HEAD by the #170 economy extractor, correcting a brainstorm that
  mis-read our injected ch03 chests as vanilla Ch4's). Hooks: the **wolf-pack parley** (Marty Talks Lupin)
  and **Trex as the fog scout** (Thief +5 fog vision). **No thief/chest-race** — foreign to Ch4 (no chests);
  Trex earns his spotlight as the one who can see in the hunt, which fits the chapter's actual gimmick.
- **ch05 (The Empire's Reach twin)** — DefeatBoss (Ravisin); retile Ch5's spread-village field as an
  **open-air elven-tomb depression** (crypt tileset + crystal pillars — keep the open spread-site skeleton,
  dress it as a ruin); **no fog** (mood from art, not vision). Emulates Ch5's two set-pieces: (a) the
  **Natasha→Joshua escort** becomes **Basil (Natasha-donor Cleric) chaperoned to Talk Sahnar (Joshua-donor
  Myrmidon)** — a convertible crit-threat you neutralize by recruiting; (b) the **village-raid race**
  becomes the **Phantom-Ship eruption** (injected `EARTHQUAKE`/`TILECHANGE`) spawning undead that raid
  **spread reward-sites** (elven reliquaries), with vanilla's **Guiding Ring** as the save-all reward
  (the earlier crest-of-cold-iron name was retired 2026-08-09). Ch5-magnitude economy incl. the
  **elven store** (Armory + Vendor);
  ch05 is the first chapter at/above the FE8-Ch5 reward tier, so stat-boosters + a promotion item unlock
  here (per §Reward budget above).

Both stay `status: planned` seeds — this sets the targets; the map + events build at each slice, checked
against the twin via `make difficulty` (economy #170 + recruit/reinforcement dynamics #171 now modeled).
_Decided: 2026-07-15 (Nicolas + CLAUDE). Supersedes the earlier "split old Ch4 into two Ch4-parity halves"
framing and the brainstormed Ch11-map-borrow (issues #24/#25) — both retired._

**ch04 "The White Moose" (#24) — reveal-flow, "the wolves turn the tide" difficulty, and roster mirrored to the twin.** Building the ch04 slice settled three things:
- **Flow — the reveal.** ch04 OPENS monsters-only (the ranged Mogall crossfire pocket = the difficulty); on **turn 2 the wolf pack bursts from the NW fog** beside the party — Lupin commands them (intelligence shown by ACTION), Marty reads it cross-field and flags the parley. **The reveal cutscene IS the parley teaching** (no separate tutorial — it plants the idea at the moment of decision). Retiming the pack from the turn-1 line to a reveal reshapes the curve to peak mid-fight; total pressure is unchanged.
- **Difficulty model — "the wolves turn the tide."** Target = **dead-on vanilla on the PLAYED (parley) path**, not a softened bar. So the raw no-parley fight sits ABOVE vanilla (the tax for refusing the mechanic), and the parley discounts it back to vanilla: verified **static ×1.15 threat / ×1.19 clear-load (PARITY, above ×1.0 intentionally)** with **parley-path clear-load 2.5 ≈ vanilla's 2.6** (`make difficulty CH=ch04`). This retires the stale "lean generous" framing: the house target is measured vanilla parity (via the three-dimensional `tools/difficulty.py`); generosity means rewards/recruits/exp, **never softened OR hardened enemies** — lord-select already swings party throughput, so above-vanilla enemies would compound into "harder than an already-hard base game."
- **Roster mirrors vanilla Ch4 1:1.** Vanilla Ch4 = **Mogall×4 · Revenant×12 · Bonewalker×6 (MELEE, iron sword/lance) · Entombed×1 = 23** (verified against `events_udefs.c` UnitDef_088B4A80 line + 088B4C24 Revenant pack + 088B4C88 Bonewalker pack). Our prior roster had **drifted** to D&D-monster-matched classes (bonewalker-BOW "phantom wraiths", Entombed brute, **zero Revenants**). Corrected to the twin's FE8 classes/levels/weapons; the one deliberate divergence is narrative — 6 of the twin's melee Revenants become the convertible Mauthe Doog pack.

**Principle (general, applies to every chapter): verify a chapter's data against its FE8 twin before trusting the YAML.** Our own data files can carry accidental drift (as ch04's roster did). Read the twin's `events_udefs.c` arrays and diff class/level/weapon counts. Divergence from vanilla is legitimate only when **purposeful** — it helps us better match vanilla's *felt* difficulty given our different party, or it's narrative (the wolf pack) — never when it's accidental drift. No drift-guard tooling (Nicolas's call, 2026-07-21) — just the verify-first reflex. ch03 (hosted) and planned ch05 should get the same twin-diff when next touched.
_Decided: 2026-07-21 (Nicolas + CLAUDE, ch04 slice #24). Supersedes the ch04 YAML's earlier "lean generous" `difficulty_note` and the 2026-07-17 D&D-matched roster grounding._

**ch04 Stage 2b — the Marty→Lupin parley rides ONE shared talk-recruit flow (reused from ch03).** The green (Trex) and red (Lupin) recruits are the *same* flow — a CHAR-per-recruiter list → a shared talk script whose `CUSA` flips the target BLUE — extracted from `inject_ch03` into `talk_recruit_wiring` (which ch05's Basil/Sahnar reuse). The only red-specific piece is a **`pre_script`** spliced into the talk script *before* the `CUSA`: a group parley uses it to bring the rest of the group over (ch04 splices the wolf pack's conversion sweep — see "the parley converts the pack IN PLACE" below). Only Lupin (the `CUSA` target) becomes a PC; the pack stays uncontrolled GREEN (no Rout count). Placement: Lupin is the **red pack leader** on the turn-2 wave's first tile (`CHARACTER_DUESSEL`, Cavalier, his YAML level, **not** autolevelled so his stats persist through the `CUSA` into a fresh recruit). The YAML wave stays `count: 6` so `make difficulty` still reads 6 turn-2 hostiles (parity held); the **5-generics-+-Lupin split is injector-side only**. Two deliberate departures from ch03: (1) **talker = Marty ONLY**, not any-party-member (Nicolas 2026-07-21 — the reveal centres Marty's creature diplomacy), data-driven from the wave's `parley.by`; (2) the pack is a *group* outcome, not a single recruit, so the `pre_script` seam does real work here. Because the parley is Marty-gated, **Marty is force-deployed in ch04** so benching him can't miss the recruit — via vanilla's own per-chapter `ForceDeploymentEnt` data path (`{pid, route=ANY, chapter=slot}`, scanned by `IsCharacterForceDeployed_`), which the lord-select hook (#42) cleared of vanilla's by-slot entries but kept the scan for *exactly* this ("added our way, not the by-slot table"). **No new engine code** — a non-lord unit is fielded purely by adding a data row (harmless if the player *chose* Marty as lead: the lord check already force-deploys him). The reusable helper `_force_deploy_units(pids, host_index)` is where ch05 hooks a Marty-style gated recruiter.
_Decided: 2026-07-21 (Nicolas + CLAUDE, ch04 slice #24, Stage 2b)._

**ch04 — the parley converts the pack IN PLACE, and the ally count scales with survivors.** Marty's Talk no longer clears the pack and reloads a green table; it runs one **`CHECK_ALIVE`-guarded `CUSN` per wolf** (`convert_survivors_green`), flipping each survivor GREEN where it stands. Three decomp facts force that exact shape, and the naive version is broken without the third: (1) `UnitChangeFaction` (`bmunit.c:1010`) copies the unit into a free slot of the new faction and clears the old one, and `GetUnitFromCharId` scans blue → green → red, so a second `CUSN` on a *shared* pid re-finds the wolf it just converted — **distinct pids per wolf are mandatory** (`CH04_PACK_PIDS`, drawn from the unnamed generic band `0xB0..0xB9`, guarded by `assert_pack_pids_addressable`); (2) `UnitKill` (`bmunit.c:988`) keeps the slot only for BLUE units and **wipes** a non-blue one (`pCharacterData = NULL`), so a killed wolf's pid stops resolving; (3) a `CUSN` on an unresolvable pid returns **`EVC_ERROR`** — only `DISA`/`KILL` get the graceful no-op (`eventscr.c:3317`) — so a bare sweep would break in exactly the kill-then-parley case. `CHECK_ALIVE` is safe on a wiped slot (`eventscr.c:3212`) and is already ch02's per-chwinga idiom. **What this buys, beyond not teleporting the pack home mid-fight: parleying EARLY is now the reward.** The old `LOAD1` brought the *full* five-wolf table back however many you had killed (proved in-engine by `ch04packmath`), so shooting first cost nothing; `CUSN` can only convert what still exists, so the ally count scales with survivors for free — no table-scaling code. **Accepted trade-off (Nicolas):** `CUSN` changes faction, not class, so the allies stay `CLASS_MAUTHEDOOG` in the green NPC palette; the `lycanroc-pack` reskin stays *declared but unworn* in `campaign.yaml` for a later class-remap hook, which can be added without redoing any of this. The regression gate is `ch04packmath`: kill 2 of 5, parley, and the green count must equal the number left standing.
**Measured, so don't re-derive it: the wolves do NOT respawn or relocate during the parley.** A clean
`recordch04parley` sampled every wolf before the Talk and immediately after conversion — `0xB0 (2,0)`, `0xB1 (0,2)`,
`0xB2 (0,0)`, `0xB4 (1,0)`, `0xB5 (0,1)`, unchanged. Any movement afterwards is the greens' own phase.
_Decided: 2026-08-01 (Nicolas + CLAUDE, #203 — folds in the pack-math question from #24 Stage 5)._

**A reskin may restyle a village; it may not stop it being one — visitable terrain is now protected.** ch04 shipped its whole slice with **no material reward at all**: the Lonelywood village was authored in YAML, drawn on the map, and unobtainable. Two independent halves were broken and each hid the other. (1) FE8 gates the **Visit** menu item on the TERRAIN under the unit — `HOUSE`/`INN`/`RUINS_VILLAGE`/`VILLAGE_REGULAR` (`bmmenu.c:735`) — *before* it ever consults the location event, and the snowy-bern reskin mapped vanilla's village metatile **872 → 994 (`RUINS_REGULAR`)**; its own neighbours (`871→897`, `873→899`) show the intent was **898**, the one `VILLAGE_REGULAR` tile in the tileset and the very metatile ch01/ch02 already use for their houses. (2) `inject_ch04` blanked `EventListScr_Ch5_Location`, where `VILL` entries live. Nothing caught either: the building still *drew* correctly (identical 3×3 stamp to Targos's houses), the map compiled, the chapter played. **The durable fix is the rule, not the tile** — `preserve_terrain_variants` was `[12]` (forest only, #193), so `preserved_terrain_targets` never checked villages; it now protects all four visitable terrains, which makes a terrain-changing retile *fail the import* instead of silently deleting a reward. Re-applying that guarantee to the committed grid corrected **exactly two cells** (the two village doors), leaving the other 44 protected cells untouched. Content-side, `assert_village_tiles_visitable` rejects a `villages:` entry standing on scenery, and the chapter YAML now carries the village's `tile:`, its reward and its line (a village's text is CONTENT — putting it in the injector is the mistake #208 exists to undo). **Placement is vanilla's, not ours** (Nicolas: "we copied vanilla ch 4, just copy that"): vanilla Ch4 wires `Village(0, …, 8, 2)` — one text box then `SVAL(EVT_SLOT_3, ITEM_AXE_IRON)` + `GIVEITEMTO(CHAR_EVT_ACTIVE_UNIT)` — and `Village(0, …, 1, 11)`, its **recruit** village, whose role the Marty→Lupin parley took over (that cottage is wired with a line of its own — see "a village's line is dialogue" below). One consequence: our authored moose-sighting `AREA` started at `(8,2)` — the village doorstep — so stepping up to visit would have fired the sighting instead; it now starts at `x=9` (vanilla's own AREA touched neither village). Gate: the `ch04village` scenario visits the tile and asserts the axe is in the party's hands afterwards and was not before.
_Decided: 2026-08-01 (Nicolas + CLAUDE, #205)._

**A village's line is dialogue, so its A-press breaks are AUTHORED — `visit_text` is a list of boxes, never a flowed scalar.** Village text went in as one folded scalar and was flattened to a single run before wrapping, so the boxes fell wherever 42 columns happened to land. That is not cosmetic: the axe village's text is vanilla's `MSG_9B5` **copied 1:1 on Nicolas's instruction**, and vanilla ships it as **four** boxes each broken on a sentence — ours came out as **three**, buttoning mid-sentence on *"a handy bridge if / you could knock it over."* 1:1 in words, not on screen, which is not what 1:1 meant. `visit_text` is now a **list, one entry per GBA box** (`village_boxes()`), and a flowed scalar is rejected outright rather than silently reflowed — `_script_to_message` keeps each entry's pages whole, so authored beats survive as the A-press breaks. The axe village is restored to vanilla's own four. **Generalises the craft rule from the dialogue-pass skill (draft BOXED, never as prose) to the one text channel that had escaped it** — every other scene already authors its beats as `script:` entries.
_Decided: 2026-08-05 (CLAUDE, #24 — found while wiring the second village)._

**ch04's second village pays in lore, and the frost druid it seeds is never named there.** Vanilla Ch4's other cottage at (1,11) is its **Lute recruit** village (`9B2`/`9B3`/`9B4` — three variants by visitor, zero lore), and the Marty→Lupin parley took that job, so the door sat on visitable terrain with no Location entry for the whole slice: FE8 runs a village off that event, so the player saw a cottage they could not enter. **There was nothing to copy — the line is ours** (Nicolas: "at least a lore drop or a hint"). Two canon beats the campaign had never spent carry it: the DM notes' *"the frost druids did visit, but were largely ignored by villagefolk"*, and the book's Ravisin (p.80), who *"won't rest until the forest is free of loggers."* So a logger tells you the woman in white furs came to the cutting camps, that the foreman laughed her off, that she walked away **southeast** smiling, and that the beasts started talking that same tenday — the chapter's fiction explained by the townsfolk's own shrug. **She is never NAMED and the stones are never mentioned:** the ending owns ch04's single Ravisin seed (review cut 2026-07-03 consolidated the dread there) and Lupin owns the reveal of the tomb door, so the village is the setup, not a second seed. Staging is book-sourced too — Lonelywood's forest folk *"value their privacy and are much less inclined to welcome strangers into their meager dwellings"* (p.79), hence a man who talks through a barred door and never opens it, on `FID_VillagerMan3`, the mug vanilla itself puts on its snag village. **Reward is the line alone** — ch04's economy is deliberately Ch4-lean (one Iron Axe, no gold, no chests), and `ch04_village_script` drops vanilla's give-item tail for a village that declares no `visit_reward` rather than handing over a default. Each village gets its **own** event script and message id (`CH04_VILLAGE_SLOTS`, keyed by the YAML id): two doors sharing one script show the same line at both and run the give-item tail twice. **Both doors also moved off vanilla's `BG_NORMAL_VILLAGE`, a TEMPERATE GREEN TOWN, onto `CH04_OPENING_FOREST_BG` — our winterized fogged forest, the art Pinky's opening beat already stands in.** During a village visit the backdrop is the entire screen, so ch04 was playing both of its villages in summer, in a snowbound fog chapter. It is the forest and not our snow-TOWN art (`BG_MS_TARGOS_WINTER`) because **there is no town on this map**: both cottages are cabins standing in the woods and the visitor is outside one of them (Nicolas, 2026-08-05: *"if we're outside their cabin, just use the bg you put behind pinky in his fog scene"*). General rule this instances: **a reused vanilla BG is a climate claim** — every backdrop on a winter map has to be checked against the map it plays over, not inherited because the vanilla scene it copies used it. Gate: the `ch04cottage` scenario, whose evidence is the door itself — an item check cannot settle a village whose reward is words, so it asserts Visit was offered, a text box actually opened, and the terrain went `VILLAGE_REGULAR → VILLAGE_CLOSED`, which only happens if the event ran to the end.
_Decided: 2026-08-05 (Nicolas + CLAUDE, #24 — the last ch04 item; Nicolas assembled the line from three sourced drafts)._

**A hosted chapter's goal strings are message ids, so it must OWN them — inheriting a donor slot's is how two chapters overwrite each other.** `_retarget_host_chapter` copies a donor slot's whole `goal` block, text ids included, and vanilla points many slots at one string (six share `windowTextId` 414). ch04's donor is **ch02's own host slot**, which `inject_ch02` has already rewritten by the time `inject_ch04` runs — so ch04 inherited ch02's `windowTextId` *and* `statusObjectiveTextId` wholesale, and the later injector won. It never looked broken because both chapters write the same strings (`'Defeat enemy'` / `'Defeat all monsters'`) and ch04 wrote no window string at all; the defect was **latent**, waiting on the first wording that diverged or the next `defeat_all` chapter. Every hosted chapter now **declares** its pair as constants, `_retarget_host_chapter` takes them and overrides the donor's — keeping map ids, event group and goal ids one decision — and they are registered in `HOSTED_CHAPTER_MESSAGE_IDS`, which makes the existing `assert_message_ids_unique()` bind on them and fail the build on a collision. ch01/ch02/ch03 keep the ids their donors already gave them (distinct); only **ch04 moved, to `0x9C4`/`0x9C5` out of the dead Ch5 block it owns**, and it now writes both strings instead of inheriting a window. **Method note, learned the hard way twice in one session: post-injection goal ids cannot be read from `HEAD` (vanilla, pre-copy) or from the working tree (whatever the last build or `git restore` left) — RUN the injector and read the result.** The 12-char window budget (`goal_window_body()`) is unchanged.
_Decided: 2026-08-02 (CLAUDE, #207 — investigation corrected the issue's original diagnosis)._

**A map change picks its tiles by TERRAIN, and a declared terrain is not a painted tile.** ch04's Iron Axe exists because vanilla Ch4's village hands it over as the **tool for chopping a snag into a bridge** (`MSG_9B5` is that tutorial, copied 1:1 — Nicolas, 2026-08-02). Snags are natively attackable (`bmtrick.c` auto-adds a 20 HP `TRAP_OBSTACLE` on every `TERRAIN_SNAG` tile), but the bridge half is a **MapChange** applied by `UpdateObstacleFromBattle`, and `_retarget_host_chapter` zeroes `changeLayerId` for every hosted chapter — so ch04 had none and the axe had no job. Vanilla's own region and roles are copied (snag at (4,8), 1×3 → plains / crossing / plains, dropping the trunk across the river at (4,9)), along with the **visited-village door flip** we had never done. The ch03 chest/door emitter was **generalised, not copied**: `map_changes_asm(symbol, changes)` + `_inject_tile_changes`, with ch03 rebuilt on it — FE8 resolves a change by POSITION, so chests, doors and obstacles share one array. **Tiles are resolved by terrain name at build time, never hardcoded** (the reskin renumbers everything; #205 is the cautionary tale). The trap this cost a rebuild to find: **snowy-bern declares `TERRAIN_BRIDGE_SNAG` on metatile 36 but never painted it** — writing it put a *black square* in the river while every terrain byte read correctly and the in-engine assertion PASSED. Only looking at the frame caught it. So `_snowy_metatile_for` now skips blank metatiles and fails loudly when a terrain has no painted tile, a unit test asserts no map change writes one, and the crossing uses metatile 2 — the bridge this map already lays over this same river. **Corollary to "verify via data, not pixels": data proves a change FUNCTIONS, pixels prove it LOOKS like anything at all. A tile swap needs both.**
_Decided: 2026-08-02 (Nicolas + CLAUDE, #214)._

Historical note: the metatile 2 masonry crossing above was the temporary safe fallback; the
winterized felled-snag decision below supersedes it.

**The felled snag keeps vanilla's full three-tile silhouette, winterized in snowy-bern (#24).**
The masonry fallback above was mechanically safe and visually wrong: chopping a tree made a
stone bridge appear. Vanilla Ch4's change is a composed `7 / 4 / 11` picture -- wood fragments
on the near bank, the trunk over water, then fragments on the far bank -- so snowy-bern now
paints the same composition into its matching unused `7 / 36 / 11` slots. The grass pixels are
replaced with snowy-bern snow; the wood silhouette is lifted intact and recoloured with the
muted ramp from snowy-bern's upright snag 35. All three cells use Snowy Bern's existing lit
palette bank 4; the shared palette stays byte-for-byte untouched. That matters under fog:
tileset banks 5-9 are derived fog copies of lit banks 0-4, not spare authoring banks. The bank
fragments preserve snow tile 67's pixel pattern and the center keeps the vanilla trunk/water
silhouette, remapped only to colours already native to the snag palette.
`paint-metatile` is the reusable authoring seam: it splits a 16x16 indexed PNG into 8x8 tiles,
reuses byte-identical art, allocates only unreferenced tile ids, can claim an unused palette
bank in the lit 0-4 half, rejects the derived fog half, and preserves terrain unless explicitly
authored. Runtime still resolves each preferred
slot through `_snowy_metatile_for`, so `7 / 36 / 11` is accepted only while it carries
`PLAINS / BRIDGE_SNAG / PLAINS` **and each preferred slot is visibly painted, not merely
terrain-correct**. That preferred-path check has its own regression because bypassing the
ordinary search's blank-art guard can recreate the original solid-block failure. The enlarged
binary round-trip render is
`docs/demo/ch04-snowy-snag-bridge.png`; `ch04snag` remains the mechanism gate and an in-engine
frame remains the art gate.
_Decided: 2026-08-10 (Nicolas + Codex, #24; visual composition supplied by Nicolas)._

**ch04 Stage 2c — the reveal cutscene reuses the turn-2 TurnEvent script (load + stage as one).** Following vanilla Ch4's `EventScr_089F199C` shape, the turn-2 script that already `LOAD1`s the reveal wave *also* stages it in ONE script (`CAMERA2` to the NW fog → `LOAD1`/`ENUN` → `MUSC` → `CUMO_CHAR` Lupin → stub beats → `EVBIT_T`), rather than a separate cutscene script — that's how vanilla does a reinforcement-with-scene. On-map (no `BACG`); the beats are faced map bubbles (`_script_to_message`) on Lupin (Duessel) + Marty (Seth). Two beats plant the parley: Lupin commands the pack (shows intelligence) and Marty flags "talk to it" — the cutscene *is* the parley teaching (no separate tutorial). **Stub lines + `SONG_TENSION` placeholder; Stage 4 finalizes dialogue + music via the dialogue-pass skill.** Dead Ch5 slots `EventScr_089F22A4` (reused) + msgs `0x9BB`/`0x9BC`.
_Decided: 2026-07-21 (Nicolas + CLAUDE, ch04 slice #24, Stage 2c)._

**Parity-engine v1 gaps closed (#176 economy drops, #177 area-triggered reinforcements).** Two channels the
first cut of the extractors punted on, both read from HEAD like the rest: (1) **enemy drops** — a red unit
flagged `.itemDrop` drops its **last** inventory item on death (`US_DROP_ITEM`, the final slot per
`statscreen.c:726`); `vanilla_economy` now values it as a `drops` channel folded into `total_gold` (the Ch4/Ch5
lock twins carry none, so the lock is unchanged, but Ch2's Vulnerary / Ch3's keys / Ch13's crests now count).
(2) **area/zone-triggered reinforcements** — `_vanilla_reinforcement_turns` matched only the `TurnEventPlayer`
macro, so it missed Ch4 "Ancient Horrors"' waves: a turn-2 Bonewalker pack written as a raw
`TURN(…, FACTION_BLUE)` and a Revenant pack behind a temp-flag-gated `TURN` that an `AREA(…)` trigger arms on
zone-entry. It now also reads the raw-`TURN` expansion, treats any **flag-gated** turn event (and any `AREA`/
`AFEV` script that LOADs a force) as a reinforcement, and models zone-entry arrivals as `_ZONE_ENTRY_TURN`
(> 1, so they leave the turn-1 line) — Ch4 reads 16 line + 7 reinforcements, Ch5's 2/6/8 detection unchanged.
_Decided: 2026-07-16 (CLAUDE; TDD). Closes the v1 scope noted on #170/#171._
Worked example — **ch02 (parity FE8 Ch2):** gems + premium consumables only (vanilla Ch2's village
gifts) + a regular armory + one enemy consumable drop; **no boosters, no promos.** The three chwinga
"charms" are those gifts — **Elixir / Pure Water / Hand Axe** (the Hand Axe stands in for vanilla's
**Red Gem**, which is lent forward to ch03's gem mine; see the Ch3-deviations ADR below — net wealth
across ch02+ch03 is unchanged).
_Reconstructed: 2026-06-22 (CLAUDE, decomp event-data + `events_shoplist.c` scan) — upgrades
fe8-pacing §3 from era-buckets to a decomp-pinned curve (correcting the old "promos at Ch9–13": promos
+ boosters actually start Ch5, Master Seal/Secret Shop start ~Ch14a). Companion to the recruit budget._

**Ch3 "The Termalaine Mine" — four sanctioned deviations from strict per-chapter parity.**
ch03 reskins vanilla FE8 Ch3 "The Bandits of Borgo" (Seize big-battle; the game's first chests +
first thief). Roster + reward footprints mirror it 1:1, with four deliberate, parity-neutral
deviations (Nicolas-directed):
1. **The boss is a real monster.** A grell IS a floating tentacled eye-aberration, so the boss slot
   (vanilla Bazba, Brigand L6) becomes a **CLASS_MOGALL** with the Evil Eye — NOT a frailty cheat.
   A same-level mogall is far weaker than a Brigand, so it carries a **level bump (L12)** to hold
   Bazba's pressure. Verified on `make difficulty CH=ch03`: clear-load ×0.99, threat ×1.12 (within
   band; the magic Evil Eye vs our low-RES melee runs intentionally hot). Parity is *measured*, not
   assumed — this is exactly the wiggle-room the difficulty engine exists to provide.
2. **Monster foe-type debut moves ch04 → ch03.** The grell is chronologically the party's first
   monster. The `introduces: monsters` ledger entry moved to ch03 (out of ch04, which stays a
   monster/fog set-piece but is no longer the *first*). Monster-effective GEAR stays deferred (none
   on the reward curve yet).
3. **The ch02↔ch03 gem/hand-axe swap.** Vanilla's single early gem (the Ch2 Red Gem) is *lent
   forward* to ch03's gem mine (it's literally a famous tourmaline mine; Trex the thief opens the
   seam). To keep wealth on-curve, vanilla Ch3's Hand Axe chest moves *back* to ch02's chwinga-mote
   gift. Net result: total wealth AND the exact item set across ch02+ch03 are identical to vanilla —
   only the chapter each of the two items appears in is swapped. (We considered keeping the gem at
   ch02 for strict per-chapter parity; chose the swap for the gem-mine payoff, since it's net-neutral
   and the Ch2 gem money is meant for world-map shopping after the chapter anyway, not the thin Ch2 armory.)
4. **Objective is Defeat Boss, not Seize (added 2026-07-06, Nicolas).** Vanilla Ch3 wins by seizing
   Bazba's tile (14,1); ours wins by **killing the grell** on that tile. Both require defeating the
   boss — Defeat Boss just drops the extra "step onto the tile" beat, which reads truer for slaying an
   aberration than capturing a throne. Mechanically near-identical (the grell sits on 14,1 regardless);
   the parity band is unchanged. (The ch03 YAML `objective.type` and `win_condition` reflect this.)
_Decided: 2026-06-26 (Nicolas + CLAUDE, Ch3 design-lock session; grounded in the FE8 decomp, the DM
notes, and the Frostmaiden book "A Beautiful Mine" pp.93–96) — item 4 added 2026-07-06. FE8 has no
multi-level maps, so the book's 3-level mine is authored as one flat walled interior (rooms via
TERRAIN_DOOR + one TILECHANGE), not a verticality gimmick — the doors make the thief (Trex) matter._

**Ch3 dialogue re-pass on the 2026-07-06 reframe (2026-07-09, Nicolas + CLAUDE).** Three fiction
changes settled while re-passing the opening + RBG-execution/Trex-recruit beats (roster/positions
unchanged; still plays like Bandits of Borgo): (a) **Trex's cosmetic wings are dropped** — the
table gave him self-fashioned wings, but they're not in his FE portrait or map sprite, so they're
cut from the fiction (his hook was always the self-taught eloquence, not the costume). This retires
`lore/trex.md`'s wings content and Meesmickle's wings-based ending button; it also moots the "wings
pixel edit" art task on #23. (b) **Pinky's shaft-scout folds into the opening cutscene** — as the
army's flier he does a flyover recon from the mine mouth; the grell is now **visible at (14,1) from
turn 1** (Bazba-style), so the old standalone `shaft_mouth_reached` beat, its scripted grell spawn,
and its "open the way down" map-change are all retired (the deep workings are pathable from the
start). The RBG/Pinky Wish-seed two-hander is preserved intact. (c) **Canon name fix:** the town
speaker is **Oarus Masthew** (book pp.93–94), not "Maxol" — corrected in the crier + ending lines.

**Ch3 layout = vanilla Borgo geometry repainted, NOT a custom Gem-Mine blockout.**
The 2026-06-29 session *proposed* pivoting the ch03 layout to a custom flattened trace of the
book's Gem Mine map (Map 1.19) and posted a blockout on #23 pending Nicolas's OK. That OK never
came; on review Nicolas ruled the other way: **repaint vanilla Ch3 "Bandits of Borgo" geometry
with the `cave-interior` (Cynon Mineshaft) tiles** — don't fabricate map geometry from scratch
when a vanilla-proven Seize layout exists. This restores the ch03 YAML's own `base_layout: Ch3Map`
record (the YAML never adopted the pivot) and extends the "ALL mechanical data is vanilla" instinct
to map flow: vanilla shape, our skin. The tileset choice (Cynon Mineshaft, Gray, no re-palette) and
the thin-converter tooling from the pivot exploration all still stand — only the layout source
changes. Enemy/chest tiles stay the vanilla Ch3 coordinates (no repositioning pass needed, one less
deviation). The book's Gem Mine map remains flavor reference; the rejected blockout stays on #23
for the record.
_Decided: 2026-07-04 (Nicolas, mobile session — ruling on the #23 pending decision)._

**Ch3 chains off ch02's ending (`MNC2(0x4)`); the party persists, no armed seed.**
ch02's ending scene now `MNC2(0x4)`s straight into ch03 (hosted on chapter slot 4 by
`inject_ch03`), replacing the dev-placeholder→title landing it parked on while ch03 was
unbuilt (the placeholder pattern is unchanged — ch03's *own* ending still parks on it until
ch04 hosts). Two coupled moves in `build_campaign.main()`: (a) `inject_ch03` is now called in
**every non-boot build** (hosted alongside inject_ch02, in the sandbox build too, so ch02's
`MNC2(0x4)` never points at an unhosted slot); (b) it's called with **`boot=False`** — the
party that persists from ch02 feeds ch03's Preparations, so the `--ch03-boot` **armed party
seed** (`UnitDef_088B47E4`, LOAD1'd only under boot) is a standalone-playtest crutch only, not
part of the real chain. Verified in-engine by `clear_ch02`, which now A-mashes the ch02 ending
until `chapter() == 4` (ch03) and FAILs if the chain doesn't land — the ch02→ch03 analogue of
the `reachCh02Map` `MNC2(0x3)` proof.
_Decided: 2026-07-11 (CLAUDE, #23 item 1 — chaining pass)._

**Ch3 chests + doors ride ONE per-chapter MapChange array; a door opens to the tile below it.**
FE8 flips a tile on loot/open via a per-chapter `struct MapChange` array (`gChapterDataAssetTable[map.changeLayerId]`):
opening a chest runs `CallChestOpeningEvent(GetMapChangeIdAt(x,y), item)` and opening a door runs
`CallTileChangeEvent(GetMapChangeIdAt(x,y))` — **both look up the change by POSITION** (`GetMapChangeIdAt`
auto-finds the 1×1 region covering the tile), so chests and doors coexist in one array (`MS_Ch03MapChanges`);
ids only need to stay unique. `ApplyMapChangesById` writes `gBmMapBaseTiles[y][x] = tile` for each non-zero
`metatile<<2` word. **The chests** all open to the shared FF5-navy open tile (17→29). **The doors** each open to
the metatile **directly below the door cell** (Nicolas 2026-07-11 — "use the tile directly adjacent and below
it"), read off the painted `.mar` at build time (`_read_map_metatile`) so it tracks any re-retile — no hand-copied
tile numbers. On the committed map that's road/stairs (572/626/492, all passable): vanilla Ch3's `Door_(6,10)`
opens the lower gallery, `Door_(10,5)` the stairs down, `Door_(2,3)` the upper room. Authored as `chests:`/`doors:`
position lists in the ch03 YAML → `Chest()`/`Door_()` in `EventListScr_Ch4_Location[]` + the paired MapChange.
Verified in-engine (`PT_HOST_CHAPTER=4 run.sh ch03door`): hand a unit a Door Key, drive Door, and
`gBmMapBaseTiles[3][2]` flips 3248→1968 (812→492<<2). The chest path shares this array + code path, so the
door proof covers both. `gBmMapBaseTiles` is a ROM-`.data` pointer (objdump `g O ROM` @ 0x085AF5DC) → the
EWRAM `sBmBaseTilesPool` row array, never reassigned — read the pointer from ROM, then index the rows.
_Decided: 2026-07-11 (Nicolas — open-door tile rule; CLAUDE — shared-array wiring, #23 chests/doors)._

**A campaign item icon can use a colour pal 0 lacks, via an additive third item palette.**
FE8 item icons share a 16-colour pal 0, which has no pink and no globally-free colour index. The pink
Tourmaline (`ITEM_REDGEM` reskin, Nicolas) therefore cannot recolour pal 0. The earlier assumption that
the second source icon palette could be repainted was wrong: `LoadIconPalettes` places it in BG bank 5,
which regular map/UI text can also use. Repainting it made that text pink.

The corrected mechanism keeps both vanilla source banks byte-for-byte intact: (a) `inject_item_icons`
still swaps the Red Gem tiles; (b) `inject_item_icon_pal2` **appends** a third 16-colour source bank at
bytes 64–95 of `item_icon_palette.agbpal` and emits `gMSPal2IconIds[]`; (c) the generic
`_patch_draw_icon_pal2` hook leaves FE8's normal `ApplyPalettes(..., Dest, 2)` load alone. When an
opted-in icon is drawn with normal item-UI base bank 4, it copies source bank 2 into reserved BG bank 15
at draw time and replaces that icon's palette nibble with bank 15. The draw-time copy matters: earlier UI
initialisation can overwrite a loader-time copy. Other icon callers retain their vanilla base.

The palette-bank assertion in `run.sh ch03tourmaline` proves bank 5 remains vanilla (`0x7FDE` at index 1)
while bank 15 carries the custom palette (`0x7FFF`), and audits the active BG tilemaps so bank 15 is used
only by Tourmaline's four icon tiles. The accompanying screenshot proves the floor and text retain their
normal colours while Tourmaline is pink. More custom colours can share `item_icon_pal2`. The GBA has only
16 BG palette banks (0–15), so a further distinct palette is not an append-only live-memory change: it
requires a new BG-bank reservation and runtime collision audit in every relevant UI context. The cast
palette is an OBJ palette (bank 11), not a BG palette, so an item icon cannot point to it directly.
_Revised: 2026-07-14 (Nicolas — observed pink text; Codex — additive source bank, draw-time BG bank-15
route, and active-tilemap regression check; supersedes the 2026-07-11 pal-1 assumption)._

**Two healers, differentiated by donor (same move as the shamans).** The army's two staff users get
*distinct* vanilla donor lines to avoid stat-twins: **Sclorbo → Moulder** (the durable "war-priest":
HP70/Def25, balanced, accurate) and **Basil → Natasha** (the frail "mage-healer": HP50/Def15 but
Pow60/Res55/Lck60 — a glass, dodgy, magically-potent nuke-healer). The frail line sits
on Basil deliberately: **Sclorbo is a lord candidate** (#42) and the per-lord floor would have to work
harder on a frailer lord (he's already the weakest, staff-only lord pick), whereas **Basil is not a lord**
(joins Ch5, after the Ch1 lord-select), so frailty there carries no survivability-floor cost — and "fragile
but potent natural magic" suits an awakened shrub. Sclorbo is a **Priest → Bishop/Sage**; Basil is a
**Cleric → Bishop/Valkyrie** (see the next entry), so since 2026-08-08 the two differ by class as well
as by donor — but the donor is still what separates the stat lines, and it is the part that would matter
even if they shared a class.
_Decided: 2026-06-20 (Nicolas); Basil's class revised 2026-08-08._

**Basil is a Cleric, because Priest promotes into the wrong weapon type.** Basil was a Priest from
2026-06-20 until 2026-08-08, on the reasonable-looking grounds that she is the same class as Sclorbo
and differs only by donor. That was the wrong class, and the decomp says why: `ClassData.promotion`
for `CLASS_PRIEST` is **`CLASS_SAGE`** — an *anima* mage — while `CLASS_CLERIC`'s is **`CLASS_BISHOP_F`**,
which is *light*. Basil's own `battle_anim.spell_palette_tint` has always declared `[staff, light]`, so
Priest pointed her at the one promoted class whose weapon type contradicts her shipped art. Cleric's
branch (`gPromoJidLut`: Bishop_F / Valkyrie) is the one her kit already assumed.
Three things made this cheap enough to be worth doing, all verified rather than assumed:
**(1) the art does not move** — bust, map sprite and battle anim are all keyed to the *character* slot
(`GetUnitSMSId` override, a private `gUnitSpecificBanimConfigs` AnimConf), never to the class, and the
`clone_from: bishop` donor supplies the STAFF+LIGHT pair Bishop_F needs anyway;
**(2) the locked dialogue does not move** — not one locked Basil line in any chapter genders her, so the
whole ch05 corpus ported unchanged;
**(3) the slot does not move** — `gender:` in the unit YAML rewrites `.attributes` (`_set_gender`) on
whatever character slot the unit wears, so a female Cleric rides the male Artur slot fine, and promotion
is keyed by CLASS in `gPromoJidLut`, never by character.
Two bonuses that were not the reason but are real: Cleric's bases (HP16/Def0/Res6/**Con4** vs Priest's
18/1/5/**5**) lean the same way the Natasha donor does, and `CanUnitRescue` is `GetUnitAid(actor) >=
UNIT_CON(target)` (`bmunit.c:905`) — so Con 4 widens the set of party members who can ferry the ch05
escort, which is the chapter's whole set-piece. Growths are byte-identical between the two classes,
so nothing about her level-up curve changed. `gender: female` is mechanically inert on a foot unit:
both `CA_FEMALE` readers in the decomp (`GetUnitAid`, `koido.c`'s rescued-unit sprite) gate on
`CA_MOUNTEDAID` first. Basil is an awakened *plant*, which RotFM gives no gender, so nothing in canon
was overridden. Guarded by `test_basil_is_a_cleric_because_priest_promotes_into_the_wrong_weapon_type`
and `test_basil_bases_are_vanilla_cleric_class_data_verbatim`, both pinned against the decomp.
_Decided: 2026-08-08 (Nicolas, after an adversarial review that reversed CLAUDE's initial "not worth it")._

**Lord floor, runtime mechanism (#45 3b/3c): a build-baked table applied once at the first player phase.**
The build emits `gLordFloorDeltas[]` (`events_udefs.c`, parallel to `gLordSelectCandidates[]`): one
`{+maxHP, +Def, +Res}` row per candidate = `difficulty.lord_floor_delta` @target 3.5 vs Ch1 enemies (Ch1 →
shamans +7HP/+4Def, the armor tanks 0). The engine applies the **chosen** lead's row once — `LordFloor_ApplyOnce`
(`eventinfo.c`, beside `LordSelect_GetPid`), called from **`EndPrepScreen`** (`prep_sallycursor.c`), right after
`ShrinkPlayerUnits` finalizes deployment on the prep "Fight!". **Hook-point lesson (the #45 3c open question, found by
playtest):** every player-*phase-start* seam — `BmMain_StartPhase`, and the cursor-reset
`ProcFun_ResetCursorPosition` the crash guards use — fires BEFORE prep deployment finalizes on turn 1, so the chosen
lead isn't findable yet (`GetUnitFromCharId` → NULL) and the floor lands a phase late (ch01: +7 at turn 2, not turn
1). The deployment-finalization seam in `EndPrepScreen` is the first point the lead is deployed + valid; lord-select is
always a prep chapter, so it suffices. Apply-once is a permanent flag (`0xFA`, just above the `0xF0` candidate block)
**spent only on a real application** — a pick flag is set AND the lead is found — so the prologue (no pick) skips
cleanly; the buff then bakes into the saved unit and fades as it levels. Presence-guarded in
`check.py check_engine_guards_present`; playtest-verified by `tools/playtest/run.sh lordfloor` (marty +7HP/+4Def at
ch01 turn 1, stable across phases — no double-apply).
_Decided: 2026-06-19 (CLAUDE; decomp-traced + playtest-corrected — resolves #45 3c open hook-point question)_

**Per-chapter parity beyond Ch1 = enemy-pressure vs a `parity_reference` vanilla chapter.**
Our cast is fixed all game and already at vanilla parity (above), so a chapter's difficulty is set by its
enemies + deploy cap. The difficulty engine measures **enemy pressure** — threat/slot (Σ enemy
damage-per-round vs a fixed yardstick unit ÷ deploy cap) and clear-load/slot (Σ enemy bulk ÷ deploy cap) —
for our chapter and for the vanilla chapter named in a new per-chapter YAML field `parity_reference:
"FE8 ChN"` (the cadence-bar source of truth; vanilla enemies auto-extracted from the decomp). Parity =
within a band. The engine also still reports our actual cast vs our enemies (throughput / durability /
carry) as the absolute "can our roster clear it" check. **First cut analyzes at base level**; leveled stat
projection is a deferred fast-follow (needs the recruit schedule, #45 item 5). Execution + full design: #48.
_Decided: 2026-06-19 (Nicolas)_

**Implementation: the vanilla force comes from a curated array registry, not a per-chapter header.**
The decomp only decompiled enemy `UnitDefinition` arrays to C for the Prologue + Ch1 (`*-eventudefs.h`);
Ch2+ live in the monolithic `events_udefs.c` with address-named arrays interleaved with green/skirmish/
cutscene units that a region-scan would wrongly pull in. So `tools/difficulty.py` resolves a
`parity_reference` through a small **registry** (`PARITY_REFERENCE_UDEFS`: ref → file + the exact fightable
red array names) — the single human-curated point of "which vanilla arrays ARE this chapter's enemies".
Both sides project every enemy (generics AND named bosses) off **class base autoleveled to its level** — a
boss's personal line is the dynamic playtest's concern, not this static proxy — so ours and vanilla resolve
on identical footing and the yardstick/deploy-cap cancel in the ratio. Validation: our Ch1, mirrored 1:1 off
FE8 Ch1, reads at parity (threat ×0.89, clear-load ×0.97, both inside ±25%). Registry curation method for the
events_udefs.c chapters: the arrays a chapter's `chN-eventscript.h` references **whose RED units carry
weapons** — which excludes the interleaved skirmish/tower data (unreferenced) and the cutscene/preview arrays
(endgame villains placed with empty `.items`). Curated + fully modeled: Prologue, Ch1, **Ch2 (9), Ch3 (10),
Ch4 (23), Ch5 (23), Ch6 (25)**. **FE8 Ch13** (our ch08 — a scripted-defeat objective, informational only, not
a CI-gated chapter) is the lone deferred reference. `make difficulty CH=chNN` gains the pressure line;
`make difficulty` (no CH) prints the campaign curve.
_Implemented: 2026-06-19 (CLAUDE; pipeline track, TDD)_

**The parity curve is surfaced in CI, and the hard gate enforces per-chapter via an opt-in `balance_locked` flag (#48 (b)).**
CI's `build` job runs `make difficulty-gate` (`difficulty.py --curve --check`) on every build (after the
submodule checkout it needs to read the decomp HEAD), so balance spikes/sags and parity regressions are
visible on every PR **and** a regression on a finished chapter hard-fails the build. The gate is **per-chapter
opt-in**: because we author chapters as we go (the campaign isn't done until it's basically done), an
all-chapters gate would redden CI for every unwritten chapter. Instead a chapter is enforced only once content
marks it balance-final with **`balance_locked: true`** in its chapter YAML. `curve_gate_failures(rows)` fails a
**locked** chapter that is off-parity (`verdict != OK`), unreliably measured (a dropped boss — an unreliable OK
is not a pass), or has no curated `parity_reference` at all (you can't lock a chapter the metric can't measure —
a config mistake, surfaced loudly). **Unlocked** chapters (unwritten or mid-authoring) stay informational and
never gate, so an in-progress chapter never reddens CI; with zero locks the gate passes (enforces nothing),
which is why `--check` can ship before any chapter is locked. The lock is set in the **content** lane
(`campaigns/**`); the gate logic that reads it is **pipeline** (`difficulty.py`). Workflow: author a chapter's
enemy inventory → confirm it reads OK on the curve → add `balance_locked: true` → CI now defends it.
Decision: explicit flag over auto-detecting an authored force, because a parity gate's job is to lock in
*finished* work — auto-detect can't tell "balanced" from "halfway through placing enemies" and would fire
mid-authoring (Nicolas, 2026-06-21).
_Implemented: 2026-06-19 (informative curve); per-chapter gate enforcing 2026-06-21 (CLAUDE; pipeline track, TDD)_

**Monster/exotic enemy weapons stay out of the content-owned weapon map; venin is a base-might proxy (#53).**
FE8 Ch4 "Ancient Horrors" (all-monster) and Ch6 "Victims of War" needed weapons our cast never carries: the
monster claws (`fetid/rotten/venin-claw`), Evil Eye, and extended standards (`thunder`, `halberd`, `venin-axe`,
`iron-blade`, `horseslayer`). Their stats live in `fe_combat.W`, but the decomp-item→weapon mapping for them is
a **difficulty-local** `VANILLA_ONLY_ITEM_TO_WEAPON` merged into `ITEM_TO_WEAPON` — deliberately **not** in
`inject/decomp.py`'s content-facing `WEAPON_ITEM_ENUM` (that map drives the build's authored YAML loadouts and
is content-owned across the seam; our cast authors none of these). Modeling calls: **venin/poison weapons**
(which drain HP over turns in vanilla, not on-hit) are modeled at their **base might** as a low static-DPR
proxy — low threat, but the unit still resolves and counts as modeled rather than being dropped. **Monster
claws** are plain physical might (off-triangle, vs Def); **halberd/horseslayer** keep their effective-vs-cav
triple. **Staff-only healers** (a Priest/Troubadour carrying no weapon) are still dropped by design — that is a
weaponless drop, not an unmodeled-weapon drop, so an all-modeled reference can legitimately resolve fewer
units than it has armed-RED entries (Ch6: 27 armed → 25 modeled). _Implemented: 2026-06-19 (CLAUDE; pipeline track, TDD)_

**A fielded healer/support unit is modeled as weaponless (0 throughput, still a body for durability); `_weapon_for` honors the YAML `unlock` flag (#62).**
The difficulty engine couldn't fairly model a staff-only unit (our Sclorbo, vanilla's Moulder): `_weapon_for`
either crashed (`attack_speed` → `NoneType.wt`) or mis-roled a base healer as an attacker by crediting a tome
its base class can't wield. Two changes: (1) **`fe_combat` is now None-weapon-safe** — a `Combatant(weapon=None)`
has attack speed = Spd (no weight to bear), deals 0 damage / 0 throughput as an attacker, but is a valid
*defender* (enemies still resolve hit/damage against it, so its durability is computed). (2) **`_weapon_for`
skips inventory items whose `unlock` precondition isn't met** for the modeled (base-class) state — the YAML's
own `unlock: promotion` flag (e.g. `sclorbo.yaml`'s Light tomes) is the data-driven gate, cleaner than
inferring class weapon-ranks. So a base Priest resolves to **weaponless support = 0 throughput**, mirroring
vanilla Moulder, instead of an inflated 0.84 kills/round. **Healing itself stays unmodeled** (the static proxy
disclaims it; both our and vanilla fields run a healer, so `durability(min)` understatement is largely a
canceling artifact) — modeling heal-per-turn was scoped out as optional. _Implemented: 2026-06-20 (CLAUDE; pipeline track, TDD)_

**The vanilla PLAYER deploy field is derived from the decomp per chapter, not hand-maintained (#61).**
The party-side parity delta (our cast vs vanilla's deploy on the same enemy set) was keyed off a hand-curated
`VANILLA_FIELDS` dict that only held Ch1, so every other chapter printed "delta skipped." It now derives from
the decomp (HEAD) the same way the enemy force does: `PARITY_REFERENCE_ALLY_UDEFS` maps a chapter's
`parity_reference` to the reference chapter's blue force-deploy + reinforcement `UnitDefinition` arrays
(e.g. `UnitDef_Event_Ch1Ally`/`…AllyReinforce`, `UnitDef_Event_Ch2Ally`). Each named ally resolves to
**class base + its personal line** (the same donor-base inheritance our cast uses, via the unit's `.charIndex`)
— allies are **not** autoleveled (CharacterData stores their join-level display stats), and the weapon is the
**first attacking item** (symmetry with how `player_combatant` models our cast; a staff-only ally → weaponless
support per #62). `VANILLA_FIELDS` is deleted. The Ch1 delta is materially unchanged (throughput 3.74 → 3.69,
durability/carry identical) — the small shift is *more* faithful (Seth/Franz now use their equipped first weapon
from HEAD, not a hand-picked strongest), and Gilliam's hand-typo Con 13 is corrected to 14. _Implemented: 2026-06-20 (CLAUDE; pipeline track, TDD)_

**How the deploy cap + prep screen are actually wired (the [decomp] mechanism).**
`hasPrepScreen` in `chapter_settings.json` is dead — "left over from FE7"
(`chapterdata.h:37`). The real gate is the `PREP` event command (0x3E,
`Event3E_PrepScreenCall` → `gProcScr_SALLYCURSOR`): every vanilla prep chapter
(Ch4+) ends its beginning scene with `CALL(EventScr_08591FD8)` (`eventscr.c:4283`,
a shared `CLEAN`/`PREP`/`CLEAN` script), and so does our ch01. The deploy cap is
the **ally `UnitDefinition` table itself**: `GetChapterAllyUnitCount()` counts its
entries (zero-terminator scan), the prep flow clamps deployment to that count
(`SortPlayerUnitsForPrepScreen`), and the table's `xPosition/yPosition` are the
deploy tiles. The table is never LOADed on a prep chapter — the whole party joins
via a separate join-LOAD in the beginning scene and the engine benches everyone
past the cap. Force-deployment = `gForceDeploymentList` (`data_event_trigger.c`,
`{pid, route, chapter}`; vanilla: Eirika/Ephraim everywhere + per-chapter joiners) —
#42's chosen-lord patch point. Prep-header cosmetics: `prepScreenNumber` in
chapter settings is a double-wide glyph index = **2 × chapter number**.
Note ch01 has a prep screen where vanilla Ch1 has none: the cap is the parity;
Pick Units only chooses *which* PCs fill it (Nicolas, 2026-06-10).
_Decided: 2026-06-10 (decomp trace, ch01 slice)_

**Ch2 "Cold Welcome" hosting (#22): slot 3, party-persist, DefeatAll — simpler than ch01.**
ch02 rides the *next* vanilla slot after ch01 (slot 2 → slot 3, `CHAPTER_L_3`), reached by
ch01's ending `MNC2(0x3)` (was the dev placeholder). Three ways it diverges from `inject_ch01`,
all because the slice is mid-campaign rather than the cast's first chapter:
(1) **Party persists** — no *founding-cast* join-LOAD; the saved roster carries over and the prep
flow fields 5 of it (cap = `UnitDef_Event_Ch3Ally` entry count). The one exception is an **off-map
recruit** who joined in a cutscene and was never a unit (Baxby, ch01 ending): he gets a small
between-chapter join-LOAD before PREP so he enters the saved party — see the Recruit-wiring ADR. (2) **No lord-select** — the lead was
chosen in ch01; the flag-driven `IsCharacterForceDeployed_` hook auto-force-deploys it in *any*
later chapter with zero per-chapter wiring (only `CauseGameOverIfLordDies`, already vanilla in
`EventListScr_Ch3_Misc`, is needed). (3) **DefeatAll, not Seize** — the slot-3 host `goal` is
swapped to vanilla **slot-4's `defeat_all` template** (`windowDataType: defeat_all`), and the
vanilla Ch3 `Seize(14,1)` + chests/doors are dropped from `EventListScr_Ch3_Location`, so the
engine's `CountRedUnits()` rout-win is the only path.
**The combat is a faithful reskin of vanilla FE8 Ch2 "The Protected" (the parity_reference).**
The RED band (`UnitDef_088B463C`, Beginning-scene `LOAD1`) is vanilla Ch2's exact count/level/mix —
4 generic Brigand (L3, L3-drops-Vulnerary, L3, L2) + 1 Archer (L1) + Bone (named L4, fixed) + Bazba
(named L6, Steel Axe), grounded in decomp tables `UnitDef_088B4344` + `UnitDef_088B44AC` —
**reflavored as chardalyn berserkers** (Auril-maddened humans; real axes/bow = zero reskin stretch, so
balance is exactly vanilla's). Halvar rides the Bazba slot, Grukk the Bone slot. The turn-3
reinforcement pair (vanilla `UnitDef_088B4470`: L2 + L3 Brigand) rides `UnitDef_088B4758` (the empty
vanilla table), freeing `UnitDef_088B4718` for the protect layer.
**The protect layer = three GREEN chwinga, with a per-unit soft-fail charm-gift (the chapter's
signature beat).** Replaces the abandoned sled-defend idea. The chwinga are harmless snow-spirits
(book: "Starting Quest: Nature Spirits", p25–26) on the **Pegasus chassis** (`CLASS_PEGASUS_KNIGHT`) —
the verified balance match to vanilla's green Ross+Garcia (3 pegs ≈ 9–11 output vs 12; Mage over-shoots
Res≈0 brigands, Myrmidon wildly over). They LOAD GREEN from `UnitDef_088B4718` (vanilla Ch3's Colm
green table, repurposed), ride three distinct minor NPC slots (DARA/KLIMT/MANSEL) so each is
individually trackable, and the **single enemy Archer hard-counters the fliers** — that bow IS the
protect tension. The mechanic is the idiomatic FE8 survival idiom, NOT a death-flag: at the ending
scene each chwinga's survival is read with `CHECK_ALIVE` → `BEQ(skip, EVT_SLOT_C, EVT_SLOT_0)` →
`SVAL(EVT_SLOT_3, <charm>)` + `GIVEITEMTO(player leader)`. A fallen chwinga simply forfeits its own
charm — never a game over. The three charms are vanilla Ch2's three village gifts 1:1 —
**Red Gem `0x76` / Elixir `0x6D` / Pure Water `0x6E`** (in-budget by the Reward ADR; no boosters/promos).
No on-map chest and `gold_reward: 0` — vanilla Ch2 has neither (the gifts ARE the loot).
**Two non-obvious gotchas this surfaced:**
• **The winter map is a faithful reskin — walkability ≈ vanilla FE8 Ch2.** A cell-by-cell terrain
diff (our `.mar` vs vanilla `Ch2Map`, terrain bytes off each tileset's `.bin`) differs on **2 of 225
cells** (the two village tiles). So positions are authored on the built `.mar`'s walkable tiles
(plains/forest), verified in-bounds. Two real traps: (1) author against the committed **`.mar`**, NOT
an ephemeral editor-export grid — that review grid disagrees with the build on ~5 cells; (2) positions echo
vanilla Ch2's geography (boss/archer/Bone east, the lone Vulnerary-dropper on vanilla's SW `(6,10)`
tile, chwinga + party NW) but stay on distinct walkable cells — vanilla stacks several units on shared
spawn tiles via REDA entry-paths, which our `redaCount: 0` direct placement can't. (The parity the gate
enforces is the enemy *count/level* mix, not exact tiles.)
• **Ch2 cutscene msg-id pool = dead vanilla Ch3 scene texts** `0x98b–0x992, 0x995–0x99a`
(referenced only by the `ch3-eventscript.h` scenes our host overwrites). **`0x993`/`0x994` are LIVE
battle quotes in `data_battlequotes.c`** and are deliberately excluded — the exact false-negative
the handoff warns hex-grep produces.
**Deferred (flagged in code, not in this pass):** the **dialogue reground** — the LOCKED 2026-06-19
cutscene text still frames the dropped sled (Wolfram's rear-bark "…the sled"; the ending narration
"…ringing the sled") and the reinforcements as "Snow Wolves", and the opening lacks a chwinga intro
beat; this is a Nicolas co-write via the `dialogue-pass` skill (chwinga intro beat + de-sled the
bark/ending), wired as placeholder meanwhile. Also deferred: the **chwinga art** — map-sprite reskin +
portraits + name-text (`Mote/Rime/Glimmer`) over the DARA/KLIMT/MANSEL placeholder slots (#38/#39);
Vellynne's cutscene bust (#19 — placeholder `FID_Ismaire` face meanwhile); the chardalyn map-sprite
reskin (vanilla brigand sprite for now); the "Chapter 2" title-card glyphs (atlas lacks C/W/d/m); and
the in-game load-test. The chapter builds green, decodes clean (`verify_text` 0 runaway), holds
difficulty parity, and chains ch01 → ch02 → ch03 (`MNC2(0x4)`; see the Ch3-chains ADR above —
the ch02 ending's original dev-placeholder landing was retired when ch03 landed).
_Implemented: 2026-06-22 (CLAUDE; content track — host wiring + cutscenes, build-green). Reground
2026-06-22 (CLAUDE) — vanilla-Ch2 enemy parity (chardalyn berserkers), 3 green chwinga + per-unit
soft-fail charm-gifts, sled dropped._

**No world map ⇒ `GetBattleMapKind()` falls back to STORY (engine hardening).**
Vanilla classifies most chapter slots (slot 2 onward — `CHAPTER_L_2`...) by scanning
`gGMData` world-map node state and falls back to `BATTLEMAP_KIND_SKIRMISH` when no
node matches; entering through the world map guarantees a node match. Our boot and
`MNC2` chapter hand-offs never populate `gGMData`, so every node-slot chapter was
misclassified as a skirmish — which swaps the beginning scene for
`EventScr_SkirmishCommonBeginning` (black-screen hang; `bm.c CallBeginningEvents`),
hides the ally unit table, and disables force-deploy. Patched in
`build_campaign._patch_battle_map_kind_fallback`: the no-node fallback returns
STORY. Skirmishes are unreachable without a world map, so nothing legitimate hits
the old fallback. Slot 1 (ch00's host) never needed this — it's in the function's
hardcoded STORY list, which is why the prologue worked and ch01 didn't.
_Decided: 2026-06-10 (ch01 slice debugging; found via proc-table dump → `evStart =
EventScr_SkirmishCommonBeginning`)_

**Game over = the lord-analog only; story-required allies "retreat" instead.**
A chapter's game-over trigger is the must-survive lead alone (ch00: Hlin; from Ch1
the player-chosen lord, #42) — vanilla's exact shape: only Eirika/Ephraim carry
`EVFLAG_GAMEOVER` quotes everywhere, Seth's death quote has no flag. A story-required
non-lord ally (ch00: Scramsax) gets a **flag-less defeat quote** framed as a retreat
("too weak to continue the fight"): the battle continues, and the character is out of
the fight, not dead, so later chapters can use them freely. Vanilla also supports
per-chapter `EVFLAG_GAMEOVER` for guests (Duessel Ch10, Mansel Ch19) — available if a
future chapter truly needs it, but the default is lord-only.
Mechanism note: injected `gDefeatTalkList` entries go at the **head** of the list —
see "Chapter outcomes ride gDefeatTalkList" below for why.
_Decided: 2026-06-09 (Nicolas; retreat framing is his)_

**Player-chosen lord (#42): route-split menu between the Northlook muster and preps.**
The player picks the company's must-survive lead — presumably the PC they played in
the campaign — once, in ch01's beginning scene, *after* the muster (the bar-scene
beat) and *before* the prep screen locks them into the field (placement: Nicolas,
2026-06-10). UI is a clone of vanilla's post-Ch8 route-split menu
(`CallRouteSplitMenu`, `ch8-eventscript.h`): `ASMC` opens a `StartMenu` over the
map, each pick shows a per-candidate confirm text whose `[Yes]` answer lands in
`EVT_SLOT_C`, and "No" loops back to the menu. Candidates = the classed cast in
`PORTRAIT_MAP` order; menu defs, candidate table, and confirm texts are
build-generated (no character names in C).
**Persistence:** one *permanent* event flag per candidate, `0xF0 + menu index` —
permanent flags (ids ≥ 101) ride the save file, `ResetPermanentFlags` (`bmsave.c`)
zeroes them on New Game, and vanilla scripts touch none above `0xE7`, so the 0xF0
block is ours. `LordSelect_GetPid` (injected, `eventinfo.c`) scans the flags;
fallback while unset = first candidate (Braulo), so a debug entry straight into a
chapter never soft-locks.
**Hooks** (campaign-agnostic, `build_campaign._inject_lord_select_engine`):
`IsCharacterForceDeployed_` — the chosen lead is always fielded by the prep flow;
`CanUnitSeize` — Seize belongs to the chosen lead (vanilla hardcoded
Eirika/Ephraim); `UnitKill` — the chosen lead's death raises `EVFLAG_GAMEOVER`
(caught by each chapter's `CauseGameOverIfLordDies` AFEV) whatever the death path;
and the vanilla **route-wide** Eirika/Ephraim `EVFLAG_GAMEOVER` defeat entries are
demoted to flag-less quotes so the PCs riding those slots can die like anyone else
when not chosen. Scene gotcha: chapter loads come up black — the menu needs the
vanilla `FADU(16)`-after-LOAD idiom (cf. Ch4) or it runs invisibly.
Verified by the `ch01lord` playtest: pick the last candidate (benched by default
under the 4-cap) → flag set, force-deployed with the cap intact, death = game-over
screen; ch00 gameover/retreat semantics unchanged.
_Decided: 2026-06-10 (placement Nicolas; mechanism decomp-traced; closes #42)_

**Lord-select UI (#46): the existing #42 menu COMPOSED with stock components, not a bespoke screen.**
The pick screen shows each candidate's portrait + a qualitative **pitch** (strengths/weaknesses
in words; **no numeric stats** — a hand-authored `lord_pitch:` per PC YAML, Nicolas 2026-06-21)
so the choice is informed. The #42 menu already works — a candidate list over the scenic BACG
with a route-split confirm flow (pick → "Will N lead?" [Yes/No] → permanent flag
`LORDSEL_FLAG_BASE + i`, read by `LordSelect_GetPid`). #46 only adds the info panel, by
**composing ready-made components** rather than building a screen: each `MenuItemDef` gets the
engine's built-in **`onSwitchIn`** hook (`uimenu.c`), which as the cursor lands on candidate *i*
draws their **chibi face** via `PutFaceChibi` (a BG-tilemap face — it layers over the scenic
BACG, **no OBJ-vs-BG priority fight**) and their **pitch** via the stock, self-framed,
auto-wrapped **`StartHelpBox`** (one msg id per candidate, parallel to `gLordSelectCandidates[]`).
The candidate **names are the menu list itself** (the first place the game states them — the
onboarding requirement). Portrait id + name come from each pid's `CharacterData`, so nothing
depends on units being loaded at menu time. A one-time explainer text box precedes the pick loop
(feedback item #4's "(a) explain"). **Why not the earlier plans:** the first hand-built menu used
a full-bust `StartFace2` (an OBJ sprite that lost the priority fight to the scenic BACG) + custom
frames that wouldn't draw — so it was abandoned. The follow-up plan to **clone `prep_unitselect.c`**
into a dedicated `engine/lord_select_screen.c` was dropped as over-engineering (Nicolas, 2026-06-24):
the game is full of reusable boxes/menus/faces, and the eventscript TU keeps no mutable storage
(no `.bss`/`ewram_data` placement), so a Text-managing screen there is the wrong shape. Compose
`PutFaceChibi` + `StartHelpBox` + the existing menu instead. All of it lives where the #42 menu
already does (build-generated into `ch2-eventscript.h`); no new engine source, no injection hook.
Full DoD checklist lives on **#46**.
_Decided: 2026-06-24 (Nicolas; "grab reusable components, don't build bespoke"; supersedes the
2026-06-22 prep_unitselect-clone direction; tracked on #46)_

**Chapter outcomes ride gDefeatTalkList; entries go at the HEAD of the table.**
A chapter's win and lose are both event-flag watchers in `EventListScr_<Ch>_Misc`
(vanilla Prologue shape, `prologue-eventinfo.h`): `DefeatBoss(<ending scene>)` fires on
`EVFLAG_DEFEAT_BOSS` and `CauseGameOverIfLordDies` fires on `EVFLAG_GAMEOVER`. Neither
flag is set by the engine directly — **both are set by the dying unit's `gDefeatTalkList`
entry** (`.flag` on the defeat quote; `CA_BOSS` alone sets nothing — every vanilla boss
has a chapter-keyed entry with `EVFLAG_DEFEAT_BOSS`). Three traps, all hit on 2026-06-09:
- Emptying the Misc list silently removes BOTH the win and the lose condition.
- `GetDefeatTalkEntry` (eventinfo.c) returns the FIRST match, and vanilla gives every
  playable slot a generic `chapter = 0xFF` death quote mid-table — so injected
  chapter-keyed entries must go at the **head** of the list (vanilla's own ordering:
  boss entries first, generics after), or e.g. NATASHA's generic quote shadows the
  flagged one and game over never fires. Never append after the `{.pid = -1}`
  terminator either: the scan stops there.
- The goal banner ("Defeat boss" vs the host chapter's "Seize gate") is chapter DATA
  (`chapter_settings.json` `goal`), not events — copy the vanilla Prologue's block.
Boss AI gotcha: O'Neill's `.ai = {0x6, 0x3, …}` decodes to **DoNothing + NeverMove**
(`cp_data.c gAi1ScriptTable`/`gAi2ScriptTable`) — he only attacks because the vanilla
tutorial event-scripts it. For unscripted stationary-aggressive bosses copy Breguet:
`{0x3, 0x3, 0x9, 0x20}` (ActionStanding 100% + NeverMove).
_Decided: 2026-06-09 (found via the automated ch00 playtests; see Automated playtests)_

**Automated playtests: mGBA Lua scripting drives deterministic win/lose checks.**
`tools/playtest/run.sh win|gameover|retreat|titlecard` runs a scripted ch00 playtest in the mGBA
0.11 nightly (`--script`; auto-downloaded to `tools/emulator/`, gitignored): a Lua
coroutine injects buttons closed-loop against real memory (cursor `gBmSt`, phase/turn
`gPlaySt`, units `gUnitArray*`, menus + game-over via `sProcArray` proc scans, pathing
via the game's own `gBmMapMovement`), with symbol addresses regenerated from the ELF
each run (`gen_symbols.py`). Deaths are engineered by HP-poking units then letting real
combat resolve, so the event engine is exercised end-to-end; verdicts are memory
asserts (chapter index change / game-over proc), not pixels. Exit 0 = PASS; artifacts
(log + milestone screenshots) in `/tmp/playtest-<scenario>/`. Synthetic macOS
keypresses still don't reach mGBA — in-emulator scripting is the supported path.
Art/feel checks stay human (Nicolas).
_Decided: 2026-06-09 (titlecard scenario added 2026-06-09: opens the map-menu Status
screen — which decompresses the title card — and screenshots it, so recomposed titles
get eyeballed without a manual run)_

**Playtest platform first brick = a generic SMOKE LIVENESS net, not more hand-scripted scenarios (#49).**
The #49 spine is `I/O harness → stability fuzzer → LLM-player`. The first brick is a generic driver that
boots any reachable chapter, **idles every player unit and just ends the turn each phase**, and asserts the
chapter reaches a clean terminal **with no crash/soft-lock/hang** — most chapters terminate in a *loss*
(idle party overwhelmed), which for a *stability* net is a fine clean terminal. The point is to exercise
load + every phase/event path to a clean end as content lands (#20–#28), catching the boot/soft-lock/text-
decoder-runaway class — not to win (winning is the next brick, a greedy clear-bot). **Two outcomes:** PASS
(exit 0) = no crash/soft-lock over the run, whether it reached a clean terminal OR just survived the turn
budget still cycling; FAIL (exit 1) = soft-lock (or a crash, caught by run.sh). An idle party usually *can't*
force a terminal (verified: both prologue and ch01 survive 30 idle turns), so budget-survival is the normal
healthy outcome and counts as PASS — an earlier INCONCLUSIVE+WARN bucket was dropped because a warning that
fires on every healthy run is noise. Completability ("can it be *won*") is the clear-bot's job, not this
net's. The stability verdict is a **pure function over
state snapshots** (`tools/playtest/liveness.lua`: `{frame,turn,faction,hpsum,procfp,chapter_advanced,
gameover}` series → `LIVE|TERMINAL_WIN|TERMINAL_LOSS|SOFTLOCK`) so it is **unit-tested without an emulator**
(`test_liveness.lua`, run by `make test`) — soft-lock = no change in `{turn,faction,hpsum,procfp}` for
`softlock_frames` while input is being fed; budget-exhaustion and a wedged emulator live outside the pure
verdict (driver → INCONCLUSIVE; run.sh wall-clock → ERROR). This makes `lua` a **dev dependency** (macOS:
`brew install lua`; `make test` skips the Lua tests with a notice when it's absent). The smoke **driver**
is just another scenario in `harness.lua` (`scenarios.smoke*`) reusing the primitives already in scope —
`harness.lua` is the I/O harness (primitives + scenario registry + per-frame coroutine runner) in one file,
so a scenario already shares everything: no `io_core` extraction, one file = single source of truth. Only
the pure verdict is a separate module (`liveness.lua`). Extracting an `io_core` for a future non-coroutine
consumer (the fuzzer's external driver / LLM-player) is deferred until one actually exists (YAGNI).
_Decided: 2026-06-19 (CLAUDE; pipeline track. liveness.lua + tests landed TDD; smoke driver scenario + run.sh wiring follow)_

**Playtest platform brick 2 = a greedy CLEAR-BOT that proves completability with real combat (#60).**
The smoke net proves a chapter doesn't crash/soft-lock; the clear-bot proves it can be *won* — and is the
rule-based precursor to the LLM-player (swap the policy later). `scenarios.clear` actually plays the chapter
(no `pokeFrail` cheat like `scenarios.win`): each player phase it marches every unit at the boss and attacks
with real combat, rides out enemy phases, and wins when the chapter advances (FAIL on game-over or a turn
budget). **Boss detection is generic** — a red unit whose `CharacterData.attributes` (`pCharacterData` at
Unit `+0x00`, attributes `+0x28`) has `CA_BOSS = (1 << 15)` (`include/bmunit.h:326`) — no hardcoded char ids
(verified: finds Sephek `0x68` on the prologue). The target choice is a **pure** function
(`clearbot.lua` `pickTarget(reachable, enemies, prefs)`: melee-range, boss-first then lowest-HP), unit-tested
without an emulator (`test_clearbot.lua`, in `make test`) — driving stays in the scenario. **Both win
objectives are handled generically by one `clearDrive` loop**: kill the boss, and if the chapter hasn't
already advanced (DefeatBoss), send a unit onto the boss's old tile to **Seize** (the seize tile = the dead
boss's tile; a non-seizer just Waits, so the loop tries the next unit) — win = chapter advances OR the title
screen (ch01's ch02 isn't hosted). A naive greedy melee strategy cleared **both the prologue (DefeatBoss) and
ch01 (Seize, real combat through a 10-goblin escort) in 3 turns each** with no `pokeFrail` and no game-over —
no gang-up/heal/don't-feed-the-lord logic needed yet (harder chapters may). ch02+ (save-state checkpoints) is
the remaining follow-up (#60).
_Decided: 2026-06-19 (CLAUDE; pipeline track. pickTarget TDD; scenarios.clear + clear_ch01 + clearprobe verified on a built ROM)_

**Playtest platform brick 3 = a SEEDED random-input fuzzer ("smart monkey") over the same I/O layer (#49).**
The directed smoke/clear bots only ever drive clean, scripted input orderings; the fuzzer injects *random*
inputs to surface the crashes/soft-locks those miss. Decisions:
- **Reproducibility is the contract** — a crash is worthless if it can't replay. So the fuzzer uses our **own**
  LCG PRNG (`fuzzrng.lua`, not host `math.random`, which differs between the CI `lua` and mGBA's embedded
  Lua), giving an identical input sequence for a given seed on any Lua ≥ 5.3. Seed comes from `PT_SEED`
  (default 1), is logged, and a FAIL prints `PT_SEED=N run.sh fuzz` to replay. The PRNG + weighted input
  policy are the **pure** core, unit-tested without an emulator (`test_fuzzrng.lua`, in `make test`).
- **Broad in-chapter surface + a B-mash unstick watchdog**, not a restricted key set (Nicolas deferred the
  call; this is what mature game-QA soak-bots do). All keys incl. START/SELECT (so menus get coverage),
  weighted toward the productive map keys. The watchdog handles the false-positive risk: liveness gets a
  second, shorter `nudge_frames` stall threshold → state `NUDGE` → the driver mashes **B** to back out of a
  benign menu. If even a full softlock-window of B can't escape, that **is** the bug (a screen with no exit).
- **Soft-lock = UNRESPONSIVENESS, not lack-of-progress.** Two false positives surfaced and were fixed in the
  *driver* (liveness.lua stayed pure): **(1)** a random Suspend drops to the title screen — a legit non-crash
  state where the progress key is frozen and B can't escape; the driver detects "not on a live map"
  (`liveOnMap` = a blue unit loaded and not on the title proc; deliberately *not* `inChapter`, which is false
  during a legit enemy phase) and treats leaving the map as a clean fuzz terminal instead of judging
  liveness or injecting recovery inputs into an unrelated screen.
  **(2)** the bot roams the cursor without ending a turn, so the smoke bot's progress key
  `{turn,faction,hpsum,procfp}` sits still on a *responsive* map; the fuzz driver instead feeds a
  **responsiveness fingerprint** (`fuzzFingerprint` folds the map cursor into the `procfp` field) so "no
  change" means the game stopped *responding*, not that the random bot hasn't progressed. Verdicts: clean
  terminal (win/loss) or surviving the frame budget = PASS; a genuine freeze = FAIL. Boot/title/prep fuzzing
  is a separate, noisier surface, deferred. Verified on a built ROM: 5 seeds clean (1 win, 4 budget-survival),
  no false positives. The remaining #49 spine after this is the LLM-player (swap the rule-based policy).
_Decided: 2026-06-19 (CLAUDE; pipeline track. fuzzrng + liveness NUDGE TDD; scenarios.fuzz + fuzz_ch01 verified across seeds on a built ROM)_

**Playtest platform brick 4 = an LLM-player as a SOAK/BALANCE tool, built policy-and-transport-first (#63).**
The final #49 spine brick swaps the greedy clear-bot's rule-based `pickTarget` for an LLM *policy* over the
same I/O layer. Its job is dynamic balance signal — when a competent player loses units or barely clears a
chapter, that's the same signal `difficulty.py` models statically, now observed live; its credibility bar is
beating vanilla FE8 (so the signal isn't overfit to our maps). Locked architecture (brainstormed w/ Nicolas):
- **Transport = sidecar file-handshake.** mGBA's embedded Lua can't make network calls, so the harness
  serializes the board to a request file and blocks; an external `tools/playtest/llm_player.py` (Anthropic SDK,
  ordinary testable Python) decides and writes the response. Mirrors the platform doctrine — *pure core, driver
  owns I/O* — with the LLM **policy** in the Python sidecar. (Rejected: in-emulator socket = fragile.)
- **Granularity = per-turn commander.** The LLM gets the whole board once per player phase and emits an ordered
  list of unit orders; the harness executes them with existing primitives. ~6–8× fewer calls than per-unit and
  better play (tactics are interdependent: gang-up, bait, stay out of boss range).
- **Model = Sonnet default, `PT_MODEL` knob.** A weak player fires *false* balance alarms, defeating the soak,
  so default to one that plays well; a cheap Haiku soak is one flag away. No tiered/escalation plumbing (YAGNI).
- **Determinism + cost = one artifact, the board-hash-keyed transcript.** Each decision is keyed by
  `hash(serialize_board) + seed + chapter + turn`: replay hit → cached orders (free, deterministic); miss in
  replay → hard fail; miss in local soak → call the LLM, append. This single mechanism satisfies the platform's
  "replays identically on CI `lua` and mGBA" rule **and** makes re-soaks cost nothing.
- **M1 (this commit) = the three PURE cores only, no LLM calls** (TDD, `tools/test_llm_player.py` in `make
  test`, no emulator): `serialize_board` (deterministic compact JSON — units normalized by id so unit-array
  iteration order can't change the bytes/key), `validate_orders` (illegal orders → a `rejected` list with
  reasons so a bad LLM turn is dropped, never soft-locks — the harness runs the survivors), and `Transcript`
  record/replay keyed by `transcript_key`. Swap point stays the pure `clearbot.lua pickTarget`. M2 wires the
  sidecar handshake + `llmDrive` scenario (replay-only on the prologue), M3 the live policy, M4 the soak report
  into the difficulty curve, M5 the vanilla-FE8 validation milestone (needs a save-state checkpoint).
_Decided: 2026-06-20 (CLAUDE; pipeline track. Epic #63; M1 cores TDD'd green, 20 asserts in make test)_

**#63 M2 = the sidecar handshake ships PROVIDER-AGNOSTIC — a free local model is one env var away.**
Nicolas (2026-07-02) was cost-shy about the LLM-player; the happy medium is supporting free local models
(Llama/Gemma via Ollama or llama.cpp) alongside Anthropic. Settled:
- **Two transports, no SDK dependency.** `llm_player.py` speaks the Anthropic Messages API *or* any
  OpenAI-compatible `/chat/completions` endpoint, both via stdlib `urllib` (~15 lines each; a new dependency
  for two POSTs is the bigger risk, and the sidecar must run anywhere a playtester has python3). Knobs:
  `PT_PROVIDER` (`anthropic` default per the epic's "a weak player fires FALSE balance alarms" — Sonnet;
  `openai` = OpenAI-compatible), `PT_MODEL`, `PT_BASE_URL` (openai default = local Ollama,
  `http://localhost:11434/v1`), `PT_API_KEY`/`ANTHROPIC_API_KEY` (the latter feeds ONLY the anthropic
  transport — resolving it for the openai provider would Bearer-leak the Anthropic secret to whatever host
  `PT_BASE_URL` names). **The free path is plumbing/smoke value; the paid path is balance-signal value** — a
  Gemma-grade commander proves the loop and soaks for crashes, but its losses are weak evidence about chapter
  difficulty. Both record into the same transcript format. Model output passes a non-finite gate (`NaN` /
  `1e999`→inf orders are culled) — a one-off model hiccup must not record a transcript entry the strict
  Lua-side JSON reader can never parse.
- **Handshake = numbered files, tmp+rename both directions.** Harness writes `req-<n>.json`
  `{seed, chapter, turn, faction, board}` into `PT_LLM_DIR` and polls (wall-clock deadline — at 240fps a
  frame budget would be 4× too impatient); sidecar answers `resp-<n>.json` `{orders, rejected}`, lowest
  unanswered request first, and drains pending requests before honoring its `stop` file — **which `run.sh`
  touches when the run ends**, so the sidecar saves its transcript and exits on its own (no Ctrl-C-dependent
  save). Every write on both sides is tmp+`rename` so a poller never reads a half-written file; `run.sh llm`
  clears stale handshake files (a leftover `resp-1.json` would satisfy the first poll instantly with last
  run's orders), the sidecar tolerates a request vanishing mid-step (that cleanup can race a sidecar started
  first) and warns at startup about pre-existing requests (usually a crashed prior run).
- **Validation lives sidecar-side; the harness re-checks only what can change.** Orders pass
  `validate_orders` against the request's own board before they ship — including: attack targets must be
  foes and staff targets allies (friendly-fire "attacks" would blind-A into the Trade/Item submenu); a unit
  the exporter gave no `range` (staff-only/weaponless) can target nothing; `seize` is gated on the board's
  objective (the export carries no goal tile). The Lua executor re-checks just the mid-phase deltas (target
  died to an earlier order → reject before input) and stops on failed menus without rescue input. Any
  live-policy failure (endpoint down) still answers the harness with an `{error}` response — a fast
  diagnosable FAIL, not a 90s timeout;
  a replay-mode transcript miss does the same and exits non-zero — CI/replay stays closed-world.
- **Exported unit ids: blue = charId (PCs are unique), red = 1000+slot** — generic enemies *share* a charId,
  so the slot disambiguates which brigand an attack order targets.
- **Lua JSON is a vendored ~200-line subset (`tools/playtest/json.lua`), not a library.** mGBA's Lua has no
  JSON; encode writes sorted keys (deterministic bytes, mirroring the serializer doctrine), decode rejects
  trailing garbage (a truncated file must not half-parse into plausible orders). Unit-tested without mGBA
  (`test_json.lua`, 45 asserts) + a cross-language round trip (Lua req → Python sidecar → Lua resp) verified.
- **M2 limitations (deliberate, → M3):** staff orders fail closed as unsupported. Attack command/weapon/target
  selection now runs through the state-driven controller below; choosing among multiple legal targets by
  policy remains an M3 concern. In-emulator prologue
  replay needs local mGBA (CI has none — the platform rule); the protocol itself is fully unit-tested.
_Decided: 2026-07-02 (CLAUDE; pipeline track. Epic #63 M2 + Nicolas's free-model direction; 23 new Python
asserts + 45 Lua asserts in make test)_

**Playtest controller contract = observe, classify, enumerate, guard one input, verify, trace (#220).**
**Standing rule, in Nicolas's words: no brute-force, row-probing or cadence input in a scenario —
reproducible is not the same as justified.** Timing and plausible-looking button sequences are not game-state evidence. The shared mGBA driver reads
FE8U memory directly and turns exact Proc scripts/current callbacks plus live engine structures into a named
state. Standard menus are actionable only when their Proc is unlocked, not frozen, and neither ending nor
doomed; commands come from
`MenuProc.menuItems[] -> MenuItemProc.def -> MenuItemDef.overrideId`. Preparations commands come from the
live `ProcPrepMenu` items and callbacks. The minimum stable semantic ids are Talk `0x5A`, Wait `0x6B`, and
End Phase `0x78`; existing shared paths also use semantic Attack/weapon/target, Seize, Visit, and Status
where needed. Fight leaves the main Preparations menu through its live
`PrepScreenMenu_OnStartPress`/START callback—never B/Check Map or the View Map menu. This agrees with the
[official FE8 manual](https://www.nintendo.com/eu/media/downloads/games_8/emanuals/game_boy_advance_8/Manual_GameBoyAdvance_FireEmblemTheSacredStones_EN_DE_FR_ES_IT.pdf),
but live decomp state is authoritative.

The pure `tools/playtest/controller.lua` owns classification and legal-action enumeration. The mGBA-facing
observer/driver in `harness.lua` may execute **one** input only when that action is legal in the current
state; it then waits for a documented postcondition. Unknown, malformed, locked, frozen, or mismatched
states fail closed without a recovery button. Dialogue A is legal only under
`gProcScr_TalkWaitForInput` + `TalkWaitForInput_OnIdle`. Every attempted input emits a JSON transition record
containing frame-adjacent before/after observations, prior state, legal intentions, chosen intention/key,
expected postcondition, and verdict; failures retain the raw Proc inventory and produce a screenshot.
Map selection mirrors `GetPlayerSelectKind` from live `gUnitLookup` state/status/attributes, and movement A
requires both the engine movement map and an unoccupied `gBmMapUnit` tile. Unknown standard menus expose at
most their currently highlighted enabled item, and only when its live `onSelected` callback exists; choosing
that item is scenario policy, not a controller guess. Open Preparations help is passive and receives no input.

Scenarios own goals, assertions, and deterministic policy; the controller owns reusable UI mechanics.
Random actions remain confined to named fuzz scenarios. This does not require rewriting every historical
chapter-specific recorder in one patch, but any path migrated to the controller may not reintroduce row
guesses, cadence dialogue, or unrelated fallback inputs. The unlocked/not-frozen menu check was
cross-checked against the CC0 portions of
[GBA Fire Emblem for Screen Readers](https://github.com/StanHash/GBA-Fire-Embem-for-Screen-Readers);
addresses remain generated from our ELF rather than copied. The same semantic observer is intentionally a
future seam for replay, accessibility narration, dialogue transcript verification, target/forecast
inspection, and external policies—those products are follow-ups, not controller responsibilities.
_Decided: 2026-08-03 (#220; supersedes timing/row-driven common harness mechanics and #63 M2's blind Attack
executor limitation)_

**A scenario that produces a VERDICT may not drive the UI with a raw `press` — enforced, not
reviewed (#238).** #220 set the contract but migrated only the shared paths; the historical
verdict scenarios kept their blind cadences, and a blind cadence makes a green run worthless as
evidence. `ch01win` was the proof: it rode straight through the lord-select Yes/No prompt that
cost #232 three sessions, mashing A at a prompt it never saw, and passed. `check.py
check_verdict_scenarios_are_guarded` now fails the build on one, scoping from **`matrix.yaml`'s
`kind`** and following harness.lua's call graph, with a small named allowlist
(`BLIND_PRESS_ALLOWED`) carrying each exception's reason. `record`/`diagnostic` scenarios stay
blind by design — nothing is asserted there, so nothing can pass for the wrong reason.

Three lessons from the migration, all of which cost real evidence:

- **Count presses by ENCLOSING FUNCTION, never by distance to the next `scenarios.X`.** Splitting
  harness.lua on scenario definitions charges every intervening `local function` helper to
  whichever scenario sits above it. #238's own scope list was built that way and was wrong in both
  directions: it named `retreat` (which has none of its own) and missed `reachRbgCh01` (8) — a
  fifth hand-rolled copy of the ch01 lead route nobody knew was there.
- **A fixed press count is not a walk to a row.** FE8 menus WRAP, so `rows - 1` DOWNs land on the
  last candidate only if the menu opened on row 0. Walk off the LIVE cursor, stop when it arrives,
  and ASSERT where it landed — otherwise picking a different lord than the one the scenario names
  passes silently.
- **Watch the field the engine's key handler actually moves.** `recordunitlist` stopped its roster
  walk on `unk_2c` (the on-screen row, which CLAMPS as the list scrolls under it) and `+0x38`
  (untouched by the D-pad) instead of `unk_30`, so it could capture a fraction of the roster and
  still report PASS.

**Two of these blind presses turned out to be LOAD-BEARING, and only running the scenarios
found them.** Removing a cadence is not a no-op, and neither was worth a guess:

- **`clear_ch02`'s A-mash was answering a prompt the scenario never knew existed.** The ch02
  ending's third charm-gift lands on a full inventory, so FE8 raises
  `gSendToConvoyMenuItems` — "which item goes to the convoy" — and the entire MNC2 chain
  stops until it is answered. The mash resolved it by accident; drive the ending on observed
  state without naming that prompt and the run sits behind it for its whole budget and reports
  "2/3 charms" on a chapter that never left slot 3. That verdict's green had been resting on a
  stray press. The chooser is now a classified `send_to_convoy` state.
- **A scenario's own comment is not evidence.** `recordsupply` claimed "a NON-lord deployed
  unit's action menu has NO Supply row". `SupplyUsability` (bmmenu.c) returns `MENU_ENABLED`
  for the lead **or** for anyone `IsAdjacentForSupply` finds orthogonally beside them — so the
  claim is false for a neighbour, and the first deployed non-lord spawns right next to Pinky.
  The assertion caught the comment, not a defect. Contrast assertions have to be written
  against the engine's rule, not the prose around them.

**What the contract costs, measured, so it is not re-litigated (Nicolas's standing question).**
The gates cost **~1.5s on `make check`** and a few percent on `make matrix` (4–6 min warm, 14/14).
The real cost is not seconds: it is that a new FE8 input state must be CLASSIFIED before a scenario
can drive it. #238 named six in one pass — the inventory list, the send-to-convoy chooser, the
Character screen, the Pick Units grid, the in-map convoy, and four unit commands — and each new
chapter will surface more. That work always existed; the cadence deferred it into mystery failures
instead of paying it. **If the stall detector ever false-positives, `TUNE.stallFrames` is the dial
— do not remove it.**

**The acceptance test for a migrated scenario is the BITE TEST, not a green run.** Break a
classification deliberately and confirm the scenario now FAILS. A migration's whole claim is
"this run means something now", and only a sabotage proves it — #240 established this on
`ch01win` (the same sabotage passed before the migration), and #238 repeated it on the
Character screen (`fail:state-timeout` where the old code, which consulted no classification
at all, could not have noticed) and on the lead-menu walk landing one row short.

**Naming a new state is not finished until the DRIVERS know about it.** Code review caught two
instances on this branch. `item_list` and `send_to_convoy` had classified as `generic_menu`
before they were named, so `cancelToPlayerMap` could back out of both; giving them their own
states silently removed that — and that function is the recovery path #238 had just put behind
`ch01win`'s post-seize menu surprise. `awaitControllerState`'s recovery had the same gap for
`supply_screen`/`unit_list_screen`. **A classification change is a change to what the harness
can escape from**, so a new state ships with its cancel wired in the same commit.

**Enumerate a movement action only where the engine would actually move.** The Character
screen's UP at row 0 is not a no-op: `sub_809144C` sets `unk_29 = 3`, routing into
`sub_80917D8`, the sort-column mode — a persistent input state the observer reports as
`scrolling`, i.e. as a transition offering nothing. Advertising UP there hands a driver an
action that walks it somewhere it has no enumerated way out of, to sit until the stall watch
fires on a wait the controller itself caused. Both ends of that walk are now bounded off
`gUnknown_0200F158`, the same field the engine bounds against — the rule `prep_pick_units`
already followed.

**An absence assertion must assert the state first.** `legalActions` returns `nil` when
`classify` finds no state, and `findAction(nil, …)` is `nil` — so "the command was not offered"
and "we could not tell what was on screen" were indistinguishable. `recordsupply`'s contrast
check now requires a live `unit_command_menu` before concluding Supply is absent.

Also: **a budget must not count the frames a screen spends TEARING DOWN.** `cancelToPlayerMap`
looped eight times total, and the convoy's fade-out held a `transition` for far longer than
that, so the cap decided the failure — the trap `docs/decisions.md` already records from #232.
It now counts CANCELS, with a separate `TUNE.cancelFrames` ceiling for transitions.

Newly classified for it, by the usual four-edit recipe (`gen_symbols.py` WANTED → `CALLBACK_NAMES`
→ `observeController` → a `classify` rule): unit commands Chest `0x5D`, Door `0x5E`, Item `0x67`
and Supply `0x69`; the **inventory list** a unit's Item command opens (`gItemSelectMenuItems`,
`0x43`–`0x47`); the **send-to-convoy chooser** (`gSendToConvoyMenuItems`, `0x2A`–`0x2F`); the
map-menu **Character screen** (`ProcScr_UnitListScreen_Field`); the **Pick Units** deploy grid;
and the in-map **convoy** (`ProcScr_BmSupplyScreen`). The inventory list needed its own state
because `MENU_DISABLED` means something different there: `ItemSelectMenu_Usability` greys any
item the unit cannot *use* — a weapon, a vulnerary at full HP — but `Menu_OnIdle`'s A path never
consults availability and `ItemSelectMenu_Effect` opens the submenu regardless. A greyed row is
still a live row; reading it as a command menu reported "unsupported standard menu" the moment
every item happened to be unusable, which is Hlin's whole inventory at ch00 turn 1. Two ordering rules came
with them. The Character screen and the convoy sit **above `player_phase`** — the map is still in
the proc pool underneath, and `player_map_idle` would offer cursor moves that go nowhere. And each
of the three screens reports a **transition while its own scroll animates** (`unk_29` on the
Character screen, `list_num_pre != list_num_cur` on Pick Units): FE8's key handler does not run in
that window, so an input sent then is lost outright, and calling it an input state is how a press
goes missing. Pick Units' legal moves mirror `ProcPrepUnit_Idle`'s TWO-COLUMN bounds exactly (LEFT
only from an odd index, RIGHT only from an even one short of the end, UP/DOWN by two) — a press
outside them moves nothing, and a driver that assumed a straight list would go on to act on
whoever it was still parked on.
_Decided: 2026-08-06 (#238; extends #220's contract from the shared paths to every verdict scenario)_

**A multi-page screen is driven one guarded press PER PAGE, and the gap between pages is a
real transition — do not classify it away.** `ch05arena` drove the Arena's two pre-fight
dialogue pages with a single press on an 1800-frame budget and reached combat only through
`guardedInput`'s lost-input re-press: a pass by accident, which #255's verdict cache would have
frozen. The fix is a loop that waits for each page to reach its own input wait, presses once with
its own postcondition, and **counts the pages** — so the run asserts the screen's anatomy (the two
`PROC_CALL`s of `gProcScr_ArenaUiMain`, msgs `0x8D5` and `0x8D3`) instead of merely arriving.

The inherited diagnosis was wrong and cost nothing only because it was instrumented before it was
believed. #269 recorded that a bounded loop of presses failed `not-legal` on a `transition` and
concluded `controller.lua` must learn to classify the Arena dialogue state. It already does: an
instrumented run logs `dialogue_wait(talk_wait in talk_wait_input) -> transition(player_phase
idle=nil is not a known callback) -> dialogue_wait -> transition`. Each page classifies correctly;
the `transition` is the gap where the talk proc is still PRINTING and no `gProcScr_TalkWaitForInput`
exists — there is genuinely nothing to advance there, and teaching the classifier to offer
`advance_dialogue` in it would have manufactured exactly the lost press #238 warns about. The loop
that fails is the one that presses without waiting. **A `not-legal` on a `transition` usually means
the driver pressed too early, not that the classifier is missing a state.** Scenarios that walk a
multi-page screen carry a state TRAIL in their log for this reason: the first run then diagnoses
itself, instead of costing a second one.
_Decided: 2026-08-12 (#269; the ch05arena press, measured in-engine — the diagnosis it corrects
came from the issue itself)_

**Recording a cutscene as a review GIF (the standard way to show Nicolas motion).**
The harness fast-forwards non-recorded lead-up, so an assert scenario's screenshots can land
on fades — to SEE a scene play, use a `record*` scenario: it drives the game to the
scene, then captures PNG motion frames `NN-<tag>.png` into `/tmp/playtest-<scenario>/`.
Existing: `recordending` (ch01 outro, tag `end`), `recordch01trail` (`trail`),
`recordlord` (`lord`), `recordch01`/`record`/`scenes` (`op`/`bt`). To record a NEW scene,
add `scenarios.record<name>` that drives to it then captures; for an OUTRO, reuse the win
drive (cf. `recordending`'s copy of `ch01win`) and swap the fast win-wait for
`pokeNormalConfig()` (restores readable typewriter speed after the battle's
`pokeFastConfig`) + `recordCutscene`. Its old numeric `pressEvery` option is now only a
compatibility switch: positive enables A **only while the controller observes FE8's dialogue-input
wait**, and zero disables it; there is no timing cadence or fallback input. A recorder with an
unfilmed `pre` step must return `false, reason` on failure and put configuration restoration in
`afterPre`, whose setup/cleanup lifecycle is guaranteed and plain-Lua tested. Then assemble + show:
`tools/playtest/make_gif.py <scenario> <tag> --name <basename> --open` (PIL; `--fps`
controls read pace — **~6 fps for text-heavy scenes Nicolas needs to read**, 12 for quick
motion; `--scale` nearest-upscales the 240×160 frame; the default output is `docs/demo/` on the
feature branch for GitHub review, and must be pruned before merge unless a live document retains it
as evidence — [[feedback_sharing_visual_drafts]]).
_Decided: 2026-06-17 (#21 ending review); updated 2026-08-03 for the #220 controller contract and #219 recorder cleanup._

**One manifest owns "what a playtest scenario needs"; `run.sh` and the matrix runner both read it (#231).**
`tools/playtest/matrix.yaml` is the single source of the scenario → ROM configuration / `PT_HOST_CHAPTER` /
checkpoint / fps-vsync-deadline table. Before this, that table was split three ways — the ROM flag and host
chapter existed only in `harness.lua`'s per-scenario `Run:` comments, the checkpoint map and the timing
policy lived in two bash `case` blocks in `run.sh`, and nothing connected them — so the operator carried it
in their head and "a failing playtest may be the WRONG ROM" was the standing top gotcha. `run.sh` now
resolves through `matrix.py resolve` and keeps only its real job (run ONE scenario in mGBA);
`matrix.py run --suite <name>` groups a selection by ROM configuration, builds each **at most once**, runs
sequentially, and prints a `variant | scenario | verdict | time | artifacts` table with `results.json`
beside it. Decisions worth keeping:
- **Every scenario is enumerated in the manifest, defaults and all.** Absence is a `check.py` drift failure
  (`check_playtest_matrix`), not a silent canonical/host-1 default that fails later in the emulator.
- **Resolution is `defaults < class rules (in order) < the scenario's row`** — a direct port of `run.sh`'s
  `case` semantics, including that a later rule overrides only the keys it names. So `record*` still means
  60fps/vsync/300s, and `recordch02ending` still takes 600s on top of it, without restating either.
- **Ordering is about checkpoints, not just builds.** Save states are ROM-hash-stamped, so switching ROM
  configuration invalidates *all* of them, and `ckpt_ch02start` replays the whole ch00→ch01→ch02 chain to
  rebuild one. Inside a group, checkpointless scenarios run first (a cheap failure surfaces before a long
  checkpoint build) and checkpoint-sharing scenarios stay contiguous. The lint pins a checkpoint and its
  `ckpt_*` builder to the same ROM configuration — a mismatch is an invisible double cost, since the
  consumer would discard the state as hash-stale.
- **`build_campaign.py` stamps `.build-config.json`** (gitignored) with the boot flags that produced the ROM
  in the tree, because nothing in the `.gba` says how it was built. `run.sh` refuses a wrong-ROM run in 0s
  with the exact `make` line instead of letting mGBA time out; an unrecognised or missing stamp stays out of
  the way rather than blocking.
- **A failed build blocks only its own group**, and a failed scenario does not stop the matrix — one broken
  configuration must not hide the state of the others.
- **Sequential by construction.** mGBA runs share emulator/save state, and two ROM builds in one tree corrupt
  each other, so neither is parallelised; the win comes from not rebuilding and not re-earning checkpoints.
- **Suites are curated, not derived.** `gate` is deliberately tight (controller contract + ch00/ch01 spine +
  SMS budget + the current chapter); the per-chapter suites are each a single ROM build; `--all` runs every
  non-manual verdict scenario. `llm` is `manual` (external sidecar) and never auto-selected.
_Decided: 2026-08-05 (CLAUDE; #231 = #222 workstream 1. Workstreams 2–4 — state inspector, declarative
scenario manifests, static chapter lint — stay deferred and get re-scoped from the ch05 build experience.)_

**Chapter title cards are IMAGES, recomposed from vanilla glyphs.**
FE8's intro/Status title banner is a 4bpp graphic (`chap_title_data[chapTitleId]`,
`src/chapter_title.c`), not text — text ids (`chapTitleTextId`, 0x160+) only feed the
save-select/Status *strings*. `tools/gen_chapter_title.py` rebuilds the card for a
custom chapter by cutting verified glyphs out of the vanilla cards (atlas of hand-read
cut columns; unknown glyph = hard error) and recomposing at vanilla's optical center
(x≈99), so letterforms, outline, shadow, and palette indices stay pixel-identical to
the runtime palette. `inject_prologue` writes it over the host slot's PNG (a restored
build artifact; stale `.4bpp`/`.lz` removed so make re-converts) and sets both
`chapTitleTextId` and the copied goal block's `statusObjectiveTextId` (else the Status
screen keeps vanilla's "Defeat O'Neill") from the chapter YAML. Extend the glyph atlas
per new chapter title.
_Decided: 2026-06-09_

**A spawn-node story chapter needs the no-world-map title fallback, not just a recomposed card.**
Writing `chap_title_<chapTitleId>.png` is necessary but **not sufficient** for a chapter whose
host slot maps to a world-map monster-spawn node. Both the intro banner (`chapterintrofx*`) and
the Status screen (`uichapterstatus`) read the title via **`GetChapterTitleWM`** (`chapter_title.c`),
which returns a **skirmish-name card** (`0x46 + i`) when the node is in `gWMMonsterSpawnLocations`
*and* `GetNextUnclearedNode(&gGMData) != unk`. Vanilla only takes that branch on a postgame revisit;
during a story playthrough the node is the next uncleared one, so it returns `chapTitleId`. Our build
has **no world map** (see the `GetBattleMapKind` STORY fallback below), so `gGMData` node states are
never populated → the branch always fires. ch01/ch02 escaped it only because their slots' nodes aren't
spawn locations; **ch03 hosts vanilla slot 4 = `WM_NODE_ZahaWoods` (the first spawn node)**, so it
rendered "Za'ha Woods" over its own card until fixed. Fix = a campaign-agnostic engine hook
(`_patch_chapter_title_wm_fallback`, sibling to the battle-map-kind fallback) neutering the guard so
`GetChapterTitleWM` always returns the ROM `chapTitleId`. Verified in-engine (`PT_HOST_CHAPTER=4
run.sh titlecard` → `docs/demo/ch03-title-card-ingame.png`). **Separately**, the borrowed slot-6
defeat_boss goal block leaked its Status *objective* text ("Defeat Saar", vanilla Ch6's boss) because
inject_ch03 set `chapTitleTextId` but not `statusObjectiveTextId` — now set to `'Defeat '+<boss fe_name>`
("Defeat Grell"), the prologue precedent (the goal WINDOW banner is a static "Defeat boss" by goal type, so
only the Status-objective text leaked). ch03 load-tests `smoke_ch03`/`clear_ch03` added (mirror ch02;
`clear_ch03` routs via real combat, wiring-not-balance, since the grell has no `CA_BOSS`).
_Decided: 2026-07-11_

**Every decomp file an engine hook patches must be registered in `PATCHED_DECOMP_FILES`.**
`restore_vanilla_sources()` git-restores exactly that list to vanilla before re-injecting. A
**non-idempotent** hook (one whose guard hard-exits when the source isn't in vanilla form, e.g. the
pal-1 `DrawIcon` hook on `src/icon.c`) breaks the *second* build if its file is unregistered — the
first build patches it, the next build's guard rejects the already-patched form. The ch03 pink-icon
slice shipped `icon.c` (+ the repainted `item_icon_palette.agbpal` / `item_icon_red_gem.png`) unregistered;
it built once in-session but a fresh session's rebuild died on `DrawIcon not in expected vanilla form`.
Registered them retroactively. Idempotent `.replace()`-only patches (e.g. `titlescreen.c`) self-heal and
don't strictly need it, but register anyway for a clean restore each build.
_Decided: 2026-07-11_

**Seize-map legibility: the seize tile must read as a seize point and the boss sits on it — a level-design checkpoint**
Vanilla FE8 doesn't *prompt* a seize. The goal window for `GOAL_TYPE_SEIZE` prints a static
label and returns with no counter ([player_interface.c:1585-1592](../blob/main/fireemblem8u/src/player_interface.c#L1585-L1592)); the actual teaching is **spatial** — the Seize command is tile-gated to a
`TERRAIN_THRONE`/`TERRAIN_GATE` tile (`UnitActionMenu_CanSeize` → `TILE_COMMAND_SEIZE`,
`src/bmmenu.c`), that tile is a visually unmistakable throne/gate, and the **boss conventionally
stands on it**, so kill → obvious empty special tile → Seize is one square. There is no
auto-tutorial (only the player-initiated Guide, `src/bmguide.c`). The label alone does **not**
carry it. So every Seize-objective map must pass a **design-review checkpoint**, verified per map
as a line on the chapter's vertical-slice checklist and re-checked at playtest:
- **(a)** the seize tile uses distinct Seize terrain (throne/gate-style) so it reads as a special
  tile *and* the tile-info readout is not "Plain"; and
- **(b)** the boss is placed **on** the seize tile (or the tile is otherwise made unmistakable the
  moment the boss dies), so killing the boss self-evidently reveals where to go.

A dialogue nudge is at most belt-and-suspenders, never the fix. Applies to every Seize-objective
map — in the MVP that's **Ch1 (#57/#21)** and **Ch3 — The Termalaine Mine (#23)**; re-check any
future Seize map. (The Prologue is `defeat_boss`, not Seize, so it's out of scope.)
_Decided: 2026-06-19; from the brother's v0.1.0 playtest (#56 → #57)._

**Ch1 resolution (2026-06-20, #57).** The camp seize tile [21,7] is now the snowy-bern castle-gate
metatile 938 (`TERRAIN_GATE_CASTLE`) — reads unmistakably as a Seize point (criterion a), with the
chief on it (criterion b). This also **restores vanilla Ch1's gate bonus (+20 avo / +3 def)** to the
boss: the v0.1.0 tile was a deliberate bonus-free "ruins arch" deviation, now reverted to full
"Seize the gate" field parity (the deviation was the outlier, not the bonus). ⚠ The boss is
correspondingly tankier — flagged to the pipeline/difficulty track so its ch01 parity bar accounts
for the terrain. Ch3's seize tile still needs the same pass.

**Title banner theme: "glacial blue", a pure PALETTE recolor (no pixel edits).**
The banner's whole look is palette data: letters ride `gPal_08A07C58`'s green tint
pair (Status config `0x80`; `gPal_08A07AD8` is the bonus-claim green ramp), and the
Status plaque art is a SPRITE whose leaf-green ramp lives in `Pal_PlayStatusSprites`
pal 0 (OBJ rows 8–9 — found by dumping palette RAM from the `titlecard` playtest
scenario and matching on-screen pixels; it is NOT in the BG bank or the title
palettes). `build_campaign.py:inject_title_theme` reads `title_theme.letter_colors`
(six colors, light→dark) from `campaign.yaml`, maps vanilla's six letter greens 1:1,
hue-maps every other green-dominant color (plaque leaves, dim shimmer variant) into
the same family, and repoints the three `.s` incbins at generated `.bin`s (the `.s`
files are restored each build). The in-map chapter intro uses the gray tint pair
(config 8 → +0xA0) and stays vanilla white. Chosen from 4 in-game mockups
(vanilla / glacial / glacial+snow caps / frost white); snow caps rejected as less
readable. Applies to every chapter's card automatically.
_Decided: 2026-06-09 (Nicolas picked glacial blue; plaque recolor approved on the
in-game render)_

---

## Weapon & Magic Systems

**Weapon triangle: vanilla FE (Sword > Axe > Lance); damage-type names are flavor**
The triangle is FE-native and driven by weapon TYPE (`src/bmbattle.c sWeaponTriangleRules`):
Sword > Axe > Lance > Sword, +1 ATK / +15 hit. D&D damage-type names (slashing,
bludgeoning, piercing, …) are **cosmetic per-weapon labels** shown in the item info — NOT
a relabeling of the triangle. A "claw" wolf and an axe bandit are both the **axe type** and
read identically on the triangle; the difference is sprite + label only.
_Decided: 2026-05-29 (supersedes the May 2026 "reskin the triangle to Slashing/Bludgeoning/Piercing," which conflicted with FE weapon types)_

**Magic triangle: vanilla FE (Anima > Light > Dark)**
FE-native: Anima > Light > Dark > Anima, +1 ATK / +15 hit (`sWeaponTriangleRules`). Caster
spread after the 2026-05-30 promotion fix: Rootis = Anima; Marty & Meesmickle = Dark (both
Shaman, differentiated at promotion — Marty→Druid, Meesmickle→Summoner); Light is covered by
Sclorbo (Priest→Bishop, attack tomes at promotion). Note: reclassing Marty off Light (to honor
his D&D Druid identity → FE Druid) means two Dark casters rather than one-each across the triangle.
_Decided: 2026-05-29; caster spread updated 2026-05-30_

**Damage-type / elemental flavor: dropped as a game feature; deferred to battle-anim art**
There is **no** damage-type label, enum, weapon tag, or combat-preview icon — it was a vestige
of the abandoned "D&D combat layer" and added nothing once combat went pure-FE. A character's
elemental identity (Rootis = ice, Marty = spores/poison, …) is carried by **sprite/portrait art,
item names, and — eventually — custom battle animations** (where the spell visual can reference the
D&D spell for inspiration), not by any mechanic or UI tag. ~~Iconic matchups still use vanilla FE
weapon **effectiveness**, keyed to enemy class (see Combat System §).~~ *(That carve-out was
superseded 2026-07-02 — iconic matchups are out entirely; see below.)* Retires GitHub issues #7
(damage-type enum) and #10 (combat-preview icon).
_Decided: 2026-06-04 (supersedes the 13-damage-type-label plan; resistance was already dropped 2026-05-28)_

**Spell economy: finite-use tomes that deplete and are restocked with gold (decision B)**
Every spell is a finite-use item with FE tome/staff durability. Charges DEPLETE in use and
are **restocked with gold between chapters at a shop** — there is no free per-chapter refill.
Cantrips are high-count items (30–50 uses) rather than truly infinite. This puts casters in
the same gold/durability economy as martial weapons, preserving FE's core resource-management
layer (the whole party shops, scavenges, rations). Flavor the restock per character (forage /
scribe / pray); mechanically these are vanilla FE tomes/staves.
_Decided: 2026-05-29 (supersedes the May 2026 "free chapter-refill, cantrips infinite, slots not buyable")_

**Decision B needs (almost) no code — vanilla FE8 IS the spell economy (#9 delta audit).**
Decomp-grounded findings (issue #9 has the full table): tome depletion (`bmitem.c
GetItemAfterUse`, high-byte uses counter), the uses/maxUses display on BOTH the item menu and
the stat screen, and gold-restock shops (`bmshop.c` sells fresh full-uses items at
`costPerUse × uses`; vanilla Ch5's vendor already stocks Fire + Lightning tomes) are ALL stock
behavior — and the primary-cantrip counts already sit in decision B's band (Fire 40, Flux 45,
Thunder/Lightning 35, Elfire/Shine 30). **Depleted tomes break-and-rebuy, no gray-out**
(Nicolas, 2026-07-02, settling the question posted on #9): a spent tome breaks and vanishes
like an iron sword — stock FE8 behavior IS the decision-B economy; a persistent grayed slot
would deviate from vanilla for no mechanical gain.
What remains is CONTENT, landing with its first consumer per the no-dead-code rule: a
`shops:` block + `ShopList_Event_*` injection when the first shop chapter is authored
(vanilla cadence: ~Ch5), per-PC `inventory:` → loadout wiring (today `CLASS_LOADOUT` ships
class-stock items; changing it alters playtested ch01 balance, so it rides a chapter slice
with an emulator pass), and secondary-cantrip `maxUses` overrides once the per-PC spell kits
assign them (the same data_items string-patch idiom the injector already uses elsewhere).
_Decided: 2026-07-02 (CLAUDE; resolves #9's engine half as already-vanilla; gray-out settled by Nicolas same day)_

**Iconic matchups are OUT — the vanilla principle covers item DATA, not just mechanisms (#8 reverted).**
The #8 implementation (Fire/Elfire flagged `effective` vs the ice-monster classes, PR #114) used only
FE8's native effectiveness system — but Nicolas ruled (2026-07-02) that the vanilla-combat principle
extends to item *data*: stock weapons must behave exactly as a vanilla FE8 player expects, and vanilla
Fire/Elfire carry no effectiveness. The precise boundary (Nicolas, same day, sharpened once more when he
caught that even "personal bases/growths are ours" overstates it): **ALL mechanical data is vanilla —
class data verbatim, character data inherited from a class-matched vanilla DONOR, item data stock.**
`patch_character_data` copies each cast slot's growths and weapon ranks verbatim from its vanilla donor
(`GROWTH_DONOR`/`STAT_DONOR`) and lands its personal bases on the donor's own statline (an FE-strict unit
IS its donor mechanically — Rootis fights on Lute's Mage line, Wolfram on Gilliam's Knight line, renamed
and re-drawn; Baxby's YAML names Franz as his donor for when his wiring lands); enemy class clones
inherit the same way. What is genuinely ours: the donor/class *choice* per character, identity cosmetics
(names, portraits, sprites, dialogue), levels, roster composition, and placements. Nothing about a *class*
or a *stock item* changes — no custom classes, no stat/effectiveness/might edits to stock weapons. (The
YAML `fe_stats` mechanism CAN stack a deliberate divergence on the donor line; the FE-strict default is
divergence-free, and any future use of it is a per-unit balance decision, not a principle change.)
PR #114 was reverted wholesale (injector, campaign.yaml
`iconic_matchups:` block, elfire weapon model, class tags, tests, and its ADR); the 2026-05-28/06-04
"iconic matchups via effectiveness" carve-outs above are annotated superseded. Fire-vs-ice survives as
**flavor only** — item names, dialogue, and battle-anim art. Issue #8 closes as not-planned.
_Decided: 2026-07-02 (Nicolas; supersedes the 2026-05-28 iconic-matchup carve-out)_

**Comments are testimony, code is evidence — the comment-drift guard (post-mortem of the "zeroed growths" incident).**
A stale `build_campaign.py` section header claimed "zeroed personal growths / pure class rate" long after
donor-parity replaced that mechanism; an ADR then cited the comment as fact and had to be corrected twice
(PRs #120/#121) — while the *tests* pinning the real donor behavior were green the whole time. Root cause:
comments restating WHAT code does are unverified duplication (a single-source-of-truth violation), and the
existing dead-concepts lint scanned docs only, with patterns too narrow for the comment's phrasing. Settled:
- **The dead-concepts lint scans hand-written CODE comments too** (`check.py` `CODE_GLOBS`: tools py/lua/sh,
  engine C, Makefile — decomp submodule, generated files, `check.py` itself, and `test_*` fixtures exempt),
  and `check_tool_refs_exist` now also catches dangling `tools/…`/`docs/…` pointers in code comments
  (gitignored targets = declared build artifacts, not rot). Regression-pinned by
  `tools/test_check_comment_drift.py`, including the exact incident line.
- **Registry discipline:** a change that RETIRES a mechanism or term registers its key phrases in
  `DEAD_CONCEPTS` in the same commit — that registration is what makes the lint effective; the incident's
  phrases were registered but too narrowly (now broadened). This joins the Definition of Done.
- **Write rules:** a comment says WHY; the WHAT belongs to the code and its tests. An ADR asserting a
  mechanical fact must be verified against the implementing symbol (cite it), never against nearby prose.
  Semantic drift the lint can't see is caught by the same rule in review: header comments of touched
  sections are in scope for every diff review.
- A full 7-agent comment-vs-code sweep of the hand-written tree ran with this change; findings fixed in the
  same PR.
_Decided: 2026-07-02 (CLAUDE after Nicolas caught the propagated stale comment; guard + sweep in one PR)_

**The difficulty curve projects planned chapters forward from their vanilla reference (#123).**
Nicolas (2026-07-02): "Can we not project forward based on vanilla?" We can — every chapter already
declares its `parity_reference`, and the #48 extractor models the VANILLA side of the comparison, so a
`status: planned` chapter's row now prints its reference's own threat/slot + clear-load/slot as its
**(target)** — the bar the authored chapter must land within the ±25% band of — instead of a blank
"not modeled" line. The whole campaign arc is visible before content exists, and authoring starts
against a known number. Mechanics: `vanilla_projection` (informational only; planned chapters never
gate); threat counts the FULL force, clear-load excludes units the fixed early-game yardstick cannot
damage at all (a promoted wall would read `inf`) and the row says how many were excluded — ch08's
Hamill Canyon bar reads huge and partly yardstick-proof, consistent with its scripted-defeat design.
Landed with it: the **FE8 Ch13 reference curated** (11 armed-RED ch13a arrays; cutscene loads excluded;
staff-only healers drop by design) and six vanilla-only weapons modeled verbatim from `data_items.c`
(steel-lance, steel-bow, slim-lance, short-spear, zanbato, elfire — elfire returns on the VANILLA-ONLY
side of the #53 seam with plain stats; the #8 effectiveness experiment stays reverted). Drop-census
verified before adding: all LOCKED references were already fully modeled, so no locked bar moved.
_Decided: 2026-07-02 (CLAUDE; #123 from Nicolas's forward-projection ask)_

**MVP weapons = stock FE weapons (no custom Might); personal weapons are post-MVP**
PCs carry plain vanilla FE weapons whose stats (Mt/Hit/Crit/Wt/uses) come verbatim from a stock
FE8 item, named in each inventory entry's `fe_base` field — there is **no custom Might authoring**.
Conventions:
- **Physical weapons use stock names** (Iron Axe, Hand Axe, Iron Bow, Iron Lance, Javelin, Heal).
  Visual identity rides on the **sprite/portrait art** (an Iron Axe can be drawn as an anchor).
- **Tomes keep an element-right flavor NAME but are mechanically the basic stock tome** (name-only
  reskin, stock stats): Rootis "Ray of Frost" = `Fire`; Marty "Shillelagh" / Meesmickle "Eldritch
  Blast" = `Flux`; Sclorbo "Frostsong"/"Withering Impression" = `Lightning`. This avoids a stock
  tome name (e.g. "Fire") clashing with an ice/fungal caster's element.
- **Personal/signature weapons return post-MVP** as story progression, each mapped to an FE
  equivalent (e.g. Braulo's "Ole Shipwrecker" → Killer Axe, looted at the Ch 10 frozen wreck). Their flavor names are parked in
  `lore/<pc>.md` ("Signature gear").
This resolves the old "weapon Might TBD" / "uses: null TBD" placeholders.
_Decided: 2026-05-30_

---

## Economy

**Gold Pieces (GP) replace FE gold (same mechanic, D&D label)**
Armory = weapon shop. Vendor = item shop. FE8 world-map shop system preserved.
_Decided: May 2026_

**~~No arena~~ — SUPERSEDED 2026-07-29. The arena is KEPT, and it keeps its name.**
Original decision (May 2026): "FE8's arena is removed. Wolfram's Forge fills the 'spend gold to
get stronger' role." The role was identified correctly — the arena *is* spend-gold-to-get-stronger
— but the **label was wrong, and the label did the damage.** Calling the replacement a *Forge*
promises gear-smithing, which the arena mechanic cannot do (it wagers gold on single combat and
pays double; it never touches equipment). Writing ch05 surfaced this: the seed scene had Wolfram
offering to put an edge on the party's weapons, i.e. a mechanic we do not have and are not
building.

So: **FE8's arena stays, mechanically untouched, and stays called an arena in-game.** No new
mechanic, no rename for the player to learn, and vanilla's own tutorial text becomes reusable
nearly verbatim. What changes is only the fiction around it:

- **ch05's tomb is an arena that a tomb was later built into — and this is CANON, not our
  invention.** RotFM's Elven Tomb: *"An amphitheater was built for **Orem** to tell the other elves
  of his ascension and return, and when he eventually died the place was refashioned into his
  tomb."* Nicolas remembered this from the Sahnar research and was right; CLAUDE initially recorded
  it as unevidenced after grepping the repo instead of actually verifying, which is not
  verification. Our own map description had also arrived at the shape independently — "a snowy
  sunken depression ringed by crystal pillars and statues… the moon dial sits at center" is
  amphitheatre geometry. So the venue is canon and the geometry already matched it.
  **Caveat, ours not canon's:** the amphitheatre was built for ORATORY — Orem addressing his
  people — not for combat. So the arena reading is carried as **Wolfram's inference, never the
  narrator's fact**: he senses chips struck off blade edges in the floor and concludes blades met
  here, and reads it as a TRAINING floor. Both are things the wear pattern can actually tell a
  metallurgist: a battle leaves bodies and broken weapons, whereas thousands of small chips spread
  evenly through a floor means repeated, sustained, non-lethal contact. He never claims a who or a
  when. It stays his deduction rather than the narrator's assertion — he is a smith, not a
  historian, the same rule we applied to RBG (don't make him a history professor) — and that is
  what lets our arena and the canon both stand without either overwriting the other.
- **Wolfram opens it, and ch05 is the ORIGIN, not the only instance.** He finds it by metal-sense —
  the floor is full of blade-chips left by centuries of sparring — and gets it usable; afterwards
  he can set one up wherever the party camps, so arenas recur as they do in vanilla. The entry fee
  is his materials.
- **He is the right owner** even though he is a smith: his established function is reading a place
  by what he can sense (`0x9BE`), his bible has him never backing down from a fight, and he is the
  one character whose flavor explains why a four-thousand-year-old anything can be made to work
  again. Getting it running is his; what it does once running is vanilla's arena.
- The permadeath stake finally has a reason rather than being an abstract bet: the niches still
  hold the place's champions, and a unit that loses does not come back out.

Wolfram had also gone under-used — this gives him an on-screen role the campaign was missing.
_Decided: May 2026; superseded 2026-07-29 (Nicolas + CLAUDE, ch05 dialogue pass)._

**Arena presentation: winter is campaign-wide; attendants remain chapter-owned.**
The arena stays mechanically and structurally vanilla, and the winter reads through palette only —
never through replaced graphics or TSA. **Both arena views are expressed as a DELTA over the base
ROM's own words, and that is the decision.** Each view names only the entries that change; every
other word is copied from vanilla at build time.

Both views were first authored as complete 64-word replacements, and both were rejected on sight
for the same reason — so the shape of the data now makes that failure unrepresentable.

- The **welcome screen** (the coliseum exterior) changes 16 words of 64: the sky drops to a flat
  overcast, and the stall awnings take the same blue the banners fly inside. **The sandstone is
  deliberately untouched.** The rejected pass cooled the entire building; it held luminance
  faithfully (range 159 → 175) while crushing the masonry's saturation from 0.29–0.74 down to
  0.10–0.20, and the stone stopped reading as a material. Warm stone under cold weather is what
  sells the cold — a uniformly cool frame just reads as fog.
- The **in-combat coliseum** changes 11 words: the fighting floor turns snow-white and the red
  hanging banners turn blue, over vanilla's own stone, wood, gold, crowd and combatants. Its
  rejected pass was the same mistake: a cold ramp across all 64 entries of each
  `Pal_ArenaBattleBg_A/B/C` phase. Only 3 of those 64 entries animate (the crowd's gold flicker
  and one stone tone), so a delta preserves the ten-frame cycle for free where a regenerated ramp
  has to reproduce it by hand.

Both edits are provably local: an isolation mask over the real TSA showed the sky, the awnings, the
floor and the banners each own palette indices nothing else uses, so palette-only was possible with
no tile remap. `tools/rom_bg_preview.py` is what answered that, offline, in milliseconds. Before and
after: `docs/demo/ch05-arena-{welcome,combat}.png`, with the rejected pass kept as
`ch05-arena-combat-REJECTED.png`.

**The general lesson, and the reason both passes shipped past their tests:** a wash-out is a
*chroma* failure, and every check we had measured luminance. Palette work must assert what stayed
vanilla, not only what changed — the `ch05arena` proof now anchors three untouched vanilla words in
each view alongside the ones it expects to move.

The special Arena image owns the visible floor as well as the stands, and Arena mode explicitly
skips the normal `battle_terrain_tougijou1` platform path (`EfxClearScreenFx` clears BG2 when
`GetBattleAnimArenaFlag()` is true) — so that terrain asset is dead data here and stays untouched.

The default attendant remains FE8's human Arena Master; ch05 alone overrides him with Generic
Pretsel's armored skeleton, a courteous dead elven functionary still operating the tomb's ancient
arena. Every selection is data-driven at two levels (campaign palette, chapter face), additive
rather than a shared-asset overwrite, and falls back to the vanilla palette/face when a setting is
absent. Implementation scope and acceptance criteria live in issue #265.
_Decided: 2026-08-11; combat treatment settled 2026-08-12 (Nicolas; #265)._

**Gold availability follows vanilla FE8 — no per-chapter clear bonus**
FE8 grants gold only from in-map sources, never a flat "chapter cleared" stipend
(verified in the decomp: the prologue/Ch1/Ch2 event scripts give zero gold). Our gold
likewise comes only from: gold-giving villages (`SVAL(EVT_SLOT_3, n)` +
`GIVEITEMTOMAIN(leader)` → "Got n gold" popup), sellable enemy drops + gems
(RedGem/BlueGem/…), and chests. Chapter YAML records gold as concrete in-map sources,
**not** an abstract `gold_reward` field. ch01 is a net wash like vanilla Ch1 (~0 gold):
the ~200g job payment for recovering the iron is immediately spent winning over Baxby (a
**free story-recruit** — FE8 shops sell items, not units, so recruitment is a unit join,
not a purchase), so nothing is added or subtracted in-game. The "two hundred gold" in the
ending dialogue is flavor only.
_Decided: 2026-06-17_

---

## Distribution & Scope

**Distribution: private, pre-patched `.gba` shared with the 7 players (no public ROM or patch)**
Players get a pre-patched `.gba` via a private link Nicolas shares — no public hosting of the
copyrighted ROM. The README + `docs/playtesters.md` are the tester landing page (install + carry
your save), pointing at that private link. A **public `.bps` patch was evaluated and rejected**
(#59): the `fireemblem8u` decomp build on our toolchain is **non-matching** — it does not
byte-reproduce retail FE8 (recompiled code + re-compressed graphics differ across the ROM), so a
patch from a tester's retail ROM to our build is ~ROM-sized (measured **11.4 MB, 71% of the ROM**),
a pointless download that also effectively republishes the game. A small public patch would first
require a byte-matching build (a separate toolchain effort, not planned). The pure-Python BPS
encoder (`tools/make_bps.py`, tested) stays in the repo for that future, or for small deltas between
our own consecutive builds. Non-SRD content (Artificer, Circle of Spores, homebrew races) is used
freely for this private distribution.
_Decided: May 2026; reaffirmed private-only 2026-06-20 after the public-`.bps` evaluation (#59)_

**Physical cartridges are the intended final hand-off — parked until the ROM is done (#228, 2026-08-05).**
Nicolas plans to give each player a real GBA cartridge rather than only the private `.gba` link (repro shells from
InsideGadgets). This does not change the decision above — a cart is the same private distribution in a nicer wrapper,
one per player, handed over directly. Requirements and the hardware link live on **#228**; nothing is decidable until
there is a finished ROM to flash, so it stays parked rather than scoped. The one non-obvious requirement worth
recording here: the cart must have **working SRAM save hardware** (FE8 saves to SRAM), and one test cart must be
flashed and played on real hardware before doing the rest — real-hardware timing is not mGBA, and our custom battle
anims and palette work are exactly what can differ.

**Permadeath: player choice via FE8's Casual/Classic toggle**
The toggle ships as-is from vanilla FE8. In-fiction flavor for Casual retreats: "retreated to the sled" / "carried to safety by Baxby."
_Decided: May 2026_

**MVP scope: 8 chapters (Prologue–Ch 8), ending at the Eastway scripted defeat → Revel's End cliffhanger**
The MVP runs **Prologue + Ch 1–8** (see `docs/CHAPTERS.md`). The finale, **Ch 8 (The
Eastway Ambush)**, ends in a scripted defeat — "You wake up on the road to Revel's
End…" → credits. Revel's End itself is the post-MVP **Ch 9** (`docs/roadmap.md`).
Chapters beyond the DM notes require a future writing session.
_Decided: May 2026; recount to 8 on 2026-05-31 after the old Ch 4 was split into Ch 4 (White Moose) + Ch 5 (Elven Tomb)_

**Unbuilt chapter boundaries land on a reusable dev placeholder, not a vanilla map**
We develop chapter-by-chapter, so a finished chapter's `unlocks_chapter` often points at a
chapter that isn't hosted yet. Instead of `MNC2`'ing onto a leftover vanilla map, such a
boundary ends on the **dev placeholder** (`dev_placeholder_scene` in `tools/build_campaign.py`):
RBG delivers a cheese-pun "still under construction, thanks for playtesting" line over the
campfire BG, then `MNTS` returns to the title screen. It's a pure event scene (no map/units).
Punt it forward at each new boundary until the real next chapter lands.
_Decided: 2026-06-17_

**Release versioning: `v0.<chapters-playable>.<patch>`, staying `0.x` until the full MVP ships as `v1.0`**
A single-line `VERSION` file at the repo root is the source of truth. `tools/build.sh dist`
reads it and stamps `dist/ManchegoStars-v<VERSION>-YYYY-MM-DD.gba`; each shipped build is tagged
`git tag v<VERSION> && git push --tags`. The middle number tracks how many chapters are
playable + balanced, so it climbs to `v0.8.x` over the MVP and the MVP release (Prologue + Ch 1–8)
is **`v1.0.0`**. "Alpha" stays as the title-screen/README *label* for the whole `0.x` phase — the
file/tag is versioned, the in-game label is not. The first build under this scheme is **`v0.1.0`**
(Prologue + Ch 1 playable, with the #45 lord-survivability floor). The pre-versioning
`ManchegoStars-Alpha-2026-06-17.gba` is **not** retro-tagged — the scheme starts clean at `v0.1.0`.
_Decided: 2026-06-19_

**Playtest carryover: testers carry their own `.sav` across builds; a per-release starter save is the fallback**
FE8 validates a save by a **fixed** magic (`SAVEMAGIC32`/`SAVEMAGIC16`) + a checksum over the save
block (`fireemblem8u/src/bmsave-lib.c`, `ReadGlobalSaveInfo`/`ReadSaveBlockInfo`); `EraseSramDataIfInvalid`
wipes anything that fails on boot. Those magics are compile-time constants, so a **rebuild alone never
invalidates a save** — the only thing that can is the save-block *layout* shifting, which moves the old
bytes to wrong offsets and fails the checksum. Manchego Stars reskins **within FE8's fixed chapter/
character slots** and never touches the save structs, the array dims that size `struct GameSaveBlock`
(`BWL_ARRAY_NUM` roster, `WIN_ARRAY_NUM` chapters), or the magics — so the layout is stable across our
drops and an old `.sav` stays valid. Default is therefore **carry-forward**: testers keep their battery
`.sav` (in-game Save — **not** emulator save-*states*, which are ROM-version-specific and break every
build) and move it onto the new build; per-emulator steps (Pizza Boy / Delta) live in
`docs/playtesters.md`. `tools/check.py check_save_layout_stable` pins those constants and fails the
build if a future submodule bump ever shifts the layout — **that** drop, and only that, gets a
per-release starter `.sav` (the fallback) plus a save-version note. Build/dist stamps the private
`.gba`: `tools/build.sh dist` (#37).
_Decided: 2026-06-20 (revises the 2026-06-19 starter-save-first call from #59 after verifying the layout is stable)_

---

## Art & Audio

**Battle-anim ground platforms: vendored snow/ice (FE-Repo, not stone)**
FE8's battle "platform" (the ground combatants stand on) is terrain-driven (`gBanimFloorfx` →
`battle_terrain_table[]`); vanilla has **no snow platform** (the pale `siroyuka1` is a stone floor).
So we vendor from the FE-Repo `{Cynon} Battle Platforms` pack (F2E, **credit Cynon** in `CREDITS.md`),
256×32 = drop-in for the vanilla format. Per-chapter picks, book-grounded (twilight palettes for the
Everlasting Rime, never the bright "Light" daylight unless chosen):
- **Prologue (the Eastway caravan road, windswept tundra)** → `Snowdrift`, palette cooled ~20% for twilight.
- **Ch1 (the Iron Trail, rocky mountain pass)** → `Snow Uneven Ground` (**Light** — Nicolas's pick 2026-06-23; Night/Medium read too dark/blue).
- **Frozen-water beats** (Lac Dinneshere etc.) → back-pocket `Ice Flat` / `Ice FE6 Magically Frozen Lake`.
**Done (2026-06-23):** `inject_battle_platforms` vendors the three platforms into new
`battle_terrain_table` slots (115–117), remaps `BanimTerrainGroundDefault` to snow-OPEN
(plains→Snowdrift, rough→Uneven, water→Ice) for the prologue/sandbox (`battleTileSet 0`), and
adds a snow-ROUGH `BanimTerrainGround_Tileset15` (open ground→Uneven) that **Ch1 (idx 2)** is
pointed at via `chapter_settings.json`. Resolves per-tile, no force. Verified in-engine: RBG
fires in real Ch1 on the Uneven ground unforced. RBG's faked battle anim keeps its **current
scale** (the ~0.92× shrink was previewed and declined). Future snow chapters: set their
`battleTileSet` to 0 (open) or 0x15 (rough) per scenery.
_Decided: 2026-06-23_

**Faked battle anims: per-CHARACTER (`_u25`), not per-class clones (#65 M-A → M-B)**
Milestone A (RBG) gave a unit its custom anim by cloning a stat-identical **class** (`clone_into`)
and repointing the clone's `AnimConf`. That does **not scale**: FE8 has only ~3 unused class slots
(`CLASS_BLST_*_EMPTY`), and the goblin map-sprite reskins (#21) already take two. So M-B moves the
PCs to FE8's dormant **per-character** path: an engine hook (`_patch_banim_character_unique`, in
`engine_hooks.py`) swaps the four combat anim lookups in `banim-ekrbattleintro.c` from
`GetBattleAnimationId` → `GetBattleAnimationId_WithUnique`, which reads `pCharacterData->_u25` →
`gUnitSpecificBanimConfigs[]`. Per PC, `inject_battle_anims` appends the unit's `AnimConf` to that
table and sets the character's `_u25` index; **no class slot, ever** — the unit deploys as its plain
vanilla class. Scales to all 8 PCs + any **named boss** (anything with a unique character id).
- **Generic enemies stay class-bound.** A horde of goblins shares one character id (0), so `_u25`
  can't address them; their custom asset is a class-bound **map sprite** anyway. A goblin *battle*
  anim (#90) would attach as a class-level `.pBattleAnimDef` on their existing reskin clone class.
- **RBG migrated** off its clone (freed `CLASS_BLST_KILLER_EMPTY`). Pure text transforms are TDD'd
  (`test_build_campaign.CharacterUniqueBanim`); the hook is guarded by `check_engine_guards_present`.
- **Melee cadence** is studied per donor from the decomp (`ref_to_battleframe._melee_mode_body`,
  from the vanilla Pirate axe `motion.s`): lunge-in, wind-up held longest, `hit_normal` on the
  swing-through, backward dodge, no projectile. FE frames built by `tools/descale_battleframe.py`
  (flip → uniform scale → shared feet anchor → sharpen → curated family palette → 1px outline).
- Verified in-engine (TESTCH sandbox `recordanim`): **braulo** (deploys Pirate 0x42) and **RBG**
  (deploys Archer 0x19) both animate custom via `_u25`; braulo's 96-tile sprite fits VRAM.
_Decided: 2026-06-26_

**Faked anim fidelity pass: archer-palette cyan, melee lunge, record-capture (#65 M-B)**
Three faults surfaced when polishing RBG + braulo end-to-end on the `_u25` path; all fixed
campaign-agnostically.
- **RBG "cyan" was an engine bug, not the art.** `GetBanimPalette` (`banim-ekrmain.c`) loads a
  combatant's palette from `banim_data[GetBanimPalette(banim_id)]`, but for `CLASS_ARCHER/_F/
  SNIPER/_F` it returns a hardcoded canonical **bow** palette row (0x25/0x27/0x29/0x2B) *regardless
  of `banim_id`* — a vanilla palette-share that is only correct for the stock bow anim. RBG deploys
  as a real `CLASS_ARCHER` (the whole point of `_u25`: no class slot), so his custom appended banim's
  tiles got painted with the vanilla archer palette → cyan. M-A's class-clone dodged it by deploying
  as a ballista clone, not `CLASS_ARCHER`. Fix: `engine_hooks._patch_banim_palette_custom_guard`
  short-circuits `GetBanimPalette` to return `banim_id` for any **custom (appended) banim** (id ≥ the
  vanilla banim count, derived at inject time), before the vanilla switch — vanilla units byte-for-byte
  unchanged. Guarded by `check_engine_guards_present`; TDD'd. RBG also **rescaled to vanilla** (body 38).
- **Melee LUNGE lives in the frame OAM, not the script.** The Pirate's forward step is its frames'
  dx sweep (~0 → −45 → 0), but a faked anim anchors all frames to one feet point, so braulo swung on
  the spot. `build_battle_anim` now bakes a per-beat forward OAM step (`MELEE_LUNGE_DX`) for melee, and
  `_melee_mode_body` **holds** the lunged peak through the hit then eases back over a 6-tick return —
  matching the Pirate's frames 2/3/5 (forward) + 7/8 (return). DEFERRED: the white swing-arc
  weapon-trail (**#91**).
- **`recordanim` capture caught the quote, not the attack.** `captureAttack` counted entering
  `gProc_ekrBattle` as success, but a talky foe's in-battle quote (`ProcScr_BattleEventEngine`) holds
  for A and ate the budget before the swing drew. Fix: tap A while the quote box is up, screenshot
  only quote-less frames, and key the verdict on capturing real anim frames (`sawAnim`).
_Decided: 2026-06-26_

**Faked battle-animation review loop: donor visuals, game-valid previews, and archive cost (#65)**
Meesmickle exposed four rules that apply to every remaining custom battle animation.
- **Study the donor's pictures as well as its commands.** A `motion.s` command can start an engine
  effect, play audio, or merely advance actor frames. The vanilla Shaman's visible charge is not a
  reusable Flux effect: it is drawn across roughly 35 Shaman actor frames between
  `banim_code_sound_elec_charge` and `banim_code_call_spell_anim`. A three-pose replacement can copy
  that timing and sound but cannot reproduce the visual charge unless the supplied art includes a
  charge loop. Meesmickle deliberately ships with a held wind-up pose plus the vanilla charge sound
  and Flux release; that limitation was accepted after an in-engine comparison. Future magic donors
  must classify every visible beat as actor art versus engine effect before wiring begins.
- **"Least processed" still means game-valid.** The first review image comes from cleaned alpha art,
  one shared geometry transform, hard alpha, and the final shared OBJ palette (at most 15 visible
  colours). Sharpening, outline growth, and pixel touch-up are later A/B passes. Never ask for visual
  approval on a full-colour intermediate that cannot be packed into the GBA.
- **OBJ palette index 0 is transparency, even when its RGB is black.** Opaque black therefore needs
  a duplicate nonzero palette entry; mapping it to index 0 creates holes that a desktop PNG preview
  will not reveal. Palette tests pin this, and the accepted candidate still requires a real mGBA
  capture before merge.
- **Batch art decisions before the archive rebuild.** `data_banim.o` is produced by a serial linker
  that walks all 1,507 battle-animation inputs, so a full repack takes minutes. Direct palette-valid
  previews are the fast iteration loop; pay the archive rebuild only after a candidate is selected,
  then use `recordanim` as the final visual gate. Do not describe the full repack as a normal
  per-preview step or start it before the user approves the packed-pixel preview.
_Decided: 2026-07-14 (Meesmickle review + in-engine close-out, PR #163)_

**Imported enemy battle anims: transcribe a REAL community animation, bind per-CLASS (#90)**
Where PCs get a FAKED 3-pose anim on a per-character `_u25` (above), reskinned ENEMY *classes*
(kobolds, fire imps) that carry a custom map sprite but animate vanilla in the close-up get a
REAL, FE-native community animation imported *whole* and bound at the class via
`ClassData.pBattleAnimDef` (generic enemies have no unique character id, so `_u25` can't apply).
`tools/feditor_to_banim.py` parses an FEditor "For Each Frame" `.txt` + its per-frame PNGs into the
decomp banim shape, reusing `ref_to_battleframe`'s OBJ tiler; `build_campaign.inject_enemy_class_battle_anims`
clones the donor class's `AnimConf`, repoints each weapon animId, and points the reskin clone class's
`.pBattleAnimDef` at it (additive; the donor class + its AnimConf stay byte-vanilla). Driven by a
`battle_anim:` block on each `enemy_class_reskins` entry (source dir + per-weapon `{dir,txt,abbr,wtypes}`;
`wtypes` match the donor AnimConf verbatim; optional `recolor:`). Off-by-one shared with #65: AnimConf
`.index` = animId + 1.

The non-obvious findings (so the next importer doesn't re-derive them):
- **The author's OAM is NOT shipped.** The pack's `.bin` is FEditor's Java project blob; the `.dmp` is
  only the compiled SCRIPT (it *references* OAM by offset but doesn't contain it). FEBuilder regenerates
  the tile placements from the frame PNGs at insert — so re-tiling the PNGs (what we do) is the required
  step, not reinvention. And we can't use FEBuilder itself: it's a Windows GUI that byte-patches a built
  ROM, whereas we emit decomp source the build compiles.
- **FEditor bakes a palette SWATCH into the top rows of every frame PNG** (the 16 colours as a strip).
  Left in, it tiles as a floating garbage strip AND inflates the sprite bbox — which shoved the OAM origin
  ~30px sideways (to the sprite edge) and off vertically. Strip the top rows; then anchor at the FE8 sprite
  pivot (`w/2, h*5/8` of the CLEAN bbox — the engine origin, learned from vanilla `banm_ax1` OAM, feet below).
- **Battle palettes have 4 faction banks** (`BANIMPAL_RED=1` for enemies). A community anim ships ONE native
  (often ally-looking) palette across all banks, so an always-hostile reskin needs a recolor into the enemy
  bank (`enemy_red_recolor`: faction-blue clothing → red ramp). Goblins kept their native palette (Nicolas).
- **Quantize to GBA BGR555 before counting palette colours.** Two 8-bit PNG colours that round to the same
  5-bit value ARE one colour on hardware; without quantizing, a hardware-15-colour anim (Lizardzerker) spuriously
  overflowed the 15-slot budget.
- **FEditor `.txt` carries `#` comments** (a "delete # on import" header AND inline notes on mode headers /
  command lines); strip everything after `#` per line, and read the mode number by regex.

Sources (F2U/F2E, credited in each `_vendored/*/CREDITS.md`): Lizard Wildling {Lenh} → kobold-grunt;
Lizardzerker {Seliost1} → kobold-blade (sword) + kobold-brute (axe); Goblin Spearman {Battle of Wesnoth,
scripted Norikins} → both fire-imp goblins (lance-only, so ALL weapon slots point at the one spear anim —
the axe fighter swings a spear too). Testing is unified on the TESTCH sandbox: it deploys one hostile of
every `enemy_class_reskins` slot, and `recordenemy` (PT_CHAR=<name>) baits any into a counter to capture its
anim — the enemy analogue of `recordanim` for the PC cast (the ch03-specific `recordkobold` was retired).
_Decided: 2026-07-17 (kobolds + fire imps, PR #90)_

**A PC flier rides the IMPORT pipeline (N frames) bound per-CHARACTER (Pinky, #90→PC)**
The faked 3-pose path (`_u25`, above) can't carry a flier: a hover-and-swoop needs real motion, not
three static poses. So Pinky (the army's flier — **he/him**, RBG's homunculus son) is the first PC to
merge the two pipelines: his anim is a REAL N-frame animation transcribed by `feditor_to_banim` (the #90
enemy path) but bound per-CHARACTER via `_u25` (not per-class). `build_unit_battle_anim` is the seam — a
`battle_anim.import: {txt, frames_dir}` block builds via `feditor_to_banim.build_import`; anything else
(a `frames:` list) builds the faked 3-pose. Both return the identical `{sheets, pal, motion_s}` shape, so
the per-character binding (clone donor AnimConf → append banim row → `gUnitSpecificBanimConfigs` → set the
char's `_u25`) is byte-for-byte the same either way. The donor is a new `pegasus` `BANIM_DONORS` row
(`CLASS_PEGASUS_KNIGHT`, `ITYPE_LANCE`) — it only supplies the AnimConf to clone + the lance slot to
repoint; `motion`/`cadence` are unused on the import path (the `.txt` owns the cadence).

`tools/poses_to_feditor.py` is the art bridge: hi-res poses → the 248×160 FEditor frames the importer
eats. It is the INVERSE of `descale_battleframe.py` — descale PINS the feet so the body never moves
between beats (right for a foot unit's static poses); a flier wants the OPPOSITE, so each pose sits at its
own spot on a shared canvas and the per-frame shift BECOMES the on-screen motion. The arc lives in a
`poses.yaml` manifest (one uniform downscale for every frame + per-pose `dx/dy`).

The non-obvious findings (a flier is fussier than a foot unit — the next one will hit these):
- **Facing:** flip source to screen-left (whole-cast convention; `descale` flips by default) AND make the
  dive/impact `dx` NEGATIVE — a left-facing unit strikes toward a foe on its left (like the melee lunge).
  Un-flipped, he faced away and moon-walked.
- **Scale + the ear-clip:** Pinky is the roster's SMALLEST (idle ~27×31, under the mages' 32×39). His ear
  clipped FLAT in-engine at larger sizes — not an OBJ-budget or a source crop, but his long **tail dragged
  the `w/2, h*5/8` anchor DOWN toward the feet, lifting the whole sprite into the arena's top clip line**
  (tail-less units don't). Shrinking him dropped the ear-tip clear. (If a future tailed/tall unit clips,
  the real fix is a body-based anchor, not just shrinking.)
- **Arc = vanilla, not the layout sketch.** Trace the DONOR's real on-screen path (rise high → dive → strike
  at melee range ~56px), not a directional mock-up. My first arc followed the concept-art layout literally
  and the impact sailed *past* the foe.
- **Flyback ≠ the attack reversed.** Playing the dive pose backward moon-walks (the pose points the wrong
  way for the travel). The return bounces UP into the upright hover pose and glides home.
- **Linger like vanilla.** Hold the apex (the hover) and the impact/swirl long (≈16 / ≈15 ticks); a flier
  that darts through every beat reads cheap. Vanilla lingers at the peak and the strike.

**Dodge timing is synced by `wait_hp_deplete`, and the trigger is in the SCRIPT, not on screen.** The dodge
(Mode 7/8) fought us hardest; the durable rules:
- `wait_hp_deplete` (`0x85000001`, the FEditor `C01` "NOP") is NOT a NOP — it PAUSES the animation until the
  attacker's hit resolves (the beat the MISS fires). Frames placed BEFORE it fire early (at `start_dodge`);
  frames AFTER it fire AT the resolution. Vanilla hops at `start_dodge` (before the wait) → reads early for a
  big hop. Put the hop AFTER `wait_hp_deplete` to sync it to the miss.
- A flier dodge needs its OWN frame: `Pinky_006` = the jump art placed BACK (`+dx`, mirror of the forward
  launch). Reusing `apex`/`mid` teleports him up the attack arc; reusing the launch jump lunges him forward
  INTO the strike.
- To hold the dodge "back" for the whole thrust (hop at full lance-extension, land as the enemy retracts),
  HOLD the back-frame across many ticks (a grounded beat after the wait to reach full extension, then ~50
  ticks on `Pinky_006`). Sub-frame timing is tuned by the durations, verified against the Soldier's
  lance-reach in the capture — read the TRIGGER (lance fully out / retracting), don't chase the on-screen
  "MISS" text (Nicolas).

**Process cost worth remembering (see decisions Operational Gotchas + [[feedback_check_precedent_before_inventing]]):**
a `recordanim` capture interleaves MULTIPLE combat beats (attack 1 · enemy counter/dodge · attack 2 on a
double) — I burned many rebuilds analyzing the WRONG frames (Pinky's 2nd-attack swoop mislabeled as the
dodge). ALWAYS identify which beat a frame window is FIRST (attacker moves toward the foe; defender dodges
away), and render an UNCROPPED full-combat GIF for review so cropping can't mislead.

Tuned entirely on the TESTCH `recordanim` capture (class 0x48); `PT_CHAR=pinky`. No lance is drawn — a
body-slam dive, matching his lanceless map sprite.
_Decided: 2026-07-18 (Pinky, PR #190)_

**Baxby's axe-beak charge, and the SECOND palette path that repaints a custom anim (#206)**
Baxby is the other half of #206: same defect (a giant bird rendering as a man on a horse), same
class (`CLASS_CAVALIER`, ridden so the mount can BE the unit), same imported path — his attack is
travel, so `descale_battleframe`'s pinned feet are wrong for him. What was NOT the same is that his
sprite came out **correctly drawn and completely miscoloured**, and finding out why took the whole
session.

- **The cause is FE8's per-CHARACTER battle palette, and it is keyed on character × CLASS.**
  `gAnimCharaPalConfig[pid][i] == jid` sets `gBanimUniquePal[pos]`, and `UpdateBanimFrame` then
  LZ77s `character_battle_animation_palette_table[...]` **over** the palette just loaded from the
  unit's own `banim_data` row. Vanilla wants that (Seth's personal Paladin colours). We do not: our
  cast wears vanilla character SLOTS, so **Baxby rides FORDE — whose row is
  `[CLASS_CAVALIER -> 0x57]` — and Baxby deploys AS a Cavalier.** Exact match, so the engine threw
  away his axe-beak palette and painted the bird in Forde's green.
- **Lupin escaped by pure luck, which is why this survived his PR.** He rides Duessel, whose
  personal palettes are all magic classes (Shaman/Druid/Summoner), so his Cavalier deployment never
  matched. The hazard is a property of the SLOT, not of the art or the pipeline.
- **This is the SECOND such path.** `_patch_banim_palette_custom_guard` (the RBG cyan fix) already
  covers the CLASS-keyed redirect in `GetBanimPalette`. This one is CHARACTER-keyed and lives in a
  different function (`banim-ekrbattleintro.c`), so the first guard could never have caught it.
  `_patch_banim_unique_pal_custom_guard` closes it the same campaign-agnostic way: the character
  palette may apply only to a VANILLA banim id (`gBanimIdx[pos] < first_custom_banim`), on both
  sides of the screen. It names no character — the condition is "is this an appended banim", not
  "is this Forde" — and vanilla units are byte-unchanged. Guarded by `check_engine_guards_present`.
- **Every future custom-anim unit is now covered**, which matters for #25: Basil and Sahnar's slots
  would each have needed this checked by hand otherwise.

**Three pipeline rules the same unit earned:**
- **A CASCADED pose sheet splits on ink, not on gutters.** The generator may lay its poses out
  diagonally so their bounding boxes overlap on BOTH axes with no transparent column or row
  anywhere — the gutter splitter then sees the whole page as one pose. `split_pose_sheet` now falls
  through to connectivity inside each gutter cell, and two rules keep a pose whole: a blob under
  `POSE_SHARE` of the biggest is that pose's own detached art (an impact spark's outer rays, a
  motion streak) and is merged into the nearest pose by real ink distance, never dropped; and two
  pose-sized blobs that merely sit within `gap` of each other are one pose (a raised paw across an
  empty column, a shadow under the feet) — only OVERLAPPING blobs are separate poses. **The
  non-obvious half is the per-pose ink MASK**: cascaded boxes intersect, so each crop contains a
  slice of the next pose's art and cropping the box alone tows a neighbour's feathers into the
  frame. Pixels below `ALPHA_ON` belong to no pose and are left exactly as they lie, which is what
  keeps a gutter-separated sheet splitting byte-identically (pinned against the shipped sources).
- **A subject with ONE dominant hue must reserve its identity colours.** The `<=15`-colour median
  cut is area-weighted, so a tan bird spent every slot on one tan ramp (13 shades of it) and the
  saddle, the crest and the eye vanished — he read as a monochrome blob. `reserve:` was built to
  rescue a single colour the art lacked (a carrot nose, a lens to paint with); the general rule is
  broader: **reserve the colours that carry IDENTITY, not the ones that carry volume**, sampled
  from the source art rather than invented. Three reserved entries cost nothing real here — twelve
  tans still carry the body.
- **Read the arc's fixed points off already-approved anims.** A new unit's placement is not free
  invention: the foe's near edge (x≈73) and a grounded mount's ground line (y=141) were MEASURED
  off the shipped, filmed frames of two approved units, and everything else was solved from
  geometry against them. Same discipline as the recorded body-height recipe — don't re-derive a
  number the cast has already settled.

**The debugging lesson, because it is the transferable part: SYMMETRY IS A HYPOTHESIS-KILLER, and
the swap is what proved it.** Baxby's assets verified clean at every offline stage — palette bytes,
sheet PNGs, PNG→4bpp round trip, sheet-packing collisions, OAM/`attr2` ranges, mode tables, frame
commands, and a full engine-accurate reassembly of every frame from sheet+OAM (0 mismatched pixels,
for both units). All of that only ever narrowed *where* the fault was not. What actually located it
was **giving Baxby LUPIN's assets and rebuilding**: the wolf rendered corrupt — in Baxby's colours
— which proved in one run that the fault was the SLOT, not the art, and pointed straight at a
palette rather than tiles. When two units differ only in which one works, stop auditing the broken
one's data and swap them. Corollary to [[verify via data, not pixels]]: correct data proves the
asset chain, and says nothing about what the engine does with it afterwards.
_Decided: 2026-08-03 (Baxby, #206)_

**Lupin's wolf pounce: the import path grows an OUTLINE, and the detail it cannot carry gets PAINTED (#206)**
Lupin fought as a stock red Cavalier — a man on a horse — because he rides `CLASS_CAVALIER` so the wolf can
*be* the mount. He takes the **imported** path (`poses_to_feditor` → `feditor_to_banim`, Pinky's), not the
faked 3-pose one, for the same structural reason Pinky did: a quadruped's attack **is travel** (coil → leave
the ground → land on the foe), and `descale_battleframe` deliberately PINS the feet.

- **The donor repoints ALL THREE Cavalier weapon slots** (`BANIM_DONORS['cavalier']`: SWORD, LANCE and the
  unarmed/`ITYPE_ITEM` entry). Any slot left vanilla is a slot where the wolf renders as a horseman, which
  is the entire defect. His ch04 kit is Iron Sword + Iron Lance (`CLASS_LOADOUT`), so both fighting slots
  are live. Baxby (#206's other half) is the same class and reuses the row.
- **Cadence and sound are read off FE8's OWN WOLF, `banim_mdg_at1`** (`CLASS_MAUTHEDOOG`, banim 0xB0 — what
  the rest of his pack fights as), NOT off the Cavalier donor: a gallop-and-thrust is the wrong rhythm for a
  beast that leaps. That yields the wolf sound codes (C5A opens, C5B just before contact, C5D on recovery,
  C20 the impact SFX), and it re-confirms the #24 rule from vanilla's own hand — its `attack_miss` is the
  attack body with **only** the hit code and impact SFX removed; `prepare_hp_deplete` stays.
- **Three OPT-IN manifest keys on the import path**, all defaulting off so Pinky's shipped frames re-render
  byte-identical (verified): `outline: true` re-strokes the silhouette in the palette ink — the faked path
  has always done this and the import path never did, which is why Lupin first read as a grey blob next to
  the eight finished anims; `sharpen:` pre-unsharps before the area shrink (his 1.6 = Wolfram's approved
  value); `reserve:` forces a colour into the ≤15-colour palette (the seam `descale --reserve` opened for
  Rootis's carrot nose) — here a **true white** that the grey art does not contain, to paint a lens with.
- **Measured, and it corrected the obvious guess: `sharpen` does not rescue small detail.** It rescues
  detail at or above one shrink cell; anything FINER comes out slightly *worse*, because the unsharp halo
  brightens exactly the neighbours the box filter then averages back in. Pinned in
  `test_poses_to_feditor.TestSharpen`. So sub-cell features have no generated answer at all.
- **Which is why the frames are HAND-PAINTED and are themselves the deliverable.** Lupin's spectacles land
  ~4×3 px with a sub-pixel frame stroke — and they are the whole reason #206 chose generated art over the
  FE-Repo wolf anims that were already free. Nicolas paints them at final size in the browser pixel editor
  (`tools/banim_paint.py`, which hands `map_sprite_editor` one shared window of the 248×160 canvas via its
  new `--frame WxH`), exactly as his MAP sprite already did. `poses.yaml` carries `hand_painted: true` and
  `poses_to_feditor` then **refuses to re-render without `--force`**.
- **Two ways that paint can be silently destroyed, both now closed.** (1) Re-rendering the frames — the
  guard above. (2) Re-opening the editor: the sheet is scratch *derived from* the frames, so the naive
  `edit` rebuilt it every run. Both nearly fired in one session (the frames were re-rendered mid-paint to
  add the white; only the saved sheet still held the glasses, and they were carried across by colour).
  `prepare_sheet` now KEEPS an existing sheet unless its shape changed or `--reset` is passed.
- **`tools/split_pose_sheet.py`** turns one generated sheet into per-pose sources: reading order over a
  GRID (not just a strip), and keying the baked ground shadow by **morphological reconstruction** — grey fur
  lands within ~40 of that teal in RGB, so any flat colour key wide enough to catch the ellipse's own
  gradient also eats the wolf. The shadow must go: the battle screen draws its own platform, and an
  airborne pose would tow a floating blob.
- **Trap worth naming: a unit's SLOT is `PORTRAIT_MAP`, its STATS are `STAT_DONOR`, and they differ.** Lupin
  is Duessel (0x1D) wearing Kyle's growths (0x11). Taking the donor for the slot put `PT_CHAR=lupin` on a
  unit that is not on the map; the injector's own output is what caught it.

**Two process rules the same session earned, because both cost a rebuild:**
- **The approved render recipe is RECORDED — read it before sizing a new anim.** Every shipped unit
  carries its own in its YAML (`--body 38..44`, `--thin-outline`, `--sharpen 0..2.0`: RBG 38, Rootis 40,
  Braulo/Wolfram/Sclorbo 44) and the rationale is in this file. Deriving a body height from first
  principles instead re-opens a question Nicolas already closed — *"we've done so many animations, you
  should have checked I approved the in game render quality and dimensions."*
- **Show new sprite art at 1:1 AND zoomed, beside already-approved siblings.** A lone
  nearest-neighbour blow-up of a *correctly sized* FE8 sprite reads as "horribly pixelized"; the
  comparison row is what makes the scale judgeable at all. (Stills → Preview, motion → Safari.)
- **The division of labour that worked, and is the default for this kind of detail:** Nicolas paints,
  the pipeline is built around him. Two generated attempts at the spectacles both lost to five minutes
  of his hand-painting, and his simplification of the plumbing — *"you could pass me the images in the
  state they are ready to go in game, no re-render needed"* — is why the frames, not a diff, are the
  committed artifact.
_Decided: 2026-08-02 (Lupin, #206)_

**Every ATTACKING banim mode must ARM the HP depletion — the unit it starves is the OPPONENT (#24)**
C01 `banim_code_wait_hp_deplete` (`0x85000001`) "freezes if no HP depletion is occurring/has occurred" —
the decomp states the hazard on the macro itself (`include/banim_code.inc`). The non-obvious half is **who
hangs**: every vanilla dodge/stand mode waits *bare* on C01 and relies on the **attacker's** script having
armed a depletion, with `prepare_hp_deplete` (C04, melee) or `call_spell_anim` (C05, projectile/spell).
So an attacking mode must arm one **even when nothing connects, and even when it never waits itself** —
a miss is exactly the case an author skips. Every vanilla donor we clone obeys this: `banim_pirm_ax1` and
`banim_armm_sp1` keep C04 in `attack_miss` and drop only `hit_normal`; `banim_arcm_ar1` / `banim_sham_mg1`
make `attack_miss` their *attack* body, arrow and all.

Four of our generated/imported paths broke it, and all four soft-lock — the whole proc tree wedges with
`GAMECTRL` at `lock=1`, `ekrBattleInRoundIdle` spinning on `(gBanimDoneFlag[0] + gBanimDoneFlag[1]) == 2`:
- **Faked MELEE `attack_miss`** emitted the wait with no C04. *This is what froze ch04 turn 4:* Braulo's
  counter missed Lupin, both anims stuck on C01, `gBanimDoneFlag = [0, 0]`.
- **Faked MELEE `attack_range`/`_critical`** ran the DEFENDER "stand" body (waits, arms nothing) on the
  assumption "a melee unit can't strike at range". False for us — `CLASS_PIRATE` ships a **Hand Axe** and
  `CLASS_ARMOR_KNIGHT`/`PEGASUS` a **Javelin**. Now the vanilla Armor Knight's thrown shape (C05).
- **Faked RANGED/MAGIC `attack_miss`** held a still frame and armed nothing; now the attack body, per the
  archer/shaman donors.
- **IMPORTED `Pinky.txt` mode 12** — the *community source* omitted C04. Her miss ended early while the
  Mauthe Doog's dodge blocked forever: `gBanimDoneFlag = [0, 1]`, the asymmetric signature of "the
  attacker finished, the defender is still waiting for a depletion nobody armed".

Guarded, not just fixed: `feditor_to_banim.validate_hp_deplete_arming` runs at `emit_motion_s` (the one
choke point every import crosses) and **fails the build** on any mode that opens with C03 and arms nothing,
so a community script's hole can never again surface as one unlucky combat mid-playtest. Auditing all 11
vendored/imported scripts found Pinky's the only offender. `TestHpDepleteArming` pins both halves of the
contract on both generators (attackers arm; dodge/stand deliberately do NOT).

**Method note (this is how a banim freeze gets diagnosed).** Read it as DATA, never pixels
([[feedback_verify_via_data_not_pixels]]): the proc pool carries its own diagnosis — `proc_lockCnt`
(the wait semaphore), `proc_scrCur` (which PROC_* command it sits on) and `proc_name` — and
`gBanimDoneFlag` + `gAnims[n].currentRoundType` name the stuck **side** and **round** outright. The
harness's `freezeReport` (smoke driver, fires on any SOFTLOCK verdict) prints all of it, so one run turns
"the game froze" into "the right side is playing MISS_CLOSE and never signals done". The inherited lead
said "Revenant vs Wolfram / check `battleTileSet 0x15`"; the actual pair was Lupin vs Braulo and the
tileset was irrelevant — [[feedback_inherited_leads_are_hypotheses]] again.
_Decided: 2026-07-31 (ch04 turn-4 soft-lock, #24)_

**Character-scoped spell colours are campaign data; the tint rides a dedicated overlay global (#165, #168)**
Marty's `battle_anim.spell_palette_tint` declares a character + weapon-type match in YAML, so one
row covers every Dark tome he can wield without naming Marty in engine code or changing the tome's
mechanics. The generated table (`gBanimSpellPaletteTints`) is immutable ROM data. At spell dispatch,
`StartSpellAnimation` records the matching tint id in `gMSSpellTint` — a dedicated
`EWRAM_OVERLAY(banim) u8` declared beside `gEfxSpellAnimExists` in `banim-ekrbattle.c` (the enum is
honest: `BANIM_SPELL_TINT_NONE = 0`, `BANIM_SPELL_TINT_GREEN = 1`). Palette registration reads
`gMSSpellTint` and recolours saturated BG/OBJ colours while retaining neutral greys; teardown
(`EkrEfxStatusClear`) clears it alongside the vanilla `gEfxSpellAnimExists` reset.

The durable lesson: a caster-scoped tint gets its **own** overlay-banim global declared beside
`gEfxSpellAnimExists` — do **not** overload the spell-lifecycle flag. A global's storage is decided
by the compilation unit it lives in, not the abstract `EWRAM_*` macro: declared inside an unrelated
TU the linker placed it in ROM (read-only, silently ignored writes), but declared beside the proven
`EWRAM_OVERLAY(banim)` siblings in `banim-ekrbattle.c` it links writable. Overloading
`gEfxSpellAnimExists` (the earlier shipped form) worked only because every vanilla reader compared
`== 0`/`false`, an unenforced invariant that any future `= true`/`== 1` would silently break; the
dedicated global removes that landmine. The TESTCH `recordanim` capture is the visual gate; Marty
renders green Flux in mGBA while the table stays character- and `ITYPE_DARK`-scoped.
_Decided: 2026-07-15 (#165 shipped the feature; #168 replaced the `gEfxSpellAnimExists` overload with
the dedicated `gMSSpellTint` global, gated on the in-engine Marty capture)_

**A caster clones from its OWN class; the spell tint is the flavour lever, not the donor (Rootis, #65)**
Rootis (frost snowman-mage) is the first faked caster whose element is flavour-only. Two decisions
generalise from him:
- **`clone_from` = the unit's own vanilla class, chosen by weapon type — not "any magic donor".** The
  private AnimConf repoints the entry matching the donor's `wtype`, so the custom anim only binds to
  the weapon the unit actually wields. Rootis is a **Mage** (ITYPE_ANIMA), so his donor is the new
  `mage` (`CLASS_MAGE`, `0x0100 | ITYPE_ANIMA`) — **not** the shaman (ITYPE_DARK) that Marty/Meesmickle
  use. A shaman donor would repoint the DARK slot and leave his Anima casts on the vanilla mage anim.
  The `magic` motion cadence (settle → charge-hold → release) is donor-agnostic and shared. General
  rule for the next caster: pick the `BANIM_DONORS` entry whose `wtype` matches the tome the unit wields.
- **Ice/frost element = the `spell_palette_tint`, layered on the vanilla spell — do NOT swap the spell
  proc.** FE8 ships a real ice anima spell (Fimbulvetr), but wiring a per-character spell-anim *swap*
  would be new machinery and its full-screen blizzard is oversized for a basic tome. Instead Rootis
  keeps the vanilla red Fire projectile (his tome is mechanically Fire) and a `color: blue` tint
  recolours it icy-blue in-engine — the same `BanimSpellPaletteCopy` seam as Marty's green, extended
  with `BANIM_SPELL_TINT_BLUE` + `BanimSpellTintBlue` (blue channel dominant, green kept mid so it reads
  as bright cyan-white frost, not navy). The enum is honest and the recolour dispatches on the tint id;
  vanilla and unconfigured casters stay byte-vanilla. **Review order matters:** the regular (untinted)
  spell was captured in-engine and approved *before* the tint was added — never bundle the colour change
  with the first anim review (you can't tell a wrong pose from a wrong colour if both land at once).
- **Descale palette: reserve small accent colours in the ADAPTIVE path too.** Rootis is near-monochrome
  blue/white, so his orange carrot nose (a handful of px) lost the median-cut frequency contest and
  quantised out. `descale_battleframe.descale` now threads `--reserve` through to `_shared_palette`
  (it previously only reached the locked-layout path), so `--reserve 240,110,55` forces the carrot into
  the ≤15-colour palette. Row-1 look (thin outline, no sharpen, `--body 40`) chosen over the heavier
  full-outline default. Recipe recorded in `rootis.yaml`.
_Decided: 2026-07-17 (Rootis frost-mage anim, `feat/rootis-battle-anim`; in-engine `recordanim` gate)_

**Per-caster charge flash: pulse the actor's OWN palette, armed from an EXISTING banim command (#183)**
Each custom caster's sprite pulses its signature colour on the wind-up beat (Rootis blue, Marty green,
Meesmickle purple) — a "gathering power" tell the faked 3-pose magic cadence otherwise lacks. The
reusable pattern (`_patch_banim_charge_flash`, hook + `battle_charge_flashes` data):
- **Adding a caster = one YAML block** (`charge_flash: {color}` on `battle_anim`); the weapon type is
  auto-derived from the caster's donor, so nothing else is needed. **A new colour = one line** in
  `build_campaign.CHARGE_FLASH_RGB` (name → RGB); `charge_flash_target` packs it to BGR555. The table
  (`gMSChargeFlashes`, `{character, weapon_type, BGR555}`) rides `data_banimconfunk.c`; the engine names
  no character. Same character+weapon scoping as the spell tint (`gMSSpellTint`).
- **The reusable engine kernel (copy this for any per-caster actor-visual effect):** (1) *arm from an
  existing banim script command* — hook the interpreter switch in `banim-main.c` on a command ALREADY
  in the faked body, so the donor-matched animation script is never edited. We use **start-attack
  (`case 0x07`)** — it fires one settle beat before the wind-up arm-raise, and a raised-cosine LUT that
  ramps from 0 makes the pulse *bloom* exactly on the arm-raise (the elec-charge marker, `case 0x28`,
  fires ~18 ticks too late). (2) *Identify the attacker* via `GetAnimPosition(anim)` →
  `gpEkrBattleUnitLeft/Right` + `GetItemType(bu->weaponBefore)` (the spell-tint pattern). (3) *Pulse the
  actor OBJ palette* `PAL_OBJ(0x7)` (L) / `PAL_OBJ(0x9)` (R): a `PROC_REPEAT` proc snapshots the 16
  colours, blends toward the target by the LUT each frame, and restores + `Proc_Break`s at the end
  (bleeding into the cast). *Timing is engine-only* — start point and throb count/speed are the
  `case`-choice + `_CHARGE_FLASH_FRAMES`/`_THROBS` constants; never lengthen the animation to fit it.
- **A flash is a WASH toward a bright colour, not a hue-transform.** A palette-transform (like the
  spell tint's `BanimSpellTintBlue`) does nothing on a caster already near the target hue — Rootis's
  white-blue snowman only flipped its nose. Blend toward a saturated target so it reads on any base.
- **Two build-system gotchas that cost a rebuild each (so the next hook author skips them):**
  (a) **A new hook-target file MUST be added to `build_campaign.PATCHED_DECOMP_FILES`** — else
  `restore_vanilla_sources` doesn't reset it, the injection's `if not already patched` guard skips
  re-injection, and a *stale* prior injection persists silently (old symbols, or a no-op edit).
  (b) **No `.bss` statics in banim TUs** — the decomp linker discards `.bss` there (`` `.bss'
  referenced in ... discarded section``). Put mutable per-effect state in the **proc struct** (pool-
  allocated), not a `static` uninitialised global. The `const` LUT is fine (`.rodata`).
_Decided: 2026-07-18 (Marty/Rootis/Meesmickle charge flash, `feat/183-charge-flash`; TDD + in-engine
`recordanim` gate; validated the arm-raise sync + multi-throb feel with Nicolas)_

**A HEALER (staff caster) rides ONE anim for heal + defense + post-promo attack — the last PC anim (Sclorbo, #191)**
Sclorbo is the army's first healer (Priest → Bishop) and the first non-attacker to animate. Four things
generalise (the reusable "healer donor" — Basil, #25, uses it too):
- **Donor = BISHOP, cloned, with BOTH the STAFF and LIGHT slots repointed to one custom animId.** The
  vanilla Bishop `AnimConf` is the only healer table carrying both a staff slot (defense + heal) AND a
  light slot (post-promotion attack); Priest's has no attack slot. `banim_clone_conf` clones on the first
  wtype then `banim_repoint_conf`s the rest — the existing #90 precedent, so `BANIM_DONORS` wtype may now
  be a **list**. Because `_u25` binds the same clone to BOTH promote states, one anim covers everything;
  `call_spell_anim` resolves heal-efx vs light-efx from the *equipped item* at cast time (staff → Heal,
  Light tome → Light), so the single staff-raise **cast pose serves both**.
- **Load-bearing decomp fact: restorative staves render the ARENA.** Heal/Mend/Physic/… play a real
  battle-anim cast (`StartSpellAnimHeal`, efx `0x26`); only Warp/Rescue/Torch/Unlock force the map
  (`banim-ekrbattleintro.c:1413`, efx `-2`). So the healer's cast pose is on-screen **every heal in the
  MVP**, not just after promotion — all three poses (idle / dodge / cast) matter pre-promo. Isolation is
  airtight: `GetBattleAnimationId_WithUnique` (`banim-ekrbattleintro.c:1492`) substitutes the private
  clone only when `_u25 != 0`, so no other Bishop/Sage/multi-weapon unit is touched.
- **Per-caster charge-flash WAVEFORM (extends #183).** The #183 kernel was a shared 3-throb pulse; a
  `u8 waveform` field on `gMSChargeFlashes` now selects it (`0` = pulse, `1` = build) against a second
  const LUT (`sMSChargeFlashBuild`, one slow raised-cosine swell). Sclorbo = cyan **build** on both his
  staff and light rows; Marty/Rootis/Meesmickle default to `0` and stay byte-identical. "Slow building
  glow, not pulses" was Nicolas's call, matched to his flame pigment.
- **Match a caster's own pigment with a DEDICATED tint, not a near neighbour.** The glow blends toward a
  flat BGR555 target so it hit the flame cyan `RGB(31,219,219)/0x6F63` immediately. The **spell tint** is a
  hue-*transform*, though: reusing Rootis's `BanimSpellTintBlue` (blue-channel-dominant) read as a deeper
  blue, so `BANIM_SPELL_TINT_CYAN` / `BanimSpellTintCyan` was added — red suppressed, green AND blue both
  pinned to the highlight — applied to staff + light. Accepted coverage gap (Nicolas): the heal's white
  "recovery poof" loads via a direct `SpellFx_RegisterBgPal` that bypasses the `OBJPAL_BANIM_SPELL` tint
  hook, so it stays white; the orb/sparkles/glow go cyan and carry the identity.
- **Descale facing: a multi-pose source sheet may not face one way.** Sclorbo's source idle + cast faced
  opposite his charge/dodge; `descale_battleframe`'s flip is uniform, so two of three landed backwards —
  visible only in-engine. Fix = mirror the odd source crops *before* descaling. Rule for the next
  multi-pose art: verify all poses share a facing, or pre-mirror the outliers.
- **The `recordanim` harness now captures non-attackers:** a staff-only unit dispatches to
  `captureHealerAnim` (drive Staff→Heal a wounded ally for the cast; sit adjacent to a foe + end turn for
  the dodge) instead of bailing. The custom-vs-vanilla side-by-side was produced by toggling the
  `battle_anim` block off + rebuilding (the ROM `_u25` is `const`, so it can't be poked at runtime).
_Decided: 2026-07-19 (Sclorbo healer anim, `feat/191-sclorbo-battle-anim`; TDD + in-engine `recordanim`
gate; glow/tint/facing GIF-reviewed and approved by Nicolas — "looks perfect")_

**Event backgrounds (`BACG`): vendored winter CGs, injected as NEW `gConvoBackgroundData` slots**
Cutscene backdrops are `gConvoBackgroundData[]` (eventscr2.c) `{tiles, map, palette}` triples, 240×160,
4bpp with up to **8 sixteen-colour sub-palettes** (one per 8×8 tile = 128 colours). We vendor winter
backdrops from the FE-Repo (the Icewind Dale set is rich)
and add each as an **additive new slot** past `BG_BLANK` (0x35) — never reskin a vanilla entry.
- **Pipeline:** `tools/bg_to_fe8.py` (any image → 240×160, GBA-5bit, tile-banked mode-P PNG; greedy
  ≤8-bank pack, falling back to an 8-bank refit for dithered CGs — see the entry below) → `inject_backgrounds` copies it to `graphics/bg/`, appends the enum id (backgrounds.h),
  extern decls (bg.h), table row (eventscr2.c) and incbin symbols (data_bg.s); make's generic
  gbagfx/FETSATOOL rules build the bins. The 4 patched files are in `PATCHED_DECOMP_FILES`.
- **Gotcha — index 0 is transparent.** GBA BG colour index 0 shows the backdrop (FE8 sets it black),
  so a converter that uses local index 0 for a real colour renders **black holes** wherever that colour
  appears (caught in-engine on the ch02 Targos BG: the bright sky/snow speckled black). `bg_to_fe8.py`
  reserves index 0 (colours start at local 1; ≤15 usable per bank). A flat-quant *preview* won't show
  this — only the real GBA render does, so **verify event BGs in-engine**, not by reconstructing the PNG.
- **Slots: appended PAST the sentinel, so there is no ceiling.** Campaign BGs start at **0x38**, after
  vanilla's last enum `BG_RANDOM` (0x37) — relocating BG_RANDOM to free 0x36 would have capped us at one
  extra BG. The two pre-0x38 indices get placeholder table rows so the table stays index==enum contiguous
  (`eventscr.c` short-circuits on `bgIndex == BG_RANDOM` before any lookup, so it never reads its row).
  First use: ch02 Targos ending (Zeldacrafter snow-town).
_Decided: 2026-06-25_

**A dithered CG needs the banks FITTED to it, not tiles that already agree (`bg_to_fe8.py`)**
The original converter only ever *packed*: it quantised globally, then put two tiles in one bank when
one tile's colour SET nested inside the other's. That reproduces a clean low-colour source **exactly**
(the Zeldacrafter Targos snow-town: 15 colours, 1 bank), and it cannot convert a photo-derived CG at
all. A dithered source checkerboards two shades pixel-by-pixel, so a single 8×8 tile of dusk sky holds
16–18 colours that no other tile matches: the Fenriel winter CGs needed 265–377 banks, and squeezing
`--colors` down until they packed left **15 colours in 1 bank — 7 of FE8's 8 thrown away**.
- So `bank_cluster` fits 8 palettes of 15 to the picture: seed by tile mean colour (farthest-point,
  deterministic), then alternate *requantise each bank from its assigned tiles' pixels* / *reassign each
  tile to the bank that reproduces it with least error*. Both steps only lower error, so it converges.
- **8 is the engine's budget for a plain `BACG`, and only that:** `eventscr.c` loads one with
  `ApplyPalettes(pal, 8, 8)` + a `0x8000` TSA base, i.e. banks 0–7 → hardware palettes 8–15.
  **The FADE/TRANSITION path applies only 6** — `sub_800EC50` / `sub_800ED50`
  (`ConvoBackgroundFadeProc`) call `ApplyPalettes(pal, 0, 6)` / `(pal, 8, 6)`. An 8-bank BG shown
  through those loses banks 6–7 and renders garbage in whatever they cover, and nothing in the
  build catches it. So a BG destined for a transition/fade-in subcode is converted
  **`--banks 6`**; `--banks` is validated 1..8 for that reason (`bg_to_fe8.py` refuses more, since
  no path can load them). Ch01's ending is a plain `BACG` + `FADU`, hence 8. **Bremen is banked at
  8: ch07 must either show it with a plain `BACG` or reconvert it at 6.**
- **The packing path is kept and tried first**, so every already-shipped BG still converts
  byte-identically (asserted on `bg_TargosWinter.png`); clustering is lossy and only the fallback.
- **A bank no tile chose is compacted away**, so the reported bank count is the count actually
  used — an emptied bank is re-seeded from the whole image and rarely wins a tile back, which
  would otherwise reproduce the wasted-budget failure the function exists to fix while printing 8.
- **Bank palettes are snapped back to the 5-bit grid.** MEDIANCUT returns cluster AVERAGES, which
  land off-grid even when every input pixel was on it; gbagfx then truncates the low 3 bits, so an
  unrounded palette ships colours the tool never chose its indices for.
- Squared distances are computed in **int32**. In int16 a channel delta squares to 65025, wraps
  negative, and `argmin` then picks the **worst** bank — which renders as bright blotches in dark
  regions. Caught by looking at the output, exactly as the index-0 gotcha above was.
First use: Bryn Shander's ch01 ending + Bremen's reserved ch07 slot, both 8 banks / 120 colours,
verified in-engine on the `recordending` cutscene.
_Decided: 2026-08-09_

**Maps: hand-drawn in Tiled, NOT AI-generated**
Use community Frostmaiden maps (from `docs/frostmaiden-resources.md`) as layout references. Use FEUniverse map pool for tileset/format guidance. Agents help with unit placement and events, never spatial layout.
_Decided: May 2026_

**Audio: vanilla FE8 soundtrack for MVP**
Investigate Frostmaiden Spotify album + community soundtracks as stretch-goal custom tracks post-ship.
_Decided: May 2026_

**Art: CUSTOM indexed-palette pixel art for every PC/recruit sprite part — portrait, map sprite, AND battle animation.**
Not recolored vanilla, and not reused vanilla class animations. Combat is pure vanilla FE8, so the art is the
single biggest lever for making the game feel like the actual D&D campaign — worth doing custom and taking the time.
Each piece is produced **faithfully from the character's clean Gemini/Nano-Banana bust reference** via tooling
(`tools/ref_to_bust.py` → `tools/portrait_tool.py`): the generative bust is the **pre-approved source art** and is
converted — not hand-pixeled (Nicolas is not a pixel artist) — into the final 16-color indexed asset. Nicolas supplies
one clean frameless **"<Name> Face Clean"** bust per character; Claude converts it. Specs: 16-color GBA palette, 8×8 tiles.
Per-unit design briefs (must-keep tells, expression, palette plan) live in each unit's YAML `art:` block
(`campaigns/.../{pcs,npcs}/*.yaml`).
**Sequencing — three waves:** (1) all 10 cast portraits, then (2) all map sprites (16×16 chibis), then (3) battle animations.
_Decided: May 2026; full-custom direction + Gemini-ref-to-asset pipeline proven 2026-06-01 (Braulo, then Prof. R.B. Geenius)._

**Guest (campaign-NPC) portraits: vendor by default, custom when the character recurs; injection is optional-by-file.**
The custom-art-everywhere rule above covers the **CAST**; chapter guests (e.g. the ch00 cold-open's
Hlin/Scramsax/Sephek) decide per character: a vendored FE-Repo mug (originals + credits in
`campaigns/.../portraits/vendor/`, regenerated by `portraits/guest_vendor_busts.py`) or the custom ref pipeline when
the character matters beyond their chapter (Sephek recurs → custom bust from Nicolas's "Sephak Bust Dagger" ref; the
official book art was tried first and rejected as a style mismatch with the GBA mugs). `inject_portraits` dresses a
guest's vanilla slot only when `portraits/<unit>.png` exists (`GUEST_PORTRAIT_MAP`), so wiring lands ahead of art and
a missing bust keeps the vanilla face. Guest art records live in the chapter YAML's unit `art:` blocks (guests have
no `{pcs,npcs}` YAML).
_Decided: 2026-06-09 (ch00 guest looks picked by Nicolas: Sephek custom w/ ice dagger; Hlin = Pirate Lady v3
silver-haired recolor; Scramsax = community Hero mug as-is)._
_ch05 Ravisin (frost-druid boss): vendored **Aversa {Garytop} [F2E]** from the FE-Repo,
not generated art. Nicolas approved a strict seven-entry palette substitution on 2026-08-10:
silver hair -> auburn/chestnut and warm skin -> frost-pale; the original brown face/chest
markings, black feather mantle, crown, expressions, alpha and every pixel position stay
unchanged. portraits/ravisin.py byte-regenerates the 96x80 indexed bust from the vendored
sheet. She dresses collision-free Riev, and her raw on-map pid 0xb8 explicitly points both
CharacterData.portraitId to Riev's 0x48 and nameTextId to Riev's retitled MSG_246. Her authored
ch05 YAML `personal` line is also copied onto raw 0xb8's CharacterData bases; unlike regular
cast members, a raw pid never passes through `patch_character_data`, so leaving that step out
silently produced a naked Druid even though the balance report saw the intended boss stats.
Dressing graphics without the portrait binding leaves the boss faceless; leaving the name on
generic MSG_255 makes the correctly rendered boss read "Monster"; leaving the personal bases
at zero discards the authored boss line. A named raw-pid guest therefore needs all three pieces
bound explicitly: portrait, name, and personal CharacterData stats._
_Decided: 2026-08-10 (Nicolas + Codex; visual palette approval, then deterministic implementation);
raw-pid personal-stat binding corrected 2026-08-11._
_ch01 Hruna (Foaming Mugs quest-giver): vendored **Generic Villager {Cynon} [F2E]**, periwinkle→olive-wool
recolor; rides the generic `Villager_Woman` face slot (FID 0x60). Deliberately departs from book canon (the
bundled, scarf-wrapped, eyes-only frost-dwarf) in favour of an open, sympathetic "please help us" mug — Nicolas's
call for a one-chapter NPC (a scarf-wrapped Assassin recolor was prototyped and rejected as "too suspicious").
Decided: 2026-06-16._

**Map sprites: per-CHARACTER sprite + palette override; custom cast share a bespoke palette in their own OBJ bank.**
FE8 draws overworld sprites by **class** (`GetUnitSMSId → pClassData->SMSId`), so a class swap would hit every unit of
that class — including enemies — and couldn't distinguish two cast on the same class (Marty & Meesmickle are both Shaman).
Instead each cast member gets a **custom SMS slot** (ids 107+; classes top out at 106) and a **per-character override** in
`GetUnitSMSId` (generic table; campaign data injected by `build_campaign.inject_map_sprites`, parallel to portraits).
Stock classes and vanilla enemies are untouched. **Colour: the custom cast share one bespoke 16-colour palette in their
own OBJ palette bank** — map sprites can't carry their own palette; a sprite picks one of the resident faction banks by
allegiance (`GetUnitSpritePalette → bank` per `UNIT_FACTION`). We add a **per-character override there** (sibling to the
`GetUnitSMSId` hook) that points custom cast at the **campaign-unused purple bank (`0xB` / `OBJPAL_UNITSPRITE_PURPLE`)**,
into which `ApplyUnitSpritePalettes` loads a bespoke cast palette (`campaigns/.../map_sprites/cast_palette.png`). Bank
`0xB` is free in single-player play: its only consumers are the **Light Rune** (an unused DUMMY item, never placed in any
chapter) and the **link-arena 4th-player colour** (multiplayer only — our ROM is single-player). This leaves the shared
player palette (bank `0xC`, blue) untouched, so the **not-yet-custom cast always render correctly during rollout** (no
mis-tint, no palette-sequencing gotcha) while the custom cast get the full 16 colours free of the "team-blue"
constraint. Greying still works: `GetUnitDisplayedSpritePalette` short-circuits acted units to the grey bank `0xF`
*before* reaching our hook. The palette is designed once to union-cover the cast's signature hues (reds/blacks/whites/
greys + Rootis ice-blue, Sclorbo cyan, Pinky pink, RBG gold/purple/green), and the same `cast_palette.png` is the
recolour target for every base sprite.

**Guests reuse the STANDARD player palette — no cast bank (2026-06-09).** A custom sprite only needs the bespoke
purple-bank palette if its colours fall outside FE8's stock palettes. Cold-open guests (`PROLOGUE_GUEST_SPRITES`,
e.g. Hlin's female-Fighter sheet from the FE-Repo) are vendored already drawn to `unit_icon_pal_player.agbpal` (the
blue player bank `0xC`), so they get the SMS + MU overrides like the cast but are **kept out of `gMapPaletteOverride`**
— they render through the resident faction bank, no extra palette plumbing. This matters because bank `0xB` is the only
free OBJ bank (the cast already claim it for their shared palette); a second distinct sprite palette has nowhere to go,
so a standard-palette sheet is the only way to add a custom sprite alongside the cast. To check a vendored sheet:
compare its 16-colour palette to `unit_icon_pal_player.agbpal` — exact match ⇒ guest path (no override); custom colours
⇒ it must be re-indexed to `cast_palette.png` and join the cast bank.

**Custom map sprites RECLAIM dead vanilla wait rows instead of appending — conservatively (#227, 2026-08-05).**
We were not out of SMS ids; we were wasting them. Vanilla assigns map sprites per **CLASS** (107 rows serve 127
classes — every Cavalier draws row 4); we assign per **CHARACTER**, which is the design and is what makes the cast look
custom. But `CUSTOM_SMS_BASE = 107` only ever *appended*, so 19 custom rows stacked on top of dozens of rows belonging
to classes this campaign can never field. `claim_sms_id` now hands out **reclaimed rows first**, appending only as
fallback; `_write_wait_row` places a row at exactly the index its id names (replacing in place when reclaimed) and
`sys.exit`s otherwise — which also closes the id/row **desync** hazard, since ids are now claimed only by the pass
about to write the row. All 19 custom sprites currently fit in reclaimed rows, leaving the whole 107–127 range spare.

**The reclaim policy is deliberately conservative, and that is Nicolas's call, not an optimisation.** Reachability is
seeded with **FE8's entire player promotion tree** — every class a player unit could ever hold or become — not merely
the classes our YAML names today, *because the roster is not final*: "we have characters we haven't recruited yet, so
your list is by definition incomplete." Reserving the whole tree costs ~30 reclaimable rows and removes the dependency
on the cast being finished. Three further reservations exist because no computation can infer them:
- **the four literal ids** `0x5B`/`0x5C`/`0x5D` (ballista traps, by `trap->extra`) and `0x66` (trap type `0xD`).
  `RenderUnitSprites` draws these map OBJECTS by literal id with **no class involved**, so a class-only scan calls them
  free and reusing one puts a cast member on any map with a ballista. This is the #218 failure shape exactly.
- **declared art donors** (`art.map_sprite.base: 'Cyclops'`) — named by sheet, not by `CLASS_` enum, so the token scan
  misses them, and naming a vanilla class as a donor is fair warning we might field it.
- **`CLASS_BARD` / `CLASS_DANCER` / the three `MANAKETE` classes** — the cast already includes a bard in D&D terms, and
  Frostmaiden has a white dragon (Arveiaturace). `CLASS_MANAKETE` is also the only class pointing at the shared `Blank`
  fallback row.

**Two traps found building this, both worth remembering.** (1) **`ClassData.promotion` is only ONE branch.** FE8's real
branching table is `gPromoJidLut[][2]` (`src/classchg-data.c`): Myrmidon → Assassin *or* Swordmaster, Priest → Bishop
*or* Sage, Thief → Assassin *or* Rogue. Following `.promotion` alone under-counted by five classes (Bishop, Ranger,
Rogue, Summoner, Wyvern Knight F) — rows a PC can promote into. **The player picks either branch; reachability must
close over both.** (2) **`donor_sms_geometry` was reading the MUTABLE working tree.** A donor's geometry is a fact about
*vanilla*, so once we reuse a donor's row the lookup finds our macro — or loses the symbol outright. It reads
`HEAD` now, like every other decomp read.

**Custom SMS ids are capped at 127 by the engine, and the cap is enforced at the append (#225, 2026-08-05).**
FE8 resolves every map sprite's geometry through a masked index — `#define GetInfo(id) (unit_icon_wait_table[(id) &
((1<<7)-1)])` in `src/bmudisp.c`. An id ≥ 128 therefore reads a **vanilla** row: id 128 draws Ephraim Lord's sheet at
Ephraim Lord's size class. It does not crash, does not warn, and fails no test — the unit simply renders as somebody
else. Critically **the mask is not the array bound**: `gUnitSpriteSlots` is `u8[0xD0]` and `UNITSPRITE_MAX` is `0xD0`,
so ids 128–207 remain valid *slot-cache* indices; nothing downstream can notice. Vanilla ships 107 rows and
`CUSTOM_SMS_BASE = 107`, so the whole custom budget is **ids 107–127 — 21 sprites**, and every pass spends from it
(cast idle, guests, pre-recruit variants, scripted neutrals, the chwinga reskin, `enemy_class_reskins`).
So: **`_append_wait_rows` is the only way to add a wait row**, it `sys.exit`s naming the id and the unit that would
overflow, and it prints the remaining headroom (loudly under `SMS_ID_LOW_WATER`). The ceiling itself is *read from the
decomp* (`_sms_id_mask_bits` parses the `GetInfo` define out of HEAD) rather than hardcoded, so a decomp bump moves the
guard with it instead of leaving a stale `127` behind. Going past 127 for real is a much larger job — widen or re-point
the mask and audit every `UseUnitSprite` / `StartUiSMS` / `StartWorldMapSMS` caller — and is deliberately not done here.
Live budget at the time of writing: **126 used, 2 left**; ch05's Basil + Sahnar are exactly those two.

**Loading the cast bank is only half the job — several vanilla screens BLANK it again (#218, 2026-08-05).**
Bank `0xB` is free in vanilla precisely because nothing renders from it, and vanilla exploits that: a screen calls
`ApplyUnitSpritePalettes()` and then immediately zeroes bank `0xB` as scratch cleanup. Harmless in vanilla; for us a
zeroed 16-colour bank draws every index as colour 0, so the cast come out as **correctly shaped BLACK SILHOUETTES** —
right sheet, right chr, right position, no colour. That is the signature to recognise: *shape correct, colour absent
⇒ the bank was blanked, not the sprite mis-injected.* Every such site is listed in `build_campaign.PURPLE_BANK_BLANKERS`
and deleted by `_drop_purple_bank_fills`, which `sys.exit`s if a site stops matching verbatim (a decomp bump must fail
loudly, not silently blacken a roster). **The list is per-site and not a grep because the idiom is spelled differently
on each screen**: `CpuFastFill(0, PAL_OBJ(0x0B), 0x20)` in `prep_unitselect.c` (Pick Units) but the raw
`CpuFastFill(0, gPaletteBuffer + 0x1B0, PLTT_SIZE_4BPP)` in `unitlistscreen.c` (the Character list) — `0x1B0` is
`0x100 + 0x0B*0x10`, the same bank by arithmetic. Missing that second spelling is exactly why the 2026-07 Pick Units
fix did not generalise, and the Character screen — which players open constantly — stayed broken until #218.
**Any new screen that draws cast map sprites goes in that table, not in a new hook.** Finding the second site by hand
is not a strategy, so `check.py check_purple_bank_blankers_known` now greps the decomp **at HEAD** (the working tree has
the fills patched out, so linting it would pass vacuously) for any literal bank-`0x0B` palette fill and fails the build
unless that file is already in `PURPLE_BANK_BLANKERS`. A third screen — new, or arriving with a decomp bump — is now
caught by CI instead of by a player noticing black silhouettes.

**Enemy map sprites: clone the class into an unused slot, don't reskin the shared class (#21, 2026-06-16).**
The cast's per-CHARACTER override is the wrong tool for ENEMIES: generic grunts share a pid (`0x80`), so there is no
character to key on, and the cast bank forces the cast palette (enemies want their faction palette). Reskinning the
shared `CLASS_SOLDIER`/`CLASS_FIGHTER` SMS would turn **every** soldier/fighter in **every** chapter into the themed
sprite (and would have to be undone the moment a chapter wants human soldiers as enemies). So we **clone** the base
class into an otherwise-unused class slot — vanilla's ballista-empty classes (`CLASS_BLST_REGULAR_EMPTY` 0x6A,
`CLASS_BLST_LONG_EMPTY` 0x6B), which exist in `gClassData`/the move table but are unreferenced by this campaign — copying
the **entire** class body (so stats, weapon ranks, terrain tables, and `pBattleAnimDef` ride along ⇒ combat is identical
and never crashes) and changing only `.number`, `.SMSId` (→ a new wait row) and the move-table row at `slot-1` (→ the
themed walk sheet, reusing the base class's motion script). Enemies of the cloned class render the themed sprite under
the standard **enemy faction palette**, so the donor sheet is remapped onto the **base class's standard SMS palette index
layout** (`map_sprite_tool.remap_sms_palette`), NOT the cast palette. Reversible (delete the YAML block) and reusable
(any future themed enemy). The mechanism is campaign-agnostic C; the goblin/chapter framing lives in campaign YAML
(`campaign.yaml enemy_class_reskins: [{id, base, slot, sprite, frame?}]`), injected by
`build_campaign.inject_enemy_class_reskins` and opted into per chapter by `inject_ch01`'s grunt-class swap. Ch1's grunts
use it (the **Fire Imp** {Alexsplode, FE-Repo} for both soldier and fighter grunts — the "Foaming Mugs goblins"; the
chief stays the vanilla Knight). Verified non-destructive: the `CLASS_SOLDIER`/`CLASS_FIGHTER` entries are byte-unchanged
(SMSId 0x3f/0x31).

**Green NPC chwinga: per-CHARACTER override of a derived cast sprite, tinted by the green faction palette (#38, 2026-06-24).**
The ch02 chwinga are the green-faction mirror of the enemy reskin. Unlike enemy grunts they ride **distinct NPC slots**
(`DARA`/`KLIMT`/`MANSEL`) — so the cast's per-CHARACTER `gMapSpriteOverride` IS the right tool (their class,
`CLASS_PEGASUS_KNIGHT`, is a balance chassis shared with player flier Pinky, so a class-level reskin would turn Pinky into
a chwinga). They are kept OUT of `gMapPaletteOverride`, so `GetUnitSpritePalette` falls through to the faction switch and
the **green NPC bank** tints them automatically (no bespoke palette). Sprite source: Sclorbo's map sprite — he is a
chwinga (Nicolas, 2026-06-24: "use his sprite, apply the green ally palette"; identical green triplets, blue glow kept).
His **cast-palette** sheet is remapped onto his SMS base's (`Civilian_F1`) standard role layout at build time
(`map_sprite_tool.remap_sms_palette`), so the single source of truth stays `sclorbo.png` (no committed derived asset);
one shared SMS slot + glide MU sheet serve all three identical NPC slots. Injected by
`build_campaign._inject_ch02_chwinga_sprites` (inside `inject_map_sprites`, which owns the override tables).

**A cast member that CHANGES faction colour (green NPC → blue player on recruit) is faction-tinted, not
cast-palette-pinned (`FACTION_TINTED_CAST`, #23, 2026-07-10).** Trex is a Colm-style talk recruit: he stands GREEN,
then a `CUSA` flips his faction to blue on Talk. He shipped with a custom cast map sprite, so his charId landed in
`gMapPaletteOverride` — and `GetUnitSpritePalette` honours that override **unconditionally**, pinning his one bespoke
(blue player) cast palette regardless of faction. Result: a green-faction Trex still drew blue (Nicolas caught it in
the recruit GIF). A charId-keyed cast override simply cannot follow a faction change. Fix = generalise the chwinga /
enemy-reskin logic to a cast member: the `FACTION_TINTED_CAST` set (`build_campaign`) routes his sheet through
`remap_sms_palette` onto his donor class's (`Thief`) standard SMS **role layout** and keeps his charId **OUT of**
`gMapPaletteOverride`, so `GetUnitSpritePalette` falls through to the faction switch. His custom winged-kobold **shape**
still ships — the SMS + MU overrides (`gMapSpriteOverride`) are retained — only the palette is now side-driven: green
as an NPC, then the standard blue player bank once recruited. Idle + committed walk are both remapped with the donor
WAIT palette so they share role indices (no derived asset: temp dir; single source stays `map_sprites/trex.png`).
Trade-off accepted (Nicolas, 2026-07-10: "reads more blue than green, but I'll take it"): faction tinting gives the
class's standard green/blue ramps, not a hand-tuned green — the bespoke cast palette and faction tinting are mutually
exclusive for one sheet (a role-layout sheet is what lets *either* faction palette land correctly). If a role reads
wrong, `remap_sms_palette`'s `overrides={src_idx: std_idx}` knob corrects it. This is the pattern for **any** future
recruit with a custom sprite (talk or green-start): add its uid to `FACTION_TINTED_CAST`.

**When the RECRUITED look is the bespoke sheet, faction-tinting is the wrong tool — give the unit a
PRE-RECRUIT variant instead (`pre_recruit_roles`, #24, 2026-07-30).** Lupin is the same shape of problem as
Trex (placed RED as the wolf pack's leader, `CUSA`'d over by Marty's parley) but the opposite requirement:
Nicolas's call is **red while hostile, the finalized grey once recruited** — "only his colours change upon
recruitment". `FACTION_TINTED_CAST` can't do that; it trades the bespoke palette away, so he'd join as
standard **blue**. Leaving him in `gMapPaletteOverride` can't either: that override is unconditional, so a
hostile Lupin renders grey — and FE reads grey as *already acted*. A single sheet can't serve both, because
the cast palette's index roles are not the standard palette's (his grey ramp lands on cast 1/2/3/4/11, which
under the enemy palette gives dark maroon, pink-grey, near-white and **bright green** at 11), and there is no
spare cast-palette entry to redefine — all 16 are in use across the cast sheets. So the unit gets **two
sheets**: the committed cast one, and a standard-palette one **derived at build time** by remapping cast
indices to SMS roles (`art.map_sprite.pre_recruit_roles`, `_remap_indices`) — no committed derived asset, so
every pixel edit to the cast sheet flows into the pre-recruit look automatically. `gPreRecruitVariant`
(charId → SMS id + MU sheet) is consulted by all three per-character override hooks **only while
`UNIT_FACTION != FACTION_BLUE`**: sprite and walk return the variant, and the palette hook *skips* the purple
bank so `GetUnitSpritePalette` falls through to the faction switch. Empty table == exactly vanilla. Note an
explicit ROLE map is required, not `remap_sms_palette`'s nearest-RGB: a grey ramp nearest-matched against a
coloured palette collapses onto the constant entries and the unit barely changes colour by side. One
limitation, accepted: an index serving two roles can't be split (Lupin's cast 2 is body shadow *and* the
glasses pupil, so the pupil goes dark-red with the shading — invisible at 32×32). This is the pattern for a
recruit whose joined look is its bespoke art; `FACTION_TINTED_CAST` remains right when the joined look may be
the side's standard blue.
_Decided: 2026-07-30_

**A luminance recolour can collide two ROLES on one index — check the roles, not just the ramp (#24).**
Lupin's map sprite lost its inner-ear wedges, and it read as a drawing mistake in the hand-drawn glasses pass.
It wasn't: the shape was intact in all 18 frames. The recolour that moved the source onto the cast grey ramp
landed the inner-ear pink (`b2629c`, luma 128) and the light body fur (`719ac1`, luma 146) on the **same**
cast index 3, so the ears were painted body-colour. Caught by Nicolas comparing against the pack sprite, whose
map sent that pink to a pale index. Recovered by re-deriving the 10 px/frame from the source colour and
setting them to cast 11. **After any luminance-driven remap, list the source colours that share a target index
and check none of them are different features** — a ramp can look perfectly graded and still have eaten a
detail.
_Recorded: 2026-07-30_

**Pick a sprite already drawn in the standard SMS palette.** The first attempt (BoW "Goblin Spearman") had its own
9-colour palette, so nearest-mapping it to the standard layout collapsed it to a dark, unreadable blob (and a remap-target
bug — matching to the *player* palette while the unit displays under the *enemy* palette — turned its red pixels green by
accident). The Fire Imp is authored in the **standard SMS palette**: its body sits on the faction-colour ramp (indices
7–10), so under the enemy palette it becomes a **fully-shaded red imp** (glowing eyes, pointy ears) with zero remap
guesswork — the remap is an identity pass. Lesson: prefer FE-Repo sprites already in the standard palette; the index roles
must line up with the faction ramp or the faction recolour produces mud. **Green enemies are not practical** — green is the
NPC/ally palette (the engine applies it by allegiance, and FE's colour language reads green as friendly), and a custom
green-in-a-spare-bank would need an OBJ bank, but the one free bank (`0xB`) is already the cast's; red is the correct,
free "enemy" signal.

**`frame` override for off-size sprites.** A reskin sprite need not match the base class's SMS size: the Fire Imp is a
tall **16×32** sprite on a 16×16-combat soldier/fighter. The optional `frame: 16x32` in the reskin YAML sets the wait-row
size flag; the engine draws the taller idle correctly (same mechanism mounted 16×32 classes use) while combat stays the
base class's. Absent `frame`, the base class's own SMS geometry is used.
_Decided: 2026-06-16; shipped for the ch01 grunts (#21) as the Fire Imp, `make` green + `ch01win` PASS + in-game screenshot._

**Item reflavor = global name + icon swap per item id; the cast's per-unit `name:` fields are documentation only (#21, 2026-06-16).**
FE8 stores **one** name message and **one** 16×16 icon per item id (`gItemData[].nameTextId` / `.iconId`), so a reflavored
consumable necessarily reads the same for the whole party — the per-unit inventory `name:` fields in the cast YAML (which
historically varied: "Healing Potion" / "Blood Vial" / "Goodberry") cannot differ in-engine and are kept purely as
documentation/flavor. The reflavored Vulnerary is unified party-wide as **"Goodberry"** (Marty's druidic ration; Meesmickle's
blood-draught flavor survives only as a YAML comment). Two campaign-agnostic, data-driven mechanisms inject this:
`build_campaign.inject_item_names` (campaign.yaml `item_names: {ITEM_ENUM: name}` → rewrites the item's `nameTextId` message,
terminator-parity padded) and `build_campaign.inject_item_icons` (campaign.yaml `item_icons: {ITEM_ENUM: asset}` → overwrites
the item's tracked `.png` source under `graphics/item_icon/`, which gbagfx compiles to the `.4bpp`). Both resolve the item's
id/iconId from `data_items.c` and the icon's source file from `data_item_icon.s`'s incbin order — never hardcoded. The icon is
authored from FE8's **shared item-icon palette** (one fixed 16-colour bank for all item icons) via `tools/item_icon_tool.py`
(`blueberry_grid`, design "L2": blue body, dark five-point calyx button, green branch rooted in the button's centre, single
left leaf — iterated with Nicolas). Authoring in the shared palette means the icon
needs no recolour; a vendored fruit icon would have had to be re-indexed to that palette anyway, so generated-via-tooling was
simpler than sourcing from the FE-Repo.
_Decided: 2026-06-16; shipped for the Goodberry (#21), `make` green + `verify_text` 3404/0 + `ch01win` PASS + in-ROM icon render._

**Palette off-by-one (2026-06-06, found on the first in-game cast test).** The cast bank loads one slot high: a
rainbow-palette test (each index a distinct hue) showed every sprite index `k` rendering cast colour `k-1`
(snowman-white→yellow, meesmickle's red cape→cyan, etc.). `gMapSpriteOverride`/`gCastMapPalette` data and the 4bpp
indices were all verified byte-correct, so the shift is in the engine's OBJ-bank load, not the injection.
**Fix:** `build_campaign._read_cast_palette` pre-rotates the 16-colour block up by one (`out[1:] + out[:1]`) so each
colour lands on its intended index. Don't "correct" `gCastMapPalette` to match `cast_palette.png` order — it is
intentionally rotated.

**Map sprites are IDLE-ONLY for now (movement auto-derive deferred).** The finished cast idle (`<id>.png`) is folded
onto the real cast id and injected; the stale per-class `<id>_mu.png` walk sheets were removed, so a *moving* unit
currently falls back to its stock class sprite (standing shows the custom sprite). The 32×32 action/side sheets explored
in the editor are exploratory and not injected. **Geometry base is a token:** for non-decomp FE-Repo donors the YAML
`art.map_sprite.base` is set to any decomp class of matching frame size (16×16 or 32×32) purely to read the SMS size;
the real art donor is named in a comment + `CREDITS.md`.

**Two sheets per character, grouped as one deliverable** (battle anims #39 are a separate track):
- **Idle** = the small **wait** sheet (16×16 frame strip), `unit_icon_wait_table[SMSId]`, swapped via the `GetUnitSMSId`
  per-character override above. *(Proven in mGBA, Braulo placeholder.)*
- **Hover/selected + walking** = the larger per-class **MU** sheet (`gMuInfoTable` = `unit_icon_move_table[classId-1]`;
  a **32×480 strip = 15 frames of 32×32**). Override the same way: `MuProc` carries `->unit`, so patch `GetMuImg` to
  return a per-character custom sheet (reusing the class's motion script, so only the graphics change) before falling
  back to the class sheet. Both in-chapter MU draws route through `GetMuImg`, so one hook covers hover + walk.
The MU sheet is the bigger art lift (a 15-frame walk cycle), but it stays in the map-sprite group, not battle anims.
One gotcha: `StartMu`/`StartMuExt` decompress the sheet *before* setting `proc->unit`, so the override reloads the
graphics after `proc->unit` is set (else it falls back to the class sheet).
_Decided 2026-06-04; both override paths (idle + MU) built and proven in mGBA with Braulo placeholders (idle = Dancer, hover/walk = Mogall). Colour mechanism revised 2026-06-05 to the dedicated-bank approach (bank 0xB) after confirming the bank is free in single-player play — supersedes the earlier "modify the shared player palette" plan, which carried a rollout mis-tint gotcha._

**Map-sprite ART process: reskin a vanilla FE base, NOT downscale generated art.**
The portrait pipeline (Gemini bust → downscale → indexed) does **not** transfer to map sprites: at 16×16 / 32×32,
downscaling detailed or AI-generated art yields irregular colours + mush (researched; AI tools make high-res
"pixel-*styled*" images that always need pixel-by-pixel cleanup). The FE-community standard is to **edit an existing
map-sprite base** (FEU Map Sprite Repository, Klokinator FE-Repo) — it bakes in the chibi proportions and, crucially,
the **already-animated walk cycle** (you re-skin the motion instead of animating 15 frames from scratch). At 16px a
heavily-reskinned base *is* effectively custom. **Process (decided 2026-06-04):** (1) pick the vanilla base of the
class closest to each character's build; (2) **programmatic recolour first** — remap the base to the shared cast
palette + light edits, render in mGBA, Nicolas judges; (3) **fallback = hand-edit in LibreSprite** (free Aseprite fork)
where the recolour isn't good enough (Nicolas will do the pixel pass). Idle (3f) first, then the walk MU
(15f). I handle palette-enforce / sheet-assembly / injection; the creative pixel judgement is the split point.
_Decided 2026-06-04 (Nicolas: recolour-first, hands-on fallback, free tool). See FEU "Map Sprite Insertion Mania" thread._

**Map-sprite EDITING surface + geometry/animation read from the decomp (2026-06-05).**
The creative pixel pass is done in a local, offline, stdlib-only browser editor — `tools/map_sprite_editor.py
--campaign <name>` — an Aseprite-style canvas (tool column, palette locked to `cast_palette.png`, checkerboard
transparency, zoom, onion skin, donor reference / A-B overlay, motion map) with a live idle preview, a frame
timeline, a per-character picker, **Save** (writes exact cast indices back to `<id>.png`) and **Reset** (reverts to
the clean-recolour snapshot in `map_sprites/.base/`, gitignored). It supersedes the LibreSprite fallback. Companion
batch ops are in `tools/map_sprite_tool.py`: `recolour` (donor → cast palette, nearest-colour + `d:c` overrides),
`preview`, `grid`, `palette`, `setpx`. Two things are READ FROM THE DECOMP, never guessed (a 16×96 sheet is ambiguous,
6×16×16 vs 3×16×32): **(a) frame size** per donor from `UNIT_ICON_SIZE_*` in `src/unit_icon_wait_data.c` via
`map_sprite_tool.donor_sms_geometry(base)` — Cyclops/Berserker/Mauthedoog/Manakete_Myrrh are **16×32**, the rest 16×16;
used by both the editor and `inject_map_sprites`; **(b) idle timing** from `bmudisp.c` (`GetGameClock() % 72` →
frames 0,1,2 held 32/4/32/4 ticks @60fps), which also drives the editor's "follow motion" (an edit rides the bob
across frames, offsets measured per-row from each character's own donor). _Guessing the size from PNG dims cost real
time once; the rule is read it from the decomp._

**Enemy/non-cast sprites: vanilla FE8 where the look fits; community (FEUniverse) or custom only where a creature has no vanilla analogue** (Grells, Messie, ice trolls).
The full-custom rule above is for the player cast + named recruits, where identity matters most.
_Decided: May 2026_

**Cutscene art: portrait-based dialogue only for MVP**
CG-style illustrations (Braulo shackle break, Messie rising, Revel's End fade) are post-ship stretch goals.
_Decided: May 2026_

**Maps: one community winter tileset + Tiled layouts, inserted decomp-native**
~8 of the 9 MVP maps are snow/ice, so we use **one shared winter tileset** — **Snowy Bern / Snowy Peaks** (FEU t/7204: snow ground, frozen buildings, walls, ice/water, forest, temple, mountains) — and author each chapter's layout in **Tiled**. Insertion is **decomp-native**: a GBAFE map is 4 pieces wired through `gChapterDataAssetTable` (`data/data_8B363C.s`) and incbinned in `data/const_data_chapter_maps.s` — tile graphics (`.4bpp.lz`), palette (`.gbapal`, raw), tile config/terrain (`.bin.lz` = 8192 B TSA + 1024 B terrain), layout (`graphics/map/layout/*.bin.lz`). A chapter's `src/data/chapter_settings.json` holds **u8 indices** into the asset table per piece (jsonproc regenerates `chapter_settings.h` each build). Layout `.bin` = `width, height` then `w·h` LE u16, each = **metatile_index × 4**; source path is `.mar`+`.json` → `scripts/mar_to_map.py` → `.bin` → Makefile `%.lz`.

**The tileset did NOT need grit / the Map Hacking Suite:** the community package ships pieces byte-identical to the decomp's (palette = `.gbapal`, mapchip_config = tile-config `.bin`, obj = GBA-LZ `.4bpp`), so it's a straight drop-in. `tools/build_campaign.py:inject_winter_tileset()` copies the pieces in, appends asset-table entries, and points a chapter at them — proven in-engine on the test chapter. **No raw-ROM hex / FEBuilder.** We did NOT palette-swap a temperate tileset and did NOT find ready-made snow town maps (community has tilesets, not finished maps). Tileset asset = #41 (done); pipeline = #40 (register/wire done; Tiled `.tmx`→`.bin` authoring is the open half); both feed per-chapter maps #20–#28. Workflow doc: `campaigns/.../maps/README.md`. Credit authors in `CREDITS.md`.
_Decided: 2026-06-07_

**Winter retiles preserve the vanilla artists' forest sequences as a strict generation AND import invariant.**
When a Snowy Bern retile has a vanilla layout reference, that layout is the structural source of truth
for every `TERRAIN_FOREST` (`0x0c`) cell. Each source metatile must resolve through the approved
per-metatile mapping in `campaigns/rime-of-the-frostmaiden/maps/reskin-learned.json`; repeated vanilla
trees repeat their winter counterpart, and horizontal/vertical/cluster components keep their authored
sequence roles. The editor generator must stop with the unmapped source metatile(s) and coordinates
rather than collapse them to its generic forest fallback. Its exported JSON stamps the vanilla layout,
and `import_map_layout.py` rechecks the same mapping so a browser edit cannot silently flatten the
sequence or substitute a non-forest target. The target metatile must itself remain terrain `0x0c`.
Custom canvases with no vanilla source are exempt. A deliberate forest-composition departure is a new
map-design decision, not a quiet override of this guard. The mapping data is authoritative; tools and
tests consume it rather than carrying a second mapping table. Issue #193.
_Decided: 2026-07-20 with Nicolas (approved after Ch00–Ch02 before/after review)._

**Tilesets stay coherent; Snowy Bern may borrow only Super Fields' complete Snag family.**
Snowy Bern remains the shared winter art direction, including Ch4's forest retile. Keep the whole N426
Snow / Fields + Customs set vendored intact as a coherent winter alternative; do not retain the complete
green-grass Super Fields default as an alternate, and do not casually mix either set's tiles into Snowy
Bern. The one approved exception is the functional Snag family Snowy Bern lacks: copy Super Fields
metatiles 8 and 35 pixel-exact into Snowy Bern's matching empty slots, preserve terrain `0x33` and the
readable brown silhouette, and use otherwise-unused Snowy Bern graphic capacity so existing art is
untouched. The approved transfer renders through Snowy Bern's native **palette bank 4**; assigning the
donor pixels to bank 5 was the washed/gold/green failure and is explicitly rejected. Match vanilla Snag
placement (Ch4 E9 uses metatile 35), just as the winter forest variants match vanilla's original sequences.
_Decided: 2026-07-20 with Nicolas (#24)._

**Adopting non-FE sprite sources (Basil/Oddish)**
Basil's whole kit (portrait, SMS+MU map sprites, battle-anim frames) adopts **Oddish** sprite art
instead of generating or hand-drawing — Nicolas's call: prefer existing pixel art over generation
when a source fits. What the next adoption should know:
- **PMD SpriteCollab** (`github.com/PMDCollab/SpriteCollab`, `sprite/<dex>`) is the goldmine: official
  CHUNSOFT *Explorers of Sky* sheets with **8 directions × full action set** (Idle/Walk/Charge/Shoot/
  Attack/Hurt…). Mainline games only ever drew front/back — PMD is the only source of the **side-facing**
  poses FE8 battle anims need, and its **W row natively faces left** (FE8 player side; Marty faces left).
  Its `*-Shadow.png` sheets mark the ground: **align multi-sheet frames by shadow centroid**, not content
  bbox (poses lean; the ground line doesn't). Per-file `credits.txt` → `CREDITS.md`.
- **Pixel-art rescale without generation:** ffmpeg ships `hqx`/`xbr`/`super2xsai` filters (no new
  tooling). Integer hqx only — for 1.5x do `hqx=3` then an exact half downscale. Alpha survives via a
  **black matte for the colors + a separate hqx pass on the binary mask** (black fringe hides in the
  dark outline; magenta mattes leave a visible ring). After ANY resize, threshold alpha at 128 and
  **re-lock every pixel to the source's quantized palette** — LANCZOS + any-alpha indexing leaves ghost
  pixels that read as a halo/outline (caught by Nicolas on the first portrait pass).
- **Portrait dead zone:** the 96×80 bust's top 48 rows only draw x=16..80 (`gSprite_Face96x96` OAM
  layout), so wide-topped busts are capped by that 64px channel — descale/position to fit and prove it
  with `portrait_tool.py preview` (draw the red-hatch dead-zone overlay when showing candidates).
  `generate` also requires a **full 16-entry PNG palette** — Pillow writes truncated palettes; pad to 16.
- **Native-size adoption beats rescaling on map sprites:** PMD Oddish frames (14-20px) drop straight
  into the **16×32 tall SMS class** — but the wait-table donor must match the sheet's **frame count**:
  most 16×32 rows are 2-frame; the 3-frame 16×32 donors are the monster rows (we use **Cyclops**,
  the `donor_sms_geometry` docstring example). `map_sprite_swapper.py` grew `--idle-frame-h 32` for
  16×32 idle sheets (Trex's 16×16 default untouched).
- **Pending for the ch05 recruit wiring (#25):** Basil's `battle_anim:` block stays undeclared until
  `BANIM_DONORS` grows a **`priest` staff/heal donor** (he heals — shaman/dark is the wrong clone) —
  frames + recipe live in `battle_anims/basil/` + `npcs/basil.yaml` meanwhile.
_Decided: 2026-07-16_

**Adopting sprites, part 2 — Lupin (Lycanroc) + Sahnar (spectral skeleton)**
Two more recruits' art adopted from community/non-FE sprites (#181). What generalizes:
- **Sources beyond PMD/Pokémon:** a plain DeviantArt overworld sheet works too. Lupin's map sprite is
  the **Midday Lycanroc** form from *"Rockruff & Lycanroc Overworlds"* by **princess-phoenix** (CC-BY 3.0
  — cleaner licensing than most FE-Repo assets). Get the signed image URL via the DeviantArt **oEmbed**
  endpoint (`backend.deviantart.com/oembed?url=…`) — the raw wixmp URL 401s without the token.
- **Hand-drawing identity details onto an adopted sprite:** Lupin's glasses were drawn per-frame,
  **anchored to the source's eye pixel** (detected by color) so they track the walk-cycle head-bob
  automatically — the eye moves, the glasses follow. Iterate the design on the un-recolored base first
  (bold vs thin, opaque vs clear lens, height, pupil), THEN recolor. Draw glasses only on face-visible
  directions (down + both sides); the back/up run has no face.
- **`base:` for a quadruped map sprite = geometry token only.** Lupin uses `base: Gwyllgi` (FE8's own
  dire-wolf: `{3 frames, UNIT_ICON_SIZE_32x32}` wait-table row) — apt AND correct geometry; the class
  stays Cavalier. Committed both the 32×96 wait + 32×480 MU (real directional walk from the sheet;
  right = engine H-flip of the side run), unlike Baxby's synth-MU.
- **The community has NO mummy — only skeletal undead.** Swept FE-Repo (40k-file listing) + FEUniverse +
  broader web (FFTA/Castlevania exist but can't port a battle **anim** into FE's frame format). Undead
  busts are green-zombie recolors or bare skeletons; undead sword **anims** are all skeletal monsters
  (Bonewalker/Wight/Specter). So a literal "mummy" = custom/generation for everything; a **skeletal
  revenant** is the cohesive, fully-sourced alternative. Sahnar took the skeleton route (Nicolas's call).
- **Trio cohesion via one artist + palette-lock:** Sahnar's map sprite + battle anim are a matched
  **Alexsplode** pair (the "Specter"); the portrait is **Glaceo**'s "Skeleton (Assassin)" bust. No single
  artist made all three, so the **portrait is the free variable** — recolor its robe to the map sprite's
  *exact* cast cloak shade (don't grab a mismatched premade undead bust). Match the map's dominant tone,
  not its lightest: the cloak read dark because idx1 dominated, so the portrait's hood bulk must be dark
  too (a big-canvas hood over-reads any light highlight). **Do NOT recolor the battle anim** — keep its
  native palette (Nicolas: it's polished/consistent; the skull + spectral glow are the throughline).
- **Recoloring an anim GIF:** remap by matching the source cloak RGBs on the composited RGBA frames
  (robust), or swap the GIF's palette entries directly (cloak lives in a contiguous index band).
- **Deferred anims now have a home:** Sahnar's Specter sword anim + Lupin's Lycanroc #0745 anim both ride
  the **#90 enemy-anim import pipeline** (`tools/feditor_to_banim.py`) once picked up — source pointers in
  the YAMLs + on #24 (Lupin) / #25 (Sahnar). Not vendored yet (re-fetch on pickup).
_Decided: 2026-07-17_

---

## Class Mapping & Promotions

All 8 PCs (and recruits) are **stock vanilla FE8 classes** — class bases, caps, MOV, and CON come
from the class (`fireemblem8u/src/data_classes.c`). **No custom classes, no per-character
abilities.** Individuality comes from flavor text, sprite/portrait art, and palette.

**Growths + starting weapon ranks: copied from a class-matched vanilla "stat donor" unit**
"Do what the actual game does" — rather than invent growths, each cast unit takes the personal
growths and base weapon ranks of a canonical FE8 unit of the same class, so it levels and fights
like a real FE unit of that class. Donors (`STAT_DONOR` in `tools/build_campaign.py`): Shaman→Knoll,
Mage→Lute, Archer→Neimi, Armor Knight→Gilliam, Priest→Moulder, Pegasus Knight→Vanessa, Pirate→Garcia
(no PC pirate exists in FE8; the axe-fighter is the proxy). Base stats stay the pure class baseline
(personal base deltas 0). Donor data is read from a pre-patch vanilla snapshot so it's correct even
when a donor is itself a portrait slot we repurpose. Per-unit growth/rank tuning, if ever wanted, is
a later balance pass.
_Decided: 2026-06-04 (replaces the earlier zeroed-growths / flat-E-rank placeholder)_

**This does NOT mean stripping vanilla FE8 *class features*.** A stock class keeps its built-in
kit — Berserker crit, Bishop's bonus vs monsters, **Summoner's Summon command (CA_SUMMON)**,
Canto, flight, etc. We dropped the homebrew D&D ability layer, not FE mechanics.

**Base classes**
| PC | FE base | D&D source |
|---|---|---|
| Braulo | Pirate | Barbarian (Berserker) |
| Marty | Shaman | Druid (Circle of Spores) — FE8's Druid class is reachable only via Shaman |
| Meesmickle | Shaman | Warlock (The Fiend) |
| Prof. RBG | Archer | Artificer (Artillerist) |
| Rootis | Mage | Sorcerer (Draconic) |
| Sclorbo | Priest | Bard (College of Lore) |
| Wolfram | Knight (Armor Knight) | Metallurgist |
| Pinky | Pegasus Knight | — (RBG's homunculus "son"; no D&D class — the 8th PC, a lord candidate) |

Marty & Meesmickle share the Shaman base class and the same Ewan-donor **bases**, but they are **not** stat-twins from the start: their **personal growths differ from level 1** (Marty inherits Knoll's, Meesmickle Ewan's — split toward their promotions), and the class branches at the Master Seal (Marty → **Druid**, Meesmickle → **Summoner**). Donor split detail: §Party-side parity (#45).
_Decided: 2026-05-30 (supersedes the 2026-05-27 "Marty→Monk for sprite differentiation," which forced an illegal Monk→Summoner promotion)_

**Pepperjack & Brie are vanilla FE8 map ballistae (siege the party mans), NOT roster recruits**
RBG (an Artillerist artificer) builds his ordnance — the cannon-golem art (barrel snout, rope fuse) was always artillery — so they're implemented the **vanilla way**: a map-placed siege emplacement (ballista terrain + the ballista object), not a unit class. **No recruit slot, no `deploy_limit` cost**; their YAML carries `fe_stats.class: null` with `role: ballista`, because a ballista is map equipment, not a character. They appear from the vanilla ballista era — FE8 debuts ballistae in Ch10 "Revolt at Carcino" (Eirika route) → our ~Ch10 onward — as flavored emplacements on relevant maps; the party mans them like any FE8 ballista (`US_IN_BALLISTA`). They're a couple (Brie built for Pepperjack, Adam/Eve framing) with mirrored designs in opposing palettes, and speak Pokémon-style (each only says its own name — "Pepperjack!" / "Brie!"). Brie is the only female of the cast (`gender: female`). Combined concept ref → `data/portraits/pepperjack-and-brie.jpeg`; full flavor → `lore/pepperjack-and-brie.md`.
_Decided: 2026-06-20 (supersedes the 2026-05-29 "ordinary recruits, not summons" and the 2026-06-04 "join as regular FE8 units, not ballistae" framings — we don't break from vanilla, so ballistae stay map siege)_

**Promotions are FE8's vanilla BRANCHED choice (the player picks at the Master Seal)**
Every promoting class has two vanilla options (`fireemblem8u/src/classchg-data.c`); each unit YAML
lists the `branch` + a thematic `default` (in **bold**):
- Braulo: Pirate → {Warrior, **Berserker**}
- Marty: Shaman → {**Druid**, Summoner} — Druid = his D&D class name; Summoner = the Summon command
- Meesmickle: Shaman → {Druid, **Summoner**}
- RBG: Archer → {**Sniper**, Ranger}
- Rootis: Mage → {**Sage**, Mage Knight}
- Sclorbo: Priest → {**Bishop**, Sage}
- Wolfram: Armor Knight → {**General**, Great Knight}
- Pinky: Pegasus Knight → {**Falcon Knight**, Wyvern Knight}
_Decided: 2026-05-30 (fixes the illegal Monk→Summoner and the non-existent "Dark Sage")_

**Sclorbo: stock Priest → Bishop (staff healer; attack tomes at promotion)**
A vanilla Priest — staff-only healer at base, Light attack from the Bishop promotion. He is the
MVP healer. The earlier "Lore Bishop" custom hybrid (Dancer chassis + retained Dance + per-turn
Dance-or-Cast lever + custom heal tiers) is gone: no Dancer, no Dance, no Rapier.
_Decided: 2026-05-29_

**Rootis: stock Mage → Sage / Mage Knight**
A plain anima caster (ice = flavor only). The earlier "Dragon Wings = Manakete-style class
transform" and "custom flier Sage" are gone with the ability strip — no transform, no dragon form,
no Sorcery Points. His draconic identity is sprite art + lore.
_Decided: 2026-05-29_

**FE stat column folds 5e stats to FE stats**
Class-mapping docs surface FE engine stats (STR/DEX/MAG/etc.) instead of 5e stats (WIS/INT/CHA). All magic-stat 5e classes (WIS Druid, INT Artificer, CHA Warlock/Sorcerer/Bard) use MAG in engine. Flavor distinctions stay in YAML metadata, not class mapping.
_Decided: 2026-05-27_

**Wolfram & RBG are NOT casters**
Both are stock physical classes with **no spell access**: Wolfram is a Lance Knight (STR), RBG a
Bow Archer (SKL/DEX). The earlier "hybrid caster" overlay (secondary MAG, finite-use cantrip
tomes) is gone. Their fire/forge and firearm/gadget flavor is sprite art + lore only.
_Decided: 2026-05-29_

**The promotion seam (Ch 8 → 9): foreshadow in the MVP, pay off at Revel's End**
The MVP plays entirely **unpromoted** (5e levels 1–5); promotions are post-MVP. The seam:
- **Foreshadow in MVP (updated 2026-08-09).** Saving all four **Ch 5 (Elven Tomb)** reliquaries
  awards vanilla's **Guiding Ring**. The earlier plan for Ravisin to drop a flavored
  **crest of cold iron** was retired: it had no item id and lived on an unread `drops:` key.
  The real ring sits in the convoy, unusable, as the same Chekhov's gun for promotion.
- **Pay off at the seam.** The **first Master-Seal-equivalent** is obtained in/after the
  Revel's End break (**Ch 9**, post-MVP) — diegetically looted from the prison or earned in
  the escape. This matches FE8 holding promotions until the route-split era
  (`fe8-pacing-reference.md §3`).
- **Promotions go live ~Ch 10–12** (see memory `manchego-stars-campaign-structure`); PCs reach
  5e ~L11 / first FE promotion there. Specific crests (Knight Crest, Guiding Ring) may
  *flavor-appear* for an early single promotion, but the **Master Seal is the universal
  mechanism** (avoids class-matching headaches across 8 PCs).
_Decided: May 2026; renumbered to Ch 8→9 on 2026-05-31 after the Ch 4 split (was Ch 7→8)_

---

## Story & Dialogue

**Tutorial-parity is a standing guardrail, not a one-time map.**
Combat is vanilla-strict (no new mechanics), but rewriting cutscenes and reordering content can
silently strip the onboarding a vanilla player gets — and vanilla delivers it through BOTH
`PLAY_FLAG_TUTORIAL`-gated boxes AND mandatory story dialogue (a veteran who declines the tutorial
still sees the dialogue half; e.g. Tirado narrating that Ephraim "uses the terrain wisely",
`texts.txt`). Since our chapters are authored as-we-go, any static "lesson → chapter" map rots the
moment a debut moves. So the system is three parts: (1) a **stable catalog** of what vanilla
teaches + channel + decomp citation — `campaigns/.../onboarding-catalog.yaml`; (2) a **living
ledger** in each chapter YAML — an `introduces:` list of the concepts making their first campaign
appearance there and how we cover them (`coverage`: tutorial box vs in-voice dialogue, per the
C-hybrid — boxes for dry systemic lessons, dialogue for threats/narrative); (3) a **dialogue-pass
reflex** (skill step) that cross-checks new firsts against the catalog + prior ledger at
beat-planning and flags the owed heads-up. `tools/gen_onboarding_index.py` rolls up coverage →
`docs/ONBOARDING.md`; `tools/test_onboarding.py` gates integrity (orphan / double-debut concepts)
+ doc freshness. Each concept debuts once. (Catalog citations + precise vanilla trigger chapters
are a living decomp sweep; entries marked "decomp sweep TBD" are grounded as authoring proceeds.)
Follow-up: the ONBOARDING.md freshness check lives in `test_onboarding.py` rather than
`check.py`'s `check_generated_indexes_fresh` because `check.py` is pipeline-lane-owned — fold it in
there via the pipeline lane when convenient (issue/coordination, not a content-lane edit).
_Decided: 2026-06-21 (Nicolas; "build this in as the guardrail so we create freely without dropping vanilla things")_

**Faceless narration/asides always ride an opaque SOLOTEXTBOXSTART box, never the translucent talk window (#58).**
A `narration:` (faceless) line shown via the default `Text()`/TEXTSTART path renders in the translucent
conversation window — illegible over a BACG's scene art (the brother's v0.1.0 "Marty leans in..." aside). The
engine routes text type 0 (TEXTSTART) to the faced talk system (`sub_800E210`) and type 4 (SOLOTEXTBOXSTART) to
the opaque, auto-centered BoxDialogue (`sub_800E31C`, helpbox.c) — and the opaque box draws **no faces**. So in
`build_campaign.py`, scenic beats are emitted per-beat (`_scenic_beat_calls`): a beat that is ALL faceless
narration rides `SVAL(EVT_SLOT_B,0xFF00FF) + SOLOTEXTBOXSTART` (auto-center) and is wrapped at the on-map width
(28, not the 42 scenic wrap, so the centered box fits 240px); any faced beat stays on `Text()`. Because the box
can't mix with faces, a beat mixing narration + dialogue must be **split** with a `beat_break` (e.g. ch01 ending
E2/E2b) so the aside gets its own box. Campaign-wide convention; the road-sign narration already used this.
_Decided: 2026-06-20; from the brother's v0.1.0 playtest (#58)._

**Dialogue is co-written via the `dialogue-pass` skill: voice bibles → beats → 2–3 variants per beat, Nicolas picks.**
Neither of us is a creative writer, so the workflow encodes what three expert communities converge on — FE hack
writing ("every sentence spoken should have a purpose"; pace in A-presses, 2 visible lines/box), DM practice (voice
flows from a character document), and evaluated human-AI co-writing (hierarchical bible→beats→lines with human
curation at every level, never accepted wholesale). Voice bibles live as **§Voice sections in `lore/*.md`** (diction
rules, calibration lines, banned list; `lore/narration.md` holds the card/crawl/tour register + vanilla pacing
budgets measured from the decomp). Workflow + budgets + insertion gates: `.claude/skills/dialogue-pass/SKILL.md`.
_Decided: 2026-06-09 (community research: FEU writing threads, DM voice guides, Dramatron CHI'23)._

**MINE THE CORPUS BEFORE WRITING A LINE — this is now step 0 of the drafting loop, not advice.**
ch05's Basil/Sahnar scene burned a dozen rejected drafts written from instinct; **two Ewan/Saleh support conversations fixed it in a single pass.** FE8 ships ~40k lines and we were cherry-picking six quotes and then guessing. The method (`.claude/skills/dialogue-pass/references/natural-speech.md`, wired as SKILL.md drafting-loop step 0): read the twin chapter's scenes with `tools/vanilla_scene.py`, and for a two-hander find the **relationship twin** among FE8's ~217 two-character scenes — its **support conversations** are the game's intimate two-handers and the closest form to most of our scenes. Pick the pair whose *dynamic* matches (eager student + reserved mentor → Ewan/Saleh) and read all of them.
The diagnosis it produced — **"epigram disease," our single most common dialogue failure**: every line polished into an artifact that lands one beat and hands off, which reads as poetry rather than talk. **Vanilla is redundant and inefficient and that is precisely why it sounds human** (Joshua and Natasha both apologise twice; she says four things that all mean "I'm leaving"). Four laws follow: turns are **lopsided** (two words answered by forty); the eager character **runs on and interrupts himself**; characters **say the feeling plainly** instead of burying it in subtext; reserve reads as **brevity and plain complete sentences**, never as an ellipsis on every line. Corollary applied to `basil.md`: the "2–5 words, no subordinate clauses" spec was retired — it made her read as slow rather than gentle.
_Decided: 2026-07-23 (Nicolas + CLAUDE; ch05 9BB — "you have the entire game's dialogue and you're not writing like it")_

**Villain voice is grounded in FE8's own script, and contrasting clichés are banned.**
Two more craft rules in `.claude/skills/dialogue-pass/SKILL.md`. (1) **No "not X, but Y"** — no antithesis, no then/now contrast, no defining by negation; state what IS. It is a *tic*, not a style: once it is in your ear every character sounds identical, and it was the single biggest cause of flat ch05 dialogue (*"that's not life, it's fever"*, *"I don't kill, I cleanse"*). But over-correcting into uniform flat declaratives reads as **monotone** — vary rhythm and temperature. (2) **Ground villains in the decomp corpus** (`fireemblem8u/texts/texts.txt`), not invention: FE8 villains address the party directly with an insult-name (dogs/wretches/rats), *relish* it, and use dark irony — Valter's *"I'll save you worthless dogs from your own incompetence. You'll thank me later"* is the shape a mercy-doctrine should take (swagger, not sermon).
_Decided: 2026-07-23 (Nicolas + CLAUDE; ch05 eruption beat)._

**Dialogue-pass craft learnings (2026-07-23, ch05 opening) — folded into the skill's Craft check.**
Two failure modes surfaced hard while writing ch05 and are now first-class checks in
`.claude/skills/dialogue-pass/SKILL.md`: (1) **people talking, not mood-narration** — the #1 cause of
"dry"; a line that *describes atmosphere* ("she wakes the sad things") is dead even when evocative, so
every box must be a person reacting/joking/asking, with dread carried by a concrete in-character line;
(2) **draft BOXED, not prose** — prose-length lines read wordy and hide the A-press pacing, so lines are
hand-boxed (2 lines, ~29–30 ch; on-map ≤29) from the first pass and shown boxed. Also: **canon research
in the ROM-free web env** — the RotFM PDF lives on Nicolas's Mac, so fill canon gaps from online
actual-play recaps + the Forgotten Realms wiki (this caught Sahnar's real identity: female, elven royalty,
awake-and-aware for millennia). Verify against Nicolas's table, which outranks book canon for our version.
_Decided: 2026-07-23 (ch05 opening dialogue pass, ROM-free web session)._

**ch05 opening uses the vanilla two-scene rhythm: a focused PRE-MAP cutscene + an ON-MAP opening scene.**
`chapter_start` (Text_BG) carries the ch04 thread and mood (party descends the gateway into the open-air
hollow; Lupin/Marty/Pinky; Ravisin stays SILENT — saved for the eruption); then the map loads and a
`map_opening` on-map scene brings the enemies into view and Basil (a green ally) joins. More dynamic than
one talking-heads cutscene, and it's what FE8 does. Villain reveal is *earned* at the eruption (she acts,
she doesn't monologue at the door). _Decided: 2026-07-23 (ch05 opening, with Nicolas)._
**In-engine dialogue review is motion, not stills:** `tools/playtest/run.sh record` captures every 5th frame
through both scenes; deduped GIFs (opened in Safari) are what Nicolas signs off before art-visible text commits —
static screenshots catch the typewriter mid-stroke and false-alarm as cut-off text. _Decided: 2026-06-10 with
Nicolas ("use this format going forward")._

**New-game opening sequence: three exclusive content layers, written in story order.**
Mirrors vanilla FE8's structure (decomp-grounded): (1) **lore crawl** (#43, replaces `StartIntroMonologue`'s 7
subtitle cards) = the COSMIC layer — Auril, the two-year Rime, the sacrifice lotteries (adapted from the book's Cold
Open boxed text, printed p.22); (2) **world-map tour** (#43, replaces `WM_TEXT(0x8DB)`'s Magvel nation tour) = the
GEOGRAPHIC layer — all ten towns in 4 cards, grouped Bryn Shander / Maer Dualdon / Lac Dinneshere / Redwaters
(one fewer A-press than vanilla's 5 nations); (3) **chapter scenes** = LOCAL plot only, dialogue-driven like
vanilla's prologue (zero world exposition — vanilla puts none there either), plus brown-box location cards
(`BROWNBOXTEXT`, the "Renais Castle" analog). No layer repeats another's facts, so #43 can land later without
rewriting prologue text. Corollaries: the **Northlook hiring scene opens ch01** (not the ch00 ending, which fades to
black on Scramsax's last line — location cards are scene-OPENERS in FE grammar, so ch01's opening owns the
Northlook card; no closing tease); Sephek's prologue escape
leaves **no corpse** (blade to shards, body rimes over, gone) — the withered-corpse reveal is **reserved for his
true death** in his payoff chapter (`lore/sephek-kaltro.md` §Imagery budget).
_Decided: 2026-06-09 with Nicolas (towns: all ten, lake-grouped; location card: yes; Northlook → ch01);
2026-06-10 (ch00 ends on dialogue fade-out, no card tease — Nicolas's call, FE scene-grammar)._

**Lore crawl rides vanilla's seven-slide proc untouched; slides are re-rendered PNGs, gated by `MONTAGE=1`.**
The "long ago…" monologue is seven prerendered 4bpp slides (`graphics/op_subtitle/`, `gOpSubtitleGfxLut`), not
message text — `opsubtitle.c` walks them with hardcoded transitions (plain fades 0-1, flare reveal on 2,
cross-blends 3-4, mural close 5-6; START skips). Our crawl was locked at 7 cards to reuse that machinery with zero
proc changes: `tools/gen_subtitle_cards.py` re-renders the slides from `events/opening-montage.yaml` (Georgia 13px
+1px tracking — side-by-side closest to vanilla's serif; quantized into the vanilla 16-color ramp so the warm AA
browns match; ≤220px lines, 24px pitch, block centered on (120,80); slide-display LUT retimed `120+8·words`,
clamped 240-360 frames). Index 0 is GBA-transparent → in-engine the cards read cream-on-black like vanilla, so the
slate PNG background is a converter placeholder only. **Build modes:** default `make` keeps the straight-to-map dev
boot; `MONTAGE=1 make` keeps `StartIntroMonologue` wired and re-renders the slides (distribution #37 must set it).
The controller covers the default straight-to-map build. A `MONTAGE=1` automation must add the subtitle proc's
explicit live skip-input state before pressing START; there is no cadence fallback. `record` captures the crawl
for GIF review. **Backdrop mural:** vanilla composites
the slides over `Img_CommGameBgScreen` (the brown rune wall)
— a SHARED asset (shops, chapter-intro fx, ending details, mural_background), so it is never overwritten; instead
opsubtitle.c is patched to montage-local `Img/Pal_MontageMural` symbols incbin'd in `data_opsubtitle.s`, fed by the
book's ch1 opener painting (aurora over a snow-buried township, `campaigns/.../events/opening-mural.png`; build
derives the 256×160 16-color mural: brightness 0.75, 15 colors + black at GBA-transparent index 0).
_Decided: 2026-06-10; crawl and aurora mural both GIF-reviewed and approved by Nicolas._

**Build the two flavours with `tools/build.sh test|dist` — a plain `make` after `build_campaign --montage` silently clobbers the montage.**
The `fireemblem8.gba` make target ALWAYS re-runs `build_campaign.py`, appending `--montage` only when `MONTAGE=1`. So the
intuitive "run `build_campaign.py --montage`, then `make`" sequence re-runs the generator WITHOUT the flag on that second
step and reverts the montage sources → a no-opener ROM byte-identical to the test build (this masqueraded as a "montage
won't compile / stale-objects" bug for a whole session; it was never a compile problem). The montage flavour MUST be one
command: `make MONTAGE=1`, wrapped as `tools/build.sh dist` (test = `tools/build.sh test`). A correct montage ROM's md5 is
NOT the no-opener `142971e3`. Sanity check after a build: `grep -c "skip intro monologue" fireemblem8u/src/gamecontrol.c`
= 0 for dist, 1 for test. Also: the decomp ships Linux `#!/bin/python3` shebangs that do not exist on macOS, and any
`git checkout` inside the `fireemblem8u` submodule reverts the fix — the next build then dies on `bad interpreter`,
minutes in, from a Makefile rule that looks unrelated. `setup-toolchain.sh` and `build.sh` both rewrite them, but the
DOCUMENTED build command is plain `make`, which bypassed both, so the failure kept recurring (three times in one session,
2026-08-05). **`build_campaign.normalise_decomp_shebangs` now re-applies it idempotently on EVERY build** — the hole is
closed at the one place every build passes through, rather than in wrappers a caller has to remember.
_Decided: 2026-06-17; root-caused + dist (with opener) GIF-verified end-to-end
(`run.sh recordopening`: title → New Game → lore crawl → Ten Towns tour → prologue map)._

**World-map tour rides vanilla's drawn-map slot with two Icewind Dale backdrops, selected by a free mask bit.**
The drawn map (`WM_SHOWDRAWNMAP` → `StartGmapRm`, `worldmap_rm.c`) is one 240×160 prerendered screen: a 30×20 TSA
over ≤640 unique 4bpp tiles at BG VRAM 0, palette rows 5-8 (raw TSA entries get +0x5000). `tools/gen_drawnmap.py`
converts source art into that format (crop 3:2 → 240×160 → erase source lettering with rect median filters — it
never survives the downscale — → re-letter in a 3×5 micro-caps font + Georgia titles → per-tile 4-row palette
quantization; `--emit` writes the ROM trio into `campaigns/.../events/`). **Format gotchas (cost a debug session
each):** tile 0 must be fully transparent — during the blocking display `GmapRm_80C2320` parks BG1 behind a
cleared-to-tile-0 BG2, so a non-blank tile 0 paints the whole screen through the wrong palette; and TSA rows are
stored bottom-up (`TmApplyTsa` walks the dest upward). **Backdrop pair (Nicolas, 2026-06-10):** map A = the Gemini
Magvel-style repaint of the whole dale (establishing shot, card 1), map B = the purchased hand-drawn ten-towns map,
icy duotone, all ten towns + three lakes re-lettered (cards 2-6). Vanilla's `Img/Pal/Tsa_EventGmap` are shared with
ch2/ch5 WM events, so the consumer is patched to montage-local `*_MontageDrawnMap{A,B}` symbols (mural rule);
`GMAPRM_FLAG_4` (0x10, never read by engine code) on the `WM_SHOWDRAWNMAP` mask picks map B. **Event**
(`inject_world_tour`, MONTAGE=1): `EventScrWM_Prologue_Beginning` rewritten on vanilla's own rhythm — spawn lord,
SILENT → THE BEGINNING, map revealed by `WM_FADEOUT`; the A→B swap hides under a `FADI`/`FADU` pair (masks leave
the GmapRm blend flags clear, vanilla's prologue shape). The WM text window covers the bottom ~50 rows, so map B
shows at scroll y=24 and rides vanilla's pan trick (`WM_MOVECAM2` scrolls BG1 here, not the camera) down to y=48
for the Redwaters card and back for the closer; both maps are lettered for those scrolls. The 6 locked `town_tour`
cards become msg 0x8DB (vanilla's WM narration, referenced only here) as `[BreakTalk]` segments ↔ `TEXTCONT`
boundaries, 42-char lines, 2-line pages. **Save-slot banners:** `sub_80895B4`'s `config&1` palette table continues
past the 9-color `gPal_08A07AD8` label — the save-slot select reads pair 0's tail + the +0x10 dim row through
`gUnknown_08A07AEA`/`gUnknown_08A07B0A`, so `inject_title_theme` recolors those too (16 + first 7 colors) or the
unselected slots stay vanilla green; the per-difficulty pairs stay vanilla (semantic colors).
_Decided: 2026-06-10; full New-Game-to-map GIF reviewed and approved by Nicolas ("perfect"), save-slot fix verified
in-emulator. Closes the tour half of #43 and bootstraps #29._

**Multi-speaker cutscene faces: the budget is PODIUMS (positions), not speakers (the 4-face fix).**
Only `FACE_SLOT_COUNT = 4` faces load at once (the `gFaces` pool; `include/face.h`), but a big set
piece (the ch01 Beat-1 Northlook scene) has ~10 speakers. `_script_to_message` tracks the 8 talk
POSITIONS as a live map (≤4 loaded) + an LRU: reusing a podium for a new speaker emits
`[OpenX][ClearFace]` (scene.c fades out `faces[activePosition]` and frees its slot; the command's
temporary lock means the fade-out completes BEFORE the next `[LoadFace]`, so the pool never
overflows), and a full pool evicts the LRU. A `preload` list seeds silent **listeners** before the
dialogue (so no one talks to an empty room); a `(podium, None)` staging value is a faceless box.
≤4-podium scripts (the prologue) render byte-identically to the old lazy-load path.

**Staging = clean two-shots.** Face podiums (gTalkFaceHPosLut, px = x·8; faces are 96px wide):
FarLeft 24 / MidLeft 48 / Left 72 / Right 168 / MidRight 192 / FarRight 216. Only podiums ≥96px
apart avoid overlap, so the one clean pair is **MidLeft ↔ MidRight** (144px). Speakers therefore
rotate through the mid-left spotlight with the anchor (Hlin) at mid-right; listeners fill outer
podiums where slight overlap reads as "standing together." (Decided after Nicolas flagged 3-stacked
listeners and Hlin/Scramsax overlap as too crowded.)

**Scene wiring.** The locked chapter `script:` splits on `beat_break` sentinels into one `Text()`
per beat — each `Text` ends in `REMA`, which clears all faces (`sub_800E640`) → a fresh 4-face
budget per beat while the `BACG` background persists across `REMA` (cf. ch16a). At the head of
`EventScr_Ch2_BeginningScene`: `REMOVEPORTRAITS`→`BACG(BG_FIREPLACE)`→`FADU`→`BROWNBOXTEXT`
(auto-dismissing "The Northlook" card)→beats A–E (Hlin's "who leads?" lands in beat E, still at the
Northlook)→`FADI`. Then the **lord-select runs over its own scenic BG, not the battle map**
(`CH01_LORDSEL_BG = BG_DARKLING_WOODS`): `BACG` draws on BG3, the menu's `ClearBg0Bg1` only touches
BG0/1, and `CallLordSelectMenu` sets `SetDispEnable(1,1,0,1,1)` (BG2/map OFF). After the pick:
`FADI`→`LOMA(host)` (`RestartBattleMap` rebuilds the map BG VRAM that `BACG` clobbered — cf. ch13a;
plain `RemoveBGIfNeeded` is for chapter *transitions*)→DISA/LOAD→`FADU`→PREP.

**ON-MAP (no-BG) event-script cutscenes anchor the talk bubble to a FACE, not a unit** (the ch03
mid-map RBG-execution beat — a mid-battle Misc `AFEV`, no `BACG`). Over a `BACG` the text is a
full-screen window; on the bare map it's a `PutTalkBubble` speech bubble, and the bubble anchors to
the on-screen face podium (`[OpenX][LoadFace]`). So a **faced** beat renders fine wherever the camera
is, but a **faceless** line (no `[OpenX]`) has no anchor — in a Misc `AFEV`/`TURN` script there is no
talking unit either — so the bubble lands off the tilemap and only a sliver shows. Two rules fall out
(`_beat_is_faceless` routes them): (1) a faceless on-map line must ride the opaque **auto-centered**
box (`SVAL(EVT_SLOT_B, 0xFF00FF)`→`SOLOTEXTBOXSTART`), which needs no anchor; (2) **never mix a faced
and a faceless speaker in one on-map beat** — the faceless half drags the shared bubble off-screen and
mis-wraps the faced half (Marty + the mugless Brute did exactly this). Split them into separate beats
(each `Text()`'s trailing `REMA` clears faces, so none bleed across — a bare `TEXTSHOW` chain without
it left Pinky's face up under Wolfram). Cleanest fix when a speaker recurs: **give it a mug** — the
Brute got one on the collision-free Caellach guest slot (`GUEST_PORTRAIT_MAP`), turning its beat into
a normal faced bubble. Verified in-engine (`recordch03midmap`, 2026-07-11).

**Transitions: keep the FADE (vanilla-flavored).** Vanilla never reuses one podium for different
*people* — each speaker gets their own slot (≤4), faces fade in once, `REMA` clears between messages
(`[ClearFace]` is in 0/119 vanilla scripts); the in-place swap (`sub_80066E0`) is vanilla but only
for one character's *expression* change. So for our one-podium roll-call the `[ClearFace]` fade
("one leaves, next arrives") fits vanilla's grammar; a swap would morph one face into another.
_Decided 2026-06-16 with Nicolas across four motion reviews (`run.sh recordch01`): Sclorbo shows
his Ross face; Marty's spore-cough is a parenthetical (FE8 has
no cutscene particle FX); Pinky (Neimi) appears beside RBG at his intro; lord-select confirm reads
"lead the party." `make` green, `verify_text` 3404/0, playtests PASS (ch00 win/gameover, ch01 entry,
ch01win). #21._

**Ch1 trail beats: vanilla-reskin hints, an Izobai boss voice, and 'Ol Bitey over the hearth.**
The two house hints reskin **vanilla Ch1's own house quotes** (`0x93B`/`0x93C`, the ids we reuse):
the gate→"the mounds provide defense and heal wounds to boot," and the armor-knight→Izobai's
scrap-plate "turns aside almost any blade… I know my armor, though… a good blast of magic could get
right through it" (the weapon-triangle tip was cut — vanilla's house never carries it). The road
sign + the dismembered sled-driver fold into one trailhead trigger. Izobai (`lore/izobai.md`,
cunning/mocking mercenary) gets a turn-1 taunt (spare `EventScr_Ch2_Turn2Player` slot) and a death
quote. **'Ol Bitey** — the stuffed fish Scramsax name-drops — is mounted over the Northlook hearth
by `inject_northlook_bitey`: a build step that git-restores the vanilla `bg_Fireplace.png` (idempotent),
paints a small fish using ONLY existing palette colours (so each 8x8 tile stays in its 4bpp 16-colour
bank), and clears the converted intermediates so `make` re-derives them. Hand-written narration must
pass `_term_pad` (the `[.]` Huffman terminator-parity pad) or it bleeds into the next message.
_Decided 2026-06-17 with Nicolas (interactive dialogue pass, one beat at a time; Bitey art reviewed
in-game). `make` green, `verify_text` 3404/0, ch01win PASS. #21._

---

**Ch1 ending "The Rolling Cheddar" wired the same way as Beat 1.**
The locked `chapter_end` script is consumed by `inject_ch01` into `EventScr_Ch2_EndingScene` exactly
like the opening: a scenic `BACG` + a "Bryn Shander" brown-box card + one `Text()` per beat (A–F),
each `Text()`'s trailing `REMA` clearing faces so the 4-face budget resets per beat. Speakers are
staged as clean two-shots — **Duvessa (the host) anchors mid-right** and the party speaks mid-left,
with the other beat speaker placed opposite her; in beat E **Baxby evicts Duvessa's mid-right podium**
(`[OpenMidRight][ClearFace]`) as she gestures to the market and the bird steps forward. Bodies/card
ride the same dead vanilla Ch1-tutorial slot-2 ids as Beat 1 (`0x946`–`0x94C`). **Baxby's cutscene
face rides the vanilla Forde slot** (`GUEST_PORTRAIT_MAP`): Forde is a Cavalier — matching Baxby's
donor class — absent from our MVP chapters (ch00–08), so dressing `FID_Forde` with `baxby.png` is
collision-free; his recruit UNIT + map sprite will ride that same Forde character slot when wired.
The scene plays over the vanilla **`BG_NORMAL_VILLAGE`** BG (we tried winterizing it — a palette swap
just washes the village out, and no clean FE8 GBA snow-village BG existed in the FE-Repo — so we use it
as-is; Nicolas 2026-06-17) and `MNC2(0x3)` still drops to vanilla Ch3 until ch02 is hosted.
_Wired 2026-06-17. `make` green, `verify_text` 3404/0, ch01win PASS (ending runs through all 6 beats
→ advances). Feel/motion review is Nicolas's in-game pass. #21._

---

**Sephek Kaltro arc — distinct from Ravisin; ch02 plants the breadcrumb; reckoning held for Act II.**
Sephek (ch00 prologue boss, escapes undead) and **Ravisin** (ch05 "The Elven Tomb" frost-druid boss,
the beast-awakener) are **separate villains and stay separate** — both serve Auril (canon: Sephek is a
frost-druid spirit in a drowned mariner's body, book p.23-24), but Ravisin's ch05 stays our clean first
boss kill and Sephek is never folded into it (that would spend his reserved drowned-mariner death-reveal
in her fight). The **ch02-targos-inn** ending plants his first breadcrumb: the frozen body is one of his
sacrifice-lottery executions; the town blames the druids' rumor, while **Rootis** privately recognizes
the dagger-of-ice M.O. from **Hlin's briefing** (the party didn't witness ch00 — that prologue deploys
Hlin + Scramsax only, so Rootis knows the method, not the man). No fight here. His **reckoning** is held
for **Act II**: the book reserved the Torrga Icevein caravan as his payoff venue, but ch00 already uses
that caravan as its setting, so his true death gets a fresh Act-II setting — **provisionally a secondary
boss on a multi-boss map** (vanilla precedent: FE8 Ch15 Caellach + Valter, the Final chapter's Demon King
+ Lyon; our own ch05 already runs Ravisin + the White Moose), firmed when the back-half DM notes arrive.
Don't spend his death-reveal imagery before then.
_Decided 2026-06-19 with Nicolas (interactive story + dialogue pass for ch02-targos-inn)._

---

**#125 msg-id collision (ch01 ending vs. the tutorial trade demo) — RESOLVED unreachable, no emulator
needed.** `CH01_ENDING_MSGS` (0x949-0x94C) are also `TEXTSHOW`n by vanilla's tutorial-mode trade demo
compiled into `src/bmtrade.c`, which nothing patches — flagged as a live risk needing an mGBA repro to
size (#122 comment-sweep). Traced instead: that demo only runs behind `CheckTradeTutorial()` ->
`CheckFlag(0x87)`, and flag `0x87` has **exactly one setter in the whole decomp** — `ENUT(0x87)` inside
`EventScr_Ch1Tut_TradeSelectGalliamEnd` (`events/ch1-tutorials.h`), part of vanilla's real Ch1 chapter
slot (`Ch1Events` in `data_8B363C.s`) — a **separate ROM asset from `PrologueEvents`**, the only slot our
chapter progression ever loads (New Game redirects to `PROLOGUE_HOST_INDEX`; `_redirect_new_game` in
`build_campaign.py`). Vanilla's real Ch1 never loads in our build (our "ch01" rides the Prologue slot
instead), so flag `0x87` can never be set, `CheckTradeTutorial()` always returns false, and the trade
demo — and this msg-id collision — is unreachable by construction. General lesson for the msg-id-vetting
gotcha (below): reachability isn't just "is this id referenced elsewhere" (the 0x993/0x994 lesson) — a
referencing event can ALSO be dead if its own trigger condition (a flag, in this case) can never be set
in our build's actual chapter-load graph. Static trace of the flag's setter(s) resolves it without mGBA.
_Decided: 2026-07-05 (CLAUDE; pipeline track. #125, closed not-planned — no code change, comment-only)._

---

**Marty's "spore covenant" is retired — a thread that reads well in a bible and never reached a beat**

Written 2026-07-23 during the ch05 dialogue pass: Marty as Ravisin's opposite number ("two
necromancers, opposite covenants: the composter vs. the taxidermist"), the dead owed a free return
to the earth, the sin being death held out of the cycle by force. It was a genuinely tidy idea and
it survived three weeks purely because it lived in `marty.md` rather than in a scene.

It never reached one. It carried an explicit IOU — *"exact line TBD in the beat; may move to the
recruit beat"* — and both candidate beats then locked without it. 9C5 gives the PARTY no lines at
all (vanilla Ch5's escalation is the arriving force speaking, and we took that shape); 9C6 turns
on Sahnar RECOGNISING Basil, not on anyone naming a sin over her. Nicolas's call, and correct:
*"it was an idea we silently moved away from… remove it so it doesn't mess with his character
later."*

The general lesson, which is why this is an ADR and not a quiet delete: **a bible section with an
open "line TBD" is a liability, not an asset.** It is unwritten dialogue stored where voice
guidance lives, so every future writer reads it as settled character and writes toward it. A voice
bible should describe how someone talks; a thread that needs a scene to exist belongs in the
chapter YAML's slot description, where it dies with the slot if the slot is cut.

Retired phrases are in `check.py` `DEAD_CONCEPTS`, so the drift lint rejects them in docs and
hand-written comments. Sahnar's ordeal no longer needs a second druid to mean something: she is a
soul held awake under stone, which is legible on its own.

_Decided: 2026-07-29 (Nicolas + CLAUDE; ch05 dialogue pass — retiring the "two druids" thread)._

---

**Vanilla's "if the escort died" cutscene is the same scene's BACK HALF — so our branch is cheap**

FE8 Ch5 ships its ending twice: `0x9C9` (34 boxes) if Natasha lives, `0x9CA` (24) if she dies.
The obvious read is "a whole alternate cutscene", and that read is what made an earlier pass mark
ours *not adopted* — it looked like duplicate exposition for a case most players never hit.

Mining it says otherwise. `0x9CA` is not a second scene. Its front is a different DELIVERY of the
same facts — fragments, interrupted by the party telling her to stop talking, then a flat
"....She's dead." — and its back is `0x9C9`'s deliberation running near-verbatim, with **exactly
one line changed** to price the loss (*"If she had lived, we might have learned more, but…."*) and
the closing box repeated word for word. The branch costs the delivery, not the scene.

So the rule for any chapter with an escort who can die: **the alternate ending is a re-delivery,
not a rewrite.** Write the lived one, then change how the information arrives and who is left to
react — and keep the last boxes shared, because that is what makes the two endings feel like one
chapter. ch05's pair sits at 25 / 18 boxes on this pattern.

The structural consequence that is easy to miss: it is the ESCORT who carries the chapter's forward
information, not a party member. That is *why* the branch has to exist, and it is also the reason
the escort's death is a real failure rather than a lost unit. Ours puts the ch06 hook in Basil's
mouth for the same reason — Sahnar is optional and cannot carry mandatory plot, and no party member
was standing in the tomb listening to Ravisin talk.

_Decided: 2026-07-30 (CLAUDE; ch05 ending block — adopting `0x9CA`, mined from `EventScr_Ch5_EndingScene`)._

---

**A recruit-gated scene block goes MID-scene, never on the button**

ch05's ending pays the question `0x9CC` deliberately left hanging (*"...Can I give you a berry
now?"*) — but only if the player actually did the escort, so the block is flag-gated on the
recruit. The placement rule that came out of writing it: **a conditional block belongs where
excising it cannot touch the scene's shape or its last box.**

Put it at the end and the scene has two different buttons, one of which most players never see, and
the closing beat stops being something you can write to. Put it in the middle and the scene reads
as one thing with a chamber in it — the surrounding beats carry the structure, and the conditional
carries the reward. Cutting it costs six boxes of warmth and nothing else.

This is not a new mechanism: `0x9C9` vs `0x9CA` is already a branch on the escort's death, one slot
later. We are reusing FE8's own conditional-ending wiring one act earlier, for a reward rather than
a failure.

_Decided: 2026-07-30 (CLAUDE; ch05 `0x9C9` Sahnar block)._

---

## Operational Gotchas (durable)

_Moved here from `HANDOFF.md` 2026-07-02 (audit): these are durable engineering constraints, not
session state. `HANDOFF.md` points here._

- **Dressing a portrait slot and NORMALIZING its mouth/eye window are two steps, and missing the
  second is silent** (2026-08-09, #25). `patch_portrait_geometry` only knew about `PORTRAIT_MAP`
  and the guests, so any other dressed slot kept the VANILLA character's mouth coordinates and the
  engine painted its blink/talk overlay at the old face's position -- smearing a block of skull
  across the eye sockets and doubling the teeth. Green build, passing scenario, corrupted face.
  Three of the four ch05 residents shipped that way, and the ch02 chwinga had been shipping it
  unnoticed since June; the fourth resident looked fine only because its donor slot's mouth
  happened to sit where ours does. `dressed_portrait_slots()` is now the single answer to "which
  slots do we overwrite" and a test asserts every dressed slot lands in it. **Three data checks
  (clip model, on-disk sheet decode, OAM probe) all passed while the face was visibly wrong --
  the corruption happens at DRAW time from a different table. Look at the rendered face.**

- **The matrix's speed problem was BUILDS, not scenarios -- and parallelism made it worse**
  (2026-08-09). A full run cost 7-9 minutes, enough that it gets skipped or over-run. Two fixes
  were tried; keep the first, do not retry the second without new hardware:
  - **ROM CACHE (kept).** Every configuration rebuilt every run even when nothing feeding a ROM
    had changed, because the tree holds one `fireemblem8.gba` and each group's `make` overwrites
    the last. ROMs are now snapshotted per (configuration, input digest) and copied back: a
    chapter suite went **37s -> 11s**, a full matrix skips ~170s of builds. The digest covers what
    the ROM is built FROM (campaign data, engine, injectors, Makefile, make flags, decomp HEAD)
    and deliberately EXCLUDES `harness.lua`/`matrix.py`/`matrix.yaml`, which drive the emulator --
    those are exactly the edits it makes free. **The ROM builds INSIDE the submodule** while the
    config stamp sits at the repo root; getting that pair wrong caches nothing, silently.
  - **PARALLEL SCENARIOS (measured, rejected, left off).** Scenarios run mGBA at `fps: 240`,
    deliberately unthrottled, so each already saturates a core; this box has 4 performance cores.
    At `jobs=4` individual scenarios went **10s -> 67s**, total wall did **not** move (444s vs
    439s), and four scenarios blew their wall-clock deadlines and reported ERROR/FAIL. Contention
    became false red, which is worse than slow. The knob survives with the numbers in
    `execute()`'s docstring so nobody re-runs the experiment blind.
  - **The real win is `SUITE=`.** A chapter suite is ~11s cached against ~6min for the full gate.
    Iterate on the chapter suite; the full matrix is the push gate, not the edit loop.

- **`harness.lua` is ONE Lua chunk against a 200-local ceiling — new top-level `local`s can stop
  the whole file loading** (2026-08-06, #232). Five new constants pushed the main function over
  Lua's limit and `harness.lua` stopped parsing outright: every scenario dies at once, and no
  source-text assertion notices, so a whole matrix run reported meaningless verdicts. Tuning lives
  in the single `TUNE` table for this reason — add to it rather than declaring another top-level
  local. `test_playtest_harness.py` now genuinely **compiles** the file, so `make test` catches it
  before anything reaches the emulator; a `loadfile` check must ASSERT, since it returns `nil, err`
  rather than raising (that is exactly how this slipped past a manual check).

- **Removing a blind input cadence can break waits that were silently relying on it** (2026-08-06,
  #232). #220 replaced cadence input with observed guarded input, which is right — but `waitFor`'s
  50-frame A-mash had been *load-bearing*: it advanced in-battle quote text, blew through the
  post-chapter save prompt, and re-sent presses FE8 drops during window fade-ins. Six waits had been
  sized or written around it and broke silently, unnoticed for weeks because the ch00/ch01 scenarios
  are not in the hand-run gate list and playtests have no CI. Two durable rules came out of it:
  **size a budget for the un-skipped case** (the ch00 boss animation measures 1238 frames against
  the old 1200 budget), and **prefer progress to wall-clock** — a running event engine is productive
  work and must not burn a stall budget, with a ceiling so a wedged one still fails closed.

- **A single guarded press can be LOST: FE8 drops input while a window animates in** (2026-08-06,
  #232). A press swallowed by a battle-forecast fade meant the wait burned its whole budget on a
  state nothing would move, and the run stayed wedged in `target_selection` for the rest of the
  scenario. `guardedInput` re-presses, but only while the state and the legal action are unchanged,
  and the FIRST attempt keeps the caller's whole budget so anything that already worked is
  untouched. Splitting that budget across attempts is a real hazard, not a hypothetical: it makes
  the first press give up early and fire a SECOND real action (it walked Marty off his parley tile).

- **A render from the frame PNGs proves the ART; only the ROM proves the TILING and the PALETTE**
  (2026-08-03, #206). A preview GIF built from `poses_to_feditor`'s output and the in-game sprite
  are separated by a whole stage — the frames are chopped into 8x8 tiles, packed into sheets, and
  described by an OAM list the engine reassembles in VRAM under a palette it chooses. So "the GIF
  looks right but the ROM doesn't" is not a contradiction to explain away; it *localises* the fault
  to that stage and rules out the art in one step. Read it as a bisect, not a mystery.

- **A scan bound is a property of the ENGINE, never of the current content** (2026-08-02, #206).
  `harness.lua`'s `blue()` searched **8** unit slots — correct back when the cast *was* 8 — so
  `recordanim` reported "lupin not deployed" for a wolf standing on the map, and the first
  instinct was to go hunting in the ROM. The TESTCH sandbox deploys 11 now. Bounds come from the
  decomp (`bmunit.h`: `blue[62]` / `red[50]` / `green[20]`). Any array walk sized to today's
  roster is a bug with a delay fuse.
- **A human's hand-edit of a GENERATED artifact must be the source of truth, or be replayable —
  otherwise it will be regenerated away** (2026-08-02, #206). Lupin's hand-painted spectacles
  nearly died twice in one session, from two directions: the frames were re-rendered underneath
  them (palette change), and the editor's sheet — being *derived from* those frames — was rebuilt
  on every open. Both routes are guarded now (`hand_painted:` + `prepare_sheet` keeping an
  existing sheet), but the general shape recurs anywhere a pipeline has a manual step: name which
  file is authoritative, and make every generator that could overwrite it refuse or replay.
- **A failing playtest may be the wrong ROM, not a regression** (2026-08-02, #207). `clear_ch02`
  FAILed with "never reached the map" during a goal-id change — on a `CH04BOOT=1` fast-boot ROM,
  which jumps New Game straight into ch04, so ch02's map is unreachable by construction. Rebuilt
  without the flag it PASSes. **Before believing a scenario failure, check which ROM it ran on:**
  the boot flags are per-chapter, and a scenario for an earlier chapter cannot pass on a later
  chapter's fast-boot build. The same applies in reverse to `PT_HOST_CHAPTER`.
  **Mechanised since 2026-08-06 (#231/#232):** `build_campaign.py` stamps `.build-config.json` with
  the flags that produced the ROM in the tree, `matrix.yaml` declares what each scenario needs, and
  `run.sh` refuses a mismatch in 0s with the exact `make` line. So this should no longer be a
  judgement call — but `MX_SKIP_ROM_CHECK=1` disables the guard and puts you straight back here
  (which is exactly what happened once inside the session that built it).
- **A guard that lists what it covers stops covering things** (2026-08-06, #138). The
  `HostChapterEventGroup` test was written after the ch04 disaster — a host slot retargeted by map
  ids alone, presenting our map while running the host slot's roster — and it iterated a
  hand-written tuple of `(HOST_INDEX, EVENT_GROUP)` pairs. It was correct and useless going
  forward: **ch05 would have been the first chapter not covered by the very test written to prevent
  its failure mode**, and ch05 hosts deeper into the divergence than ch04 did, because vanilla's
  slot index stops tracking chapter number at 4. `build_campaign.hosted_chapters()` now DISCOVERS
  chapters from `CHNN_HOST_INDEX` + `CHNN_EVENT_GROUP`, so declaring the constants is what enrols a
  chapter; it refuses a host slot with no named event group, and refuses two chapters claiming one
  slot. The general rule: **when a guard enumerates its subjects, derive the list from the data the
  subjects are already made of — never restate it.** A hand-maintained list of what to check is a
  second source of truth that silently drifts the moment someone adds the thing you were guarding.
- **The host-slot facts were already data; the refactor was not what made them lintable**
  (2026-08-06, #138). Worth recording because the epic's re-scope argued the opposite and was
  wrong: `CHNN_HOST_INDEX` / `CHNN_EVENT_GROUP` / `CHNN_GOAL_DONOR` have been module constants all
  along, so the lint never needed config-driven `inject_chapter(N)` to exist. Config-driven hosting
  is still worth doing — 2,626 LOC across five per-chapter functions with a 15-helper shared spine —
  but it is a *readability and repetition* argument, not a prerequisite for validation. Check what a
  refactor actually unblocks before sequencing work behind it.
  **What the repetition argument is actually worth, measured:** of 2,209 LOC in
  `inject_ch01`–`ch04`, just **123 (6%)** is the host skeleton a descriptor would collapse — roughly
  30 lines a chapter, and already helper calls. The other 94% is per-chapter rosters, event scripts
  and scenes, which no descriptor absorbs. So the idea is **not scheduled** and should not be
  re-opened without new evidence; it was never *rejected on principle*, it just does not pay for
  itself at this size. The one real cleanup inside it, deliberately not filed as its own issue:
  ch03's bespoke `_inject_ch03_tile_changes` should migrate onto ch04's generic
  `_inject_tile_changes` — a ~20-line change that a future chapter's tile-change work sits next to
  anyway. Byte-identical baseline to diff against if you do it:
  `42cd82360be3c186c60f9366d57c7608d3d83548`.
- **A proc's identity is its script ADDRESS, never its `PROC_NAME` string** (2026-08-06, #236).
  Freeze reports named a proc from the string pointer at proc+0x10, and that string is not an
  identity: the decomp gives `gProcScr_E_FACE` and `gProcScr_E_FACE_ExtraFrame` the same
  `PROC_NAME("E_FACE")`, and reuses `"bmenu"` and `"E_config"` three times each. Live capture was
  worse still — the field goes stale, so the proc actually running `gProcScr_Talk` printed as
  `E_FACE`, `ProcScr_StdEventEngine` printed as `MAPTASK`, and `gProcScr_TalkSkipListener` printed
  as `ekrBattleEnding`. `gen_symbols.py` now emits `procscr.lua` (952 script addresses → their
  exact symbols) and `symbols.json` (every ROM code symbol, for `inspect_state.py` to name idle
  callbacks). **Resolution is exact-match only, and an unmatched address prints
  `unknown@0x…`** — silence beats a confident wrong name, which is what cost #232 its last failure.
- **An unclassified `transition` must say what it rejected** (2026-08-06, #236). `classify()` is
  an ordered rule table, and `explain()` runs the same rules to return the verdict *plus* every
  rule considered and the predicate that failed. Five of #232's six defects were input waits
  nothing had a name for; each read as a passive transition and cost a full build-and-run cycle
  to identify. The classification is now the cheap half: `INSPECT.watch` arms only on an
  *unclassified* transition holding a byte-identical proc pool, and dumps the snapshot the moment
  the stall is provable.
- **A loop budget must not be the thing that decides failure** (2026-08-06, #232/#236). `ch01`
  stayed open for three sessions on a diagnosis that turned out to be wrong — "no page wait is
  ever classified as `dialogue_wait`, so nothing advances it". The inspector disproved it in one
  run: page waits were classified and advanced **74 times**, all passing, and the flow was still
  advancing 263 frames before the old 12000-step cap expired. A cap that fires mid-scene reports
  a timeout that names nothing, and a budget-bounded loop exits at the same frame whatever is on
  screen — so the number looks like evidence and is not. Caps are now sized far above any real
  scene (`TUNE.bootSteps`), and `INSPECT.watch` is the failure oracle.
- **A Yes/No prompt inside a scene is its own input state** (2026-08-06, #232). With the above in
  place the real `ch01` blocker took one run to name: `gProcScr_YesNoChoice` in
  `YesNoChoice_Loop_KeyHandler` — lord select's "Will \<lead\> lead the party?". It runs *inside* a
  live event scene, so the `std_event` passive rule swallowed it as a transition and nothing ever
  answered. It is classified as `yes_no_choice` and ordered above the passive rules;
  `currentChoice` (s16 @ +0x2A, `TALK_CHOICE_YES`=1/`NO`=2) decides which answer carries `A`, and
  the *scenario* chooses the answer — the controller only says what is legal.
- **Comments inside a YAML folded scalar are CONTENT, not comments** (2026-08-02, #214). Authoring
  a chapter's `visit_text: >` with `#` lines indented underneath silently folded them into the
  string, and the chapter YAML then failed to load for every test that reads it. Comments belong
  ABOVE the key. Cheap to hit, instant to diagnose once seen — the parse error names the file, not
  the line.
- **`tools/check.py` is ~22s on a clean tree and ~4 minutes on a freshly BUILT one** (measured
  2026-08-02). `check_tests_pass` runs each `tools/test_*.py` as its own process, and the heavy
  ones re-read the injected decomp. The pre-commit hook runs the same thing, so a commit right
  after `make` can appear to hang. **Restore the injected decomp files first** —
  `git -C fireemblem8u restore src/data/chapter_settings.json data/data_8B363C.s`. Not a
  regression; just know it. (`test_winter_forest_backfill` no longer needs that restore to PASS:
  since 2026-08-03 / #221 it reads its vanilla inputs through `git show HEAD:`, the same doctrine
  as the event-data rule above. The remaining decomp-reading tests still read the working tree,
  so the timing claim stands.)

- **A host slot's index stops tracking the chapter number at 5, and a hosted chapter must name the
  `ChapterEventGroup` it fills** (2026-07-31, ch04 #24). FE8 inserts chapter 5X at **slot 5**, so
  `chapter_settings.json` slot 5 ships with `mapEventDataId` → `Ch5XEvents` while a chapter hosted
  there writes its events into the `Ch5*` symbols (`Ch5EventData`). Slots 1–4 are correct only by
  the coincidence that index == chapter number there. `_retarget_host_chapter` therefore takes a
  mandatory `event_group` and repoints `mapEventDataId` itself, so map and events stay ONE decision;
  `HostChapterEventGroup` in `tools/test_build_campaign.py` pins both the trap and the repoint.
  **Why this one is worth a durable entry: it fails silently and totally.** Retargeting the map ids
  alone makes the chapter *look* injected — correct `gBmMapSize`, correct tileset, correct goal
  banner — while the slot runs the host's roster and scripts underneath. The observable symptoms all
  point away from the cause: foreign units on coordinates off your footprint, a party that never
  deploys, no PREP, and a cursor initialised onto an undeployed unit's `x=255` sentinel, which
  presents as the *playtest harness* wedging. Diagnose it by reading `gBmMapSize` and the live unit
  arrays in-engine (data, not screenshots — the map is genuinely yours, so pixels mislead) and by
  resolving the slot's `mapEventDataId` through `gChapterDataAssetTable`.

- **A scripted `MOVE` to good terrain still hangs the chapter if the unit cannot WALK there —
  connectivity is the test, not the tile.** `MOVE(...)` + `ENUN` waits on a path; when none
  exists the event engine never returns and the chapter freezes with the unit standing where it
  loaded. ch04's white moose fled to `(14, 0)`, the map's NE corner: `TERRAIN_PLAINS`, cost 1,
  entirely reasonable-looking — and sealed off from its own clearing by a wall of
  `TERRAIN_CLIFF`. `make` was green, the map was correct, and the beat wedged the game the first
  time a party unit triggered it. `assert_scripted_move_reachable` now fails the BUILD on it: it
  flood-fills the map's terrain (resolved through the layout's own tileset table, read from the
  **campaign** asset — the decomp's copy is the untracked artifact injection writes) with the
  unit's class movement-cost row, and names the nearest legal destination in the error. Two traps
  live inside that check: the cost rows in `data_terrains.c` are **designated initializers keyed
  by terrain NAME**, so reading them positionally yields a plausible-looking table where
  everything is walkable (the names carry digits — `TERRAIN_C_ROOM_09`, `TERRAIN_TILE_2E` — that a
  naive number scan eats as costs); and `data_terrains.c` is a PATCHED file, so it must be read
  at HEAD through `vanilla_decomp_text`. Covered by `ch04moose` (in-engine, both halves) and two
  unit tests — one pinning today's tile, one pinning that the OLD corner is walkable-but-cut-off,
  because "is it good terrain" is exactly the check that passes while the game hangs.
  _Recorded: 2026-07-31 (ch04 #24 Stage 4)._

- **A reachable endpoint does not define a staged escape — route and camera framing are authored
  scene data.** A single `MOVE` from the white-moose clearing to `(14,14)` was technically reachable,
  so FE8 legitimately chose its shortest path straight south; `CAMERA2(14,14)` then made `REMA`
  restore the camera over the map boundary, exposing the engine's gray out-of-map tile grid behind
  RBG's portrait. The intended beat is now explicit in the chapter YAML: `flee_route` crosses the east
  bridge at `(9,7)`, reaches the far bank at `(9,8)`, and exits southeast at `(14,14)`. The injector
  emits that as a vanilla REDA queue plus `MOVE_DEFINED`, preserving continuous normal-unit walking
  between authored waypoints, and validates every waypoint as reachable. The 15-tile-wide map exactly
  fills the GBA viewport, so centering `CAMERA2` on the moose at x=11 scrolls past the real right edge
  and renders wrapped map memory. The YAML therefore authors `camera_at: [7,4]`, the map-width center
  that pins camera x=0 while framing the clearing and bridge. Script tests pin the camera, queue, bridge
  tiles, and endpoint; the motion GIF remains the
  visual acceptance gate because reachability cannot judge composition.
  _Recorded: 2026-08-03 (Nicolas + Codex, ch04 #24 / PR #219 visual review)._

- **An `AREA` event is not "a player unit steps here" — it is "whichever unit last acted is
  standing here," and a bare abort spends the one-shot forever.** FE8 polls the Misc event list at
  the end of EVERY unit's action — `playerphase.c` and `cp_perform.c` (the AI mover) both
  `PROC_CALL_2(RunPotentialWaitEvents)` — and `EvCheck0B_AREA` (`eventinfo.c`) tests
  `gActiveUnit`'s position with **no faction check**. So an AREA drawn over ground the enemy also
  walks fires on the ENEMY phase: ch04's moose-sighting rect `(8,2)-(14,7)` is exactly where the
  turn-1 monster line stands, and a Revenant ending its move there played RBG's "After it!" to an
  empty clearing on turn 1. The second half of the trap is `StartEventFromInfo`, which
  `SetFlag(info->flag)`s the AREA's one-shot **before** it `CallEvent`s the script — so guarding
  with an early `ENDA` still burns the beat permanently. Vanilla ships the whole answer:
  `SVAL(EVT_SLOT_2, FACTION_ID_BLUE)` + `CALL(EventScr_UnTriggerIfNotFaction)` (`eventcall.h`;
  ch13b/ch15b use it verbatim), which clears the *triggered* event id — re-arming the AREA — and
  `ENDB`s the whole event rather than just its own frame. Put the guard FIRST, before any `LOAD1`
  or camera seize. **How it was caught matters more than the fix: by filming it**
  (`recordch04reveal`), not by reading the script — the wiring is correct FE8 in isolation, and
  `smoke_ch04` stayed green throughout, because a beat firing at the wrong moment is not a
  soft-lock. _Recorded: 2026-07-31 (ch04 #24 Stage 4)._

- **A chapter's message text lives in TWO decomp files, in TWO channels — a partial scan reads as
  proof that vanilla lacks a beat.** `src/events/<ch>-eventscript.h` holds the scenes, mixing
  `TEXTSHOW` (on-map, units staged by `LOAD1`, bubbles wrap at 29 chars) with
  `Text_BG(BG_*, id)` (a still backdrop, ~42 chars) — and vanilla uses the backdrop for scenes set
  ELSEWHERE, so the channel also tells you where a scene happens. Separately,
  `src/data_battlequotes.c` holds boss taunts, boss death quotes and chapter-specific unit death
  quotes, which appear in **no** eventscript. Both traps fired on ch05: `vanilla_scene.py` matched
  `TEXTSHOW` only and reported Ch5's 11-message opening as 8, hiding the exact two backdrop scenes
  our 9BC/9BD are modelled on; and a caveat was written claiming `0x9C6`/`0x9C7`/`0x9C8` "appear
  nowhere in the decomp" when all three are battle-quote entries — `0x9C6` being the escort's death
  quote, which then turned out to be a slot we owed Basil. Grep **both** files before concluding an
  id is unused, and prefer the tool (now channel-aware, guarded by `tools/test_vanilla_scene.py`).
  _Recorded: 2026-07-29 (ch05 dialogue pass)._

- **A `git` subprocess run inside a git hook resolves against the OUTER repo unless you strip `GIT_*`.**
  Git exports `GIT_DIR`/`GIT_INDEX_FILE`/`GIT_WORK_TREE` while a hook runs (pre-commit drift → `check.py`
  → the `test_*.py` suite). Any tool or **test fixture** that then shells out to `git` — `git -C <dir> …`,
  a throwaway `git init`/`commit` in a tempdir, `_vanilla_decomp_text`'s `git show HEAD:` — has its
  `-C`/cwd **overridden** by the ambient `GIT_DIR` and silently operates on the real repo. On 2026-07-21
  this flipped `core.bare=true` on the live repo and wrote a corrupt commit before it was caught. **Always
  pass a sanitized env** — `{k: v for k, v in os.environ.items() if not k.startswith('GIT_')}` — to any
  `git` subprocess that must target a specific repo, and add `-c core.hooksPath=/dev/null` to fixture
  commits so they can't re-enter the outer hook. Fixed in `_vanilla_decomp_text` + `test_map_tileset.py`.
  **It recurred on 2026-07-30** in `test_check_handoff.py` — a new fixture, written the obvious way
  (`subprocess.run(['git', ...], cwd=repo)`), which under pre-commit ran its throwaway `init`/`config`/
  `add`/`commit` against the live repo: `core.bare` flipped to `true`, `user.name`/`user.email` were
  overwritten with the fixture's `t`/`t@t`, and `HANDOFF.md` was left staged mid-commit (surfacing as a
  bogus HANDOFF-guard violation, which is what led back to it). `cwd=` is NOT a defence — the ambient
  `GIT_DIR` beats it. So: **any new test that shells out to `git` must go through a sanitized-env helper**
  — target the repo with `-C`, pass `env=` stripped of `GIT_*`, and add `-c core.hooksPath=/dev/null`. Verify
  it by running the fixture with `GIT_DIR` pointed at a decoy repo and asserting the decoy is untouched;
  the pre-fix helper corrupts the decoy, the fixed one doesn't.
- **Per-unit descale recipe is recorded in the unit YAML comment** (data-is-the-doc) — read it before
  regenerating; don't guess flags. Swapping ONE pose still requires re-descaling the **whole 3-frame set
  together** (shared palette recompute shifts the other two — that's correct, not a bug).
- **Battle-anim frames are a hard 3** (ready/windup/peak; script refs frames 0/1/2; `build_battle_anim`
  rejects any other count). The "march" is faked by the per-donor sound/shake cadence + a single engine
  OAM lunge (`MELEE_LUNGE_DX` −40 on peak), not extra art frames.
- **`make_gif.py` writes to `docs/demo/` on the active feature branch.** Show that committed GIF
  in the GitHub PR; remove it before merge once the review is complete, unless a live document
  deliberately links to it as durable evidence. Do not accumulate local review archives.
- **Event BGs: vendored winter CGs → NEW `gConvoBackgroundData` slots, additive** (`bg_to_fe8.py` →
  `inject_backgrounds`). **Color index 0 is TRANSPARENT** — using it for a real colour → black holes;
  `bg_to_fe8.py` reserves it. Slots are appended past `BG_RANDOM` at **0x38+**, so they don't run out.
  Verify event BGs **in-engine** (a flat preview won't show the holes).
- **Cutscene faces: `Text()` self-`REMA`s (clears ALL portraits); to hold one speaker while another
  exits, author raw + a per-podium `[ClearFace]`.** `Text(msg)` = `TEXTSTART TEXTSHOW TEXTEND REMA`
  (`Convo_Helpers.h`), so every beat fades out every face at its end. For a "one speaker leaves mid-scene,
  a co-speaker holds through a pause" beat (ch03 opening: Pinky scouts, RBG waits at the mine mouth):
  emit **raw `TEXTSTART/TEXTSHOW/TEXTEND` (no `REMA`)** and append **`[OpenX][ClearFace]`** to that beat's
  message body — `[ClearFace]` fades only `faces[activeFaceSlot]` (`scene.c`), leaving the others up.
  The next beat's `Text()` opens with `TEXTSTART`; because `Event1A_TEXTSTART` skips its face-clear when
  the sub-type **equals the still-active** type (`subcode == proc->activeTextType`), the held face carries
  through and its re-`[LoadFace]` early-returns on the occupied slot (`TalkLoadFace`, no reflicker). Hook:
  `_script_to_message(trailing=...)` / `_emit_scene_beats(trailings=[...])`. There is **no event-level
  single-face-remove command** — only `REMA` (all) and `FACE_SHOW`/`EvtDisplayFace` (add one); the
  per-face *fade-out* is a message text-code, not an event opcode. Verify in-engine (`recordch03open`).
- **Location-card nameplate caps at ~96px** — >~12–14 chars clip silently. Keep `location_card:` short.
- **Vanilla character-slot display names leak** unless the injector overrides it:
  `set_message_body(vanilla_name_text_id(slot), name_message_body(display_name(unit)))`. Give units a short `fe_name` (≤12).
- **Clear-bot can't fully clear a chapter yet (#60).** Helpers that must REACH a later chapter use directed
  seizes / frail+teleport (`reachCh02Map`, `clear_ch02`), not fair-play clears.
- **DefeatBoss fires from the FLAGGED defeat quote, not `CA_BOSS`** (`eventinfo.c`: `SetPidDefeatedFlag`
  runs for ANY unit whose pid matches a `gDefeatTalkList` entry on death — no boss-attribute gate). So a
  boss on a **raw pid with no `gCharacterData` entry** (ch03's grell = `0xb7`, chosen to avoid leaking a
  vanilla boss's name/face/quote) still wins the map via a head-of-list quote keyed to `(pid, CHAPTER_L_N,
  EVFLAG_DEFEAT_BOSS)`. **Trade-off:** with no `CA_BOSS` it shows **no boss HP gauge** and the generic
  clear-bot/`findBoss()` (reads `CA_BOSS`) can't target it — so a per-boss load-test must reach it by
  pid+tile (`ch03win`: teleport the grell to the lord and strike), and a future `clear_chNN` needs either a
  `CA_BOSS` character entry for the boss or a pid-targeted bot. Verified in-engine (`ch03win`, 2026-07-07).
- **A mid-map death-triggered cutscene (miniboss) = the same silent-flagged-quote idiom + a tmp-flag `AFEV`,
  NOT `DefeatBoss`.** ch03's RBG-execution beat fires when the *Icewind Brute* dies (not the boss). Recipe
  (mirror of the win, keyed to a temporary flag so the chapter continues): (1) give the miniboss a **unique
  raw pid** distinct from the shared generic AND the boss (ch03 Brute = `0xb6`, sibling of the grell's `0xb7`;
  `0xB0–0xB9` are unnamed → no name/face leak), so its flagged quote keys the trigger to it alone — reusing the
  generic `0xaa` would fire on *any* trash mob's death; (2) a **silent** (`.msg = 0`) `gDefeatTalkList` entry
  `(pid, CHAPTER_L_N, EVFLAG_TMP(a))` — `SetPidDefeatedFlag` sets the flag with no portrait to render;
  (3) a Misc `AFEV(EVFLAG_TMP(b), midmap_script, EVFLAG_TMP(a))` — `EvCheck01_AFEV` runs the script when flag
  `a` is set and marks itself done with the **ent-flag `b`** (set AFTER the script's `ENDA`), so it fires
  **exactly once** (an ent-flag of `0` would re-fire every turn once `a` is set). The vanilla ch1 idiom
  (`AFEV(EVFLAG_TMP(7), …, EVFLAG_DEFEAT_BOSS)`). Data-driven via a per-enemy `is_miniboss:` YAML flag +
  `build_campaign.midmap_minibosses`/`flag_defeat_quote`/`midmap_afev`. Verified in-engine (`ch03midmap`:
  kill the Brute → `EVFLAG_TMP(10)` → the AFEV runs the 3 on-map beats → `EVFLAG_TMP(11)` → chapter continues).
- **Don't reuse a playtest checkpoint across an injection/build change** — only across pure graphics-byte
  swaps. Checkpoints are ROM-hash-stamped in `tools/playtest/states/` (gitignored); delete `.ss`/`.romhash`
  to force a rebuild. (A battle-anim frame change IS a build change → re-record from a fresh ROM.)
- **Additive, never global** (content art): clone classes / new terrain/banim/BG slots; never edit a shared
  vanilla one in place.
- **Engine hooks live in `tools/inject/engine_hooks.py`** (guarded by `check_engine_guards_present`).
- **Turning fog OFF takes TWO steps: the vision range AND a map refresh** (2026-08-01, #204). Fog
  does two independent things, and zeroing `gPlaySt.chapterVisionRange` only undoes one of them.
  `bmtarget.c` gates target-picking on the vision range, so zeroing it does re-open targeting — but
  `RefreshUnitsOnBmMap` (`bmmap.c`) is what writes units into the tile→unit grid `gBmMapUnit`, and it
  **skips a red standing in fog entirely**, filing it under `gBmMapHidden` with `US_BIT9` instead.
  Nothing recomputes that grid on a memory poke, so until the engine's next `RefreshEntityBmMaps`
  the enemies are simply *not on the map*: `gBmMapUnit` holds none of them no matter what the unit
  array says. Any refresh fixes it — one unit's action (`MapMain_ResumeFromAction`) or a phase change
  is enough, and the refresh also refills `gBmMapFog` itself (`BmMapFill(gBmMapFog, !visionRange)`),
  so the fog map never needs poking. **Why this is worth a durable entry: every symptom points at the
  wrong layer.** `clear_ch04` sat at 10 live enemies for 16 turns with zero kills; the enemies were
  visibly on screen, the unit array listed all ten with correct coordinates, and the vision range
  read 0 — so fog looked handled. What actually happened is that the clear-bot teleported "adjacent"
  to foes the engine could not see, got a command menu with **no Attack row**, and its blind row-0
  press opened **Item** and Used a Goodberry at full HP, forever. The lesson generalises past fog:
  **the grid, not the unit array, is what the engine acts on** — so a bot must decide from
  `gBmMapUnit` (`clearbot.gridHostileInReach`) and never assume command-menu row 0 is Attack.
- **New decomp patch target → add it to `PATCHED_DECOMP_FILES`**, or the build is non-idempotent.
- **Vanilla decomp reads go through `build_campaign.vanilla_decomp_text()` (HEAD)**, never the worktree.
- **`make`-green can't prove apply timing OR rendering** — `tools/playtest/` is the dynamic arbiter. Needs a
  built ROM + `lua`; `run.sh` regenerates `symbols.lua` after a rebuild.
- **CI unit tests run in the `build` job, not the lightweight `checks` job** (need submodule + numpy/PIL).
  mGBA playtest *scenarios* are NOT CI-gated; the `test_*.lua` cores ARE, via `make test`.
- **Distribution is the private pre-patched `.gba`** (decomp build is non-matching vs retail).
- **Save layout must stay stable for testers** (#59): `check_save_layout_stable` reds on layout drift.
- **Writing any dialogue → invoke `dialogue-pass` first.** Story bodies are `make`-regenerated; gate text
  changes with `python3 tools/verify_text.py`. Card/name text is ASCII-folded in `name_message_body`.
- **`msg-id` vetting is treacherous** — `data_battlequotes.c` stores ids 4-digit zero-padded; vet in `0x0XXX` form.
- **Chapter hosting** (model on `inject_ch01`/`inject_ch02`): each chapter rides the *next* vanilla slot,
  chained via `MNC2(<next slot>)`; new snow chapters set `battleTileSet` `0` (open) or `0x15` (rough).
- **Vanilla-only (monster/exotic) weapons belong in `difficulty.py`**, not `WEAPON_ITEM_ENUM`.
- **Never a bare `make` for a shippable ROM** — `tools/build.sh` applies the decomp shebang fix; a bare
  `make` dies on the gfx tools on macOS (`decisions.md` §Distribution).
- **The FE Wiki is a CROSS-REFERENCE, never an authority** (2026-08-07). The decomp stays the source
  of truth for every FE8 claim (`CLAUDE.md`), but the wiki's per-chapter pages are worth a read when
  mining a vanilla chapter, because they state things in a form that *prompts the question* the
  decomp answers. Concretely: it says "village to the southeast → Dragonshield". The decomp says
  `SVAL(EVT_SLOT_3, 0xe)` inside one of four separately-named scripts, and nothing in it invites you
  to ask whether our pairing matches. That is exactly how ch05's swapped reliquary gifts were caught
  — **wiki raised it, decomp settled it**, which is the only order that is ever correct.
  **Fetching it:** the rendered page is blocked (403 to curl, 402 to WebFetch). Use the MediaWiki API:
  ```sh
  curl -sL -A "Mozilla/5.0" "https://fireemblem.fandom.com/api.php?action=parse\
&page=The%20Empire%27s%20Reach&prop=wikitext&format=json&formatversion=2"
  ```

### A retile inherits vanilla's GIFT PLACEMENT, not just its terrain (2026-08-07, #25)

**Which gift sits on which tile is vanilla's decision**, gated by
`assert_village_gifts_match_vanilla` for any chapter whose `map:` names a `vanilla_layout:`.
Deliberate divergence is one key on the village — `vanilla_gift_divergence: <why>` — and the error
message names it. **The default is inheritance because exceptions are rarer than re-deriving four
placements every time** (Nicolas, 2026-08-07); a from-scratch canvas is skipped, and so is a site
vanilla does not have (one we added rather than moved).

It earns a gate because nothing else can see it. Swap two gifts and the item set, the economy total
and the parity verdict are all unchanged — `difficulty.py` counts the SET, not the tiles — so
`make difficulty` still reads PARITY while the chapter's risk/reward is inverted. ch05 shipped that
way: `(12,19)` is the south-east site and the turn-2 eruption pair spawns at `(14,16)/(14,15)` beside
it, so vanilla puts its richest gift (Dracoshield, 8000g) on the site the first raiders reach and its
cheapest (Torch, 500g) at `(5,1)`, behind the whole enemy line. We had them swapped, paying the most
for the safest errand in a chapter whose structure *is* the race for the reward-sites.

Sibling of `validate_terrain_matches_vanilla` (a retile inherits vanilla's terrain), one layer up:
the rewards standing on that terrain.

### Generated art is CONVERTED by the injector, never left for make (2026-08-07, #245)

**GNU Make 3.81 — what Apple ships and what this repo builds with — drops the incbin
dependency**, so an injector must run the `gbagfx` conversions itself and drop the consuming
`.o`. It must not delete the intermediates and trust make to re-derive them.

The chain that fails: `data/data_chap_title.o` reaches its `.4bpp.lz` files through
`$$(data_dep)`, a `$(shell scaninc …)` target-specific variable resolved by `.SECONDEXPANSION`,
which 3.81 does not handle. Verified directly — with the `.lz` deleted, `make -n fireemblem8.gba`
plans **no** rule that rebuilds it.

Two consequences, and the quiet one is worse:

1. When `data_chap_title.o` needs reassembling, the build dies on `Error: file not found:
   graphics/chap_title/chap_title_N.4bpp.lz`.
2. When it does not — the common case, since its `.s` never changes — **the build succeeds and
   the ROM silently keeps the previous card.** A retitled chapter simply never lands.

This is the real root cause of **#245**, which was filed as "the `TESTCH` build race". It is not a
race and it is not `TESTCH`'s: it looked intermittent only because whether it fires depends on
whether the file survived an earlier build. `_write_chapter_title_card` now converts and drops the
`.o`, and the gate went from a standing `BLOCKED` to 15/15.

**The general rule: if an injector generates art, it owns the conversion.** Deleting an
intermediate is not a way to ask make for anything on this toolchain.

Both title-card sites are fixed — `inject_prologue` had an inline copy of
`_write_chapter_title_card` carrying the same bug, and now calls the helper. **Three more sites
have the same delete-and-hope shape and are NOT verified**, all in the montage path, which is why
they are named here rather than quietly assumed fine: the opening subtitle cards
(`.feimg2`/`.fetsa2`), `MontageMural.4bpp{,.lz}`, and the drawn world-map `.lz` copies. They may be
harmless if their consuming `.s` changes on every build (which would force the reassemble this bug
needs) — that is exactly what someone should check before trusting them.

### Vanilla prose is a legitimate PLACEHOLDER; vanilla wiring is not (2026-08-07, #25)

**A chapter is wired end-to-end first, and only its PROSE waits for the dialogue pass** (Nicolas).
ch05's four reliquary visits point at vanilla Ch5's own message ids (`0x9CD`–`0x9D0`) and we never
*write* them, so the ROM keeps vanilla's text, the ids stay unclaimed in
`HOSTED_CHAPTER_MESSAGE_IDS`, and the dialogue pass later writes our body **at the same id** — one
line per site, not a rewire. ch05's authored dialogue skips that range exactly (`0x9BE`–`0x9CC`,
then `0x9D5`), so nothing collides.

What is *not* placeholder is everything else, and that is the point: the `SVAL(EVT_SLOT_3, <item>)`
+ `GIVEITEMTO` half is the real wiring, already gated by `assert_village_gifts_match_vanilla`, so
the rewards are obtainable and correct now rather than twice. **Shops are not placeholders at all**
— `Armory`/`Vendor` take their stock directly and run no script and show no text, so listing the
tile finishes them.

The alternative — leaving the `Location` list empty until the prose lands — is what shipped ch04's
unreachable Iron Axe and left ch05 with four villages, an armory and a vendor sitting on intact
tiles that nothing pointed at. A finished-looking map with unobtainable rewards is the failure
mode; borrowed prose is not.

### Campaign-owned EVENT SCRIPTS, same as tables (2026-08-07, #25)

`declare_event_script` is the script twin of `declare_unit_table`, for the same reason: a host slot
frees only the scripts its stripped cutscenes stop referencing (slot 6 leaves five; ch05 needs
three waves plus one per village), and `MS_Ch05VisitSouth` says what it runs where
`EventScr_089F2AE4` says nothing.

**It APPENDS, so it must run AFTER the injector's block-replacement pass**, which rewrites the same
file wholesale from a copy read earlier. Declaring first silently discards every appended script —
the Location list still names them and the externs still exist, so the only symptom is a link error
pointing at the reference rather than at the loss. `assert_event_scripts_defined` pins the ordering.

### Campaign rosters live in campaign-named symbols (2026-08-07, #25)

**A chapter's unit tables are ours and are named `MS_ChNN*`** (`declare_unit_table`), appended to
`events_udefs.c` with an extern in `eventcall.h` — both already restored from HEAD each build. We no
longer block-overwrite whichever vanilla table the host slot's stripped cutscenes left unreferenced.

Two reasons, and the second is what forced it:

1. **The name lied.** ch04's moose rides a symbol our own source calls "dead Ch5 unit table". Reading
   an injector meant carrying two unrelated offsets at once: *ours* (chapter N hosts on slot N+1,
   because the prologue occupies a real, unnumbered slot — not renumberable, and invisible in play
   since the prep header reads `prepScreenNumber`) and *FE8's* (it inserted Ch5x at slot 5, so from
   slot 6 on the slot index and the vanilla symbol name disagree **in the base game**: slot 6 ships
   `Ch5EventData`, slot 7 ships `Ch6Events`). Both offsets are now stated once, in the `CH05_*`
   constant block, and nowhere else.
2. **Squatting rations you to what the slot happens to free.** Slot 5 freed seven tables; slot 6
   frees three, and ch05 needs seven. The alternative was borrowing Ch6's world-map *encounter*
   rosters — storage from a system we merely hope never runs.

Only the event-list symbols stay vanilla-named: `chapter_settings.json` resolves the
`ChapterEventGroup` from them, so they are structural. They are named in one per-chapter dict.

### Owning the symbol means owning the POINTER (2026-08-07, #25)

**Declaring a roster table does not wire it — the engine reads the roster through the
`ChapterEventGroup`.** `point_event_group_at` repoints `playerUnitsInNormal`/`InHard`, and
`assert_event_group_roster` fails the build if it was not done.

This shipped broken for one build and **had no symptom**: ch05 declared `MS_Ch05DeployCap`, nothing
pointed at it, so slot 6 kept deploying `UnitDef_Event_Ch6Ally` — vanilla Ch6's start tiles, on a map
whose geometry is vanilla Ch5's. The party appeared, PREP ran, the map drew, the load-test PASSed,
and four units stood **inside walls**. It is the ally-table twin of the host-slot/event-group
mis-target in `docs/adding-a-chapter.md` step 4, and it is invisible to every other gate.

ch03/ch04 could not hit it, because overwriting the table the group already points at cannot break
the link. Adopting campaign-owned symbols is what created the hazard, so it ships with its guard.

**Corollary — placement is verified from unit POSITIONS, never from a frame** (`INSPECT.units`, added
for this). A map sprite is drawn taller than its tile and offset upward, so a unit reads a row high,
and the camera row has to be recovered before any pixel can be assigned a coordinate at all. Nicolas
caught this one off a screenshot; confirming it took a memory dump.

### A `CHAPTER_L_*` label is resolved by VALUE, never spelled from a number (2026-08-07, #25)

`CHAPTER_L_5 = 0x06` and `CHAPTER_L_6 = 0x07` — the Ch5x insert again. Slot 6 is `CHAPTER_L_5`.
For slots 1–4 the name matches the number, which is why four injectors hardcoded the literal and were
right by accident. `chapter_label_constant(slot)` reads chapters.h. Guessing fails **silently**: a
`gDefeatTalkList` entry keyed to the wrong `.chapter` never matches, so the boss dies, no flag is
set, `DefeatBoss` never fires, and the chapter cannot be won, with nothing in the build to say why.

### A dead message id is proven by USE, not by an empty body (2026-08-08, #25)

Two death-quote ids were owed (Basil, Sahnar) and `PC_DEATH_QUOTE_MSGS` carried a TODO to
auto-allocate them "from a free pool". There is no such pool, and the two obvious audits both give
the wrong answer:

- **"The body is empty"** finds nothing. Every id in FE8's range has vanilla text. A reusable slot
  is one whose *text still exists* but that no code reaches — Lupin's `0x974` is the vanilla line
  "Place the cursor on Vanessa", alive in `texts.txt` and referenced by nothing.
- **"The id appears nowhere in the sources"** finds nothing either, for two separate reasons:
  `include/constants/msg.h` `#define`s **every** id (a declaration, not a use), and a bare-hex
  search for `0x974` collides with unrelated addresses and offsets.

The criterion that works is the one Lupin's comment already stated: no `TEXTSHOW(id)`, `.msg`, or
`.msgId` reaching it, searched over the decomp at `HEAD` with `msg.h` excluded and bare hex ignored.
Run it against `0x974` first — a method that calls Lupin's shipped slot "used" is a broken method.
**Keep the ids explicit in the table rather than auto-allocating**: a floating id would move
`verify_text` baselines under us and break the id-claiming discipline `HOSTED_CHAPTER_MESSAGE_IDS`
depends on. The TODO's premise was wrong; what was missing was the audit, not the automation.

### A host block is not the whole id budget — sweep the neighbourhood (2026-08-13, #25)

Counted while moving the Basil→Sahnar Talk off vanilla's `0x9CC` into ch05's own block, because
the placeholder pattern above has a bill and it comes due here.

ch05 hosts on slot 6, so its block is vanilla **Ch6's** `0x9E4`–`0x9F5` — 18 ids. Seven are spent
(the eruption warning, Ravisin's death quote, the two arena tutorial boxes, the two goal strings,
the Talk), leaving **eleven**. Eleven scenes are still owed: the opening's seven, both endings,
Basil's chapter-specific death quote, and Ravisin's battle taunt — which is wired *nowhere*
(`gBattleTalkList` carries a ch01 row for Izobai and none for her). Read off the block alone that
is exactly zero slack, and the `no_lupin_fallback:` branches would have nowhere to go.

**The block is not the budget.** Sweeping `0x9C6`–`0x9E3` against the post-injection tree by the
`USE` criterion (`decisions.md` → "A dead message id is proven by USE") finds **six** more free
ids: `0x9C9` `0x9CA` `0x9CB` `0x9CC` `0x9D1` `0x9D2`. Vanilla Ch5's two endings, its coda and its
Talk are reachable only from `ch5-eventscript.h`, which `inject_ch04` rewrites — the same shape
that made `0x9CD`–`0x9D0` safe for the reliquary lines. **Seventeen ids against sixteen owed.**

Two things the sweep has to be run correctly to see, both easy to get wrong:

- **Sweep the POST-INJECTION tree, not `HEAD`.** At `HEAD` all four of `0x9C9`–`0x9CC` are live in
  `ch5-eventscript.h`; after `inject_ch04` rewrites that file, none of them is. The tree that
  ships is the one that answers the question.
- **Validate the sweep against a known-LIVE id before trusting a "free" verdict.** A regex that
  misses `TEXTSHOW`/`Text_BG`/`.msg` in any of their spellings reports everything free. Run it
  against `0x9E4` and `0x9CD` first and require them to come back USED.

`0x9C6`/`0x9C7`/`0x9C8` come back **USED** and that is correct — they are live rows in
`data_battlequotes.c` keyed to `CHAPTER_L_5`, ch04's host slot. Do not talk yourself past them on
the grounds that ch04 fields neither Natasha nor Saar: that is an argument about our roster, which
can change, not about our wiring.

**A `no_lupin_fallback:` costs ONE extra id, not four.** The branch mechanism is already built and
ch04 uses it: `variant_beat()` splices the substitute boxes over the locked beat, the whole variant
scene is written to a **second** message id, and `branch_on_flag()` picks between the two at
runtime — so a branched scene is 2 ids rather than 1. Splitting a scene into prefix/arm/arm/suffix
around the differing box would cost four, and is the wrong instinct: duplicating the text is free,
ids are what is scarce. Note `variant_beat` reads `boxes:`/`replaces:` as **lists** while ch05's
blocks are authored with singular `box:`/`replaces:` — normalize the YAML, do not write a
second mechanism.

⚠️ **The "ids are what is scarce" half of that is retired** (2026-08-15, and again on the ch05
endings 2026-08-19). `gMsgTable[]` self-sizes, and a split scene costs SEAMS — see "A conditional
block inside a scene is a WHOLE second copy" below. The 2-ids-per-branched-scene shape is still
right; the reason given for it was not.

### A cutscene's CHANNEL is inherited from the twin, not chosen (2026-08-13, #25)

ch05's scene table left "on-map bubble vs `Text_BG`" as a per-scene decision, and the id-budget
work priced it as an open question. It was never open: `EventScr_Ch5_BeginningScene` at HEAD
answers it for all seven of ch05's opening scenes, because ours are its scenes one for one.

| vanilla | who | how it is played |
|---|---|---|
| `0x9BA` | Joshua's cold open | `Text_BG(BG_SERAFEW_VILLAGE)` |
| `0x9BB` | the Joshua/Natasha meet-cute | `SetBackground(BG_SERAFEW_VILLAGE)` + bare `TEXTSHOW` |
| `0x9BC` `0x9BD` | Glen's orders; Glen and Cormag after | `Text_BG(BG_SERAFEW_VILLAGE)` |
| `0x9BE` `0x9BF` | the party arrives | `SetBackground(BG_TOWN)` + bare `TEXTSHOW` |
| `0x9C0`–`0x9C2` | on the street, party staged | `TEXTSTART` — on-map bubbles |
| — | | **`CALL(EventScr_08591FD8)` — prep** |
| `0x9C3` `0x9C4` | Joshua alone; Natasha alone | `FADU(16)`, then on-map bubbles |

**`vanilla_scene.py` prints `0x9BB` as "map" and that is a reporting artifact, not a channel.**
It classifies by the text call, and `0x9BB` is a bare `TEXTSHOW`; the `SetBackground` two lines
above it is what the scene actually plays over. Reading the tool instead of the script is how
"does vanilla use a background in its opening?" stayed open — it does, for the entire first half.

Three things fall out, none of which needed an argument:

- **Two backdrops, reused.** Vanilla spends `BG_SERAFEW_VILLAGE` on four consecutive scenes and
  only cuts to `BG_TOWN` when the party physically arrives. So ch05 wants ONE tomb backdrop for
  its three pre-arrival scenes and a second for the arrival — not a mood image per scene.
- **Where PREP sits is settled**: vanilla puts two full scenes AFTER the prep `CALL` and re-opens
  with `FADU(16)`. Our scenes 6 and 7 are those scenes' twins.
- **The map half cannot start early.** `PutTalkBubble` anchors to a speaking UNIT, and vanilla
  reaches `TEXTSTART` only once the party is staged. Nothing is on ch05's field before `LOMA`,
  so scenes 1–4 could not have been bubbles whatever we preferred.

**`Text_BG` is not a spelling of `BACG` — it is a CALL with a fade cycle on both ends**
(`Convo_Helpers.h` → `Event_TextWithBG`: `FADI` if the screen is up → `REMOVEPORTRAITS` → `BACG`
→ `FADU` → text → `EventScr_TextShowWithFadeIn`, which does `CLEAN` then `FADU` back onto the
**map**). That last step is why ch03/ch04/ch05 hand-roll the sequence instead of calling it: our
openings run BEFORE `LOMA`, so the map it fades up onto is still the host slot's. The macro is
right for a village visit (`village_script` uses it) and wrong for a pre-`LOMA` opening.

Ours therefore holds ONE `BACG` across the three tomb scenes and fades through black between
them — vanilla's separation without vanilla's return-to-map. The BG is not re-issued at each
fade, and that is deliberate rather than lazy: `EventShowTextBgDirect` only decompresses while
`activeTextType` is `REMOVEPORTRAITS`/`_1A22`, and each `Text()` leaves it at `TEXTSTART`, so a
second `BACG` would be the no-op that already bit ch03 and ch04. **Filmed rather than asserted**
(`recordch05opening`), because "still in VRAM" is a decomp reading and the screen is the witness.

_Decided: 2026-08-13 (Nicolas: "does vanilla use a background in its opening scenes? lets have a
plan before jumping into assigning a BG")._

### A reporting artifact outlived the note that named it: the ch05 endings (2026-08-19, #25)

The section above records that `vanilla_scene.py` prints `0x9BB` as `"map"` and calls it *a
reporting artifact, not a channel*. It fixed the READING and left the TOOL, so the artifact was
mined a second time — and this time nobody caught it. The ch05 YAML's anatomy table, issue #25's
per-scene notes and `HANDOFF.md` all carried **"the endings are ON-MAP at 29"** for three weeks,
and the wiring was about to be built against it.

`EventScr_Ch5_EndingScene` opens `FADI(16)` — the map goes **down** — then
`SetBackground(BG_SERAFEW_VILLAGE)`, then three bare `TEXTSHOW`s. There is no `TEXTSTART` in it.
Vanilla's ch5 ending is a **backdrop scene at ~42**, and by the rule above ours inherits that.

**The tool now tracks the backdrop as scene STATE rather than classifying by the text call**,
which is what it should always have done: `TEXTSHOW` prints into whatever surface is up.
Set by `SetBackground` / `BACG` / `Text_BG`; taken down by `CLEAN` and by
`CALL(EventScr_TextShowWithFadeIn)` (which is `FADI` + `TEXTSTART` + `CLEAN` + `FADU` back onto
the map, `events_script_utils.c:211`). **`REMA` does not take a backdrop down** — it ends the
TEXT, which is why vanilla's `0x9BF` is still `BG_TOWN` with a `REMA` in front of it and no
`SetBackground` of its own. `tools/test_vanilla_scene.py` pins all three ending ids, both
`SetBackground` + bare-`TEXTSHOW` scenes, and `0x9CC` as genuinely on-map — the Talk recruit
sits forty lines from the ending in one file and takes the *other* channel, so scene 14 stays
at 29 while scenes 16 and 17 take 42.

Three things fell out, and two of them were problems the on-map reading would have shipped:

- **Six speakers, and a bubble anchors to a UNIT.** `PutTalkBubble` needs a staged speaker
  (which is why `ch05_basil_join_block` carries a `CUMO_CHAR` and the ending cannot). ch05
  deploys 9 of a 10-unit pool, so on-map Marty, Wolfram, Braulo and RBG can each be talking
  from a tile nobody is standing on. **ch04's ending had already made this exact argument for
  itself** and its comment says so; ch05's note was written without reading it.
- **The two ending fallbacks needed no re-boxing.** Both overrun 29 and were on the owed list
  for it; at 42 they fit as authored. What is still owed is the *Talk recruit's* fallback,
  which really is on-map.
- The endings cost **three** message ids, from the swept neighbourhood and ch05's host block:
  scene 16 twice (Sahnar recruited or not) and scene 17 once. It was briefly six, until the
  Lupin branch came out — see "Neither ch05 ending branches on Lupin" below.

**The lesson is the one the ch04 comment already carried: when a tool is found lying, fix the
tool.** A note that records "this output is wrong" protects only the person who read that note.

_Decided: 2026-08-19 (Nicolas: "I have no idea where that came from ... you shouldn't have to
rediscover anything")._

### `CHECK_ALIVE` answers for a unit in ANY faction — so a recruit needs its FLAG too (2026-08-19, #25)

`branch_on_check_alive`'s docstring says CHECK_ALIVE reads the ROSTER rather than the field, and
that is right as far as it goes — but "roster" is not "the player's units".
`GetUnitStructFromEventParameter` → `GetUnitFromCharId` (`bmunit.c`) sweeps unit indices
**1..0xFF**, every faction, and returns the first valid match. So CHECK_ALIVE means *does this
character exist somewhere and is it not dead*, and nothing more.

That is exactly right for Lupin and for Basil, and **wrong for Sahnar**, and the difference is
whether the unit is ever HOSTILE:

- **Basil** is a green escort who joins by `CUSA` in scene 5 and is never anyone's enemy — the
  same shape as vanilla's Natasha, whose own ending branch is a bare
  `CHECK_ALIVE(CHARACTER_NATASHA)`. A bare ALIVE is correct.
- **Lupin** is either on the ch04 carry-over roster or nowhere. A bare ALIVE is correct, and
  never-recruited collapsing with recruited-then-killed is the *point*.
- **Sahnar rises HOSTILE and only flips when Basil Talks her.** Kill Ravisin without ever
  turning her and she is alive, red, and standing on the map when the ending runs — CHECK_ALIVE
  says 1, and the berry scene plays with the party's own enemy thanking Basil by name.

The gate is therefore the **recruit flag first, then ALIVE**: `CHECK_EVENTID(EVFLAG_TMP(7))`
(set by `talk_recruit_script`'s `EVBIT_T(7)`, vanilla's own Natasha→Joshua flag) asks *was she
turned*, and `CHECK_ALIVE` then asks *is she still here*, so a Sahnar recruited and later killed
is silent too. **Vanilla chains precisely this pair** — `ch19a-eventscript.h`'s
`EventScr_089F8688` runs `CHECK_EVENTID(7)` into `CHECK_ALIVE(CHARACTER_TANA)` to pick its
ending text. Both `BEQ` to one shared label, because a beat that is SKIPPED has no second arm to
jump over; that is `save_all_bonus_script`'s shape, not `branch_on_flag`'s.

**The general rule: ask CHECK_ALIVE about a unit that could be an ENEMY and it will answer yes.**
Any conditional whose subject is an optional TALK recruit wants the flag as well.

_Recorded: 2026-08-19 (found while wiring ch05's scene 16; the first draft used a bare
CHECK_ALIVE and would have shipped it)._

### A conditional block inside a scene is a WHOLE second copy, not a spliced beat (2026-08-19, #25)

ch05's scene 16 loses six boxes when Sahnar was never recruited. The obvious wiring is to make
those boxes their own message and let the event script skip the call — three `Text()`s where
there was one, which is also how every other chapter's ending is already assembled. It was built
that way, it **passed**, and it looked wrong on the first film:

> *"can you not just keep basil in frame the whole time and just have the other characters come
> in and out, in a single continuous scene? its weird when you refresh and basil ends up right
> where she was"* — Nicolas, 2026-08-19

`Text(msg)` is `TEXTSTART` + `TEXTSHOW` + `TEXTEND` + **`REMA`**, and `REMA` ends the text: the
faces come down with it. So a scene split across three calls has two seams, and any speaker who
appears on both sides of one fades out and reloads into the seat they were already in. Basil
speaks in all three beats, so the scene's own subject flickered twice.

**Held as ONE message per arm, `_script_to_message`'s podium manager runs the whole scene**: it
loads Basil once at mid-right, never clears her, and cycles Marty → Wolfram → Sahnar → Braulo →
RBG → Braulo through mid-left with a `[ClearFace]` between each. That is the scene — the party
comes to *her* — and it falls straight out of the renderer once nothing interrupts it.

The cost is text duplication, and it is **not** a cost worth avoiding here:

- **The ids are the same either way.** Whole copies of scene 16 against beats-plus-a-twin cost
  the same count. The earlier reasoning that a split is cheaper (*"duplicating text is free, ids
  are what is scarce"*, recorded above) was priced against an id shortage that does not exist,
  and it never counted the seams.
- **Nothing is hand-duplicated.** Every copy is generated from the one locked script by
  `variant_beat`, whose `replaces:` anchors assert each edit lands where the YAML says. There is
  no second copy of the prose to drift.

`variant_beat` now takes a variant with **no `script:` key at all**, meaning *drop these boxes*.
A cut authored as six empty substitutes would say the same thing far worse, and the anchors
still apply — which matters most for a drop, because a mis-indexed cut is invisible in the
output: the result is simply a shorter scene that still reads. The build asserts the arm is six
boxes shorter and that Sahnar has no line left in it, since anchors alone cannot prove a
deletion happened.

**Two variants over one script compose only in one order.** The no-Lupin substitution is box 16
and the cut takes 8–13, so applying the cut first moves the wolf line to box 10 and the
substitution lands on the wrong box or falls off the end. Substitutions are 1-for-1 and
therefore index-preserving, so they go first; both variants stay authored against the ONE locked
script, which is the only version a reader can check the indices against.

**And the general one: a branch that PASSES can still be wrong.** The box-count assertion
covered the arm, `verify_text` covered the text, and neither can see a face reload. Presentation
is filmed (`decisions.md` → "Three data checks can pass while the thing is visibly broken").

_Decided: 2026-08-19 (Nicolas, on the first film of the ending)._

### Neither ch05 ending branches on Lupin: an ENCOUNTER is not a RECRUIT (2026-08-19, #25)

Both ch05 endings carried a `no_lupin_fallback` from 2026-07-30. Basil's line names the wolves —
*"She woke it. Like she woke the wolves"* in scene 16, *"The moose, the wolf.. they were not
alone.."* in scene 17 — and the rule that produced the fallback was **"this names an optional
recruit, so it needs an arm."**

The rule was applied to the wrong noun.

> *"we actually don't need lupin branching in the ending scene. regardless of if he was recruited,
> the party encountered him. so Basil referencing him is true no matter what"* — Nicolas

ch04's parley decides whether Lupin **JOINS**. It does not decide whether the party ever met the
pack: the turn-2 reveal puts the wolves on the field on every path, and the difficulty model
explicitly prices fighting them. So the locked line is true in both worlds and the branch could
only ever have been wrong — an arm that substitutes *"like she woke me"* for a player who fought
the wolves an hour ago is strictly worse than the line it replaces.

**The test, for any future line: does the player necessarily ENCOUNTER the thing it names?**
A unit the player fights either way is not an absent unit. Scene 17's box already made this
distinction and nobody noticed — *"the moose"* is deliberately unbranched there, on the reasoning
that Basil is listing who Ravisin WOKE rather than who survived. The wolf belonged in that list on
exactly the same grounds; it was one clause away in the same box.

What survives the correction is the shape of a real fallback. The three that remain — the arrival,
the join and the Talk recruit — all address Lupin **as a unit present in the scene**, which is the
thing recruitment actually governs. That is the line between the two cases: a beat that would
*speak to* or *stage* an absent unit needs an arm; a beat that merely *refers to something that
happened* does not.

Cost of the correction: the ending goes from six message ids to three, no id has to be appended
past `MSG_D4B` any more, and the owed-films list drops from six arms to three. `variant_beat` and
`branch_on_check_alive` are untouched — the endings simply stopped calling them for Lupin, and
`_ch05_ending_variants` now REFUSES a `no_lupin_fallback` on either ending so a restored block
cannot sit in the YAML looking live.

_Decided: 2026-08-19 (Nicolas)._

### A portrait SLOT name is not a face TAG, and the near-miss is silent (2026-08-13, #25)

Sephek's face is spelled two ways in this repo. `GUEST_PORTRAIT_MAP['sephek-kaltro']` says
`'O_Neill'` — a portrait-slot name, which is what dresses busts — while `PROLOGUE_SEPHEK_SLOT`
says `'ONEILL'`, and only the second is a spelling `_fid_tag` can map, because its irregulars
table keys on `ONEILL`. Routing his face through the map emits `[FID_O_Neill]`, and
`textdefs.txt` defines `[FID_ONeill]`. **Nothing downstream complains** — the same shape as the
`0x9CC` bug #276 fixed, where every text decoder was green while the wrong face was on screen.
The guard is a test that every `FID_` tag a scene emits is defined in `textdefs.txt`, checked
against `FID_ONeill` present and `FID_O_Neill` absent so the fixture cannot rot into a tautology.

_Decided: 2026-08-13 (#25, wiring ch05's opening — first scene to give Sephek a cutscene face
outside the prologue)._

### "Did the player recruit them?" is `CHECK_ALIVE`, and it needs no flag (2026-08-13, #25)

ch05's `no_lupin_fallback:` arms need to know whether ch04's optional parley happened — three of
them today; the two ENDINGS were unbranched 2026-08-19, see below. Two
answers were proposed here before anyone read the decomp — carry a persistent flag out of ch04, or
test whether Lupin is standing on the ch05 field — and **both are wrong**. Vanilla has shipped the
answer since 2005.

`CHECK_ALIVE(pid)` (`EvtCheckUnitNotDead`, `EVSUBCMD_CHECK_ALIVE`) leaves `1`/`0` in `EVT_SLOT_C`,
and `BEQ(label, EVT_SLOT_C, EVT_SLOT_0)` jumps to the absent arm on `0`. `eventscr.c` is explicit
about what `0` means: **the unit was not found at all, OR it carries `US_DEAD`.** Never recruited
and recruited-then-killed collapse into one arm — and that is the behaviour we want, not a wart to
work around. A dead Lupin should no more be described as "out there now, with travelers" than one
who was never won.

**The precedent is our own scene's ancestor.** `ch14a-eventscript.h` branches its ending on
`CHECK_ALIVE(CHARACTER_JOSHUA)` three separate times — Joshua being vanilla Ch5's optional Talk
recruit, and Sahnar's exact donor. Vanilla re-checks inline at each branch point rather than
caching a result, so the idiom is cheap and repeatable.

**Why the field test would have been actively wrong here:** ch05 deploys **9 of a 10-unit pool**,
so Lupin can be recruited, alive, and simply benched — and a field-presence test sends that player
down the no-Lupin arm, having earned the wolf. `CHECK_ALIVE` reads the ROSTER, not the map, so it
gets the benched case right. FE8 draws this distinction itself: `EVSUBCMD_CHECK_DEPLOYED` is a
separate subcommand, and vanilla uses ALIVE for dialogue branches and DEPLOYED for map logic.

**And no flag is involved**, so the open question about whether `EVFLAG_TMP(9)` survives a chapter
boundary is moot rather than unanswered — we never needed it to.

Reuse, don't add a mechanism: `branch_on_flag()` already emits this exact skeleton
(`CHECK_EVENTID` → `BEQ` → arm → `GOTO`/`LABEL`), and `convert_survivors_green()` already emits
`CHECK_ALIVE` in ch04's pack parley, so the macro is proven in our build. The sibling is the same
function with the check swapped.

### The `--ch05-boot` ROM can only ever play the NO-Lupin arm (2026-08-13, #25)

Built at ch05 scene 4, the first scene with a `no_lupin_fallback`. Recorded here because it is the
trap that would make the owed four-state proof **vacuous**: a scenario that always walks one arm
passes just as green as one that walks the right arm.

`CH05_BEGINNING_SCRIPT` asks `CHECK_ALIVE` **before `LOMA`** — that is forced, because scene 4 is a
pre-map backdrop scene and its channel is inherited (see "A cutscene's CHANNEL is inherited"). The
`--ch05-boot` party seed (`MS_Ch05BootSeed`) is `LOAD1`ed **after** `LOMA`, several lines further
down, because its whole job is to give PREP a party from a COLD New Game. So at the instant the
branch runs on a boot ROM, `gUnitArrayBlue` holds nothing, `GetUnitFromCharId` returns NULL, slot C
is 0, and the fallback plays — **every time, for every unit, no matter what the seed contains.**
Filmed and confirmed 2026-08-13: `recordch05opening` on `ch05boot` opens scene 4 on Pinky's *"The
tracks stop here, Father"*, never Lupin's *"The trail leads here"*.

So: **the boot ROMs prove the fallback arm and are structurally blind to the other three states.**
Proving "recruited, alive, deployed" and "recruited, alive, BENCHED" needs the REAL chain
(ch04 → ch05) where `ReadGameSave` has filled `gUnitArrayBlue` before the chapter's events run.
Do not "fix" this by moving the seed load above the branch — it sits after `LOMA` because `LOMA`
rebuilds the map, and units loaded before it are placed on the outgoing one.

**The placement itself is vanilla's, and was checked rather than assumed.** `EventScr_Ch7_Beginning`
`Scene` branches its own opening dialogue on `CHECK_ALIVE(CHARACTER_FRANZ)`, then `GILLIAM`,
`MOULDER` and `VANESSA` — four optional units, asked inside a beginning scene. Asking that early is
a thing vanilla does. (Vanilla asks after its ally `LOAD3` rather than before, which is exactly why
the boot-ROM blindness above is a real difference and not a quibble.)

### A glued em-dash still has to FIT (2026-08-13, #25)

`_wrap_fe_lines` keeps a bare `--` from opening a line by gluing it to the word before it. It did
that **without re-measuring**, so any line that ended within two characters of the width came out
over it. ch05 scene 4's Wolfram line sits exactly on that boundary — *"Struck off edges. There was
fighting here --"* is 44 against the scenic 42 — and it is what found the bug, but the glue lives in
the shared wrapper, so every chapter was exposed. The fix moves the word DOWN with its dash rather
than letting the line run over; the dash still never opens a line, which is the property the glue
existed for. No shipped message body moved (full suite + `verify_text` green over 3404 messages),
because nothing else had a line that landed in the two-character window.

General shape, and the reason this is written down: **a formatting rule that edits a line after the
width check has to re-run the width check.** The failure is invisible to every decoder — the text
is well-formed, correctly encoded, and simply too wide.

**And the first fix only MOVED the overflow, which review caught.** Re-measuring the line the dash
leaves is not enough; the line it lands on has to fit too. Where it cannot — a word whose own length
plus `' --'` already exceeds the width — the two rules genuinely conflict, the pair is atomic, and
the glue wins: that line goes out over-width because no shorter arrangement exists. So the invariant
is *"within the width unless it is a lone word carrying its dash"*, and the test now says exactly
that, plus walks the dash through every gap in a sentence at every width from 20 to 44 rather than
trusting the one sentence that found the bug. No authored box is anywhere near the atomic case; if
one ever is, reword it rather than loosening the glue.

### The alive arm needed a LEVER, and the boot seed was a second reason it had none (2026-08-14, #25)

`--ch05-lupin` (with `--ch05-boot`) `LOAD1`s a one-unit table holding Lupin **before** the opening
runs, which is what makes scene 4's ALIVE arm reachable from a cold boot at all. Nicolas asked for
both paths on film; only one of them could be made.

**There were two independent reasons, either fatal on its own** — the second only surfaced when the
first was being fixed, which is why it is written down:
  1. the branch runs before `LOMA` while the boot party seed is `LOAD1`ed after it, so
     `gUnitArrayBlue` is empty when `CHECK_ALIVE` asks (the ADR above);
  2. **Lupin is not in that seed.** It zips the cast against 9 deploy slots and he is last, so he
     falls off the end. Even hoisting the seed above the branch would still have played the
     no-Lupin arm — and would have looked like the fix working.

Loading pre-`LOMA` is safe, and that was checked rather than assumed: `RestartBattleMap`
(`bmio.c:1043`) rebuilds map, BGs, sprites and traps and **never touches the unit arrays**, so the
unit survives as a roster entry, which is all `CHECK_ALIVE` reads.

**What the two films do and do not prove.** Measured: they agree through scenes 1-3 (bar 2-4 frame
emulator timing jitter) and diverge from scene 4's FIRST BOX to the end — the tail is not four
scenes of difference, it is the two box 1s being different lengths and time-shifting everything
after, so no frame lines up again. "They differ only in box 1" is therefore **not testable by frame
equality**, and the harness comment no longer claims it is. Compare by eye.

Against #25's four states this settles **two**: *never recruited* (the plain boot film) and
*recruited, alive, on the roster* (the proof ROM). **Benched** and **recruited-then-killed** are
still only a decomp reading — `CHECK_ALIVE` ignores `US_NOT_DEPLOYED` and treats `US_DEAD` as
absent — and a reading is not a run.

### A letterbox mat is not picture, and a CENTRE crop keeps half of it (2026-08-14, #25)

Nicolas, looking at the shipped ch05 opening: *"you see the black bar to the right in the
background?"* He was right, and it was in **both** ch05 backdrops.

The FE-Repo's `FE9-10 CG Rips` are **letterboxed**: a 240-wide picture sitting in a 256-wide
canvas, the spare 16 columns filled flat black. `bg_to_fe8.py --fit crop` centre-crops, taking
columns 8..247 — so it kept **half the mat** on the right and threw away **8 columns of real
picture** on the left. Both `bg_ElvenTomb` and `bg_ForestOutskirtsWinter` shipped that way.

**What let it through is the part worth remembering.** Each BG was vendored against the check
*"0 of 38400 pixels differ from the 5-bit source crop"* — and that check passed, correctly. It
proves the CONVERSION is faithful to the crop. It says nothing about whether the crop was the
right crop, because the crop is on both sides of the comparison. A fidelity check cannot audit
its own reference frame. (Same shape as `decisions.md` → "A scenario's verdict only covers what
it READS".) The check now compares against the source PICTURE, and a test asserts no shipped BG
has a flat edge column.

**The detector is UNIFORMITY, not darkness.** Measured on the two real rips, a mat column holds
exactly **1** distinct colour while the art beside it holds **8–12** — so the two are nowhere near
each other and no tolerance is needed. Keying on "is it black" would have missed a white or
magenta mat and risked eating genuinely dark art (the tomb's left edge is brightness ~38 and is
real stonework). `trim_uniform_border` strips edge rows/columns that are a single flat colour,
with a `min_keep` rail so a picture that is largely flat by design (a night sky, a fade to black)
is left alone rather than trimmed to nothing.

Both BGs now land **1:1 with no scaling and no crop of real art at all** — the trimmed source is
exactly 240x160. Bank counts are unchanged (2 and 3).

### Inheriting a channel is not inheriting a POSITION: scene 5 plays after PREP (2026-08-14, #25)

"A cutscene's CHANNEL is inherited from the twin" (above) reads vanilla Ch5's own beginning scene
and gets ch05's seven openers right — three tomb backdrops, the ridge, an on-map bubble, then two
scenes after the prep `CALL`. It also implies scene 5 sits where its twin sits, **before** that
`CALL`. It cannot, and the reason is ours, not vanilla's.

**Vanilla stages its speaking party; we don't have one yet.** `EventScr_Ch5_BeginningScene`
`LOAD1`s `UnitDef_088B59C8` and `UnitDef_088B56F8` — Eirika's group — and only *then* plays
`0x9C0`–`0x9C2` as on-map bubbles; the ally table `UnitDef_Event_Ch4Ally` goes in right before
prep, as the deploy template. Our party arrives **through prep**: on a prep chapter the ally table
is never `LOAD`ed and the roster is placed by Pick Units (see "How the deploy cap + prep screen
are actually wired"). So at the point vanilla's twin plays, ch05's field holds sixteen risen dead,
Ravisin, and one green shrub — and Basil's *"Oh! Tourists. In the tomb."* would be addressed to an
empty pocket, in **both** arms.

So the beat moves after `CALL(CH05_PREP_SCRIPT)`, and takes vanilla's own after-prep shape, which
is what `0x9C3`/`0x9C4` already are: **`FADU(16)`** — the shared prep prologue fades to black and
leaves it there, so anything visible afterwards brings its own fade-up — then `CUMO_CHAR` +
`STAL(60)` + `CURE` to put the camera on the speaker, then `TEXTSTART`. `PutTalkBubble` anchors to
a unit, so the camera move is load-bearing and not decoration.

Two things fall out, both good:
- **The ask and the flip are one beat.** The `CUSA` was already after prep, for an unrelated
  reason (Basil is green across the prep screen so Pick Units never sees her and she costs no
  slot). Box 3 is *"...Take me to her?"*; the next command is the green→blue flip that answers it.
  Before this the CUSA was silent and the join simply happened.
- **Two branches now share one event list**, so `branch_on_check_alive` gets its `label_base`
  used in anger for the first time: the arrival keeps 0/1, the join takes 2/3. `BEQ`/`GOTO` scan
  the list for a matching `LABEL`, so a second branch left at the default would have jumped into
  the arrival's arms.

**The general rule.** The twin answers *how a scene is played* — backdrop or bubble, and how wide.
It answers *where the scene sits* only where the surrounding machinery is also vanilla's. Ours
diverges at exactly one place, prep, and that is the seam to check every time.

### A fallback line chosen as PROSE has not been boxed (2026-08-14, #25)

ch05's five no-Lupin substitutes were chosen 2026-07-30 as single lines. Three of the five do not
fit one box at the talk bubble's 29 characters. (Two of the five have since been retired with the
endings' branches — and both of those were among the over-long ones, which is how the endings
ended up owing no boxing at all.) Scene 5's is 74 characters, and rendered flowed it
paged itself mid-clause — *"You just-- came"* / *"here. On your own."* — an A-press the author
never placed, on a scene whose locked arm was hand-boxed to this exact width in July.

This is the reliquary lesson arriving from a new direction: **the authored A-press breaks ARE the
pacing.** There it was a flowed YAML scalar reflowing 27 boxes; here it is a substitute written at
one width and rendered at a narrower one. The wrapper is not choosing badly — it has no idea where
the beat turns.

**So `variant_beat` now accepts a `script:` entry that is a LIST of boxes**, replacing the one
named box with all of them; `boxes:`/`replaces:`/`script:` still agree one-for-one, so this stays
one mechanism rather than a second. Substitutions are resolved against the original beat and
spliced afterwards — editing in place would shift every later `boxes:` index and the anchor
assertion would then blame the locked script for moving.

**Two arms of a branch are not required to cost the same number of A-presses.** Scene 5's no-Lupin
arm is 4 against the locked arm's 3. Nothing reads them together; each has to stand up alone.

Nicolas chose the break (2026-08-14): after the shock (*"...You're none of hers."*) rather than at
the sentence boundary, so her run-on then arrives whole. That is her register — `lore/basil.md`
§Voice, *"runs on when she cares"*, corpus twin Ewan — and splitting on the full stop would have
cut the tumble in half and buttoned the first box on *"one of you."*, which is not where the beat
turns. **The remaining on-map fallback (the Talk recruit's) overruns identically and takes the
same treatment when it is wired.**

### A face that never speaks must be PRELOADED, and podium rungs overlap (2026-08-14, #25)

ch05's scene 3 stages Ravisin raising Sahnar with **no dialogue at all** — Nicolas's call
(*"you don't need to even add lines... just add sahnars portrait to the scene"*), which keeps the
seven locked boxes and protects the beat the scene exists for. Getting a silent face on screen
taught two engine facts, both found **by filming**, neither visible to any static check: every id,
box count, wrap and podium assertion passed while the scene played wrong.

**1. A silent face cannot arrive mid-scene.** `TalkPrepNextChar` (`scene.c:626`) reopens the talk
bubble whenever the ACTIVE face slot differs from the SPEAKING one — `ClearTalkBubble()` then
`StartTalkOpen()` for the active face. A `[LoadFace]` for someone who does not speak next
therefore opens a bubble of its own, and the scene plays with **two stacked bubbles**. Vanilla
never does it: every mid-message `[LoadFace]` in the corpus has that face speak immediately
(MSG_904, MSG_092C, MSG_095A), and its silent loads are always **preloads before the first box**
(MSG_0954, MSG_095D, MSG_095E). So the directive is `present:` — *"on screen for this scene,
never speaks"* — rendering through `_script_to_message`'s existing `preload` path. It was first
built as `enters:`, and that name was a lie: position is not expressible, so a directive implying
it invites the bug back.

Two false trails, recorded because both looked right: `[SendToBack]` is **portrait z-order**
(`SetTalkFaceLayer` via `TALK_FLAG_4`), not a window close; and `[OpenX]` is only
`SetActiveTalkFace`, so nothing "leaves a window open".

**2. Podium rungs overlap, and the SPEAKER is drawn on top.** The tags are a ladder
(`msg_list.txt`: Right 11, MidRight 12, FarRight 13). For a scene of speakers that is harmless
and vanilla leans on it — ch05's own scene 4 seats four across adjacent rungs and each is drawn
over the others when its turn comes. **A silent face never gets a turn**, so on a neighbouring
rung it is buried for the whole scene (Sahnar played hers as a hood behind Ravisin's shoulder),
and on the SAME rung it is `[ClearFace]`d outright before the first box. Vanilla's stable
two-face right side leaves a rung empty — Right + FarRight, never MidRight + FarRight (MSG_904,
MSG_092C, MSG_0937, MSG_0954) — reached in three of those by sliding the incumbent out with
`[MoveRight]`. Ours reseats statically instead, which is free across the fade between scenes.
`assert_silent_faces_have_elbow_room` enforces it at distance 0 **and** 1.

**The first version of that guard banned adjacency outright and immediately rejected scene 4**,
which is shipped and accepted. The rule is about SILENCE, not adjacency; a test pins that
speakers on adjacent rungs stay legal so it cannot creep back.

### A unit's LOAD tile is not its POST, and the difference cost us the arena (2026-08-14, #25)

Vanilla Ch5 `LOAD1`s Joshua on **(12,6)** and, as the very next command, walks him off it:
`MOVE(0x0, CHARACTER_JOSHUA, 9, 7)`. ch05 lifted the load tile and dropped the MOVE, on the
reasoning that our Sahnar simply fights where she lands.

That is a bug wearing a decision's clothes. **(12,6) is `TERRAIN_ARENA_REGULAR` and the arena
tutorial's own trigger is `AREA(..., 12, 6, 12, 6)`** — a hostile parked there makes the arena
unenterable for the entire chapter and silently kills the `arena-wager` debut (#264/#265, still
`status: active`). The chapter YAML said *"which is the ARENA tile (12,6)"* two lines from the
placement the whole time.

So the walk-off is chapter data, not flourish: **`walks_to: [9, 7]`** (vanilla's tile —
`TERRAIN_ROAD`, no defensive bonus, clear of the arena mouth), and `ch05_sahnar_station` refuses
to build without it. The escort distance `assert_green_recruit_placement` measures is to the
POST, because that is where the Talk happens.

**Generalise it:** when a retile lifts a vanilla unit's coordinates, lift what the event script
does to that unit NEXT. A tile that a vanilla unit leaves immediately is usually a tile something
else needs. `ch05arena` is the witness — it asserts the tile is empty, and it was failing its
first check on every run.

### AI parity can hide in a GLOBAL table, not in the unit's own bytes (2026-08-14, #25)

Sahnar is Joshua, so she must play as Joshua plays — and half of how Joshua plays is a
**refusal**. `AI_A_07` is `gAiScript_ActionInRange_ExceptNatasha`: `AiScriptCmd_05_DoStandardAction`
routes through `AiIsUnitEnemyAndNotInScrList`, which tests each candidate's
`pCharacterData->number` against a list — and vanilla's list (`cp_data.c` `gUnknown_085A8A00`)
holds `CHARACTER_NATASHA` **literally**. That carve-out is the only reason a fragile Cleric can
walk up to a Killing Edge on the arena tile at all.

Copying `.ai = {0x7, 0x3, 0x9, 0x0}` does **not** copy it. Basil takes Natasha as a STAT_DONOR but
deploys on her own CHARACTER slot, so `0x7` silently degrades to plain `AI_A_00` and the escort is
a legal target. `repoint_escort_safe_ai_list` rewrites the list to our escort at build time.

**Safe because the list has exactly one client in all of FE8**: `.ai = {0x7,` appears once, on
`UnitDef_088B5914` — read from decomp HEAD, never the built tree. `AI_A_07` exists to serve one
unit in one chapter, and that chapter is ch05's twin. Guarded three ways: the patch hard-exits
unless it finds vanilla's form, `src/cp_data.c` joins `PATCHED_DECOMP_FILES` so it restores each
build, and `assert_escort_safe_ai_has_one_client` sweeps **every** `CH##_AI` table — scoping that
sweep to ch05 was the first cut and defeated its own purpose, since the hazard is a future chapter
reaching for `{0x7,` on its own account.

**The general shape:** a unit's behaviour is not always in its own data. Before claiming an AI
byte is copied faithfully, find what the script it selects actually READS.

### A scenario written against the old design will FAIL ON SUCCESS (2026-08-14, #25)

Moving Sahnar from a turn-2 riser to a turn-1 unit broke three playtest scenarios, and the
instructive one is `ch05recruit`: it waited on `turn() >= 2 and redSahnar()`. With her red from
turn 1 that is satisfied the instant the counter ticks — **before Ravisin says a word** — so the
gate would have reported *"eruption warning showed 0 boxes"* and blamed the warning. The chapter
would have been fine and the accusation would have pointed at it.

This is the standing *"a scenario can FAIL on success, and it will blame the chapter"* lesson with
a new trigger: not the scenario's own bookkeeping, but a **design change the scenario predates**.
When a placement or trigger moves, grep the harness for what waited on the old one.

The repair also split a compound assertion into two honest ones — Sahnar is RED on her post at
turn 1 (which nothing witnessed before: an empty arena passes every other ch05 scenario, and the
first symptom would be a Talk with no target), and separately the eruption's four boxes on turn 2.

### A vendored anim's palette is a BY-EYE call, so it gets an editor, not a function (2026-08-17, #25)

A community battle animation arrives on its author's own colours, and for a named unit those are
often wrong on faction while being right on everything else. The enemy-reskin path answers this
with `recolor:` naming a **function** (`enemy_red_recolor`: blue-dominant clothing → a red ramp at
the same brightness). That works for a generic class, where the question is only "which side is it
on". It does not work for a character, and Ravisin is why.

**A ramp cannot be inferred from RGB.** The author shipped an index-aligned "enemy" swatch, so
swapping it looked free — and it turned her **hair teal**, because the art does not use those
indices the way the swatch suggests. Auburn hair matching her bust was the entire reason that
animation was chosen over the hooded finalists. No rule over colour values would have known that;
the ramp had to be *looked at*.

So a character's palette is hand-edited: **`tools/banim_palette.py`**, a local browser editor for
an imported anim's own 15 colours, with the animation playing at the `.txt`'s real cadence while
they change. Neither existing tool could do it, and the reason is worth keeping — `map_sprite_swapper`
remaps **indices** against the locked cast palette and `map_sprite_editor` paints **pixels** against
a palette it holds still. Both move pixels and hold colours fixed. Here the colours are the variable,
and the target colour is not in the sprite's set to begin with. Its `👁 isolate` is the load-bearing
control: it answers "which index owns the hair" before anything moves, which is precisely what the
rejected swatch got wrong.

The edit lands as `palette_edit:` on the unit's `import:` block and is applied as
`build_import(recolor=...)` — **the agbpal only**. Every sheet index is byte-identical, so an edit
is reversible, re-runnable, and never a silent re-import. Swatch ORDER comes from
`feditor_to_banim._palette` itself rather than a local derivation: edit index N in the tool, index N
in the ROM. A missing `palette_edit:` file **raises** — a typo must fail the build, because the whole
premise is that native was wrong for this unit.

**And a ramp must stay a ramp.** The first hand edit set the robe's three entries to one flat black
and the skin's two to one flat white. It rendered as a silhouette: fold shading gone, and the cast
FX — indices 2/3 draw the spell fan as well as cloth — became a solid void. This is the rejected
Arena palettes' failure one axis over. **Those crushed CHROMA, this crushed VALUE**; merging distinct
ramp entries into a single colour destroys form either way. Ship the intent with the steps intact
(`docs/demo/ch05-ravisin-palette.png`). Judge it offline first — this whole loop cost seconds and no
ROM build, the same reason `rom_bg_preview.py` exists.

### A LOCK has a DATE, and facts settled after it still apply (2026-08-19, #25, #293)

ch05's scene 17 called Basil **"he"** twice. Her text was locked 2026-07-30; her `gender: female`
was settled 2026-08-08. Nobody contradicted anybody — **the lock simply predated the decision**,
and "locked" was read as "checked", which it never was.

So a locked scene is frozen against *re-litigation*, not against *facts*. Before wiring one, diff
its lock date against anything settled since about the characters it names — pronouns, class,
who is recruitable, who is even alive. Correcting a scene to match a later-settled fact is not
reopening the dialogue pass and does not need a fresh one; it is the same kind of change as
updating a stale constant. Preserve box count and rhythm, note the correction and its date in the
scene's own `description:`, and move on.

The exposure grows with the gap: ch05's endings were locked in July and are being wired in
August, and they are the LAST scenes anyone will read before they ship.

### A battle anim carries FOUR palettes and the engine picks one; ours are four copies (2026-08-20, #25)

Asked directly ("do the battle anims not get the red faction palette?") and worth writing down,
because the two halves of a reskin behave oppositely and the difference is invisible until a
creature is on screen twice.

- **A MAP sprite is recoloured by the ENGINE at runtime.** `ApplyUnitSpritePalettes` loads
  `unit_icon_pal_enemy` into the sprite's OBJ bank, so one sheet reads blue as an ally and red as
  a foe. This is why a vendored sheet's own colours barely matter — `inject_enemy_class_reskins`
  only has to remap it onto the base class's SMS palette.
- **A BATTLE anim is not.** `GetBanimFactionPalette` (`banim-ekrcmd.c:115`) maps the unit's
  faction to `BANIMPAL_BLUE/RED/GREEN/PURPLE` = 0..3, and that index is an OFFSET into the
  palette buffer (`gUnknown_08802B04 + gBanimFactionPal[side] * 0x10`). So an anim's `.agbpal` is
  **128 bytes — four 16-colour banks — and the engine SELECTS one.** It transforms nothing.

Vanilla ships four genuinely different banks: `banim_arcm_ar1.agbpal`'s blue bank holds
`(216,248,112)` where its red bank holds `(168,208,248)` in the same slot.

**Ours are 128 bytes with all four banks byte-identical.** `feditor_to_banim` imports the single
palette an FEditor script carries and replicates it, so a community anim renders in its native
colours on every side. That is not a bug — it is what `recolor: enemy_red` exists to correct, and
why the kobolds declare it while the PC cast does not.

**`enemy_red` is not always the right correction.** It keys on blue-dominant colours
(`b > r + 30 and b >= g`) to catch faction-swappable cloth, and ch05's skeletons have cool bluish
BONE highlights — applying it reddens the skeleton itself rather than its armour. Checked against
the imported palettes before shipping and rejected on the picture, the same call Ravisin's palette
records: `decisions.md` → "A vendored anim's palette is a BY-EYE call". ch05's four ship NATIVE,
so its risen guard wear blue armour in the close-up and take the engine's red only on the map.
The remedy if that ever bothers anyone is a hand-edited bank via `tools/banim_palette.py`, not a
blanket hue rule.

_Recorded: 2026-08-20 (Nicolas asked; the answer was not written down anywhere)._

### `recordenemy` baits by REACH OVERLAP, not by melee — an archer can be benched (2026-08-20, #25)

The bench picked "a live melee player unit" and stood it orthogonally adjacent to its target,
because it films a COUNTER-attack. A bow has no range-1 attack, so an adjacent bait produced no
animation — and that got written down as *archers cannot be benched*, with `CLASS_ARCHER` left
out of `CLASS_RESKIN_FOE_WEAPON` as if the class were the problem.

It is not. **Approach an archer with a bow or a tome and it answers at range 2** (Nicolas: "we
tested RBG and he's an archer"). The limitation was the picker's, wearing a class's name.

The bait is now chosen by finding a party unit whose weapon reach OVERLAPS the foe's, and stands
at a distance both can strike at; the candidate tiles are the Manhattan ring at that distance,
UP before DOWN before sideways. At distance 1 that ring is `{0,-1},{0,1},{-1,0},{1,0}` — byte-for-
byte the literal list it replaced.

**The order is written out, not sorted, and that is the review's finding.** A comparator on |dx|
leaves `{0,-1}` and `{0,+1}` tied and `table.sort` is not stable, so "up first" was luck — and the
first cut of this drew DOWN first, which on the bench's own y=9 row is straight off the map.
**The bounds were a literal too** (`ty <= 15`, from a bigger chapter) while the sandbox is 15x10,
and `mapUnitAt` reads `gBmMapUnit`'s zero-filled border row and answers *empty* for y=10 — so the
off-map tile would have been accepted and `cursorTo` could never reach it. Both now come from
`mapSize()`.

**The "clean tile" rule got more correct on the way.** It asked whether another foe was
orthogonally ADJACENT to the bait — a proxy for the real question, *is another foe inside the
BAIT's own attack range*, which is what makes the attack menu ambiguous and films the wrong
creature. Identical at melee; at range the old test would have let a second skeleton into the menu.

**The general shape, and it is the third instance this month:** a check written for the only case
that existed encodes that case rather than the property. See also `mapfull`'s grid (below) and the
bench's flat x-spacing assertion, both of which were right until a second row or a second chapter
existed.

_Recorded: 2026-08-20 (bone-archer filmed on the fix; Marty baits it with Flux from the far platform)._

### `mapfull` was chapter-generic in name and ch03-shaped in fact (2026-08-20, #25)

Its grid was the literals `{0,8,15} x {0,8,16}` — exactly ch03's 17x16 map — while the scenario
was described and used as chapter-generic. On ch05 (15x21) that walked the cursor to x=16, off
the map, and the run reported `FAIL: controller fault: cursor_right` AFTER capturing every tile it
wanted: a verdict accusing the chapter of something the scenario did to itself.

The worse half is silent. Those stops cover rows 0-15 of a 21-row map, so it would have produced a
confident "full-map grid captured" that was missing the bottom quarter — including ch05's deploy
pocket. **A check that cannot see what it is missing is not a check.**

The grid now derives from `mapSize()`, stepping a screenful (15x10) and always finishing on the
far edge. Two further things the ch05 pan taught, both cheap and both about COST rather than
correctness:

- **Poking fast config before the boot does NOTHING, and the timeouts are not root-caused.**
  It was added claiming to fix them; `bootToMap` goes through New Game and `InitPlayConfig`
  (`bmio.c:936`) `CpuFill16`s `gPlaySt` to zero and sets `textSpeed = 1`, so a pre-boot poke is
  wiped. An earlier run had already passed without it in 22s, so the two timeouts are flake or
  something not yet found — recorded as open rather than closed, because a false cause in a
  comment is worse than none.
- **`--ch05-moose` is the WRONG shortcut for it**, tempting as it looks: `recordch05moose`
  documents that `bootToMap` is the wrong driver on that ROM, because there the beginning script
  IS the beat.

_Recorded: 2026-08-20 (three runs spent on one screenshot; the grid, the speed, and the boot)._

### The TESTCH bench is bounded by SMS VRAM, not by its tile row (2026-08-19, #25)

The bench ran out of seats at seven and it was briefly written down as "the bench is full",
which invites a redesign. It is not a limit FE8 imposes — it is the geometry of one row.

`SANDBOX_FOE_POSITIONS` is a single row at y=9 with **spacing 2**, and the spacing is load-bearing:
`recordenemy` places the bait unit orthogonally adjacent to its target and requires **no other foe
adjacent**, or the counter-attack it films is the wrong creature's. On a 15-wide map that yields
x=2,4,…,14 — seven. The party sits at y=4, so **a second row lifts it immediately**; a wider
`ch-test-snowfield.json` does too. (`sandbox_map_size` READS that map, because the test chapter is
repointed at it by `inject_winter_tileset` and is not vanilla Ch1's.)

**The real ceiling is SMS VRAM, and it is much higher.** `ResetUnitSprites` (`bmudisp.c`) hands out
`0x40` = **64 slots**, consumed from both ends by two counters that grow toward each other:

| counter | starts | per distinct sprite |
|---|---|---|
| `gSMS16xGfxIndexCounter` | 63, walks **down** | −1 per 16×16 |
| `gSMS32xGfxIndexCounter` | 0, walks **up** | +2 per 16×32, +4 per 32×32 |

When they **cross**, later sprites silently overwrite earlier ones — the failure `recordunitlist`
exists to catch. Two consequences worth holding on to:

- **Cost is per DISTINCT sprite, not per unit.** Twenty kobolds of one class cost one slot; the
  bench pays once per creature, and its seven spend ~10 of the 64 alongside the player party.
- **The two size classes are not interchangeable.** A 32×32 costs four times a 16×16 and eats from
  the opposite end, so a bench of monsters exhausts the pool far sooner than a bench of humans.

What actually failed before was neither ceiling: the row held a tile at x=16 on a 15-wide map, and
`_next_sandbox_tile` only ever guarded running OUT of tiles, never a tile that does not EXIST. The
seventh creature deployed off the map edge and `recordenemy` failed walking the cursor to a column
the map has not got. `assert_sandbox_bench_fits` now reads the map and fails the build instead.

### A community map sprite is keyed on GREEN, not on index 0 (2026-08-17, #25)

Every map sprite this repo had vendored until now came from the decomp, where transparency is
palette **index 0**. `map_sprite_tool.recolour` was written against that and assumed it. FE-Repo
community sheets do not follow the convention: they ship on a green key, **`#80a080`**, and
their index 0 is an ordinary colour. Ravisin's donor is exactly that — index 0 is a cream used
by **12** pixels, and the backdrop is **253** pixels of green at index 5.

Converting one as though index 0 were transparent turns the BACKDROP into a real cast colour,
and **nothing downstream notices**: geometry passes, the ≤16-colour check passes, the preview
looks correct because a preview paints index 0 as the page background whether or not the sheet
means it. It renders in game as a solid frame-sized block with the art inside it. Nicolas did a
full palette pass against that broken baseline before anyone spotted it.

Two closures, because detection and prevention are different failures:
- **`_transparent_index` detects the key** — a sheet carrying `#80a080` is a community sheet and
  that colour is never part of the art; otherwise index 0, unchanged for every vanilla donor.
- **`sheet_info` rejects a finished sheet with no index-0 pixel at all.** Always wrong, invisible
  to every other check, and one line to catch.
- **`recolour` asserts transparency lands EXACTLY on the donor's key pixels** — the set, not the
  count. This is the guard that matters, and the weak version above is why: the first shipped
  sheets passed "has any index-0 pixel?" with 265 legitimate background pixels while carrying
  **holes punched clean through Ravisin's face**. Recovering the palette work after the green-key
  discovery re-derived the donor→cast map by voting on surviving pixels, and the 12 cream
  face-highlight pixels — already wrongly zeroed by the botched first repair — had no votes left,
  so they fell through a `.get(v, 0)` default straight back to transparent. **A colour may map to
  0 only if it IS the key.** A default of "transparent" for an unmapped colour turns every
  recovery mistake into a hole; the fallback is now nearest-cast-colour, and the invariant is
  checked rather than trusted.

Also fixed, because it is what forced the conversion to be hand-rolled twice: `recolour`
validated its output against a donor resolved from the INPUT FILENAME. That works for a vanilla
sheet and is impossible for a vendored one — `Druid Hoodless (F) {Ultra-Fenix, Velvet Kitsune}`
is in no wait table, so the tool exited on every community sheet it was handed. It now takes an
explicit `donor=` and falls through to inference when there is no decomp row to check against.

**A donor is read for FRAME SIZE only — and `pattern` is not a frame count.** The wait row's
first field is `pattern`, which `unit_icon_data.h` itself calls unused. It was briefly read here
as a frame count, which is the very misreading this ADR warns about one paragraph up: Eirika Lord
carries `0`, the Druid `2`, the Bonewalker `3`, and **all three sheets are 16x48** — three frames.
The count comes from the sheet HEIGHT and from nothing else.

That correction matters, because the conclusion drawn from the misreading ("frame count doesn't
matter") is **unsafe**. `ApplyUnitSpriteImage16x16` (`bmudisp.c`) loops `for (i = 0; i < 3; i++)`
unconditionally, so a 2-frame 16x16 sheet is read past its end — and `sheet_info` used to accept
one. `_assert_frame_count` now rejects it. Ravisin's `base: Druid` is correct, and it is correct
because both sheets are three frames, not despite a difference that never existed.

### Ravisin's map sprite rides SCRIPTED_NEUTRAL_SPRITES, boss or not (2026-08-17, #25)

She is ch05's boss, not a neutral, but the table's name describes its ORIGIN rather than its
rule. What it actually serves is *a raw pid wearing our own art*, which `classed_cast` never
sees — the same reason her bust, name and stats are all bound explicitly off the ch05 YAML.
Without a row her pid falls through `GetUnitSMSId` to `CLASS_DRUID`'s stock sprite: the hooded
**man** she stopped being when her battle animation landed, with her own committed sheets sitting
unused. That is the white moose's #24 failure exactly, and `assert_custom_art_pid_wired` now
guards her pid the way it guards the moose's.

The **cast palette** is right for her on the table's own test — she never changes faction
(hostile from spawn, never recruited, never converted; her death ends the chapter), so leaving
the faction ramp costs nothing, and only the cast bank can hold the exact black robe /
near-white skin / auburn hair her battle anim was hand-edited to. The sprite was chosen
**hoodless** for the same reason the anim was: her bust has no hood, and the mismatch being
closed is a hooded man standing in for her on the map.

### An artifact is not its inputs — verify the FILE you are shipping (2026-08-14, #25)

The scene-3 review GIF was assembled three times. Two of those runs read the frame directory
before the scene was re-filmed, and one finished last and won the filename. The committed clip was
therefore a **pre-fix capture showing the exact defect the commit above fixed**, and it went onto
the PR that way; Nicolas caught it.

The source frames had been checked by eye and were correct. **Checking the inputs is not checking
the output.** Verify a review artifact by decoding the artifact — for a GIF, iterate its own
frames — and be wary of the same output path being written by more than one job.

**The "one output path" half bit again, sequentially rather than concurrently (2026-08-19, #25).**
Every `recordenemy` run writes `/tmp/playtest-recordenemy`, **cleared at the start of each run**.
Filming Ravisin and then filming the moose before building her GIF destroyed the first run's
frames, and cost a re-run of a scene Nicolas had already watched — the most expensive thing in
this repo. **Build the artifact before starting the next run**, and treat a shared scratch path as
a resource with one owner at a time. It does not take two jobs racing; two jobs in sequence will
do it.

**And the third case, which the same rule covers: a REPAIR must be verified against the ORIGINAL,
never against the state the previous repair left.** Ravisin's map sprite shipped with holes through
her face because a recovery pass re-derived its colour map by voting on surviving pixels — and the
pixels it needed had already been zeroed by an earlier bad fix, so they had no votes and fell to a
`.get(v, 0)` default. Each fix was checked against its predecessor's damage and looked correct.

### An FEditor `L` is an authoring bracket, not an instruction (2026-08-08, #25)

Sahnar's Specter is the first vendored anim using FEditor's loop syntax — a bare `L` (`LOOPSTART {`)
closed by a `C01` (`LOOPEND }`) — and it crashed `parse_feditor` on `int("L")`. There is no loop
opcode in `banim_code.inc` to emit: vanilla encodes the same shape (frames after
`banim_code_call_spell_anim`, then the wait) as a **flat run**, see `banim_bgl_mg1_motion.s`. So the
`L` is dropped and its paired `C01` does the waiting. It surfaced only because the Specter's two
RANGED modes use it — modes a sword Myrmidon never plays, which is exactly the kind of thing that
would otherwise have sat unparsed until some later unit needed those modes.

### Arming the HP depletion is not LANDING it (2026-08-08, #25)

#24/#201 established that an imported mode which swings (C03) must ARM the depletion (C04/C05),
because the opponent's dodge mode waits bare on C01. Sahnar's Specter armed correctly and still
soft-locked combat: its mode 1 is `C03 C07 C04 ... C01` with **no hit code**, so it waits on a
depletion nothing ever started. The battle parks in `ekrBattleInRoundIdle` and every proc freezes.
Vanilla's own `banim_myrm_sw1` is the reference shape: `prepare_hp_deplete -> hit_normal ->
wait_hp_deplete`.

**Why it survived a green capture, a green gate and a review.** FE8 resolves damage in DATA
regardless of the animation — the foe dies, the HP bar is right, every frame looks correct, and
the hang only appears on the NEXT input. A one-round capture never asks for a next input. It took
filming FOUR rounds, then a control run on a known-good unit (Braulo 2/2, Sahnar dead at round 2),
to separate "my capture loop is wrong" from "this animation is broken".

**Mode 12 is exempt, and that exemption is the load-bearing part.** Slot 12 is `attack_miss`
(`ref_to_battleframe._MODE_ORDER`): armed-but-hitless by design, keeping C04 precisely so the
opponent's C01 still returns. Every anim we ship — Pinky, Lupin, Baxby, the wildling and
lizardzerker reskins — is shaped that way and correct to be. The first version of this rule
rejected all of them, and "fixed" Sahnar's mode 12 into a bug. **When a new lint fires on most of
the existing corpus, the lint is the thing that is wrong.** `test_every_shipped_anim_passes_the_
arming_rules` now runs the rule over every committed `.txt` so the next tightening is measured
against real assets, not fixtures.

### A donor row is completed for the CLASS, not for the unit that lands it (2026-08-08, #25)

Sahnar's anim is an import, so `BANIM_DONORS['myrmidon']`'s `motion`/`cadence` go unused for her —
which made "leave the cadence `None`" tempting. `test_every_melee_donor_names_a_known_cadence`
rejected it, and the test is right: the row is keyed by CLASS, so the next Myrmidon to take the
faked 3-pose path would inherit the hole. The `sword` cadence in `ref_to_battleframe._MELEE_CADENCE`
is therefore read off FE8's own `banim_myrm_sw1` (swing_short → hit → swing_shorter → step_heavy,
with the `slash_air` lifted from its critical mode, the only place vanilla gives the blade an arc)
rather than borrowed from the axe or lance rows.

**A green recruit's TILE is load-bearing, and getting it wrong has no symptom (#25).**
ch05's Basil is LOADed GREEN and CUSA'd blue by the opening's own join beat. The obvious tile for
her is the one her vanilla twin stands on — this chapter lifts *everything* 1:1 from FE8 Ch5, so
that is the habit — but Natasha is **BLUE** in `UnitDef_Event_Ch5Ally`, meaning her tile is now one
of our **nine PREP deploy slots**. A green body parked there silently costs the player a
deployment on a map whose difficulty is priced for the full cap, and nothing anywhere reports it.
Two more failures in the same family: an impassable tile makes the recruit untalkable, and a tile
walled off from the unit she must reach kills the set-piece with no symptom but a player who never
manages the Talk. `assert_green_recruit_placement` gates all three at injection time (deploy-slot
collision, passability, and a flood-fill to the target — the same fill
`assert_scripted_move_reachable` runs). Basil sits at **(5,15)**, the row-15 corridor at the
pocket's mouth, clear of all nine slots and of the four stairs.
_Decided: 2026-08-08 (#25, the ch05 recruit wiring)._

**Wiring a recruit and PROVING it are different jobs, and the passing scenario proved nothing.**
`ch05village` was green across every version of ch05's opening, including ones where Basil never
joined: it leaves Preparations with START and walks a *different* unit to a door, so a green shrub
nobody can command is invisible to it. The recruit chain needed its own gate, and `ch05recruit` is
it — three assertions in the order the player meets them: Basil is BLUE and commandable at turn 1
(the opening CUSA landed, the step with no other witness), Sahnar rises RED on turn 2, and Basil's
Talk flips her BLUE. It also gates the RECRUITER, not just the recruit: if the CHAR list named the
wrong talker the command menu simply has no Talk, and the chapter looks fine until a player tries.
**Its first run failed for the wrong reason, which is the lesson.** It reported "the CUSA did not
fire" when the CUSA was fine — the scene shows vanilla's 32-box `0x9CC` and my advance-dialogue
loop capped at 3600 frames, expiring 18 boxes in. *A loop cap must never be what decides failure.*
The fix is both halves: a budget with real headroom, **and** a verdict that tells "still running"
from "finished and still red", because reporting one as the other is how a wiring bug gets
invented and then hunted.
_Decided: 2026-08-08 (#25; the scenario caught its own author first)._

**DISPLAYING a vanilla message id you do not own is fine; displaying one another chapter WRITES
is not (#25 review).** ch05's scene labels read `slot: "vanilla 0x9C2"`, and those labels name the
chapter we **mine** (vanilla Ch5) — not the block we may write into. ch04 hosts on slot 5 and owns
`0x9BA..0x9C6` outright, so `0x9C2` in the built ROM is ch04's own no-parley ending. Pointing
Basil's join beat at it would have played Pinky and Marty discussing supper, in ch04's voice, with
ch04's faces — a green build, a passing `ch05recruit` (it reads factions, not text), and the wrong
scene on screen. The reliquary pattern is still correct and still in use: `0x9CC` and `0x9CD..0x9D0`
are written by NO hosted chapter, so the ROM holds vanilla's prose and borrowing it is exactly the
placeholder ADR. The two cases are indistinguishable at the call site — both are an int in a
constant — so `assert_message_id_unclaimed` now checks it instead of asking anyone to remember.
The join beat ships SILENT until the dialogue pass gives it an id from ch05's own block
(vanilla Ch6, `0x9E4..0x9F5`); a silent beat also keeps the script in vanilla's safe shape, since
one that continues with VISIBLE content after the prep prologue needs its own `FADU(16)` first.
_Decided: 2026-08-08 (found by `/code-review high` on PR #252, not by the build or the gate)._

---

**The village-raid race is four vanilla parts, and ch05 shipped none of them (#25)**
ch05 declared a race for its four reliquaries since #196 — *"the eruption's dead race the party
for the spread reward-sites"*, plus a save-all bonus — and nothing on the map could reach a site
or pay for saving one. What vanilla Ch5 supplies, and what we were missing:
- **The destruction hook is already in the macro.** `Village(eid, scr, x, y)` expands to the
  `VILL` on the door *and* a `LOCA(eid, 1, x, y - 1, TILE_COMMAND_20)` one tile north.
  `AiPillageAction` calls `StartAvailableTileEvent(x, y - 1)` (`cp_perform.c`), which lands on
  that second entry and flips the tile through the chapter's MapChange array.
- **A real event id.** `location_events()` hardcoded `Village(0, ..)`, and flag 0 is
  `EVFLAG_ALWAYS_FALSE` — `CheckChapterFlag(0)` returns 0 forever, so no visit was ever recorded,
  no raider hook was ever disarmed, and nothing could be counted. ch05 takes `EVFLAG_TMP(9..12)`,
  **not** vanilla's `8..11`: its opening already ends on `ENUT(8)` (`ENUT` is `EvtSetFlag`, a
  vanilla prep idiom from ch12a/ch18a — not an un-trigger) and the Sahnar Talk holds 7.
- **MapChanges, ordered ruins-before-doors.** Four 3×2 ruins at `(doorX-1, doorY-1)` then four
  1×1 closed doors, which is vanilla's own array. `GetMapChangeIdAt` keeps the **last** region
  covering a tile (`bmtrick.c`) and the 3×2 overlaps its own door, so doors-first would make
  *visiting* a site collapse the building. The 3×2 footprint is also not decoration: the pillage
  lookup happens at `(x, y-1)`, so a change on the door alone is never found.
- **`TERRAIN_RUINS_REGULAR` is the lost state**, and the choice is load-bearing. FE8 decides both
  "can a unit Visit here" (`CanUnitVisit`) and "is this worth pillaging"
  (`gTerrainList_LootableVillages`) from the terrain. `TERRAIN_RUINS_VILLAGE` — the
  obvious-sounding pick — is in **both** lists, so a site ruined into it would be lootable again.
- **Raider AI on every wave.** All six of vanilla Ch5's reinforcements carry
  `.ai = {0x0, 0x4, 0x9, 0x0}` (AI_B_04, `AiScr_AiB_PillageThenPursue`) and nothing else does.
  Ours spawn on those same three tile-pairs, so all three eruption waves raid.

**The prize is a Guiding Ring, and the "crest of cold iron" is retired.** Vanilla Ch5 has **zero
droppers** — Saar included — and its one relic is gated on all four village ids at the ending
(`SVAL(EVT_SLOT_3, 0x68)` → `GIVEITEMTO(CHAR_EVT_PLAYER_LEADER)`). The crest was our invention
(the promotion-seam foreshadow, May 2026): it had no item id in any table, and Ravisin carried it
on a `drops:` key the injector never reads, so it was decoration that read like wiring. Items are
vanilla's unless there is a reason — the Goodberry and Tourmaline are the only renames — so the
foreshadow is now a real Guiding Ring nobody is near using, earned by saving all four sites
rather than handed over for killing the boss.

**The race also has to be SAID.** Vanilla spends its turn-2 box on the raiders' intent ("steal our
way through this pathetic town"); ours said only that more dead were coming, so the first warning
the player got was the engine's "The village was destroyed." popup, after a site was gone.
The beat mined from vanilla `0x9C5` now names the reliquaries. Its YAML slot label is anatomy only:
ch04 writes literal `0x9C5` as its Status objective, while ch05 hosts through `Ch6Events` and writes
the warning at its own `0x9E4`. That id is named and registered in `HOSTED_CHAPTER_MESSAGE_IDS`, so
the ownership guard fails before any later scene can double-claim it. "Houses" and "mausoleums"
were both tried and both collide with the fiction: the west resident calls the whole tomb *"this
house"*, and only Orem is buried here.
_Implemented: 2026-08-11 (#260)._

**Two scenarios, because one run cannot walk both paths.** `ch05raid` idles and proves a site is
LOST (terrain `0x03 → 0x25`, no gift, event id still unset — `TILE_COMMAND_20` changes the tile
and sets nothing, which is exactly why a sacked site cannot count). `ch05crest` saves all four,
kills Ravisin, and proves the ring lands. Neither `ch05village` nor `ch05reliquaries` could ever
have seen any of this: they walk a unit to a door and read what it hands over.
_Decided: 2026-08-09 (Nicolas: "we do what vanilla does"; all three open questions answered by
mining vanilla Ch5 rather than by choosing)._

---

**Playtest runs are the most expensive thing in this repo, and the human WATCHES them**
Nicolas, 2026-08-10, after a session that ran scenarios fourteen times: *"I am watching right now
as you run scenarios again and again... I am tired of it."* Two rules, because there are two
separate wastes and only one of them is about suite size.

**1. Run the smallest set that covers what changed.**
- Touched one chapter's constants → that chapter's suite (`SUITE=ch05`, ~11s cached).
- Touched an arbitrary subset → `matrix.py run --scenarios a,b,c`.
- Touched a SHARED helper (`location_events`, `collectedItems`, `village_script`, anything in
  `harness.lua`'s common section) → name the affected chapters' scenarios explicitly.
- **Do not run the full `make matrix` gate locally** (Nicolas, 2026-08-10: *"I dont want you to
  run the 7 min gate thing anymore"*). The verdict cache below now means a green scenario whose
  inputs are unchanged does not re-run — but it keys on `rom_input_hash`, so any
  `build_campaign.py` or campaign-data edit invalidated every row. Phase 2 scopes that to what
  the build actually wrote (a ch05 edit: 6 of 20). **The ban is permanent — it is a habit, not
  a feature waiting to be built.** #255 closed 2026-08-13 having deliberately dropped the code
  that would have retired it: what replaces the gate is "run your chapter's suite while
  developing (ch05 = 6 scenarios, one ROM build), never the gate". A scenario audit found
  nothing to retire either — 98 scenarios, and the gate's 20 are a curated union of the ch01
  spine + `recordunitlist` + ch04 + ch05, each pinning a distinct engine hook. The real problem
  is GROWTH (~6 per chapter), which scoping addresses and deletion does not.
  CI cannot take the gate either: CI builds against a MOCK base ROM
  (`head -c 16M /dev/urandom`), because the real FE8 ROM is copyrighted and not in the repo, and
  random bytes do not boot in mGBA.
- **`matrix.py run --suite X --dry-run` costs nothing and says what would actually run.** Reach
  for it before deciding a run is needed at all.
- **Never after a merge.** CI has already built and checked; a run whose result cannot change a
  decision is pure cost. If the result would not change what you do next, do not run it.
- The chapter suites are a SINGLE SOURCE and they go stale: `ch05` still listed `ch05village`
  alone long after three more ch05 scenarios landed in `gate`. Adding a scenario means adding it
  to its chapter suite too, not just to `gate`.

**2. When a scenario fails, spend ONE run learning, not one run per guess.**
This is the expensive half and it is not about suites. `ch05crest` failed four times in a row,
each run revealing exactly one blocker — a hidden striker, then a missing melee weapon, then a
combat wait that never ends — because each run only logged enough to test the hypothesis in hand.
All three were visible in the same memory at the same moment. The rule: on the first failure,
dump the whole neighbourhood of state the next three hypotheses could possibly need (every
candidate unit's `state`, its grid cell, its weapon range, whether the engine calls the action
legal), read it, then fix everything it shows. `inspect_state.py render` is the first stop, not
the last. A generalisation of the standing rule "do not re-run to re-test a hypothesis the
evidence already killed" — re-running to test a *new* hypothesis one at a time costs the same.

**3. A beat at the END of a long scene gets a DEBUG BOOT before it gets a film.**
Nicolas, 2026-08-15, stopping a run himself mid-scene: *"you're filming the wrong scene... that's
the chapter intro not the moose thing we're working on."* ch05's scene 7 is the last beat of a
~52-A-press opening, so `recordch05join` replayed four backdrop scenes, Preparations, the join
and Sahnar's monologue — **4m33s of footage he had already signed off — to reach ten seconds of
moose.** Three times. The rules above are about which scenarios to run; this is about what a
single run costs before it reaches the thing under review, and it is the same waste wearing a
different hat.

The fix is a boot that LANDS on the beat: `--ch05-moose` replaces the whole beginning scene with
scene 7 and the two LOAD1s it cannot do without, so New Game → title → chapter intro → the beat.
**4m33s → 34s**, and iteration becomes compile-time only. It is cheap — the block was already
factored (`ch05_moose_charge_block`), so the debug script is that call plus `LOMA` — and it
should be built BEFORE the first film of a late beat, not after the third.

Two things to get right, both learned by getting them wrong:
- **`bootToMap()` is the wrong driver on a debug boot**, because it drives to `player_map_idle`
  and on such a ROM the beginning scene IS the beat — so it mashes A through the whole thing and
  hands the film an idle map (measured: 3000 frames of nothing). Stop at `chapter_intro_input`,
  spend its one press, and let the film open on the `FADU` so the camera move and the hold are
  in shot.
- **The debug flag must not touch the shipping script.** `--ch05-moose` is a branch at the top of
  `ch05_beginning_script` and nothing else; a test asserts the real opening still carries prep
  and scenes 5–7.

**4. `run.sh` does not BUILD, and `make` can inject without relinking.**
Two runs on 2026-08-15 were spent on a ROM ten minutes older than the change under test, and
Nicolas reported the truth both times — *"sounded like the same rumble"*, then *"nothing changed
in that last run"* — because nothing had. `matrix.py` builds and then runs; `run.sh` only runs,
and reaching for it directly (to get `PT_SOUND`) silently tests the previous binary. `check-rom`
could not see it: the FLAGS matched exactly, only the code was stale.

Worse, the obvious fix hides a second trap. `make` re-ran injection and did **not** relink — the
ROM was three minutes older than the sources it was supposedly built from — and the check that
"confirmed" the sound was in it grepped the injected `ch6-eventscript.h`, i.e. an INPUT to the
build rather than its output. That is "an artifact is not its inputs" one layer down.

`run.sh` now refuses when `build_campaign.py` or `campaigns/**` is newer than the `.gba`, naming
the offending files. Verify a ROM against the ROM.

**5. Which ID SPACE a sound comes from, before which sound.**
FE8 has ~340 sound effects and names about sixty of them, so a cry has to be chosen by number.
There are two numberings and they do not agree. `banim_code_sound_*` (banim_code.inc) encodes
`0x850000XX` for BATTLE ANIMATIONS, and XX is not a song id; `SOUN`/`EvtPlaySong` takes a song
id, whose only definition is the ORDER of `sound/song_table.s`. Reading the first as the second
put `se_sys_hp2` (an HP-bar tick), `se_sys_bikkuri_mark1` (the "!" popup) and `dummy_song` in
front of Nicolas as monster roars — four auditions, each a ROM build and a watched run, before
the mismatch surfaced. He described one as *"the silliest little animal noise"*, which was
exactly right: it was a menu blip.

`tools/sfx_preview.py` renders any sound to WAV straight from the decomp -- song table ->
song `.s` -> voicegroup -> `direct_sound_samples/*.bin`, resampled by the interval between the
note the sequence plays and the sample's base key. No ROM, no emulator; `--html` writes a page
with play buttons. Picking ch05's bellow went from a build-and-watch per candidate to one page
and one listen. Noise/square-channel effects (ch05's own rumble is one) have no sample to export
and are reported as skipped rather than approximated.

**6. Nothing in the gate listens.** ch05's bellow shipped through four films with
`MUSCMID(SONG_SILENT)` where a DUCK was meant. That command fades the silent song IN -- it
replaces the BGM permanently -- so the chapter would have run from turn 1 to the boss in silence.
Every scenario passed, `verify_text` passed, every film looked right. It surfaced because Nicolas
asked whether the music comes back. The pair is `MUSI`/`MUNO` (`EvtSetVolumeDown` /
`EvtUnsetVolumeDown`), which ch05's reliquary visits already used. Audio is un-gated by
construction; `PT_SOUND=1` at least makes a run audible on purpose.

The wider rule this instantiates: *the fast-boot idea is not ch05's*. `TESTCH` and `--lord-boot`
are the same move for the test chapter and the lord-select screen. Any feature whose screen is
hard to reach should get one first — save-states do not substitute (they are invalid across code
changes) and `PT_FPS=240` is only a fallback.

_Decided: 2026-08-10 (Nicolas)._

**A green scenario whose inputs are byte-identical does not re-run. That is a build-system
problem, not a policy one.** `make` does not recompile clean objects and `bazel` does not re-run
cached tests; our matrix re-ran everything because the invalidation logic was never written, so
the only two options on the menu were "run all 17" and "a human picks by judgment" — and the
human picking is what kept failing. The scenario COUNT should keep growing (17 → 30 as chapters
land; capping it means deleting proof). What must stop growing is the number that EXECUTE.

**The soundness rule, which is the entire licence to skip.** A verdict is a pure function of the
ROM it boots, the scenario's own Lua, the harness helpers it transitively reaches, its
`matrix.yaml` entry, and the driver around it (`controller.lua`, the dofile'd modules, `run.sh`).
If all of those are byte-identical a PASS cannot become a FAIL. **A FAIL is never cached** — a
flaky red must always re-run; only green is skippable. Anything that cannot be pinned (no decomp
HEAD, a scenario `harness.lua` does not define) returns no key at all, and no key means no cache:
unknown is conservative, never optimistic.

**Do NOT hash `harness.lua` as a whole file.** It is one Lua chunk and nearly every task edits it,
so a whole-file hash invalidates all 17 scenarios on every commit and the cache never hits — the
feature becomes theatre. The granularity is the scenario's transitive helper CLOSURE, which
`check.py`'s blind-press gate already needed and which now lives in `matrix.py`
(`harness_functions`/`reaches`) with the rest of the code that reads harness.lua.

**What makes the closure sound is `harness_shared`, and this is the part that is easy to get
wrong.** Chunking by top-level function charges each chunk to the function that OPENS it, so
top-level data declared between two helpers — `TUNE`, `CALLBACK_NAMES`, the constants — is
glommed onto whichever helper happens to precede it. That data feeds every observation, so a key
built from a closure alone would miss an edit to it and serve a stale PASS. So the file is
PARTITIONED instead: each chunk is a function body (closure-attributable) plus a residue after
its column-0 terminator (shared by everyone), and a chunk with no terminator — a one-line
`local function yield() … end` — is unattributable, which means shared, never dropped. Verified
against the real 8,124-line harness: editing another scenario or rewording a comment holds the
key still; editing the scenario's own body, a helper it reaches, `TUNE`, `CALLBACK_NAMES`,
`controller.lua`, or its manifest entry all move it.

**Five more things belong in the key, and code review found every one of them.** Each is a
way for two genuinely different runs to collide: the ambient `PT_*` knobs `run.sh` passes into
the wrapper (`PT_SEED=7 … fuzz_ch01` would otherwise be served the seed-1 PASS — kept in sync
with `run.sh` by a test, because a hand-kept list rots and rotting *here* means a stale green);
a checkpoint-backed scenario's `ckpt_X` builder, which `run.sh` invokes directly so nothing in
Lua reaches it; a helper passed as a VALUE rather than called, which escapes a call-graph that
only follows `name(` (the closure now follows MENTIONS — median 58 → 66 of 237 functions, and
over-reaching only ever costs a re-run); `record`/`diagnostic` scenarios, which must never be
skipped because they exist to REFILL `/tmp/playtest-<name>` that `make_gif.py` then reads; and
the generated `symbols.lua`/`procscr.lua`, which are excluded because `run.sh` rewrites them
*after* the fingerprint is taken — hashing them cost two re-runs per engine change before the
cache converged, and their content is already implied by the ELF and by `gen_symbols.py`.

**The ROM cache had to cache the ELF too, and finding that is why the verdict cache's key is
trustworthy at all.** The key assumes identical ROM inputs imply identical symbols. That was
false: `restore_cached_rom` copied `fireemblem8.gba` and the build stamp but not
`fireemblem8.elf`, while `gen_symbols.py` reads the ELF to emit the tables the harness
dofiles — and the boot flags MOVE symbols (a ch05boot ELF and a canonical ELF disagree on 58
of the names the harness reads: `gUnitLookup`, `gItemData`, `Menu_OnIdle`, …). The gate spans
four ROM configurations, so a warm run restored three of them against the previous config's
symbol table and read the wrong memory — a live bug since the ROM cache landed, and one that
presents as unexplained flakiness rather than as anything pointing at the cache. The slot is
now `.gba` + `.elf` + `.json`, restored all-or-nothing, because half a slot is worse than
none. 44 MB per configuration, against a debugging session that finds nothing.

**A fresh RED always evicts a stored green.** Same key, different verdict, means the stored
green is now a lie, and leaving it makes the next run report a scenario green while it is red
right now. `run.sh` evicts too, because a scenario run DIRECTLY — which is how debugging
happens — never passes through the matrix. `MX_NO_CACHE=1` still evicts on a failure: bypassing
the cache must not become a way to fail a scenario and leave the lie in place.

**A cached green must never read as a fresh one**, so the table carries a `source` column
(`ran`/`cached`), the summary says `N ran, M cached`, and the run's log and screenshots are kept
beside the verdict — `/tmp/playtest-<name>` will have been overwritten by whatever ran last, and
a cached green nobody can look at is a green nobody can audit. `--no-verdict-cache` / `MX_NO_CACHE=1`
opts out. A group with nothing left to run is never BUILT, which is where the biggest saving is: a
doc-only or harness-only change costs no `make` and no emulator at all.

**Phase 2: the build attributes its own writes, and a ch05 edit stops re-running the
prologue.** Measured on the real gate, for a one-line ch05 enemy-level change: **6 run, 14
cached of 20**. The same edit under phase 1 alone re-ran all twenty, because
`rom_input_hash` cannot tell a ch05 edit from any other. `tools/build_scopes.py` watches the
decomp while `build_campaign.py` runs and records, per injection step, the files that step
actually wrote plus a digest of their contents; `matrix.py` keys each scenario on just the
scopes it depends on.

**Derived, never declared.** A step's scope is read off its own function name
(`inject_ch05` → `chapter:ch05`), and its file list is what the filesystem says it wrote —
not a table anybody maintains. Hand-kept impact maps rot silently and let real regressions
through, which is the exact failure this feature exists to prevent.

Three rules make it sound, and all three are the conservative direction:

- **A file written by more than one step belongs to EVERY step that wrote it.** This is the
  subtle killer. Nine shared tables (`chapter_settings.json`, `data_8B363C.s`,
  `src/events_udefs.c`, …) are written by both the global passes and ch05. Blaming the last
  writer would charge them to ch05 alone, and a portrait edit would then move only ch05's
  digest while every global scenario was served a stale PASS.
- **Unattributable means `global`.** Writes between steps, writes outside the walked roots
  (reconciled from git's own view of the decomp at the end), and any step whose name does
  not identify exactly one chapter — `chain_ch04_to_ch05` names two — all land in `global`,
  which every scenario depends on.
- **A scenario's chapter dependency comes from where it ACTUALLY WENT, not from a field.**
  The first cut read `matrix.yaml`'s `host_chapter` as the last chapter played. It is not —
  it is the harness's `PT_HOST_CHAPTER` hint and defaults to `1`, so `ch01win` boots at the
  prologue, plays into ch01, and declares `host_chapter: 1`. Reading it as an upper bound
  let ch01's map change without re-running the scenario that plays it: a stale PASS, caught
  in review. Every controller observation carries `world.chapter`, so a scenario's own log
  records its traversal; `matrix.py` stores that beside the verdict and scopes the next key
  to exactly those chapters. Cold (nothing observed yet) it depends on every chapter from
  its boot point FORWARD and converges after one pass. **Why trusting the observation is
  safe:** for a change to send a scenario somewhere new, that change must be in a scope it
  already depends on — a chapter it visits, or `global`, where the chapter-CHAINING steps
  live because their names name two chapters — so it re-runs and re-observes first. Slot
  numbers come from `tools/inject/hosts.py`, the file that ENROLS a chapter, so adding ch06
  is one line there and nothing in the matrix.

- **The scoped key still pins the ROM inputs no scope can see.** Everything else reaches the
  ROM as a file some injector WRITES, which the manifest observes — but the decomp's own
  sources are COMPILED (we patch only a handful), so a submodule bump touching an engine
  file no injector writes rebuilds the ROM and moves not one scope digest. `engine/` and the
  `Makefile` are the same shape. Those stay in the key as a narrow `engine_input_hash`;
  campaign data, which is what actually changes, stays scope-attributed.

**The manifest only exists AFTER the build**, which changes the shape of a run: a
configuration whose ROM inputs moved cannot be keyed on scopes until it is built, so
`execute()` asks the cache again *after* each build. Building can now REMOVE work rather
than merely precede it. Phase 1's "a fully cached group is never built" path still applies
whenever `rom_input_hash` hits, which is what keeps a doc-only change free. For the same
reason `--dry-run` says so out loud when a configuration changed: its listing is the coarse
answer, and most of those scenarios turn out cached once the build reports what it wrote.
The manifest travels in the ROM cache slot alongside the ELF, and for the same reason.

**Measured, and then re-measured properly — the first number was wrong.** An early pass
reported a ch05 enemy-level edit at 6 run / 14 cached. That measurement applied ONE ROM
configuration's manifest to every scenario; each configuration has its own, and they must be
built in the matrix's own alternating order. Driven through the real build by the
invalidation probe (`probe_invalidation.py`), the honest figure is **18 run, 2 cached** — chapter isolation
is far weaker than that first number claimed, because five whole-campaign tables are
rewritten by every chapter injector (see the line-level attribution note below). Recorded
with the error intact because a wrong measurement in an ADR is worse than no measurement,
and because the mistake — comparing keys instead of running the thing — is the reusable
lesson.

**Verified deterministic**: two consecutive identical builds produce byte-identical
manifests across all seven scopes. That matters because the attribution detects writes by
mtime, and a path set that churned would move a digest with no content behind it. A
config SWITCH does change which files get rewritten — that is real, and it is why the
measurement above compares two builds of the same configuration.

**What phase 2 does NOT buy.** Attribution is per FILE, so an edit to a chapter early in
the shared tables still moves the later chapters' digests: a ch02 enemy level moves ch02,
ch03, ch04 and ch05 (12 run, 8 cached) because every later chapter injector rewrites a
shared table that now carries ch02's bytes. The direction #255 asked for — a LATE chapter
edit not re-running everything before it — is the one that works, and it is the common case
while the campaign is built forward. Sub-file attribution would fix the rest and is a much
bigger lift with much more to get wrong; do not reach for it without a measurement saying
it pays.
_Decided: 2026-08-12 (#255 phase 2)._

**A cache can be right for the wrong reason, and only the artifact says which.**
The invalidation probe's `prologue` case went red in the most alarming way available: bumping
`level: 5 → 6` under the ch00 YAML's `enemy_units` — real, chapter-scoped content — moved **no**
scope digest in any of the four ROM configurations, so nothing re-ran. That is the exact
signature of a stale-PASS hole, and the manifest is precisely the wrong place to investigate it,
because the manifest is the thing under suspicion.

Settled by building the prologue ROM **twice**, edited and not: identical sha256. Then tighter,
by hashing all 20,263 files of the decomp tree after an injector-only run in each state: **zero**
differed. So the cache was correct, and correct for a reason nobody had written down —
`inject_prologue` emitted its two `UnitDefinition` rosters as **C literals**, under a comment
that said "Positions/levels/items from the chapter YAML". Only the boss's *weapon* was ever
wired (#52). Every literal matched the YAML by hand, so the chapter file looked authoritative
and the built ROM agreed with it; a rebalance authored in YAML would simply never have shipped,
with no symptom anywhere. The same three levels were hardcoded a **second** time in step 4b's
`guest_patch` (`baseLevel` in `data_characters.c`), so the two encodings of one number could
have drifted apart as well.

`_prologue_roster_blocks` now sources levels, positions, the guard head-count and the enemy
weapons from the chapter YAML, and `guest_patch` reads the same field the roster does. The
rewiring was verified **byte-neutral** — same ROM sha256 as before the change — which is the
proof that it is a plumbing fix and not a balance change. The probe is now green at **7 run, 13
cached**: the prologue is *hosted on chapter 1*, so `ch01`, `ch01win`, `controller_turn`,
`gameover`, `lordfloor`, `retreat` and `win` share its data and correctly move with it.

Three durable rules:

- **A comment claiming a value is data-driven is testimony, not proof.** This one had been
  false for months and read as true because the literals agreed with the data.
- **When the cache and the content disagree, the ARTIFACT arbitrates.** Two builds and a
  byte-compare cost ten minutes, need no emulator, and cannot be argued with. Reasoning from
  the manifest would have "confirmed" whichever answer was reached first.
- **A red probe case is worth more than a green one, and the fix is upstream more often than
  it looks.** The expectation was right (`win` *should* re-run on a prologue edit); what was
  broken was the pipeline that made it true. Adjusting the expectation would have closed the
  ticket and left the bug.
_Decided: 2026-08-13 (Claude, #255; the probe's first genuine catch)._

**WHEN a scope is hashed is the whole feature. Hashing at the end of the build undid it.**
Sticky ownership re-hashed every inherited path in `finish()` — after all steps had run. Every
chapter injector rewrites the same five whole-campaign tables, so by the end of the build that
shared file holds the LAST chapter's bytes, and `finish()` charged them to ch04, ch03, ch02 and
ch01 alike. Editing the chapter under development therefore re-ran the whole campaign's
scenarios: the measured **18 of 20**. The path-set churn the stickiness was added to fix was
real; hashing at the wrong moment quietly gave the win back.

Each scope is now fixed to the moment its own step ended (`_claim` → `_freeze`), and the
previous manifest is seeded in `__init__` rather than merged in `finish()`, because seeding
after the fact is what forced the late hash. `global` is the deliberate exception — it means
"the whole build", so its reference point is the end of it.

This is the direction that matters for how the campaign is actually built: **forward**. A ch05
edit no longer moves ch04's digest, because ch04's claim happens before ch05's step writes
anything. The reverse (editing an early chapter) still invalidates the later ones, and that is
correct-but-coarse — the shared table genuinely does carry ch02's bytes into ch05's copy. Fixing
that needs sub-file attribution, and the note above still applies: do not reach for it without a
measurement saying it pays. Editing ch02 while building ch06 is not the common case.

Cost measured in the profile: `_freeze` is 0.165s of a 70s injection, and the whole scoping
machinery 1.8s, nearly all of it the `stat` walks that were already there.
_Decided: 2026-08-13 (Claude, #255 phase 2 follow-up)._

**The playtest cache was never the biggest drag; the INJECTOR is.** Profiling
`build_campaign.py` to settle an unrelated question showed where a build's time actually goes:
of a 63s `make`, the ARM compile is **12s** and the Python injection is **51s**. It is paid on
every build whether or not a playtest ever runs, and it is single-threaded. `cProfile` (70s under
profiling overhead) puts almost all of it in two places, both of which look fixable without
touching what the injector produces:

- **`ref_to_battleframe._cell_is_empty` — ~28s, via 11 MILLION `PIL.Image.getpixel` calls.**
  180k invocations walking cells pixel-by-pixel in Python. `getpixel` per pixel is the classic
  PIL antipattern; a numpy view or `getbbox()` over the crop answers the same question in bulk.
- **YAML parsing — ~22s across 534 `safe_load` calls**, of which `_load_chapter_yaml` alone is
  9s over 62 calls, i.e. the same chapter files parsed dozens of times per build. Memoizing by
  path+mtime and using libyaml's `CSafeLoader` are both small, local changes.

Recorded here because the lesson generalises past this repo: the scenario cache was optimising
*how many scenarios re-run*, which is the visible cost, while a fixed 51s tax sat on every build
unmeasured. **Profile the thing everything waits on before optimising the thing that waits.**
_Decided: 2026-08-13 (Nicolas + Claude; measured, not estimated)._

**Honest ceiling of phase 1 alone, kept because it explains why phase 2 exists.** Keying on
`rom_input_hash` means any
`build_campaign.py` or `campaign.yaml` edit invalidates every scenario, and nearly every feature
task touches `build_campaign.py`. This phase buys doc-only changes, harness-only changes, and
repeat runs while debugging something else. Phase 2 — having the build attribute its own writes
per scope (`global` / `chapter:N`) so a ch05 edit stops re-running the prologue — is where the
ceiling lifts, and it must be DERIVED at build time from what the builder did, never a
hand-declared impact map: hand-maintained maps rot silently and let real regressions through,
which is the exact failure this exists to avoid.
_Decided: 2026-08-12 (#255 phase 1; measured: a repeat `--scenarios ch05arena` went 10s + 1 build
to 0s + 0 builds)._

**Reading a VANILLA tileset's art: the committed object sheet is an INVERTED grayscale PNG**
`map_tileset_tool.Tileset` wants `.4bpp` + `.gbapal` + `.bin`. For our vendored tilesets those
three files are the committed source. For a *vanilla* tileset they are build artifacts and are
not in the decomp's HEAD — what is committed is `graphics/map/ObjectTypeN.png`,
`graphics/map/MapPaletteN.pal` and `graphics/map/TileConfigurationN.bin`. Rebuild the other two:

- `ObjectTypeN.png` is 256x256 **mode-L**, and its gray levels are the 4-bit index **inverted** —
  white is index 0, black is index 15, so `index = 15 - (gray // 17)`. Pack it straight and you
  get a picture that looks plausible (coherent shapes, wrong hues) rather than obvious garbage,
  which is exactly how it survives a glance. Rebuild the mode-P form and hand it to
  `convert_object_png`; do not write a second packer.
- `MapPaletteN.pal` is JASC-PAL, 160 colours = the 10 banks x 16 the `.gbapal` holds.
- The chapter's three asset names come from `vanilla_layout_tileset_assets(dec, layout)` — asset
  table proximity is NOT authoritative (that docstring says why). Vanilla Ch4 is
  `ObjectType1 / MapPalette1 / TileConfiguration1`.

**Verify by byte-compare, not by eye**: pack the sheet and assert it equals the decomp's own
built `ObjectTypeN.4bpp`. That check is what caught the inversion; the render alone did not.
An instance of "verify via data, not pixels" pointed the other way — here the DATA is ground
truth for a question that *looks* like an art question.
_Decided: 2026-08-10 (Claude, while surveying the snag family for #24)._

**A wash-out is a CHROMA failure, and our checks all measured luminance**
Two Arena palettes were authored, shipped past every automated check, and were rejected on
sight — the combat coliseum and then the welcome exterior. Both preserved luminance faithfully
(the exterior's range even *widened*, 159 → 175) and both crushed saturation: the masonry went
from 0.29–0.74 down to 0.10–0.20 and stopped reading as stone. Nothing we assert on catches
that, because a palette test naturally reaches for "is it the right brightness."

Two durable rules came out of it:

- **Recolour work is expressed as a DELTA over vanilla, never as a replacement palette.** Name
  only the words that change; the build composes them over the base ROM's own bytes. A delta
  cannot wash out what it does not mention, and it preserves animated entries for free (the
  Arena backdrop cycles 3 of its 64 words — a hand-authored phase set has to reproduce that
  by hand and silently flattens it if it doesn't).
- **Assert what stayed VANILLA, not only what changed.** A proof that only checks the new
  colours arrived would have passed the rejected palettes too. `ch05arena` now anchors three
  untouched vanilla words per view alongside the ones it expects to move.

Artistically the same lesson: cooling *everything* reads as fog, not winter. Warm stone under
a cold sky is colder than cold stone under a cold sky, because the contrast is what carries it.
_Decided: 2026-08-12 (Nicolas + Claude, #265)._

**Composition needs the base ROM; config loading must not**
CI runs `make test` **before** it mocks `baserom.gba` (the mock exists only for the link check),
so anything a unit test reaches must not open the ROM. Making `arena_presentation_config()` —
a config loader consumed by `dressed_portrait_slots()` — compose palettes against vanilla took
eleven unrelated portrait tests down with it. Validation of campaign data stays pure; composing
against vanilla bytes is deferred to build time. Assert on the *delta* in tests: it is ROM-free
and a stronger statement about the YAML than the composed result is.
_Decided: 2026-08-12 (Claude, #265)._

**Reading a vanilla BG asset offline: `tools/rom_bg_preview.py`, and TSA is not always LZ77**
Every backdrop we recolour is a plain `.incbin` from `baserom.gba` at a fixed offset, so the
exact pixels the GBA would draw can be reproduced in milliseconds with no build and no emulator.
`rom_bg_preview.py` does that, and its `--index-map` / `--isolate` answer the question a palette
edit must answer first: *which index owns this thing, and does anything else share it?* Use it
before touching a palette; spend the one in-engine run confirming the answer, not finding it.

Two traps it encodes, both settled from the decomp rather than by guessing:

- **The TSA palette nibble is RELATIVE** (0..3), not the hardware bank. The engine chooses where
  the four banks land — `gPaletteBuffer + 0x60` → banks 6..9 for the combat backdrop,
  `ApplyPalettes(..., 0xC, 4)` → banks 12..15 for the exterior. Index with the relative value,
  report with the hardware one.
- **Not every TSA is compressed.** `CallARM_FillTileRect` takes a raw blob, and `TmApplyTsa`
  (`asm/arm.s`) settles its shape: the loops are INCLUSIVE (the stored bytes are width-1 and
  height-1) and it fills BOTTOM-TO-TOP, so the TSA's first row is the screen's last. Getting
  that wrong renders a sheared picture that looks like a decode bug in the image data.
_Decided: 2026-08-12 (Claude, #265)._

### The injector was slow in Python, not in work

`build_campaign.py` was 50s of a 64s `make` — paid on every build, whether or not a playtest
ever ran. None of it was the work it does; all of it was the shape of the loops doing it. Three
fixes took it to 18s (`make`: 64.5s → 21.0s) with the ROM **byte-identical**:

- **Per-pixel PIL is the antipattern that costs the most.** `_cell_is_empty` asked
  `getpixel` 11 million times whether a cell was transparent, re-entering PIL's pixel-access
  machinery on every read (~28s). The alpha band reshapes into `(rows, TILE, cols, TILE)` and
  answers the whole image in one `any()`. `nonzero()` walks row-major, which is what keeps
  tiles emitting in the original order — the ordering is the part a rewrite here can silently
  break.
- **Parse each YAML once, and parse it in C.** PyYAML's pure-Python scanner walks a document
  one character at a time (6M `reader.forward` calls, ~22s); libyaml's `CSafeLoader` builds the
  identical documents an order of magnitude faster. Separately, injectors re-parsed the same
  handful of chapter files 62 times because each wanted one line, so `_load_chapter_yaml`
  memoizes on path + mtime + size. **It hands back a deep copy**: several injectors edit the
  dict they are given, and a shared parse must not leak one injector's edits into the next
  one's view.
- **The remaining per-pixel loops** (`_load_frame`, the swatch strip) vectorize the same way.

**The negative result, so nobody re-attempts it: `getcolors(1 << 24)` is load-bearing.** PIL
sizes the histogram from `maxcolors`, so that bound costs a fresh multi-megabyte allocation on
every call — 42ms per frame against 0.15ms at `1 << 16`, 8.6s of the injection. It cannot be
tightened, because **getcolors returns colours in hash-bucket order and the bucket count comes
from `maxcolors`**: a smaller bound reorders the palette, which reorders every sheet index with
it and moves ROM bytes for no visual change. The trap is that it looks safe — a single
7-colour frame compares equal both ways. Baxby's 5-frame set is where `(112, 80, 128)` jumps
five slots. Buying the 8.6s back means accepting a new palette order and re-proving the anims
in-engine, which is a playtest this repo does not want to spend.

**The acceptance test for injector performance work is a byte-compare, and it is cheap.** These
changes are meant to be output-identical, so the proof is `shasum -a 256
fireemblem8u/fireemblem8.gba` matching the pre-change build — no emulator, no playtest. Cheaper
still when bisecting a difference: run `build_campaign.py` alone and hash the files it wrote
into the decomp (tracked-modified + untracked), which names the offending artifact directly
instead of leaving you with one changed ROM hash. That is what identified the palette
reordering above. Do not accept a speedup that moves a ROM byte.

_Decided: 2026-08-13 (Claude, #274)._

### A battle anim binds to a CHARACTER, not to the cast (2026-08-15, #25)

The white moose is ch05's miniboss and the first unit to want a custom battle animation without
being a cast member. Every unit that had one before it rode a vanilla `CHARACTER_` slot, so
`inject_battle_anims` hardcoded its `_u25` binding as `[CHARACTER_<slot> - 1]` and read the slot
out of `PORTRAIT_MAP`. The moose has no such slot: it is the raw on-map pid `0xb9`, a
`gCharacterData` GAP, exactly like Ravisin at `0xb8`.

**The engine never cared.** `GetBattleAnimationId_WithUnique` reads
`unit->pCharacterData->_u25`, and that is the same field on a gap row as on a named one — the
gaps simply omit it, which defaults to `{0, 0}`, i.e. "no unique anim". The only thing standing
between the moose and a battle anim was the injector's marker STRING. So the fix is
`banim_u25_marker()`: a raw pid is addressed by `[0xb9 - 1]`, the identical designator
`raw_pid_portrait_data` has always written through, and a cast member still resolves to its
`CHARACTER_` enum. `RAW_PID_BATTLE_ANIMS` is the registry, and its unit declares `battle_anim:`
on the CHAPTER YAML that already owns its pid, class, AI and art — a `pcs/npcs` file would be a
second definition site and would put a miniboss on the deployable cast roster.

**The cadence is read off the donor's own script, never off a neighbouring row.** Nicolas chose
`clone_from: gwyllgi` for cadence, and the Gwyllgi's anim is `banim_cer_at1` (animId `0xB1`) —
internally "cer", for Cerberus. It is NOT `banim_mdg_at1` (`0xB0`), the Mauthe Doog's, which is
what Lupin's imported pounce reads; the two beasts are the unpromoted and promoted halves of one
line and vanilla gives each its own script. `cer_at1` runs growl (`mauthedoog_1`) → snap
(`mauthedoog_2`) → the shared contact hit → footfall away (`mauthedoog_3`), with **no screen
shake and no dirt kick**. The lance row's shake is the ARMOUR's weight; copying it onto a
quadruped would have been adapting a sibling row instead of reading the donor, which is the
exact mistake the sword row's comment was already written to prevent.

**The sandbox bench had a silent hole, and it is the same hole as #206.** `recordenemy` deploys
the TESTCH foes by CLASS, which is right for a class-level reskin and WRONG for a per-character
anim: a Gwyllgi deployed under the generic `0x80` monster charIndex plays the stock hound, so the
bench would have greenlit the opposite of what it was run for. The foe row now carries the
creature's OWN pid, and the scenario baits by pid rather than by class.

**The three-pose descale, for the next creature.** `--body 56` lands exactly the 88x64 the
injector's docstring names. `--noflip` because the master already faced left, like FE8's own
`cer_at1` sheet. No `--sharpen` (it grains a white flank) and no `--flat`: that palette is tuned
for warm hues and collapsed the blood-red antlers to tan — a chroma wash-out of the one accent
the creature is recognised by, which is the Arena palette lesson on a sprite.

_Decided: 2026-08-15 (Nicolas chose the donor; Claude wired it, #25)._

### A name needs a STRING, not a character slot (2026-08-15, #25)

ch05's white moose read **"Monster"** in combat, because a raw-pid gap's `nameTextId` points at
the generic monster message every `0xB0`-range gap shares — so it can never be retitled for one
creature. The reflex was the campaign's usual identity move: pick a collision-free vanilla
character and retitle ITS name message, the way Ravisin rides Riev. The obvious beast donor was
Morva, FE8's own Great Dragon.

**Nicolas stopped that, and the reason generalizes.** The roadmap has two dragons coming —
Arveiaturace in ch10 and the **Chardalyn Dragon** as a ch13–14 marquee boss — and Morva is the
best dragon identity in the game. Spending it on a moose would burn a named future for a string.
Worse, the fix he'd already rejected one step earlier was the same shape: renaming
`ITEM_MONSTER_HELLFANG` to "Antlers" would have cost every future Gwyllgi its weapon name,
because FE8 stores one name message per item id.

**The rule was already settled — for classes, in #90.** `campaign.yaml` says it outright: the
kobolds ride their OWN appended class ids "not a scarce vanilla ballista-empty… so
`CLASS_BLST_KILLER_EMPTY` stays free". The goblins took vanilla's dead ballista-empties; the
kobolds appended. Message ids are the same shape of resource: `gMsgTable[]` is generated from
`texts.txt`, `GetStringFromIndex` has no bounds check and there is no count constant, so a new
trailing header EXTENDS the table. The moose's name is `MSG_D4C`, appended past vanilla's last
id (`MSG_D4B`) and claimed in `HOSTED_CHAPTER_MESSAGE_IDS` like any other id ch05 writes. No
donor spent, and it generalizes: Messie and both dragons get names without paying a slot.

**So a donor slot is for BUSTS, and only for busts.** `RAW_PID_PORTRAITS`'s second element is
now either a donor slot name (Ravisin → Riev, dressed) or an int id we own (the moose, named and
undressed), and `portrait_id` may be None. `dressed_guest_slots` skips name-only units so a PNG
sitting in `portraits/` cannot silently dress a slot — which is exactly how the moose would have
picked up the retired full-body Wyrdeer bust. **An asset on disk is not a decision to ship it.**

**And the weapon was a real defect, spotted off a combat frame.** The moose deploys as
`CLASS_GWYLLGI` but carried `ITEM_MONSTER_ROTTENCLW` — the REVENANT's claw, which is why ch04's
three Revenants hold it: a different creature's gear entirely. The first fix was `HELLFANG`, the
Gwyllgi's own, and it was class-correct but cost too much (see the parity ADR below). It now
carries `FIREFANG` — the Mauthe Doog's, and the Mauthe Doog is this creature's own unpromoted
tier (`data_classes.c`: `CLASS_MAUTHEDOOG.promotion = CLASS_GWYLLGI`). Same beast line, lower
tier: it answers the Revenant problem as fully as HellFang did, at 11.8 threat instead of 24.6.

**The correction worth keeping: "not currently wired" is not "never will be".** Twice in one
session an unused thing was treated as free to consume — an unreferenced item name, then an
unused character slot. The test is not "does anything use this today", it is "can I name a
future that wants it".

_Decided: 2026-08-15 (Nicolas; Claude wired it, #25)._

### `convertible` prices a fight the player declines — name the chapter after it and they won't (2026-08-15, #25)

ch05's white moose carried `convertible: true`, which in `difficulty.py` does two things: it
exempts the unit from the role-inversion check, and it applies `CONVERT_CLEAR_DISCOUNT` (0.5) to
clear-load. The YAML's own justification was that the objective is `defeat_boss`, so "the player
can win WITHOUT ever fighting the moose" — while admitting in the next line that it "is NOT
recruitable and never changes faction".

**Nicolas: the previous chapter is named "The White Moose".** A party that has just spent an
entire map hunting this animal is going to fight it. Half-pricing its clear-load models a game
nobody plays. `convertible` is for a unit that is *neutralized* — recruited, flipped, removed
from the fight — not for one the player is merely *permitted* to walk past.

**The flag was also masking a real warning, at BOTH weapons.** With it removed the model says
`boss ravisin (threat 8.4) is out-threatened by white-moose` — and that fires at the old Revenant
claw (14.1) just as it does at the Gwyllgi's Hell Fang (24.6). The role inversion predates the
weapon fix entirely; the exemption had simply been hiding it since #171. That is the cost of an
exemption flag: it does not just adjust a number, it switches off a check, and the check it
switched off was the one with something to say.

**And it restores the structure this very file already claimed.** ch05's roster comment has read
"Structure preserved: 16 line + 6 eruption reinf + 1 convertible (Sahnar) = vanilla's line 16 ·
reinf 6 · convertible 1" the whole time, while the model actually reported **15/6/2**. Sahnar is
ch05's one true convertible (Basil's Talk, the Joshua flip). Flipping the moose to `false` makes
the measurement match the design note: 16/6/1, the twin exactly. Aggregate cost is a rounding
error — clear-load/slot 4.5 → 4.7, chapter verdict still PARITY, full `--curve --check` green.

**The general rule: a modelling flag that says "the player won't do this" has to survive the
question "why would they not?".** If the answer is only "the win condition does not require it",
that is permission, not prediction — and the fiction, the chapter title, and the map's own
geography all vote the other way.

_Decided: 2026-08-15 (Nicolas)._

### One unit can BE the parity overage, and the band will hide it (2026-08-15, #25)

ch05 measured "PARITY (within band)" at threat/slot x1.20 with the white moose on the Gwyllgi's
own `HELLFANG`. Nicolas would not accept the verdict — *"I'm having a hard time understanding how
we realistically match parity with an extra monster"* — and the arithmetic says he was right:

| | Σ threat | /slot | vs vanilla |
|---|---|---|---|
| vanilla FE8 Ch5 (23 enemies) | 103.0 | 11.45 | — |
| ours WITHOUT the moose (22) | 99.5 | 11.06 | **x0.97** |
| ours WITH the moose (23) | 124.1 | 13.79 | **x1.20** |

**The moose was 20% of the entire force's threat and the whole overage.** Every other unit in the
chapter was already at parity. The verdict was true and misleading at once: `threat/slot` sums the
force and divides by the deploy cap, so one unit's 24.6 becomes +2.7 per slot and fits under a
±25% band with room to spare. `role_findings()` exists because this exact unit slipped through
once before; the aggregate learned nothing from that, because the aggregate cannot.

**Headcount parity is not force parity.** Both sides field exactly 23. We were not adding a body
— we were carrying vanilla's roster size with one slot holding a unit that hit 4x harder than
vanilla's hottest (24.6 against a 6.3 class-base ceiling).

**And the obvious repair moves the wrong dial.** Trimming trash to pay for a hot boss-adjacent
unit cuts CLEAR-LOAD, not threat: reavers 8→6 buys threat x1.14 but drags clear-load to x0.76,
and one more cut puts it out of band on the low side. A chapter cannot buy its way back to parity
by deleting bodies.

**The fix was the weapon, and it stayed inside the creature's own line.** `FIREFANG` is the Mauthe
Doog's, and the Mauthe Doog is the Gwyllgi's unpromoted tier — so the moose keeps its class, its
map sprite geometry, its doubling, and the distinct `cer_at1` voice, while dropping 24.6 → 11.8
and the chapter 1.20 → **x1.08** with clear-load unmoved at x0.84. Turn-1 pressure lands at 9.5
against vanilla's 9.0.

**The tool now says it for you.** `solo_contributors()` prints, under the verdict, any single
`count: 1` unit carrying =>10% of the force's threat and what the chapter measures without it —
the sentence that had to be computed by hand here. It is INFORMATION, not a gate: the two
obvious thresholds were both tried and rejected. A unit's SHARE barely moves when you
strengthen it, because it inflates the denominator too (ch05 read 16.4% with the shipped moose
and 17.2% with the rejected one), and leave-one-out by unit id just names whichever group has
the biggest `count`. It immediately surfaced ch03's Grell at **24% of its force** — a larger
share than the moose ever had, on a boss that also dies in 1.1 rounds (#284).

**Rule: when a chapter is at the edge of the band, ask WHICH UNIT is the overage before accepting
the verdict.** If one unit is a fifth of the force's threat, the band is not measuring parity, it
is absorbing an outlier. And the corollary for the metric itself: never quote a per-unit
class-base number next to a with-personal one — vanilla hides its named units' teeth in personal
lines (Saar and Joshua are both 6.2 class-base), so class-base flatters any unit whose danger
lives in class+weapon instead.

_Decided: 2026-08-15 (Nicolas)._

### The role check has to read the personal line; the aggregate cannot yet (2026-08-15, #25)

`role_findings()` collected each unit's `personal:` line and then used it for exactly ONE of its
three checks — boss durability, under the comment *"this is the one place the real article is
compared."* Its two THREAT checks ran on class base. That is defensible for the AGGREGATE (a sum
over 23 units, symmetric on both sides) and wrong for a check whose stated job is *"compare the
EXTREMES unit-to-unit"*, because FE8 puts a named unit's teeth in its personal line. Both halves
of the bias pushed the same way:

- **Our boss was understated.** Ravisin reads 8.4 class-base and 12.5 real, so the moose's 11.8
  "out-threatened" a boss that actually out-threatens it.
- **The twin's ceiling excluded the twin's own named units.** `max(vanilla_enemies())` is the top
  CLASS-BASE threat — 6.3, a generic Soldier — while vanilla Ch5 fields Joshua at 21.4. Measuring
  our named units against a bar built only from THEIR generics flags every named unit we field.

**A personal line reaches our units from two places, and the check knew one.** A raw-pid enemy
carries `personal:` in the chapter YAML (Ravisin); a CAST member deployed hostile carries it via
`BASE_DONOR`, written into its character slot by the build (Sahnar rides Joshua's, Lupin rides
Kyle's). Reading only the first made ch05's red Myrmidon measure **6.2** against the **21.4** she
actually fights at. `unit_real_article()` resolves both; `vanilla_threat_ceiling()` includes the
twin's named units. All three of ch05's standing warnings clear, correctly — and a true inversion
still fires, which is the guard test.

**The AGGREGATE stays class-base, and not for want of trying.** Measured both ways, threat
improves everywhere (ch01 x1.15→x1.08, ch03 x1.12→x1.03, ch05 x1.08→x1.04) — but CLEAR-LOAD
breaks on a real FE8 fact: **Saar's personal line puts him at Def 13 against the yardstick's 13
attack, so he takes zero damage and `rounds_to_kill` is infinite.** A ratio against infinity is
meaningless. The repo already has the mechanism (ch08 excludes "yardstick-proof units" from
clear-load), but applying it symmetrically re-baselines every curated chapter, and on the real
article **ch02's clear-load falls to x0.64 — out of band.** That is either ch02 genuinely
under-loaded with the class-base metric hiding it, or an artifact of the exclusion policy. It
needs its own investigation and its own issue; it is not a change to make in passing.

_Decided: 2026-08-15 (Nicolas asked why personal stats were being ignored)._

### A test below `unittest.main()` is not a test (2026-08-15)

`make test` — what CI runs — executes each file as a **script**, so `unittest.main()` collects
only what is defined by the time it is reached and then exits. In `tools/test_build_campaign.py`
that call sat at line ~4776 of a 5723-line file, and the **twelve TestCase classes below it — 88
tests, including all 26 of `Ch04Stage4Scenes` — had never run.**

**Nothing could have told us.** The file passed. The suite was green. `python3 -m unittest` still
collected all 490, so the two ways of running the suite disagreed in silence, and the only visible
symptom was a test count nobody had reason to compare. Every one of the 88 passed once enabled,
which is the point: this was not latent rot, it was 88 assertions we believed we had and did not.

The runner now lives at the end of the file, and `check.py check_every_test_actually_runs` fails
the build for any TestCase defined after it. Same family as
`check_verdict_scenarios_are_guarded`: **a green suite that is not measuring what it claims.**

Found while reviewing #25's branch for merge, from a 402-vs-490 discrepancy between `make test`
and `-m unittest` that was worth one command to chase.

_Decided: 2026-08-15._

### A skip guard must key on a symbol only WE write (2026-08-16, #25)

`test_the_live_ch05_group_deploys_our_table` asserts against the INJECTED decomp, and it
correctly carried a skip for a clean checkout — keyed on `struct ChapterEventGroup Ch6Events`.
**That is vanilla's own symbol.** It is present in a pristine tree, so the guard never fired, and
on CI — which runs `make test` before any injection — the assertion ran against vanilla data and
duly reported our roster pointer missing.

**Three separate things had to be true for this to stay hidden, and all three were.** The class
sat below `unittest.main()` and had never run (see "A test below `unittest.main()` is not a
test"), so the broken guard was never exercised. The symbol it tested was plausible — it names
the very structure the test is about. And **it could not fail on a developer machine**: any tree
that has run a build is injected, so the guard's flaw is invisible exactly where the tests get
run most. Waking 88 dormant tests and watching them all pass locally was not the evidence it
looked like.

**The rule: a guard that asks "has our injection happened?" must name something only WE emit.**
`MS_Ch05DeployCap` is ours — absent pristine, present once injected — and the fix was verified
in both directions (`git show HEAD:` vs the working tree) rather than assumed. Vanilla symbols
answer "is the decomp checked out", which is a different question and almost never the one being
asked.

**Corollary for reading the decomp at all.** Three of the other woken classes touch the decomp
and are safe, because they go through `vanilla_decomp_text()` (`git show HEAD:`) rather than the
worktree — the same rule as "Read decomp data through `git show HEAD:`, never the built tree".
A test that reads the WORKTREE is asserting about a build artifact and needs an
injection-keyed skip; a test that reads HEAD needs none.

_Decided: 2026-08-16 (found by CI on #286, after the dormant-test fix woke the class)._

### A boss on a vanilla SLOT already has its line — measure what deploys (2026-08-16, #284)

#284 opened on a measurement, not on the game: *"ch02's and ch03's bosses carry no personal
line, so they are naked class bases and fold in about a third of the time their vanilla
counterparts take."* Half of that was true. **ch02's was never wrong at all.**

FE8 builds a named boss as **class base plus a personal stat line** — vanilla Bazba is a L6
Brigand *plus* HP+5/Pow+3/Skl+4/Spd+2/Def+2/Res+2/Lck+1, and that line is most of why he reads
as a wall. Halvar **deploys on the Bazba slot**, and nothing in the build patches it (only
`PORTRAIT_MAP` cast slots get rewritten), so the ROM has been adding Bazba's line to him the
whole time. He fights at HP 29/Def 6 — **3.6 rounds, the bar exactly**. What folded in 1.2
rounds was `difficulty.py`'s model of him, which projected every enemy off naked class base
because it had no idea which character slot the unit rides.

**The tool knew two of the three ways a personal line reaches a unit.** `unit_real_article()`
read `personal:` in the chapter YAML (Ravisin) and `BASE_DONOR` for a cast member deployed
hostile (Sahnar on Joshua's). The third — an enemy deployed on a vanilla CHARACTER slot — had
no representation at all. `ENEMY_BASE_SLOT` is now that third source, and each entry points at
the constant the injector already builds the unit from, so the slot name is written once.

Verified against the **built** character table rather than by reading the injector, because the
question is what survives the build:

| our unit | slot | personal bases after injection | measured |
|---|---|---|---|
| ch01 `goblin-chief` | BREGUET | unchanged: HP+3/Pow+3/Spd+1/Lck+2 | 5.2 → **6.2 rounds** (bar 6.2) |
| ch02 `raider-captain` | BAZBA | unchanged: Bazba's full line | 1.2 → **3.6 rounds** (bar 3.6) |
| ch02 `raider-bruiser` | BONE | unchanged: HP+3/Pow+1/Skl+3/Def+1 | — |
| ch00 `sephek-kaltro` | ONEILL | **zeroed by the build** | 2.1 rounds (bar 2.2) |

**Riding a slot is not enough — the slot has to survive the build, and one does not.**
`inject_prologue` deliberately zeroes its guests' personal bases so they read as pure class
base, so Sephek is genuinely naked *despite* deploying on O'Neill's slot. Mapping him anyway
inflated his threat to **2.9x the Prologue's ceiling** and reddened CH0 — caught by the very
gate this issue added, on its first run. `PROLOGUE_ZEROED_GUEST_SLOTS` now names that exclusion
and an assert keeps it in step with the injector.

**ch03's grell is the one that was really wrong**, and for the opposite reason: it rides raw pid
`0xb7`, and a CharacterData gap is all zeros. It goes from 1.1 to **3.6 rounds** on an authored
line, HP 21/Def 3 → HP 36/Def 8.

**A `personal:` block is not injected by writing it.** `RAW_PID_PERSONAL_SOURCES` is what carries
one into the ROM, and it was a passenger inside the loop over `RAW_PID_PORTRAITS` — so a line
authored for a pid with no portrait binding would have been silently dropped, which is exactly
the grell's shape (it keeps the generic monster name plate on purpose). The two bindings are now
independent passes. Declaring the line in YAML and confirming the tool's number would have
"verified" a boss that never changed in the game: *a declaration is not art*, again.

**ch03 could not take any monster boss's line verbatim, and the reason generalizes.** Every
named monster in the decomp with a personal line (Maelduin, Cyclops, Wight, Deathgoyle, Gorgon)
is a **promoted late-game** unit, so all five carry Pow+5..+10. Applied to a ch03 boss they fix
durability and blow out threat — measured, at the Grell's own level: 9.6–20.0 against FE8 Ch3's
threat ceiling of **6.8**, every one of them tripping the outlier check. Dropping the Grell's
level does not rescue it (a L4 Deathgoyle line still reads 9.6). **A vanilla boss line is
calibrated against the party that faces it**, and lifting one across eight chapters imports that
calibration with it.

So the Grell takes Maelduin's **defensive half near-verbatim** (HP+15/Def+5 against its
HP+15/Def+4) and drops its offensive half. Maelduin is the decomp's one defensive monster boss,
which is what makes it the honest donor: durability was the deficit, offence never was. The
result is 3.6 rounds at HP 36/Def 8 — Bazba's bar exactly, and just inside Ravisin's 37/10 two
chapters later, so the boss curve stays monotonic. Threat is unchanged at 7.6, which matters:
the Grell hits RES with an Evil Eye in a chapter whose twin fields no magic at all, and that
hazard was a deliberate ch03 choice already shipped, not something to re-open here.

**The rule: a named boss is class base plus a personal line, and the line is what carries its
durability.** Where a level was bumped to fake one — the Grell's `level: 12` carried the comment
*"level holds boss pressure"* — the bump is offence, not survivability, and the two are not
interchangeable.

**No parity ratio moves, and that is not a bug.** The AGGREGATE resolves both sides off class
base on purpose, so a personal line is invisible to it: ch02 reads x0.79/x0.75 before and after,
ch03 x1.12/x0.99 before and after. **ch02 is `[locked]` and its lock needs no re-baseline** — the
numbers under the lock are byte-identical, so the "deliberate re-baseline, Nicolas's call" the
issue anticipated never arises here. That question belongs entirely to #285, which changes the
footing; measured on that footing the grell's line lands ch03 at x1.03/x1.00, near-centre.

**The audit the fix demanded.** Every boss was measured against its own twin's bar, on the real
article. ch00's Sephek (2.1 vs 2.2) and ch01's chief (6.2 vs 6.2) clear it — the chief on
Breguet's inherited line plus class Def 10, Sephek on class base alone against a twin whose own
boss is nearly as bare. **A personal line is the MECHANISM, not a checkbox**: a boss already at
its bar needs nothing, and the rule to write down is about the measurement, not about a required
YAML key. Two are open and belong elsewhere: ch06's Messie reads 2.7 against 12.9 but is
`status: planned` brainstorm seed, and ch08's ice troll is **undentable** (Def 15 vs the
yardstick's 13 attack) — the same `inf` that blocks #285, on our side of the table for once.
That one matters to #285 beyond ch08: the exclusion policy cannot be written as "a vanilla
quirk we tolerate" when our own content produces it too.

**The prologue is the mirror case, deliberately left alone.** Asked whether the guests need
lines to match a boss that got one, the measurement says the boss needs nothing (Sephek 2.1
against a 2.2 bar) and points at the player side instead. Vanilla's prologue pair splits in
half: **Eirika's personal line is Lck+5 and nothing else** — she is essentially class base, so
the zeroing costs Hlin nothing and her frailty is authored (`level: 3`, "the weak lead"). But
**Seth's line is most of what Seth is** (HP+7/Pow+7/Skl+9/Spd+5/Def+3/Res+5/Lck+13); stripped,
he falls from surviving 23.8 rounds to 5.5. Scramsax measures **5.7** — a Seth-analog Jeigan,
authored as one ("promoted prepromote — high stats despite low internal level (cf. Seth)"),
missing the line that makes a Jeigan one. Not changed and not filed (Nicolas, 2026-08-16): ch00
is `[locked]`, has shipped and been played, and this is the STATIC proxy, which assumes the
worst foe reaches a unit and cannot see that Hlin sits back at (8,5) while Scramsax stands
forward at (13,9). Recorded here so a prologue that ever plays wrong starts with the number.

**And the gate now reads what it had been printing.** ch03's paper boss shipped for months under
a green `--curve --check` because the aggregate sums the force and divides by the deploy cap, so
one soft unit dissolves into a 23-unit average — the same blind spot as *"One unit can BE the
parity overage"*, in the opposite direction. `role_findings()` had been emitting the warning the
entire time and **nothing consumed it**. `curve_gate_failures` now fails a `locked` chapter that
has an open role finding, and the curve prints the findings under the table. A chapter marked
balance-final with a per-unit check still complaining is a contradiction; the opt-in stays
per-chapter, so mid-authoring chapters warn without reddening CI. It earned itself immediately:
the bad Sephek mapping above was caught by this gate, not by review.

**The lesson under all of it: an issue's premise is a hypothesis too.** #284 stated a defect in
two chapters, with a measurement table, and the measurement was the thing that was broken. One
of the two chapters needed no content change at all, and authoring the "fix" it asked for would
have added a second source of truth for a line the slot already owns — agreeing with the ROM
today and free to drift from it tomorrow. Checking what the BUILT character table contains,
before changing content to match a number, is what separated the two cases.

_Decided: 2026-08-16 (#284; the grell's donor and sizing are new, ch02 turned out to need no
content change)._

### A zero is a cliff, not a measurement — the aggregate reads the real article (2026-08-16, #285)

The parity AGGREGATE projected every unit off **class base**, dropping personal lines on both
sides. That was defensible while it was symmetric, and it stopped being symmetric the moment
either side's named units mattered. Both halves are now the real article, and the change moves
every chapter *toward* 1.00:

| chapter | threat, class base → real | clear-load, class base → real | |
|---|---|---|---|
| CH0 | x1.23 → **x1.13** | x1.07 → **x1.00** | `[locked]` |
| CH1 | x0.89 → **x0.89** | x0.97 → **x0.97** | `[locked]` |
| CH2 | x0.79 → **x0.81** | x0.75 → **x0.79** | `[locked]` |
| CH3 | x1.12 → **x1.03** | x0.99 → **x1.00** | |
| CH4 | x1.15 → **x1.15** | x1.19 → **x1.19** | |
| CH5 | x1.08 → **x1.04** | x0.84 → **x0.88** | |

**ch02 never falls to x0.64, and finding out why is what unblocked this.** That number was
measured before #284, when the tool could not see a personal line inherited from a vanilla
CHARACTER slot — so ch02's boss contributed Bazba's line to the twin's side of the comparison
and a naked Brigand to ours. With `ENEMY_BASE_SLOT` supplying the third source, ch02 reads
**x0.79**, inside the band. The blocker was the same missing mechanism that opened #284, not a
content problem and not the exclusion policy.

**The undentable problem is real, and EXCLUSION was the wrong answer to it.** Vanilla Ch5's Saar
with his own line sits at Def 13 against the yardstick's 13 attack: exactly zero damage, so
`rounds_to_kill` is `inf`. The repo's existing mechanism dropped such units from clear-load —
and dropping them is not symmetric in practice, because the two sides do not field walls in the
same places:

| | class base | real article |
|---|---|---|
| vanilla Saar | 12.9 rounds | **excluded → 0.0** |
| our Ravisin | 2.9 rounds | **13.4 rounds** |

Ravisin was *deliberately built to Saar's bar* — 13.4 against his 12.9, that is the whole point
of her personal line — and the metric counted ours in full while zeroing the twin's. On a
9-slot cap that one asymmetry is +2.9 clear-load per slot: **ch05 read x1.34 with exclusion and
nothing in the chapter had changed.** An exclusion policy cannot be fixed by applying it
"symmetrically", because symmetry in the RULE is not symmetry in the RESULT.

**So the metric floors the damage instead of dropping the unit.** `metric_rounds_to_kill()`
scores an undentable unit as if each hit chipped 1. FE8 really does deal 0 there — the floor is
a property of the measurement, not a claim about the game — and it earns its place on three
counts: every unit stays in the comparison on both sides, the load becomes **monotonic in Def**
(more armour is never less work, where `rounds_to_kill` has a cliff from 12.9 straight to
infinite), and it preserves the ordering that matters — Saar scores **22.8** against Ravisin's
**13.4**, which is the truth about which is the harder wall. ch05 lands at **x0.88**.

**The floor must carry the same accuracy divisor `rounds_to_kill` uses**, and the first
implementation did not — which broke the very property it was introduced for. Scoring `hp/hits`
instead of `hp/(hits × accuracy)` made the load jump *down* across the cliff: real Saar read
**46.8 rounds at Def 11 and 36.0 at Def 12**, a tougher unit costing less work. Worse, the test
asserting monotonicity could not fail, because its fixture had Spd 0 and Lck 0 — 100% hit chance
is the one case where the divisor-free form happens to be continuous. **A property test whose
fixture sits on the only point where the bug is invisible is not a test**; the fixture now uses a
unit that can be missed. With the divisor the floor is not merely monotonic but *continuous*: a
unit taking exactly 1 damage per hit already scores `hp/(hits × accuracy)`, so the floor meets
the last dentable value rather than stepping at it. Caught by `/code-review`, not by the suite.

That also retires the "N yardstick-proof units excluded from clear-load" note as a *mechanism*;
the count is still printed for planned chapters, because it is worth knowing that a chapter you
are about to write fields a wall, but nothing is skipped any more.

**No locked baseline goes out of band, and none needed content changes.** All three locked
chapters move toward parity. The re-baseline this issue and #284 both anticipated turned out to
be a re-reading, not a re-tuning.

**One consistency fix rode along, and it was a duplicated force builder.** `solo_contributors()`
kept its own copy of the our-side expansion, which multiplied `count` over `enemy_combatants` —
and that collapses a `composition` entry to its DISTINCT classes. On ch01 it therefore counted
six bodies where the verdict counted three, and printed *"without it the chapter is x1.14"*
directly beneath a row reading x0.89. Both now come from one `chapter_units()`. A note that
cannot reconcile with the number it explains is worse than no note, and two functions that must
agree about the same force will not stay agreeing.

_Decided: 2026-08-16 (#285). The three locked baselines were re-measured on the new footing, all
move toward parity, and none needed re-tuning — so the "locked chapters re-approved by Nicolas"
item was moot: **a sign-off that guards a scenario is not owed when the scenario does not
happen** (Nicolas, asked what there was to decide)._

---

### One death quote per character (2026-08-16, #25)

FE8 lets a pid hold two death quotes: a chapter-keyed `gDefeatTalkList` row scans ahead of its
`chapter = 0xFF` one, and vanilla uses that for the escort a chapter is built around — Natasha
gets `MSG_9C6` in Ch5 and nobody else on the map has one but the boss. Basil is Natasha's donor
and holds exactly her role in ch05, so she inherited the slot, and both boxes shipped: the
universal *"Oh-- I'm sorry. I had more berries... I was going to..."* and the ch05 *"But I
haven't-- I still have her berry..."*

**Cut on sight** (Nicolas, on the PR): the two are the same interrupted apology about the same
undelivered berry, so the second box bought a mechanism and no line. The berry quote MOVED to
her universal one and the chapter row is gone. **We ship one death quote per character.**

Two things worth keeping from it. First, the general rule this is an instance of: *a slot vanilla
fills is not a slot we owe.* The empty `0x9C6` anatomy citation invited a second box the way a
free message id invites a scene, and the invitation was the whole reason it got written — the
line was chosen to fill a slot rather than because the character had two things to say.

Second, the hazard, because it survives the cut and will bite whoever revisits this:
`GetDefeatTalkEntry` returns the FIRST pid match, and `inject_pc_death_quotes` runs LAST in
`main()` and prepends at the head. A chapter injector that prepends its own row therefore lands
*behind* the universal rows and never matches — quote silently absent, build green,
`verify_text` green, nothing to see. If a character ever does earn a second quote, the ordering
belongs in `pc_death_quote_rows` and nowhere else; its docstring says so.

_Decided: 2026-08-16 (Nicolas). Scene 13's wiring, its host-block id `0x9F3` and the
`CHAPTER_DEATH_QUOTE_OVERRIDES` registry were all deleted rather than left unwired: this is a
retired mechanism, not a parked one._

---

### A ground array holds index + 1, and nobody was reading the ground (2026-08-16, #65 / #25)

Nicolas, on the ch05 PR: *"the platforms in combat you have are the grassy road ones."* Two
independent faults, and the second was invisible for two months because the first hid it.

**ch05 and ch02 never named a ground at all.** A hosted chapter that sets no `battleTileSet`
keeps its HOST SLOT's vanilla one, and vanilla's slots are not our world: ch05 sits on slot 6,
which ships vanilla Ch6's `battleTileSet = 6` — a table that sends `TERRAIN_ROAD` to `michi1`
and `TERRAIN_PLAINS` to `heichi1`. ch05's map is **53% road**, so a snowbound elven tomb staged
essentially every fight on a dirt track. ch02's slot 3 was wrong the same way. Both were wrong
*by omission*, which is why one line each would have been the wrong fix:
`CHAPTER_BATTLE_TILESETS` is now **required total** by the injector and by a test, so a new
chapter must state its ground rather than inherit one.

**And the snow arrays were off by one.** `GetBanimTerrainGround` ends `return ret - 1`, so a
`BanimTerrainGround_*` array holds **table index + 1**. The cave path always knew that (it
writes 21 for `siroyuka1` at index 20); the snow path wrote raw indices. Every snow chapter had
therefore been drawing the row *below* the platform it named since #65 — open ground resolved
to `mizuiumi1`, a vanilla **lake**, and chapters that asked for rough got the drift. Both paths
now go through one `_ground_value()`.

Three things worth keeping:

1. **Nothing in this repo read the ground.** Not the build, not a unit test, not a scenario. The
   first `recordch05platform` asserted *terrain*, filmed, and PASSED while the fighters stood on
   the wrong platform — terrain says which tile, and the ground is the answer to a different
   question. It now reads `gBanimFloorfx`, the engine's own resolved table index, and names the
   row. *A scenario's verdict only covers what it READS* has now cost us twice.
2. **The plausible wrong answer is the dangerous one.** Grass under snow got reported by eye in a
   day. The drift-instead-of-rough error survived two months because the wrong platform was
   still snow. Where a defect's failure mode is "looks fine", an assertion is the only detector.
3. **Verify a palette from data, never from a crop.** The first measurement that caught it
   sampled a band containing background as well as slab, which diluted the share; the honest
   test compares against colours **unique** to each candidate platform. Extends
   `feedback_verify_via_data_not_pixels` to grounds.

`TERRAIN_ROAD` then got its own slot — *"vanilla already has a road terrain right? can't you
just assign these tiles to that?"* (Nicolas). Correct, and it deflated a change we had described
as adding a category: the engine's array is flat, one entry per terrain, and `ROAD` already had
an entry that our helper was collapsing into "everything else". Its ground is the vendored
`Snow Dirt Path` ({Cynon}, F2E), chosen over a consistent-looking alternative with the tradeoff
stated and accepted: **its three distance bands are not the same material**, so a ranged
exchange reads browner than a melee one. The twilight tint is the knob if that ever grates.

_Decided: 2026-08-16 (Nicolas). Proof: `recordch05platform` PASS, ground index 118 =
`ms_snowpath`, slab 54–73% colours unique to that platform and 0% of either neighbour._

---

## Open Questions (not yet decided)

See `docs/PRD.md §13` for the full list. Key unresolved items:
- Signature moments for Marty, Meesmickle, Rootis, Sclorbo (Nicolas to recall)
- Velynne Harpell's arc (check published adventure)
- Sephek Kaltro — did he appear in the campaign?
- Messie's specific Bremen function (shop? services? quest-giver?)
- Unit struct save budget for D&D fields (audit in Phase 1, issue #10)
