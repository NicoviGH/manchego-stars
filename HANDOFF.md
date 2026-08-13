# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-08-13 (Claude). **#255 and #274 are both DONE and merged — do not reopen
either.** The generated decomp tree is intentionally dirty as recorded below.

## In flight

**Nothing.** `main` is at #275 (the fast injector), CI green.

## Next task

**Back to ch05 content.** The build friction that was blocking it is gone: `make` is **21s
warm** (was 64.5s) after #274 took `build_campaign.py` from 50s to 18s, byte-identical. Both
#255 and #274 are closed; resist reopening them.

The most visible ch05 gap is the one under "Current state" below: **its opening and recruit
still play VANILLA prose**, so the player watches Hlin Trollbane's bust talk to vanilla Joshua.
That is a content job (`dialogue-pass`), not an engine one.

## Current state

- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
- **Checkout path: `/Users/Yonick/Projects/manchego-stars`** — the ONE tree (#267, closed
  2026-08-12). The old `Documents/Codex/...` copy and a stale 12-commits-behind copy are gone;
  both were audited for unpushed commits, unique branches and stashes first. The tree is clean
  except for the intentionally dirty `fireemblem8u` submodule plus Nicolas's untracked `.agents/`
  and `AGENTS.md` — preserve those and stage paths explicitly.
- **One stash exists:** `stash@{0}: preserve pre-rename local HANDOFF before syncing #24`. It is
  historical insurance for a file that has since been rewritten several times; do not apply or
  drop it casually.
- **The full `make matrix` gate is NEVER to be run locally** (Nicolas, 2026-08-10) — permanent,
  not pending anything; #255 deliberately dropped the code that would have retired it. Run the
  chapter suite or `matrix.py run --scenarios a,b,c`. Rules: `CLAUDE.md` → the matrix row.
  **`matrix.py run --suite X --dry-run` is free and says what would actually run** — reach for
  it before deciding a run is needed at all.
- **Both caches are warm and both were re-seeded on 2026-08-12.** `.matrix-romcache` was cleared
  when the ELF fix landed (every old slot was missing its `.elf`), so the first run of each ROM
  configuration rebuilds once. `.matrix-verdictcache` holds `ch05arena`.
- **ch05's Arena is complete (#265/#268).** Both views are winterized as palette DELTAS over
  vanilla — welcome screen 16 words of 64 (overcast sky, banner-blue awnings, **sandstone left
  warm on purpose**), combat coliseum 11 words (snow floor, blue banners). Ch05 alone gets the
  armored-skeleton attendant on the Glen slot. Before/after: `docs/demo/ch05-arena-*.png`.
- **`tools/rom_bg_preview.py` is new and worth reaching for.** It decodes a vanilla BG asset
  straight out of `baserom.gba` and paints it exactly as the GBA would, so palette work costs
  milliseconds instead of a build plus an emulator run. `--index-map` / `--isolate` answer "which
  index owns this, and does anything else share it?" It knows `arena_battle` and `arena_front`;
  adding an asset is a few lines. Use it before any recolour (ch07's Bremen backdrop, title screen).
- **ch05's opening and recruit still play VANILLA prose.** In-game this looks like a bug and is
  not one: `0x9CC` runs vanilla's Joshua/Natasha scene, and because Hlin Trollbane's bust is
  dressed onto the Natasha slot the player watches *Hlin* talk to *vanilla Joshua*.
- **ch05's village-raid RACE is wired and proven in-engine (#254).** A reliquary can be lost
  (raider AI → the tile flips to ruins, no gift, its event id never sets) and saving all four
  pays out vanilla's Guiding Ring at the ending.
- **Bryn Shander's ch01 ending and Bremen's reserved ch07 backdrop are vendored winter CGs**
  (#256). Bremen is banked at **8** palettes and nothing references it yet: ch07 must show it with
  a plain `BACG` or reconvert at `--banks 6`, because the fade/transition procs apply only six.
- **Ravisin is complete**: portrait/name/stats (#259), turn-2 eruption warning at `0x9E4` (#261),
  locked death quote at `0x9E5` (#263). Raw pid `0xb8` does not pass through the regular cast
  identity injector, so all three are bound explicitly from the ch05 YAML / Riev slot.
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

**A scenario can FAIL on success, and it will blame the chapter.**
`ch05crest` reached its PASS state on its first run and reported FAIL three times running. Three
distinct causes, none of them the chapter: it read *"the chapter is over because we won"* as
*"the boss was never on the map"*; it drove input at a `US_HIDDEN` unit (the visitor still inside
a village event — every other scenario filters `US_UNSELECTABLE` alone, which is only right when
the party is standing still); and `chooseAttack` timed out **because** the kill landed, since a
boss death that ends the chapter never greys the actor out (pass its second exit). When a verdict
accuses the chapter, check the scenario is not describing its own bookkeeping.

**A terrain byte is not a picture.** `ch05raid` asserted `0x25` and passed while
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
- **A recolour is a DELTA over vanilla, and a wash-out is a CHROMA failure.** Two Arena palettes
  passed every automated check and were rejected on sight; both held luminance and crushed
  saturation. Name only the words that change, and assert what stayed VANILLA as well as what
  moved. Reach for `tools/rom_bg_preview.py` before touching a palette — it answers "which index
  owns this?" offline. Long form: `decisions.md` → "A wash-out is a CHROMA failure".
- **CI runs `make test` BEFORE it mocks `baserom.gba`**, so nothing a unit test reaches may open
  the ROM. Keep config loading pure and defer composition to build time.
- **Never commit the `fireemblem8u` submodule pointer** — it is dirty from build artifacts by
  design. `git add` paths explicitly (`git add campaigns docs tools`), never `git add -A` alone.
