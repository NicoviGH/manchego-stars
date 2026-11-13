---
id: 407
title: "A simulated enemy phase starts as the game's does"
date: "2026-11-13"
section: "Combat System"
issues: [510]
---

# A simulated enemy phase starts as the game's does

The bot reads an enemy phase during the player's by calling the game's own AI in a sandbox
(the turn order, then each unit's decision). It never ran what the game runs first:
`AiPhaseInit` (cp_phase.c). So a simulated decision read whatever the player phase had left
in `gAiState`, with `gPlaySt.faction` still the player's.

**Every simulated phase and every single strike now starts through `Sight.aiPhaseStart`**
(sight.lua): the faction red, `AiPhaseInit`'s field assignments written as they stand
(`flags`, `unk7E`, `orderState`, `cmd_result`, `specialItemFlags` from `gAiItemConfigTable`,
`unk84`), then its two calls, `UpdateAllPhaseHealingAIStatus` and `SetupUnitInventoryAIFlags`,
in the same call list as what the caller runs next (so no call of its own is added).
`AiPhaseInit` itself is not called: it starts the order proc, which would play the phase. A
decision that starts no phase refuses to run with the faction not red.

**What it was costing (confirmed, vanilla Ch9, campaign 4006, attempt 1, tags `phstart1`
against `phstart1ctl`, the same code with the phase start switched off).** In every read made
once all player units had acted, `gAiState.flags` held 4, `AI_FLAG_BERSERKED`. A berserked
unit runs no script (cp_decide.c), so the looting read's 104 decisions in that state were all
attacks, each on a red unit, and none took a village. With the phase start the flags read 1,
no looter attacks its own side, and the read finds 21 looting decisions against 14. That is
the "last read of each player phase" lead left open after the AI-bytes leak (#510 comment
6860128405). Why the game holds 4 there was read, not traced: `AiPhaseBerserkInit`
(cp_phase.c) is the only writer of that value, and bm.c starts its proc around the player
phase.

**What else the phase start decides, from the decomp (read by subagents, not measured on a
run):** the turn order and the staff AI read other units' heal flag, which a plan that wounds
an enemy left as it stood before the wound; with the faction the player's, the escape move
returns no point and the heal-staff gate counts the player's units (`GetCurrentPhase`);
`specialItemFlags` gates the AI's door key, lockpick and antitoxin, and on turn 1 held
whatever the save had.

## Three things done so the phase start costs nothing

Each was measured: main and the branch back to back, `PT_LEAKGUARD=1`, suite runs
`scout-ch6/1001`, `vanilla-ch5/1001` and `scout-ch14/1001` on three workers. Every version
below plays main's acts on all three (the same act hashes) and reports no leak.

| | Ch5 frames | Ch5 CPU s | Ch14 CPU s | wall |
|---|---|---|---|---|
| main (`d24e89c3a001`) | 166,458 | 72.4 | 46.2 | 1m18.0 |
| the heal flags read before every decision (`47007dec`) | 171,743 | 75.6 | 48.2 | 1m21.3 |
| the two calls on every strike (`9fc6f804`) | 169,527 | 74.5 | 47.8 | 1m21.2 |
| as merged (`c3fe6ffd`) | 166,271 | 72.6 | 47.2 | 1m18.3 |

The ids are the records' instruments in the vanilla store's `runs.jsonl`. The last row was
timed at a load average of 7.5 to 9.6, the others at 4.5 to 6; the same calls at the lower
load (`b51a9976`, before the start was keyed) took 72.1 and 46.1. Frames are the emulated
work and do not move with load.

1. **The heal flags are read again only when an enemy's HP was written** inside the phase
   (`Sight.decisionCalls`, `healStale`). The game reads them after every act (cp_perform.c
   `CpPerform_Cleanup`); a simulated phase changes an enemy's HP in two places (the counter's
   expected damage on a striker, and a struck target that is red, which takes a berserked
   striker), and both go through one function that marks the flags stale. Read before every
   decision it was 36,166 calls in the Ch5 attempt and changed nothing where no HP had: the
   flag is HP against two thresholds, the exit one never under the enter one
   (`gAI3HealingThresholdTable`), and nothing else writes it.
2. **A single strike's phase start is read once for the board it is asked on.** A strike
   stands one unit elsewhere and changes its first weapon; neither call reads where a unit
   stands or the order of its bag. So the first strike makes the two calls and what they
   left (`bestBlueMov`, every unit's `aiFlags`) is kept (`Sight.phaseStarted`) and written
   back for the later ones, by every unit's HP and state word (`Sight.phaseKey`): a strike
   asked on a board staged otherwise makes its own. Not written back: a player unit's
   `ai_counter` and the scratch maps the call fills. No decision was seen to read them
   (the same acts with the calls on every strike and with them once, on the three runs and
   on Ch9), and no reader of `ai_counter` on a unit other than the one deciding exists in
   the decomp; that no AI path reads a stale scratch map was not traced.
3. **The played-exchange memo leaves `aiFlags` and `ai_counter` out of its key**
   (`Sight.battleWord`). The phase start rewrites both on a unit and no battle code reads
   either (`aiFlags` is read in the AI's files, eventscr3.c and bmsave.c; `ai_counter` by the
   AI on the unit deciding and by bmsave.c). In the key, `ai_counter` made one exchange a new
   one wherever the unit stood: Ch6 seed 1001 played 1,949 simulations for the 1,496 it
   needs, the same 434 decisions (confirmed by undoing that one byte). `aiFlags` is left out
   for the same reason; its cost was not measured.

## What is handed back, and what is not

When the sandbox returns, the writes made here, `bestBlueMov` and the units' `aiFlags` and
`ai_counter` are put back (journaled, or kept by `Sight.keepAi`). The scratch maps
`SetupUnitInventoryAIFlags` fills for each player unit are not, as no game call's map writes
are: what follows a phase start is an enemy's decision, which makes its maps anew.

**The looting read's phase start sees no player unit.** That read hides the player's units
from the AI (when does a tile fall undefended), and `SetupUnitInventoryAIFlags` skips a hidden
unit, so there `bestBlueMov` is 0 and no tile is kept from a looter for a faster player unit
(cp_utility.c `AiTryMoveTowards`). Before, it was the last real enemy phase's value. Read off
the decomp; its effect on a closing turn is not measured.

## The Ch9 attempt

Campaign 4006, Ch9, attempt 1 is a loss on turn 10 without the phase start (`phstart1ctl`,
and main's `keepai10g`) and a win in 19 turns with no death with it (`phstart1`; the same acts
as merged, `phstart3`, leak guard on). One game is a lead, not a verdict, and the village at
(11,15) and the recruit (charId 18) are still missed. The frozen suite was not run (AGENTS.md:
never for a PR).
