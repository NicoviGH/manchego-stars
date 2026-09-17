---
id: 194
title: "A glued em-dash still has to FIT"
date: "2026-08-13"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A glued em-dash still has to FIT

`_wrap_fe_lines` keeps a bare `--` from opening a line by gluing it to the word before it. It did
that **without re-measuring**, so any line that ended within two characters of the width came out
over it. ch05 scene 4's Wolfram line sits exactly on that boundary — *"Struck off edges. There was
fighting here --"* is 44 against the scenic 42 — and it is what found the bug, but the glue lives in
the shared wrapper, so every chapter was exposed. The fix moves the word DOWN with its dash rather
than letting the line run over; the dash still never opens a line, which is the property the glue
existed for. No shipped message body moved (full suite + `verify_text` green over 3404 messages),
because nothing else had a line that landed in the two-character window.

General shape, and the reason this is written down: **a formatting rule that edits a line after the
width check has to re-run the width check.** The failure is invisible to every decoder — the text
is well-formed, correctly encoded, and simply too wide.

**And the first fix only MOVED the overflow, which review caught.** Re-measuring the line the dash
leaves is not enough; the line it lands on has to fit too. Where it cannot — a word whose own length
plus `' --'` already exceeds the width — the two rules genuinely conflict, the pair is atomic, and
the glue wins: that line goes out over-width because no shorter arrangement exists. So the invariant
is *"within the width unless it is a lone word carrying its dash"*, and the test now says exactly
that, plus walks the dash through every gap in a sentence at every width from 20 to 44 rather than
trusting the one sentence that found the bug. No authored box is anywhere near the atomic case; if
one ever is, reword it rather than loosening the glue.
