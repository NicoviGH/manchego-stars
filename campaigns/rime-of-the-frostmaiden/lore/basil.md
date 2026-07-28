# Basil — the sentient goodberry shrub (ch05 recruit) — Lore & Voice

> **DRAFT — Phase 0 of the ch05 dialogue pass (2026-07-23). Co-written with Nicolas.
> Verbalness fork RESOLVED (Groot-flavored + self-sufficient); origin (Ravisin's shrub)
> approved; calibration lines still await red-pen.** ch05 "The
> Elven Tomb" recruit — the Natasha beat (fragile healer the party escorts). Mechanics in
> [`chapters/ch05-the-elven-tomb.yaml`](../chapters/ch05-the-elven-tomb.yaml) (Priest;
> Goodberries = the cosmetic skin on a vanilla heal staff; the in-fiction source of the
> party's reflavored Vulneraries) and [`npcs/basil.yaml`](../npcs/basil.yaml). Art landed
> PR #179 (Oddish-sourced).

## Concept

A small **sentient goodberry shrub** — and, in canon, **Ravisin's own**: her awakened
companion, kept at the druid's side so she always has goodberries to hand (RotFM). So Basil
is the **villain's gentle pet, made kind** — the one soft thing the cold woman keeps
close. (Not "a grieving zealot": `ravisin.md` bans grief/pathos for her outright — she keeps
him because a druid wants goodberries to hand, not because she is lonely.) **He is already
called Basil** — he introduces himself, and nobody in the party ever calls him anything else
(LOCKED 2026-07-23, Nicolas: no "unnamed shrub" phase, no naming ceremony — the party naming
him would have contradicted the locked opening, where he speaks as `basil:` from his first
line). Where the name came from is deliberately unexplained. When Ravisin falls the party
takes him in — they **repot him**, and he becomes their second healer, growing Goodberries
and handing them out, which is every heal-staff and Vulnerary the party drinks. He is **guileless, gentle, and growing**
(literally, over the campaign): no guile, no agenda, just the urge to feed and mend the
people around him. As the fragile recruiter he must be walked into danger to reach Sahnar —
and it's *Basil*, not a blade, that turns the old duelist.

- **The arc:** Ravisin's shrub → the party's heart. Made by the old druidcraft, kept by its
  coldest servant; in the party's hands the same green magic just *feeds people*. He is living
  proof it didn't have to serve the winter. (Approved flavor, 2026-07-23, Nicolas.)
- **Wants:** sun, water, and for everyone to be fed and unhurt. That's the whole list.
- **Love-language is feeding** (the campaign's "feed them" motif — cf. Lupin's pack, ch04):
  a berry offered *is* Basil saying he cares. He heals by feeding.
- **Why he turns Sahnar:** he isn't afraid of the sword; he offers the scary dead queen a
  berry. A living green thing, tended and kind, is the proof the old craft still grows —
  and that reaches Sahnar where a blade never could, through her long, bound watch.

## Voice — **REVISED 2026-07-23 after the 9BB write. Corpus twin: EWAN (of Ewan/Saleh).**

> The earlier spec here said "usually 2–5 words, no subordinate clauses." **It was wrong and it
> is retired.** In practice it made Basil read as *slow* — jokes landed at his expense and the
> scene read as haiku rather than talk. Nicolas: "it makes Basil sound unintelligent."

**Warm, eager, and he TUMBLES.** When something matters to him he spills — several sentences in
one turn, interrupting himself, doubling back, arguing with a "no" before it arrives. Read
**Ewan** in the Ewan/Saleh supports: *"No way. I wanna be just like you. Why would I go study
somewhere else? Wait— you've gotta go out on a mission again, don't you! Take me with you!"*
That's the register. He is **awakened, not simple-minded** — the plainness is a kind heart with
no guile, never a small mind. He is **self-sufficient**: he carries his own beats, including the
Sahnar recruit — **no translator crutch**. He is NOT Marty — where Marty *sells*, Basil *offers*.

**Diction rules**
- **Runs on when he cares.** Long turns, stacked short sentences, self-interruption ("—and
  then—", "Wait—"). Answers a question and keeps going. Short lines are for when he's *hurt*.
- **He says the feeling out loud.** No coy subtext: "I'm worried." "I counted them." "I wish I
  could share my berries with her." Plain sincerity is his whole charm.
- **Concrete and countable.** He notices numbers and specifics — three arrows, six days, which
  stone the sun cleared. Attention is how he loves.
- **Feeding = affection.** Offering food is comfort, greeting, and love.
- **Plant-logic, lightly:** sun, rain, roots, frost, growing. He reads the world as *tending*.
- **No guile, irony, or sarcasm.** He means every word.
- **Never write his lines as epigrams.** If a line sounds quotable, it is probably wrong for
  him — see `.claude/skills/dialogue-pass/references/natural-speech.md`.

**Calibration lines (draft — for Nicolas's red-pen; not yet used in any beat)**
- (adopted at the end — repotted, not renamed) "A pot. …Mine?" → "I will grow. For you."
- (healing in battle) "Hurt. Here. Eat." / "Eat. Grow. Stay."
- (refusing Ravisin as she rips Sahnar up — his breaking point) "No. Not her. …I won't."
- (the Sahnar turn — **carries the recruit alone**, offering the berry to the bound mummy)
  "She hurt you. You are not hers. …Wake up. I have you. Eat."
- (to Marty, on their two ways of winning people) "You sell. I feed. …Same."

**Banned:** needing a party-member to translate for him (rejected — he stands on his own);
writing him **simple-minded** (spare speech, full soul — never dumb); long or winding sentences;
subordinate clauses; cutesy baby-talk / "hehe" overload; modern slang; any edge (sarcasm,
menace — he has none); a literal "I am Basil" Groot-quote gimmick unless Nicolas asks for it;
**grieving or mourning Ravisin** (`ravisin.md`: she is never mourned — see Q4 below).

## Open questions for Nicolas
1. ~~**The verbalness fork (A vs B)**~~ — **RESOLVED 2026-07-23:** Groot-flavored + self-sufficient
   (see §Voice header).
2. ~~**Does Basil name himself or accept the name?**~~ — **RESOLVED 2026-07-23 (Nicolas): neither.
   He is simply Basil from his first line.** No unnamed phase, no naming beat; the origin of the
   name is left unexplained. Simpler, and it matches the locked opening.
3. ~~**When does he leave Ravisin?**~~ — **RESOLVED 2026-07-23 by the locked ch05 opening:** he is
   a **GREEN ally** on the map from the start (not Ravisin's unit, not a starting player unit), and
   **converts to a player unit on the `map_opening` join** when he asks to be taken to Sahnar. The
   `chapter_end` beat is then the *adoption* (repotting him), not the discovery or a naming.
4. ~~**Does Basil grieve Ravisin?**~~ — **RESOLVED: no.** `ravisin.md`'s banned list settles it —
   she is never mourned or softened, and Basil's kindness must not read as the story pitying her.
   Play him **relieved**, not bereaved.
