---
id: 142
title: "Winter retiles preserve the vanilla artists' forest sequences as a strict generation AND import invariant."
date: "2026-07-20"
section: "Art & Audio"
issues: []
---

# Winter retiles preserve the vanilla artists' forest sequences as a strict generation AND import invariant.

When a Snowy Bern retile has a vanilla layout reference, that layout is the structural source of truth
for every `TERRAIN_FOREST` (`0x0c`) cell. Each source metatile must resolve through the approved
per-metatile mapping in `campaigns/rime-of-the-frostmaiden/maps/reskin-learned.json`; repeated vanilla
trees repeat their winter counterpart, and horizontal/vertical/cluster components keep their authored
sequence roles. The editor generator must stop with the unmapped source metatile(s) and coordinates
rather than collapse them to its generic forest fallback. Its exported JSON stamps the vanilla layout,
and `import_map_layout.py` rechecks the same mapping so a browser edit cannot silently flatten the
sequence or substitute a non-forest target. The target metatile must itself remain terrain `0x0c`.
Custom canvases with no vanilla source are exempt. A deliberate forest-composition departure is a new
map-design decision, not a quiet override of this guard. The mapping data is authoritative; tools and
tests consume it rather than carrying a second mapping table. Issue #193.
_Decided: 2026-07-20 with Nicolas (approved after Ch00–Ch02 before/after review)._
