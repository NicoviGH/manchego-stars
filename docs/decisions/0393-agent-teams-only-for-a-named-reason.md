---
id: 393
title: "Agent teams: only for a named reason, one writer per slice, seams agreed first, models by judgement"
date: "2026-11-07"
section: "Working Conventions (Definition of Done)"
issues: [577, 510]
---

# Agent teams: only for a named reason, one writer per slice, seams agreed first, models by judgement

#510 PR-F (PR #576) was the first PR built by an agent team: a lead, three builders on
disjoint file slices, and a fresh reviewer, all on Opus. It shipped (19 review findings plus 4
from the re-review, all fixed), but subagents were 86% of a $35.99 session and spent the 5-hour
limit. Each agent was woken back up 2 to 8 times, at 100k-330k of context each time. The retro
checked what went wrong against current published practice (Anthropic's multi-agent research
system and harness posts, Claude Code's agent-teams, sub-agents, costs and prompt-caching docs,
and Cognition's 2025 and 2026 multi-agent posts). It is the cost half of the 2026-10-26 call
behind inline implementation (100-200k subagent tokens per task under subagent-driven
development), now measured for teams.

## The rules

1. **One agent is the default.** A team needs a named reason: the work splits into pieces that
   share no files and need no result from each other, it cannot fit one context window, or it
   needs an independent reviewer (always: the author is never the reviewer). Sequential work, or
   work with many dependencies between pieces, stays with one agent. Claude Code's docs put a
   team at about 7x the tokens of a normal session when teammates plan first; Anthropic puts
   multi-agent at about 15x chat tokens, against about 4x for one agent.
2. **One writer per file slice.** Every file has one owning agent; a file nobody owns is named
   before work starts (PR-F's `matrix.py` was nobody's and failed the drift check late).
3. **Seams are agreed in a shared file before coding.** Each interface between slices states
   what done looks like and how it is tested (Anthropic's "sprint contracts"), and the lead
   reviews them before any builder starts. PR-F's Important findings were nearly all at the
   seams: a forced plan's `broken` against the witness rule, the offered acts read on the wrong
   board, a full-information plan played on the fogged game, a run's identity spelled twice.
4. **Models follow the judgement load.** Opus for the lead, for a slice that holds a design
   call, and for the reviewer. Sonnet for a well-specified builder. Sonnet or Haiku for a batch
   of live runs that only runs commands and reports. The lead makes nits and one-line fixes
   itself. Cognition found that handing judgement to the cheaper model backfires, and that
   mechanical work saved 25-62% per task. An agent's model is never changed mid-task, because
   that rebuilds its whole cache.
5. **A fresh agent with a short brief beats waking an old one.** Each wake-up re-reads the
   agent's whole conversation. Agent definitions cap the window at `autoCompactWindow: 200000`
   (an integer: `200k` reads as 200). Past it, or at a handoff point, the slice goes to a fresh
   agent with a brief.
6. **Results come back as files.** An agent writes its report or output to a file and returns
   the path, so the lead's context does not carry copies, and peers read the file instead of
   the lead relaying it.
7. **One message per agent per round,** and peers settle a seam between themselves.
8. **Expensive verification runs once, after the code is final.** A live emulator proof made
   mid-review goes stale when a fix changes the bot (the instrument hash), and PR-F paid for
   two rounds of proof that way.
9. **The subagent prompt cache is held for an hour** (`subagentPromptCacheTtl: "1h"` in
   `.claude/settings.json`). Subagent caches default to five minutes even on a subscription. A
   teammate idle longer than that between rounds re-writes its whole conversation at the cache
   write price (1.25x input) instead of reading it (0.05x on Opus 5.5 and Sonnet 5.5). A 1-hour
   write costs 2x, which pays as soon as one idle gap passes five minutes.
10. **Cost is measured per task.** `/usage` after a team run, in the retro: total, subagent
    share, wake-ups per agent.

Fixes after a team's review go to each file's owner, all at once (one wave), per the
`review-to-clean` skill's team rule.

Sources: https://www.anthropic.com/engineering/multi-agent-research-system,
https://anthropic.com/engineering/harness-design-long-running-apps,
https://code.claude.com/docs/en/agent-teams, https://code.claude.com/docs/en/sub-agents,
https://code.claude.com/docs/en/costs.md, https://code.claude.com/docs/en/prompt-caching.md,
https://cognition.com/blog/dont-build-multi-agents, https://cognition.com/blog/multi-agents-working,
https://cognition.com/blog/devin-fusion. Some figures from the Anthropic and Cognition blog posts
were read through a summarising fetch, not quoted from the page.
