---
id: 240
title: "The injector was slow in Python, not in work"
date: "2026-08-13"
section: "Operational Gotchas (durable)"
issues: [274]
---

# The injector was slow in Python, not in work

`build_campaign.py` was 50s of a 64s `make` — paid on every build, whether or not a playtest
ever ran. None of it was the work it does; all of it was the shape of the loops doing it. Three
fixes took it to 18s (`make`: 64.5s → 21.0s) with the ROM **byte-identical**:

- **Per-pixel PIL is the antipattern that costs the most.** `_cell_is_empty` asked
  `getpixel` 11 million times whether a cell was transparent, re-entering PIL's pixel-access
  machinery on every read (~28s). The alpha band reshapes into `(rows, TILE, cols, TILE)` and
  answers the whole image in one `any()`. `nonzero()` walks row-major, which is what keeps
  tiles emitting in the original order — the ordering is the part a rewrite here can silently
  break.
- **Parse each YAML once, and parse it in C.** PyYAML's pure-Python scanner walks a document
  one character at a time (6M `reader.forward` calls, ~22s); libyaml's `CSafeLoader` builds the
  identical documents an order of magnitude faster. Separately, injectors re-parsed the same
  handful of chapter files 62 times because each wanted one line, so `_load_chapter_yaml`
  memoizes on path + mtime + size. **It hands back a deep copy**: several injectors edit the
  dict they are given, and a shared parse must not leak one injector's edits into the next
  one's view.
- **The remaining per-pixel loops** (`_load_frame`, the swatch strip) vectorize the same way.

**The negative result, so nobody re-attempts it: `getcolors(1 << 24)` is load-bearing.** PIL
sizes the histogram from `maxcolors`, so that bound costs a fresh multi-megabyte allocation on
every call — 42ms per frame against 0.15ms at `1 << 16`, 8.6s of the injection. It cannot be
tightened, because **getcolors returns colours in hash-bucket order and the bucket count comes
from `maxcolors`**: a smaller bound reorders the palette, which reorders every sheet index with
it and moves ROM bytes for no visual change. The trap is that it looks safe — a single
7-colour frame compares equal both ways. Baxby's 5-frame set is where `(112, 80, 128)` jumps
five slots. Buying the 8.6s back means accepting a new palette order and re-proving the anims
in-engine, which is a playtest this repo does not want to spend.

**The acceptance test for injector performance work is a byte-compare, and it is cheap.** These
changes are meant to be output-identical, so the proof is `shasum -a 256
fireemblem8u/fireemblem8.gba` matching the pre-change build — no emulator, no playtest. Cheaper
still when bisecting a difference: run `build_campaign.py` alone and hash the files it wrote
into the decomp (tracked-modified + untracked), which names the offending artifact directly
instead of leaving you with one changed ROM hash. That is what identified the palette
reordering above. Do not accept a speedup that moves a ROM byte.

_Decided: 2026-08-13 (Claude, #274)._
