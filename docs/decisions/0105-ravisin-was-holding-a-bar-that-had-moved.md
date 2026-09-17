---
id: 105
title: "Ravisin was holding a bar that had moved"
date: "2026-08-22"
section: "Distribution & Scope"
issues: [303]
---

# Ravisin was holding a bar that had moved

ch05's boss note read *"~13 rounds to kill — Saar's bar"* since she was authored, and she hit it
exactly: 13.4. **But Saar measures 22.8.** The bar was set before #285 taught the model to apply a
personal line to BOTH sides — while vanilla's bosses were still read off naked class base, Saar
really did project near 13. When #285 landed he moved and nobody re-checked her.

The consequence was invisible until modes could be graded: ch05 sat under vanilla's clear-load in
EVERY mode (x0.88 authored, x0.86 Normal) and fell out of band on Tutorial (**x0.74**), because
that is where the generics floor to class base and the boss becomes most of the ratio.

Her line goes HP 15→21, Def 5→6. She now measures **23.4 rounds against Saar's 22.8**, and ch05 is
in band in all three modes (x0.92 / x1.02 / x1.04; authored clear-load x0.88 → x1.03).

**Def is a CLIFF on a boss, not a dial.** +1 moves her 13.4 → 20.1 rounds; +2 overshoots to 40.2,
because the yardstick's damage approaches zero and rounds-to-kill diverges. Reach for HP to carry
the rest of a durability change, and never tune a wall by Def alone.

**The general rule: a bar measured against vanilla is a MEASUREMENT, not a constant.** When the
model changes what it measures on the vanilla side, every number that was calibrated against it is
stale — and nothing fails, because our side still hits the number it was given. `RavisinHoldsSaarsBar`
now pins her as a RANGE against Saar's live value rather than against a literal, so the next such
change fails a test instead of quietly re-opening the gap.

_Decided: 2026-08-22. Found while investigating ch05's Tutorial band miss under #303's `--mode`._
