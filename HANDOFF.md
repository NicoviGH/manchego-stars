# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only. Settled decisions live in `docs/decisions.md`; operating rules
live in `CLAUDE.md`; issue scope and backlog live in GitHub.

## Current state

- Branch: `feat/65-wolfram-banim`; remote PR branch is `91300d8` (Wolfram-only).
- The Tourmaline palette correction merged separately as PR #162 (`f9ed1cc`). The local checkout still
  has the pre-split palette commit `a16c193` above the Wolfram commit; rebase it onto `origin/main`
  before the next push to #161. The current animation visual pass remains uncommitted.
- Current focus: battle-animation visual review for RBG and Wolfram.
- Before a context rollover, warn Nicolas, refresh this file, and begin a fresh instance. Do not rely
  on automatic context compaction as the handoff mechanism.

## This session

### Battle animations

- **RBG:** regenerated the three frames from the supplied source art with
  `--body 38 --noflip --thin-outline`. This is the requested middle ground between no added outline
  and the prior heavy full-outline result. GitHub review GIF:
  `docs/demo/rbg-anim.gif`.
- **Wolfram:** regenerated the three frames from the supplied alpha masters with
  `--body 44 --sharpen 1.6 --thin-outline`. Body 44 matches Braulo's deliberately large NPC-enemy
  scale; the RBG-style 4-connected ring restores the silhouette without the heavy full outline.
  The TESTCH ROM and `PT_CHAR=wolfram recordanim` both passed. GitHub review GIF:
  `docs/demo/wolfram-anim.gif`.
- Both use the existing per-character `_u25` battle-animation path. `PT_CHAR=prof-rbg recordanim`
  and `PT_CHAR=wolfram recordanim` passed after regeneration.
- Per-unit source paths and recipes are recorded in
  `campaigns/rime-of-the-frostmaiden/pcs/prof-rbg.yaml` and `pcs/wolfram.yaml`. The pipeline is
  `tools/descale_battleframe.py`; read the YAML comment before regenerating a frame.

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

- `make TESTCH=1 CAMPAIGN=rime-of-the-frostmaiden fireemblem8.gba` -> PASS (latest Wolfram frames).
- `PT_CHAR=wolfram tools/playtest/run.sh recordanim` -> PASS (141 captured frames; class `0x9`).
- `python3 -m unittest tools.test_build_campaign` -> 88 tests passed.
- `make check` -> `drift check: clean`.
- `PT_HOST_CHAPTER=4 tools/playtest/run.sh ch03tourmaline` -> PASS.
- `git diff --check` -> clean.

## Working tree - do not lose or revert

Modified current-session work:

- `campaigns/rime-of-the-frostmaiden/battle_anims/{prof-rbg,wolfram}/*.png`
- `campaigns/rime-of-the-frostmaiden/{campaign.yaml,pcs/prof-rbg.yaml,pcs/wolfram.yaml}`
- `tools/build_campaign.py`, `tools/check.py`, `tools/inject/engine_hooks.py`,
  `tools/playtest/harness.lua`, `tools/test_build_campaign.py`
- `docs/decisions.md` and this handoff.

Other working-tree state:

- `fireemblem8u` is dirty from injected/generated build artifacts. Never commit its submodule pointer.
- `tools/key_magenta.py` is untracked user/scratch tooling; leave it alone unless explicitly asked.
- `.agents/` and `skills-lock.json` are the local project handoff/superpowers skill setup created this
  session; leave them uncommitted unless Nicolas asks to version them.

## Next steps

1. Review `docs/demo/wolfram-anim.gif` against `docs/demo/rbg-anim.gif` in PR #161;
   prune both before merge unless a live document deliberately links them.
2. If art is accepted, decide whether these current changes belong in one #65 commit/PR; do not include
   unrelated palette work unless its scope is explicitly included.
3. Before pushing #161 again, rebase the local branch onto `origin/main` so its already-merged palette
   commit is not reintroduced.
4. Before any additional custom item palette, audit a free live BG bank in every target UI context.
   The GBA has exactly 16 BG palette banks (0-15); adding a source palette does not create a 17th live
   bank.

## Quick commands

```sh
# Battle-animation capture (requires a TESTCH ROM)
PT_CHAR=wolfram tools/playtest/run.sh recordanim
tools/playtest/make_gif.py recordanim wolfram --name wolfram-anim-thin-outline-review --open
PT_CHAR=prof-rbg tools/playtest/run.sh recordanim

# Tourmaline visual regression (requires CH03BOOT ROM)
PT_HOST_CHAPTER=4 tools/playtest/run.sh ch03tourmaline

# Required before claiming a change is finished
python3 -m unittest tools.test_build_campaign
make check
git diff --check
```
