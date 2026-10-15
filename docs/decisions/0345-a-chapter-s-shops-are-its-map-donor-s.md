---
id: 345
title: "A chapter's in-map shops are its map donor's"
date: "2026-10-14"
section: "Economy"
issues: [493]
---

# A chapter's in-map shops are its map donor's

Nicolas, 2026-10-14: handle shops the way vanilla does, because the shop stands exactly where
vanilla puts it.

A shop is part of the map. FE8 offers the Shop command off the tile's terrain, and the Location
list line (`Armory(stock, x, y)`) only names the stock. So a chapter on a vanilla map has that
map's shops, on its tiles, with its stock. `inject.villages.chapter_shops` reads them from the
map donor's own eventinfo at HEAD (`map.vanilla_layout`). The injector, difficulty's economy
parity and the wiki all read it there. No chapter declares a shop.

Why: ch02 sits on vanilla Ch2's map and shipped without vanilla Ch2's Armory. ch05 had copied its
two shop lines into a module tuple, so nothing reached any other chapter. Difficulty compared the
twin's shops against `available_shops`, a world-map town label (the world map is #29), which made
ch02 look stocked. A chapter now names its donor once, as `map.vanilla_layout`; `base_layout`
retired.

_Decided: 2026-10-14._
