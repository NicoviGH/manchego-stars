---
id: 188
title: "A conditional block inside a scene is a WHOLE second copy, not a spliced beat"
date: "2026-08-19"
section: "Operational Gotchas (durable)"
issues: [25]
---

# A conditional block inside a scene is a WHOLE second copy, not a spliced beat

ch05's scene 16 loses six boxes when Sahnar was never recruited. The obvious wiring is to make
those boxes their own message and let the event script skip the call — three `Text()`s where
there was one, which is also how every other chapter's ending is already assembled. It was built
that way, it **passed**, and it looked wrong on the first film:

> *"can you not just keep basil in frame the whole time and just have the other characters come
> in and out, in a single continuous scene? its weird when you refresh and basil ends up right
> where she was"* — Nicolas, 2026-08-19

`Text(msg)` is `TEXTSTART` + `TEXTSHOW` + `TEXTEND` + **`REMA`**, and `REMA` ends the text: the
faces come down with it. So a scene split across three calls has two seams, and any speaker who
appears on both sides of one fades out and reloads into the seat they were already in. Basil
speaks in all three beats, so the scene's own subject flickered twice.

**Held as ONE message per arm, `_script_to_message`'s podium manager runs the whole scene**: it
loads Basil once at mid-right, never clears her, and cycles Marty → Wolfram → Sahnar → Braulo →
RBG → Braulo through mid-left with a `[ClearFace]` between each. That is the scene — the party
comes to *her* — and it falls straight out of the renderer once nothing interrupts it.

The cost is text duplication, and it is **not** a cost worth avoiding here:

- **The ids are the same either way.** Whole copies of scene 16 against beats-plus-a-twin cost
  the same count. The earlier reasoning that a split is cheaper (*"duplicating text is free, ids
  are what is scarce"*, recorded above) was priced against an id shortage that does not exist,
  and it never counted the seams.
- **Nothing is hand-duplicated.** Every copy is generated from the one locked script by
  `variant_beat`, whose `replaces:` anchors assert each edit lands where the YAML says. There is
  no second copy of the prose to drift.

`variant_beat` now takes a variant with **no `script:` key at all**, meaning *drop these boxes*.
A cut authored as six empty substitutes would say the same thing far worse, and the anchors
still apply — which matters most for a drop, because a mis-indexed cut is invisible in the
output: the result is simply a shorter scene that still reads. The build asserts the arm is six
boxes shorter and that Sahnar has no line left in it, since anchors alone cannot prove a
deletion happened.

**Two variants over one script compose only in one order.** The no-Lupin substitution is box 16
and the cut takes 8–13, so applying the cut first moves the wolf line to box 10 and the
substitution lands on the wrong box or falls off the end. Substitutions are 1-for-1 and
therefore index-preserving, so they go first; both variants stay authored against the ONE locked
script, which is the only version a reader can check the indices against.

**And the general one: a branch that PASSES can still be wrong.** The box-count assertion
covered the arm, `verify_text` covered the text, and neither can see a face reload. Presentation
is filmed (`decisions.md` → "Three data checks can pass while the thing is visibly broken").

_Decided: 2026-08-19 (Nicolas, on the first film of the ending)._
