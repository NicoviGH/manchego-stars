# Handoff: **Ch1 slice (#21) — #42 LORD SELECT DONE (Nicolas approved the UI) + ch01 WIN/SEIZE PLAYTESTED (`ch01win` PASS: Braulo marches, chief falls, Seize → chapter 3). NEXT = goblin art decision (Nicolas) → Goodberry rename → dialogue LAST.**

**Date:** 2026-06-10
**Session focus:** #42 player-chosen lord end to end (route-split menu, permanent-flag
persistence, the four engine hooks; Nicolas placed the menu after the Northlook muster
and approved the UI from the review GIF), then the ch01 **win/seize** playtest:
`ch01win` PASSES — Braulo marches the trail, the chief falls, Seize fires the ending
and MNC2 advances to chapter slot 3. Ch1's engine work is now fully machine-verified
(entry/preps/cap, chosen-lord force-deploy + game over, win-by-Seize).

**Live checklist = GitHub issues (#21 = Ch1 slice; #42 CLOSED by e5013c0).**

---

## THE LORD-SELECT MECHANISM (full detail in decisions.md §Player-chosen lord, 2026-06-10)
- **UI**: vanilla post-Ch8 route-split menu clone (`CallRouteSplitMenu` idiom,
  ch8-eventscript.h): ASMC opens StartMenu over the map; per-candidate confirm text,
  `[Yes]` answer lands in EVT_SLOT_C, "No" loops back to the menu (LABEL/BNE).
- **Persistence**: ONE permanent flag per candidate, `0xF0 + menu index` — saved with
  the file, zeroed on New Game (`ResetPermanentFlags`, bmsave.c); vanilla scripts use
  nothing above 0xE7. `LordSelect_GetPid` (injected, eventinfo.c) scans; fallback =
  first candidate (Braulo) so debug entry never soft-locks.
- **Hooks** (`build_campaign._inject_lord_select_engine`, campaign-agnostic):
  `IsCharacterForceDeployed_` (always fielded), `CanUnitSeize` (chosen lead only),
  `UnitKill` (death → EVFLAG_GAMEOVER, any death path), vanilla route-wide
  Eirika/Ephraim GAMEOVER defeat entries demoted to flag-less quotes.
- Candidates/menu/confirm texts build-generated from the classed cast (PORTRAIT_MAP
  order, 8 today). Confirm/prompt = dead vanilla slot-2 text ids (0x957, 0x959+).

## NEXT SESSION (in order)
1. **Goblin art decision with Nicolas:** map sprites + boss portrait for
   soldier/fighter/armor-knight goblins. FE-Repo reskin bases ([[reference_fe_repo]]);
   grunts show vanilla class names + sprites; chief shows vanilla Breguet face in his
   death quote (0x961 staging uses FID_Breguet).
2. **Goodberry rename** (Vulnerary→Goodberry party-wide) — lands within this slice.
3. **Dialogue pass LAST**: Northlook opening (hand-off from ch00 ending), lord-select
   prompt/confirm wording, house hints 0x93B/0x93C, road sign 0x955, ending 0x954,
   chief quote 0x961; then `record`/`recordlord` GIFs → Nicolas sign-off.
4. Carried: #29 world map; Scramsax Hero mug [F2E] license recheck; ch02+ YAML
   `ea_file:` schema cleanup; GitHub housekeeping (#21 slice checklist) — gh ran fine
   this session for `issue view`; broader writes still try with Nicolas present.

## What was wired this session
- `build_campaign.py`: `_inject_lord_select_engine` (4 hooks above; runs with the
  engine-hardening block), LORDSEL_* constants, candidate-table append to
  events_udefs.c, menu C code prepended to ch2-eventscript.h (its OWN #includes:
  uimenu/fontgrp/hardware/uiutils — ch2's stock include set lacks them), beginning
  scene rebuilt with FADU(16) + prompt + LABEL/ASMC/confirm/BNE loop before PREP.
- `harness.lua`: `ch01lord` (menu-driven pick of the LAST candidate = pinky/NEIMI,
  benched by default → asserts flag set + force-deployed under the 4-cap + death =
  game-over screen), `recordlord` (continuous "lord"-tagged frames), and `ch01win`
  (default lord marches to (21,7), kills the chief, **Seize → chapter 3**; escort
  goblins poked frail+harmless so they can't kill or bodyblock; chief frail). New
  consts LORD_CANDIDATES=8, LORDSEL_FLAG_BASE, CHAR_PINKY=0x08, CHAR_CHIEF=0x46.
  Harness hardening: `marchToward` takes map bounds (ch01 = 25×16) and verifies the
  selection actually computed a movement map; `endTurn`/`runEnemyPhase` take an
  optional cursor-park tile; `pokeFastConfig` = map-anim combat + fast game speed
  (10-goblin enemy phases overflow the 3600-frame budget with full battle anims).
- GIF pipeline (no ffmpeg/magick on this Mac): PIL assembles
  `/tmp/playtest-recordlord/*-lord.png` → 2x NEAREST → 83ms frames →
  map-review/lord-select/lord-select-flow.gif (+ 3 stills). **GIF → `open -a Safari`.**

## Tried/learned this session
- **Chapter loads come up BLACK**: the menu ran invisibly (pure-black screenshots)
  until the scene got vanilla's `FADU(16)`-after-LOAD idiom (cf. Ch4 beginning).
  Any future pre-PREP scene content needs the same.
- **rodata is discarded by the decomp ldscript**: `static const` tables and `""`
  string literals in injected C land in `.rodata` → link error ("defined in
  discarded section"). Use `CONST_DATA` (= SECTION(".data")) and vanilla's dummy
  `.name = (const char *)0x8205958` pointer instead of `""`.
- chX-eventscript.h files each carry their OWN #include list (compiled together in
  events_script.c but agbcc -Werror trips on implicit decls before later includes).
- Save-menu vs lord-menu discrimination in the harness: the lord menu is the first
  `sProc_Menu` while ch01's goblins exist (`red(0x46)`) — the save screen runs
  before any LOAD. A-tap races (tap lands the frame the menu opens → selects item
  0) FAIL loudly, never false-PASS (flag assert catches the wrong pick).
- Vanilla `[Yes]` text command = the whole confirm mechanism; result in EVT_SLOT_C
  (1 = yes). Parity rule for generated bodies: printable chars only, pad `[.]` when
  odd (mirrors MSG_C14/C17/C18).
- `cast[0]` (PORTRAIT_MAP order) = braulo = the no-flag fallback — keep braulo first.
- **The phase banner eats key presses**: an A meant to select a unit lands in the
  PLAYER PHASE interlude → no selection → `gBmMapMovement` is stale (reads cost 0
  everywhere) → the old marchToward "moved" to any tile, A on empty ground opened
  the MAP menu, and chooseWait's UP-wrap picked **End** — silently burning whole
  turns. Fixes: wait ~100 frames after phase sync AND demand unreachable tiles in
  the movement map before trusting it (a real map always has some).
- Seize is the TOP action-menu item on the seize tile (assumed from vanilla,
  confirmed by ch01win) — plain A after moving onto it.

## Current state
- ✅ `make` green; `verify_text` 3404 msgs 0 runaway; playtests PASS: ch00
  win/gameover/retreat, ch01 (default lord via blind A-taps), **ch01lord**,
  **ch01win** (seize → chapter 3).
- ✅ Pushed `e5013c0` (Closes #42), `e83e725` (recordlord + handoff); ch01win +
  harness hardening in the commit carrying this handoff update.
- ✅ Menu UI **approved by Nicolas** (GIF review): 8 names over the winter map,
  confirm box types out, prep screen force-deploys the pick. ch00 Braulo-death
  game over now rides the UnitKill hook (vanilla route-wide entry demoted) —
  `gameover` scenario PASS.
- ⚠️ House/sign/ending/lord-prompt texts are functional placeholders (dialogue pass).
- ⚠️ ch01 ending MNC2(0x3) lands on vanilla Ch3 until ch02 is wired.
- ⚠️ Party=8 assert + LORD_CANDIDATES=8 in harness must bump when pepperjack & brie
  get class YAMLs (they're name-only; excluded from cast/candidates).
- ℹ️ ch02+ YAMLs still carry aspirational `ea_file:` fields (schema cleanup, carried).

## Blockers
- None. (Goblin art is a Nicolas-decision walkthrough, not a blocker.)

## Key files
- `tools/build_campaign.py` — `_inject_lord_select_engine`, LORDSEL_* constants,
  `inject_ch01` (menu codegen in step 4a, texts in step 6).
- `tools/playtest/harness.lua` — `ch01lord`, `ch01win`, `recordlord`, lord consts.
- `docs/decisions.md` — §Player-chosen lord (2026-06-10) = the mechanism SoT.
- `map-review/lord-select/` — stills + flow GIF shown to Nicolas.
- `campaigns/.../chapters/ch01-the-iron-trail.yaml` — slice source of truth.
- `fireemblem8u/src/events/ch8-eventscript.h` (vanilla route-split donor, via
  `git -C fireemblem8u show HEAD:...`).

## Gotchas (carried)
- Story text: YAML `script:` → build_campaign generates bodies; `make` overwrites
  manual decomp edits. Gate: `python3 tools/verify_text.py`.
- Odd-length NAME strings: pad with [.] (terminator parity); generated lord texts
  already do this.
- gDefeatTalkList: chapter-keyed entries at the HEAD; never after `{.pid=-1}`.
- Vanilla facts: `git -C fireemblem8u show HEAD:<file>` — the working tree holds OUR
  injected artifacts.
- Bash cwd drifts between tool calls — `cd` to repo root for git/make (bit AGAIN:
  ran make from fireemblem8u/ and got "up to date" from the decomp's own Makefile).
- **PNG → `open` (Preview); GIF → `open -a Safari`.**
- Synthetic macOS keypresses don't reach mGBA; in-emulator Lua is the path.
- Pinky is male — "he" (memory: cast notes; slipped twice this session).
- Frostmaiden book: `references/References/icewind-dale-...pdf`; DM notes:
  `/Users/Yonick/Documents/Claude/Projects/Manchego Stars / Fire Emblem Game/References/DungeonMasterNotesIcewindDale.pdf`.
  PDF page = printed page + 1.

## Memory
[[manchego-stars-project]] · [[feedback_fe-strictness]] · [[feedback_use_decomp]] ·
[[manchego-stars-automated-playtests]] · [[feedback_sharing_visual_drafts]] ·
[[feedback_answer_before_picker]] · [[reference_fe_repo]] (goblin reskins next) ·
[[project_manchego_stars_cast_notes]] (Pinky = he)

## Standing rules
Combat = pure vanilla FE; **field parity with vanilla ch N (both sides) is doctrine**
(the cap is the parity; Pick Units only chooses who fills it; the chosen lord is
force-deployed). Story/dialogue = collaborative (variants → Nicolas picks); art shown
before committing. Auto-push to main once green; never commit the `fireemblem8u`
submodule pointer. Playtests machine-run for logic, Nicolas for feel.
