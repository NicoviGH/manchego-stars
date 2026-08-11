# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-08-11 (Codex). `main` contains `54a4a1b`, the squash merge of PR #266, plus the
handoff correction that follows, and is level with `origin/main` after this handoff. **Issue #265
is the only feature in flight:** its local branch has the approved ADR but no implementation and no
PR. Clean context point for a fresh instance; the generated decomp tree is intentionally dirty as
recorded below.

## In flight

**#265 — winter Arena presentation.** Local branch: `feat/265-winter-arena-ui`. It contains one
unpushed documentation commit recording the settled ADR in `docs/decisions.md`; there is **no code,
no vendored portrait, and no PR yet**. The full executable scope and acceptance checklist live in
GitHub issue #265, not in a standalone spec. The issue's stale link to the deleted
`docs/superpowers/specs/...` file was corrected to the ADR during this handoff. Parent #25 now marks
the arena tutorial and onboarding ledger complete and leaves the #265 presentation checkbox open.

**#264 result:** PR #266 squash-merged as `54a4a1b`; issue #264 is closed and its short-lived remote
branch is deleted. Ch05 owns host messages `0x9E6`/`0x9E7` and a one-shot `AREA` event at arena tile
`(12,6)`. The callback rejects non-blue factions before entering tutorial mode, preserves vanilla's
camera/cursor/flag flow, and records `arena-wager` in the onboarding ledger. `inject_ch05` consumes a
dedicated wiring contract, so the onboarding test proves live builder outputs instead of grepping
for symbol names. The real `ch05arena` proof fired the lesson once, blocked replay, opened semantic
Arena command `0x62`, reached the inline TalkChoice, deducted the accepted 690G, and generated a
Pegasus Knight opponent. The apparent duplicate Braulo was disproved: the unit log has one player
character `0x01`; the similar sprites are tomb guards. Independent review had no remaining findings,
and GitHub `checks` + `build` passed on reviewed head `8ae6b83` before the squash merge.

## Next task

**#265 — implement the approved Arena presentation seam.** Read issue #265, the Arena ADR in
`docs/decisions.md`, `campaign.yaml`, ch05 YAML, and the real vanilla `ArenaUi_Init` path before
editing. The design is settled: keep vanilla graphics/TSA and mechanics; use a campaign-owned
four-bank cold-grey palette throughout Rime; use vanilla human face `0x67` by default; override only
ch05 with Generic Pretsel's pinned armored-skeleton portrait. Missing configuration must fall back
to untouched vanilla assets. Runtime support stays campaign-agnostic; campaign palette ownership
belongs in `campaign.yaml`, and the attendant override belongs in chapter YAML.

Continue on `feat/265-winter-arena-ui` after rebasing it onto this handoff commit. Follow the issue's
TDD order: write failing configuration/fallback/live-call-site tests first; vendor the exact pinned
FE-Repo asset and credit/source metadata; derive and validate exactly 64 GBA colors; generate the
campaign/chapter bindings; then extend the existing `ch05arena` proof to capture the cold palette and
skeleton while retaining its real wager/opponent assertions. Run focused tests, `make check`,
`verify_text`, a CH05BOOT proof build, and the final default build. Do not run the full matrix. Do not
create a standalone design/spec document: decision in ADR, execution checklist in issue #265.

## Current state

- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
- **Checkout path:** `/Users/Yonick/Documents/Codex/2026-08-03/Manchego Stars Codex` (the folder
  was renamed; do not use the former path). At handoff completion the checkout is on
  `feat/265-winter-arena-ui`, based on the pushed handoff commit on `main`, with one unpushed ADR
  commit and no implementation. The top level is otherwise clean except for the intentionally dirty
  `fireemblem8u` submodule plus Nicolas's untracked `.agents/` and `AGENTS.md`; preserve all three
  and stage paths explicitly. The submodule contains the full generated campaign build, not a
  pointer change to commit. Use a clean temporary checkout when a verification needs vanilla decomp
  state instead of resetting this working copy behind Nicolas's back.
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
- **The reliquary race is now announced on turn 2 (#261).** Ravisin's four boxes live at host-owned
  `0x9E4`, after the wave LOAD and before Sahnar's rise. Later waves do not replay it.
- **Ravisin's locked death quote is live (#263).** It owns host message `0x9E5`, uses her live
  Riev-slot face, and preserves `EVFLAG_DEFEAT_BOSS`; the later dev placeholder is still expected
  because the rest of the ending is not wired yet.
- **The arena tutorial and its full interaction proof are live (#264/#266).** The reusable
  `ch05arena` scenario now covers the one-shot lesson and the real Arena command through accepted
  wager, gold deduction, and opponent generation. Extend it for #265; do not replace it with a
  palette-only screenshot shortcut.
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

**A sandboxed `gh auth status` is a false negative on this Mac.** It reports NicoviGH's saved token
as invalid because the restricted process cannot read macOS Keychain. The same command outside the
sandbox authenticates correctly with `repo`/`workflow` scopes. Do not ask Nicolas to log in again;
run GitHub CLI commands with the required escalation so `gh` can reach the keyring.

**A sandboxed mGBA GUI crash is not a ROM crash.** The pasted AppKit registration abort happened
before the ROM ran because the GUI process was launched in the restricted sandbox. Escalated mGBA
proof runs are normal; diagnose ROM state only after the emulator actually boots.

**Arena proof must follow the real command, not sprite resemblance or token presence.** The action
menu's semantic Arena id is `0x62`; accepted flow reaches inline `gProcScr_TalkChoice`, mutates gold,
and generates the opponent in `gArenaState`. Likewise, a live-wiring test must inspect the generated
builder output and the `inject_ch05` consumer, not merely grep for `CH05_*` names.

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
