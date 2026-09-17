---
id: 266
title: "Permadeath is a combat rule, not a narrative one"
date: "2026-08-29"
section: "Operational Gotchas (durable)"
issues: []
---

# Permadeath is a combat rule, not a narrative one

**The eight PCs appear in every cutscene whether or not they are alive.** No `CHECK_ALIVE`, no
alternate lines, no fallback speaker. Recruits and NPCs -- Basil, Sahnar, Lupin, the boat crews --
keep vanilla's treatment and branch normally.

**Why we diverge from vanilla here, deliberately.** Vanilla gates dialogue on aliveness 121 times,
110 of them on 33 *named playable* characters, and its idiom is cheap: `CHECK_ALIVE` picks a
message id rather than forking the scene (`SVAL(EVT_SLOT_2, <id>)` then one `TEXTSHOW`), and where
several characters matter the checks collapse to one shared label -- two characters give two
outcomes, not four. The FALLBACK is what we cannot copy: vanilla hands the dead character's lines
to someone who *cannot* die. FE8 Ch4's recruit scene is the model -- Artur recruits Lute
(`MSG_9AD`), and if Artur is dead **Eirika** speaks the identical beat and Lute answers "Yes? Who
are you?" instead of greeting a friend (`MSG_9AE`); `MSG_9AF`'s four-hander becomes the same
conversation between Eirika and Seth alone (`MSG_9B0`).

That strategy rests on a character who is structurally always present. **We have none:** the
player picks their lord at the start, and `difficulty.py`'s lord sweep tests every PC as the
must-survive unit. There is no Eirika to hand the line to.

And the deeper reason: these scenes are a record of a D&D campaign that actually happened. Writing
a PC out of one because a player lost them on a map would rewrite what the table did -- the hack
would stop resembling the campaign it exists to preserve. Combat is FE; the story is theirs.

**The invariant that makes it safe: a cutscene LOADs its actors, never assumes them.** `LoadUnit`
performs no death check (`bmunit.c`), so loading a dead character works and always has -- vanilla's
gating is an authorial choice, not an engine limit. But `GetUnitFromCharId` returns NULL for an
absent unit, and `CUMO_CHAR`/`MOVE` resolve through it, so a staged beat that assumes a unit is
standing on the map is the never-returns soft-lock `assert_scripted_move_reachable` was written
for. Vanilla's own scenes `LOAD1`/`LOAD2` their actors before staging them; ch04's moose does the
same. Every scene of ours must.
