---
id: 439
title: "Holding still is not a plan once the bot stalls"
date: "2026-11-21"
section: "Combat System"
issues: [699, 510]
---

# Holding still is not a plan once the bot stalls

**Decided (#699 step 3b), #510 step 9.** Extends ADR 0384 (the risk cap and the plan rank) and
ADR 0403 (the stall readings).

**The fault.** A plan under the style's risk cap is `admitted`, and `M.outranks` ranks every
admitted plan above every other. An all-hold plan risks nothing, so it is always admitted. When
every plan that attacks is over the cap, holding wins, turn after turn, until botrun's `stuck`
abort (`quiet >= M.QUIET_BOUND`, 16 player phases). Ch21: every plan that attacks Lyon is over the
cap. Ch15: in 66 of 117 stuck runs every attack plan was over the cap, and holding won.

**Nicolas's call (2026-11-21).** "Staying still is not actively advancing the level at all and
should not be a viable choice", unless the player is baiting enemies into counters.

**The rule.** `botrun`'s `memo()` passes the planner `idle = quiet >= M.GOAL_QUIET`: the `quiet`
the abort reads, and the threshold the ledger's stall rule already uses (ADR 0403). No new weight.
Under `opts.idle`, a plan ADVANCES when it does any of these:

- kills a red unit with a chance above `DUST`: by our blows, or by our counters in the judged
  enemy phase (a bait counts, which is the baiting exception);
- takes a goal: a visit, chest, talk or rescue (a convoy use is no goal);
- raises the chance of the win, or wounds a unit the win needs: the boss of a Defeat-boss
  chapter, any red of a Rout.

A plan that only moves units nearer a goal does not advance (nearing is what `GOAL_QUIET` found
idle), and neither does a blow that deals nothing (Ch15: 29 runs chipped Caellach for 0 damage).
A plan that does not advance is not admitted, whatever its risk. Its rank carries `idle = 1`
(0 when it advances), placed in the non-admitted lead order of `M.outranks` right after
`first_game_over`: a plan that risks ending the game still ranks last, below a hold, and an idle
hold ranks below every other plan. The least-risk advancing plan is then played through the
existing fallback (`FALLBACK_SACRIFICE`), and `considered` rejects the idle plans as "idle".

**What does not change.** Without `opts.idle`, nothing. With it and no plan that advances (the
board offers nothing to advance), `idle` is left off every rank, so the hold is played as before
and no fallback is flagged. `pick()` makes that call over the plans that may be played and
re-admits every plan judged when it moves, so `M.rebase` and the lookahead's finalists compare
ranks read alike.
