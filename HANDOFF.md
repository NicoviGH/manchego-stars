# Handoff: friend playtest feedback shipped (#1,#2,#3,#5,#6) + robust quote-capture tooling. Open: rescue black-sprite (#44), lord-select UX (#4), difficulty.

**Date:** 2026-06-17 (session 11)
**Where we are:** Friends played the alpha (title → opening montage → Prologue → Ch1) and gave
feedback; this session fixed the in-alpha items and hardened the playtest harness. Five of six
feedback items are **done, committed, pushed, and confirmed** (two confirmed in-game by Nicolas).
One new bug surfaced (rescue → black sprite, **#44**) and two items need Nicolas's direction
(lord-select UX **#4**, difficulty).

`make` green · `verify_text` 3404/0 · drift clean · `ch01win`/`ch01lord`/`recordsupply`/`recordfix`
PASS. **Last commit `55ab3cf`.**

## Shipped this session (committed + pushed)
- **#1 Pinky lingered behind Braulo in the Northlook cutscene** (`f2cd040`). The RBG+Pinky
  two-shot now ENDS beat B (its REMA clears them); Braulo's "name the job" line moved to the head
  of beat C so he starts on a fresh stage. Nicolas chose "keep the pair" (option B). Verified via
  `recordch01` message decode.
- **#2 Braulo force-deployed when not the lord + #3 Braulo had Supply** (`08d12dd`). Both were
  vanilla logic keyed on `CHARACTER_EIRIKA` (Braulo's slot). Force-deploy now only fields the
  LordSelect-chosen lead (`gForceDeploymentList` body cleared); Supply (`SupplyUsability`) routes
  through `LordSelect_GetPid()`. **Cross-character verified:** `ch01lord` (Pinky as lord: flagged,
  force-deployed under the 4-cap, death→game-over) + `recordsupply` (Pinky-lord benches Braulo +
  opens the convoy via Supply; a non-lord has no Supply row).
- **#5 roadsign unreadable** — boxed (`8537b57`, other instance: `SOLOTEXTBOXSTART` opaque box) AND
  moved to a **battle-start turn-1 event** (`c550a95`) so the party always reads it (was a [8,8]
  tile trigger). **Confirmed in-game** (Nicolas): boxed "BRYN SHANDER — 2 MILES … KEEP WALKING" +
  body render centered over the snow at battle start.
- **#6 per-PC death quotes** (`8537b57`, other instance). One dying line per deployable cast member
  via the vanilla `gDefeatTalkList` path. **Confirmed in-game** (Nicolas saw Marty's).
- **Playtest tooling** (`e1a2cb5`, `49be242`, `6514001`, `55ab3cf`):
  - Fixed bit-rotted `ch01lord`/`recordlord` lord-menu detection (the menu became a scenic
    `StartMenu`; detect by `menuOpen()` alone, 200-iter budget).
  - New scenarios: `recordsupply`, `recordrescue` (repro #44), `recordfix` (battle-start roadsign +
    a PC death), `ckpt_lordpinky` (Pinky-as-lord prep checkpoint).
  - `run.sh PT_FPS=240` override: run a `record*` capture at top speed (60fps+videoSync is ONLY for
    smooth-fade GIFs; static text/boxes + proc-detected captures read fine fast).
  - **Robust in-battle quote capture** (`55ab3cf`): `procActive(SYM.ProcScr_BattleEventEngine)` is
    true exactly while an in-combat quote box is up (death quotes, taunts) — capture loops hold +
    screenshot it instead of A-mashing past it. (`ProcScr_StdEventEngine` is live during ALL map/turn
    event processing, so it must NOT gate "quote up".) `recordfix` asserts `quoteBoxShot=true`.

## Open items (next session)
1. **🔴 Rescue → black sprite (#44).** A rescued/carried custom-cast map sprite renders black.
   Repro: `tools/playtest/run.sh recordrescue`. Root-cause findings in the issue (MU path
   `Make6CMOVEUNITForUnitBeingRescued`, koido.c:60; mounted units force `CLASS_CIVILIAN`+palette
   `0xC`; the foot path *should* be correct via the patched `GetUnitSpritePalette` → confirm
   sheet-vs-palette next). **An overnight background agent is investigating this** — check its report
   first thing. Non-critical for the alpha.
2. **#4 Lord-select screen UX** — friends want the lord-choice screen to (a) explain what's
   happening and (b) show the candidates' sprites. **Needs Nicolas's design direction** before
   building (the menu is a `StartMenu(MenuDef_LordSelect)` over `BG_DARKLING_WOODS`).
3. **Difficulty balance** — friends found Ch1 harder than vanilla. Diagnosis: Ch1 is a 1:1 vanilla
   mirror, but our roster has no Seth-tier crutch + squishy classes. Levers discussed: raise
   `deploy_limit` (4→5/6, lead recommendation), generous EXP, an anchor unit, light enemy softening;
   AVOID blanket party-leveling / gutting enemies. Nicolas wants to **quantify** ch1 difficulty
   (ours vs vanilla) — a balance-report script (not yet built) is the parked idea. Needs his calls.

## On-demand builds (unchanged)
`tools/build.sh test` (lean, straight-to-map) · `tools/build.sh dist` (with #43 montage opener,
stamps `dist/`). NEVER a bare `make` for a shippable ROM — it strips the montage.

## Key files (this session)
- `tools/build_campaign.py` — `inject_ch01`: roadsign is the first turn-1 entry in
  `EventListScr_Ch2_Turn` (battle-start #5), AREA tile trigger dropped from `_Misc`; beat arrays
  `b1_preload`/`b1_overrides` (beat B ends on RBG+Pinky, Braulo in beat C #1);
  `_inject_lord_select_engine` (convoy/force-deploy/seize/UnitKill hooks #2/#3).
- `campaigns/.../chapters/ch01-the-iron-trail.yaml` — roadsign event `trigger: battle_start`.
- `campaigns/.../{pcs,npcs}/*.yaml` — `death_quote` per deployable (#6).
- `tools/playtest/harness.lua` — `recordsupply`/`recordrescue`/`recordfix`/`ckpt_lordpinky`/
  `reachPrepPinky`; proc-detect quote capture. `run.sh` — `PT_FPS` + checkpoint mappings.
  `gen_symbols.py` — PrepUnitScreen/BmSupplyScreen/Battle+StdEventEngine.

## Gotchas (carried + new)
- Story text → `make` regenerates bodies; gate with `verify_text` after any text change.
- **Hand-written narration → `_term_pad`** (odd printable count needs the `[.]` pad).
- FE8 convoy access is OFF in prologue/`CHAPTER_L_1`; our Ch1 is host slot **2** so Supply IS
  available there (that's why the friend saw Braulo with it).
- **Playtest speed:** `record*` defaults to 60fps+videoSync (smooth fades). For static/proc-detected
  captures use `PT_FPS=240 tools/playtest/run.sh <scenario>` (~4× faster). Background `run.sh` calls
  need an explicit `cd` into the repo (background shell resets cwd).
- **Capturing a brief in-combat quote:** detect `ProcScr_BattleEventEngine` and hold; don't sample +
  A-mash (it dismisses the box). Death quotes can pop at the enemy→player phase boundary.
- `ls *.png | tail` sorts "99" after "100+" (string sort) — use `sort -n` on the numeric prefix.
- Built ROM at `fireemblem8u/fireemblem8.gba`. Synthetic macOS keypresses don't reach mGBA. Nicolas
  can't see inline renders — save to `map-review/` (gitignored) and `open`. Izobai female; Pinky male.
- **Never commit the `fireemblem8u` submodule pointer** (build artifact); stage repo files explicitly.

## Memory
[[manchego-stars-project]] · [[project_manchego_stars_campaign_structure]] · [[manchego-stars-automated-playtests]] ·
[[manchego_stars_guest_map_sprite_wiring]] · [[manchego_stars_non_lord_cursor_crash]] · [[feedback_use_decomp]] ·
[[feedback_collaborative_map_design]] · [[feedback_show_before_committing_art]] · [[feedback_answer_before_picker]] ·
[[feedback_proactive-push]] · [[feedback_clean_doc_rewrites]] · [[feedback_handoff_vs_memory]] · [[feedback_fe-level-design]]

## Standing rules
Combat = pure vanilla FE; field parity with vanilla ch N is doctrine. Custom art where it matters,
**show before committing**; bring 2-3 options, let Nicolas drive. Story/dialogue = collaborative.
**Fast playtests for logic; 60fps recordings only for fade spot-checks** (checkpoints + `PT_FPS` make
this cheap). Repo is the source of truth, NOT memory. Auto-push to main once green; never commit the
`fireemblem8u` submodule pointer.
