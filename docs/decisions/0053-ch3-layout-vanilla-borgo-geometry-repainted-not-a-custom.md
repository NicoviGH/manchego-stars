---
id: 53
title: "Ch3 layout = vanilla Borgo geometry repainted, NOT a custom Gem-Mine blockout."
date: "2026-07-04"
section: "Combat System"
issues: [23]
---

# Ch3 layout = vanilla Borgo geometry repainted, NOT a custom Gem-Mine blockout.

The 2026-06-29 session *proposed* pivoting the ch03 layout to a custom flattened trace of the
book's Gem Mine map (Map 1.19) and posted a blockout on #23 pending Nicolas's OK. That OK never
came; on review Nicolas ruled the other way: **repaint vanilla Ch3 "Bandits of Borgo" geometry
with the `cave-interior` (Cynon Mineshaft) tiles** — don't fabricate map geometry from scratch
when a vanilla-proven Seize layout exists. This restores the ch03 YAML's own `base_layout: Ch3Map`
record (the YAML never adopted the pivot) and extends the "ALL mechanical data is vanilla" instinct
to map flow: vanilla shape, our skin. The tileset choice (Cynon Mineshaft, Gray, no re-palette) and
the thin-converter tooling from the pivot exploration all still stand — only the layout source
changes. Enemy/chest tiles stay the vanilla Ch3 coordinates (no repositioning pass needed, one less
deviation). The book's Gem Mine map remains flavor reference; the rejected blockout stays on #23
for the record.
_Decided: 2026-07-04 (Nicolas, mobile session — ruling on the #23 pending decision)._
