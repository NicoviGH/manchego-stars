---
id: 300
title: "The injector is a package, build_campaign.py is its CLI, and a chapter's public ids are a leaf"
date: "2026-09-30"
section: "Operational Gotchas (durable)"
issues: [389]
---

# The injector is a package, build_campaign.py is its CLI, and a chapter's public ids are a leaf

`build_campaign.py` was 15,562 lines, larger than a context window, so every injection change
was made semi-blind. It is now ~380 lines: the argument parser and `main()`, which stays the
authoritative pass list. Everything `main()` calls lives in `tools/inject/`.

## The layout

- **Shared layer**: `text` (message bodies, the script compiler), `scenes`, `cast`, `units`,
  `hosting`, `maps`, `asset_table`, `terrain`, `recruit`, `villages`, beside the older `decomp`,
  `paths`, `hosts`.
- **One module per domain pass**: `names`, `sms`, `map_sprites`, `battle_anims`, `reskins`,
  `platforms`, `arena`, `messages`, `traps`, `chapter_settings`, `scene_actors`, `warm`, ...
- **`inject/chapters/`**: one module per hosted chapter.
- **`inject/chapter_ids.py`**: every `CHNN_*`/`PROLOGUE_*` constant ANOTHER module reads. A
  constant only its own chapter reads stays in that chapter's module.

Placement was DERIVED, not chosen by banner (ADR 0287): a definition reached by exactly one pass
lives with that pass, and one reached by several went to the shared module for its domain. Each
module keeps its definitions in their original order and their comments.

## Why `chapter_ids` exists

Chapters read each other's ids in both directions (ch05 replays ch03's and ch04's texts; ch04
names ch05's pids), and the shared layer reads them too (`messages` registers every `*_MSG`,
`cast` binds boss pids to faces). No layering of whole chapter modules is acyclic under that. A
leaf of public ids is, and it is the same shape `hosts.py` already had for host slots.

## Three consequences for code that is not moving

- **A registry that scanned `globals()` now scans `inject.namespace`.** `injector_message_ids`,
  `raw_pid_claims` and `chapter_yaml_for` discover ids from constant NAMES. Split across modules,
  `globals()` is one module's view, and a smaller view finds fewer ids without failing (ADR
  0296's vacuous pass, arriving by code movement). `injector_constants(pattern)` scans every
  injector module and raises if two modules bind one name to different values.
- **A test stubs with `inject.namespace.stubbed(name, value)`.** `from inject.paths import REPO`
  gives each importer its own binding, so `mock.patch.object(inject.paths, 'REPO', tmp)` leaves
  the code under test reading the real path: a stub that stubs nothing. `stubbed` rebinds the
  name in every injector module that holds it, which is what `bc.REPO = tmp` did while there was
  one namespace. It raises if no module binds the name.
- **Callers outside the injector name the module**: `inject.cast.PORTRAIT_MAP`, not `bc.X`.
  `build_campaign` re-exports nothing, so a stale `bc.X` fails with AttributeError.

## The gate

Pure movement, so the injected tree must be byte-identical. `tools/injection_fingerprint.py`
now takes `--flags`. The default build never reaches the boot flags' code (`inject_test_chapter`,
`_configure_boot`'s five arms, ch05's debug arms, the montage), so a default-only gate would
have moved those paths unchecked. All ten configurations fingerprinted IDENTICAL before and after.
The three discovered registries were dumped before and after and compared equal. The unit suite
was split alongside (`tools/test_inject_<module>.py`, each class routed to the module it
exercises).

Recording those ten baselines is also how #417 was found: since #405, every build except the
canonical one died at a post-injection guard that audited the prologue's slot in builds that
never inject it.

`chapters/ch05.py` is ~2,100 lines, over the issue's ~1,300 target. Splitting its scene builders
out made two import cycles and pushed ch05-private constants into `chapter_ids`, which is worse
than one long module whose contents all belong to one chapter.
