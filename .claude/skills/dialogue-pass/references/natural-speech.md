# Natural speech — mine the corpus, then write

**This is law, not advice.** It was learned expensively: ch05's 9BB took a dozen rejected
drafts, and every one failed the same way. Read this *before* drafting any scene, and do the
mining step for real — not from memory of what FE8 sounds like.

## Step 0 (MANDATORY): find the corpus twin before you write a line

Do not draft from instinct. FE8 ships ~40,000 lines; find the scene that already solves your
problem and read it.

```sh
# the twin chapter's own scenes, boxed, with counts
python3 tools/vanilla_scene.py ch5 [SceneFragment]
```

To find a *relationship* twin (the highest-value search — supports are FE8's intimate
two-handers and are the closest form to most of our scenes), scan `texts/texts.txt` for
messages with exactly two `[LoadFace][FID_x]` speakers and 6–20 `[A]` presses. That surfaces
~217 scenes; group them by speaker pair and the frequent pairs are the support conversations.
Then pick the pair whose *dynamic* matches yours and read every scene they have.

**Worked example:** for Basil (eager, gentle) + Sahnar (reserved, ancient), the twin is
**Ewan + Saleh** — enthusiastic student, quiet reserved mentor. Reading two of their supports
fixed four faults at once, after a dozen drafts of guessing had fixed none.

## The four faults (all of mine, all fixable)

Judge every draft against these before showing it to Nicolas.

**1. Epigram disease — the big one.** Every line polished into a perfect little artifact that
lands one beat and hands off. Strung together it reads as poetry, not talk. **Vanilla is
redundant and inefficient, and that is exactly why it sounds like people:**

> **Joshua:** "No, pardon me! I never meant to startle you. May I offer my apologies…"
> **Natasha:** "No, it's not necessary… It was my fault. Excuse me, I must be going… Good day to you."

Both apologise twice; Natasha says four things that all mean "I'm leaving." Compressing that
to one perfect line kills it. **Let characters waste words.**

**2. Metronomic turns.** Statement → response → statement → response, two lines each. Real
turns are lopsided: Saleh says *"....Ewan."* and Ewan fires back forty words. An excited
character **runs on, interrupts himself, and changes direction mid-turn** — Ewan: *"No way. I
wanna be just like you. Why would I go study somewhere else? **Wait...** You've gotta go out on
a mission again, don't you! Take me with you! I've practiced a lot..."*

**3. Subtext-burial.** FE8 characters SAY the feeling: *"I'm so glad to see you."* *"You're
safe."* *"You're the best."* Hiding everything in implication reads as coy, and it starves the
scene of warmth. Say it plainly; let the *subtext* be what the saying costs.

**4. The ellipsis tic.** `...` on every line stops reading as a pause and makes everything
portentous. Vanilla uses `......` sparingly, as a real beat (Saleh uses one before he gives
in). Reserve is conveyed by **brevity and plainness**, never by trailing dots.

## Positive rules

- **Register = how much and how fast someone talks**, more than word choice. Eager characters
  spill; reserved characters answer in one plain sentence and stop.
- **Plain complete sentences for the reserved character.** Saleh: *"My mission is my life. If
  you wish to learn magic, you'd be better served by another."* Direct, unornamented, a little
  blunt, kind underneath. Not aphorism.
- **No crafted beauty.** There is not one deliberate aphorism in an Ewan/Saleh support. If a
  line sounds quotable, check whether a person would actually say it out loud.
- **Contractions and casual register** where the character allows ("wanna", "gotta", "a ton of").
- **A character's own values should generate their turns**, not the other character teaching
  them. Basil's doubt had to come from *her* horror at an unhealed animal, not from Sahnar
  pronouncing a verdict on Ravisin.
- **Villains condemn themselves in reported speech.** *"She said it would still run"* damns
  Ravisin harder than any character analysing her would.
- **Close a two-hander the way vanilla does** — one character alone, looking ahead. Joshua's
  3-box / 5-line aside (observation → wry regret → shrug into his next errand) is the pattern;
  ch05's 9BB matches it beat for beat.

## Also see

- `fe8-register.md` — the villain register + archetype table.
- `scene-pacing.md` — measured box budgets; vanilla front-loads its bookend cutscenes and keeps
  mid-battle beats to ~3 boxes.
- `SKILL.md` §Craft check — no contrasting clichés; people talking, not mood-narration.
