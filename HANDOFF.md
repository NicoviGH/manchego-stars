# Handoff: **Prologue (#20) win/lose VERIFIED by automated playtests; next = title card + cutscenes/dialogue + portraits.**

**Date:** 2026-06-09
**Session focus:** (a) Nicolas's manual playtest exposed two ch00 bugs (boss kill didn't end
the chapter; boss inert) — root-caused and fixed; (b) built an **automated mGBA playtest
harness** (Nicolas asked if I could run playtests myself — yes), which caught two more real
bugs; (c) all three ch00 win/lose scenarios now PASS automatically.

**Live checklist = GitHub issue #20.** HANDOFF = current state + next steps; sub-steps -> TodoWrite.

---

## Current state
- ✅ **ch00 win/lose wiring DONE and machine-verified** (commits 7cbe18c + 6f79c73, pushed):
  - `tools/playtest/run.sh win` → PASS: boss kill plays quote, DefeatBoss fires, chapter advances.
  - `tools/playtest/run.sh gameover` → PASS: Hlin death → EVFLAG_GAMEOVER → game-over screen.
  - `tools/playtest/run.sh retreat` → PASS: Scramsax death → quote, battle continues, no game over.
- ✅ **Automated playtest harness** (`tools/playtest/`): mGBA **0.11 nightly** `--script` Lua API
  (auto-downloads to `tools/emulator/`, gitignored; stable 0.10.x has no `--script`). Closed-loop
  button injection + memory asserts: phase/turn (`gPlaySt`), units (`gUnitArray*`), menus &
  game-over via `sProcArray` proc scans, movement via the game's own `gBmMapMovement`. ELF
  symbols regenerated per run (`gen_symbols.py`). Deaths engineered by HP-pokes resolved through
  REAL combat so the whole event chain is exercised. Artifacts: `/tmp/playtest-<scenario>/`.
  Memory: [[manchego-stars-automated-playtests]]; rationale in `docs/decisions.md`.
- ✅ **Four ch00 bugs fixed this session** (all recorded in `docs/decisions.md` → "Chapter
  outcomes ride gDefeatTalkList" + "Win/lose…Misc event list" notes):
  1. Misc event list was emptied → BOTH win and lose watchers gone. Now carries
     `DefeatBoss(EventScr_Ch1_EndingScene)` + `CauseGameOverIfLordDies` (vanilla Prologue shape).
  2. Sephek AI was O'Neill's `{0x6,0x3}` = DoNothing+NeverMove (vanilla scripts O'Neill's attack).
     Now Breguet's `{0x3,0x3,0x9,0x20}` = attack-in-place, never move.
  3. Sephek had NO flagged `gDefeatTalkList` entry → EVFLAG_DEFEAT_BOSS never set (CA_BOSS alone
     sets nothing). Added entry with `EVFLAG_DEFEAT_BOSS`.
  4. Injected quote entries were shadowed by vanilla's generic `chapter=0xFF` death quotes
     (first match wins) → entries now injected at the table HEAD.
  Plus: goal banner said "Seize gate" (host chapter data) → vanilla Prologue `goal` block copied.
- ✅ Earlier state intact: map renders, deploy clean, Hlin sprite approved, difficulty tuned
  (Hlin unpromoted Fighter / Scramsax Hero / Sephek Myrmidon L5 + 2 Fighter guards).
- ⚠️ Win currently ends in a placeholder: victory sting + `MNC2(0x2)` hop (vanilla Ch2).
  Real ending cutscene (Sephek escapes → The Northlook) replaces it in the dialogue pass.
- ⚠️ All quote msgs are placeholders (Sephek 0x0936 / Hlin 0x0917 / Scramsax 0x0C25) until
  the dialogue pass.

## Tried but didn't work / gotchas
- Synthetic macOS keypresses (osascript) do NOT reach mGBA — in-emulator Lua scripting is the
  supported automation path. Stable mGBA 0.10.x lacks `--script`; use the vendored nightly.
- Naive "closest tile" marching gets units stuck on mountain maps — read `gBmMapMovement`
  (filled while a unit is selected; cost < 120 = reachable) and pick from real reachable tiles.
- Vanilla guard AI `{0x0,0xa}` does NOT pursue at long range (they engage when approached) —
  fine for ch00, but don't rely on enemies coming to you in future test scenarios.

## Blockers
- None. (Manual mGBA playtests by Nicolas are now only needed for art/feel/dialogue.)

## NEXT STEPS (priority order)
1. **Title card** "A Dagger of Ice".
2. **Cutscenes + dialogue** — opening (cold open / corner Sephek), mid-fight frost line, ending
   (Sephek "defeated" → escapes → hard cut to The Northlook; replaces the MNC2 placeholder).
   Co-written w/ Nicolas ([[feedback_collaborative_story_planning]]), not committed solo.
   Includes real lines for the three placeholder quote msgs.
3. **Portraits** for Hlin / Scramsax / Sephek — placeholder or vendored from FE-Repo (#19).
4. (When ch01 starts) extend the playtest harness: scenario per chapter objective; consider a
   `make playtest` target running all scenarios.

## Asset access (IMPORTANT — established pattern)
Pull a specific file from the **Klokinator FE-Repo** by **vendoring** it (2.3 GB — do NOT
submodule; never claim inaccessible) ([[feedback_vendor_community_assets]]):
```
gh api "repos/Klokinator/FE-Repo/contents/<url-encoded path>?ref=main" \
  --jq '.[] | select(.name=="<exact filename>") | .download_url'
curl -fsSL "<download_url>" -o campaigns/rime-of-the-frostmaiden/<dir>/<dest>.png
```
Credit the `{Artist}` from the filename in the asset dir's README + CREDITS.md.

## Build / run / playtest / debug
- Build: `make CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba` (green at session end;
  `make check` = drift guard). Regenerate indexes after YAML edits (`tools/gen_*_index.py`).
- **Automated playtest:** `tools/playtest/run.sh win|gameover|retreat` (exit 0 = PASS; log +
  screenshots in `/tmp/playtest-<scenario>/`; wipes the .sav; kills running mGBA instances).
- Manual run (art/feel): `pkill -9 -i mgba; rm -f fireemblem8u/fireemblem8.sav; "/Applications/mGBA.app/Contents/MacOS/mGBA" "$PWD/fireemblem8u/fireemblem8.gba" &` then New Game.
- Screen capture works (`screencapture -x -o out.png`); the harness also takes its own shots.
- Debug a crash: `mGBA -g <rom>` + `arm-none-eabi-gdb -q fireemblem8u/fireemblem8.elf`,
  `target remote :2345`, hardware watchpoint on the suspect global.
- **Env note:** if `make` dies on a missing module, point `python3` at one with
  numpy/pillow/pyyaml.

## Key files
- `tools/playtest/{run.sh,harness.lua,gen_symbols.py}` — the automated playtest harness
  (symbols.lua is generated; mGBA nightly lives in `tools/emulator/`, both gitignored).
- `tools/build_campaign.py` — `inject_prologue`: step 2 rosters/AI, step 3 Misc win/lose +
  begin/ending scenes, step 5 defeat quotes (HEAD insertion), goal-block copy in step 1.
- `campaigns/rime-of-the-frostmaiden/chapters/ch00-prologue-a-dagger-of-ice.yaml` — design SoT.
- `docs/decisions.md` — "Chapter outcomes ride gDefeatTalkList" + "Automated playtests" entries.
- `fireemblem8u/src/data_battlequotes.c`, `src/events/ch1-eventinfo.h` — build artifacts to
  inspect when verifying what actually got injected.

## Memory
- [[manchego-stars-project]] · [[manchego-stars-automated-playtests]] · [[manchego_stars_non_lord_cursor_crash]] · [[manchego_stars_guest_map_sprite_wiring]] · [[feedback_vendor_community_assets]] · [[feedback_chapter_vertical_slice]] · [[feedback_collaborative_story_planning]] · [[reference_fe_repo]]

## Standing rules
Combat = pure vanilla FE. Maps/sprites = vendor + reskin community/vanilla assets (not submodule).
Story/dialogue = collaborative with Nicolas. Engine guards stay campaign-agnostic. Auto-push to
main once green; don't commit the `fireemblem8u` submodule pointer. Playtests: machine-run for
logic, Nicolas for art/feel.
