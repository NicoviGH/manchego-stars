---
id: 159
title: "MINE THE CORPUS BEFORE WRITING A LINE — this is now step 0 of the drafting loop, not advice."
date: "2026-07-23"
section: "Story & Dialogue"
issues: []
---

# MINE THE CORPUS BEFORE WRITING A LINE — this is now step 0 of the drafting loop, not advice.

ch05's Basil/Sahnar scene burned a dozen rejected drafts written from instinct; **two Ewan/Saleh support conversations fixed it in a single pass.** FE8 ships ~40k lines and we were cherry-picking six quotes and then guessing. The method (`.claude/skills/dialogue-pass/references/natural-speech.md`, wired as SKILL.md drafting-loop step 0): read the twin chapter's scenes with `tools/vanilla_scene.py`, and for a two-hander find the **relationship twin** among FE8's ~217 two-character scenes — its **support conversations** are the game's intimate two-handers and the closest form to most of our scenes. Pick the pair whose *dynamic* matches (eager student + reserved mentor → Ewan/Saleh) and read all of them.
The diagnosis it produced — **"epigram disease," our single most common dialogue failure**: every line polished into an artifact that lands one beat and hands off, which reads as poetry rather than talk. **Vanilla is redundant and inefficient and that is precisely why it sounds human** (Joshua and Natasha both apologise twice; she says four things that all mean "I'm leaving"). Four laws follow: turns are **lopsided** (two words answered by forty); the eager character **runs on and interrupts himself**; characters **say the feeling plainly** instead of burying it in subtext; reserve reads as **brevity and plain complete sentences**, never as an ellipsis on every line. Corollary applied to `basil.md`: the "2–5 words, no subordinate clauses" spec was retired — it made her read as slow rather than gentle.
_Decided: 2026-07-23 (Nicolas + CLAUDE; ch05 9BB — "you have the entire game's dialogue and you're not writing like it")_
