---
id: 486
title: "A Lockpick thief's chest is read closed: the forecast reads the AI's use-item act"
date: "2026-11-27"
section: "Combat System"
issues: [764, 510]
---

# A Lockpick thief's chest is read closed: the forecast reads the AI's use-item act

**Decided (2026-11-27, #764 fix order item 1: Ch16's east thief).** The closings forecast
(`sight.closings`, its replay of the enemy phases) closes a chest when the AI's decision is a
use-item act (`Board.AI_ACTION_USEITEM`, 6) made with a Lockpick on that open chest's own tile
(`Sight.picksChest`), as well as for a pillage (4) and a Rogue's pick (13).

**Why.** A thief opens a chest with its Lockpick through the special-item step.
`AiScriptCmd_10_DoLooting` (`cp_script.c`) runs `AiTryDoSpecialItems` before the pillage search.
`AiSpecialItemLockpick` (`cpextra_80407F0.c`) is the one special item that targets chests
(`sAiSpecialItemFuncLut`), and it decides `UNIT_ACTION_STEAL` (0x06, the same value as
`AI_ACTION_USEITEM`) on the chest's tile. The replay acted only on a pillage, so every Lockpick
thief's chest read as never closed. A Chest Key goes through the pillage search and was already
read. Instrumented replay `d785a` (Ch16 s4005, a temporary closings log): thief 129 was listed as
a looter on turns 12 and 13. It decided action 6 on (20,3) in every replayed phase, and the
forecast closed nothing. Readers of `k711a` had refuted the other causes: its AI (ai2 5,
`AiScr_AiB_PillageThenEscape`), fog (none), and absence from the board. No chest row of `k711a`'s
attempt 1 had `closes_on`.

**Proof.** `test_sight.lua` "picksChest:" (5 checks), plus a source pin that closings calls it.
With `sight.lua`/`board.lua` reverted, both fail. One replay, `p786a` (Ch16 s4005, main plus this
change), against main's `k711a`:

| Attempt | Run | Turns | Deaths | Chests the forecast reads closing (plan rows) | Not clean for |
|---|---|---|---|---|---|
| 1 | k711a | 21 | 0 | none | the east thief looted (20,5); (3,12) never offered |
| 1 | p786a | 17 | 0 | (20,1) 3, (20,3) 3, (20,5) 3 | (20,1) and (20,3) skipped |
| 2 | k711a | 27 | 0 | (20,5) 14 (source untested: likely the closer attempt 1 remembered) | the Knight Crest stolen from Marisa, turn 14 |
| 2 | p786a | 15 | 0 | (20,1) 1, (20,3) 1, (20,5) 7 | (3,12) taken by the west thief |

In both tries the east thief looted no chest. Why neither try is clean is on #764.
