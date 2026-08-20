# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-08-20 (Claude). **#291-#293 and #295 are DONE and merged — do not reopen any.**
The generated decomp tree is intentionally dirty as recorded below.

## In flight

**Nothing.** `main` is at #295, CI green.

## Next task

**ch05's enemy reskins — the risen tomb-guard still look like living people.** Nicolas raised
this 2026-08-19 and it is the last thing before ch05 reads as finished. Tracked on **#25**
(`enemy_class_reskins` wiring + FE-Repo imports), and the two long comments there dated
2026-08-19/20 carry the whole survey — read those before starting, they exist so nobody
re-derives it.

**Nicolas has APPROVED the asset set** (2026-08-20): map sprites `Bonewalker (U) Lance {Epicer}`,
`Axe {Snerdels}`, `One Arm {IS}`, `Wight Bow {IS}`; anims Skeleberdier (lance **+ axe +
handaxe**), Bonewalker one-arm (sword), Wight Sniper (bow). Board with every one of them playing:
`https://claude.ai/code/artifact/1528d16d-3854-43ea-9742-7280d09df17d`.

⚠️ **`docs/fe-repo-scouting.md` says "axe undead ❌ no undead axe anim" and that is WRONG** — the
Skeleberdier ships Axe (Swing), Axe (Stab) and Handaxe natively (by tatata). The ch05 YAML's
`tomb-reaver` still says `source: palette_swap` on that stale basis. Fix the doc in the same
commit as the wiring. **One import covers the lance guard AND all eight axe reavers.**

**Reuse; none of this needs new tooling** (Nicolas, explicitly). `inject_enemy_class_reskins` +
`inject_enemy_class_battle_anims` already ship the ch01 goblins, ch03 kobolds and ch04 lycanroc
pack — copy those `enemy_class_reskins` entries. Vendored anims live at
`engine/battle_anims/_vendored/<source>/<mode>/` as an FEditor `<Mode>.txt` plus `<Mode>_NNN.png`
frames, **which is exactly the shape the FE-Repo ships** (its mode folders carry the `.txt` and
the numbered PNGs beside the `.bin`), so vendoring is a download into the right directory.

Three things checked and CLEARED, so nobody re-investigates them:
- **A community sheet's green key at a non-zero palette index is already handled.**
  `map_sprite_tool.GREEN_KEYS` detects the key by COLOUR; the Epicer lance sheet carries it at
  index 6 and `recolour` mapped `6->0` correctly.
- **An RGBA community sheet needs a lossless mode-P pass** (the One Arm sheet is RGBA with 12
  opaque colours). Sahnar's and Ravisin's shipped sheets are `P` in `map_sprites/` and their
  FE-Repo originals are RGBA, so the step has precedent.
- **A size-class mismatch is the `frame:` field, in either direction.** The axe sheet is 16x48
  against `CLASS_FIGHTER`'s declared 16x32; `frame: 16x16` on the reskin entry is the whole fix
  (the Fire Imp uses the same field the other way).

Still owed on ch05's dialogue, and NOT part of the reskins: the **Talk recruit's no-Lupin
fallback** (`0x9D1`) — wiring plus its boxing at 29, the last of the three surviving fallbacks —
and the two unproven `CHECK_ALIVE` states (recruited-but-BENCHED, recruited-then-killed).

## ch05's dialogue is COMPLETE — 17 of 17 (#295)

Both endings shipped 2026-08-19 and are filmed (`docs/demo/ch05-ending.gif`). Three things
settled there that a future session will otherwise re-derive, all long-form in `decisions.md`:

- **The endings are BACKDROP scenes at 42, not on-map at 29.** The YAML, issue #25 and this file
  all said on-map for three weeks; it came from `vanilla_scene.py` classifying by the text CALL,
  so a bare `TEXTSHOW` read as on-map whatever backdrop was up. **The tool is fixed** and its
  suite pins it. The Talk recruit (`0x9CC`) really is on-map — the two sit forty lines apart in
  one vanilla file and take different channels.
- **A conditional block inside a scene is a WHOLE second copy, not a spliced beat.** Split across
  three `Text()` calls scene 16 passed every check and looked wrong: each `Text()` is its own
  `TEXTSTART..REMA`, so Basil faded out and reloaded into her own seat twice. Ids are not scarce;
  seams are expensive.
- **`CHECK_ALIVE` answers for a unit in ANY faction** (`GetUnitFromCharId` sweeps 1..0xFF), so an
  optional TALK recruit needs its recruit FLAG as well — an un-turned Sahnar is alive and RED.
- **An ENCOUNTER is not a RECRUIT.** Both endings' Lupin branches were retired: ch04's parley
  decides whether he JOINS, not whether the party met the pack.

**`--ch05-ending=<arm>`** (`full` / `no-sahnar` / `basil-died`) boots straight to the ending.
`recordch05ending` films the full arm and its **box count is the arm assertion** (20 = 19 + the
placeholder's line). The other two arms are unfilmed.

## Ravisin is COMPLETE — do not redo any of it

Portrait/name/stats (#259), turn-2 warning `0x9E4` (#261), death quote `0x9E5` (#263), battle
anim (#286/#290), **hand-edited anim palette (#291)** and **map sprite (#292)**. Films:
`docs/demo/ch05-ravisin-battle-anim.gif`, `ch05-moose-battle-anim.gif`.

Two traps a future session could walk back into, both already paid for:
- ⚠️ **Do NOT "fix" her faction colour by reinstating the author's enemy palette.** It is
  index-aligned so the swap looks free, and it turns her HAIR TEAL — already rejected on sight.
  Why her palette is hand-edited at all: `decisions.md` → "A vendored anim's palette is a BY-EYE
  call". Her look is aimed at her BUST (black robe, near-white skin), not at a faction ramp.
- ⚠️ **Her map sprite is HOODLESS on purpose** — her bust and anim both are, and `CLASS_DRUID`'s
  stock sprite is a hooded man, which is the mismatch it closes. Binding:
  `decisions.md` → "Ravisin's map sprite rides SCRIPTED_NEUTRAL_SPRITES, boss or not".

## Art tooling — reach for these before inventing anything

- **`tools/banim_palette.py`** (#291) — browser editor for an imported battle anim's own 15
  colours, playing at the `.txt`'s real cadence; `👁 isolate` says which index owns what BEFORE
  anything moves. Writes `palette.json`, applied as `build_import(recolor=...)` — agbpal only.
- **`tools/map_sprite_swapper.py`** is still the tool for MAP sprites (index swaps against the
  locked cast palette) and **Nicolas drives it**, as he did for Sahnar. Get a vendored sheet onto
  that palette first with `map_sprite_tool.recolour`, passing `--donor <Class>`.
- **Vendoring from the FE-Repo:** the index is `map-review/ch05/fe-repo/file_urls.json` (2905 map
  sprites, 2001 anims, 16457 portraits). **Search it; never walk folders, never submodule.**
  Every trap it hides — the green `#80a080` key, why a preview cannot see a mis-keyed sheet, and
  why `pattern` is not a frame count — is long-form in `decisions.md` → "A community map sprite is
  keyed on GREEN, not on index 0". The guards now fail the build, so trust them over memory.

## ch05's dialogue — the standing rules

**Worked TOP TO BOTTOM in player order** (Nicolas, 2026-08-13). The ordered inventory of all 17
scenes is the table in **issue #25**, the canonical view; do not re-derive an order from the
YAML's `vanilla 0xNNN` labels, which are anatomy citations naming the scene we MINE and are never
ids we write. All seventeen are wired (#295); what is left is the Talk recruit's no-Lupin
fallback, which is a BRANCH rather than a scene — see **Next task**.

**Basil has ONE death quote** (#289) and scene 13 is closed by that decision rather than by
wiring: the berry line is her universal `0x97A` and fires wherever she falls. The empty vanilla
`0x9C6` escort slot is not an invitation to write a second — `decisions.md` → "One death quote
per character".

**Message ids are NOT scarce, and a previous session's framing of them was wrong** (Nicolas
corrected it 2026-08-15). `gMsgTable[]` is a generated C array built from `texts.txt` by the
Makefile; `GetStringFromIndex` indexes it with no bounds check and there is no count constant, so
the table SELF-SIZES from the text source. Appending past the last vanilla id (`MSG_D4B`) extends
it — the same "append into free space, never disturb a vanilla slot" model as `CAMPAIGN_BGS` past
`BG_RANDOM` and the enemy slots at `0x80+`. We build from source; we are not patching a fixed
binary.

What the host-block discipline is actually FOR, and still is: never write an id another chapter
writes (`HOSTED_CHAPTER_MESSAGE_IDS` guards that), and never overwrite vanilla text still reachable
in the built ROM. Neither is a budget. If a beat wants another id, append one — do not redesign a
scene around a shortage that does not exist.

**Check a locked scene against facts settled AFTER its lock date before wiring it** — the
endings were locked in July and ship in August. `decisions.md` → "A LOCK has a DATE, and facts
settled after it still apply" (#293 was exactly this).

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
- **ch05's Arena is complete (#265/#268).** Both views are winterized as palette DELTAS over
  vanilla — welcome screen 16 words of 64 (overcast sky, banner-blue awnings, **sandstone left
  warm on purpose**), combat coliseum 11 words (snow floor, blue banners). Ch05 alone gets the
  armored-skeleton attendant on the Glen slot. Before/after: `docs/demo/ch05-arena-*.png`.
- **Every hosted chapter now NAMES its battle ground** (`CHAPTER_BATTLE_TILESETS`, #289) and the
  registry is required TOTAL — a new chapter must state its ground or the build stops. Two were
  wrong by omission (ch05 and ch02 kept their host slot's vanilla one; ch05's map is 53% road, so
  it fought on `michi1`, a dirt track). **And the snow arrays were OFF BY ONE since #65** —
  `GetBanimTerrainGround` ends `return ret - 1`, so those arrays hold table index + 1; every snow
  chapter drew the row BELOW the platform it named, with open ground landing on `mizuiumi1`, a
  vanilla LAKE. Both fixed; `_ground_value()` owns the convention. `TERRAIN_ROAD` has its own
  ground now (vendored `Snow Dirt Path` {Cynon}), and `recordch05platform` gates it by reading
  `gBanimFloorfx` — the engine's own answer, because reading TERRAIN passed on the wrong platform.
- **`tools/rom_bg_preview.py` is new and worth reaching for.** It decodes a vanilla BG asset
  straight out of `baserom.gba` and paints it exactly as the GBA would, so palette work costs
  milliseconds instead of a build plus an emulator run. `--index-map` / `--isolate` answer "which
  index owns this, and does anything else share it?" It knows `arena_battle` and `arena_front`;
  adding an asset is a few lines. Use it before any recolour (ch07's Bremen backdrop, title screen).
- **ch05's village-raid RACE is wired and proven in-engine (#254).** A reliquary can be lost
  (raider AI → the tile flips to ruins, no gift, its event id never sets) and saving all four
  pays out vanilla's Guiding Ring at the ending.
- **Bryn Shander's ch01 ending and Bremen's reserved ch07 backdrop are vendored winter CGs**
  (#256). Bremen is banked at **8** palettes and nothing references it yet: ch07 must show it with
  a plain `BACG` or reconvert at `--banks 6`, because the fade/transition procs apply only six.
- **Raw pid `0xb8` does not pass through the regular cast identity injector**, so everything
  Ravisin has — bust, name, stats, anim, map sprite — is bound explicitly from the ch05 YAML /
  Riev slot. See the "Ravisin is COMPLETE" section above before touching any of it.
- **Cross-agent continuity:** Nicolas uses Codex only between Claude sessions. Codex must leave an
  explicit HANDOFF entry naming what it changed, the active branch/PR and commit state,
  verification actually run, and the exact next step. Ordinary short-lived feature branches in this
  checkout, one at a time — **do not create worktrees unless Nicolas explicitly changes that.**
- **ch05's OPENING IS COMPLETE, all seven scenes, and filmed.** Backdrop half (1–4) before
  `LOMA`, then prep, then 5/6/7 on the map. Scene 7 ends on a full-screen bellow CG that ducks
  the music, shakes, cries (`SOUN(0x32C)`) and restores — see `ch05_moose_charge_block`, whose
  comments carry the four engine facts that cost a run each. Film:
  `docs/demo/ch05-moose-charges.gif`.
- **`PT_CHAR=white-moose tools/playtest/run.sh recordenemy` is the battle-anim bench**, and it
  now takes RAW-PID creatures, not just class reskins — the TESTCH sandbox deploys them under
  their own pid. That is the cheap way to look at any new anim (one 40s run, no chapter boot).
  ⚠️ **The bench ROW is full at 7** — its row geometry, not an engine limit; a second row lifts
  it. Ceiling, spacing rule and the VRAM arithmetic: `decisions.md` → "The TESTCH bench is bounded
  by SMS VRAM, not by its tile row".
- **`--ch05-moose` boots straight to scene 7 (34s vs 4m33s).** Any late beat should get a boot
  like it BEFORE its first film, not after the third — `decisions.md` → "Playtest runs are the
  most expensive thing in this repo", rule 3. `bootToMap()` is the wrong driver on such a ROM.
- **`tools/sfx_preview.py` renders any FE8 sound to WAV from the decomp — no ROM, no emulator.**
  `--grep <word> --html <file>` writes a page with play buttons and waveforms. Reach for it
  before ever building a ROM to hear a sound. **`banim_code_sound_*` is NOT the song id space**
  (`decisions.md` rule 5) — song ids come from `sound/song_table.s` and nowhere else.
- **`PT_SOUND=1` unmutes a playtest run**, and is in the verdict-cache key. Muted stays the
  default. **Nothing in the gate listens** — ch05 nearly shipped silent from turn 1 and no
  scenario, verdict or film caught it (`decisions.md` rule 6).
- **`run.sh` refuses a ROM older than the campaign sources.** It does not BUILD — only
  `matrix.py` does — and `make` can re-inject WITHOUT relinking, so "I confirmed it is in the
  ROM" has to mean the `.gba` and not the injected header (`decisions.md` rule 4).

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

**A GENERATED COMMENT IS PART OF THE SCRIPT IT DESCRIBES.** Four tests broke in one session
because an emitted `/* ... */` mentioned the command it was explaining — `TEXTCONT`, `CAMERA`,
`FADI/FADU`, `MUSI/MUNO` — and the tests grep the generated event script. Describe the command,
never name it, inside a string that gets emitted.

**A REVIEW ARTIFACT IS NOT ITS INPUTS.** The scene-3 GIF was assembled three times; two of those
jobs read the frame directory before the scene was re-filmed, one of them finished last and won
the filename, and a PRE-FIX clip showing the exact defect went onto the PR. The source frames had
been checked by eye. Verify the FILE — for a GIF, decode its own frames — and never let two jobs
write one output path. Long form: `decisions.md` → "An artifact is not its inputs".

**A LOAD tile is not a POST.** When a retile lifts a vanilla unit's coordinates, lift what the
event script does to that unit NEXT: a tile vanilla vacates immediately is usually a tile
something else needs. ch05 dropped Joshua's `MOVE` off (12,6) and lost the arena for the whole
chapter, with the YAML comment naming that tile as the arena two lines away.

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
