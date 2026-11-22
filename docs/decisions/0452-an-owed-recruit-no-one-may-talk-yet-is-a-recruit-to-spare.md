---
id: 452
title: "An owed recruit no one may Talk yet is a recruit to spare"
date: "2026-11-22"
section: "Combat System"
issues: [730, 699, 510]
---

# An owed recruit no one may Talk yet is a recruit to spare

**Decided (#730 fix 2), #510 step 9. Nicolas, 2026-11-22:** "Yes, its the same consequence as when
Seth counters and kills Joshua before Natasha reaches him." A recruit the game still owes
(`ctx.owedRecruits`, botrun's: the charIds the chapter's talks would bring over, less the party)
that dies to us is lost, whether or not anyone on our side may Talk it yet (vanilla Ch10's Marisa,
charId 0x16, before Gerik joins; Ch13).

**The gap.** `recruitsOf` listed a red unit as a recruit only when a blue unit's `mayTalkOver` it,
so before its talker joined its death forfeited nothing, to our counter (the judged phase's
`felled`) or to our own blow (`fx.recruitHit`).

**What changed.** `recruitsOf` also returns `loose`: the red, unfogged units on the field whose
charId is owed and that no blue unit may Talk. They are kept apart from `ctx.recruits` (the talker
recruits): no one can Talk a loose unit, so the march has nothing to stand beside
(`besideGoal`, `stepsToward`), and a loose red keeps the damage, kill and advance credit of any red,
so a Rout's loose last enemy is still a target. Only its death is priced, from the planner's one
reader of a recruit's fall (`fx.recruitHit` for our blow, `felled` for our counter); fix 1's sparing
waits read it too.

**The price is the talker's, one combination.** (1) Rank: `Goals.forfeited` takes `closes.loose`
and adds `owed:<unit id>` when the unit's chance to fall, less what a win outlasts
(`lost * (1 - win)`), passes `Goals.DUST`; `forfeits = #st.forfeited` ranks it first, as
`recruit:<id>` does. (2) Value: a talker's goal pays `Goals.worth(g, W) * (c - before)` with `c`
the reach chance times `(1 - pWin)` times `(1 - recruitHit)` times `(1 - felled)`. A loose unit
pays `W.death * (c - 1)` with the same `c` from the same helper (`sparedOf`), its reach chance
being 1 (nothing to reach: no one can Talk it yet), so `c = (1 - pWin)` times the same two blow
factors. Its gold is 0 here (a talker's worth is its items' gold plus `W.death`); the items of a
unit nobody can Talk are not read.

**The price is paid by the judge only.** The value term runs in the judged phase and the
lookahead (`goalTerm` with `rows`), never in a menu's or the beam's partial score. The rank orders
by what the game forbids (admitted, then forfeits), and its forfeit already counts the death; a
partial score that pre-pays it prunes the plan the rank would pick, as in #722. Replay: the term in
the beam cut the one admitted plan on turn 8 (it fells Marisa, 0.05 max death chance) and left plans
that let her kill a healer (0.82). The talker recruit's goal term still runs in the beam; that is
older than this change and is filed apart, not changed here.

**A win by the kill does not forfeit it.** Decided by the coordinator, 2026-11-22. A loose unit
whose death is the win (a Defeat-boss boss, a Rout's last red) would otherwise make every
winning plan forfeit `owed:<id>` while a hold forfeits 0, and with no ledger row GOAL_QUIET's
stall could never release it: the bot would hold for good. A talker recruit's row is released by
that stall; for a unit with no row the equivalent is that the plan whose kill ends the chapter
forfeits nothing, the win ending the chapter. A score's `fx.win = kill` (the boss) is set for a
loose boss because it keeps the red path.

**Why no ledger row.** A row nobody can take would stay feasible and hold the Seize for good, so
only the death counts; a win does not close `owed:<id>`.

**What it does not do.** No new weight and no change to any board without such a unit. A talker
whose row is not feasible (stalled, unknown, absent) gets no price, as before: such a row means
the goal is out of reach or deliberately released (Amelia on turn 10 in `fix730`: no talker can
reach her before her scripted removal), and pricing it would charge a recruit already lost. Once a
talker joins, the unit is an ordinary recruit and its row takes over.

**Owed means a Talk that recruits?** `ctx.owedRecruits` is every Talk-table target less the pairs
the table holds both ways with one script (`Sight.recruitTalks`). Searched the decomp on purpose
(`src/events/*eventinfo.h`, 65 `CHAR`/`CharacterEvent` entries against `*eventscript.h`): every
entry whose script has no `CUSA` (change to our side) is half of a both-ways pair with one script
(Ch8, 13b, 15a, 15b, 9b: conversations between our units) or a `CALL` script (Rennac, Syrene,
recruits), apart from Ch1's two both-ways Franz entries. No one-way talk that only gives dialogue
or an item has a red target, so no filter was added.

**Proof.** `test_bot.lua`. Fail on main (4): the counter that fells an owed recruit forfeits
`owed:129`; the plan whose counter spares it ranks above the one that fells it; our own blow that
fells it forfeits it; the plan played does not strike. Pass on purpose (2): no owed set (a red the
game does not owe is no recruit); with a talker (the `recruit:129` row alone). Added by the
review, each failing once its line is removed: a kill that ends the chapter forfeits nothing and is
played; equal forfeits order by the chance, a death's worth of it; a loose red keeps damage credit;
who is loose (a green, a fogged red and an unowed red are not; a talker recruit is not loose and
the march's alone); a counter that fells nothing forfeits nothing.

**Replay (`b640e-cs-s4008`, Ch10, one attempt each; the start was played by an older bot, so the
base is the recording).**

| Build | Result | Marisa |
|---|---|---|
| Recorded | won, 15 turns, 1 death | killed turn 8 by our blow |
| `fix730c` (loose also a recruit, price at the judge only) | won, 17 turns, 0 deaths | killed turn 8 |
| `fix730d` (loose a red, price in the beam) | lost, 14 turns, 5 deaths | none attacks her; she kills five |
| `fix730f` (`fix730d` with her marked a recruit) | won, 18 turns, 2 deaths | spared by a retreat, not admitted |
| `fix730g` (loose a red, price at the judge only) | won, 17 turns, 0 deaths | killed turn 8, the played plan admitted (0.045) |

Item 5 and 7 (the loose unit is a red to the march and the credit) are not the cause of `fix730d`'s
loss: `fix730g` keeps them. The beam's pre-paid price is, and the test pins it with BEAM and
PER_UNIT at 1.
