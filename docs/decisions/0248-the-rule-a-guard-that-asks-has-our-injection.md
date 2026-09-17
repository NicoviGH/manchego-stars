---
id: 248
title: "The rule: a guard that asks \"has our injection happened?\" must name something only WE emit."
date: "2026-08-16"
section: "Operational Gotchas (durable)"
issues: [286]
---

# The rule: a guard that asks "has our injection happened?" must name something only WE emit.

`MS_Ch05DeployCap` is ours — absent pristine, present once injected — and the fix was verified
in both directions (`git show HEAD:` vs the working tree) rather than assumed. Vanilla symbols
answer "is the decomp checked out", which is a different question and almost never the one being
asked.

**Corollary for reading the decomp at all.** Three of the other woken classes touch the decomp
and are safe, because they go through `vanilla_decomp_text()` (`git show HEAD:`) rather than the
worktree — the same rule as "Read decomp data through `git show HEAD:`, never the built tree".
A test that reads the WORKTREE is asserting about a build artifact and needs an
injection-keyed skip; a test that reads HEAD needs none.

_Decided: 2026-08-16 (found by CI on #286, after the dormant-test fix woke the class)._
