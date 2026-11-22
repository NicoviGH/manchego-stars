---
id: 449
title: "A retry remembers an arrival by its class and turn, not its slot"
date: "2026-11-22"
section: "Combat System"
issues: [713, 510]
---

# A retry remembers an arrival by its class and turn, not its slot

**Decided (#713 plan, fix 2), #510 step 9.** Amends ADR 0399's key. Fix 1 (an enemy seen this
attempt and then fogged) and fix 3 (summing unseen strikes) are Nicolas's calls on #713 and are
not built here.

**Why.** ADR 0399 kept a remembered enemy by slot, character and class (`Board.memoryKey`). A
reinforcement lands in a slot an earlier unit died out of, and which slot depends on who died.
On Ch19 `b640e-cs-s4003` the Sniper of slot 147 in attempt 2 was not remembered: slot 147 held a
Great Knight and a Warrior in attempt 1. A player does not recall "slot 147"; he recalls the
Sniper that came on turn 7.

**The rule.** An arrival (a red unit that stood off the field and then on it) is keyed by
character, class and the turn it first stood on the board: `a:<char>:<class>:<turn>`. Two Snipers
of one wave are one memory, as to a player. The turn is the board turn `arrivals_seen` already
names (`boardTurn`: the next player turn after an enemy-phase landing). It is read for a fogged
arrival too, since the key only names the unit for matching; what the bot may know of a fogged
unit is #713 fix 1's question.

**A unit on the field at the start keeps its slot key.** Every attempt loads the same start, so
its slot is stable, and a player recalls it by where it stood, which its start slot stands for;
keying on the start tile instead would add a tile read for nothing and break when a unit is moved
by a start event. So its key is unchanged: `<slot>:<char>:<class>`.

**Stored memory keeps working.** `sight.knows` tries the arrival key and then the slot key, and an
entry written before this ADR has no `arrival`, so it is keyed by slot and still matches as it did.
An entry with an arrival has no slot key, so it never matches by slot. Memory lives for one
campaign's attempts (`campaign.lua`), so no stored file needs migrating.

**Wiring.** `botrun.changes` stamps each red unit's arrival turn (0 at the first board) and tells
the sight (`sight.arrived`); `enemies_seen` entries carry `arrival`; `campaign.lua` keeps and copies
it into `style.memory.enemies`; `sight.knows` reads it.
