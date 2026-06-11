# Handoff: **Ch1 slice (#21) — #42 PLAYER-CHOSEN LORD DONE & playtested (menu → saved choice → force-deploy/Seize/game-over all real; pushed `e5013c0`). GIF shown to Nicolas in Safari — UI feedback pending. NEXT = ch01 win/seize playtest → goblin art decision (Nicolas) → Goodberry rename → dialogue LAST.**

**Date:** 2026-06-10
**Session focus:** #42 player-chosen lord, end to end: traced the vanilla route-split
menu + permanent-flag persistence + the four engine hooks, wired the menu into ch01's
beginning scene (Nicolas placed it: after the Northlook muster, before preps), built
`ch01lord` + `recordlord` playtest scenarios, all green, committed `Closes #42`.

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
1. **Nicolas's verdict on the lord-select UI** (GIF was opened in Safari;
   map-review/lord-select/). Prompt/confirm wording = placeholders (dialogue pass owns).
2. **ch01 win/seize playtest** (`ch01win`): A-taps take default lord (Braulo) →
   pokeFrail chief + pokeHarmless escort each turn → march Braulo to (21,7), kill,
   Seize → assert ending fires (chapter → 3). NOTE before writing it:
   - `marchToward` scans hardcoded ch00 bounds `x 0..14, y 0..9` — ch01 map is
     **25×16** (read from maps/ch01-the-iron-trail.json); add bounds params.
   - `EMPTY_TILE = (2,2)` (endTurn cursor parker) — verify it's empty on ch01.
   - Seize menu item position after moving onto (21,7): top of the action menu
     (assumed, vanilla); `chooseWait`'s UP-wrap trick picks Wait, NOT Seize.
   - This in-game-verifies the `CanUnitSeize` patch (machine-verified so far:
     flag, force-deploy, game-over via `ch01lord`).
3. **Goblin art decision with Nicolas:** map sprites + boss portrait for
   soldier/fighter/armor-knight goblins. FE-Repo reskin bases ([[reference_fe_repo]]);
   grunts show vanilla class names + sprites; chief shows vanilla Breguet face in his
   death quote (0x961 staging uses FID_Breguet).
4. **Goodberry rename** (Vulnerary→Goodberry party-wide) — lands within this slice.
5. **Dialogue pass LAST**: Northlook opening (hand-off from ch00 ending), lord-select
   prompt/confirm wording, house hints 0x93B/0x93C, road sign 0x955, ending 0x954,
   chief quote 0x961; then `record`/`recordlord` GIFs → Nicolas sign-off.
6. Carried: #29 world map; Scramsax Hero mug [F2E] license recheck; ch02+ YAML
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
  game-over screen) and `recordlord` (continuous "lord"-tagged frames). New consts
  LORD_CANDIDATES=8, LORDSEL_FLAG_BASE, CHAR_PINKY=0x08, CHAR_CHIEF=0x46.
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

## Current state
- ✅ `make` green; `verify_text` 3404 msgs 0 runaway; playtests PASS: ch00
  win/gameover/retreat, ch01 (default lord via blind A-taps), **ch01lord**.
- ✅ Pushed `e5013c0` (Closes #42; build_campaign + harness + decisions.md §lord).
- ✅ Menu verified on-screen: 8 names over the winter map, confirm box types out,
  prep screen force-deploys the pick. ch00 Braulo-death game over now rides the
  UnitKill hook (vanilla route-wide entry demoted) — `gameover` scenario PASS.
- ⚠️ `recordlord` harness addition is committed in THIS handoff commit (was made
  after e5013c0 for the GIF).
- ⚠️ House/sign/ending/lord-prompt texts are functional placeholders (dialogue pass).
- ⚠️ ch01 ending MNC2(0x3) lands on vanilla Ch3 until ch02 is wired.
- ⚠️ Party=8 assert + LORD_CANDIDATES=8 in harness must bump when pepperjack & brie
  get class YAMLs (they're name-only; excluded from cast/candidates).
- ℹ️ ch02+ YAMLs still carry aspirational `ea_file:` fields (schema cleanup, carried).

## Blockers
- None. (ch01win seize playtest has the three harness gotchas listed in Next #2.)

## Key files
- `tools/build_campaign.py` — `_inject_lord_select_engine`, LORDSEL_* constants,
  `inject_ch01` (menu codegen in step 4a, texts in step 6).
- `tools/playtest/harness.lua` — `ch01lord`, `recordlord`, lord constants.
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
