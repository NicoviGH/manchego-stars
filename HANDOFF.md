# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-08-11 (Codex). `main` contains `9971e0e`, the squash merge of PR #259, and is
level with `origin/main` after this handoff. **Nothing is in flight.** Clean context point for a
fresh instance; the local build tree is intentionally dirty as recorded below.

## In flight

**Nothing.** PR #259 is squash-merged as `9971e0e`; issue #258 is closed. The remote feature
branch was deleted and local `main` is level with `origin/main`.

**#259 result:** Ravisin now dresses collision-free Riev with Nicolas's approved deterministic
palette edit of Garytop's FE-Repo Aversa mug (auburn hair, frost-pale skin, original brown
markings/geometry preserved). Her raw ch05 pid `0xb8` binds to portrait `0x48`, retitled
`MSG_246`, and the exact YAML `personal` boss line; the live status screen reads Ravisin rather
than Monster and shows HP 39 / Mag 10 / Skl 9 / Spd 3 / Lck 5 / Def 11 / Res 13. The review found
no Critical, Important or Minor issues. Both GitHub `checks` and `build` jobs passed; the real-map
`recordravisin` scenario passed, as did 208 build-campaign tests, 71 matrix tests, all Lua tests,
and `verify_text` (3404 messages, 0 runaway).

## Next task

**#25 — finish ch05, The Elven Tomb.** Read the live issue before choosing a slice; its checklist
is authoritative. Mechanics, map, parity, villages, reliquary race, Basil/Sahnar stats and
Sahnar's battle animation are already wired. Remaining work is dialogue/art: opening + ending,
four reliquary lines, Basil→Sahnar Talk, the five no-Lupin fallbacks, arena tutorial, Ravisin's
death quote, enemy reskins and the onboarding `introduces:` entry.

**Next slice: stage Ravisin's locked turn-2 eruption warning at `0x9C5`.** Its portrait dependency
is now satisfied. Invoke the repository's `dialogue-pass` workflow before inserting the four
already-approved boxes, claim `0x9C5` in `HOSTED_CHAPTER_MESSAGE_IDS`, add the `TEXTSHOW` beat to
the turn-2 wave script, run `python3 tools/verify_text.py`, and record/prove that smallest scene
on the real ch05 map. Once that beat is visible, wire Ravisin's already-authored death quote at
`0x9C8`; it was silent only because she previously had no face.

## Current state

- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
- **Checkout path:** `/Users/Yonick/Documents/Codex/2026-08-03/Manchego Stars Codex` (the folder
  was renamed; do not use the former path). Top-level `main` is clean except for the intentionally
  dirty `fireemblem8u` submodule plus Nicolas's untracked `.agents/` and `AGENTS.md`; preserve all
  three and stage paths explicitly. The submodule contains the full generated campaign build,
  not a pointer change to commit. Use a clean temporary checkout when a verification needs vanilla
  decomp state instead of resetting this working copy behind Nicolas's back.
- **One stash exists:** `stash@{0}: preserve pre-rename local HANDOFF before syncing #24`. It is
  historical insurance; do not apply or drop it casually.
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
- **Bryn Shander's ch01 ending and Bremen's reserved ch07 backdrop are vendored winter CGs**
  (#256). Bremen is banked at **8** palettes and nothing references it yet: ch07 must show it with
  a plain `BACG` or reconvert at `--banks 6`, because the fade/transition procs apply only six
  (`decisions.md` → the `bg_to_fe8.py` refit entry).
- **The race is wired but UNANNOUNCED** until `0x9C5` gets on screen (above). Today the only
  warning is reliquary-south's line plus the engine's "The village was destroyed." popup.
- **Ravisin's portrait/name/stats are complete (#259).** Raw pid `0xb8` does not pass through the
  regular cast identity injector, so all three are bound explicitly from the ch05 YAML / Riev
  slot. Do not add autolevel: vanilla Saar proves this boss pattern is class base + personal line.
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
