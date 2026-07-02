# Building Manchego Stars with AI Agents — Project History & Professional Case Study

> Prepared for Nicolas, 2026-07-02. Purpose: a "sell yourself" artifact — the project's history,
> what you learned, and ready-to-use material for interviews, resume entries, and LinkedIn.
> This is a personal-development doc, not project documentation; feel free to move it out of the repo.

---

## 1. The elevator pitch (30 seconds)

> "I'm a product manager, and over five weeks of nights-and-weekends I shipped a playable Game Boy
> Advance tactics game by directing AI coding agents — 529 commits, ~100 issues and PRs, a CI
> pipeline, and a v0.1.0 release my friends are playtesting. I wrote none of the code by hand.
> My job was the PM job: vision, scope, prioritization, process design, and quality gates — applied
> to an AI 'team' instead of a human one. The most transferable thing I learned is that managing
> AI agents *is* product management: the teams that win with AI are the ones that give it crisp
> requirements, hard guardrails, and fast feedback loops — and I now know how to build all three."

## 2. The project in numbers

| Metric | Value |
|---|---|
| Calendar span | **36 days** (2026-05-27 → 2026-07-02), nights/weekends, ~6–7 intensive days |
| Commits | **529** on main |
| Issues + PRs | **~103** (GitHub-tracked backlog with M0–M4 milestones) |
| First release | **v0.1.0**, 2026-06-19 (23 days in) — Prologue + Chapter 1, distributed to the campaign's players |
| Content shipped | Ch0–Ch2 complete & playable; Ch3 designed + fully written; Ch4–8 designed; 8 custom player characters with hand-directed portrait art; custom battle animations shipping |
| Infrastructure | CI (build + drift-guard, median 3.2 min), 2,700 LOC of tests, an automated in-emulator playtest harness, a data-driven content pipeline (YAML → ROM injection) |
| Team | 1 PM (me) + AI coding agents (Claude Code). Zero hand-written code. |

**What it is:** a ROM hack of *Fire Emblem: The Sacred Stones* (GBA), built from the community C
decompilation, that converts my group's multi-year D&D campaign into a playable tactics game —
their characters, their story beats, delivered as a `.gba` file that runs on any emulator.

**Independent calibration** (from a field benchmark done 2026-07-02): the most celebrated Fire
Emblem ROM hacks — multi-year community projects — ship with *no version control, no CI, no
automated tests*. This project's engineering process (git + CI + data pipeline + automated
in-emulator testing) **exceeds every shipped FE hack we could find**, and its emulator-scripted
test harness has essentially one peer in the entire ROM-hacking scene (pokeemerald-expansion's
battle-test runner, built by a large community).

## 3. The narrative arc — five phases and what each taught

### Phase 1 — Vision & scaffold (May 27–31)
Wrote a PRD before any code: problem ("the campaign is over; the memories deserve better than a
group chat"), audience (exactly 6 friends), success metrics ("that's my character!" recognition in
seconds), and explicit **non-goals** (no public release, no custom engine, no AI-generated maps).
Set up the repo, backlog, and operating instructions for the AI (CLAUDE.md).

**PM lesson:** non-goals did more work than goals. Every scope fight for the next month was
settled by pointing at a non-goal written on day one.

### Phase 2 — The defining product pivot (May 28 – June 4)
The original concept layered D&D 5e mechanics (d20 rolls, armor class, saves, damage types) onto
Fire Emblem combat. Playing with early prototypes made the problem obvious: **it stopped feeling
like Fire Emblem.** I made the call the AI would never have made on its own — and repeatedly had
to *re-enforce* against its instinct to add D&D mechanics back:

> **"Combat is vanilla FE8. D&D is flavor. The d20 survives only as a cosmetic crit animation."**

A whole mechanics layer (damage types, AC, saves, homebrew classes) was cut over a week of
"audit" commits, with each decision written into a dated decision log. The PRD itself was then
pruned from 847 to 594 lines ("v2.0 — pruned to vision + durable design").

**PM lesson (interview gold):** the highest-value acts were *subtractive*. AI generates
possibilities at zero marginal cost; the scarce skill is killing them. I have dated ADR entries
documenting each cut and why.

### Phase 3 — Pipeline before content (June 1–10)
Instead of hand-building chapters, invested in a **content pipeline**: characters and chapters
defined in YAML data files, injected into the game's C source at build time by tooling, with a
hard architectural rule — *"if it references a character name or plot event, it goes in data, not
engine code"* — mechanically enforced by a checker that runs in CI and pre-commit. Also built:
an art pipeline (AI-generated character busts → automated conversion to GBA's 16-color indexed
format), generated documentation (chapter/roster indexes regenerated from data and diffed in CI so
docs can't silently rot), and an **automated in-emulator playtest harness** that boots the game,
plays it, and asserts win/loss/softlock states from memory reads.

**PM lesson:** "the time the *second* chapter takes is what you divide your timeline by."
Chapter 2 shipped in a fraction of Chapter 1's time because the pipeline existed. This is the
platform-investment argument every PM makes; here I got to run both sides of the experiment myself.

### Phase 4 — Process failure and the fix (June 17–24)
As velocity rose, I hit the classic scaling failure: work went straight to main, and on June 19
main went red for **21 consecutive CI runs (~3 hours)**. First response was an org-design
mistake: splitting work into fixed "lanes" (content vs. pipeline) with ownership enforced by file
paths. It lasted five days — features kept spanning both lanes, and the boundary "sawed the
feature in half." On June 24 I replaced it with **feature-flow**: one issue → one short-lived
branch → PR → CI gate → squash-merge, with only *invariants* (not ownership) enforced by
machine. The decision log records the reversal and the root cause: *"conflating build-isolation
with ownership."*

**Result, measurable:** every one of the 23 CI failures in the project's history was a direct
push to main; in the 60 CI runs after feature-flow adoption, **100% passed**.

**PM lesson (interview gold):** process is a product you iterate with data. I shipped a process,
watched it fail, diagnosed the actual constraint, and shipped a replacement — in one week, with
before/after metrics.

### Phase 5 — Operating rhythm (June 24 – now)
Steady state: vertical slices (one complete, playable chapter at a time — map, dialogue, art,
events, tests), released to real users (my players) with a structured feedback form and a triage
process that routes each piece of feedback to the right workstream. Friend playtest feedback is
filed through a GitHub issue form; a triage skill classifies it (defect vs. aspiration vs. data
point) and gates the right slice's definition-of-done. A full independent repo audit (July 2)
confirmed the process holds and identified the next round of debt to pay down — which was then
executed autonomously by agents while I traveled.

## 4. What I actually did (the PM skill inventory)

Framed the way an interviewer will probe it — "if the AI wrote all the code, what did *you* do?"

1. **Product vision & requirements.** Wrote and maintained the PRD; defined success as user
   recognition ("that's my character"), not feature count. Every chapter design starts from
   *which campaign memories must land* — requirements the AI cannot know.
2. **Scope control under infinite supply.** The binding constraint with AI isn't build capacity,
   it's decision capacity. I cut a whole mechanics system, capped the MVP at 8 chapters,
   rejected a public release (11 MB patch = legal exposure; private distribution instead), and
   wrote non-goals that stuck.
3. **Org/process design for an AI team.** Designed the operating system the agents run inside:
   session-start checklists, a live-state handoff doc (institutional memory between stateless
   sessions), a dated decision log with supersede chains (so settled questions stay settled), a
   model-selection guide (cheap model for dialogue generation, expensive model for cross-cutting
   engine work — cost/quality routing), and the feature-flow branching discipline.
4. **Quality systems, not quality vibes.** Everything I cared about became a machine check:
   docs that reference missing files fail CI; stale generated indexes fail CI; campaign names in
   engine code fail CI; text corruption fails CI; a save-format change that would break my
   testers' saves fails CI. The principle — recorded as an ADR on June 4 — was *"discipline is
   mechanized, not remembered."*
5. **Stakeholder & feedback management.** Real users (the players) get versioned builds, a
   playtest form, and triaged follow-ups. Review-on-mobile workflows (committed GIF/PNG demos
   viewable from a phone) kept me in the approval loop while traveling.
6. **Judgment calls the AI flagged but couldn't make.** Art direction approvals, difficulty
   parity targets ("mirror vanilla chapter N's pressure, never inflate stats"), story tone,
   which vanilla-game deviations are acceptable (each one logged as a sanctioned deviation).

## 5. What I learned about building with AI (the transferable insights)

These are the soundbites for "what did you learn?" questions:

- **AI raises the ceiling on individual leverage, but only through PM discipline.** The
  difference between my week-1 chaos and week-4 velocity wasn't better prompts — it was better
  *process*: single sources of truth, mechanized gates, small reviewable increments.
- **Context is the product you manage.** AI sessions are stateless; the project's real asset is
  its written memory (decision log, handoff doc, operating instructions). I learned to treat
  documentation as the *interface to my team*, with the same rigor as an API: one fact, one
  place, generated indexes, freshness checks.
- **The AI's failure mode is agreeable scope creep; the PM's job is to be the immune system.**
  Every D&D mechanic I cut tried to come back. Guardrails in prose don't hold; guardrails in CI do.
- **Verification beats generation.** The projects' most valuable tooling isn't what writes the
  game — it's what *checks* the game: the emulator harness, the text decoder, the difficulty
  parity gates. When output is cheap, trust is the bottleneck, and trust comes from tests.
- **Process changes need before/after metrics, even solo.** Red-main streak → feature-flow →
  100% pass rate is a one-sentence, data-backed process story.

## 6. Ready-to-use material

### Resume entry (pick one)

**Compact:**
> **AI-Directed Game Development (personal project)** — Shipped a playable GBA tactics game
> (Fire Emblem ROM hack of a D&D campaign) in 5 weeks by directing AI coding agents end-to-end:
> 529 commits, ~100 tracked issues/PRs, CI with build/content-drift gates, automated in-emulator
> testing, and a v0.1.0 release to real users — with zero hand-written code. Designed the product
> (PRD, scope, non-goals) and the process (data-driven content pipeline, ADR decision log,
> PR-based feature flow that took CI from a 21-run failure streak to 100% pass).

**Skills-forward:**
> **Product Manager, "Manchego Stars" (AI-built GBA game)** — First-hand case study in managing
> AI agents as a development team: wrote the PRD and killed an entire mechanics system to protect
> product feel; built the team's "operating system" (single-source-of-truth docs, mechanized
> quality gates, model-cost routing); ran versioned releases with structured playtest feedback
> from real users. Engineering process independently benchmarked above every shipped project in
> its (ROM-hacking) field.

### Interview stories (STAR-ready)

1. **The pivot** — *Situation:* hybrid D&D/FE combat made the game feel like neither. *Task:*
   protect the core experience. *Action:* cut damage types/AC/saves entirely; enforced "D&D is
   flavor" with a CI check that rejects campaign concepts in engine code. *Result:* playtesters'
   verdict — "plays like Fire Emblem, reads like our campaign"; zero re-litigations since, because
   the decision is written down and machine-enforced.
2. **The red main** — *S:* 21 consecutive CI failures in one evening. *T:* stop the bleeding
   without killing velocity. *A:* tried fixed ownership lanes (failed — documented why), replaced
   with feature-flow PR discipline in under a week. *R:* 100% CI pass over the next 60 runs;
   the failure mode (direct pushes to main) structurally eliminated.
3. **Pipeline before content** — *S:* 9 chapters to build, each initially hand-wired. *T:*
   make chapter N+1 cheaper than chapter N. *A:* YAML-driven content pipeline + generated docs +
   difficulty-parity tooling that benchmarks every chapter against its vanilla-game reference.
   *R:* Chapter 2 shipped in a fraction of Chapter 1's time; Chapter 3's design + full dialogue
   were locked in two sessions.
4. **Managing an AI team member** — *S:* stateless collaborator with superhuman output and no
   memory. *T:* get senior-engineer reliability out of it. *A:* wrote its onboarding doc
   (CLAUDE.md), its memory (HANDOFF.md), its guardrails (check.py), and its review process
   (PR + CI + code-review pass); routed tasks to cheap vs. expensive models by complexity.
   *R:* the "team" ships vertical slices unsupervised — including a full repo audit and cleanup
   executed while I was traveling.
5. **Feedback loops with real users** — *S:* friends playtesting builds. *T:* turn "my friend
   said Ch1 was hard" into engineering signal. *A:* structured playtest issue form + triage
   process routing each item to a workstream; difficulty data points logged against the balance
   tooling's predictions. *R:* balance calls made on data ("alpha said harder-than-vanilla; second
   run said good — matches the parity model"), not vibes.

### LinkedIn post skeleton

Hook ("I shipped a Game Boy Advance game without writing a line of code — and it was the most PM
work I've ever done") → the numbers → the three lessons (subtraction is the job; docs are the
interface to an AI team; trust comes from verification, so build the checks first) → the human
ending (it's my D&D group's campaign, and my friends are playing it).

### Honest-framing notes (for the inevitable probing question)

- Don't claim you learned to *code*. Claim you learned to **specify, verify, and integrate** —
  and can now read a diff, a CI log, and an architecture argument well enough to govern them.
  That's the PM skill employers actually want from "AI fluency."
- Have one technical artifact you can walk through cold: the engine/content boundary rule is the
  best one (why it exists, how it's enforced, what it makes cheap — a second campaign).
- The weak spots the audit found (a build-script monolith, doc drift) are *also* good material:
  you commissioned an independent audit, got findings ranked by cost, and executed the fixes —
  that's a management story, not a confession.

---

*Sources: repo git history (529 commits, unshallowed), `docs/decisions.md` dated ADRs,
`docs/audit-2026-07-02.md` (independent audit + field benchmark), GitHub issue/PR/CI records.*
