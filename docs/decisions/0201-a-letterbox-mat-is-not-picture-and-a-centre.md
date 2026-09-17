---
id: 201
title: "A letterbox mat is not picture, and a CENTRE crop keeps half of it"
date: "2026-08-14"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A letterbox mat is not picture, and a CENTRE crop keeps half of it

Nicolas, looking at the shipped ch05 opening: *"you see the black bar to the right in the
background?"* He was right, and it was in **both** ch05 backdrops.

The FE-Repo's `FE9-10 CG Rips` are **letterboxed**: a 240-wide picture sitting in a 256-wide
canvas, the spare 16 columns filled flat black. `bg_to_fe8.py --fit crop` centre-crops, taking
columns 8..247 — so it kept **half the mat** on the right and threw away **8 columns of real
picture** on the left. Both `bg_ElvenTomb` and `bg_ForestOutskirtsWinter` shipped that way.

**What let it through is the part worth remembering.** Each BG was vendored against the check
*"0 of 38400 pixels differ from the 5-bit source crop"* — and that check passed, correctly. It
proves the CONVERSION is faithful to the crop. It says nothing about whether the crop was the
right crop, because the crop is on both sides of the comparison. A fidelity check cannot audit
its own reference frame. (Same shape as `decisions.md` → "A scenario's verdict only covers what
it READS".) The check now compares against the source PICTURE, and a test asserts no shipped BG
has a flat edge column.

**The detector is UNIFORMITY, not darkness.** Measured on the two real rips, a mat column holds
exactly **1** distinct colour while the art beside it holds **8–12** — so the two are nowhere near
each other and no tolerance is needed. Keying on "is it black" would have missed a white or
magenta mat and risked eating genuinely dark art (the tomb's left edge is brightness ~38 and is
real stonework). `trim_uniform_border` strips edge rows/columns that are a single flat colour,
with a `min_keep` rail so a picture that is largely flat by design (a night sky, a fade to black)
is left alone rather than trimmed to nothing.

Both BGs now land **1:1 with no scaling and no crop of real art at all** — the trimmed source is
exactly 240x160. Bank counts are unchanged (2 and 3).
