# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only. Settled decisions live in `docs/decisions.md`; operating rules
live in `CLAUDE.md`/`AGENTS.md`; issue scope and backlog live in GitHub. Before a context rollover,
warn Nicolas, refresh this file, and begin a fresh instance — don't rely on auto-compaction.

## Current state

- **Winter forest fidelity is an invariant (#193, merged `6a538bc`).** Snowy Bern retiles preserve the
  vanilla artists' forest sequences: the learned per-metatile map in `reskin-learned.json` is the sole
  authority, `gen_map_editor.py` refuses to generate on an unmapped forest variant, and
  `import_map_layout.py` re-checks every protected cell. Ch00–Ch02 backfilled. ADR: "Winter retiles
  preserve the vanilla artists' forest sequences…".
- **ch04 "The White Moose" (#24, branch `feat/24-ch04-map`, worktree `.claude/worktrees/ch04-map`) — combat host built; REDESIGNED 2026-07-21 into a full chapter.**
  `inject_ch04` hosts Ch4 on the vanilla Ch5 slot (15×15 snowy retile, fog 3, PREP 9-of-10, DefeatAll,
  `--ch04-boot`, `chain_ch03_to_ch04`). **This session redesigned the chapter around the wolf-parley
  REVEAL, adopted the "wolves turn the tide" difficulty model (raw fight above vanilla; parley discounts
  it back to dead-on vanilla — static ×1.15/×1.19, parley-path clear-load 2.5≈2.6), and REALIGNED the
  roster to mirror the vanilla-Ch4 twin 1:1** (Mogall×4·Revenant×12·melee Bonewalker×6·Entombed×1;
  the prior roster had drifted to D&D-monster-matched classes). Full design + staged checklist:
  **issue #24's 2026-07-21 comment** + `docs/decisions.md` ADR (on the branch). **Stage 1b is now DONE
  and committed (`cef0419`): `inject_ch04` wired to the realigned roster (added `CLASS_REVENANT` pid
  0xaa + melee `CLASS_BONEWALKER` pid 0xac / iron sword+lance; wave guard 16/4/3→10/6/7), village→Iron
  Axe, `difficulty_note`/`placement_directives` rewritten for the reveal, roster/spatial/dropper tests
  repinned. `make` + unit tests + `make check` + `git diff --check` all GREEN; parity holds (×1.15/×1.19,
  parley-path clear-load 2.5≈2.6).** **Stage 2a is now also DONE and committed (`8f2f784`): the reusable
  recruit-faction foundation + Lupin wired into the cast.** New `recruit_initial_faction(unit)` —
  GREEN (Colm/Trex/Basil) vs RED (Joshua/Lupin/Sahnar), opt-in via YAML `recruit.initial_faction`; Lupin
  rides the collision-free `Duessel` identity slot (STAT_DONOR = Kyle), recruited during ch04 so he's on
  the field from ch05 (ch04 deploy stays 10); death-quote id `0x974` + provisional in-voice line +
  a cast-wide death-quote coverage test. 198 tests / build / `verify_text` / `make check` all GREEN.
  Resume point = the next Stage-2 increment (see NEXT).
- **Parity/difficulty engine is three-dimensional** (`tools/difficulty.py`, all from HEAD): enemy
  pressure + item economy (#170/#172; drops #176/#178) + battlefield dynamics (convertibles + reinforcement
  timing #171/#174; area/zone #177/#178). `make difficulty CH=chNN` shows all three.
- **PC battle anims — 8 of 8 DONE** (braulo, marty, meesmickle, prof-rbg, wolfram, rootis, pinky, sclorbo).
  Sclorbo (#191) added the reusable **BISHOP dual-slot donor** (staff heal + light attack) that
  **Basil (ch05, #25) plugs into** (`battle_anim: {clone_from: bishop}` — no new donor work).
- **Enemy battle-anim import pipeline** (#90) + **per-caster charge flash** (#183) shipped; spell-palette
  tint (#168/#169) shipped. ch03 (#23) complete.
- **Recruit art shipped** (portraits + map sprites): Basil/Oddish (#179), Lupin + Sahnar (#181). Their
  build *wiring* (slot, STAT_DONOR, live `battle_anim:`) is ch04/ch05-slice work (#24/#25).

## This session (2026-07-21 cont'd, Opus — Stage 1b to green, Stage 2 design + Stage 2a)

- **Stage 1b landed** (`cef0419`) — `inject_ch04` wired to the twin-realigned roster (see Current state).
- **HANDOFF reconciled** (`25f18e1`) — the branch's `HANDOFF.md` predated the `14c5466` clean refresh and
  would have regressed live state on merge; synced it to current. **Both copies (main tree + the
  `ch04-map` worktree) are now byte-identical — keep them in sync (a branch copy silently regresses live
  state on merge).**
- **Stage 2 design brainstormed + LOCKED, recorded on issue #24** (2026-07-21 comment). Key calls:
  Lupin recruits **Joshua-style** (`CUSA` red→blue, keeps his shipped grey-glasses sprite — the visibly-
  intelligent leader among the ugly pack); the **generic pack table-swaps** (Mauthe Doog → green Lycanroc
  NPCs, a shape change `CUSA` can't do); wolves become **green NPC allies**, only Lupin becomes a **PC**;
  turn-2 reveal cutscene rides the existing turn-2 `LOAD1`. **Everything is built REUSABLE — ch05 reuses
  both flavours (Basil green→blue, Sahnar red→blue).**
- **Engine facts VERIFIED in the decomp** (not assumed): `DISA(pid)` clears the *first valid* unit, so
  repeated `DISA` on the shared generic pid clears the whole pack → **no distinct-PID work**; red→blue
  recruit = `CUSA` (vanilla Joshua/Marisa — `ch10a` Gerik→Marisa, `src/eventscr.c:3348`); the turn-2
  cutscene-beside-`LOAD1` shape is vanilla Ch4 `EventScr_089F199C`.
- **Stage 2a landed** (`8f2f784`) — the reusable recruit-faction foundation + Lupin cast wiring (see
  Current state). **Reuse-debt filed on #24:** auto-allocate death-quote msg ids from a free pool so new
  recruits need only YAML (the manual `PC_DEATH_QUOTE_MSGS` slot-vetting is a smell).

## NEXT SESSION — start here: finish the ch04 slice (`feat/24-ch04-map`)

Design is LOCKED (2026-07-21). **Read issue #24's 2026-07-21 comment for the full design + staged
checklist**, and the `docs/decisions.md` ch04 ADR (both authoritative). Work in the
`.claude/worktrees/ch04-map` worktree. The staged build, `Closes #24`:

1. ~~**Stage 1b — `inject_ch04` wiring to GREEN.**~~ **DONE (`cef0419`).**
2. **Stage 2 — parley/convert + reveal cutscene (IN PROGRESS).**
   - ~~Stage 2a — reusable recruit-faction foundation + Lupin cast wiring.~~ **DONE (`8f2f784`).**
   - **Stage 2b — RESUME HERE: place Lupin RED on the ch04 map + the Marty→Lupin parley.** Extract the
     recruit-assembly out of `inject_ch03` (currently inline ~L6294–6308: green table + `talk_recruiters` +
     `talk_recruit_char_entries` + `talk_recruit_script`'s `CUSA`) into a **shared, faction-parameterized
     function** ch03/ch04/ch05 all call (use `recruit_initial_faction`). Then ch04: emit Lupin as a RED
     enemy leader with pid `CHARACTER_DUESSEL` among the turn-2 wave (make the pack **5 generic Mauthe
     Doogs + Lupin = 6**, holding the turn-2 parity count — re-check `make difficulty CH=ch04`); wire the
     parley `CHAR(flag, script, <recruiters>, CHARACTER_DUESSEL)` into `EventListScr_Ch5_Character`; the
     script = `DISA`×5 (clear generic pack) + `LOAD1` green Lycanroc NPC table + `ENUN` + `CUSA(lupin)`.
   - **Stage 2c — turn-2 reveal cutscene** riding the existing turn-2 `LOAD1` (stub lines; real dialogue in Stage 4).
3. **Stage 3 — art:** green Lycanroc pack map sprite via the pipeline (princess-phoenix source + green
   palette, no glasses). **Render Lupin hostile/recruited + the pack for Nicolas to finalize the palette
   (red-tint vs grey) before committing art** (show-before-committing).
4. **Stage 4 — scenes** (off the ch03 template): Lonelywood opening, moose-flees, real ending (replace
   `dev_placeholder_scene()`); finalize Lupin's death line + all ch04 text via the **`dialogue-pass`** skill.
5. **Stage 5 — spatial check + `--ch04-boot` playtest** → confirm parity in-engine → open the PR (`Closes #24`).

Then: **#138** config-driven `inject_chapter(descriptor)` (approved, paused for ch04/ch05); **ch05** (#25)
grounding pass (apply the same verify-against-twin roster check); **#29** world map.

## Working tree - do not lose or revert

- `fireemblem8u` is dirty from injected/generated build artifacts. **Never commit its submodule pointer.**
  To run the map/forest tests cleanly after a build, restore the injected decomp files:
  `git -C fireemblem8u restore src/data/chapter_settings.json data/data_8B363C.s`.
- Untracked local/session files (`.agents/`, `AGENTS.md`, `skills-lock.json`) are intentionally not
  versioned; leave them alone. `tools/key_magenta.py` is **gitignored** (#178).
- `feat/24-ch04-map` (worktree `.claude/worktrees/ch04-map`) carries the ch04 slice. Session commits:
  `cef0419` (Stage 1b) → `25f18e1` (HANDOFF sync) → `8f2f784` (Stage 2a). **All committed and build-green;
  no loose uncommitted work.** Push before ending if not already pushed. `review/` in the worktree is
  untracked session output (leave it; do not commit). The old `feat/24-ch04-roster-grounding` branch is
  superseded (retire it).
- **DESIGN FOR REUSE (Nicolas, emphatic).** Every new component is built reusable — the game is long and
  re-deriving wastes time/tokens. Extend the existing refactored machinery (the recruit/faction helpers),
  don't write per-chapter one-offs. ch05 reuses green→blue (Basil) + red→blue (Sahnar). Add slots/pids as
  needed rather than shoehorn into "available" ones.

## Quick commands

```sh
# Parity/difficulty read (all from HEAD)
make difficulty CH=ch04

# ch04 fast-boot playtest build (New Game -> White Moose forest, party + foes deployed)
make CAMPAIGN=rime-of-the-frostmaiden CH04BOOT=1 fireemblem8.gba -j$(nproc)

# Required before claiming a change is finished
python3 -m unittest tools.test_build_campaign tools.test_difficulty
make check
git diff --check
```
