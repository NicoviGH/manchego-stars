# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-08-13 (Claude). **#255 and #274 are both DONE and merged — do not reopen
either.** The generated decomp tree is intentionally dirty as recorded below.

## In flight

**Nothing.** `main` is at #276 (ch05's Talk recruit, reviewed and merged), CI green.

## Next task

**ch05's dialogue wiring, worked TOP TO BOTTOM in player order** (Nicolas, 2026-08-13). The
ordered inventory of all 17 scenes — 6 done, 11 left — is the table in **issue #25**, which is
the canonical view; do not re-derive an order from the YAML's `vanilla 0xNNN` labels, which are
anatomy citations naming the scene we MINE and are never ids we write. Reading them as an order
is what made the list confusing in the first place.

Next up is **scene 1, Basil and Sahnar talking through the stone** (16 boxes), then straight
down the table. All of it is locked text from PR #196: this is wiring, not writing.

**The id budget is already resolved — do not re-litigate it.** 17 ids against 16 owed, allocated
scene by scene in #25's table; claim each in `HOSTED_CHAPTER_MESSAGE_IDS` as it lands. Method and
the two ways to run the sweep wrong: `docs/decisions.md` → "A host block is not the whole id
budget". A fallback arm costs ONE extra id (`variant_beat` + `branch_on_flag`, ch04's mechanism),
not four.

Two things the wiring still has to decide per scene, and one open question:
- **Channel** — on-map bubble (wraps 29, needs a staged unit to anchor to) vs `Text_BG` (~42).
  Scenes 1–4 and 6 happen before the party is on the field, so nothing is staged for a bubble.
- **Where PREP sits** — `CH05_BEGINNING_SCRIPT` runs LOMA → line LOAD1s → `CALL` prep → the join
  CUSA, silently. Scene 5 IS the join and scene 7 is the last beat before the map, so the seven
  openers have to be placed around that `CALL`.
- **OPEN:** the no-Lupin arms need a signal that ch04's parley happened. `CH04_LUPIN_TALK_FLAG`
  is `EVFLAG_TMP(9)` and survival across the chapter boundary is unverified; testing whether
  Lupin is on the ch05 field is probably the better signal. Settle before wiring any of the five.

## Current state

- **Environment: Nicolas is on his Mac. ROM builds, `verify_text` and mGBA playtests are LIVE.**
- **Checkout path: `/Users/Yonick/Projects/manchego-stars`** — the ONE tree (#267, closed
  2026-08-12). The old `Documents/Codex/...` copy and a stale 12-commits-behind copy are gone;
  both were audited for unpushed commits, unique branches and stashes first. The tree is clean
  except for the intentionally dirty `fireemblem8u` submodule plus Nicolas's untracked `.agents/`
  and `AGENTS.md` — preserve those and stage paths explicitly.
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
- **ch05's opening plays NO dialogue at all** — not vanilla prose, silence. `CH05_BEGINNING_SCRIPT`
  is ours already (LOMA → the line LOAD1s → `CALL` prep → the join CUSA) and simply has no
  `TEXTSHOW` in it. The RECRUIT was the one playing vanilla prose, and #276 fixed it. Both halves
  used to be described here as one thing; they were never the same problem.
- **Ravisin's battle taunt is wired NOWHERE**, and neither is any no-Lupin arm. Both are rows in
  #25's scene table now. The chapter's ENDING is additionally blocked behind ch06 hosting — ch05's
  win still lands on the dev placeholder.
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
