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
   stays `W.death`, ADR 0381's price for a green unit. Every blue counts as a talker, one that
   has acted this turn too (it Talks next turn), so a replan after its move keeps the recruit.
2. **A Talk left the recruit striking in the judged phase.** `score` set no `gone` for a
   Talk, so the sandbox's enemy phase still had the recruit red. A Talk now takes it off the
   enemy side, as a kill does.
3. **A lord's death was one unit's.** With (1), the turn 5 plan accepted Eirika at 0.76 to
   spare Joshua at 0.97, and the chapter was lost. The game ends on `EVFLAG_GAMEOVER` (0x65):
   a dying unit's defeat-talk entry (`GetDefeatTalkEntry`, quote text or none) names the flag
   its death sets, `SetPidDefeatedFlag` sets it (never 0x65 for the chapter's protected unit on
   a non-story map), and `RunWaitEvents` starts the game over when it is set [code]. sight runs
   that step for every unit on the field, any side (an escort's death can end the game too),
   in one sandbox at the start: it reads the flag back, then clears the unit's flag with the
   game's `ClearFlag` before the next (`sight.objective.gameOver`; vanilla Ch5: Eirika alone
   [ROM]). The planner pays such a death at `W.win`, every death through one `loss()`.
   Nicolas: a game rule, not a design question.
4. **An uncertain kill was played one way.** Eirika's attack then killed an enemy the plan's
   average kept standing (kill < 0.5), and Joshua's AI turned on her. The judge now plays the
   enemy phase both ways for the plan's `M.BRANCH` = 2 most uncertain kills (nearest 0.5),
   each way weighted by its chance, a survivor at its HP given that it lives. A target's
   chance is all the plan's blows on it composed at its own HP: read one blow at a time, each
   at the HP the earlier ones leave on average, two 50% blows of 10 on 20 HP were no kill at
   all; composed, a quarter. `BRANCH` is a cost cap (2^BRANCH enemy phases per judged plan),
   not a weight, and it has no floor: at `W.win`, a 3% chance of a lord's death costs three
   units' deaths.
5. **The guide's strategy, as claims.** The wiki's line ("kill any nearby mobile enemies while
   staying away from Joshua, then simply have Natasha walk up to him") was curated as
   `unmodelled`. It is now two claims: `recruit` Joshua `by` Natasha, and `avoid` the
   Myrmidon (the map's only one) for everyone else. The ROM is USA (`BE8E`, the decomp's
   SHA-1), where the wiki says Joshua does not strike Natasha (not checked in the ROM: the
   enemy phase is the game's own AI either way). [Retired 2026-10-30, see the amendment
   below: A claimed recruit is played first: the talker `exploring` sends to it (one with a
   way to it) has only Talks, the march on it and the retreat toward it on its menu (Natasha
   healed and held for five turns before).] An
   `avoid` claim gives way on a stalled board, for the one plan that must change it (botrun
   clears `stalled` after its first act), where the planner already takes the least it must
   and still pays any death the move risks (attempt 7: Natasha dead, every unit kept out of
   Joshua's reach between them and the boss, the board repeating until `stuck`).

**Measured in the ROM** (vanilla, seed 1, the `e1-vanilla-ch3` starts; CPU s), after the
review fixes (#552; the last set five runs at once):

| Run | Before | After |
|---|---|---|
| Ch5, attempts until clean | Joshua killed or never reached; no clean clear | **clean at attempt 9** (even, `avoid`): Joshua recruited, none lost, every village. Joshua joined in 6 of 9 attempts |
| Ch5 attempt 7 | `stuck` t22 | won t21 (Natasha, Vanessa, Lute lost) |
| Ch2 | clean at attempt 2 (11.1) | clean at attempt 1 (9.7-11.2) |
| Ch3 | clean at attempt 1 (15.0) | clean at attempt 1 (16.1-18.3), Colm recruited |
| Ch4 | clean at attempt 1 (19.0) | clean at attempt 1 (21.2-28.2) |
| Manchego Stars ch01 (New Game) | clean at attempt 1 (8.2) | clean at attempt 1 (9.0-10.2) |

**Still open: the village at (5,1).** Attempts 5 and 8 lose no one and recruit Joshua but
miss it: won past ("unreached", 8) or pillaged first ("closed", 5); attempts 3 and 6 pass it
up ("skipped"). The planner takes the win while a reward is still open; part A recorded the
same village on its Ch5 runs. One clean style of nine is the measure until that is closed.

The kill branch costs about 30% a turn (Ch5 attempt 1: 2.35 s a turn before, 3.0 s after).

**Amended 2026-10-30 (#510; Nicolas: retire it).** The talker's duty in (5) is retired. A
claimed recruit still sends its talker to it (`exploring`: the march on it), but the talker
keeps its whole menu, heal and hold tiles included. The duty was set before anything priced
the recruit; since ADR 0383, the recruit's goal worth pulls the talker there, and the planner
prices the turn a hold costs against the death a march risks. The cut menu left that trade
unjudged: in vanilla Ch5 attempt 2, all ten judged plans walked Natasha into a 0.56 chance to
die on turn 3, because no plan holding her back existed to judge. Measured on the same envs,
seed 1 (vanilla Ch5 attempts 1-9, with the duty against without): clean clears 1 against 2,
Joshua recruited 5 against 8, deaths 12 against 9, Natasha killed 5 against 0 (turn 3 in
attempts 2, 4, 5 and 8, turn 5 in 6), stuck 1 against 0. CPU is higher in all, 280 s against
297 s (235 s against 264 s without attempt 5), because the runs play more turns: 64 against 75
in the other eight. A turn and a plan cost less: 3.67 s a turn against 3.52, 1.61 s a plan
against 1.47 (attempt 5 left out, whose 43 cheap stalled turns, 1.06 s each, would make the
duty look cheaper per turn). Vanilla Ch2's Talk recruits are frame-identical.
