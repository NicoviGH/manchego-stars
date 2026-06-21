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
- *Live state* → the **per-track** handoffs (`HANDOFF-content.md` / `HANDOFF-pipeline.md`), each maintained by its lane instance; `/handoff` run in a lane updates that lane's file. **`HANDOFF.md` is a thin router** (integration-tree pointers + current release) and carries no per-session snapshot, so it can't drift — recent history lives in `git log` + closed issues, not there. *Vision/pitch* → `PRD.md` (no specifics that live elsewhere).
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

**Seam enforcement: a lane-ownership guard, because the seam was honor-system and got crossed.**
The first parallel run had violations — the pipeline instance edited `build_campaign.py` (content-owned)
because nothing *stopped* it (and because no worktree isolation was actually engaged: both sessions ran in
the primary checkout on `main`). Documentation + the file seam weren't enough; ownership is now **enforced**.
`tools/check.py` carries the ownership map (single source, also summarized in `CLAUDE.md` §Tracks:
pipeline = `difficulty.py`/`fe_combat.py`/`check.py`/`playtest/**`/`build.sh`/`worktree-setup.sh`/`hooks/**`/
`.github/workflows/**`; content = `campaigns/**`/`build_campaign.py`/`portrait_tool.py`/`map_sprite_tool.py`/
`ref_to_bust.py`; everything else incl. `tools/inject/**` + docs = shared) and `check_lane_ownership()`, run
by the pre-commit hook + CI. The lane is read from the `inst/<track>` **branch name** (inherently
per-worktree; `.git/config` is shared), `manchego.lane` config as fallback. **Enforcement is scoped to lane
worktrees**: on `inst/<track>` a staged file owned by the *other* lane is blocked (`--no-verify` overrides;
CI enforces on `inst/*` PRs via `GITHUB_HEAD_REF`/`BASE_REF`). The **primary checkout (`main`) is
unrestricted** — it's the integration/solo tree where one person does one thing at a time, so there's no seam
to cross; blocking it would only tax normal single-window work. The seam can only be *violated* when two
instances run concurrently, and concurrency already **requires** a worktree per instance (two builds in one
tree corrupt each other) — so enforcing exactly where worktrees exist covers the real risk. Shared cross-lane
constants (e.g. the weapon↔ITEM map) live in `tools/inject/decomp.py`, not either side's file. Issue #55.
_Decided: 2026-06-19_

**Track work always happens in that track's worktree — even solo.** "Work the content track" / "work the
pipeline track" means: switch into `../ms-content` (`inst/content`) or `../ms-pipeline` (`inst/pipeline`)
*first*, then work. `main` is reserved for cross-track integration and ad-hoc one-offs. This is broader than
the build-isolation rationale above (which only *requires* a worktree when two instances run concurrently):
making the worktree the unconditional home for track work removes the "is anyone else running?" judgment call,
keeps every track commit on its `inst/<track>` branch where the lane guard applies, and means a fresh instance
told to "work the content track" lands in the right tree by default instead of editing `main`. The worktrees
are persistent (already bootstrapped); `tools/worktree-setup.sh` only re-creates a missing one.
_Decided: 2026-06-19 (Nicolas)_

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

**The parity curve is surfaced in CI informatively; the hard gate is built but unwired until content lands (#48 (b)).**
CI's `build` job now runs `make difficulty` on every build (after the submodule checkout it needs to read
the decomp HEAD), so balance spikes/sags and parity regressions are visible on every PR. It is **informative
only** — `make difficulty` always exits 0. The enforcing form is `make difficulty-gate`
(`difficulty.py --curve --check`): `curve_gate_failures(rows)` fails any chapter that **claims a
`parity_reference`** and is either off-parity (`verdict != OK`) or unreliably measured (a dropped boss — an
unreliable OK is not a pass); chapters with no curated reference are informational and never gate. Today
`difficulty-gate` is RED by design (our Ch2–Ch7 enemy inventories aren't authored yet, so our side reads 0.0 /
off-parity), so CI runs the informative `difficulty`. **The flip is a one-word CI change** —
`difficulty` → `difficulty-gate` — once the content track authors those slices.
_Implemented: 2026-06-19 (CLAUDE; pipeline track, TDD)_

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
motion; `--scale` nearest-upscales the 240×160 frame; `--open` saves to `map-review/`,
gitignored, and opens in Safari since Preview paginates GIFs and inline renders aren't
visible to Nicolas — [[feedback_sharing_visual_drafts]]).
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

**Playtest carryover: ship a per-release starter save; don't rely on cross-build SRAM compatibility**
Each new build a tester receives ships with a **starter `.sav`** that drops them at the newest
playable chapter (prior chapters marked cleared), so playtesters **never replay Prologue/Ch 1** to
reach new content. We do **not** lean on save carryover across builds: FE8 validates a save by a
**fixed** magic (`SAVEMAGIC32`/`SAVEMAGIC16`) + a checksum (`fireemblem8u/src/bmsave-lib.c`), and
`EraseSramDataIfInvalid` wipes anything that fails on boot. The magic is constant, so a rebuild
*alone* doesn't invalidate a save — but adding/finishing chapters shifts the save-data layout
(chapter count, unit tables, `PlaySt`, SRAM offsets), after which an old `.sav` fails the checksum
(auto-wiped) or loads as garbage. Emulator save-*states* are ROM-version-specific and break every
build, so testers are told to use the provided save and not carry old saves/states. The starter
save is produced/bundled by the friend build (`tools/build.sh dist`, release #37). A future in-game
**chapter-select / debug warp** is a possible cleaner alternative (more work, reusable) — stretch.
_Decided: 2026-06-19; from the brother's v0.1.0 playtest (#59)_

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
left leaf — iterated with Nicolas, renders in `map-review/goodberry-icon/`). Authoring in the shared palette means the icon
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

**Transitions: keep the FADE (vanilla-flavored).** Vanilla never reuses one podium for different
*people* — each speaker gets their own slot (≤4), faces fade in once, `REMA` clears between messages
(`[ClearFace]` is in 0/119 vanilla scripts); the in-place swap (`sub_80066E0`) is vanilla but only
for one character's *expression* change. So for our one-podium roll-call the `[ClearFace]` fade
("one leaves, next arrives") fits vanilla's grammar; a swap would morph one face into another.
_Decided 2026-06-16 with Nicolas across four motion reviews (`map-review/ch01-beat1-northlook.gif`,
`run.sh recordch01`): Sclorbo shows his Ross face; Marty's spore-cough is a parenthetical (FE8 has
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

## Open Questions (not yet decided)

See `docs/PRD.md §13` for the full list. Key unresolved items:
- Signature moments for Marty, Meesmickle, Rootis, Sclorbo (Nicolas to recall)
- Velynne Harpell's arc (check published adventure)
- Sephek Kaltro — did he appear in the campaign?
- Messie's specific Bremen function (shop? services? quest-giver?)
- Unit struct save budget for D&D fields (audit in Phase 1, issue #10)
