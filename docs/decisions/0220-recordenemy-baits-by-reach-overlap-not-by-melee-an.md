---
id: 220
title: "`recordenemy` baits by REACH OVERLAP, not by melee — an archer can be benched"
date: "2026-08-20"
section: "Operational Gotchas (durable)"
issues: [25]
---

# `recordenemy` baits by REACH OVERLAP, not by melee — an archer can be benched

The bench picked "a live melee player unit" and stood it orthogonally adjacent to its target,
because it films a COUNTER-attack. A bow has no range-1 attack, so an adjacent bait produced no
animation — and that got written down as *archers cannot be benched*, with `CLASS_ARCHER` left
out of `CLASS_RESKIN_FOE_WEAPON` as if the class were the problem.

It is not. **Approach an archer with a bow or a tome and it answers at range 2** (Nicolas: "we
tested RBG and he's an archer"). The limitation was the picker's, wearing a class's name.

The bait is now chosen by finding a party unit whose weapon reach OVERLAPS the foe's, and stands
at a distance both can strike at; the candidate tiles are the Manhattan ring at that distance,
UP before DOWN before sideways. At distance 1 that ring is `{0,-1},{0,1},{-1,0},{1,0}` — byte-for-
byte the literal list it replaced.

**The order is written out, not sorted, and that is the review's finding.** A comparator on |dx|
leaves `{0,-1}` and `{0,+1}` tied and `table.sort` is not stable, so "up first" was luck — and the
first cut of this drew DOWN first, which on the bench's own y=9 row is straight off the map.
**The bounds were a literal too** (`ty <= 15`, from a bigger chapter) while the sandbox is 15x10,
and `mapUnitAt` reads `gBmMapUnit`'s zero-filled border row and answers *empty* for y=10 — so the
off-map tile would have been accepted and `cursorTo` could never reach it. Both now come from
`mapSize()`.

**The "clean tile" rule got more correct on the way.** It asked whether another foe was
orthogonally ADJACENT to the bait — a proxy for the real question, *is another foe inside the
BAIT's own attack range*, which is what makes the attack menu ambiguous and films the wrong
creature. Identical at melee; at range the old test would have let a second skeleton into the menu.

**The general shape, and it is the third instance this month:** a check written for the only case
that existed encodes that case rather than the property. See also `mapfull`'s grid (below) and the
bench's flat x-spacing assertion, both of which were right until a second row or a second chapter
existed.

_Recorded: 2026-08-20 (bone-archer filmed on the fix; Marty baits it with Flux from the far platform)._
