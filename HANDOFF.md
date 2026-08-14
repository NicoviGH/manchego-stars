# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only: where the tree is, what is in flight, what is owed, what to do
next. **Settled decisions live in `docs/decisions.md`** — if a thing is decided, it belongs there
and gets deleted from here. Operating rules live in `CLAUDE.md`/`AGENTS.md`; scope and backlog
live in GitHub issues. Before a context rollover, warn Nicolas, refresh this file, and start a
fresh instance — don't rely on auto-compaction.

Refreshed 2026-08-14 (Claude). **#255, #274, #277, #278, #279, #280 and #281 are DONE and merged —
do not reopen any of them.** The generated decomp tree is intentionally dirty as recorded below.

## In flight

**Nothing.** `main` is at #281 (ch05's scene-3 summon + scene 6), CI green.

## Next task

**ch05's dialogue wiring, worked TOP TO BOTTOM in player order** (Nicolas, 2026-08-13). The
ordered inventory of all 17 scenes — **12 done, 5 left** — is the table in **issue #25**, which is
the canonical view; do not re-derive an order from the YAML's `vanilla 0xNNN` labels, which are
anatomy citations naming the scene we MINE and are never ids we write. Reading them as an order
is what made the list confusing in the first place.

Next up is **scene 7 — Pinky asks why the moose isn't running, and it charges** (`0x9F1`, 2 boxes,
no fallback), then straight down the table. All of it is locked text from PR #196: this is wiring,
not writing.

Scene 7 sits AFTER the prep `CALL`, alongside scenes 5 and 6 — the last beat before the map, and
it ends on `meesmickle: "You had to ask?"` straight into turn 1. It needs no fade of its own:
scene 5 already brought the screen up after the prep prologue's fade to black, and 6 and 7 ride
that. It is an ON-MAP beat like the two before it, so it wraps at the bubble's **29**, and
`PutTalkBubble` anchors to a unit — Pinky is deployed by prep, so `CUMO_CHAR` him. **The moose
cannot speak** (locked 2026-07-03); its charge is pure stage direction.

**Then four rows remain**: Ravisin's battle taunt (`0x9F2`, wired NOWHERE — `gBattleTalkList` has
a ch01 Izobai row and nothing for her), Basil's death quote (`0x9F3`), and the two endings
(`0x9C9`/`0x9CA`, `0x9CB`/`0x9CC`), which are a 2×2 over Basil alive/dead × Lupin present/absent.

**The mechanisms EXIST — reuse them, do not rebuild them (#278, #280).**
`branch_on_check_alive(CH05_LUPIN_CHARACTER, if_alive, if_absent)` emits the arm-picker and shares
`_branch_on_slot_c` with `branch_on_flag` so the two cannot drift; `label_base` keeps several
branches in one event list from colliding (the arrival holds 0/1, the join 2/3 — **a third branch
must take 4/5**). `_ch05_scene_and_variant` renders a locked scene and its no-Lupin twin as two
message bodies, parameterised by channel width, so a further branched scene costs a call.
`ch05_beginning_script` assembles the whole opening in one testable place.

**A fallback line chosen as PROSE has not been BOXED (#280).** Three of the five substitutes are
too long for the bubble's 29 and page themselves mid-clause if left flowed. `variant_beat` now
accepts a `script:` entry that is a LIST of boxes so the AUTHOR places the extra A-press; the two
arms need not cost the same number of A-presses. **The Talk recruit's fallback overruns
identically and is still owed that treatment.** Long form: `decisions.md` → "A fallback line
chosen as PROSE has not been boxed".

**The id budget is already resolved — do not re-litigate it.** 17 ids against 16 owed, allocated
scene by scene in #25's table; claim each in `HOSTED_CHAPTER_MESSAGE_IDS` as it lands. `0x9E9`
`0x9EA` `0x9EB` (scenes 1–3), `0x9EC` `0x9ED` (scene 4 + fallback), `0x9EE` `0x9EF` (scene 5 +
fallback) and `0x9F0` (scene 6) are SPENT; scene 7 takes `0x9F1`. Method and the two ways to run
the sweep wrong: `docs/decisions.md` → "A host block is not the whole id budget". A fallback arm
costs ONE extra id, not four.

**A SILENT face on a backdrop scene is `present:`, and it must be preloaded.** ch05's scene 3
stages Ravisin's raised Sahnar with no dialogue at all (Nicolas, 2026-08-14 — *"you don't need to
even add lines"*), which is the cheapest possible way to stage an event: no box, no A-press, the
locked script untouched. Two engine facts came with it and both were found **by filming**, not by
reading: a face loaded MID-message opens a bubble of its own (two stacked bubbles), so silent
faces go through `_script_to_message`'s `preload` path; and podium rungs OVERLAP with the speaker
drawn on top, so a silent face needs an empty rung beside it (Right + FarRight, never MidRight +
FarRight). `assert_silent_faces_have_elbow_room` enforces the second. Long form, including two
false trails worth not re-walking (`[SendToBack]` is z-order, `[OpenX]` is not a window):
`docs/decisions.md` → "A face that never speaks must be PRELOADED".

**Both arms of the branch are proven in-engine (#279). Two of #25's four states are still owed.**

- **PROVEN — never recruited → no-Lupin arm.** The plain `--ch05-boot` ROM walks it and can walk
  nothing else, for two independent reasons: the branch runs before `LOMA` while the boot party
  seed is `LOAD1`ed after it (so `gUnitArrayBlue` is empty when `CHECK_ALIVE` asks), **and Lupin is
  not in that seed at all** — it zips the cast against 9 deploy slots and he is last. The second
  reason would have survived the obvious fix and looked like success, so do not "fix" this by
  hoisting the seed above `LOMA`; `LOMA` rebuilds the map.
- **PROVEN — on the roster and alive → Lupin's arm**, via **`--ch05-lupin`** (with `--ch05-boot`),
  which `LOAD1`s a one-unit Lupin table BEFORE the opening. Safe because `RestartBattleMap`
  (`bmio.c:1043`) never touches the unit arrays. Scenario `recordch05openinglupin` on the
  `ch05lupinboot` ROM. Nicolas watched both runs 2026-08-14 and confirmed the branch works.
- **OWED — benched, and recruited-then-killed.** `CHECK_ALIVE` ignores `US_NOT_DEPLOYED` and treats
  `US_DEAD` as absent, so both should take the arm we want — but that is a decomp reading, and a
  reading is not a run. Benched needs a roster entry that is NOT on the map, which `--ch05-lupin`'s
  `LOAD1` does not produce.

Long form: `decisions.md` → "The `--ch05-boot` ROM can only ever play the NO-Lupin arm" and "The
alive arm needed a LEVER". The branch's PLACEMENT that early is vanilla's own:
`EventScr_Ch7_BeginningScene` branches on `CHECK_ALIVE(CHARACTER_FRANZ)` and three more optional
units inside a beginning scene.

Two questions this used to leave open are now SETTLED — read them, don't re-derive them:
- **CHANNEL is inherited from the vanilla twin. WHERE THE SCENE SITS IS NOT** (corrected by #280).
  The twin says how a scene is PLAYED — backdrop or bubble, and how wide: scenes 1–4 are backdrop
  (42), scene 5 is an on-map bubble (29). It says where the scene sits only where the surrounding
  machinery is also vanilla's, **and ours diverges at exactly one place: prep.** Vanilla plays its
  street scenes before the prep `CALL` because it `LOAD1`s Eirika's group there; our party is
  placed BY prep, so **scene 5 plays AFTER `CALL(CH05_PREP_SCRIPT)` too** — all three of 5, 6 and
  7 do, and anything visible after that `CALL` brings its own `FADU(16)`. Long form + the full
  table: `docs/decisions.md` → "A cutscene's CHANNEL is inherited from the twin, not chosen" and
  "Inheriting a channel is not inheriting a POSITION". **`vanilla_scene.py` prints `0x9BB` as
  "map" and that is a reporting artifact** — it classifies by the text call, and the
  `SetBackground` above it is the real channel.
- **The no-Lupin signal: `CHECK_ALIVE(CHARACTER_LUPIN)` + `BEQ`, no flag.** Vanilla's own answer,
  and `ch14a` branches its ending on `CHECK_ALIVE(CHARACTER_JOSHUA)` — Ch5's optional Talk recruit
  and Sahnar's donor, i.e. our scene's ancestor. It reads the ROSTER, so it also handles the
  benched case that ch05's 9-of-10 deploy makes real. Long form: `docs/decisions.md` → "Did the
  player recruit them?". **Built and both arms filmed at #278/#279** — see the four-state tally
  above for the two that are still owed.

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
- **`tools/rom_bg_preview.py` is new and worth reaching for.** It decodes a vanilla BG asset
  straight out of `baserom.gba` and paints it exactly as the GBA would, so palette work costs
  milliseconds instead of a build plus an emulator run. `--index-map` / `--isolate` answer "which
  index owns this, and does anything else share it?" It knows `arena_battle` and `arena_front`;
  adding an asset is a few lines. Use it before any recolour (ch07's Bremen backdrop, title screen).
- **ch05's opening now SPEAKS, for scenes 1–5 (#277, #278, #280).** `CH05_BEGINNING_SCRIPT` opens on one
  `BACG(BG_MS_ELVEN_TOMB)` held across scenes 1–3, faded through black between them, then **CUTS to
  `BG_MS_FOREST_OUTSKIRTS_WINTER` for scene 4** (the ridge — vanilla switches BG at this same
  arrival beat), branches on `CHECK_ALIVE`, and only then `FADI` → `LOMA` → the LOAD1s → prep,
  unchanged. **A second `BACG` must be preceded by `REMOVEPORTRAITS`** or the first BG simply stays
  in VRAM — `Text()` leaves `activeTextType` at TEXTSTART and `BACG` only decompresses under
  REMOVEPORTRAITS/_1A22. That is the ch03/ch04 stale-BG bug. **Do not reach for `Text_BG` to extend
  it**: that macro ends in `EventScr_TextShowWithFadeIn`, which CLEANs and fades up onto the MAP —
  and before `LOMA` that map is still the host slot's. ch03 and ch04 hand-roll the same sequence for
  the same reason. `recordch05opening` films the whole backdrop half (49 boxes, two BGs);
  **both arms are filmed** (#279): `docs/demo/ch05-opening.gif` is the no-Lupin arm (Pinky opens)
  and `docs/demo/ch05-opening-lupin.gif` is Lupin's. Both are on the FIXED ROM, so they carry the
  letterbox trim and Sahnar's fade. They agree through scenes 1–3 and diverge from scene 4's first
  box to the end — the tail is time-shift, not four scenes of difference, so compare by EYE.
  **Scene 5 then plays AFTER the prep `CALL`** (#280) — its own `FADU(16)`, `CUMO_CHAR` to Basil,
  the second `CHECK_ALIVE` branch at labels 2/3, then the `CUSA` that joins her. Filmed separately
  by `recordch05join`/`recordch05joinlupin` (`docs/demo/ch05-join*.gif`) because the two films sit
  on opposite sides of Preparations.
- **Scenes 3 and 6 landed at #281, and SAHNAR IS NOW A TURN-1 UNIT.** Ravisin raises her on screen
  during scene 3 — a `present:` portrait, no dialogue — and scene 6 (`0x9F0`) is vanilla's `0x9C3`
  exactly: `CUMO_AT(12,6)` → `LOAD1` → **`MOVE` to (9,7)** → `CUMO_CHAR` → the seven boxes. That
  MOVE is not optional: (12,6) is the arena tile AND the tutorial's `AREA` trigger, so a unit left
  standing there locks the arena for the whole chapter (`decisions.md` → "A unit's LOAD tile is
  not its POST"). Her `walks_to` in the chapter YAML owns it. She also carries Joshua's exact AI
  including his refusal to strike the escort, which rides a GLOBAL character list rather than her
  own bytes (`decisions.md` → "AI parity can hide in a GLOBAL table"). Scene 6 costs **7**
  A-presses, not the 6 the table said — the same locked words, re-boxed for the bubble's 29.
  Films: `docs/demo/ch05-scene3-summon.gif`, `docs/demo/ch05-join-and-sahnar-alone.gif`.
- **`arrives_turn` no longer means anything for Sahnar, and three scenarios had to be taught that.**
  `ch05recruit` asserts she is RED on **(9,7)** at turn 1 and counts the eruption's four boxes
  separately; `recordch05join` runs past the join CUSA through scene 6; `recordch05recruit` no
  longer ends turn 1 at all. If a placement or trigger moves again, grep the harness for what
  waited on the old one — `decisions.md` → "A scenario written against the old design will FAIL ON
  SUCCESS".
- **Any ch05boot scenario pays for the opening in its BOOT.** It is ~52 A-presses ahead of the map,
  and `bootToMap()` drives all of it. Every ch05boot scenario now pokes fast config BEFORE the
  boot; a new one that pokes it after will burn over half the `record*` 300s budget on a scene it
  never films. **`bootToMap(true)` stops at prep — but it ALSO returns true from its
  `player_map_idle` branch**, so pair it with `controllerState() ~= "prep_main"` (ch03prep's idiom)
  or a missed classification silently mashes past the beat you meant to film.
- **Ravisin's battle taunt is wired NOWHERE.** It is a row in #25's scene table. The no-Lupin arms
  are no longer in that state: scenes 4 and 5 are BUILT and the mechanism is reusable (#278/#280);
  the rest are wiring, not invention.
- **Both caches are cold for ch05.** `.matrix-verdictcache` was invalidated by #281; `ch05arena`,
  `ch05recruit` and `recordch05join` all re-ran and PASSed on 2026-08-14, and `recordch05opening`
  with them. Nothing about ch05 needs re-running to start scene 7.
- **The ENDING SCENES ARE NOT BLOCKED by ch06 hosting** (corrected 2026-08-13, Nicolas) — this
  file and #25 both claimed they were, and both were wrong. `dev_placeholder_scene()` is the
  LANDING, standing in for the `MNC2(next)` of an unhosted next chapter; it says nothing about
  whether an ending CUTSCENE can play before it. **ch04 already ships the pattern**, written while
  ch05 was unhosted: `MUSC(SONG_VICTORY)` → `FADI` → BACG scene → `branch_on_flag` over its two
  variants → `FADI` → `dev_placeholder_scene()`. `ch05_ending_script` is that shape with the scene
  missing (`MUSC` → save-all payout → `FADI` → placeholder), and scenes 16/17 slot in where ch04's
  do. Hosting ch06 later only swaps the final landing. What the endings DO depend on is the
  `CHECK_ALIVE` branch, because they are a 2x2 — Basil alive/dead × Lupin present/absent, ids
  `0x9C9`/`0x9CA` and `0x9CB`/`0x9CC` — which is another reason to build that mechanism at scene 4.
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
