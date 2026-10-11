---
id: 342
title: "The roster keeps vanilla's recruit cadence; ch07 and ch08 add Halvar, Meriwa and the White Moose"
date: "2026-10-11"
section: "Combat System"
issues: [459, 27, 25, 28]
---

# The roster keeps vanilla's recruit cadence; ch07 and ch08 add Halvar, Meriwa and the White Moose

Nicolas, 2026-10-11 (#459). **The party gets the bodies vanilla's Eirika route would have given it
by the same chapter, and fills the role of each vanilla recruit it is missing.** This replaces ADR
0047's "~16–18 pool" budget, which stopped well short of vanilla's 33.

**What we are missing.** Matched recruit by recruit through Ch8 (vanilla's join table is #459's,
derived from the decomp), the cast covers every vanilla unit except four:

| vanilla | why it has no match |
|---|---|
| Seth | none on purpose: no Jagen (ADR 0042; `npcs/baxby.yaml`) |
| Eirika / Ephraim | the lord is a player-picked PC with no LORD class (ADRs 0010, 0062). Ephraim only fields in Ch8 on Eirika's route: `ch8-eventscript.h` `REMU(CHARACTER_EPHRAIM)` removes him, Forde and Kyle stay (MSG_C10), and he returns at Ch15 autolevelled (`AutolevelSecondaryLord`) |
| Ross | the second axe |
| Artur | light magic (Rootis is Lute, the anima Mage) |
| Forde | the second Ch8 cavalier (Lupin already carries Kyle's line) |

Marty and Meesmickle (two Knolls, Ch15 in vanilla) are the extras that make the count 13 against 14
entering ch07.

**The fill, ch07–ch08:**

| unit | class | covers | joins | how |
|---|---|---|---|---|
| **Halvar Berylbore**, Grynsk's son (he/him) | Fighter | Ross | ch07 ending | one neutral line, "you found my father": true whether or not Grynsk's boat came home (flag `0xFC`) |
| **Meriwa**, the merfolk Messie has been talking to (she/her) | Monk | Artur | ch07 ending | Messie sends her with the party as proof of the truce |
| **The White Moose** | Cavalier | Forde | ch08 start | Marty talks to it: Ravisin is dead and it no longer has hate in its heart |

That is 16 fielded in ch08 against vanilla's 17; the one short is Ephraim, who leaves after Ch8.
ch09 (Revel's End) adds vanilla's Tana body, a flier; a griffon rider met in the breakout is the
direction (griffons: *Rime* pp.163, 198).

**Every join happens in a scene, never mid-battle.** Vanilla Ch6–8 have no talk recruit (`CUSA`), and
Ch7 adds no one, so ch07's force stays vanilla Ch7's 19 units with none removed. Talk recruits come
back from ch09–10, where vanilla has five of them, and are decided per chapter.

**Join levels are chapter-appropriate.** A recruit joins at the level it would have reached had it
joined on vanilla's schedule, read off vanilla's own late joiners against its party (Forde L6, Kyle L5
when Ch8's typical party is about L7; `tools/exp_curve.py`). Targets: Halvar about L7 (ch07's own
Fishers are Lv7), Meriwa L5–7, the Moose L6–7 (Lv6 in ch05). `make difficulty` sets each at wiring.

**The White Moose retreats in ch05 instead of dying**, as Nerra does in ch06 (ADR 0337), so every
player has it to recruit. The fight is unchanged, so ch05's force and lock do not move. It joins as
Lupin did: the beast is the unit, on the Cavalier class, every Cavalier weapon slot on its own anim.
Its map sprite and anim lose their blood first (cast palette index 6, `#cf2026`).

**Art.** Meriwa wears Stephano's Mermaid (already in the ROM for ch06; lance, bow, staff and magic,
with the magic cast on light tomes). On the map she draws from the shared 16-colour cast palette,
whose one green makes her flatter than the ch06 mermaids; her battle palette has no such limit.
Halvar is the vanilla Fighter. Each needs a portrait.

**Rejected:**
- Grynsk and Tali as recruits (Nicolas).
- Hlin Trollbane as an Ephraim analogue (Nicolas).
- Baxby as Seth: it would move ch02–ch06's locked force for a ch01 gap he cannot reach, and ADR 0042
  already rules out a Jagen.
- N426's Shark Rider as a recruit: a shark on every land map after ch07 reads as a joke. Merfolk
  slither, which is fine.
- Nerra: her voice bans pleading or switching sides.
- A mammoth rider (`Grand Mahout`) or a goliath for the Cavalier: no story in ch07–08 to bring them.
  `docs/fe-repo-scouting.md` keeps the mount sweep.
