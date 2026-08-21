# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-08-20 (Claude), and DEEP-CLEANED at Nicolas's instruction: anything already
recorded in `docs/decisions.md`, `CLAUDE.md` or a GitHub issue was deleted from here rather than
restated. Five gotchas that lived ONLY here were migrated into `decisions.md` first — check that
a thing has a home before cutting it.

## In flight

**Nothing.** `main` is at **#296**, CI green.

## Next task

**ch05 is content-complete.** What remains on it is small and precise:

- **The Talk recruit's no-Lupin fallback** (`0x9D1`) — the last of the three surviving fallbacks,
  and the only one still owed. It needs wiring AND its boxing at 29: it overruns the talk bubble
  and pages itself mid-clause if left flowed. This is the one channel where that still bites, the
  endings having turned out to be backdrop scenes at 42. Detail on **#25**.
- **Two `CHECK_ALIVE` states are unproven** — recruited-but-BENCHED and recruited-then-killed.
  Both should take the arm we want by a decomp reading, and a reading is not a run. ch05 deploys
  9 of a 10-unit pool, so benched-but-alive is reachable in ordinary play.
- **Two ending arms are unfilmed** — `--ch05-ending=no-sahnar` and `=basil-died` boot straight to
  each.

**Then ch06**, which is unhosted; ch05's win still lands on the RBG campfire dev placeholder, and
that is BY DESIGN — the placeholder IS the "next chapter" slot.

One open question Nicolas has not ruled on: **the reskin classes inherit their donor's CLASS
NAME**, so ch05's skeletons read "Soldier"/"Fighter", ch01's goblins read "Soldier" and ch03's
kobolds read "Brigand". No reskin in `campaign.yaml` carries a name. Campaign-wide change, not
ch05's — raise it before acting.

## Recently landed — do not redo

Each of these is DONE, merged, and documented where it belongs. Listed only so a fresh session
does not reopen one; the detail is on the issue and in `docs/decisions.md`.

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
