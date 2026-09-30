---
id: 299
title: "CI caches the VANILLA decomp build, and the mock base ROM is seeded"
date: "2026-09-30"
section: "Operational Gotchas (durable)"
issues: [416]
---

# CI caches the VANILLA decomp build, and the mock base ROM is seeded

The `build` job is the PR's critical path (~3 min; `tests` ~1 min, `checks` ~25s run beside
it). Of its `make green`, 25s was injection and ~122s was compiling the decomp from scratch --
and that compile was mostly the vanilla decomp's OWN assets: 6,006 `gbagfx` conversions,
2,199 compressions, the music. Those are a function of the submodule commit and the
toolchain, and of nothing we author.

## The rule

The vanilla build's outputs (every file `make` adds to the untracked set) are cached on what
they were BUILT WITH: the submodule commit, the runner image, the ARM binutils version, a hash
of the agbcc binaries actually installed, and the mock version. Not on hand-bumped labels: the
first cut keyed on `agbcc-v1`, and the agbcc cache rebuilds from pret/agbcc's tip on a miss,
so a new compiler or runner image would have reused old objects (review of #415). On a hit they are unpacked, tracked sources are pinned to an old mtime so `make` reads
the outputs as up to date, and injection then makes only its own dependants rebuild. Safe
because the decomp's rules depend on SOURCES only (never on tool binaries, which are rebuilt
every run) and C header dependencies ride in the cached `.d` files.

**The mock base ROM is seeded** (`random.Random(8)`), not `/dev/urandom`. Vanilla `.s` files
incbin from it, so a random mock made every build unique: nothing cached from it could be
reused, and no two ROMs could be compared.

## Measured, not argued

Clean build (`workflow_dispatch`, `no_cache`), cache miss and cache hit all printed ROM sha1
`c62dd296...` -- byte-identical. The job went ~188s -> ~148s on a hit.

## What it exposed

The cache removed less than the vanilla asset count suggested: the build after injection still
does 1,515 conversions, re-links all 2,199 battle-anim sheets and recompiles every C file, on a
miss and a hit alike. On CI that is real work. It is our own injected content, which no vanilla
build holds (ADR 0301 measured it, #416). Caching the injected build's outputs is the next lever.
