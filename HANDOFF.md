# Handoff - Manchego Stars live state

`HANDOFF.md` is live state only. Settled decisions live in `docs/decisions.md`; operating rules
live in `CLAUDE.md`; issue scope and backlog live in GitHub.

## Current state

- **Battle anims** (Codex session): RBG/Wolfram (#161), Meesmickle (#163), Marty + green Dark magic
  (#166), Tourmaline palette fix (#162) — all merged. Detail in "Prior session" below.
- **⭐ NEXT-INSTANCE SEQUENCE (do in this order — see "Next steps"):**
  1. **Merge PR #167** — registers the #166 spell-tint hook in the check.py guard tuple + adds its two
     patched TUs (`banim-efxmagic.c`/`banim-ekrutils.c`) to `PATCHED_DECOMP_FILES`. Two standards gaps
     Codex missed (icon.c-class latent bug). Verified: rebuild from vanilla green, 95 tests, check.py clean.
  2. **Do #168** — the deeper spell-tint refactor (Stages 1–4: drop dead migration shims → replace the
     `gEfxSpellAnimExists` overload with a dedicated `gMSSpellTint` global → honest enum → docs/tests).
     Nicolas wants it now (no tech debt). Full staged checklist + findings rationale on the issue.
  3. **Resume ch04/ch05 re-basing** — full brainstorm + decomp data captured on **#24** (ch04) and
     **#25** (ch05). Pending 3 confirms from Nicolas (A-vs-B / ch04 chests / ch05 fog — the interrupted
     AskUserQuestion). Direction: Option B (ch04←Ch11 Creeping Darkness, ch05←Ch11 Phantom Ship), parity
     ch04→FE8 Ch4 & ch05→FE8 Ch5, economy/recruit twins Ch4/Ch5.
  4. Queued: **#138** config-driven `inject_chapter(descriptor)` (incremental; YAML `host:` block —
     approved direction, paused for the ch04/ch05 design). Then next battle anim / #29 world map.
- Before a context rollover, warn Nicolas, refresh this file, and begin a fresh instance. Do not rely
  on automatic context compaction as the handoff mechanism.

## This session (2026-07-15, Opus — review, fixes, planning; no chapter code shipped)

- **Reviewed Codex's #166** (green Dark magic). Feature is good (data-driven, boundary-clean, works
  in-engine) but missed two of our registration conventions → fixed in **PR #167** (open, awaiting
  Nicolas's merge). Also digested the implementation and filed the deeper cleanup as **#168** (Nicolas
  asked for the plan; wants it done now). Key critique: the `gEfxSpellAnimExists` overload is
  verified-safe today but an unenforced landmine, and a dedicated global is reachable (vanilla's own
  `gEfxSpellAnimExists` is a working `EWRAM_OVERLAY(banim)` global).
- **ch04/ch05 re-basing brainstorm** — in flight, captured on #24/#25 (see sequence above). Confirmed
  from the decomp: vanilla Ch4 is NOT fog; the Ch11 pair (Creeping Darkness / Phantom Ship) are the
  only fog+monster chapters. `parity_reference` drives the difficulty gate independently of
  `fe8_base_map`, so "Ch11 theme, Ch4/Ch5 pressure" is supported.
- Earlier this session (already merged): ch03 title card + "Defeat Grell" objective + smoke/clear_ch03
  load-tests (**#160**) — ch03 (#23) is now down to enemy battle-anim art only.

## Prior session (Codex — battle animations)

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
- **Marty:** added a per-character Shaman battle animation (`mart_sh1`) from the supplied ready,
  charge, and cast art. Nicolas approved the 39-pixel-height candidate with the restored cap spots
  and face-pixel contrast. Marty's YAML declares a green tint for `ITYPE_DARK`, so all of his Dark
  tome visuals use the treatment while Meesmickle and every other caster remain vanilla. The final
  TESTCH capture visibly rendered the green charge/Flux effect in mGBA.
- The tint's generated lookup table is immutable campaign data. Its transient id reuses the existing
  writable spell-effect lifecycle state; the rejected standalone flag landed in ROM or a discarded
  EWRAM section. The durable rationale and `0/1/2` lifecycle contract are in `docs/decisions.md`.

### Demo cleanup

- Removed the 382-file local `review/` archive and pruned 20 unlinked `docs/demo` artifacts from
  #161. The temporary RBG/Wolfram review GIFs were also removed before merge; retain only
  document-linked demos in `docs/demo/`.
- `make_gif.py` now writes to `docs/demo/` for feature-branch review; other transient renderers write
  under `/tmp/manchego-stars-review`. Remove review GIFs before merge unless a live document links them.
- The approved Marty in-game GIF was shown on PR #166 and pruned before merge.
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
- `python3 -m unittest tools.test_build_campaign.BattleSpellPaletteTint` -> 5 tests passed.
- `PT_CHAR=marty tools/playtest/run.sh recordanim` -> PASS (248 captured frames; class `0x2D`);
  the approved capture visibly includes green charge and Flux palettes.

## Working tree - do not lose or revert

All Meesmickle source, pipeline, and animation changes are merged in PR #163. Its remote feature
branch and temporary review GIF are pruned.

Marty's source frames, data-driven spell tint, tests, and durable decision record are in PR #166;
its temporary review GIF is pruned from the merge tree.

Other working-tree state:

- `fireemblem8u` is dirty from injected/generated build artifacts. Never commit its submodule pointer.
- Other untracked local/session files are intentionally not versioned; leave them alone unless
  Nicolas explicitly asks to version or remove them.

## Next steps (ordered — the live sequence for the next instance)

1. **Merge PR #167** (spell-tint hook registration — guard + `PATCHED_DECOMP_FILES`). CI green; it's a
   pure standards fix, no feature change. Nicolas merges (self-merge classifier blocks Claude).
2. **#168 — refactor the #165 spell-palette-tint** (Nicolas: do now, don't accumulate debt). One
   feature-flow branch off main after #167. Stages 1–4 on the issue; Stage 2 (de-overload → dedicated
   `gMSSpellTint`) is the only real risk (linker placement) — gated by `PT_CHAR=marty recordanim` green
   Flux in-engine. Skip the spec doc (repo convention); record the superseding ADR in `decisions.md`.
3. **Resume the ch04/ch05 re-basing** (#24 + #25). First get Nicolas's 3 confirms (A-vs-B / ch04 chests /
   ch05 fog), then: curate FE8 Ch4 **and** Ch5 in `difficulty.py PARITY_REFERENCE_UDEFS`, re-base the two
   seed YAMLs (`fe8_base_map` → Ch11 pair; `parity_reference` → Ch4 / Ch5), tune rosters via
   `make difficulty` to the low band edge, update `decisions.md` + `CHAPTERS.md`. Still `status: planned`
   seed work (sets targets; the map/event build happens at each slice, M3).
4. Then **#138** (config-driven `inject_chapter`, incremental — approved direction) / next battle anim /
   #29 world map.
- Standing art-palette rule: before any additional custom item palette, audit a free live BG bank in
  every target UI context (16 BG banks 0–15; a source palette does not create a 17th live bank).

## Quick commands

```sh
# Battle-animation capture (requires a TESTCH ROM)
PT_CHAR=meesmickle tools/playtest/run.sh recordanim
tools/playtest/make_gif.py recordanim meesmickle --name meesmickle-anim --open
PT_CHAR=marty tools/playtest/run.sh recordanim
PT_CHAR=wolfram tools/playtest/run.sh recordanim
PT_CHAR=prof-rbg tools/playtest/run.sh recordanim

# Tourmaline visual regression (requires CH03BOOT ROM)
PT_HOST_CHAPTER=4 tools/playtest/run.sh ch03tourmaline

# Required before claiming a change is finished
python3 -m unittest tools.test_build_campaign
make check
git diff --check
```
