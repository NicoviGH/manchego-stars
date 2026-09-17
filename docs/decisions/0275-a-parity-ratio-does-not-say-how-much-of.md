---
id: 275
title: "A parity ratio does not say how much of the twin it COPIED, so mirror% says it"
date: "2026-09-04"
section: "Operational Gotchas (durable)"
issues: [367]
---

# A parity ratio does not say how much of the twin it COPIED, so mirror% says it

ch06 reads **x1.00 threat / x1.00 clear-load** against vanilla Ch6 — a perfect score on the only
chapter whose clock measured wrong in both directions. Both facts are true, and they are not in
tension, because the ratio was never a measurement of ch06: **ch06 reproduces 100% of Ch6's
27-unit force, so x1.00 is a checksum on the donor pipeline.** A ratio is an aggregate over stats.
A transcribed force and a composed force that happens to land on the same per-slot pressure print
the same number, and nothing in the report distinguished them.

`mirror_share` prints, beside every ratio, the share of the **twin's** force the chapter
reproduces exactly. Measured across the campaign:

| ch00 | ch01 | **ch02** | ch03 | ch04 | ch05 | **ch06** |
|---|---|---|---|---|---|---|
| 33% | 30% | **100%** | 90% | 61% | 52% | **100%** |

**The trend is the finding, not the ch06 cell.** mirror% has climbed as the donor pipeline
improved — every gain in derivation fidelity made the gate more tautological, and nobody was
watching that happen because there was no number for it.

What a body IS, and why each choice:

- **(class, level), not class.** An L9 fighter is not the twin's L1 one; class alone would score
  a re-levelled force as a copy.
- **A multiset intersection.** Doubling a body cannot score it twice against a twin that fields
  one.
- **The denominator is the TWIN's body count**, so fielding more than the twin never reads above
  100%. The question is how much of the twin we reproduced, not how much of ours is borrowed.
- **Both sides count line AND reinforcements**, at each body's DECLARED level. This is the
  choice that found a bug, and the bug is below.
- **Nothing is dropped for carrying no modeled weapon.** The pressure metric drops a staff-only
  healer because it contributes no damage; this measures the force's SHAPE, and a healer the twin
  fields is a unit we did or did not reproduce. So the two numbers on the same line count
  different totals on purpose — ch06 prints 25 modeled enemies and 27 mirrored bodies.

**It does not gate.** A high mirror is not a defect and a low one is not either — ch03 at 90% and
ch01 at 30% are both fine chapters. It is a legibility number: it says how much a verdict is
worth, and at ≥90% the report says so in words.

**mirror% is mode-invariant, and that is not an omission.** A difficulty mode re-projects the same
level through the chapter's malus/bonus (`mode_stats`), so it moves stats and never a unit's class
or level; the Hard-only waves are folded into both sides unconditionally. The `--mode` banner says
so, because mirror sits on a row whose other figures ARE shifted.
