---
id: 278
title: "A map's tileset has one home, and it is the one the BUILD reads"
date: "2026-09-06"
section: "Operational Gotchas (durable)"
issues: [26]
---

# A map's tileset has one home, and it is the one the BUILD reads

`map_placement_preview.load_map(stem)` read the tileset with a bare `meta['tileset']` off the
map's sidecar `<stem>.json`. ch00–ch02's sidecars predate that key, so the tool this repo calls
"the picture a placement decision gets made on" hard-crashed with `KeyError: 'tileset'` on half
the built maps. No *gate* lost coverage (`check_rescue_targets` and `check_rescue_fuse_forecast`
both skip on an unreadable map, and none of ch00–ch02 declare `rescue_boats`), but a third of the
campaign could not be previewed at all.

**The first fix was right about the shape and wrong about the direction, and the difference is
the whole ADR.** Every chapter YAML also declares `map.tileset`, and it reads like the authored
source — so the first attempt promoted it to the single source of truth, threaded
`chapter['map']['tileset']` through `terrain_grid` and `render`, and raised when the two
disagreed. Review caught the premise: **nothing in the build reads that field.**
`_register_chapter_map` resolves the tileset from the SIDECAR, defaulting to `WINTER_TILESET`
when the key is absent — which is precisely why ch00–ch02 compile correctly today and always
have. A preview sourced from the YAML would be drawing a fact the cartridge never consults, and
for exactly the keyless chapters the mismatch guard could not fire, so editing ch00's YAML would
have produced a confident render of a tileset the game does not load. The fix would have
introduced a subtler version of the bug it was closing.

**The rule the build already uses is the rule, and it now exists once.** It was written twice
inside `build_campaign` itself (`_register_chapter_map` and the layout terrain reader), and the
preview would have been a third copy; it is now `build_campaign.map_tileset(meta)`, and all three
call it. `load_map(stem)` takes no tileset argument at all — the picture cannot disagree with the
cartridge, by construction rather than by vigilance.

**The YAML field stays, and stays honest by being CHECKED.** It is documentation, and
documentation nothing reads is documentation free to rot — which is how this started.
`check_documented_tileset` fails the build when a chapter's `map.tileset` names anything other
than what `map_tileset` resolves for its compiled map. All nine chapters agree today; the point
is that they cannot quietly stop agreeing.

**A gate that cannot read its map now REPORTS rather than skipping or crashing.**
`check_rescue_targets` swallowed every exception from `terrain_grid` as a skip, which hides a
hard gate not running. The two obvious repairs were both wrong: letting it propagate crashed every
other check with it (`main` ran them in a bare loop, until #372 below), and swallowing is what it
already did.
A missing map — a chapter with no compiled `.mar` yet — stays a legitimate skip; anything else
appends to `fail`, attributed and without a traceback.

**Verified byte-identical, twice, across two different designs.** ch03–ch06 `terrain_grid` SHAs
and full PNG renders are identical before and after — and identical again between the rejected
YAML-sourced version and the shipped build-sourced one, because every chapter's documented
tileset happens to match its effective one today. That agreement is exactly why the wrong premise
produced right answers and could have shipped unnoticed; it is now a gate rather than a
coincidence. ch00–ch02 render for the first time; ch07/ch08 still have no compiled `.mar`, and
now say so precisely — `terrain_grid` raises `MapNotCompiled` for them, while the CLI render
path still surfaces the underlying `FileNotFoundError`.
