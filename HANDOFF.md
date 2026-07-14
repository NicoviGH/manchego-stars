# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only. Settled decisions live in `docs/decisions.md`; operating rules
live in `CLAUDE.md`; issue scope and backlog live in GitHub.

## Current state

- Battle-animation review for RBG and Wolfram is complete in PR #161. Meesmickle's Shaman-based
  animation is merged in PR #163 (`1cd65bd`).
- The Tourmaline palette correction is separately merged as PR #162 (`f9ed1cc`); #161 is based on
  that work and does not reintroduce the palette change.
- Current focus: choose the next character for battle-animation review.
- Before a context rollover, warn Nicolas, refresh this file, and begin a fresh instance. Do not rely
  on automatic context compaction as the handoff mechanism.

## This session

### Battle animations

- **RBG:** regenerated the three frames from the supplied source art with
  `--body 38 --noflip --thin-outline`. This is the requested middle ground between no added outline
  and the prior heavy full-outline result.
- **Wolfram:** regenerated the three frames from the supplied alpha masters with
  `--body 44 --sharpen 1.6 --thin-outline`. Body 44 matches Braulo's deliberately large NPC-enemy
  scale; the RBG-style 4-connected ring restores the silhouette without the heavy full outline.
  The TESTCH ROM and `PT_CHAR=wolfram recordanim` both passed.
- Both use the existing per-character `_u25` battle-animation path. `PT_CHAR=prof-rbg recordanim`
  and `PT_CHAR=wolfram recordanim` passed after regeneration.
- Per-unit source paths and recipes are recorded in
  `campaigns/rime-of-the-frostmaiden/pcs/prof-rbg.yaml` and `pcs/wolfram.yaml`. The pipeline is
  `tools/descale_battleframe.py`; read the YAML comment before regenerating a frame.
- **Meesmickle:** added a per-character Shaman/Flux battle animation (`mees_sh1`) using the supplied
  idle, wind-up, and cast poses. The final frames use a shared 14-colour GBA palette, face the enemy,
  preserve the source poses' relative alignment, and use the Shaman magic cadence. The vanilla
  Shaman's visual charge is baked into its many actor frames; Meesmickle instead holds the supplied
  wind-up pose with the charge sound before Flux. Nicolas accepted that limitation for this pass.
- The reusable review-loop lessons are recorded in `docs/decisions.md`: distinguish donor actor art
  from engine effects, preview the final GBA palette before packing, preserve opaque black outside
  OBJ index 0, and defer the 1,507-entry archive rebuild until a candidate is selected.

### Demo cleanup

- Removed the 382-file local `review/` archive and pruned 20 unlinked `docs/demo` artifacts from
  #161. The temporary RBG/Wolfram review GIFs were also removed before merge; retain only
  document-linked demos in `docs/demo/`.
- `make_gif.py` now writes to `docs/demo/` for feature-branch review; other transient renderers write
  under `/tmp/manchego-stars-review`. Remove review GIFs before merge unless a live document links them.
- Deleted the stale remote `feat/23-ch03-chests` branch (closed PR #156; its work landed through #157).

### Tourmaline palette correction

- The old approach reused a live palette bank and visibly recoloured map terrain/text. It is replaced.
- The build appends a third **source** item-icon palette without altering either vanilla source bank.
  At custom-icon draw time, Tourmaline is routed from normal BG bank 4 to reserved BG bank 15.
- `ch03tourmaline` passed in mGBA on the current tree: the Tourmaline is pink, bank 5 stays vanilla,
  and the active tilemap audit allows bank 15 only for Tourmaline's 2x2 icon tiles. The fresh screenshot
  is `/tmp/playtest-ch03tourmaline/0004-ch03tourmaline-inventory.png` and was opened in Safari.
- Merged separately as PR #162 (`f9ed1cc`); the PR was intentionally split from Wolfram PR #161.
- The cast palette cannot be reused directly: it is OBJ palette bank 11, while item-menu icons are BG
  palette tiles. Rationale and constraints: `docs/decisions.md` -> "A campaign item icon can use a
  colour pal 0 lacks".

## Verification

- TESTCH ROM link -> PASS with the final Meesmickle archive.
- `PT_CHAR=meesmickle tools/playtest/run.sh recordanim` -> PASS (248 captured frames; class `0x2D`).
- `python3 tools/test_descale_battleframe.py` plus
  `python3 -m unittest tools/test_ref_to_battleframe.py tools/test_build_campaign.py` -> 134 tests passed.
- `make check` -> `drift check: clean`.
- `PT_HOST_CHAPTER=4 tools/playtest/run.sh ch03tourmaline` -> PASS.
- `git diff --check` -> clean.

## Working tree - do not lose or revert

All Meesmickle source, pipeline, and animation changes are merged in PR #163. Its remote feature
branch and temporary review GIF are pruned.

Other working-tree state:

- `fireemblem8u` is dirty from injected/generated build artifacts. Never commit its submodule pointer.
- Other untracked local/session files are intentionally not versioned; leave them alone unless
  Nicolas explicitly asks to version or remove them.

## Next steps

1. Select the next character for battle-animation review. Create its short-lived feature branch and
   keep review GIFs in `docs/demo/` only while the feature branch is under review.
2. Before any additional custom item palette, audit a free live BG bank in every target UI context.
   The GBA has exactly 16 BG palette banks (0-15); adding a source palette does not create a 17th live
   bank.

## Quick commands

```sh
# Battle-animation capture (requires a TESTCH ROM)
PT_CHAR=meesmickle tools/playtest/run.sh recordanim
tools/playtest/make_gif.py recordanim meesmickle --name meesmickle-anim --open
PT_CHAR=wolfram tools/playtest/run.sh recordanim
PT_CHAR=prof-rbg tools/playtest/run.sh recordanim

# Tourmaline visual regression (requires CH03BOOT ROM)
PT_HOST_CHAPTER=4 tools/playtest/run.sh ch03tourmaline

# Required before claiming a change is finished
python3 -m unittest tools.test_build_campaign
make check
git diff --check
```
