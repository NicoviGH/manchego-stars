---
id: 382
title: "The planner pays what the clean clear counts (a recruit's death, a lord's as the chapter), plays our uncertain kills both ways, and the guide's line plays Joshua"
date: "2026-10-30"
section: "Combat System"
issues: [510]
---

# The planner pays what the clean clear counts (a recruit's death, a lord's as the chapter), plays our uncertain kills both ways, and the guide's line plays Joshua

**Decided (2026-10-30), #510 step 9, the planner's open item "vanilla Ch5's recruit 0x20".**
ADR 0381's march goal did not recruit Joshua. One instrumented run each found why, in layers:

1. **A red recruit's death was free.** Natasha marched, but Joshua charged in on enemy phase 2,
   Seth's counter took him to 9 HP, and on enemy phase 3 it killed him. The judge had the
   phase's own `felled` chance for that strike and paid nothing for it. Now a recruit (a
   non-blue unit one of ours able to act may Talk over, by the game's `CheckForCharacterEvents`:
   `recruitsOf` in bot.lua, the one owner) is paid at `W.death`: our attack's kill chance on
   it (and its damage earns nothing), and our counter's `felled` on its strikes. The mend tries
   the struck units' other acts. Its price against one of ours is Nicolas's: "early recruits
   are key members, later ones are replacements for losses. But that's subjective" -- so it
   stays `W.death`, ADR 0381's price for a green unit.
2. **A Talk left the recruit striking in the judged phase.** `score` set no `gone` for a
   Talk, so the sandbox's enemy phase still had the recruit red. A Talk now takes it off the
   enemy side, as a kill does.
3. **A lord's death was one unit's.** With (1), the turn 5 plan accepted Eirika at 0.76 to
   spare Joshua at 0.97, and the chapter was lost. The game ends on `EVFLAG_GAMEOVER` (0x65):
   a dying unit's defeat-talk entry (`GetDefeatTalkEntry`, quote text or none) names the flag
   its death sets, `SetPidDefeatedFlag` sets it (never 0x65 for the chapter's protected unit on
   a non-story map), and `RunWaitEvents` starts the game over when it is set [code]. sight runs
   that step in the sandbox per unit at the start and reads the flag back
   (`sight.objective.gameOver`; vanilla Ch5: Eirika alone [ROM]); the planner pays such a
   death at `W.win`. Nicolas: a game rule, not a design question.
4. **An uncertain kill was played one way.** Eirika's attack then killed an enemy the plan's
   average kept standing (kill < 0.5), and Joshua's AI turned on her. The judge now plays the
   enemy phase both ways for the plan's `M.BRANCH` = 2 most uncertain kills (nearest 0.5),
   each way weighted by its chance, a survivor at its HP given that it lives. `BRANCH` is a
   cost cap (2^BRANCH enemy phases per judged plan), not a weight.
5. **The guide's strategy, as claims.** The wiki's line ("kill any nearby mobile enemies while
   staying away from Joshua, then simply have Natasha walk up to him") was curated as
   `unmodelled`. It is now two claims: `recruit` Joshua `by` Natasha, and `avoid` the
   Myrmidon (the map's only one) for everyone else. The ROM is USA (`BE8E`, the decomp's
   SHA-1), where the wiki says Joshua does not strike Natasha (not checked in the ROM: the
   enemy phase is the game's own AI either way). A claimed recruit is played first: while it is on the field, its `by`'s menu is the
   Talk, the march on it and the retreat toward it (Natasha healed and held for five turns
   before). An `avoid` claim gives way on a stalled board, where the planner already takes the
   least it must (attempt 7: Natasha dead, every unit kept out of Joshua's reach between them
   and the boss, the board repeating until `stuck`).

**Measured in the ROM** (vanilla, seed 1, the `e1-vanilla-ch3` starts; CPU s):

| Run | Before | After |
|---|---|---|
| Ch5, attempts until clean | attempt 1 won t6 unclean (Joshua killed); no clean clear known | **clean at attempt 9** (even, `avoid`): Joshua recruited, none lost, every village. Joshua joined in 6 of 9 attempts; attempts 5 and 8 lost no one but left a village |
| Ch5 attempt 7 | `stuck` t22 | won t21 (Natasha, Vanessa, Lute lost) |
| Ch2 | clean at attempt 2 (11.1) | clean at attempt 1 (9.8) |
| Ch3 | clean at attempt 1 (15.0) | clean at attempt 1 (16.6), Colm recruited |
| Ch4 | clean at attempt 1 (19.0) | clean at attempt 1 (25.9) |
| Manchego Stars ch01 (New Game) | clean at attempt 1 (8.2) | clean at attempt 1 (9.0) |

The kill branch costs about 30% a turn (Ch5 attempt 1: 2.35 s a turn before, 3.0 s after;
Ch4 +36%).
