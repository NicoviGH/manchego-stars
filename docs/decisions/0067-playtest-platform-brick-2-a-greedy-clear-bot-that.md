---
id: 67
title: "Playtest platform brick 2 = a greedy CLEAR-BOT that proves completability with real combat (#60)."
date: "2026-06-19"
section: "Combat System"
issues: [60]
---

# Playtest platform brick 2 = a greedy CLEAR-BOT that proves completability with real combat (#60).

The smoke net proves a chapter doesn't crash/soft-lock; the clear-bot proves it can be *won* — and is the
rule-based precursor to the LLM-player (swap the policy later). `scenarios.clear` actually plays the chapter
(no `pokeFrail` cheat like `scenarios.win`): each player phase it marches every unit at the boss and attacks
with real combat, rides out enemy phases, and wins when the chapter advances (FAIL on game-over or a turn
budget). **Boss detection is generic** — a red unit whose `CharacterData.attributes` (`pCharacterData` at
Unit `+0x00`, attributes `+0x28`) has `CA_BOSS = (1 << 15)` (`include/bmunit.h:326`) — no hardcoded char ids
(verified: finds Sephek `0x68` on the prologue). The target choice is a **pure** function
(`clearbot.lua` `pickTarget(reachable, enemies, prefs)`: melee-range, boss-first then lowest-HP), unit-tested
without an emulator (`test_clearbot.lua`, in `make test`) — driving stays in the scenario. **Both win
objectives are handled generically by one `clearDrive` loop**: kill the boss, and if the chapter hasn't
already advanced (DefeatBoss), send a unit onto the boss's old tile to **Seize** (the seize tile = the dead
boss's tile; a non-seizer just Waits, so the loop tries the next unit) — win = chapter advances OR the title
screen (ch01's ch02 isn't hosted). A naive greedy melee strategy cleared **both the prologue (DefeatBoss) and
ch01 (Seize, real combat through a 10-goblin escort) in 3 turns each** with no `pokeFrail` and no game-over —
no gang-up/heal/don't-feed-the-lord logic needed yet (harder chapters may). ch02+ (save-state checkpoints) is
the remaining follow-up (#60).
_Decided: 2026-06-19 (CLAUDE; pipeline track. pickTarget TDD; scenarios.clear + clear_ch01 + clearprobe verified on a built ROM)_
