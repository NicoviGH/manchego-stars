# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-08-28 (Claude). Deep-cleaned 2026-08-20 at Nicolas's instruction: anything already
recorded in `docs/decisions.md`, `CLAUDE.md` or a GitHub issue was deleted from here rather than
restated. Check that a thing has a home before writing it here.

## In flight

**Nothing.** `main` is at **#331** (squash-merged 2026-08-28), the branch is deleted and the tree is
clean. **#26 stays open**: the map is done, the chapter is not.

**The design board** (rebuilt 2026-08-28 around the chapter YAML schema — every open decision names
the field it writes): `https://claude.ai/code/artifact/6952f53d-0fde-4a0f-b07c-b8fc846d6f10`
**Issue #26 carries the same list as a checklist.** Read the issue for scope, the board for reasoning.

## Next task

**The ch06 enemy roster (D5) — Nicolas asked to do this one together.** Everything the decision
needs is now on disk:

- **The bar is FE8 Ch6**: 24 enemies (27 Difficult), avg L6.2 — 6 Soldier, 3 Fighter, 3 Knight,
  3 Cavalier, 2 Mercenary, 2 Shaman (`docs/fe8-guide.md`).
- **The donor is not the bar.** Ch13 Ephraim ships 58 enemies, 19 of them Cavaliers, on "defeat
  all" — an attrition brawl, and cavalry is exactly what our river punishes. Do not import it.
- **Density already works out.** Ch6's map is 580 cells and ours is 484, so 24 enemies is slightly
  DENSER than vanilla Ch6. No scaling argument needed.
- ⚠️ **The seed is wrong and will mislead you.** `enemy_units:` still declares 9 (Messie + 8
  "Knucklehead Swarm"), and that swarm is class `gargoyle` — a **flier**. Fliers ignore the
  concentric water the whole map exists to enforce, so the seed defeats the map's own premise.
- **Water-bound mermaids** is the open proposal, not a decision: the rings become their highway,
  the 8 crossings become the player's chokepoints, and Pinky covers the deep boat — turning the
  map's flier bias into a division of labour rather than a monopoly.
- **Placement facts** (measured, from the donor's own deploy block x4-10/y0-2): a flier reaches all
  484 cells by turn 5; foot reaches every one of the 306 passable cells; both boats are turn 6 on
  foot, 5 on cavalry, 3 by air. `TERRAIN_RIVER` is impassable to foot/armour/horse, cost 2 to
  Pirate, 1 to flier; `CLIFF` and `PEAK` are impassable to everything but fliers.

Then, in Nicolas's order: **the beats** (mine vanilla Ch6's cutscenes, then map our story onto it),
then **Messie's art**.

**Messie's map sprite is NICOLAS'S, not ours** — he took it back mid-session ("I'll handle it").
Do not re-open it unprompted. The PixelLab verdict, if it comes up: it produces genuine
native-resolution pixel art that passes `map_sprite_tool` (32x32, <=16 colours, forced onto a bank),
but its text model does not know what a plesiosaur is. **34 of 40 trial generations left.**

## What ch06 still owes

`make chapter CH=ch06` derives most of it — do not restate that here. Two things it cannot see:

- **`inject_ch06` must call `_register_tileset(campaign, 'snowy-bern-ice', 'SnowIce', ...)`.**
  `TILESET_STEMS` knows the name, but `_register_chapter_map` then looks up `ObjectTypeSnowIce` /
  `MapPaletteSnowIce` / `TileConfigurationSnowIce` in the asset table and the first build
  `sys.exit`s without them. Sharing `Snow` would draw ch06 in ch04's palette.
- **Both boarding scenes are declared with empty `text:` on purpose.** The boat crews have no voice
  bible, and drafting before that pass is how dialogue drifts.

⚠️ **`gen_symbols.py` hardcodes `fireemblem8u/fireemblem8.elf`.** Pointing the harness at a
`.matrix-romcache` ROM from a different build reads shifted addresses and hangs at `boot stuck`
with procs that never change — which looks exactly like broken input and is not. Restore the ROM,
the ELF **and** `.build-config.json` from the same cache entry, then re-run `gen_symbols.py`.

**Tree state: the ROM in the tree is still `ch05boot`** (CH05BOOT=1). Nothing was built on
2026-08-28. `tools/playtest/states/` still holds valid **`prep`** and **`ch02start`** stamped for
the CANONICAL ROM, so anything wanting them needs canonical back in the tree first. A dead state is
exactly **397,312 bytes of zeros** — that size is the tell.

**The ROM cache is WARM** for `canonical`, `testch`, `ch03boot`, `ch04boot`, `ch05boot`,
`ch05lupinboot`, `ch05mooseboot` and the three ch05 ending arms (2026-08-24). Untouched since.

## Map sprites — read before any art session

All of it is in `docs/decisions.md` → **"A map sprite is 32x32 or it is nothing"**: the hard engine
ceiling, why size reads as FILL, why geometry is derived from the donor and never from sheet pixels,
why a decomp sheet's palette is a meaningless leftover, what `footprint:` actually means, and the
WALK-vs-GLIDE split that decides whether PixelLab is worth paying for. Do not restate it here.

## Recently landed — do not redo

**#331 (2026-08-28) — ch06's map is painted, compiled and committed.** Detail lives in
`docs/decisions.md` → *"ch06 departs from its donor's terrain in 21 declared cells"* and
*"The DONOR and the BAR are different chapters"*; the one-line version:

| | |
|---|---|
| `campaigns/.../maps/ch06-maer-monster.mar` | 22x22 on `snowy-bern-ice`, round-trips byte-exact |
| `snowy-bern-ice` | snowy-bern + 4 palette entries + 21 metatiles in slots snowy-bern declares unused; `.4bpp` byte-identical, `snowy-bern` and ch04 untouched |
| `terrain_divergence:` | 21 declared cells, 0 undeclared; the import guard rejects anything not listed |
| `forest_composition: replaced` | ch06 has no trees, so #193's sequence guard is exempted for FOREST only — the "deliberate departure" clause, taken explicitly |
| boats | two green `CLASS_FLEET` units, not tiles and not villages; a dead NPC stops offering Talk exactly as a burned village stops offering Visit |

⚠️ **Three guards shipped DEAD earlier that day and were fixed in the same PR** — the lesson
generalises: `_declared_divergence` matched the chapter `id` against the map stem and loaded zero
rows; `validate_vanilla_retile` compared the tileset by NAME and skipped 25 protected cells for any
variant. Both had a green suite because nothing exercised them. If you add an escape hatch to a
guard, add the test that proves the hatch opens **and** that the guard still shuts.

### Earlier



DONE and merged. One line each, so a fresh session does not reopen one. **The detail is in the
named `docs/decisions.md` ADR or on the issue — deliberately not restated here.** Where no ADR is
named, the issue is the record.

**The #302 epic — playtest cost and chapter tooling. All merged:**

| | ADR in `docs/decisions.md` |
|---|---|
| #308 verdict scenarios run headless | *A verdict scenario needs no pixels, so it runs HEADLESS* |
| #309 a config switch is 25s, not 50s | *A build is 50 seconds, and 26 of them were the same battle anims every time* |
| #310 parallel dispatch + the `pkill` that sabotaged it | *A blanket `pkill` is a serial-world habit, and parallel dispatch turned it into a saboteur* |
| #311 `make scene` — a scene without a ROM | *A scene is readable without a ROM, and a press count is read off the BODY* |
| #312 `make chapter` — status is derived | *A chapter's status is DERIVED, and HANDOFF stops carrying it* |
| #313 the ChapterEventGroup census guard | *Every ChapterEventGroup field is WRITTEN or DECLARED-INHERITED* |
| #314 a chapter declares its own scenarios | *A scenario is DECLARED by the chapter it tests* |
| #327 the Lua local-slot ceiling, measured then frozen | *The headroom guard measured one file correctly BY ACCIDENT* + *A CHAPTER is not what was filling harness.lua* |
| #302 the merge gate is bounded | *The gate is the spine plus the last two chapters; depth lives in the chapter suite* |

**ch05 is complete** (#25 and children): dialogue all 17 scenes (#295), enemy reskins (#296), the
no-Lupin Talk arm (#297), all three ending arms filmed (#299), the Arena (#265/#268), the
village-raid race and save-all payout (#254), Ravisin end-to-end (#259, #261, #263, #286, #290-292),
per-chapter battle grounds (#289), the ch01/ch07 winter CGs (#256). Reskin board:
`https://claude.ai/code/artifact/6a05e1ff-8938-49ed-8927-631d0e4dc6bd`

**Also landed:** #298 dialogue wraps by PIXELS (ADR *We wrapped on-map talk at 29 CHARACTERS; the
engine measures PIXELS*) · #300/#301 `tools/callsites.py` — **use it before changing any signature,
and especially before changing what a parameter MEANS** · #303/#304 all three difficulty modes
(ADR *Vanilla ships three difficulty modes, so we ship three*) · #306 traps are declared, not
inherited · #329 a donor is derived, not labelled (ADR *A base-map LABEL is prose — the donor is
DERIVED*) · #330 the drift lint now scans `.github/` and `.claude/skills/`.

⚠️ **Not landed, and it was buried in this list as though it were:** the **encounter-choice fields**
(`playerUnits/enemyUnitsChoice{1,2,3}InEncounter`) are still inherited on ch03 and ch05 — six vanilla
skirmish rosters each, dormant only while we expose no world map. Owed on #302.

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
- ⚠️ **Branch BEFORE editing, and check whether a file's "stale" content is already fixed on an
  unmerged branch.** 2026-08-28 cost a rework round: ch06's `parity_reference` read `FE8 Ch5` on
  `main`, so it got "fixed" there — while PR #331 had already corrected it on its branch. A whole
  session's work then had to be rebased off `main` and reconciled. `git branch --all --contains`
  and a look at open PRs answer this in seconds.
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
