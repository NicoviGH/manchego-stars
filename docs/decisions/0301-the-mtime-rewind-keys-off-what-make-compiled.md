---
id: 301
title: "The mtime rewind keys off what `make` COMPILED, not what the injector last wrote"
date: "2026-09-30"
section: "Operational Gotchas (durable)"
issues: [416]
---

# The mtime rewind keys off what `make` COMPILED, not what the injector last wrote

#416 reported that a build after injection does 1,515 `gbagfx` conversions and recompiles all
357 C files. Measured locally, a no-change rebuild was already 31s (4 conversions, 2 assembles
and a relink): ADR 0006's rewind worked. The full cascade (1,529 conversions, 357 C files,
380s) appeared only when something injected WITHOUT compiling between two builds. The
fingerprint gate (ADR 0300) does exactly that per configuration. So do a manual
`build_campaign.py` and a boot-flag switch. The rewind's baseline was "the previous
injection", so an injector-only run became it, and the next `make` found every re-emitted file
newer than its object.

## The rule

The top-level `Makefile` brackets the compile. `compiled_manifest.py forget` runs before
the decomp compile and `record` runs after it succeeds. The record (`.build-compiled/`)
holds sha1 + mtime of:

- every decomp file an injection wrote since the last record (`.build-injected.json`,
  accumulated per run from an mtime walk, so it includes the gitignored map-tileset `.4bpp`
  copies and the restored-to-vanilla files that `git status` never lists)
- every tracked file a compile regenerated, carried forward from record to record, with a copy
  of its bytes

The rewind restores a file to its compiled mtime when its bytes equal the compiled bytes, and
falls back to the previous-injection snapshot otherwise. A failed compile leaves no record.
A compile that bypassed the Makefile voids it: `load_compiled` refuses the record when any
decomp file newer than it is neither tracked, recorded, nor written by an injection since.

**What the compile wrote is put back.** textprocess writes `include/constants/msg.h` as a side
output of `src/msg_data.c`, and ours differs from HEAD (`MSG_COUNT` among it). A
`git checkout HEAD -- .` reverts it. The rewind then correctly keeps `texts.txt` older than
`msg_data.c`, so `make` never reruns textprocess, and 16 files would compile against the
vanilla header. The ROM hash did not catch that: none of the 16 reads the changed constants.
So the rewind writes the recorded copy back.

**The fingerprint gate stashes `.build-compiled`** like `.build-config.json`. Otherwise its
manifest would hash the tree's build history (the restored `msg.h`) instead of the injection.

A `git checkout` of paths skips byte-identical, stat-clean files, so #416's first lead
(the restore rewrites every listed file) was wrong. It does rewrite a stat-dirty one.

## Measured

On the Mac, default configuration:

| sequence | before | after |
|---|---|---|
| no-change rebuild | 31s, 4 conversions + relink | 29s, `make` finds the ROM up to date |
| fingerprint gate (`--ch05-boot`), then `make` | 380s, 1,529 conversions, 357 C files | 29s, up to date, our `msg.h` restored |

ROM sha1 `d1831ec0...` for every "after" build. A one-letter `death_quote` change moved it to
`2d94dd08...` (17 C files rebuilt), and reverting returned `d1831ec0...` exactly (ADR 0006's
two gates).

## CI is a different case

CI's 1,516 conversions are the same set, but there they are real work. The cache holds the
VANILLA build (ADR 0299), and all 1,160 `graphics/banim` sources are our untracked anims,
which no vanilla build has. This change leaves CI time as it was. The remaining lever is caching
the INJECTED build's outputs together with this record. It needs one more rule: a recorded file
whose bytes differ must be made newer than its record, because CI pins every tracked source to
2000-01-01. It belongs with the out-of-tree build (#408), which moves where outputs live.
