# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-08-10 (Opus). `main` = `600d9a6`, level with `origin/main`. **#253 and #254 both
merged; no branches, no stashes, nothing in flight.** Clean point for a `/clear`.

## In flight

**Nothing.** `origin` has only `main`.

**Nothing has had a `/code-review ultra <PR#>` — that is user-triggered.** #254 had a normal
`/code-review high`, which found five real defects (all fixed in the squash); #253 shipped
unreviewed.

## Next task

**Nicolas's call 2026-08-10: go back to the outlying ch04-era issues before any more ch05.**
Three cosmetic items, all with decided fixes already written on their issues:

1. **#24 — paint snowy-bern's `BRIDGE_SNAG` metatile 36.** The ch04 snag currently falls into a
   *stone bridge*: metatile 36 is DECLARED as `TERRAIN_BRIDGE_SNAG` but never painted, so
   `_is_blank_metatile` refuses it and `CH04_SNAG_BRIDGE_TILE = 2` (the ordinary masonry bridge
   this map already lays over this river) is the fallback. Paint a snow-dusted fallen trunk,
   point the constant at it, drop the fallback. `ch04snag` gates the mechanism and **cannot see
   the art** — this needs an eyes-on frame.
2. **#21 — Bryn Shander BG** → FE-Repo `Fenriel's BG/Winter BG 06` (Baxby's recruit currently
   plays over a green summer village).
3. **#27 — Bremen BG** → `Winter BG 04`. Both are already 240x160. Don't reuse
   `BG_MS_TARGOS_WINTER` a third time.

**ch05's remaining work is all on #25** and is text/art, not mechanics. The one with a hard
prerequisite is **`0x9C5`**: the eruption beat is written and LOCKED but cannot go on screen
until **Ravisin has a bust** — she is a raw pid (`CH05_BOSS_PID = 0xb8`) with no `PORTRAIT_MAP`
entry, which is also why her death quote `0x9C8` ships `.msg = 0` (a faceless line renders
boxless). Same blocker, one fix. Also owed: the Basil→Sahnar recruit text (`0x9CC`), the opening
(`0x9BA`–`0x9C4`), the arena tutorial, the no-Lupin branch, enemy reskins.

## Current state

- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
- **The full `make matrix` gate is NOT to be run locally any more** (Nicolas, 2026-08-10). Run the
  chapter suite or `matrix.py run --scenarios a,b,c`. **#255** is the fix that gives the gate a
  cheap home (verdict caching); until it lands the gate has none, because CI builds against a mock
  base ROM and cannot boot mGBA. Rules: `CLAUDE.md` → the matrix row, long form in `decisions.md`.
- `ch05raid` and `ch05crest` are new; `SUITE=ch05` now lists all five ch05 scenarios (it was stale,
  carrying `ch05village` alone).
- **ch05's village-raid RACE is wired and proven in-engine (#254).** A reliquary can be lost
  (raider AI → the tile flips to ruins, no gift, its event id never sets) and saving all four
  pays out vanilla's Guiding Ring at the ending. The `crest-of-cold-iron` is RETIRED: vanilla
  Ch5 has zero droppers, so Ravisin drops nothing and the relic is the race's prize.
- **The race is wired but UNANNOUNCED** until `0x9C5` gets on screen (above). Today the only
  warning is reliquary-south's line plus the engine's "The village was destroyed." popup.
- **ch05's opening and recruit still play VANILLA prose.** In-game this looks like a bug and is
  not one: `0x9CC` runs vanilla's Joshua/Natasha scene, and because Hlin Trollbane's bust is
  dressed onto the Natasha slot the player watches *Hlin* talk to *vanilla Joshua*.
- **Cross-agent continuity:** Nicolas uses Codex only between Claude sessions. Codex must leave an
  explicit HANDOFF entry naming what it changed, the active branch/PR and commit state,
  verification actually run, and the exact next step. Ordinary short-lived feature branches in this
  checkout, one at a time — **do not create worktrees unless Nicolas explicitly changes that.**

## Gotchas most likely to bite next (long form in `docs/decisions.md`)

**This session's headline: a scenario can FAIL on success, and it will blame the chapter.**
`ch05crest` reached its PASS state on its first run and reported FAIL three times running. Three
distinct causes, none of them the chapter: it read *"the chapter is over because we won"* as
*"the boss was never on the map"*; it drove input at a `US_HIDDEN` unit (the visitor still inside
a village event — every other scenario filters `US_UNSELECTABLE` alone, which is only right when
the party is standing still); and `chooseAttack` timed out **because** the kill landed, since a
boss death that ends the chapter never greys the actor out (pass its second exit). When a verdict
accuses the chapter, check the scenario is not describing its own bookkeeping.

**The runner-up: a terrain byte is not a picture.** `ch05raid` asserted `0x25` and passed while
its screenshot showed the wrong side of the map — the camera was wherever the fight was. Pan to
the thing, `wait()` for the scroll, then shoot. The frame now shows the engine's own tile panel
reading "Ruins".

The standing ones:

- **Read decomp data through `git show HEAD:`, never the built tree** — our injections are build
  artifacts. Signature: `make check` failing `test_difficulty` + `test_map_tileset` together right
  after a ROM build. Fix, don't debug:
  `git -C fireemblem8u restore src/data/chapter_settings.json data/data_8B363C.s`.
- **A HANDOFF/YAML lead is a hypothesis.** Proven twice now on the same line: the ch05 YAML
  asserted the save-all bonus was "Wired at inject_ch05" for months. Nothing was wired.
- **A declaration is not art.** `snowy-bern`'s metatile 36 carries `TERRAIN_BRIDGE_SNAG` and is a
  flat colour — which is #24's whole bug, and why `_drawn_block` verifies every cell it writes.
- **A scenario's verdict only covers what it READS.** `ch05village` passed for months proving
  nothing about three of the four doors, and nothing at all about the race.
- **Three data checks can pass while the thing is visibly broken.** Three ch05 faces rendered
  corrupted while the clip model, the on-disk sheets and an OAM probe all read clean, because the
  corruption happened at DRAW time from the slot's mouth/eye geometry. Verify rendering by looking.
- **Post-injection SMS ids and goal ids cannot be read from HEAD or the working tree** — run the
  injector and read the result.
- **A failing playtest may be the WRONG ROM.** Boot flags are per-chapter, and so is
  `PT_HOST_CHAPTER`. `run.sh` refuses this in 0s off `.build-config.json` — **do not reach for
  `MX_SKIP_ROM_CHECK=1`**. **Exception: `mapshot`/`mapfull` are chapter-GENERIC.**
- **`harness.lua` is one Lua chunk AT the 200-local ceiling** (2 slots free). Hang new helpers off
  an existing table (`INSPECT`, `TUNE`) or inside the scenario, never a new top-level `local`.
- **`HANDOFF.md` is authored on `main` ONLY** — gated by `check.py check_handoff_only_on_main`.
  If the guard fires on a branch: `git checkout main -- HANDOFF.md`.
- **Never commit the `fireemblem8u` submodule pointer** — it is dirty from build artifacts by
  design. `git add` paths explicitly (`git add campaigns docs tools`), never `git add -A` alone.
