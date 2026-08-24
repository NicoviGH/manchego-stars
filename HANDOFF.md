# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-08-23 (Claude). Deep-cleaned 2026-08-20 at Nicolas's instruction: anything already
recorded in `docs/decisions.md`, `CLAUDE.md` or a GitHub issue was deleted from here rather than
restated. Five gotchas that lived ONLY here were migrated into `decisions.md` first — check that
a thing has a home before cutting it.

## In flight

**Nothing.** `main` is at **#328** (`c5d326b`), CI green, no open PRs.

## Next task

**#135's ch01 finding — read the triage comment on the issue first.** A v0.1.0 playtester
reported ch01's enemy healing as *"confusing... or it was a glitch"*. It is neither a glitch nor
our invention: the 12 fort tiles came with the `Ch13EirikaMap` base layout at identical
coordinates, and the castle gate at (21,7) is ours, for Seize. Two healing terrains, two vanilla
rates (20% / 10%).

What the triage actually turned up is bigger than the report: **our Guide is effectively empty.**
We null vanilla's tutorial lists on every hosted slot (`build_campaign.py:3216`, `:7939`), so no
vanilla `ENUT` ever runs, and `IsGuideLocked()` hides the Guide map-menu command entirely unless
some entry's `displayFlag` is set. Of the 56 flags the Guide uses, our game sets exactly **one** —
234 ("Arena"), in ch05's arena beat. So ch01–ch04 appear to have **no Guide command at all**, and
from ch05 it lists one topic.

⚠️ **That last claim is a STATIC CHAIN, not an observed run — disprove it before building on it.**
The Guide command is menu id `0x74` (`menu_def.c`) and the controller already dumps `menu.items`
with `override_id` in every action record, so a headless ch01 verdict scenario settles it for free.
The fix, if it holds, is our own existing pattern: ch05's arena beat is already a verbatim
vanilla-shaped tutorial (`CAMERA → CURSOR_FLASHING → TUTORIALTEXTBOXSTART → TEXTSHOW → ENUT`,
`build_campaign.py:10520`); ch01's is the same shape with `ENUT(206)`.

**Nicolas's bar here is VANILLA PARITY and nothing more** (2026-08-24): *"we don't need to explain
it any more than vanilla does. as long as we have that guide players can reference we're good."*
Vanilla does explain it — a forced Ch1 tutorial box that flashes the tiles and names Breguet on his
gate — so parity is that beat plus the Guide entry, not a new system.

The art-consistency and prologue-difficulty halves of #135 are still untriaged.

**Then ch06 (#26), which is the #302 epic's own Definition of Done** — "ch06 costs materially fewer
evenings than ch05 did". `make chapter CH=ch06` is the orientation: not hosted, no difficulty
declared, 4 of 4 events unscripted, Messie has no portrait/map sprite/battle anim. Everything else
on #302 is model built against a guess until a real chapter runs through it, which is the "golden
cage" failure the epic names.

**Deferred on purpose, both with reasons on their issues:** #327's tail thinning (comfort, not
safety — the ceiling is measured in every chunk and frozen now) and #315's test ELF (assertion cost
was never the bottleneck; watched-run cost was, and #308–#311 fixed that).

⚠️ **`gen_symbols.py` hardcodes `fireemblem8u/fireemblem8.elf`.** Pointing the harness at a
`.matrix-romcache` ROM from a different build reads shifted addresses and hangs at `boot stuck`
with procs that never change — which looks exactly like broken input and is not. Restore the ROM,
the ELF **and** `.build-config.json` from the same cache entry, then re-run `gen_symbols.py`.

**Tree state: the ROM in the tree is `ch05boot`** (CH05BOOT=1) — the last build of the 2026-08-24
verification runs, not canonical. `tools/playtest/states/` still holds valid **`prep`** and
**`ch02start`** stamped for the CANONICAL ROM, so anything wanting them needs canonical back in the
tree first. A dead state is exactly **397,312 bytes of zeros** — that size is the tell.

**The ROM cache is WARM** for `canonical`, `testch`, `ch03boot`, `ch04boot`, `ch05boot`,
`ch05lupinboot`, `ch05mooseboot` and the three ch05 ending arms (2026-08-24). #314 touched
`Makefile`, `tools/build_campaign.py` and `tools/inject/` — all `ROM_INPUT_PATHS` entries, so
`rom_input_hash` folded and every configuration missed once; the eight builds that followed
re-warmed it. #327 touched only `tools/check.py`, which is not an input, so the cache survived it.

## Recently landed — do not redo

Each of these is DONE, merged, and documented where it belongs. Listed only so a fresh session
does not reopen one; the detail is on the issue and in `docs/decisions.md`.

- **Every ChapterEventGroup field is WRITTEN or DECLARED-INHERITED** (#313, PR #325) — the
  build fails on anything nobody has ruled on. ⚠️ `decisions.md` → "Every ChapterEventGroup
  field is WRITTEN or DECLARED-INHERITED": the census compares the field's **TARGET**, not the
  initializer token, because our injectors keep the donor's symbol and rewrite what it points
  at — a token census calls ~20 fields per chapter inherited when almost none are. It is also
  meaningful **only on an injected tree** (`injected()` gates it; CI runs `make test` before
  the build). **Nicolas ruled the six skirmish rosters KEPT** — vanilla has optional
  skirmishes so we do too, wired with the world map (#29), and deliberately not nulled. The
  guard found a sixth instance of the failure class on its first run: ch02 alone inherits
  `miscBasedEvents`, correct by coincidence of design rather than intent.
- **A chapter's status is DERIVED** (#312, PR #324) — `make chapter CH=chNN`, above. ⚠️ Two
  things in `decisions.md` → "A chapter's status is DERIVED": a message BLOCK range must be
  DECLARED and never inferred from the ids a chapter claims (a range computed from its own
  contents can only report itself as full, which is the one question it exists to answer), and
  a degraded mode must say *cannot tell* rather than report a wrong number — six of the nine
  review findings on this were fallbacks that lied. The chapter YAML now has ONE reader,
  `tools/campaign_chapters.py`, shared with the `docs/CHAPTERS.md` generator.
- **A scene is readable without a ROM** (#311, PR #323) — `make scene`, and `docs/scenes/ch05.md`
  as the golden. It renders nothing itself: each ch05 scene is already a pure
  `chap -> [(msg_id, body)]` builder, so the preview calls the SHIPPING builder and reads its
  output back. ⚠️ **`decisions.md` → "A scene is readable without a ROM"** carries the correction
  that came out of it: *presses == authored boxes* was written down twice (in #311's own scope
  and in a `decisions.md` postscript) and is **false** — a turn pages at two lines and each page
  is its own `[A]`, so ch05 scene 1 is 19 authored boxes and costs 23. A press count is a fact
  about the WRAP, readable only off the body. Same ADR has the three reader traps, each of which
  renders a plausible wrong scene.

- **The merge gate is bounded** (#302, PR #322) — it was 21 scenarios and 5 builds five chapters
  into an 18-20 chapter game, and an accumulating gate is ~130 scenarios / ~18 builds by ch18: not
  a slow gate, an unrun one. The window (spine + last two hosted chapters) is DERIVED from
  `inject/hosts.py`, so hosting a chapter ages the oldest out; depth moves to that chapter's suite
  and still runs in `--all`. ⚠️ `decisions.md` → "The gate is the spine plus the last two
  chapters" records what was deliberately NOT added: one smoke per chapter in the gate, because
  each drags its own ROM build — which is now the stated trigger for #309 phase 2.
- **A new scenario no longer kills its running siblings** (#310, PR #321) — `run.sh` opened every
  run with `pkill -9 -i mgba`, so with four scenarios in flight each new dispatch SIGKILLed the
  ones already going; the first full gate lost `ch01`, `ch04moose` and `ch04packmath` to it, all
  reporting `mGBA exited early` as though the ROM were broken. The kill is scoped to the
  scenario's own `/tmp/playtest-<name>/` now, and `gen_symbols.py` writes its three shared tables
  through a rename. ⚠️ `decisions.md` → "A blanket `pkill` is a serial-world habit": **the
  4-scenario measurement that justified the parallel default could not have caught this**, because
  the first wave of four always survives — measure a fan-out change ABOVE its own concurrency.
- **A config switch stopped costing a whole build** (#302/#309 phase 1, PR #320) — the two
  battle-anim injection steps were 26 of the injector's ~35 seconds and no boot flag reaches
  either, so every one of the twelve `rom_configs` paid them for byte-identical data. They now
  restore 639 files instead of recomputing them: a config switch is **49.0s → 25.2s**, a
  same-config rebuild 59.7s → 25.5s. ⚠️ Traps in `decisions.md` → "A build is 50 seconds": the
  cache key is the argument and the `pre`/`post` digest map is the CHECK on it (a `pre`-only rule
  looked right and would have hit exactly never — nothing wipes the decomp between builds); and a
  step wrapped in `_x.run(...)` DROPS OUT of `check_injection_order` unless its parser is told,
  which has now bitten twice. `NO_INJECT_CACHE=1` turns the cache off.
- **Headless runs made parallel dispatch pay** (#302/#310, PRs #318 + #319) — the parallel lane is
  gated on `headless` per SCENARIO (a mixed group parallelises its headless half and runs the headed
  ones after, alone), and `--jobs` now defaults to `cpus // 2` capped at 4 instead of 1. 3.2x on the
  re-measurement; the 2026-08-09 "does not pay" note is retired in `decisions.md` and in `matrix.py`.
  Scenarios also report on COMPLETION now, because dispatch lines stopped being progress once four
  of them started at once.
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

- **Where a chapter stands is `make chapter CH=chNN`** (#312) — scenes declared vs written vs
  previewable, message-id headroom, art per named unit, which scenarios cover it and what each
  last said, and everything declared but unbuilt. `make chapter` with no `CH=` is all nine at a
  glance. **Do not write any of that into this file again**: it is derived on demand, so a
  generated answer cannot go stale and prose someone has to remember to update always does.
  Two things it says today that nobody had computed: **ch05's message block is FULL**
  (`0x9E4-0x9F5`, all 18 spent — the next ch05 scene costs a redesign, not an id), and **ch01
  declares five events and has written two.**
- **Backlog swept 2026-08-22** — do NOT re-survey it by issue title or checkbox. ch03 taught that
  an unchecked box records what someone intended, not what the repo contains: #23 read as "7 open
  items" while git history and the live YAML showed the work shipped long ago. Cross-reference the
  artifact. Closed in the sweep: #303, #23, #133, #244. Still open and each carrying its own fresh
  evidence: **#135** (real v0.1.0 playtester feedback on art consistency and difficulty, never
  triaged) and **#30** (`campaign.yaml`'s `chapters:` block omits the prologue and is off-by-one
  from ch04 on — nothing reads it, so it misleads rather than breaks). #30 is now cheap: since
  #312 there is one reader for the chapter YAML (`tools/campaign_chapters.py`), so that block
  can be derived from it rather than hand-kept.
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
