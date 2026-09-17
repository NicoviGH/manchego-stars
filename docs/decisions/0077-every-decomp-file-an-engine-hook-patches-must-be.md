---
id: 77
title: "Every decomp file an engine hook patches must be registered in `PATCHED_DECOMP_FILES`."
date: "2026-07-11"
section: "Combat System"
issues: []
---

# Every decomp file an engine hook patches must be registered in `PATCHED_DECOMP_FILES`.

`restore_vanilla_sources()` git-restores exactly that list to vanilla before re-injecting. A
**non-idempotent** hook (one whose guard hard-exits when the source isn't in vanilla form, e.g. the
pal-1 `DrawIcon` hook on `src/icon.c`) breaks the *second* build if its file is unregistered — the
first build patches it, the next build's guard rejects the already-patched form. The ch03 pink-icon
slice shipped `icon.c` (+ the repainted `item_icon_palette.agbpal` / `item_icon_red_gem.png`) unregistered;
it built once in-session but a fresh session's rebuild died on `DrawIcon not in expected vanilla form`.
Registered them retroactively. Idempotent `.replace()`-only patches (e.g. `titlescreen.c`) self-heal and
don't strictly need it, but register anyway for a clean restore each build.
_Decided: 2026-07-11_
