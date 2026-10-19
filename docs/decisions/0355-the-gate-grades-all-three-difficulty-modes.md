---
id: 355
title: "The parity gate grades all three difficulty modes, never the authored table"
date: "2026-10-19"
section: "Combat System"
issues: [510]
---

# The parity gate grades all three difficulty modes, never the authored table

The finished game ships all three of vanilla's difficulties, Tutorial (Easy), Normal and
Difficult (#510 step 2). The gate graded only the **authored table**, the levels each side's
YAML or UnitDefinition declares before its mode's shift. No player ever meets a chapter at
those levels, so a lock measured there could hold while every real mode failed.

- **A locked chapter holds parity only if it holds in each of the three modes.** `make
  difficulty-gate` reads every locked chapter in Tutorial, Normal and Difficult, and a failure
  names its mode (`CH4 ch04 (difficult)`). `--mode` grades one.
- **The per-unit role checks read the mode too.** The threat-inversion arm, the ceiling arm and
  the boss-durability arm all read both sides loaded for the mode being graded. A boss that holds
  on Normal can still fold on Tutorial. Only the yardstick fallback for a twin off
  `VANILLA_CHAIN` stays on declared levels, as the aggregate does there.
- **Only locked chapters are read.** With #510's chapters unlocked, the gate reads nothing and
  passes at once. It no longer prints the whole curve on every build: the verdict diff shows
  what a PR moves (ADR 0353), and `make difficulty` prints the curve on demand.
- **The verdict diff drops its `table` column** for the same reason.

The authored table stays readable (`make difficulty` with no `--mode`), as a description of
what was authored, not as a verdict.
