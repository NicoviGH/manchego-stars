---
id: 280
title: "The tileset's one home had three more callers, and they were the ones writing TILES"
date: "2026-09-16"
section: "Operational Gotchas (durable)"
issues: [374]
---

# The tileset's one home had three more callers, and they were the ones writing TILES

#371 made `build_campaign.map_tileset(meta)` the single place the rule
`meta.get('tileset', WINTER_TILESET)` lives, and said every caller used it. Three did not, and
they were the three that emit actual tile numbers into the ROM: `ch02_map_changes` and
`ch04_map_changes` resolved their metatiles from `WINTER_TILESET` outright, and `ch05_map_changes`
from a `CH05_TILESET` constant.

**A metatile number only means a terrain inside one tileset.** `map_changes_asm` emits replacement
metatile NUMBERS, so the table they are drawn from has to be the one the chapter's own map is
built on. Resolve them from a tileset named in code and the scripted changes — ch02's sacked
Targos huts, ch04's falling snag and closing village doors, ch05's desecrated reliquaries — would
be drawn out of the wrong terrain table the moment a chapter was repainted onto another tileset.

**All three were correct, for the wrong reason, and the gate could not tell.**
`check_documented_tileset` compares the chapter YAML's `map.tileset` against the sidecar, and
neither of those is what these sites read; the YAML and the sidecar would have gone on agreeing
with each other while the emitted tiles came from somewhere else entirely. Same shape as the bug
#371 closed, one layer down — and the reason to fix it is not a live defect but that nothing was
going to report one.

**A named constant is not an improvement on a literal here.** `CH05_TILESET` reads like data, but
it is a second declaration of a fact the sidecar owns; it survives only where it belongs, at
`_register_tileset` (which tileset this injector REGISTERS), and that one cannot drift in silence,
because `_register_chapter_map` exits the build when a sidecar names a tileset nobody registered.

**Review found a fourth site, and there the assumption was load-bearing for a load test.**
`inject_winter_tileset` open-codes the registration for the flat test layout: it copies
`ch-test-snowfield.json` into the decomp and points the test chapter's asset ids at
`WINTER_TILESET` named in code, without ever reading that sidecar. It agrees today only because
that sidecar is keyless, and it could never hit `_register_chapter_map`'s `TILESET_STEMS` exit
because it never looks. The point of that chapter is to load-test the winter tileset in-engine, so
a flat field built on some other tileset would render through Snow's tile config and make the test
vacuous. It now reads the sidecar and exits by name if the two disagree — the agreement is
enforced rather than assumed.

**The sidecar's PATH gets one home too.** `_layout_sidecar(maps_dir, stem)` is now where the build
says where a compiled map's sidecar is. It keys on the STEM rather than a layout tuple because
four readers need it and two of them — `_read_map_metatile` and `_map_terrain_grid`, both reading
a map's width — have only a stem to offer; keyed on the tuple it would have covered two of the
four, which is the same partial-home this ADR is about.

**Verified byte-identical.** `gMapChangesCh02`, `gMapChangesCh04` and `gMapChangesCh05` emit the
same bytes before and after (SHA-256 unchanged on all three), because ch02's sidecar is keyless
and defaults to snowy-bern, ch04's names snowy-bern and ch05's names port-or-town-winter. That
agreement is precisely why the hardcodes looked right, so proving the switch changes nothing is
the whole verification — the tests assert the ROUTE instead, because `_drawn_block` and
`_snowy_metatile_for` exit the build when a tileset cannot express a terrain with painted art, and
a sidecar pointed at another real tileset ends the process rather than returning different tiles.
