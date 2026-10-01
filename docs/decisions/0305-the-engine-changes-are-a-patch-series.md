---
id: 305
title: "The engine changes are a patch series in this repo, not Python string patches (and not yet a fork)"
date: "2026-10-01"
section: "Operational Gotchas (durable)"
issues: [410]
---

# The engine changes are a patch series in this repo, not Python string patches (and not yet a fork)

Our campaign-agnostic engine changes (the player-start cursor and terrain-name guards, the
no-world-map fallbacks, lord select and the lord floor, the banim character/palette hooks, the
spell tint, the charge flash, the item-icon bank, the Arena seams, the d20 crit flourish) were
`str.replace` calls on decomp C at build time in `inject/engine_hooks.py`. Each carried an
`if orig not in text` guard, and `check_engine_guards_present` checked that each was defined
and called. They are now `engine/patches/NNNN-*.patch`, one change each, in `git format-patch`
shape: the message says why, the diff is plain C against vanilla.

- **One build step applies the series** (`inject.engine_patches.apply_engine_patches`) with one
  `git apply`, right after `restore_vanilla_sources`. It applies all of the patches or none of
  them, and a patch that no longer matches fails the build. Its declared writes (ADR 0304) are
  read off the patches.
- **An optional patch is applied by the step that supplies what it links against.** The crit
  flourish's patch names the d20 art's symbols, so `inject_crit_flourish` applies
  `engine/patches/optional/crit-d20-flourish.patch` only when the campaign ships the art. A
  campaign without the art still builds vanilla crits.
- **Tests read the patched C** through `engine_patches.patched_text(rel)`, which applies the
  series to vanilla copies in a scratch directory. Values the Python side owns and the patches
  carry as literals (the vanilla banim count, `LORDSEL_FLAG_BASE`) are pinned by
  `test_engine_patches.py`.
- **`check_engine_campaign_agnostic` scans the patches.** `check_engine_guards_present` is
  retired: the directory is the list, and a patch that stops applying fails the build.

## Why not the fork #410 proposed

ADR 0302 made the submodule the vanilla reference, and about 40 tools read it that way. Lord
select edits two DATA files (`data_battlequotes.c`, `data_event_trigger.c`). Pointing the
submodule at vanilla+engine would make every one of those readers a question to audit. A fork
also means a public repo and a rebase on every decomp bump.

The series is exactly the commit list a fork would hold: `git am engine/patches/*.patch` on a
branch of the submodule reproduces it. Choosing a fork later costs one command.

## Measured

The exported series reproduced the hooks' output byte for byte on all 26 files they touched,
and `injection_fingerprint` is identical on the twelve configurations of ADR 0304.
