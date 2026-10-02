---
id: 319
title: "ch00's guests fight on their twins' lines"
date: "2026-10-02"
section: "Combat System"
issues: [430]
---

# ch00's guests fight on their twins' lines

#430 step 3. The prologue injector zeroed Hlin's and Scramsax's personal bases, so each fought
at its bare class base. Scramsax, our Seth by the chapter's own difficulty note, had 22 HP /
6 Pow / 8 Def against Seth's 30 / 14 / 11, and Hlin went down in 1.8 rounds where Eirika lasts
4.7. ch00's party effect read x3.95 threat / x2.59 clear-load.

**Each guest names its `twin:` in the chapter YAML** (`CHARACTER_SETH`, `CHARACTER_EIRIKA`).
Its slot's personal layer is the twin's effective line (the twin's class base plus its personal
base, read at HEAD) minus our class base, so a Hero fights at Seth's numbers and a Fighter at
Eirika's. A layer can be negative: a Fighter has more HP than Eirika. The fields are signed.
`inject.stats.guest_personal_line` is the one source; the injector writes it and
`difficulty.fixed_roster_careers` reads it.

**Con stays our class's.** Con is the body that carries our weapon. Eirika's Con 5 works under
her Rapier; under Hlin's Hand Axe it cut her attack speed, so everything doubled her. Seth's
Con 11 equals the Hero's, so Scramsax is unaffected.

**Sephek is still zeroed.** He is the force side, and his own parity holds (ADR 0314).

**After:** ch00's party effect reads x1.98 / x1.13. The rest is Hlin's kit. Eirika's Rapier
has weapon-triangle advantage over the Prologue's axe fighters; Hlin's Hand Axe is neutral
against our axe guards and at a disadvantage against Sephek's sword. Closing that means
changing her weapon or class, which is the character's design, so it goes to Nicolas with the
no-Seth residual after step 4.
