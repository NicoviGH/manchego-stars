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
