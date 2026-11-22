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
charId is owed and that no blue unit may Talk. They join `ctx.recruits` (so the planner's one
reader of a recruit's fall, `felled` and `recruitHit`, and fix 1's sparing waits see them) but get
no talkers and no goal. `Goals.forfeited` takes `closes.loose` and adds a forfeit `owed:<unit id>`
when the plan's chance to lose the unit passes `Goals.DUST`, so it ranks first, exactly as a
recruit with a talker's `recruit:<id>` does (`forfeits = #st.forfeited`). The judged value pays
`W.death` times that chance, the recruit goal's own worth less its gold, so plans that forfeit
alike still order by it.

**Why no ledger row.** A row nobody can take would stay feasible and, as a forfeit of every win,
hold the Seize for good. So only the death counts: a win does not close `owed:<id>`.

**What it does not do.** No new weight and no change to any board without such a unit: with nothing
owed, `loose` is empty and every plan scores as before. A recruit with a talker keeps its row and
is not counted twice. Once a talker joins, the unit is an ordinary recruit and its row takes over.

**Proof.** `test_bot.lua`, four checks that fail on main: the counter that fells an owed recruit
forfeits `owed:129` (on main nothing); the plan whose counter spares it ranks above the one that
fells it (on main they tie); our own blow that fells it forfeits it and the plan played does not
strike; with a talker it is the `recruit:129` row alone.

**Replay (`fix730c`, `b640e-cs-s4008` Ch10, one attempt).** Gerik is a green NPC until turn 9, so
Marisa has no blue talker. Recorded: won in 15 turns, Marisa killed on turn 8 by our blow. Replayed:
won in 17 turns, 0 deaths, Marisa killed again on turn 8 by our own attack (unit 6). Every plan
that spares her was inadmissible (a unit's death chance 0.84 over the cap), so the plan played is
the only admitted one; it now carries the forfeit (rank `forfeits` 1) and still wins the rank,
because admission outranks forfeits. The price works; here the board gave no safe way to pay it.
