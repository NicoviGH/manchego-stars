---
id: 190
title: "The test, for any future line: does the player necessarily ENCOUNTER the thing it names?"
date: "2026-08-19"
section: "Operational Gotchas (durable)"
issues: []
---

# The test, for any future line: does the player necessarily ENCOUNTER the thing it names?

A unit the player fights either way is not an absent unit. Scene 17's box already made this
distinction and nobody noticed — *"the moose"* is deliberately unbranched there, on the reasoning
that Basil is listing who Ravisin WOKE rather than who survived. The wolf belonged in that list on
exactly the same grounds; it was one clause away in the same box.

What survives the correction is the shape of a real fallback. The three that remain — the arrival,
the join and the Talk recruit — all address Lupin **as a unit present in the scene**, which is the
thing recruitment actually governs. That is the line between the two cases: a beat that would
*speak to* or *stage* an absent unit needs an arm; a beat that merely *refers to something that
happened* does not.

Cost of the correction: the ending goes from six message ids to three, no id has to be appended
past `MSG_D4B` any more, and the owed-films list drops from six arms to three. `variant_beat` and
`branch_on_check_alive` are untouched — the endings simply stopped calling them for Lupin, and
`_ch05_ending_variants` now REFUSES a `no_lupin_fallback` on either ending so a restored block
cannot sit in the YAML looking live.

_Decided: 2026-08-19 (Nicolas)._
