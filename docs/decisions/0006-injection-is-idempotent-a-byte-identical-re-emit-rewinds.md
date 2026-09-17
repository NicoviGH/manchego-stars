---
id: 6
title: "Injection is idempotent: a byte-identical re-emit rewinds the file's mtime, so `make` skips it."
date: "2026-07-30"
section: "Engine & Tech Stack"
issues: [24]
---

# Injection is idempotent: a byte-identical re-emit rewinds the file's mtime, so `make` skips it.

Because injection rewrites the decomp's own sources every build (above), and `restore_vanilla_sources`
re-`git checkout`s them, every touched file's mtime moved on every build — and `make` keys off mtime, not
content. A no-change rebuild therefore paid the full ~354-TU cascade from restored widely-included headers
plus the serial `data_banim.o` link over 1752 assets. `build_campaign` now snapshots the previous build's
injection footprint (content sha1 + `mtime_ns`) before injecting and rewinds the mtime of every file whose
bytes come out **identical**. Only mtime is written, and only on unchanged content, so the ROM cannot move.
**Measured on the ch04 branch (CH04BOOT, `-j`):** warm rebuild **188s → 28s** (6.7×); clean build 232s
without vs 236s with, and all of {clean-without, warm-without, warm-with ×2, clean-with} produced the same
ROM `sha256 dc1c56bf…`. The risk this design carries is that a wrong content-check would be invisible to
`make` (stale objects, silently), so it is also proved from the other side: changing one line of real
content (a `death_quote`) moved the ROM sha and left that file un-rewound (482 → 481), and reverting it
returned the ROM to `dc1c56bf…` exactly. Re-run those two gates if the footprint logic is ever touched.
_Decided: 2026-07-30 (#24; written 2026-07-21, merged only once the ROM gates could run on the Mac)_

**No SRD/Open5e pull.** PC data is authored from the players' D&D Beyond JSON (`data/pc-sheets/`); D&D is flavor-only over vanilla FE combat (see FE-strictness below). No SRD downloader, no `srd-snapshot.json`, no homebrew engine classes — the cast use stock FE8 classes (see Class Mapping).
_Decided: 2026-06-04_
