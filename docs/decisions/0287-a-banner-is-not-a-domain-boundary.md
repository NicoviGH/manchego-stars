---
id: 287
title: "A banner is not a domain boundary, and the gate for moving code is its OUTPUT"
date: "2026-09-17"
section: "Operational Gotchas (durable)"
issues: [389]
---

# A banner is not a domain boundary, and the gate for moving code is its OUTPUT

`build_campaign.py` is 15,302 lines (~249k tokens) — larger than a context window, so it can
only ever be grepped, never read. #389 decomposes it. This record is the groundwork, and the
two things that first attempt got wrong.

## The gate has to be the injector's output, not the ROM

The obvious gate for pure code movement is "the built ROM is byte-identical". It does not
work: `make` legitimately skips work it believes is done, and **the first check passed in 1.1
seconds** because the decomp's make found the ROM up to date. A gate that is satisfied by
doing nothing is not a gate.

`tools/injection_fingerprint.py` measures the thing that actually matters. It restores the
decomp to HEAD, hides the caches so the injector cannot skip, runs a full injection, and hashes
**every file the injection touched** — 975 of them. Two manifests that match mean identical ROM
input, in ~50 seconds instead of a full compile.

It earned its keep immediately: the first extraction pointed `REPO` at `tools/` (a two-`dirname`
form copied from a file one directory higher), and the fingerprint caught it on the first run.

## "Every file it touched" had to be defined, because 22 of them were invisible

The first version built its manifest from `git status`, and a manifest is only as good as what
it can see. **`git status` never lists an ignored path, and `git clean` without `-x` never
removes one** — so the 22 gitignored files the injector writes were outside the gate entirely:
the seven `chap_title_N.4bpp(.lz)` pairs and the four tilesets' `ObjectType*.4bpp` /
`MapPalette*.gbapal`. `MapPaletteSnow.gbapal` is incbin'd raw into
`data/const_data_chapter_maps.s`, so it is ROM content by any definition. A refactor that
stopped producing all 22 would have printed `IDENTICAL: 972 injected files, byte for byte`.

Extension cannot separate them from the tree's other ignored files, because `make` writes 3,431
`.lz` and 2,424 `.4bpp` of its own into the same directories. **What separates them is the
run**: an ignored file counts as injector output when its mtime says this injection wrote it.
Tracked files keep being judged by content, which is stronger. And because a file the injector
*deletes* (stale artifacts, dropped so `make` regenerates them) is output that no hash of a
written file can represent, a path that existed before the run and not after is recorded as
`DELETED`.

Measured, not argued: dropping the fog-haze derivation in `_register_tileset` — a plausible
extraction slip, changing nothing but those ignored palette bytes — is reported as
`differs graphics/map/MapPaletteSnow.gbapal`. The version that shipped in the first draft of
this PR called that same tree byte-identical.

**And the scope is derived, not listed.** Naming the injected directories by hand
(`src data include graphics texts`) read as obviously complete and was not:
`linker_script_banim.txt` sits at the decomp ROOT, two injection steps append to it, and it
fell straight out of the manifest. `paths.py` is now the one place that knows which decomp
files we write, so the gate reads its scope from there — which also means a new path constant
extends the gate without anyone remembering to. A deletion marker, finally, is only weighed
over paths BOTH runs started with: `git clean` without `-x` never restores an ignored file, so
once a stale artifact is removed the next run has nothing to delete, and a straight set
difference would fail an unchanged tree. A gate that cries wolf gets ignored, which costs more
than the blind spot it was covering.

## The banners stopped meaning anything years ago

`build_campaign.py` draws 18 section banners, and the plan was to extract along them. They are
not domain boundaries — they are **where things were appended**. `inject_ch03`, `inject_ch04`
and `inject_ch05` all live under a banner that says *Chapter 6*.

Extracting the `Enemy class reskins` banner looked ideal: 147 lines, and a coupling audit said
it reached for only two names outside itself. It passed the fingerprint gate — injection output
was byte-identical — **and broke four unit tests**, because `_wait_table_len` sat inside that
banner while `_write_wait_row`, which edits the same table, sat in the SMS region outside it.
The tests patch a path constant and call both. Splitting them put one on each side of a module
boundary.

**So extraction must follow dependency clusters, not banners.** The right unit is "every
function that touches `unit_icon_wait_table`", which the banner cuts in half.

## What also has to be checked, and is easy to miss

A domain module holds its own binding for anything it imports, so `mock.patch.object(bc, 'X')`
stops reaching code that moved. The fingerprint gate cannot see this — real injection never
monkeypatches — so **the unit tests are a second, independent gate** on any move, and a
static free-name check (`ast`, comparing loaded names against module-level definitions and
imports) beats discovering missing imports one crash at a time.

## What landed here

The groundwork only, all of it verified byte-identical over 972 injected files:

- `tools/inject/paths.py` — the **79** decomp path constants. The coupling audit found every
  region of `build_campaign.py` reaching for 6 to 53 module-level names, and almost all of them
  were these. Paths have no behaviour, so this module can be imported by anything without a
  cycle, which is what makes the remaining moves independent of each other.
- `vanilla_decomp_text` and `_table_close_line` moved into `inject/decomp.py`, whose docstring
  already promised to hold exactly this ("shared decomp source-access layer… keep it
  dependency-free so neither side creates an import cycle"). A domain module can now read
  vanilla without importing `build_campaign`, which is the cycle that would otherwise block
  every extraction.

`build_campaign.py` goes 15,302 → 15,128 lines. That is not the win; the win is that the next
extraction is now a small independent move with a 40-second gate under it.
