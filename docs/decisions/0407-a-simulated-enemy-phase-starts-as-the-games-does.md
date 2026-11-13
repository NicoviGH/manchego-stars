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
`unk84`), then its two calls, `UpdateAllPhaseHealingAIStatus` and `SetupUnitInventoryAIFlags`.
`AiPhaseInit` itself is not called: it starts the order proc, which would play the phase.
Each later decision of a phase leads with `UpdateAllPhaseHealingAIStatus`, as the game runs it
after every act (cp_perform.c `CpPerform_Cleanup`). All of it is put back when the sandbox
returns (the writes are journaled, the unit bytes kept by `Sight.keepAi`). The setup's calls
ride in call lists that already ran (a list is now six calls at most), so no call is added.

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

**What else the phase start decides, from the decomp (read by a subagent, not measured on a
run):** the turn order and the staff AI read other units' heal flag, which a plan that wounds
an enemy left as it stood before the wound; with the faction the player's, the escape move
returns no point and the heal-staff gate counts the player's units; `specialItemFlags` gates
the AI's door key, lockpick and antitoxin, and on turn 1 held whatever the save had.

**The played-exchange memo leaves `ai_counter` out of its key** (`Sight.battleWord`). The
setup writes each player unit's allies within 8 tiles there; no battle code reads it (only
the AI, on the unit deciding), and in the key it made one exchange a new one wherever the
unit stood: vanilla Ch6 seed 1001 played 1,949 simulations for the 1,496 it needs, the same
434 decisions (confirmed by undoing that one byte).

**Runs (2026-11-13, `PT_LEAKGUARD=1`, main and the branch back to back).** No leak. Suite runs
`scout-ch6/1001` and `vanilla-ch5/1001` play main's acts (the same act hashes): lost on turn
2, and won on turn 11 with three deaths. Ch5: 28,196 simulations and 72.9 CPU s against
main's 28,387 and 73.1; Ch6: 1,496 and 5.6 against 1,496 and 5.4. Ch9 4006 attempt 1 is a
loss on turn 10 without the phase start and a win in 19 turns with no death with it; one
game is a lead, not a verdict, and the village and the recruit are still missed. The frozen
suite was not run (AGENTS.md: never for a PR).
