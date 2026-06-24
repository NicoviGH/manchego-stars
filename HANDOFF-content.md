# Handoff — Content track 🔒 live state

Per-track live state for the **content lane** (Ch2+ slices, dialogue, art). Worktree doctrine,
ownership map, trunk rules → `CLAUDE.md` §Tracks (read first; lane guard = `check.py
check_lane_ownership`). Seam model → `docs/decisions.md` §Seam enforcement. Backlog → GitHub issues.
**Shared builds/gotchas → `HANDOFF.md` + `CLAUDE.md`; this file = my current state + content-lane
gotchas.** Don't touch `HANDOFF-pipeline.md`.

## Base state (clean — start here)
- **`inst/content` = `a393256`**, **21 ahead of `origin/main` (`b59e706`)** — the #65 battle-anim +
  snow-platform epic + the ch02 reground. Fast-forwardable; merge down to `main` + push when ready.
- **`make` green** (last verified on the **real campaign + platforms** build, non-TESTCH). Drift
  clean, working tree clean except the `fireemblem8u` submodule pointer (**never commit it**).
- **The repeatable how lives at the convention homes** (no standalone doc): the
  `inject_battle_anims` / `inject_battle_platforms` **docstrings** (how) + `decisions.md` Art & Audio
  (why) + the **`custom_unit` issue template** (per-unit checklist). Read those before the next unit.

## ✅ Done this session — #65 battle anims + snow platforms (RBG, end-to-end)
The faked-battle-anim epic is **complete for RBG and the pipeline is generalized**:
- **RBG's custom battle anim ships**, isolated to a **stat-identical Archer-CLONE class**
  (`CLASS_BLST_KILLER_EMPTY` 0x6C) so generic/enemy archers stay byte-vanilla. `inject_battle_anims`
  generates assets + appends a `banim_data[]` row + clones the class with its own `AnimConf`.
  **Key gotcha (codified):** `AnimConf .index = anim_id + 1` (`GetBattleAnimationId` returns idx-1;
  wrong = purple dragon). Frames at `campaigns/.../battle_anims/prof-rbg/{ready,windup,peak}.png`
  (88×64, BOX-descaled from the 1920×1080 masters — **never re-shrink small art**). RBG keeps his
  **current scale** (the 0.92× shrink was previewed and declined).
- **Real snow battle platforms** (`inject_battle_platforms`): vendored 3 F2E platforms from FE-Repo
  `{Cynon}` (Snowdrift, Snow Uneven Ground Light, Ice Flat) into new `battle_terrain_table` slots
  115–117, with a **per-tile terrain→ground remap** — `BanimTerrainGroundDefault` = snow-open
  (plains→Snowdrift) for the prologue/sandbox (`battleTileSet 0`); new `BanimTerrainGround_Tileset15`
  = snow-rough (open→Uneven) for **Ch1** (idx 2, set via `chapter_settings.json`). **Verified
  in-engine unforced.** Cynon credited in `CREDITS.md`. Picks recorded in `decisions.md` (Art &
  Audio). 20 build-campaign tests green.
- **`make TESTCH=1`** = playtest ROM that boots **straight into a Ch1 sandbox** (whole cast deployed
  as their clones + reskinned foes), no prologue grind (`inject_test_chapter` re-activated via
  `--test-chapter`). Plain `make` = the full campaign.
- **Delivery channel locked:** commit a **GIF** (never MP4 — committed `.mp4` is a binary download,
  not inline on GitHub) to `docs/demo/` + push → Nicolas views on GitHub. Previews in `docs/demo/`:
  `rbg-battle.gif`, `prologue-snowdrift.gif`, `ch1-snow-uneven.gif`/`-light.gif`.

**Cross-lane (PIPELINE lane — committed to `inst/pipeline`, tracked in `HANDOFF-pipeline.md`, not my
task):** `recordrbg` checkpoint capture, `make_gif.py --mp4` (local-only), and `recordrbgtest` —
whose **deferred fix** (doesn't reach the battle anim on the TESTCH sandbox) is the pipeline lane's
top next task. Content only relies on the *capability*: `make TESTCH=1` + `run.sh recordrbg` (fresh
checkpoint) to verify a unit in-engine.

## Now / Next (priority order)

### 1. 🎯 ch02 "Cold Welcome" (#22) — tactical reground DONE; 3 human checkpoints remain
The enemy/chwinga/gift/mechanic reground is **built green** (`inject_ch02`: parity enemies, GREEN
chwinga table `088B4718`, per-survivor `CHECK_ALIVE`→`GIVEITEMTO` gifts, reinforcements `088B4758`,
sled dropped). LEFT before ch02 is "done":
- **(a) Dialogue reground — co-write via `dialogue-pass`.** Locked 2026-06-19 cutscene text still
  frames the dropped sled (Wolfram's "…the sled"; ending "…ringing the sled"), calls reinforcements
  "Snow Wolves", and lacks a chwinga intro beat (a Marty line — the befriend-creatures diplomat).
  YAML has a PENDING block marking the three edits; changing the opening beat count touches
  `CH02_OPENING_MSGS`.
- **(b) Chwinga + Vellynne art (#38/#39, #19).** Map-sprite reskin + portraits + name-text
  (Mote/Rime/Glimmer) over DARA/KLIMT/MANSEL placeholders; Vellynne's bust. **Show before commit.**
- **(c) mGBA load-test** ch01→ch02→win→chains; chwinga LOAD green, archer threatens the pegasi,
  survivors deliver charms at the ending. (Now fast via `make TESTCH=1` once a ch02 sandbox is wired,
  or the `recordrbg`/checkpoint path.)

### 2. 🅿️ #46 lord-select reskin — DESIGN LOCKED, PARKED (needs Nicolas at his computer for sign-off)
Clone/adapt `prep_unitselect.c` → `engine/lord_select_screen.c` (dedicated screen; real prep
untouched), driven by build-generated `gLordSelectCandidates[]` + a pitch-msg table. Pitch panel
replaces inventory (qualitative); A → "Will N lead?" → sets `LORDSEL_FLAG_BASE + i`. Pitches already
in `pcs/*.yaml` (`lord_pitch:`); dead msg-ids `0x929–0x92F,0x932`, explainer `0x957`; `recordlord`
in `harness.lua`. Gate: mGBA render → Nicolas sign-off; `Closes #46`+`#21`; ADR in `decisions.md`.

### 3. Supporting content / art
Vellynne portrait #19 · ch02 title card (atlas lacks C/W/d/m — visual, sign-off) · enemy YAML pass
#18 · NPC/recruit stubs #17 · world-map unlock #29 · overworld sprites #38 · onboarding-parity #64.
**The remaining cast/enemies follow the `custom_unit` issue template (open one per unit).**

## Watch out (content-lane only)
- **Additive, never global** — clone classes / new terrain slots / appended banim rows; never edit a
  shared vanilla class/anim/terrain in place. (`decisions.md` Art & Audio; the inject_* docstrings.)
- **msg-id vetting is treacherous:** `data_battlequotes.c` stores ids 4-digit zero-padded (`0x0935`);
  vet by **content** in the `0x0XXX` form, not naïve hex-grep.
- **Writing any dialogue → invoke `dialogue-pass` first.** Voice grounding: per-NPC `lore/*.md` §Voice
  + `lore/frostmaiden-voices.md` + `texts/texts.txt`. Story sources: `References/DungeonMasterNotes…pdf`
  + the Frostmaiden book (image-only — render pages with `pdftoppm` and read the PNGs).
- **Reward placement follows `parity_reference`, not chapter number** (Reward ADR).
- Long unit names overflow FE8's name buffer — add a short `fe_name` (≤12) to new units.
- Story bodies are `make`-regenerated; gate text changes with `python3 tools/verify_text.py`.
- **Chapter hosting** (model on `inject_ch01`/`inject_ch02`): each chapter rides the *next* vanilla
  slot (ch01→2; ch02→3); chains via `MNC2(<next slot>)`. New snow chapters: set their
  `battleTileSet` to `0` (open/Snowdrift) or `0x15` (rough/Uneven) per scenery.
- **Don't reuse a playtest checkpoint across an injection/build change** — only across pure
  graphics-byte swaps. A stale save-state shows the map/menu, never the battle.
- **The repo moves under you:** parallel pipeline work lands on `main`. Re-check `git log main` + sync
  before a big build.
