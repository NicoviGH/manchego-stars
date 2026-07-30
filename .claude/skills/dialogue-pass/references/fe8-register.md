# FE8 script register — how the vanilla game actually talks

Distilled from the decomp corpus (`fireemblem8u/texts/texts.txt`, ~40k lines = FE8's full
script) on 2026-07-23, while ch05's villain lines kept reading flat. **Read this before
writing any villain, and re-read the corpus when a new archetype comes up** — the point of
this file is that we ground voices in what the game shipped instead of inventing a register.

Companion to `lore/frostmaiden-voices.md` §"Two registers every line must satisfy": that file
owns the *Frostmaiden content* (who these people are); this one owns the *FE8 form*.

## Reading the corpus

- Text lives in `texts/texts.txt` as `## MSG_xxx` blocks. Names are separate short entries
  (`Valter[X]`); the scenes are elsewhere, so grep by **content**, not by speaker name.
- Inline markup you'll see and what it means for pacing:
  - `[A]` = A-press / page break · `[LF]` = line break within a box · `[X]` = end of message
  - `[.]` = a short beat · `[ToggleMouthMove]...[ToggleMouthMove]` = an ellipsis pause
  - `[ToggleSmile]` = smug/smiling portrait · `[OpenMidLeft]` / `[LoadFace][FID_x]` = staging
- Practical read: FE8 leans on **`...` pauses** and **hard short lines** far more than on long
  sentences. A beat is punctuation, not a clause.

## The villain register (the main finding)

FE8 villains are **theatrical and enjoying themselves.** Ours were failing because they were
written as calm, self-explaining ideologues. Six habits, all over the corpus:

1. **Address the party directly, with an insult-name** — dogs, wretches, rats, fools, scum.
2. **Relish it.** Appetite is on the page: hunger, blood, fun, prey.
3. **Dark irony** — reframe atrocity as a favour or a chore. This is the big one.
4. **Announce what's coming**, theatrically, right before it happens.
5. **Short sentences, heavy `...`**, and villain laughter (`Heh heh heh...`).
6. **Self-mythologize** — titles, epithets, "you will call me X".

### Calibration quotes (verbatim)

**Valter** — predator; appetite made text:
> "Ha ha... Eirika, eh? She's a ripe little peach. And her brother, Ephraim... He's better
> prey than I'd imagined. **I can feel my blood rushing at the thought.** This might be fun
> after all."

**Valter** — boss taunt; the whole register in four lines:
> "So we meet again. You know me as General Valter, but **you will call me the Moonstone.**
> I'll save you **worthless dogs** from your own incompetence. **You'll thank me later.**"

**Riev** — oily schemer; idiom + laugh:
> "Like rats in a sack, as they say. Heh heh heh..."

**Selena** — contempt then announcement:
> "What idiotic wretches you are... **Prepare yourselves to be destroyed utterly!**"

**Vigarde** — the dead-flat commander (a *different* villain shape: no relish at all, pure
imperative, very short):
> "Caellach. Riev. Shatter the remaining Sacred Stones. Caellach, take Jehanna. Riev, take
> Rausten. Go. Crush the Sacred Stones they house."

**Caellach** — gruff, petty, human; complains about his assignment:
> "Bah! Why am I stuck with Jehanna? Accursed ill luck."

### The move worth stealing most often

**Valter's "You'll thank me later."** A villain who sincerely believes their violence is a
*kindness* should deliver it as **swagger, not sermon**. Any mercy-doctrine (Ravisin's frost,
a zealot's "purification") lands better as a taunt with dark irony than as an explained creed.
If a villain is narrating their philosophy, the line is already dead — see SKILL.md §Craft
check, "people talking, not mood-narration."

## Archetype spread (so villains don't converge)

The corpus deliberately varies them — use this to keep ours distinct:

| shape | example | texture |
|---|---|---|
| predator / appetite | Valter | sensual, hunting metaphors, *enjoys* you |
| oily schemer | Riev | insinuating, idioms, laughs, obsequious to superiors |
| flat commander | Vigarde | imperatives only, no affect, very short |
| gruff careerist | Caellach | complains, ambitious, mercenary, "Bah!" |
| serene executioner | (ours: Sephek) | calm, liturgical, pitying — *never* raises voice |

Ours already occupy some of these: **Sephek** = serene executioner (his own bible), **Izobai**
= mocking bandit-warlord. So a new villain should be checked against this table for collision
before drafting — that check is the villain half of SKILL.md's cover-the-name test.

## Non-villain notes

- Allies interrupt and talk over each other (`--` interrupts are common); comic NPCs run a
  single gag hard (our Nimsy "MOUSSE?" beat is squarely in FE8 register).
- Boss death quotes are SHORT — a line or two, often an unfinished thought trailing on `...`.
