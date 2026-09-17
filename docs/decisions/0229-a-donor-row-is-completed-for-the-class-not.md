---
id: 229
title: "A donor row is completed for the CLASS, not for the unit that lands it"
date: "2026-08-08"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A donor row is completed for the CLASS, not for the unit that lands it

Sahnar's anim is an import, so `BANIM_DONORS['myrmidon']`'s `motion`/`cadence` go unused for her —
which made "leave the cadence `None`" tempting. `test_every_melee_donor_names_a_known_cadence`
rejected it, and the test is right: the row is keyed by CLASS, so the next Myrmidon to take the
faked 3-pose path would inherit the hole. The `sword` cadence in `ref_to_battleframe._MELEE_CADENCE`
is therefore read off FE8's own `banim_myrm_sw1` (swing_short → hit → swing_shorter → step_heavy,
with the `slash_air` lifted from its critical mode, the only place vanilla gives the blade an arc)
rather than borrowed from the axe or lance rows.
