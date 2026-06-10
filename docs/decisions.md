# Design Decisions — Manchego Stars

> These decisions are **settled**. Do not re-open them without a strong reason.
> Add new decisions here when they are made. Date each entry.

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
FE8 packs text two bytes per u16; `[X]` = the 0x00 string terminator. An odd number of name bytes pairs the 0x00 into the last glyph, so the decoder runs away. Vanilla pads odd names with `[.]` (`Franz[.][X]` vs `Seth[X]`); `build_campaign.py` does the same. Always confirm text with `tools/verify_text.py` (decodes messages straight from the built ROM — no mGBA), not by eye.
_Decided: 2026-06-04_

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
- *Current session state* → `HANDOFF.md`. *Vision/pitch* → `PRD.md` (no specifics that live elsewhere).
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
D&D spell for inspiration), not by any mechanic or UI tag. Iconic matchups still use vanilla FE
weapon **effectiveness**, keyed to enemy class (see Combat System §). Retires GitHub issues #7
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

---

## Distribution & Scope

**Distribution: private, pre-patched ROM sent directly to 7 players**
No patch file, no RomHack Plaza listing, no public hosting. Non-SRD content (Artificer, Circle of Spores, homebrew races) can be used freely for this private distribution.
_Decided: May 2026_

**Permadeath: player choice via FE8's Casual/Classic toggle**
The toggle ships as-is from vanilla FE8. In-fiction flavor for Casual retreats: "retreated to the sled" / "carried to safety by Baxby."
_Decided: May 2026_

**MVP scope: 8 chapters (Prologue–Ch 8), ending at the Eastway scripted defeat → Revel's End cliffhanger**
The MVP runs **Prologue + Ch 1–8** (see `docs/CHAPTERS.md`). The finale, **Ch 8 (The
Eastway Ambush)**, ends in a scripted defeat — "You wake up on the road to Revel's
End…" → credits. Revel's End itself is the post-MVP **Ch 9** (`docs/roadmap.md`).
Chapters beyond the DM notes require a future writing session.
_Decided: May 2026; recount to 8 on 2026-05-31 after the old Ch 4 was split into Ch 4 (White Moose) + Ch 5 (Elven Tomb)_

---

## Art & Audio

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

---

## Class Mapping & Promotions

All 7 PCs (and recruits) are **stock vanilla FE8 classes** — class bases, caps, MOV, and CON come
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

Marty & Meesmickle share the Shaman chassis but differentiate at **promotion**, not base.
_Decided: 2026-05-30 (supersedes the 2026-05-27 "Marty→Monk for sprite differentiation," which forced an illegal Monk→Summoner promotion)_

**Pepperjack & Brie: RBG-crafted constructs that join as regular FE8 units (class + intro TBD at chapter-build time)**
Lore: they're automatons RBG (Artillerist artificer) builds — D&D "ballistae"/cannon-constructs, not PCs. FE8 has **no playable Ballistician class** (`CLASS_BLST_LONG_*` are inert map objects; ballistae are siege *terrain/items* a unit rides). So they are **not** modeled as ballistae. Instead they enter the army the **normal FE8 way** — introduced via chapter events whenever the story has RBG build them (recruit/reinforcement flow, mirroring how the base game stages unit arrivals). Their stock FE8 class and arrival chapter are chosen **when we build those chapters**, not up front. Until then their YAML carries `class: null` (name-only in the build). Brie is the only female of the 10 (`gender: female`).
_Decided: 2026-06-04_

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
- Pinky (recruit): Pegasus Knight → {**Falcon Knight**, Wyvern Knight}
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

**Pepperjack & Brie are separate recruitable units, not RBG summons**
Two sentient automatons RBG builds; each joins the army as an ordinary FE8 recruit (`npcs/`), not a
deployable cannon/summon, and is a stock vanilla class (TBD post-MVP). Pokémon-style speech (each
only says its own name — "Pepperjack!" / "Brie!"); they're dating. Pinky (RBG's homunculus "son")
is a third recruit — the army's flier (Pegasus Knight). Combined portrait at
`data/portraits/pepperjack-and-brie.jpeg`. Full flavor in `lore/pepperjack-and-brie.md`, `lore/pinky.md`.
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
  mechanism** (avoids class-matching headaches across 7 PCs).
_Decided: May 2026; renumbered to Ch 8→9 on 2026-05-31 after the Ch 4 split (was Ch 7→8)_

---

## Story & Dialogue

**Dialogue is co-written via the `dialogue-pass` skill: voice bibles → beats → 2–3 variants per beat, Nicolas picks.**
Neither of us is a creative writer, so the workflow encodes what three expert communities converge on — FE hack
writing ("every sentence spoken should have a purpose"; pace in A-presses, 2 visible lines/box), DM practice (voice
flows from a character document), and evaluated human-AI co-writing (hierarchical bible→beats→lines with human
curation at every level, never accepted wholesale). Voice bibles live as **§Voice sections in `lore/*.md`** (diction
rules, calibration lines, banned list; `lore/narration.md` holds the card/crawl/tour register + vanilla pacing
budgets measured from the decomp). Workflow + budgets + insertion gates: `.claude/skills/dialogue-pass/SKILL.md`.
_Decided: 2026-06-09 (community research: FEU writing threads, DM voice guides, Dramatron CHI'23)._

**New-game opening sequence: three exclusive content layers, written in story order.**
Mirrors vanilla FE8's structure (decomp-grounded): (1) **lore crawl** (#43, replaces `StartIntroMonologue`'s 7
subtitle cards) = the COSMIC layer — Auril, the two-year Rime, the sacrifice lotteries (adapted from the book's Cold
Open boxed text, printed p.22); (2) **world-map tour** (#43, replaces `WM_TEXT(0x8DB)`'s Magvel nation tour) = the
GEOGRAPHIC layer — all ten towns in 4 cards, grouped Bryn Shander / Maer Dualdon / Lac Dinneshere / Redwaters
(one fewer A-press than vanilla's 5 nations); (3) **chapter scenes** = LOCAL plot only, dialogue-driven like
vanilla's prologue (zero world exposition — vanilla puts none there either), plus brown-box location cards
(`BROWNBOXTEXT`, the "Renais Castle" analog). No layer repeats another's facts, so #43 can land later without
rewriting prologue text. Corollaries: the **Northlook hiring scene opens ch01** (not the ch00 ending, which cuts to
black on a location-card tease — vanilla puts the post-battle scene in the next chapter); Sephek's prologue escape
leaves **no corpse** (blade to shards, body rimes over, gone) — the withered-corpse reveal is **reserved for his
true death** in his payoff chapter (`lore/sephek-kaltro.md` §Imagery budget).
_Decided: 2026-06-09 with Nicolas (towns: all ten, lake-grouped; location card: yes; Northlook → ch01)._

---

## Open Questions (not yet decided)

See `docs/PRD.md §13` for the full list. Key unresolved items:
- Signature moments for Marty, Meesmickle, Rootis, Sclorbo (Nicolas to recall)
- Velynne Harpell's arc (check published adventure)
- Sephek Kaltro — did he appear in the campaign?
- Messie's specific Bremen function (shop? services? quest-giver?)
- Unit struct save budget for D&D fields (audit in Phase 1, issue #10)
