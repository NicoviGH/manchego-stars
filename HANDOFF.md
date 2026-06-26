# Handoff — Manchego Stars · live state

**THIS IS A WORKTREE** (`/Users/Yonick/Projects/ms-banim-party`, branch `feat/65-party-battle-anims`,
off `main`). RBG + braulo are **committed on this branch and ready for PR/`/code-review`** (not yet
merged to `main`). Fresh instance: open THIS directory and read this file. Project-wide state (Ch2/#22,
clear-bot/#60, etc.) is unchanged on `main` — see `git log origin/main` + GitHub issues; this handoff is
scoped to the active feature.

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

### braulo — DONE ✅ (lunge + matched Pirate cadence, Nicolas-signed)
Anchor-swinging crab on the **Pirate-axe melee cadence** (`ref_to_battleframe._melee_mode_body`, TDD'd).
Two fixes this session made it match the donor:
- **Lunge.** The Pirate's forward step lives in its frame OAM dx sweep (~0 → −45 → 0), but a faked anim
  pins all frames to one feet point, so braulo swung on the spot. `build_battle_anim` now bakes a
  per-beat forward OAM step (`MELEE_LUNGE_DX`, peak dx ~−40) for melee — braulo steps INTO the swing.
- **Held cadence.** `_melee_mode_body` holds the lunged peak THROUGH the hit, then eases back over a
  6-tick return (matching the Pirate's frames 2/3/5 forward + 7/8 return) — no snap-back.
Frames vanilla-scale (body 44). Verified in-engine vs a stock-Pirate capture (`docs/demo/braulo-vs-
vanilla-pirate.gif`). DEFERRED: the white **swing-arc weapon-trail** → issue **#91** (braulo has the
lunge + dirt-kick + on-contact hit-spark, but not the vanilla's drawn slash arc).

### RBG — DONE ✅ (cyan root-caused + fixed, rescaled to vanilla)
The "cyan" was an **engine bug, not the art**: `GetBanimPalette` (`banim-ekrmain.c`) forces any
`CLASS_ARCHER/_F/SNIPER/_F` unit to the canonical vanilla **bow** palette (0x25/0x27/0x29/0x2B)
*regardless of `banim_id`* — fine for the stock bow anim, but RBG deploys as a real `CLASS_ARCHER` on
the `_u25` path, so his custom appended banim's tiles got painted with the vanilla archer palette → cyan.
(M-A dodged it by deploying as a ballista clone, not `CLASS_ARCHER`.) Fix:
`engine_hooks._patch_banim_palette_custom_guard` returns `banim_id` for any **custom (appended)** banim
(id ≥ vanilla count, derived at inject), before the vanilla switch — vanilla units byte-unchanged; TDD'd,
guarded by `check_engine_guards_present`. RBG then **rescaled to vanilla** (body 38, from
`Battle Anims/RBG Battle/cleaned/*_fam.png`, `--noflip`). Green + on-platform in-engine; the engine arrow
projectile is intact. GIF `docs/demo/rbg-anim.gif`.

### Recording harness fix (folded in)
`recordanim` GIFs were showing only the foe's battle-quote, never the swing: `captureAttack` treated
entering `gProc_ekrBattle` as success, but a talky foe's in-battle quote (`ProcScr_BattleEventEngine`)
held for A and ate the capture budget. Fixed: tap A while the quote box is up, screenshot only the
quote-less anim frames, verdict keys on `sawAnim`. Now the GIFs show the real attack + damage + impact.

### Worktree build is SET UP (don't re-debug this)
Fresh submodule lacked the decomp toolchain; bridged from the main tree
(`/Users/Yonick/Projects/manchego-stars`): copied `fireemblem8u/tools/{scaninc,gbagfx,bin2c,mid2agb,
jsonproc,aif2pcm,textencode}`, copied `tools/agbcc`, copied `baserom.gba`, cleared stale `.deps`. Build:
apply the macOS shebang fix (`tools/build.sh` lines 32-36) then
`make TESTCH=1 CAMPAIGN=rime-of-the-frostmaiden -j4`. Review: `PT_CHAR=<id> tools/playtest/run.sh
recordanim` → `tools/playtest/make_gif.py recordanim <id> --name <id>-anim`. (run.sh OVERWRITES
`/tmp/playtest-recordanim/` each run — capture one unit at a time.)

### Next steps (priority)
RBG + braulo are **DONE** (cyan fixed, both rescaled to vanilla, braulo lunge+cadence). Remaining:
1. **PR + `/code-review`** this branch (sizable engine+content change), then squash-merge.
2. **Swing-arc weapon-trail** for braulo (and a reusable per-weapon version) — issue **#91**.
3. **Roll out the remaining 6 PCs** (wolfram=Knight/lance, pinky=Pegasus, marty+meesmickle=Shaman,
   rootis=Mage, sclorbo=Cleric/staff; **meesmickle has a parked vendored Kitsune anim** at
   `battle_anims/_parked/`). Each = donor in `BANIM_DONORS` (+ its motion cadence if new) + 3 frames +
   ~4-line `battle_anim:` block. Melee units inherit the `MELEE_LUNGE_DX` lunge automatically.
4. **Goblin enemy battle anim** — issue **#90** (class-bound, not `_u25`).

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
