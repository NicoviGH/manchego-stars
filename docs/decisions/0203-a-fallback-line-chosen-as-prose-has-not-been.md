---
id: 203
title: "A fallback line chosen as PROSE has not been boxed"
date: "2026-08-14"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A fallback line chosen as PROSE has not been boxed

ch05's five no-Lupin substitutes were chosen 2026-07-30 as single lines. Three of the five do not
fit one box at the talk bubble's 29 characters. (Two of the five have since been retired with the
endings' branches — and both of those were among the over-long ones, which is how the endings
ended up owing no boxing at all.) Scene 5's is 74 characters, and rendered flowed it
paged itself mid-clause — *"You just-- came"* / *"here. On your own."* — an A-press the author
never placed, on a scene whose locked arm was hand-boxed to this exact width in July.

This is the reliquary lesson arriving from a new direction: **the authored A-press breaks ARE the
pacing.** There it was a flowed YAML scalar reflowing 27 boxes; here it is a substitute written at
one width and rendered at a narrower one. The wrapper is not choosing badly — it has no idea where
the beat turns.

**So `variant_beat` now accepts a `script:` entry that is a LIST of boxes**, replacing the one
named box with all of them; `boxes:`/`replaces:`/`script:` still agree one-for-one, so this stays
one mechanism rather than a second. Substitutions are resolved against the original beat and
spliced afterwards — editing in place would shift every later `boxes:` index and the anchor
assertion would then blame the locked script for moving.

**Two arms of a branch are not required to cost the same number of A-presses.** Scene 5's no-Lupin
arm is 4 against the locked arm's 3. Nothing reads them together; each has to stand up alone.

Nicolas chose the break (2026-08-14): after the shock (*"...You're none of hers."*) rather than at
the sentence boundary, so her run-on then arrives whole. That is her register — `lore/basil.md`
§Voice, *"runs on when she cares"*, corpus twin Ewan — and splitting on the full stop would have
cut the tumble in half and buttoned the first box on *"one of you."*, which is not where the beat
turns. **The remaining on-map fallback (the Talk recruit's) overruns identically and takes the
same treatment when it is wired.**
