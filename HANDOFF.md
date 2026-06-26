# Handoff — Manchego Stars · live state

**THIS IS A WORKTREE** (`/Users/Yonick/Projects/ms-banim-party`, branch `feat/65-party-battle-anims`,
off `main`). The in-flight work below is **UNCOMMITTED**. Fresh instance: open THIS directory and read
this file. Project-wide state (Ch2/#22, clear-bot/#60, etc.) is unchanged on `main` — see
`git log origin/main` + GitHub issues; this handoff is scoped to the active feature.

## ACTIVE FEATURE — #65 Milestone B: party battle animations (character-unique, no class slots)

### Goal (Nicolas, this session)
Give the 8 PCs custom battle anims **without** burning a class slot per unit. Then: **both braulo +
RBG GIFs on GitHub** (commit to `docs/demo/` + push, per delivery convention), **then detailed cleanup**.

### Architecture pivot — DONE & validated
RBG M-A used a per-class clone (`clone_into`) — doesn't scale (only ~3 `CLASS_BLST_*_EMPTY` slots, 2
taken by goblin reskins #21, 1 by RBG). **Switched to FE8's per-CHARACTER path:**
- **Engine hook** `engine_hooks._patch_banim_character_unique()` (TDD'd pure transform
  `_swap_combat_anim_to_unique`): swaps the 4 combat lookups in `banim-ekrbattleintro.c`
  `GetBattleAnimationId(unit_bu…` → `GetBattleAnimationId_WithUnique(…)` (+ `u32 animid`→`int`), so
  FE8 honors `pCharacterData->_u25` → `gUnitSpecificBanimConfigs[]`. Campaign-agnostic; guarded by
  `check.py check_engine_guards_present` (added to its list); called in `build_campaign.main()`.
- **`inject_battle_anims` reworked**: builds the unit's `AnimConf` (unchanged), then `banim_unique_append`
  appends it to `gUnitSpecificBanimConfigs[]` and `banim_set_char_u25` points the character's `_u25` at
  the index. **Dropped the class clone.** `deploy_class_for` simplified (units deploy as vanilla class).
  Both pure helpers TDD'd in `test_build_campaign.CharacterUniqueBanim`.
- **Goblins stay class-bound** (generic enemies have no unique char id; `_u25` is anim-only). Goblin
  battle anim = tracked follow-up **issue #90** (attaches to their existing reskin clone classes).
- **ADR** added to `docs/decisions.md` §Art & Audio (M-A class-clone → M-B character-unique, dated
  2026-06-26). Python tests green (`test_ref_to_battleframe` 33, `test_build_campaign` 35);
  `python3 tools/check.py` → drift clean; TESTCH build GREEN.

### braulo — WORKS ✅
Anchor-swinging crab on the **Pirate-axe melee cadence** (studied from vanilla
`banim_pirm_ax1_motion.s`: lunge-in, wind-up held longest, `hit_normal` on swing-through, backward
dodge, no projectile — `ref_to_battleframe._melee_mode_body`, TDD'd). Frames at **vanilla scale (body
44, flat-13 palette, thin outline)** via `tools/descale_battleframe.py`; sits centered on the platform,
renders clean in-engine (`recordanim PT_CHAR=braulo` PASS, class 0x42 = vanilla Pirate). GIF:
`map-review/braulo-anim.gif`. **Nicolas is reviewing the cadence — get sign-off.**

### RBG — BLOCKED on a cyan render bug 🛑 (systematic-debugging in progress)
RBG renders with a **persistent cyan overlay glow** in-engine (green body shows THROUGH it → engine
overlay, not a wrong palette; the built `agbpal` decodes CORRECT). Isolated so far:
- **NOT scale** — Test A (my-descaler RBG at body 64 / 104×72) = cyan.
- **NOT motion** — Test B (RBG with `motion: melee`) = cyan.
- **Tied to my-descaler's RBG frame ASSETS**: M-A's original 88×64 RBG frames render CLEAN; braulo's
  my-descaler frames render CLEAN; only **my-descaler RBG frames** are cyan.
- Sprite SHAPE is correct & animates (frames differ). Looks like the **EKR intro materialize not
  resolving for RBG**, or a palette/transparency-index quirk specific to RBG's green/purple palette
  via the descaler. Izobai (vanilla, beside RBG) resolves to normal in the same frame.
- **NEXT debug step:** diff the *generated* assets (sheets / `_oam` / `agbpal` / `motion.s`) of
  my-descaler-RBG vs the working **M-A-RBG** baseline (revert frames + rebuild to regenerate it), and
  vs my-descaler-**braulo** (clean). Find what the descaler does to RBG but not braulo (suspects:
  `_outline`/`_crisp`/`_shared_palette` passes; a near-transparent edge index; palette ordering). Form
  Hypothesis C, test minimally (per superpowers:systematic-debugging).

### ⚠️ MESSY DEBUG STATE TO RESET before continuing
- `pcs/prof-rbg.yaml` has **TEMP `motion: melee`** (line ~52) — revert to `motion: ranged`.
- `battle_anims/prof-rbg/*.png` are currently **Test-A frames (104×72, my-descaler, CYAN)** —
  `git checkout HEAD -- campaigns/rime-of-the-frostmaiden/battle_anims/prof-rbg/` restores the
  known-good **M-A frames (clean, but over-scaled 88×64)**.
- `battle_anims/braulo/*.png` = vanilla-scale body-44 (KEEP).
- Decision locked: **scale = match vanilla** (RBG ~38, braulo 44); RBG-shrink reverses the 2026-06-23
  "keep RBG scale" ADR; **detail/palette cleanup deferred** ("size first" — Nicolas).

### Worktree build is SET UP (don't re-debug this)
Fresh submodule lacked the decomp toolchain; bridged from the main tree
(`/Users/Yonick/Projects/manchego-stars`): copied `fireemblem8u/tools/{scaninc,gbagfx,bin2c,mid2agb,
jsonproc,aif2pcm,textencode}`, copied `tools/agbcc`, copied `baserom.gba`, cleared stale `.deps`. Build:
apply the macOS shebang fix (`tools/build.sh` lines 32-36) then
`make TESTCH=1 CAMPAIGN=rime-of-the-frostmaiden -j4`. Review: `PT_CHAR=<id> tools/playtest/run.sh
recordanim` → `tools/playtest/make_gif.py recordanim <id> --name <id>-anim`. (run.sh OVERWRITES
`/tmp/playtest-recordanim/` each run — capture one unit at a time.)

### Next steps (priority)
1. **Reset the debug state** (above). 2. **Root-cause RBG cyan** (asset diff, Hypothesis C).
3. Re-descale RBG to vanilla scale (body 38) cleanly once cyan is fixed — proper source is
   `Battle Anims/RBG Battle/cleaned/*_fam.png` (hi-res clean family palette; `--noflip`), NOT the muddy
   shrink-of-a-shrink. 4. Both GIFs → `docs/demo/` + push (GitHub view). 5. braulo cadence sign-off.
   6. **Commit + `/code-review`** (sizable engine+content change). 7. Detail/palette cleanup.
   8. Roll out remaining 6 PCs (wolfram=Knight/lance, pinky=Pegasus, marty+meesmickle=Shaman,
   rootis=Mage, sclorbo=Cleric/staff; **meesmickle has a parked vendored Kitsune anim** at
   `battle_anims/_parked/`). Each = donor in `BANIM_DONORS` (+ its motion cadence if new) + 3 frames +
   ~4-line `battle_anim:` block.

## Key files (this feature)
- `tools/descale_battleframe.py` — hi-res poses → FE-scale frames. **Prime suspect for the RBG cyan.**
- `tools/ref_to_battleframe.py` — banim asset gen + `_melee_mode_body`/`_mode_order` (ranged|melee).
- `tools/build_campaign.py` — `inject_battle_anims` (~2488), `banim_unique_append`/`banim_set_char_u25`
  (~2410), `BANIM_DONORS` (~2390), `deploy_class_for` (~1040), `PATCHED_DECOMP_FILES` (+`data_banimconfunk.c`,
  `banim-ekrbattleintro.c`).
- `tools/inject/engine_hooks.py` — `_patch_banim_character_unique` + `_swap_combat_anim_to_unique`.
- `tools/test_build_campaign.py::CharacterUniqueBanim`, `tools/test_ref_to_battleframe.py` (melee tests).
- `campaigns/rime-of-the-frostmaiden/pcs/{braulo,prof-rbg}.yaml` — `battle_anim:` blocks.
- `campaigns/rime-of-the-frostmaiden/battle_anims/{braulo,prof-rbg}/` — the frames.
- `docs/decisions.md` §Art & Audio — the M-B ADR.

## Project-wide (carried forward — on `main`, NOT this worktree's concern unless asked)
Ch2 #22 (2 polish items: garbled opening text, Targos ending BG — Targos BG is uncommitted in the MAIN
tree on `feat/22-targos-bg`); Ch3 #23 next; clear-bot #60 partial; LLM-player #63 M2. See
`git log origin/main` + GitHub issues. Operating instructions: `CLAUDE.md`. Decisions: `docs/decisions.md`.
