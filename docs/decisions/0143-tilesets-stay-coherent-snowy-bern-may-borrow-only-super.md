---
id: 143
title: "Tilesets stay coherent; Snowy Bern may borrow only Super Fields' complete Snag family."
date: "2026-07-20"
section: "Art & Audio"
issues: [24]
---

# Tilesets stay coherent; Snowy Bern may borrow only Super Fields' complete Snag family.

Snowy Bern remains the shared winter art direction, including Ch4's forest retile. Keep the whole N426
Snow / Fields + Customs set vendored intact as a coherent winter alternative; do not retain the complete
green-grass Super Fields default as an alternate, and do not casually mix either set's tiles into Snowy
Bern. The one approved exception is the functional Snag family Snowy Bern lacks: copy Super Fields
metatiles 8 and 35 pixel-exact into Snowy Bern's matching empty slots, preserve terrain `0x33` and the
readable brown silhouette, and use otherwise-unused Snowy Bern graphic capacity so existing art is
untouched. The approved transfer renders through Snowy Bern's native **palette bank 4**; assigning the
donor pixels to bank 5 was the washed/gold/green failure and is explicitly rejected. Match vanilla Snag
placement (Ch4 E9 uses metatile 35), just as the winter forest variants match vanilla's original sequences.
_Decided: 2026-07-20 with Nicolas (#24)._
