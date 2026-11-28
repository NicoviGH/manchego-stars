---
id: 485
title: "A hand-off moves a key only to a unit it opens for, and its giver opens no chest after it"
date: "2026-11-27"
section: "Combat System"
issues: [764, 688, 510]
---

# A hand-off moves a key only to a unit it opens for, and its giver opens no chest after it

**Decided (2026-11-27, #764 fix order item 1, follow-up to ADR 0483).** A theft's hand-off by
Trade (`Bot.handoffs`) is offered to a teammate only when, for every lock kind (doors, chests)
the item opens for its holder, it opens that kind for the teammate too. The read is the game's
own key check, run as each unit (`sight.keyOpens` over `opensWith`/`M.keyItemOpens`). Any Trade
that hands away the holder's last chest opener is marked `spends` (`tradeAct`). The planner's
judged phase then reads that holder as keeping no opener (`Planner.opensAfterTrades`, in act
order: `st.opens[holder] = 0`), so its march to a chest is no progress and its chests' chance is
0 after the Trade. Only the copy traded is skipped, so a second Lockpick still opens. A later
Trade of the same plan that gives the opener back (`restores`) undoes the zero.

**Limits.** Chests only. The per-plan opener read is a chest march's. A door's way is read on
the live bags (`sight.locked`), which no plan's Trade moves. A taker is never made a new chest
taker, because the goals' takers are fixed when the decision starts. That was true before this
change too.

**Why.** Vanilla Ch16 s4005, replay `k711a` attempt 1, turn 8: the west thief would steal
Colm's Lockpick, and the hand-off traded it to Eirika, a Lord. A Lockpick opens a lock only for
a class with CA_STEAL (`AiGetChestUnlockItemSlot`, `cp_utility.c`). The Trade won on progress
alone. The planner still counted Colm's walk to (3,12) as an opener's, because `st.opens` was set
only for a unit a thief robs (trace: chest 3,12's worth 0.666 before and after; both plans had
0 forfeits). On turn 10 the Lockpick went on to Moulder, a Priest. (3,12) was never offered
again, and the try was not clean.

**Proof.** Unit tests (`test_bot.lua` "hand-off: a key goes to no unit it opens nothing for", "…
spends it", "… opens no chest after it"). With the `bot.lua` change reverted, the first two
fail. With the `planner.lua` line reverted, the third fails. "Hand-off: a holder with a second
Lockpick keeps an opener" fails on the first version of `spendsOpener`. One replay, `h785a`
(Ch16 s4005), against main's `k711a`:

| Attempt | Run | Turns | Deaths | Result |
|---|---|---|---|---|
| 1 | k711a (main) | 21 | 0 | not clean: (20,5) looted, (3,12) never offered |
| 1 | h785a | 19 | 0 | clean |

In `h785a` no Trade was made. The west thief opened (3,12), and its kill gave the loot back.
Eirika opened (20,5) on turn 12, before the east thief reached it. One start, one try: the R6
set judges the batch.
