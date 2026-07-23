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
ch00 + ch01 with the clear-bot and A-mashes through the ending→opening→prep onto the ch02 map. That
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
  **Natasha→Joshua escort** becomes **Basil (Natasha-donor Priest) chaperoned to Talk Sahnar (Joshua-donor
  Myrmidon)** — a convertible crit-threat you neutralize by recruiting; (b) the **village-raid race**
  becomes the **Phantom-Ship eruption** (injected `EARTHQUAKE`/`TILECHANGE`) spawning undead that raid
  **spread reward-sites** (elven reliquaries), with the **crest-of-cold-iron** (promotion relic) as the
  save-all reward — our Guiding Ring. Ch5-magnitude economy incl. the **elven store** (Armory + Vendor);
  ch05 is the first chapter at/above the FE8-Ch5 reward tier, so stat-boosters + a promotion item unlock
  here (per §Reward budget above).

Both stay `status: planned` seeds — this sets the targets; the map + events build at each slice, checked
against the twin via `make difficulty` (economy #170 + recruit/reinforcement dynamics #171 now modeled).
_Decided: 2026-07-15 (Nicolas + CLAUDE). Supersedes the earlier "split old Ch4 into two Ch4-parity halves"
framing and the brainstormed Ch11-map-borrow (issues #24/#25) — both retired._

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

**Two healers, differentiated by donor (same move as the shamans).** Sclorbo and Basil are both
Priests, so they get *distinct* vanilla donor lines to avoid stat-twins: **Sclorbo → Moulder** (the
durable "war-priest": HP70/Def25, balanced, accurate) and **Basil → Natasha** (the frail "mage-healer":
HP50/Def15 but Pow60/Res55/Lck60 — a glass, dodgy, magically-potent nuke-healer). The frail line sits
on Basil deliberately: **Sclorbo is a lord candidate** (#42) and the per-lord floor would have to work
harder on a frailer lord (he's already the weakest, staff-only lord pick), whereas **Basil is not a lord**
(joins Ch5, after the Ch1 lord-select), so frailty there carries no survivability-floor cost — and "fragile
but potent natural magic" suits an awakened shrub. Donor stats only; both stay Priest → Bishop/Sage.
_Decided: 2026-06-20 (Nicolas)._

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
  during a legit enemy phase) and drives the menus *forward* back into play instead of judging liveness.
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
  died to an earlier order → downgrade to wait) and backs failed menus out with a full drain (submenus are
  also `sProc_Menu`; a fixed two-B backout can strand a unit selected). Any live-policy failure (endpoint
  down) still answers the harness with an `{error}` response — a fast diagnosable FAIL, not a 90s timeout;
  a replay-mode transcript miss does the same and exits non-zero — CI/replay stays closed-world.
- **Exported unit ids: blue = charId (PCs are unique), red = 1000+slot** — generic enemies *share* a charId,
  so the slot disambiguates which brigand an attack order targets.
- **Lua JSON is a vendored ~200-line subset (`tools/playtest/json.lua`), not a library.** mGBA's Lua has no
  JSON; encode writes sorted keys (deterministic bytes, mirroring the serializer doctrine), decode rejects
  trailing garbage (a truncated file must not half-parse into plausible orders). Unit-tested without mGBA
  (`test_json.lua`, 45 asserts) + a cross-language round trip (Lua req → Python sidecar → Lua resp) verified.
- **M2 limitations (deliberate, → M3):** `chooseAttack` fires on the UI's *default* target (unambiguous
  whenever one enemy is in range of the strike tile); staff orders execute as Wait. In-emulator prologue
  replay needs local mGBA (CI has none — the platform rule); the protocol itself is fully unit-tested.
_Decided: 2026-07-02 (CLAUDE; pipeline track. Epic #63 M2 + Nicolas's free-model direction; 23 new Python
asserts + 45 Lua asserts in make test)_

**Recording a cutscene as a review GIF (the standard way to show Nicolas motion).**
The harness fast-forwards cutscenes (mashes A), so an assert scenario's screenshots land
on fades — to SEE a scene play, use a `record*` scenario: it drives the game to the
scene, then captures PNG motion frames `NN-<tag>.png` into `/tmp/playtest-<scenario>/`.
Existing: `recordending` (ch01 outro, tag `end`), `recordch01trail` (`trail`),
`recordlord` (`lord`), `recordch01`/`record`/`scenes` (`op`/`bt`). To record a NEW scene,
add `scenarios.record<name>` that drives to it then captures; for an OUTRO, reuse the win
drive (cf. `recordending`'s copy of `ch01win`) and swap the fast win-wait for
`pokeNormalConfig()` (restores readable typewriter speed after the battle's
`pokeFastConfig`) + a slow capture loop (`if fr%8==0 then shot; if fr%18==0 then press A`
until `chapter()` advances). Then assemble + show:
`tools/playtest/make_gif.py <scenario> <tag> --name <basename> --open` (PIL; `--fps`
controls read pace — **~6 fps for text-heavy scenes Nicolas needs to read**, 12 for quick
motion; `--scale` nearest-upscales the 240×160 frame; the default output is `docs/demo/` on the
feature branch for GitHub review, and must be pruned before merge unless a live document retains it
as evidence — [[feedback_sharing_visual_drafts]]).
_Decided: 2026-06-17 (#21 ending review)._

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

**No arena**
FE8's arena is removed. Wolfram's Forge fills the "spend gold to get stronger" role.
_Decided: May 2026_

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
- **Pipeline:** `tools/bg_to_fe8.py` (any image → 240×160, GBA-5bit, tile-banked mode-P PNG; greedy ≤8
  banks) → `inject_backgrounds` copies it to `graphics/bg/`, appends the enum id (backgrounds.h),
  extern decls (bg.h), table row (eventscr2.c) and incbin symbols (data_bg.s); make's generic
  gbagfx/FETSATOOL rules build the bins. The 4 patched files are in `PATCHED_DECOMP_FILES`.
- **Gotcha — index 0 is transparent.** GBA BG colour index 0 shows the backdrop (FE8 sets it black),
  so a converter that uses local index 0 for a real colour renders **black holes** wherever that colour
  appears (caught in-engine on the ch02 Targos BG: the bright sky/snow speckled black). `bg_to_fe8.py`
  reserves index 0 (colours start at local 1; ≤15 usable per bank). A flat-quant *preview* won't show
  this — only the real GBA render does, so **verify event BGs in-engine**, not by reconstructing the PNG.
- **Slot ceiling:** only 0x36 is free before `BG_RANDOM` (0x37); a 2nd campaign BG must relocate
  BG_RANDOM first (verify nothing hardcodes 0x37). First use: ch02 Targos ending (Zeldacrafter snow-town).
_Decided: 2026-06-25_

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
- **Foreshadow in MVP.** The **Ch 5 (Elven Tomb)** frost-druid boss **Ravisin** drops a
  *flavored, locked relic* — the **crest of cold iron** ("it hums, but none of you know how
  to use it yet"). It sits in the convoy, unusable, as a Chekhov's gun for promotion.
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
Playtests pass under both: `bootToMap` alternates A/START so the crawl self-skips; `record` A-only boot captures it
for GIF review. **Backdrop mural:** vanilla composites the slides over `Img_CommGameBgScreen` (the brown rune wall)
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
= 0 for dist, 1 for test. Also: the decomp ships Linux `#!/bin/python3` shebangs that `setup-toolchain.sh` rewrites for
macOS, but any `git checkout` inside the `fireemblem8u` submodule reverts them (`bad interpreter` on the next build);
`build.sh` re-applies the fix idempotently. _Decided: 2026-06-17; root-caused + dist (with opener) GIF-verified end-to-end
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

## Operational Gotchas (durable)

_Moved here from `HANDOFF.md` 2026-07-02 (audit): these are durable engineering constraints, not
session state. `HANDOFF.md` points here._

- **A `git` subprocess run inside a git hook resolves against the OUTER repo unless you strip `GIT_*`.**
  Git exports `GIT_DIR`/`GIT_INDEX_FILE`/`GIT_WORK_TREE` while a hook runs (pre-commit drift → `check.py`
  → the `test_*.py` suite). Any tool or **test fixture** that then shells out to `git` — `git -C <dir> …`,
  a throwaway `git init`/`commit` in a tempdir, `_vanilla_decomp_text`'s `git show HEAD:` — has its
  `-C`/cwd **overridden** by the ambient `GIT_DIR` and silently operates on the real repo. On 2026-07-21
  this flipped `core.bare=true` on the live repo and wrote a corrupt commit before it was caught. **Always
  pass a sanitized env** — `{k: v for k, v in os.environ.items() if not k.startswith('GIT_')}` — to any
  `git` subprocess that must target a specific repo, and add `-c core.hooksPath=/dev/null` to fixture
  commits so they can't re-enter the outer hook. Fixed in `_vanilla_decomp_text` + `test_map_tileset.py`.
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
  `bg_to_fe8.py` reserves it. **Only slot 0x36 is free before `BG_RANDOM` (0x37).** Verify event BGs
  **in-engine** (flat preview won't show the holes).
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

---

## Open Questions (not yet decided)

See `docs/PRD.md §13` for the full list. Key unresolved items:
- Signature moments for Marty, Meesmickle, Rootis, Sclorbo (Nicolas to recall)
- Velynne Harpell's arc (check published adventure)
- Sephek Kaltro — did he appear in the campaign?
- Messie's specific Bremen function (shop? services? quest-giver?)
- Unit struct save budget for D&D fields (audit in Phase 1, issue #10)
