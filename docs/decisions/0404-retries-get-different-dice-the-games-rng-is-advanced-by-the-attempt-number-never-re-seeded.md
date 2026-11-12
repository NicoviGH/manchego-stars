---
id: 404
title: "Retries get different dice: the game's RNG is advanced by the attempt number, never re-seeded"
date: "2026-11-12"
section: "Combat System"
issues: [510]
---

# Retries get different dice: the game's RNG is advanced by the attempt number, never re-seeded

**Call 1 of the fwd1 build plan (#510 comment 6810567866), approved by Nicolas on 2026-11-11
("I approve all calls").** It amends ADR 0399's stop and ADR 0370's restart rule.

**The error.** A retry loads the chapter-start state back, which restores the game's RNG. A
style played again with the same memory therefore replayed the same game move for move, so ADR
0399 stopped a chapter when every style had been played with what it remembered, and 9 of 22
Ch6 retries had been exact repeats before that. A player who loses a map and tries it again is
not handed the same dice: a different move changes which rolls land where.

**The decision.** Attempt k of a chapter start plays with the game's own generator advanced
`(k - 1) * DICE_STRIDE` draws from the saved start (`DICE_STRIDE` = 1009, campaign.lua), taken
just before the play (`api.advanceDice`, harness.lua; `Sight.advance`, sight.lua, which is
`NextRN` of rng.c run on the three u16 words at `gRNSeeds` and written back).

- **It does not re-seed.** `InitRN` would restart the stream at one of seven starts; the
  attempt keeps the stream the game is on and only moves along it, the effect a player gets by
  redrawing a movement path. FE8 still seeds once at power-on.
- **Attempt 1 advances none.** Every measured cell (FR-002, ADR 0385) and the whole frozen suite
  are attempt 1 and play exactly as before. No measurement moves.
- **A run stays reproducible.** The same start and the same attempt number are the same dice.
  The advance is keyed on the attempt number, so it is the same in the campaign's k-th try, in
  one attempt alone (`api.only = k`, the pool) and in a diagnostic replay of it.
- **A stride of 1009, because one draw is absorbed.** The game draws a die for each tied
  direction of a unit's path (`GenerateBestMovementScript`, bmidoten.c:218-226) and for AI
  moves: 40 to 150 draws a turn on vanilla Ch8. Run `call1b` (campaign 4001, attempt 2): one
  draw ahead at the start, turn 1 drew 59 where the unshifted game drew 60, and from turn 2 on
  both games were on the same dice and played the same game (`acts_hash` and frames equal). The
  stride is more draws than a whole attempt's turns of movement could give back.
- **The dice are in the record.** `dice_start` is the three words after the advance, and each
  player phase's `progress` line in the trace has `rn`, the words that phase started on: two
  attempts on the same dice show as equal words, with no run.
- **The record proves it.** The attempt's record has `dice_advanced` (0 on attempt 1). A
  campaign builds a fresh bot per attempt, so a switch set on the campaign's api never reaches
  botrun; the count travels through `api.play`'s arguments into `info`.
- **A replay burns what its original did.** `replay` hands the harness the original record's
  `dice_advanced`, and a record from before this ADR has none, so it replays 0 draws: it
  replays what the record says, not what the attempt number implies.

**The stop is amended.** With different dice a style played again is a new try, so the
played-with-what-it-remembers bookkeeping (a try key by style and memory size) and the stop
"every style played with what it remembers" are retired. Once every style has been tried the
styles are drawn again, and a chapter stops only at the attempts cap (12, ADR 0399), a clean
clear, or a crash. `api.attempts` (`montecarlo.py resume --attempts N`, 1 to the cap) can bound
it lower for a run.

**The cost.** A failing chapter now always uses the full cap, where before it could stop early
on repeats, so a chapter the bot cannot clear costs 12 attempts every time.
An attempt alone (`api.only`) still ends at the style count (`no_style`): it has no memory, and
its draws of the styles are the campaign's.
