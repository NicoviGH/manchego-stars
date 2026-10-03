---
id: 324
title: "The role check reads both forces against our party"
date: "2026-10-03"
section: "Combat System"
issues: [430]
---

# The role check reads both forces against our party

#430 step 6. The per-unit role check (#284) still scored every unit against the fixed
`YARDSTICK` swordsman after ADR 0316 moved the aggregate off it. That read the triangle from a
sword's side only. Once ch00's guards carried lances (ADR 0322), they "out-threatened" Sephek
at 4.0. Against the party that actually meets them, Sephek hits for 8.0 and each guard for 2.5.

**On a twin the party model reaches, every arm reads our force and the twin's, both met by our
arriving party** (`chapter_matchup`'s `cross` read, `_role_findings_vs_party`). Measuring the twin
against vanilla's own party would charge it for that party. The same Shaman with the same Flux
hits ours for 31.3 and vanilla's, with Lute and Artur, for 19.6. That gap made nerra look like a
1.5x outlier.

- **Outlier:** a unit's threat over the twin's heaviest unit x1.25.
- **Inversion:** a line unit out-hitting our boss is flagged only when that ratio runs past the
  twin's own line-to-boss ratio x1.25. FE8 inverts too: vanilla Ch2's archer out-hits Bone, and
  Ch6's Horseslayer out-hits Novala. The twin's boss is the body whose CHARACTER carries
  `CA_BOSS`, where FE8 records it. Convertibles are left out on both sides.
- **Durability:** our boss's party-rounds to clear it under half the twin boss's.
- The `YARDSTICK` arms stay for a twin off `VANILLA_CHAIN` and for any call without a campaign.

**Reading on ch00-ch06:** every chapter matches its twin's per-unit profile except ch03, where the
grell hit the party for 9.7 to the kobold slinger's 13.6 (1.40x, against the twin's 0.97x).
Its level had been tuned to the yardstick, where magic reads high against a low Res. **The grell
takes `basePow: 5`**, close to the Pow+6 of Maelduin, the defensive monster boss its line already
follows. It now hits for 14.1, Bazba's 14.0. Its HP, Def, clear-load and exp yield are unchanged;
ch03 reads x0.90 / x1.14.

**Locks:** ch00 and ch03 lock with this record, beside ch04 and ch06 (#452). The four hold parity
on every arm of the gate.
