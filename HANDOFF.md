# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-08-21 (Claude). Deep-cleaned 2026-08-20 at Nicolas's instruction: anything already
recorded in `docs/decisions.md`, `CLAUDE.md` or a GitHub issue was deleted from here rather than
restated. Five gotchas that lived ONLY here were migrated into `decisions.md` first — check that
a thing has a home before cutting it.

## In flight

**Nothing.** `main` is at **#297**, CI green.

## Next task

**ch05's dialogue is DONE — every scene and every fallback is wired and proved.** What is left:

- **Two ending arms are unfilmed** — `--ch05-ending=no-sahnar` and `=basil-died` boot straight to
  each, so this is two short runs and nothing else.

**Then ch06**, which is unhosted; ch05's win still lands on the RBG campfire dev placeholder, and
that is BY DESIGN — the placeholder IS the "next chapter" slot.

**Both former open questions are RULED (Nicolas, 2026-08-21), are ADRs, and are DONE — do not
re-raise either.** Reskins keep their donor's class name, deliberately. And the character wrap is
retired: dialogue is measured in PIXELS against the window it actually renders in (#298).

## Recently landed — do not redo

Each of these is DONE, merged, and documented where it belongs. Listed only so a fresh session
does not reopen one; the detail is on the issue and in `docs/decisions.md`.

- **Dialogue wraps by PIXELS now, not characters** (#298) — three budgets in
  `tools/fe8_talk_font.py`, each measured on the window it belongs to: 203px talk bubble,
  192px auto-centered helpbox (narration + the lord-select explainer), 143px battle bubble
  (every taunt and death quote — `PutTalkBubble` FORCES that one to 20 tiles and ignores the
  text width). 60 fewer A-presses campaign-wide, no word moved. ⚠️ **A wrap change is gated by
  rendering every message under both versions and DIFFING them, not by the test suite** — three
  breakages sailed through all 546 tests and only the diff caught them; `decisions.md` has the
  method. And a press count is now a fact about the SCRIPT: the wrapper never invents a page
  break, so presses == authored boxes.
- **The Talk recruit's no-Lupin arm** (#297) — the last fallback, in `ch14a-eventscript.h`'s
  shape (a whole message per arm, converging on a shared LABEL, one CUSA). With it, **all four
  `CHECK_ALIVE` states are RUN, not read**: benched and recruited-then-killed closed by
  `ch05lupinbenched` / `ch05lupinkilled`. ⚠️ Two traps paid for and recorded in `decisions.md`:
  **box count is no longer a "which id played" witness** (this scene's two arms are both 21
  A-presses — use `INSPECT.activeMsg()`, which reads `sActiveMsg` while a box is up), and a
  harness poke that benches or kills a unit **must set `US_HIDDEN` too**, or the next phase
  transition writes it back onto the tile grid.
- **ch05's dialogue, all 17 scenes** (#295) — both endings included, filmed at
  `docs/demo/ch05-ending.gif`. Four things that stretch settled are ADRs: the endings' BACKDROP
  channel and the `vanilla_scene.py` bug behind it, why a conditional block is a whole copy rather
  than a spliced beat, `CHECK_ALIVE` answering for ANY faction, and an ENCOUNTER not being a RECRUIT.
- **ch05's enemy reskins** (#296) — all four line classes on skeleton map sprites and skeleton
  battle anims, filmed. Board:
  `https://claude.ai/code/artifact/6a05e1ff-8938-49ed-8927-631d0e4dc6bd`.
- **Ravisin, complete** (#259, #261, #263, #286, #290, #291, #292) — portrait, stats, warning,
  death quote, battle anim, hand-edited anim palette, map sprite. ⚠️ Two traps already paid for
  and recorded in `decisions.md`: her palette is a BY-EYE call (do not reinstate the author's
  index-aligned enemy palette — it turns her hair teal), and her map sprite is HOODLESS on purpose.
- **ch05's Arena** (#265/#268), **the village-raid race and save-all payout** (#254), **the
  opening's seven scenes** (#25), **per-chapter battle grounds** (#289), **the ch01/ch07 winter
  CGs** (#256).

## Current state

- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
- **Checkout: `/Users/Yonick/Projects/manchego-stars`, the ONE tree** (#267). It is clean except
  for the intentionally dirty `fireemblem8u` submodule and Nicolas's untracked `.agents/` +
  `AGENTS.md` — preserve those and **stage paths explicitly**.
- **Two sandbox false negatives on this Mac, neither a real failure.** `gh auth status` reports
  the saved token invalid because a restricted process cannot read the macOS Keychain — run `gh`
  with escalation rather than asking Nicolas to log in again. And an mGBA GUI crash with an AppKit
  registration abort happened BEFORE the ROM ran; escalated emulator runs are normal, so diagnose
  ROM state only once it actually boots.
- **Cross-agent continuity:** Nicolas uses Codex only between Claude sessions. Codex must leave an
  explicit HANDOFF entry naming what it changed, the branch/PR and commit state, verification
  actually run, and the exact next step. Short-lived feature branches in this checkout, one at a
  time — **no worktrees unless Nicolas says otherwise**.

## Before you touch anything

Everything below used to be spelled out here and is now in its real home. This list is the INDEX;
do not re-inline the content.

- **How to work here** (the matrix rule, the boundary rule, feature-flow, the tool table) →
  `CLAUDE.md`.
- **Why anything is the way it is** → `docs/decisions.md`, 55 dated entries. The ones most likely
  to bite an unfamiliar session: *"Playtest runs are the most expensive thing in this repo"*,
  *"A scenario written against the old design will FAIL ON SUCCESS"*, *"An artifact is not its
  inputs"*, *"A community map sprite is keyed on GREEN, not on index 0"*, *"The TESTCH bench is
  bounded by SMS VRAM"*, *"A battle anim carries FOUR palettes and the engine picks one"*.
- **What is left to build** → GitHub issues, #20–#28 per chapter.
- **Which asset the FE-Repo has** → `docs/fe-repo-scouting.md`. ⚠️ Its table says where an anim
  LIVES, not what it does; open a candidate's mode folders before believing a gap.

Two live workflow facts that are not decisions and have nowhere better to sit:

- **After any ROM build, `make check` fails `test_difficulty` + `test_map_tileset` together.**
  That pair is the signature of reading the BUILT decomp tree. Fix, don't debug:
  `git -C fireemblem8u restore src/data/chapter_settings.json data/data_8B363C.s`.
- **`HANDOFF.md` is authored on `main` ONLY**, gated by `check.py check_handoff_only_on_main`. If
  the guard fires on a branch: `git checkout main -- HANDOFF.md`.
