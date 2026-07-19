# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only. Settled decisions live in `docs/decisions.md`; operating rules
live in `CLAUDE.md`; issue scope and backlog live in GitHub. Before a context rollover, warn
Nicolas, refresh this file, and begin a fresh instance — don't rely on auto-compaction.

## Current state

- **Parity/difficulty engine is three-dimensional** (`tools/difficulty.py`, all read from HEAD):
  enemy pressure + **item economy** (#170/#172; drops #176/#178) + **battlefield dynamics**
  (convertibles + reinforcement timing; #171/#174; area/zone #177/#178). `make difficulty CH=chNN`
  shows all three, via `vanilla_decomp_text` (`git show HEAD:`) — immune to the working-tree injection.
- **ch04/ch05 design LOCKED** (#175; ADR "ch04 and ch05 each map 1:1…"). Each chapter maps 1:1 to its
  numeric FE8 twin (map + parity); theme layered on top. Both `status: planned` seeds; build at M3.
- **Spell-palette tint** shipped: dedicated `gMSSpellTint` overlay global (#168/#169). Green Flux etc.
- **ch03** (#23) complete (enemy battle-anim art was the last gap, via #90).
- **Enemy battle-anim import pipeline** (#90): reskinned enemy CLASSES animate as real FE-native
  community anims. `tools/feditor_to_banim.py` imports FEditor `.txt` + PNGs → decomp banim;
  `inject_enemy_class_battle_anims` binds per-class via `pBattleAnimDef`. ADR "Imported enemy battle anims".
- **Per-caster charge flash** (#183): each caster's sprite pulses its signature colour on the wind-up beat
  (Rootis blue · Marty green · Meesmickle purple). One YAML line per caster; reusable engine kernel in
  ADR "Per-caster charge flash".
- **PC battle anims — 8 of 8 DONE** (braulo, marty, meesmickle, prof-rbg, wolfram, rootis, pinky,
  **sclorbo**). ALL PC cast anims shipped. Faked 3-pose casters ride `inject_battle_anims` (per-character
  `_u25`); the flier (Pinky) rides the N-frame IMPORT path (below). Sclorbo (the healer, #191) added the
  reusable **BISHOP dual-slot donor** (staff heal + light attack from one anim) that **Basil (#25) reuses**.
- **Recruit art (ch04/ch05)** shipped as portraits + map sprites: **Basil** (Oddish, #179), **Lupin**
  (direwolf/Lycanroc + glasses) + **Sahnar** (spectral-skeleton) (#181). Their build *wiring* (slot,
  STAT_DONOR, injection, live `battle_anim:`) is ch04/ch05-slice work (#24/#25). Basil's battle anim is
  blocked on the SAME priest/staff donor Sclorbo needs (below). Deferred battle anims ride the #90 path.

## This session (2026-07-18, Opus — Pinky flier battle anim SHIPPED, #190)

- **#190 shipped** (squash `a51faf7`, merged; ADR in decisions.md "A PC flier rides the IMPORT pipeline").
  Pinky (the army's flier — **he/him**, RBG's homunculus son) gets a real **6-frame swoop**: launch →
  apex (ears out) → dive-bomb onto the foe (lanceless body-slam + pink impact swirl) → fly home.
- **New seam — merged the two banim pipelines:** a PC can now ride the #90 N-frame IMPORT path
  (`feditor_to_banim.build_import`) but bind **per-CHARACTER via `_u25`** (the enemy path binds
  per-class). `build_unit_battle_anim` dispatches on a `battle_anim.import: {txt, frames_dir}` block;
  both sources return the identical `{sheets,pal,motion_s}` shape so the binding is unchanged. New
  `pegasus` `BANIM_DONORS` row (`CLASS_PEGASUS_KNIGHT`, ITYPE_LANCE). This is the model for any PC whose
  motion can't be faked from 3 static poses.
- **New tool `tools/poses_to_feditor.py`:** hi-res poses → FEditor 248×160 frames. INVERSE of
  `descale_battleframe` — descale PINS the feet (kills inter-frame motion); this places each pose on a
  shared canvas so the per-frame shift BECOMES the on-screen motion. Arc lives in a `poses.yaml` manifest.
- **Reusable learnings (full list in the ADR):**
  - **Facing:** flip source to screen-left (cast convention) AND negate the dx signs (a left-facing unit
    strikes toward a foe on its left).
  - **Ear-clip:** his tail dragged the `w/2,h*5/8` anchor down → the ear-tip hit the arena's top clip line;
    shrinking him (idle ~27×31, the roster's smallest) cleared it. Future tailed/tall unit → body-based anchor.
  - **Arc = the DONOR's real on-screen path** (rise → dive → strike at melee range ~56px), NOT the concept
    layout (which overshot past the foe).
  - **Dodge timing is script-synced, not on-screen:** `wait_hp_deplete` (`C01`, `0x85000001`) is NOT a NOP —
    it PAUSES until the hit resolves. Put the hop AFTER it to fire at the miss (vanilla hops before → early);
    then HOLD the back-frame across the enemy's lance-extension (hop at full extension, land at retract).
  - **Process cost (recorded in memory + ADR):** a `recordanim` capture interleaves attack 1 · counter/dodge ·
    attack 2 (double) — I burned ~10 rebuilds analyzing the WRONG frames (2nd-attack swoop read as "the dodge").
    ALWAYS identify which beat a window is first (attacker → foe; defender → away); render UNCROPPED full-combat
    GIFs for review. And GitHub caches raw GIFs by URL — cache-bust with fresh filenames.
- Showcase GIF: `docs/demo/pinky-full-combat.gif`. 245 tests green, `check.py`/`verify_text`/`git diff --check` clean.

## Prior sessions (condensed — full detail in decisions.md ADRs + the PRs)

- **2026-07-18 (#183):** per-caster charge flash shipped (Marty green · Rootis blue · Meesmickle purple).
  Reusable kernel: arm from an EXISTING banim command, raised-cosine LUT, pulse the actor OBJ palette from a
  `PROC_REPEAT` proc. Gotchas: new hook-target file MUST be in `PATCHED_DECOMP_FILES`; no `.bss` statics in banim TUs.
- **2026-07-17 (#184):** Rootis frost-mage anim. `clone_from` = the unit's OWN class (new `mage` donor);
  element = colour-only spell tint, not a proc swap; `--reserve` threaded through the adaptive palette path.
- **2026-07-17 (#90):** enemy battle-anim import pipeline (kobolds/goblins) + landed the stranded Braulo refresh.
- **2026-07-17 (#181):** Lupin + Sahnar recruit art. **2026-07-16 (#179):** Basil/Oddish art kit.
- **2026-07-17 (#186, CLOSED):** ch04 roster grounded (23-unit force mirroring the vanilla Ch4 twin) +
  the tiered-difficulty ADR (roster ballpark → map+placement → spatial check → play → lock; spatial check =
  facts fed to an LLM analyst, not an LLM playing FE). `placement_directives` written into the ch04 map notes.
- **2026-07-16 (#178):** closed both parity-engine v1 gaps (economy drops #176 + area/zone reinforcements #177).

## NEXT SESSION — start here: ch04 / ch05 slices (all PC anims now done)

**Sclorbo shipped (#191, merged) — the last PC battle anim.** ADR in `decisions.md`
("A HEALER (staff caster) rides ONE anim…"). The reusable **BISHOP dual-slot donor** (staff heal + light
attack from one clone) is now what **Basil (ch05, #25) plugs into** — give Basil a `battle_anim:` block with
`clone_from: bishop` (+ his frames) when his ch05 slice is built; no new donor work needed. Note the healer
capture path added to `recordanim` (`captureHealerAnim`) for any future staff unit.

**Main line (ch04/ch05):** ch04 MAP (step 2) then ch05 slice (M3).
ch04 roster grounded; next = the Tiled retile of vanilla Ch4 per the `placement_directives`, then the spatial
check + build/play (tiered-difficulty flow). Two open ch04 events decisions: parley behavior (green-and-fight
vs green-and-leave) + teaching the player Marty can Talk to parley the wolves. ch05 not started (`status:
planned`, 8-enemy seed unmodeled — needs the same grounding pass ch04 got, + wire Lupin/Sahnar/Basil STAT_DONORs).

## Next steps (priority order)

1. **Build the ch04 / ch05 slices** (M3). Per-chapter vertical slice on #24/#25, through the
   tiered-difficulty flow. ch04 = the map step next; ch05 = the grounding pass (+ wire Basil's
   `battle_anim: {clone_from: bishop}` — donor now exists, #191).
2. **#138** config-driven `inject_chapter(descriptor)` (YAML `host:` block — approved, paused for ch04/ch05).
3. Then **#29** world map.

## Working tree - do not lose or revert

- `fireemblem8u` is dirty from injected/generated build artifacts. **Never commit its submodule pointer.**
- Untracked local/session files (`.agents/`, `AGENTS.md`, `skills-lock.json`) are intentionally not
  versioned; leave them alone. `tools/key_magenta.py` is **gitignored** (#178).
- **Nicolas's parallel ch04 work is live: branch `feat/24-ch04-roster-grounding` + worktree
  `.claude/worktrees/ch04-map` (locked, the ch04 MAP step). Leave both alone** — in-progress, not stale.
  (PR #186 is closed; the roster grounding merged/superseded — verify with Nicolas before touching.)
- The Pinky session's branch (`feat/pinky-battle-anim`, #190) is squash-merged and deleted. Everything is
  on `main` (pushed); CI green.

## Quick commands

```sh
# Parity/difficulty read (all from HEAD)
make difficulty CH=ch05            # or ch04, etc.

# Battle-animation capture (requires a `make TESTCH=1` ROM)
PT_CHAR=marty tools/playtest/run.sh recordanim          # PC anim; PT_CHAR=<id>
tools/playtest/make_gif.py recordanim marty --name X    # frames -> review GIF (fresh name = cache-bust)

# Required before claiming a change is finished
python3 -m unittest tools.test_build_campaign tools.test_difficulty
make check
git diff --check
```
