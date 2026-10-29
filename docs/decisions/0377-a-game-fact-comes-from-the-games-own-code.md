---
id: 377
title: "A game fact comes from the game's own code; re-deriving one needs a written reason"
date: "2026-10-29"
section: "Engine & Tech Stack"
issues: [510]
---

# A game fact comes from the game's own code; re-deriving one needs a written reason

**Every fact about what FE8 does or did (who can attack, how hard a blow lands, who is in the
party, what a dropped item does, who may Talk) is the game's own answer: its function run in
sight.lua's sandbox (ADR 0369), or its own record read from memory** (Nicolas, 2026-10-29: "what
good reason would there be to ever rederive code when we have the original game's source code?
knowing its a risk of simply getting it wrong or 'approximately' like the game"). This widens
ADR 0369 from the enemy's decision to every game fact the bot and its judge read. Player choices
(which target, how much risk, the team groups table ruled on 2026-10-27) are ours by nature and
are not covered.

**A re-derivation is allowed only with one of three reasons, written in the code beside it:**
1. **The game has no function for the question** ("is every reward taken"). Then compose the
   answer from the game's own answers (its flags, its battle, its calls), never from a model of
   them.
2. **A MEASURED cost.** Then cache the game's answer; never approximate it.
3. **No emulator in the process** (Python tools: the env builder, the wiki). Then read the
   decomp's DATA (tables, scripts); never re-implement its LOGIC.
"The read was already at hand" is not a reason.

**Why, in evidence:** the 2026-10-29 audit (#510 comment 6504714008) found 21 re-derivations,
several wrong in play: "joined" as "blue and not dead" missed the game's `IsUnitInCurrentRoster`
and counted a Joshua Ch5's ending had left blue AND dead as recruited (ADR 0376); hit damage as
`attack - defense` skips `BattleGenerateHitAttributes`'s Sure Shot, Great Shield, Pierce,
Silencer and damage cap; `bot.lua` priced kills with the displayed hit where FE8 rolls two
numbers (`Roll2RN`); green deaths in the enemy phase were never watched.

**Hit odds are the game's own rolls.** The planner's odds come from the game running its own
`BattleGenerateHitAttributes` in the sandbox, each roll's threshold caught at `BattleRoll1RN` /
`BattleRoll2RN` (Nicolas: "why wouldnt we?"); the cost is measured and the answer cached by unit
state.

**Claims carry their source.** Any statement about what the game does is tagged **[code]** (a
decomp file:line read in full, not a function's name or a partial read) or **[ROM]** (a value
read from a run); anything else is labelled an inference. (2026-10-29: "Ch5's ending makes Joshua
join" was claimed from `EventScr_StrictLoadUniqueAlly`'s name and first half; the routine's end
sets him dead.)

**Built, 2026-10-29 (audit findings 1-4, 20's wall, 21).** Each exchange is played by the game
every way its rolls can go (`sight.lua` `M.played`): `BattleGenerateSimulation` is run again and
again, every `BattleRoll1RN`/`BattleRoll2RN` caught at its entry with a breakpoint and its
`simResult` (r1, which a simulation returns in place of rolling) forced, depth first [code
`bmbattle.c:253-265`]. A roll's odds count every 16-bit `NextRN` through `NextRN_100` [code
`rng.c`] (the game has no function for them: reason 1). What the bot and the planner read is the
outcome distribution: kill, death, the worst counter, the expected damage; the window's hit,
damage and crit are kept for the logs only. Retired with it: the displayed-hit kill chance, both
copies of the x3 crit, `killsTarget = dmg x hits >= HP`, the "first-blow sure kill takes no
counter" rule (the game's play already stops the counter), a wall's `dmg x hits` (now the
simulation's own HP lost), and the planner's `plan.branch` (the judged phase reads the counter's
played chance to kill the striker).
- **Headless mGBA needs a patch for this.** Its frontend attaches a debugger only for `-d`/`-g`,
  and without one `emu:setBreakpoint` returns -1 [ROM]. `tools/mgba-headless-script-debugger.patch`
  (applied by `tools/build_mgba_headless.sh`) attaches one whenever a script runs, never entered:
  mGBA runs at full speed and single-steps only while a breakpoint is set, which `played` does
  only for its own calls.
- **Cost, measured on the Manchego Stars ch01 bot run (won, nobody lost, each time) [ROM]:** 827
  simulations and 10.5 CPU s before; 7,266 and 17.4 played uncached; 2,116 and 12.0 with the
  played outcomes cached by the two battle units as the simulation set them up (every byte but
  their map position) and `gBattleStats`' config and range (reason 2).
- A petrifying blow ends the battle like a death [code `bmbattle.c:1201`]; the bot counts a
  petrified unit as every HP lost. That is our pricing, not the game's, and is written beside it.

**Amended 2026-10-29 (audit findings 5-7, 13-16).** More facts the bot now takes from the game's
code, each proved in the ROM:
- **A drop** (5, 6): `NewPopup_GeneralItemGot`, whose only caller is `BATTLE_HandleItemDrop`,
  caught at its entry (r0 the receiver, r1 the item), the breakpoint armed only while
  `sProcScr_CombatAction` is live with a `US_DROP_ITEM` unit in the battle. A thief's chest is won
  back when that drop names the thief and the chest's item. 7 drops caught on Manchego Stars ch01
  with every red made a dropper (a probe, not committed): 14.1 CPU s, every battle armed.
- **Owed recruits** (7): the chapter's talk table, walked by the game (ADR 0376).
- **The enemy's decision** (13): `AiDecideMain` after the decide loop's whole per-unit step
  (ADR 0369, amended).
- **A key** (15): the item alone in the unit's bag, `GetUnitKeyItemSlotForTerrain` asked for a
  door and a chest; a Lockpick is a key only to a thief [ROM]. The passive items stay a list: the
  engine tests each by id in scattered places, with no one function (reason 1).
- **A door's reach** (16): the Door command's own check, `DoorCommandUsability` and the closed
  doors its target list names, from each wait tile; Manchego Stars ch03's chest behind the door
  at 6,12 opened, clean, 173 checks, 20.7 CPU s.
- **Green deaths** (14) are watched in the enemy phase like blue ones.

