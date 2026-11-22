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

**The rule.** An arrival (a red unit that stood off the field and then on it, or whose slot the
game killed and loaded again) is named by character, class and the turn it first stands on the
board: `a:<char>:<class>:<turn>`. Two Snipers of one wave are one memory, as to a player. The
turn is `arrivals_seen`'s `boardTurn` (ADR 0436), and it has ONE owner: `botrun`'s `stamp`, the
detector that also writes `arrivals_seen`. It reads the turn the same way from every board: the
turn after an enemy-phase landing, and for a board read inside an enemy phase. It stamps fogged
arrivals too, since the key only names the unit for matching; what the bot may know of a fogged
unit is #713 fix 1's question.

**A unit on the field at the start keeps its slot key**, `<slot>:<char>:<class>`, stamped turn 0.
Every attempt loads the same start, so its slot is stable, and a player recalls it by where it
stood; keying on the start tile would add a tile read for nothing.

**The two never match each other.** `Sight.knows` asks for the key of the unit's own kind: an
arrival's key when it has an arrival turn, the slot key when it was there at the start. So a
memory of the start's unit in slot S does not name a later arrival in S, and a memory of an
arrival does not name the start's unit there. A memory written before this ADR names every
unit by slot, so a retry reading one would not know an arrival; memory lives only for one
campaign's attempts (`campaign.lua`), so none is stored across versions and none needs reading.

**A refill is an arrival record too.** A killed slot loaded again is written to `arrivals_seen`
like any other, so `campaign.lua` feeds its turn into `style.arrivals` (ADR 0386) and its unit and
tile into `style.memory.arrivals` (ADR 0436): a retry's reinforcement claims and owed-recruit
goals see it. A slot counts as refilled only when the previous board showed its unit alive and the
game has since killed it (`killedSince`, cleared at every stamp); a kill reported late for a slot
already dead is none.

**`arrival_unstamped`** (an anomaly in the record, beside ADR 0388's) fires for two cases only: a
red on the field that no event named and no stamp holds (a unit that changed sides to red, a first
sighting mid-chapter), and a killer no board showed. Each is stamped as an arrival. A class read
another way for the same character (a promotion, a class not read) keeps its arrival turn and is no
anomaly; another character in a slot no kill was reported for is an arrival, also no anomaly.

**A killer is stamped before it is remembered.** `record` stamps the board after the deaths
before it reads a killer, so an arrival that kills on its landing turn is stored once, with its
turn. One no board showed is stamped as an arrival and noted as an `arrival_unstamped` anomaly.

**Wiring.** `stamp` tells the sight (`sight.arrived`, once per board, refreshing its reads only
when a turn above 0 changes); `enemies_seen` entries carry `arrival`; `campaign.lua` keeps and
copies it into `style.memory.enemies`; `sight.knows` reads it.
