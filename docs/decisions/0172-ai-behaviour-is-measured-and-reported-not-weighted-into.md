---
id: 172
title: "AI behaviour is MEASURED and REPORTED, not weighted into threat"
date: "2026-09-03"
section: "Operational Gotchas (durable)"
issues: [344]
---

# AI behaviour is MEASURED and REPORTED, not weighted into threat

#344 proposed weighting each unit's threat contribution by its AI behaviour, on the grounds that a
`never-move` unit contributes nothing until the player walks into its range. The issue asked for a
measurement against the twins before any weighting was picked. The measurement said **do not build
the weighting.**

**Vanilla has no single shape to weight against.** Red-force behaviour per twin runs from FE8 Ch3 at
100% static to FE8 Ch2 at 100% mobile, with Ch1 at 70/30, Ch4 56/43, Ch5 52/47 and Ch6 33/66. There
is no campaign-wide "vanilla mobile share"; behavioural parity can only ever mean *this chapter
against its own twin*.

**And ours already equals its twin, everywhere.** Measured 0 points of difference on all six active
chapters, with every enemy resolving (0 failures). That is not luck: **#335 made AI derived** --
`enemy_ai_bytes` returns the donor's bytes -- so our behavioural shape IS the twin's by construction.
A weighting would therefore apply identical weights to both sides of a ratio that is equal by
definition and report x1.00 no matter what. **It cannot catch anything.** The ch04 "78% pursuers
against a half-static twin" case is history: it was fixed by deriving AI, not by measuring it.

The only remaining channel for divergence is `ai_override`, of which the campaign has three, each
with a mandatory `why`, and none introducing a silent shift (Sephek keeps his donor's family; the
mauthedoog and the white moose are ours-only units vanilla has nothing to lend).

So the residue that IS worth having: **the split is reported next to the roster** (`make chapter`
prints `shape N come to you / N you walk into`), where a future divergence is visible instead of
latent -- and the metric stays about stats, which is what it can actually measure.

**A corollary, and the one real gap the measurement found.** `AI_BEHAVIOUR` named 8 of the decomp's
19 AI2 scripts (`gAi2ScriptTable`, `cp_data.c:1548`, read via `cp_script.c:90` as
`gpAi2Table[0][ai2]`), so eleven indices reported as bare numbers -- including `0x0A`, which
**vanilla's own Prologue fields**. Thirteen are named now: every index whose decomp SYMBOL states
its behaviour. The **six** the decomp itself gives only an address (0x08, 0x09, 0x0A, 0x0B, 0x0D,
0x0F) stay **unnamed and UNCLASSIFIED** rather than guessed at -- bucketing an unknown script as
static because it is unnamed would be a guess wearing a measurement's clothes, and it would land on
the side that lowers the number. A test pins the map against `cp_data.c` -- the tracked `.c`, never
the generated `.s`, which is a build artifact and not at HEAD at all.

**"Known but neither" is not the same fact as "unknown", and the first cut collapsed them.** Three
NAMED families -- `pillage-escape`, `escape`, `attack-walls-snags` -- are neither threat that comes
to you nor threat you walk into: the unit moves, but not at the player. Leaving them to fall through
to `unclassified` said *we do not know* about scripts the decomp names outright, and `ai2 = 0x05`
alone appears 120 times in the reference files the parity twins already read. They get their own
bucket, **on its own errand**, and a test asserts that no named family can ever fall through to
unclassified again.
