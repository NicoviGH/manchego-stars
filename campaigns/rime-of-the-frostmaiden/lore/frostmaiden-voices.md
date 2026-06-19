# Frostmaiden voices — canon NPC voice reference

Voice reference for the **named canon characters** of *Rime of the Frostmaiden* we adapt as
recurring NPCs, bosses, and quest-givers. Distinct from:
- the **PC bibles** (`braulo.md`, `marty.md`, …) — our seven player characters;
- [`npc-bench.md`](npc-bench.md) — generic, setting-true *wanderers/villagers* (house visits, shops, one-liners);
- the **major-NPC bibles** with full §Voice ([`hlin-trollbane.md`](hlin-trollbane.md),
  [`scramsax.md`](scramsax.md), [`sephek-kaltro.md`](sephek-kaltro.md),
  [`duvessa-shane.md`](duvessa-shane.md), [`vellynne-harpell.md`](vellynne-harpell.md),
  [`izobai.md`](izobai.md)).

When a canon NPC graduates to real recurring screen time, give them their own full §Voice
bible (like Vellynne) and link it from the table below. Until then, this one-liner is the
grounding. Per-town quest NPCs are pulled to canon **when we stage that chapter**, not before.

## Two registers every line must satisfy

1. **FE8 cadence (the form).** Corpus: `fireemblem8u/texts/texts.txt` (FE8's full script) and
   our own already-shipped prologue/ch01 in it. House texture: **short, hard-broken lines**
   (~30 chars/visual line to fit the box), `...` holds, `--` interrupts, dry fragments, a beat
   before the punch. Model line (our Hlin): *"No blood, either. Shards and frost. That's all
   he left."*
2. **Frostmaiden voice (the content).** Each NPC's canon diction, below. The book's read-aloud
   text sets the *narration/atmosphere* register; the appendix stat blocks
   (personality/ideal/bond/flaw) set *character*.

## Arcane Brotherhood (four wizards; recur all game)

| Character | Canon voice — one line | Our usage |
|---|---|---|
| **Vellynne Harpell** | Cold, formal, economical necromancer; a body tremor means she *rides, never walks*; uses people as instruments, races her rivals ("I don't finish second"), but the cordial-est of the four. → full bible: [`vellynne-harpell.md`](vellynne-harpell.md) | Ch2 opening (orb hook) → recurring pragmatic ally |
| **Nass Lantomir** | Naïve-grad-student energy: impulsive, scatterbrained, overconfident, rambles about her pet topics past anyone caring. | Our orb-thief — "ahead of you," a near-miss antagonist west/north |
| **Avarice** | Albino tiefling evoker. Cold, cruel, supremacist; the *ruthless* one. Openly hates Vellynne. | Later Brotherhood rival / antagonist |
| **Dzaan** | Red Wizard of Thay illusionist; arrogant, secretive; wants magic hoarded for Thay. | Later Brotherhood rival |

## Relics, villains & cult

| Character | Canon voice — one line | Our usage |
|---|---|---|
| **Professor Skant (the orb)** | Pompous, patronizing chatterbox — "speaks like a college professor and assumes all humanoids are dunderheads"; expert in Netherese history, vampires, the tarrasque. | The stolen orb. **A perfect recurring foil for RBG** — two insufferable "professors," one a ball of glass RBG can't out-talk. |
| **Auril, the Frostmaiden** | A mask of cold fury; remote, relentless, cosmic. Almost never speaks directly — she commands through frost giants and winter wolves. | The campaign's distant prime mover; keep her *off the page* and felt. |
| **Frost druids / "Children of Auril"** | Zealots: appeasement and sacrifice, *worship is the only redemption*; some are just desperate folk buying their families a winter. | Targos street-preacher (Ch2 seed) → Ch4 boss |

## Per-town / per-chapter NPCs — pull to canon when staging that chapter

- **Naerth Maxildanarr** — Targos speaker (Ch2). | **Lonelywood speaker** — old, hard-of-hearing woman (Ch4). | **Dorbulgruf Shalescar** — cantankerous old Bremen dwarf who stiffs the party (Ch7). | Dwarves of the iron job: **Hruna / Korux / Storn** (Ch1, see `izobai.md` notes).
