# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-08-22 (Claude). Deep-cleaned 2026-08-20 at Nicolas's instruction: anything already
recorded in `docs/decisions.md`, `CLAUDE.md` or a GitHub issue was deleted from here rather than
restated. Five gotchas that lived ONLY here were migrated into `decisions.md` first — check that
a thing has a home before cutting it.

## In flight

**Nothing.** `main` is at **#317** (`8b3b951`), CI green, no open PRs.

## Next task

**The #302 epic — read its body first.** It carries the measurement that reordered it, and the
board is at `https://claude.ai/code/artifact/269a5399-0385-49a8-af7a-ed069310c335`. Eight children
(#308-#315); **#308 is done** (#316 + #317).

**#310 is next and is now UNBLOCKED** — the 3.2x is already measured and sitting on the issue
(71s serial -> 22s at `--jobs 4`, zero deadline blowouts, per-scenario times identical). What is
left is raising the default for groups whose scenarios all resolve headless, keeping `jobs=1`
wherever a group contains a headed scenario, and retiring the "parallelism does not pay here" note
in `matrix.py` in the same commit.

**Then #309** — patch the linked ELF instead of rebuilding. Nine `rom_configs` are nine compiles,
and the gate's 24m51s is 5 builds plus 21 runs; headless took the runs, this takes the builds.
Then #311 / #312, then the declarative half (#313, #314, #315), then ch06 through it.

⚠️ **`gen_symbols.py` hardcodes `fireemblem8u/fireemblem8.elf`.** Pointing the harness at a
`.matrix-romcache` ROM from a different build reads shifted addresses and hangs at `boot stuck`
with procs that never change — which looks exactly like broken input and is not. Restore the ROM,
the ELF **and** `.build-config.json` from the same cache entry, then re-run `gen_symbols.py`.

**Tree state: the ROM is now `canonical`** (was ch03boot), restored from cache with its matching
ELF and stamp — every checkpoint builder runs on canonical, so verifying #317 needed it.
`tools/playtest/states/` now holds valid **`prep`** and **`ch02start`** (105,705 and 128,940 bytes,
99.4–99.5% non-zero, stamped `a44afcc2ac09:normal`); it was empty before, and four scenarios need
`ch02start`. A dead state is exactly **397,312 bytes of zeros** — that size is the tell.

## Recently landed — do not redo

Each of these is DONE, merged, and documented where it belongs. Listed only so a fresh session
does not reopen one; the detail is on the issue and in `docs/decisions.md`.

- **Verdict scenarios run HEADLESS** (#302/#308, PRs #316 + #317) — a `kind: verdict` scenario
  asserts on memory and needs no pixels, so it runs with no window and stops costing a watched
  run; `record`/`diagnostic` stay headed because their output IS the picture. `headless` is a
  DECLARED `matrix.yaml` field (`auto` derives it from `kind`), and `tools/build_mgba_headless.sh`
  builds the binary — nobody ships a macOS mGBA with headless AND Lua. ⚠️ **Nine traps in
  `decisions.md`** → "A verdict scenario needs no pixels", and three are the kind that bite
  silently: `emu:saveStateFile()` is broken headless (returns false, writes **397,312 bytes of
  zeros**, and every call site ignored the return, so a checkpoint builder run headless would have
  stamped a dead state VALID forever); **a verdict glob on the bare word matched a FAIL** whose
  reason text contained it, which is how the stamp got written anyway — classification is now one
  `verdict_passed()` helper, because four copies is why it was wrong in four places at once; and a
  failed rebuild must not delete a checkpoint it did not write. **Reading the code proved the guard
  fired; it did not prove what the caller did with the verdict.** Both directions are now proved by
  running them.
- **Traps are DECLARED, not inherited** (#302/#306) — `.traps` is a ChapterEventGroup field our
  injectors filled but never wrote, so ch06 (on `Ch7EventData`) would have shipped vanilla Ch7's
  two ballistae at its coordinates. ⚠️ Three traps in `decisions.md`: the placeable-type list is
  what `LoadTrapData` PLACES, not what `bmtrick.h` names (four enum values either do nothing or
  fall through — `TRAP_LIGHTARROW` hatches a gorgon egg); a file the build PATCHES must be in
  `PATCHED_DECOMP_FILES` or the previous build's rows survive; and **still owed on #302: the
  encounter-choice fields** (`playerUnits/enemyUnitsChoice{1,2,3}InEncounter`) are inherited on
  ch03 and ch05 — six vanilla skirmish rosters each, dormant only while we expose no world map.
- **All three difficulty modes, declared and proved in-engine** (#303/#304) — every chapter
  YAML declares its triple, `difficulty.py --mode` grades a named mode on both sides, and the
  `difficulty` scenario reads the red force off the map. ⚠️ Four traps recorded in
  `decisions.md`: a raw-pid unit inherits a `CharacterData` GAP and `baseLevel` is the field
  that decides whether the engine keeps its stat line or throws it away; **Def is a CLIFF on a
  boss, not a dial** (+1 moved Ravisin 13.4→20.1 rounds, +2 overshot to 40.2); a bar measured
  against vanilla is a MEASUREMENT, not a constant (Ravisin held "Saar's bar" for months after
  Saar moved); and **confirm the model reproduces the ROM before tuning content against a model
  number** — three level redistributions moved clear-load by 0.01, which was the clue.

- **Structural tooling, because grep kept answering questions it could not** (#300/#301) —
  `tools/callsites.py` (every call site with arguments BOUND to parameter names, which is what
  text search cannot do), two `check.py` guards, and a `.clangd` in the PARENT repo that makes
  the decomp indexable without touching the submodule. ⚠️ **Use `callsites.py` before changing
  any signature, and especially before changing what a parameter MEANS** — that second kind
  breaks no caller loudly and shipped three bugs the whole suite passed through.
- **All three ch05 ending arms filmed** (#299) — `docs/demo/ch05-ending-{no-sahnar,basil-died}.gif`.
  ⚠️ Two traps recorded in `decisions.md`: a ROM-config guard that compares only which flags are
  ON cannot tell three arms apart when they differ by a flag's VALUE, and the ending gate's box
  count is a FLOOR (it had been passing a wrong number for months) — the arm is asserted by
  message id, not by length.
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

- **Backlog swept 2026-08-22** — do NOT re-survey it by issue title or checkbox. ch03 taught that
  an unchecked box records what someone intended, not what the repo contains: #23 read as "7 open
  items" while git history and the live YAML showed the work shipped long ago. Cross-reference the
  artifact. Closed in the sweep: #303, #23, #133, #244. Still open and each carrying its own fresh
  evidence: **#135** (real v0.1.0 playtester feedback on art consistency and difficulty, never
  triaged) and **#30** (`campaign.yaml`'s `chapters:` block omits the prologue and is off-by-one
  from ch04 on — nothing reads it, so it misleads rather than breaks; a natural thing for #302 to
  derive instead of hand-keep).
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
- **What is left to build** → GitHub issues, #20–#28 per chapter; **#302** is the live epic.
- **Before a wide mechanical edit** → `tools/callsites.py`, then diff the OUTPUT. Three bugs
  shipped in one day from a regex sweep that all 546 tests passed through, and what caught them
  was rendering every message body under both versions and diffing (`decisions.md` → "We wrapped
  on-map talk at 29 CHARACTERS", §HOW THE ROLLOUT MUST BE GATED). Run that diff BEFORE the suite.
- **Which asset the FE-Repo has** → `docs/fe-repo-scouting.md`. ⚠️ Its table says where an anim
  LIVES, not what it does; open a candidate's mode folders before believing a gap.

Two live workflow facts that are not decisions and have nowhere better to sit:

- **After any ROM build, `make check` fails `test_difficulty` + `test_map_tileset` together.**
  That pair is the signature of reading the BUILT decomp tree. Fix, don't debug:
  `git -C fireemblem8u restore src/data/chapter_settings.json data/data_8B363C.s`.
- **`HANDOFF.md` is authored on `main` ONLY**, gated by `check.py check_handoff_only_on_main`. If
  the guard fires on a branch: `git checkout main -- HANDOFF.md`.
