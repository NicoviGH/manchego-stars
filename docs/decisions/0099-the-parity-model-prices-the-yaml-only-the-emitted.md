---
id: 99
title: "The parity model prices the YAML; only the EMITTED ROWS are the ROM"
date: "2026-09-04"
section: "Distribution & Scope"
issues: [26, 364]
---

# The parity model prices the YAML; only the EMITTED ROWS are the ROM

`make difficulty` reads the chapter YAML. The injector reads the same YAML and writes
`UnitDefinition` rows. When the two disagree, **parity reports on the document and the player gets
the rows** — and the gate stays green the whole way.

ch06 is the first chapter whose YAML names a dropped item in `inventory:` *as well as* in
`item_drop:`, which is a reasonable way to write it: the unit really is carrying the thing. The
injector appended the drop unconditionally, so three enemies emitted a spare copy — the halberd
Fighter shipped `{AXE_IRON, AXE_HALBERD, AXE_HALBERD}` against a vanilla donor carrying two items.
`make difficulty` read **PARITY (within band)** throughout, because nothing it looks at changed.

The same latent shape sat in `ch05_enemy_rows`, untriggered only because ch05 declares no drops at
all — which is the ordinary way this class of bug waits: correct-by-accident on the data that
exists, wrong on the first data that does not.

`_items_with_drop_last` RE-ORDERS rather than merely de-duplicating, because "last" is the part
the engine reads (FE8 drops the final item), so an inventory that listed the drop first would
otherwise drop the wrong one.

**The rule this is the second instance of** (the first is *"We wrapped on-map talk at 29
CHARACTERS"*, §HOW THE ROLLOUT MUST BE GATED): a mechanical change to how rows are BUILT is
verified by diffing the OUTPUT — the emitted decomp — never by the tests and never by a model that
consumes the same input the change did. Here that meant reading `events_udefs.c` and confirming
the three droppers carry 2/1/2 items, matching their donors at (13,6), (15,10) and (10,0).

_Decided: 2026-09-04 (Claude, hosting ch06) — found by `/code-review` on #364._
