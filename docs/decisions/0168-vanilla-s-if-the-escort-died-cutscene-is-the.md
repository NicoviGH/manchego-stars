---
id: 168
title: "Vanilla's \"if the escort died\" cutscene is the same scene's BACK HALF — so our branch is cheap"
date: "2026-07-30"
section: "Story & Dialogue"
issues: []
---

# Vanilla's "if the escort died" cutscene is the same scene's BACK HALF — so our branch is cheap

FE8 Ch5 ships its ending twice: `0x9C9` (34 boxes) if Natasha lives, `0x9CA` (24) if she dies.
The obvious read is "a whole alternate cutscene", and that read is what made an earlier pass mark
ours *not adopted* — it looked like duplicate exposition for a case most players never hit.

Mining it says otherwise. `0x9CA` is not a second scene. Its front is a different DELIVERY of the
same facts — fragments, interrupted by the party telling her to stop talking, then a flat
"....She's dead." — and its back is `0x9C9`'s deliberation running near-verbatim, with **exactly
one line changed** to price the loss (*"If she had lived, we might have learned more, but…."*) and
the closing box repeated word for word. The branch costs the delivery, not the scene.

So the rule for any chapter with an escort who can die: **the alternate ending is a re-delivery,
not a rewrite.** Write the lived one, then change how the information arrives and who is left to
react — and keep the last boxes shared, because that is what makes the two endings feel like one
chapter. ch05's pair sits at 25 / 18 boxes on this pattern.

The structural consequence that is easy to miss: it is the ESCORT who carries the chapter's forward
information, not a party member. That is *why* the branch has to exist, and it is also the reason
the escort's death is a real failure rather than a lost unit. Ours puts the ch06 hook in Basil's
mouth for the same reason — Sahnar is optional and cannot carry mandatory plot, and no party member
was standing in the tomb listening to Ravisin talk.

_Decided: 2026-07-30 (CLAUDE; ch05 ending block — adopting `0x9CA`, mined from `EventScr_Ch5_EndingScene`)._

---
