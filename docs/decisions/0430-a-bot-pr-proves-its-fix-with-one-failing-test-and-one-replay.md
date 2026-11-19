---
id: 430
title: "A bot PR proves its fix with one failing test and one replay; games are played per batch of fixes"
date: "2026-11-19"
section: "Working Conventions (Definition of Done)"
issues: [640, 510]
---
# A bot PR proves its fix with one failing test and one replay; games are played per batch of fixes

**Decided 2026-11-19 (Nicolas: "agreed").** It narrows the "Run the proof a change needs" and
"Never make tests slower" standing rules (AGENTS.md) for #510's bot work.

**Why.** A bot PR's time went to emulator games, not tests. Measured over the last 30 CI runs, a
PR's CI took about 4 minutes, and all the Lua unit tests take 0.4 s. PR #659 (#655) also played
12 Ch8 games on main and 12 on its branch, 4 `suite --only` games on each side, replays, and
back-to-back timings. Playing, waiting on and reading those runs was most of the PR's day, and
each game measured one fix alone when the next fix was already known.

**The rules.**
1. **A bot PR's proof** is a unit test that fails on the code without the fix, plus one replay
   of the game that showed the problem. A batch of games on main and on the branch, or extra
   `--only` suite games, only when the change moves how every plan is scored (the judge, the
   rank, a weight every plan pays).
2. **Timings** only when the change adds work to every turn's planning (a new search, a new
   sandbox or simulated phase) or touches tests or CI. A rule change is not timed.
3. **Fixes land back to back.** Games are played when a batch of fixes has a real chance of a
   better result: one lap, or one `attempts` set, over the batch.

**Unchanged.** The frozen suite still runs only before the bot's reading is relied on (AGENTS.md);
`/code-review`, its fixes and CI on the head commit still gate every merge. An open question
stays open until it is answered; nothing is parked for lack of movement.
