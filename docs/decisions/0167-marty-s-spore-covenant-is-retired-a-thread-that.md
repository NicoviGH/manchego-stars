---
id: 167
title: "Marty's \"spore covenant\" is retired — a thread that reads well in a bible and never reached a beat"
date: "2026-07-29"
section: "Story & Dialogue"
issues: []
---

# Marty's "spore covenant" is retired — a thread that reads well in a bible and never reached a beat

Written 2026-07-23 during the ch05 dialogue pass: Marty as Ravisin's opposite number ("two
necromancers, opposite covenants: the composter vs. the taxidermist"), the dead owed a free return
to the earth, the sin being death held out of the cycle by force. It was a genuinely tidy idea and
it survived three weeks purely because it lived in `marty.md` rather than in a scene.

It never reached one. It carried an explicit IOU — *"exact line TBD in the beat; may move to the
recruit beat"* — and both candidate beats then locked without it. 9C5 gives the PARTY no lines at
all (vanilla Ch5's escalation is the arriving force speaking, and we took that shape); 9C6 turns
on Sahnar RECOGNISING Basil, not on anyone naming a sin over her. Nicolas's call, and correct:
*"it was an idea we silently moved away from… remove it so it doesn't mess with his character
later."*

The general lesson, which is why this is an ADR and not a quiet delete: **a bible section with an
open "line TBD" is a liability, not an asset.** It is unwritten dialogue stored where voice
guidance lives, so every future writer reads it as settled character and writes toward it. A voice
bible should describe how someone talks; a thread that needs a scene to exist belongs in the
chapter YAML's slot description, where it dies with the slot if the slot is cut.

Retired phrases are in `check.py` `DEAD_CONCEPTS`, so the drift lint rejects them in docs and
hand-written comments. Sahnar's ordeal no longer needs a second druid to mean something: she is a
soul held awake under stone, which is legible on its own.

_Decided: 2026-07-29 (Nicolas + CLAUDE; ch05 dialogue pass — retiring the "two druids" thread)._

---
