---
id: 243
title: "`convertible` prices a fight the player declines — name the chapter after it and they won't"
date: "2026-08-15"
section: "Operational Gotchas (durable)"
issues: [25]
---

# `convertible` prices a fight the player declines — name the chapter after it and they won't

ch05's white moose carried `convertible: true`, which in `difficulty.py` does two things: it
exempts the unit from the role-inversion check, and it applies `CONVERT_CLEAR_DISCOUNT` (0.5) to
clear-load. The YAML's own justification was that the objective is `defeat_boss`, so "the player
can win WITHOUT ever fighting the moose" — while admitting in the next line that it "is NOT
recruitable and never changes faction".

**Nicolas: the previous chapter is named "The White Moose".** A party that has just spent an
entire map hunting this animal is going to fight it. Half-pricing its clear-load models a game
nobody plays. `convertible` is for a unit that is *neutralized* — recruited, flipped, removed
from the fight — not for one the player is merely *permitted* to walk past.

**The flag was also masking a real warning, at BOTH weapons.** With it removed the model says
`boss ravisin (threat 8.4) is out-threatened by white-moose` — and that fires at the old Revenant
claw (14.1) just as it does at the Gwyllgi's Hell Fang (24.6). The role inversion predates the
weapon fix entirely; the exemption had simply been hiding it since #171. That is the cost of an
exemption flag: it does not just adjust a number, it switches off a check, and the check it
switched off was the one with something to say.

**And it restores the structure this very file already claimed.** ch05's roster comment has read
"Structure preserved: 16 line + 6 eruption reinf + 1 convertible (Sahnar) = vanilla's line 16 ·
reinf 6 · convertible 1" the whole time, while the model actually reported **15/6/2**. Sahnar is
ch05's one true convertible (Basil's Talk, the Joshua flip). Flipping the moose to `false` makes
the measurement match the design note: 16/6/1, the twin exactly. Aggregate cost is a rounding
error — clear-load/slot 4.5 → 4.7, chapter verdict still PARITY, full `--curve --check` green.

**The general rule: a modelling flag that says "the player won't do this" has to survive the
question "why would they not?".** If the answer is only "the win condition does not require it",
that is permission, not prediction — and the fiction, the chapter title, and the map's own
geography all vote the other way.

_Decided: 2026-08-15 (Nicolas)._
