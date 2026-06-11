# Handoff: **Ch1 slice (#21) — ENGINE WIRING DONE & playtested (ch01 loads, preps work, cap enforced, all green, pushed `39b6c18`). NEXT = #42 player-chosen lord → goblin art decision (Nicolas) → win/gameover playtests for ch01 → Goodberry rename → dialogue LAST.**

**Date:** 2026-06-10
**Session focus:** Ch1 "The Iron Trail" engine wiring — traced the real prep-screen
gate in the decomp, built `inject_ch01` (map, deploy cap, rosters, events, texts,
title card), fixed the slot-2 SKIRMISH misclassification, added a `ch01` playtest
scenario. Everything green and pushed.

**Live checklist = GitHub issues (#21 = Ch1 slice; #42 pulled INTO the slice).**

---

## THE PREP-SCREEN MECHANISM (fully traced; recorded in decisions.md §Field parity)
- `hasPrepScreen` in chapter_settings.json is DEAD ("left over from FE7", chapterdata.h:37).
- Real gate: `PREP` event cmd (0x3E) → `gProcScr_SALLYCURSOR`; vanilla Ch4+ all end their
  beginning scene with `CALL(EventScr_08591FD8)` (eventscr.c:4283, shared CLEAN/PREP/CLEAN).
- **Deploy cap = the ally UnitDefinition table itself**: `GetChapterAllyUnitCount()` counts
  entries; prep flow clamps & benches past it; table x/y = the deploy tiles; table is
  never LOADed on a prep chapter (party joins via a separate join-LOAD).
- Force-deploy = `gForceDeploymentList` (data_event_trigger.c) — **#42's patch point**,
  alongside `CanUnitSeize` (bmdifficulty.c:61) and the game-over flag.
- `prepScreenNumber` (chapter settings) = 2 × chapter number (double-wide glyph index).

## NEXT SESSION (in order)
1. **#42 player-chosen lord** (the last engine chunk of the slice):
   - Menu after ch00 ending (or at ch01 start before preps?) — design with Nicolas.
   - Persist choice (candidate: one permanent EVFLAG per PC; scan to recover pid).
   - Patch points (all traced): `IsCharacterForceDeployed_` (eventinfo.c:1948) for
     force-deploy; `CanUnitSeize` (bmdifficulty.c:61, vanilla hardcodes Eirika/Ephraim);
     chosen lord's defeat quote gets `EVFLAG_GAMEOVER` (gDefeatTalkList HEAD rule).
   - Until #42: Braulo rides EIRIKA → vanilla seize + vanilla game-over quote already
     work for the default lord (playtests can proceed).
2. **Goblin art decision with Nicolas (in-slice per his 2026-06-10 note):** map sprites +
   boss portrait for soldier/fighter/armor-knight goblins. FE-Repo reskin bases ([[reference_fe_repo]]);
   grunts currently show vanilla class names + sprites; chief shows vanilla Breguet face
   in his death quote (msg 0x961 staging uses FID_Breguet).
3. **ch01 win/gameover playtests**: extend the `ch01` scenario (or add `ch01win`) to march
   the 4 onto the chief and seize (Braulo/EIRIKA can seize pre-#42); gameover = feed
   Braulo to the goblins. Reuse pokeFrail.
4. **Goodberry rename** (Vulnerary→Goodberry party-wide) — lands within this slice.
5. **Dialogue pass LAST**: Northlook opening (hand-off scene from ch00 ending beats),
   house hints (placeholders shipped at 0x93B/0x93C), road sign 0x955, ending 0x954,
   chief quote 0x961; then `record` GIFs → Nicolas sign-off.
6. Carried: #29 world map; Scramsax Hero mug [F2E] license recheck; ch02+ YAML
   `ea_file:` schema cleanup; GitHub housekeeping (#21 slice checklist, #42 comment)
   — still permission-blocked, run `gh` with Nicolas present.

## What was wired this session (tools/build_campaign.py `inject_ch01`)
- Hosted on **slot 2** (CHAPTER_L_2; ch00's `MNC2(0x2)` target; slot-N+1 pattern).
  MUST run BEFORE `inject_prologue` (reads vanilla slot 1's Seize goal template).
- Map: `Ch01IronTrailMap` asset + winter tileset; goal copied from vanilla Ch1 (Seize);
  `prepScreenNumber=2`; texts: goal 419/415 = "Seize camp", title 0x162, BREGUET name →
  "Goblin Chief"; title card `chap_title_2.png` = "Ch.1: The Iron Trail" (atlas grew
  T/i/l/n/o + whole-word "Ch.1:" (img1) and "The" (img0) cuts).
- Rosters (events_udefs.c, vanilla symbols reused — NO extern surgery):
  `UnitDef_Event_Ch2Ally` = 4-slot deploy template (cap); `UnitDef_088B440C` = 8-cast
  join LOAD; `UnitDef_088B4344` = 7 goblins (chief = BREGUET slot, lv4 armor knight on
  seize tile (21,7), vanilla AI bytes per role); `UnitDef_088B44AC` = 3 west turn-3
  reinforcements (vanilla `EventScr_LoadReinforce` idiom, TURN/FACTION_ID_BLUE).
- Events (ch2-eventinfo/eventscript, vanilla symbols reused): beginning = DISA both
  ch00 guests (DISA = ClearUnit = real party removal; Orson's idiom) → LOAD goblins →
  LOAD cast → CALL(EventScr_08591FD8) → ENUT(8); Location = House(1,7)+House(13,2)+
  Seize(21,7); Misc = road-sign AREA(8,8) + CauseGameOverIfLordDies; ending =
  victory sting + placeholder text + `MNC2(0x3)`.
- Chief defeat quote at gDefeatTalkList HEAD (no flag — Seize wins, not the kill).

## Tried/learned this session
- **Slot 2+ loaded as SKIRMISH** (black screen, `EventScr_SkirmishCommonBeginning`
  running instead of our scene): `GetBattleMapKind` (worldmap_path.c) classifies
  node-slot chapters by gGMData world-map state; we never populate it → fallback was
  SKIRMISH. Engine hardening `_patch_battle_map_kind_fallback`: no-node fallback →
  STORY. Slot 1 is in the hardcoded STORY list — why ch00 never hit this.
  **Debug recipe that found it:** harness dumps sProcArray script ptrs + EventEngineProc
  `+0x30 evStart/+0x38 evCur` on failure → `arm-none-eabi-nm` the addresses.
- Post-chapter SAVE MENU sits between MNC2 and the next chapter's events — playtest
  must A-tap through it (and must STOP tapping once SALLYCURSOR appears: A toggles
  Pick Units).
- Engine natively benches over-cap parties (SortPlayerUnitsForPrepScreen); join-LOAD
  positions are irrelevant (PREP hides + redeploys onto template tiles). Verified:
  deployed 4 land exactly on YAML deploy tiles; benched park at x=-1 hidden.
- Vanilla ch1 enemy AI bytes (decomp): soldiers hold `{0x0,0x3,0x9,0x0}`, fighters
  pursue `{0x0,0x0,0x1,0x0}`, Breguet `{0x3,0x3,0x9,0x20}`, reinforcements
  `{0x0,0x0,0x9,0x0}` — now in build_campaign CH01_AI.
- Title-card glyphs are cursive-joined: cut letters carry neighbor strokes; calibrate
  cuts against the atlas's known-good 'a', render 4x, eyeball, trim (o needed -1 col).
- Map-shot gotcha: the "unit cluster" at the map's top-left is painted fort terrain,
  not sprites — check the authored render before chasing ghosts.
- iron-ingots MacGuffin: no FE8 item; recovery is narrated in the ending (YAML notes it).

## Current state
- ✅ `make` green; `verify_text` 0 runaway; playtests: ch00 win/gameover/retreat PASS,
  **ch01 PASS** ("preps shown, guests gone, 8-unit party fields exactly 4").
- ✅ Pushed `39b6c18` (inject_ch01 + GetBattleMapKind patch + atlas + ch01 scenario +
  decisions.md §prep mechanism + §STORY fallback).
- ✅ Prep screen in-game: "Chapter 01 / Seize camp / Pick Units…/ START: Fight!".
- ⚠️ Cast = 8 classed units (pepperjack & brie are still name-only, no class YAML) —
  party=8 assert in the harness will need bumping when they get classes.
- ⚠️ House/sign/ending texts are functional placeholders pending the dialogue pass.
- ⚠️ ch01 ending MNC2(0x3) lands on vanilla Ch3 until ch02 is wired.
- ℹ️ ch02+ YAMLs still carry aspirational `ea_file:` fields (schema cleanup, carried).

## Blockers
- None. (#42 menu UI is the biggest remaining unknown; everything it patches is traced.)

## Key files
- `tools/build_campaign.py` — `inject_ch01` (the new model for chapter injection;
  supersedes inject_prologue as the reference), `_patch_battle_map_kind_fallback`,
  CH01_* constants.
- `tools/playtest/harness.lua` — `winCh00()` helper + `ch01` scenario (+ proc/unit
  dump diagnostics on failure); `gen_symbols.py` grew gProcScr_SALLYCURSOR.
- `campaigns/.../chapters/ch01-the-iron-trail.yaml` — slice source of truth.
- `docs/decisions.md` — §prep mechanism, §STORY fallback (both dated 2026-06-10).
- `fireemblem8u/src/eventinfo.c:1948` `IsCharacterForceDeployed_`;
  `src/bmdifficulty.c:61` `CanUnitSeize` — #42 patch points.
- `tools/gen_chapter_title.py` — glyph atlas (now covers Ch.N: prefixes).

## Gotchas (carried)
- Story text: YAML `script:` → build_campaign generates bodies; `make` overwrites manual
  decomp edits. Gate: `python3 tools/verify_text.py`.
- Odd-length NAME strings: pad with [.] (terminator parity).
- gDefeatTalkList: chapter-keyed entries at the HEAD; never after `{.pid=-1}`.
- Vanilla facts: `git -C fireemblem8u show HEAD:<file>` — the working tree holds OUR
  injected artifacts (ch1-eventudefs.h = ch00 cast; ch2-* = ch01 now!).
- Bash cwd drifts between tool calls — `cd` to repo root for git/make (bit again).
- **PNG → `open` (Preview); GIF → `open -a Safari`.**
- Synthetic macOS keypresses don't reach mGBA; in-emulator Lua is the path.
- Frostmaiden book: `references/References/icewind-dale-...pdf`; DM notes:
  `/Users/Yonick/Documents/Claude/Projects/Manchego Stars / Fire Emblem Game/References/DungeonMasterNotesIcewindDale.pdf`.
  PDF page = printed page + 1.

## Memory
[[manchego-stars-project]] · [[feedback_fe-strictness]] · [[feedback_use_decomp]] ·
[[manchego-stars-automated-playtests]] · [[feedback_collaborative_map_design]] ·
[[feedback_answer_before_picker]] · [[feedback_show_before_committing_art]] ·
[[reference_fe_repo]] (goblin reskins next)

## Standing rules
Combat = pure vanilla FE; **field parity with vanilla ch N (both sides) is doctrine**
(the cap is the parity; Pick Units only chooses who fills it). Story/dialogue =
collaborative (variants → Nicolas picks); art shown before committing. Auto-push to
main once green; never commit the `fireemblem8u` submodule pointer. Playtests
machine-run for logic, Nicolas for feel.
