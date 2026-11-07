---
id: 392
title: "A failure label needs a replayed witness; diagnostics never feed production"
date: "2026-11-07"
section: "Combat System"
issues: [510]
---

# A failure label needs a replayed witness; diagnostics never feed production

**Decided (Claude, 2026-11-07), #510 step 9 PR-F** (the plan's T071-T080, #510 comment
6563384310; spec User Story 4, FR-019, FR-020 and SC-004, #510 comment 6563384018). It builds on
ADR 0388 (each death is graded and cause-attributed) and changes nothing in it: the grading is
what the bot thought at the time, and this record says when an explanation of a death counts as
established.

**The rule.** A death gets a label only when a replay witnesses it: from the same pinned
pre-decision state, with the same RNG, style and budgets, the bot plays a DIFFERENT available
plan, the unit lives to the end of its turn, and no other blue or green unit dies in its place
from the pinned turn on (`traded`). Without that, the death is `unclassified`, and its ADR 0388 cause is
shown as proposed, never as the label (AS 2). A cause can be wrong in a way only a replay shows:
`fog` says the killer was hidden, not that seeing it would have saved the unit.

**The labels** (FR-020), and what witnesses each (`montecarlo.py`'s `witness_label`):
- a **deep** replay (one more player/enemy cycle in the lookahead) that avoids it: `search_miss`;
- a **full-information** replay (fog off inside the sandbox; no future arrival, no RNG) that
  avoids it: `information_unavailable`;
- a **forced** plan that avoids it is placed by what the planner itself recorded at that
  decision, in the trace's `plan` event (`planner.lua`, T076): an act of it not in
  `audit.offered` (every act key `Bot.candidates` offered), `missing_action`; every act offered
  but the plan in no `considered` entry (the beam or the budget cut it before it was judged),
  `search_miss`; judged and rejected `over_cap`, `mis_predicted_safety`; judged and
  `outranked`, `mis_scored`. A forced witness at a decision with no `audit`, or on a plan
  rejected as `stalled` (one the planner may not play), claims nothing.

A replay that played the same plan, did not avoid the death, or traded it for another unit's is
no witness, and the audit says which it was. The trade is not hypothetical: on ours-ch03 seed
1002 the forced plan (unit 3 not attacking, decision 45) saved unit 3, and the boss killed unit 5
instead. That moved the failure; it did not avoid it. A replay run again appends a new line, and
the newest line of each replay (one decision, mode and plan) is the one the audit reads. A replay whose fork did not match the original (`matched` false) is shown as
**UNMATCHED** and counted apart in the SC-004 sentence: it is a fault of the replay, not an
answer about the bot, and is never dropped as a plain non-witness.

**Every supported label is reported, plus one primary**, picked in this order: `missing_action`,
`mis_predicted_safety`, `mis_scored`, `search_miss`, `information_unavailable`. A defect the bot
owns comes before a limit of its search, and that before what it could not have known: the
first is the one a fix acts on.

**Diagnostics never feed production** (FR-019). A diagnostic or forced replay writes no `BOTRUN`
record, no retry memory, no endpoint and no label. It prints only `DIAG <json>` lines:
`{ run, ref, mode, matched, baseline, chosen, differs, failure, avoided, traded, trace,
pinned, pinned_board }` (`pinned_board`: the filed state, loaded back, holds the board the
pinned decision read), where `run` is
the original attempt's game, chapter, seed, attempt and filed trace (the suite reruns a start
under every instrument, so only the trace tells those runs apart), and `ref` the death's
`plan_ref`. A
diagnostic plays with information or depth production does not have; if its choices reached a
record or a retry, the instrument would measure the diagnostic, not the bot.

**The audit** (`montecarlo.py audit <runs .jsonl> --diag <log> ...`) reads the runs file and each
record's kept trace with `read_trace`, and the DIAG lines with `parse_lines`: no second reader. It
prints each death with its labels and each witness's `story` command, then SC-004's sentence:
how many audited failures have a witnessed label, how many stay unclassified, against the 90% bar.
It audits ONE instrument's runs, the newest run's unless `--instrument` names another, and the
sentence names it: two instruments are two bots, and one sentence over both would measure
neither. A DIAG line that replays no death of those runs (its run left the store, or it was
written before the run identity carried the trace) is printed as an **orphan** with its run and
counted in the sentence, never dropped. A line for another instrument's run belongs to that
instrument's audit.

**The deep diagnostic charges no budget.** `deep` adds its extra player/enemy cycle outside the
lookahead budget, on purpose: if it respected an exhausted budget it would be the baseline, and a
diagnostic charges no production budget anyway. FR-019's "same budgets" means the baseline and
the diagnostic start from the same budget left, and every search limit other than the extra cycle
stays the same. The plan records it as `plan.lookahead.deep`.

**How a decision is pinned.** `montecarlo.py replay` re-plays the suite run's own task (its start,
seed and instrument, `suite_tasks`) with `PT_DIAG` set, and the harness plays it again to decision
`ref`. The fork is `matched` only when every phase snapshot and every plan choice up to `ref`
equals the filed original trace's (the old traces carry no board hash). Determinism was measured:
156 of 156 re-runs of the same attempt under the same instrument, in the two stores, left
identical traces. **The hazard:** Lua seeds its string hash per process, so a `pairs` over string
keys that picks a winner would break a replay. The prefix match is the guard, which is why an
unmatched fork is reported and never silently read as "no witness". Only suite runs replay (a
campaign's chapter is reached through every chapter before it), and a held-out run is refused
while the bot is being tuned (FR-025). The replay's trace is filed beside the runs file, its
DIAG lines go to `diag.jsonl` there, and its BOTRUN line, if any, is dropped. The game's state at
the pinned decision (`pinned-*.ss`) is filed beside that trace and named in the DIAG line
(`pinned`): it is the failing decision's board fixture (T084).

**Which decision is pinned.** By default, the last decision whose act moved the dead unit before
it fell (`moved_ref`; a kept act counts under the plan that made it), not the death's
`plan_ref`. `plan_ref` is the plan that committed to the phase the unit fell in, and it need not
move the unit at all: on the suite start ours-ch03, seed 1002, unit 3 struck under plan 45 as a kept act,
and its `plan_ref` is 46, which never moves it. A replay pinned at 46 could not change what killed
it. Only when nothing moved the unit is `plan_ref` used, and the replay says so.

**Full information** (R-7). `sight.fullInfo` runs the decision in one outermost sandbox with the
vision range (gPlaySt +0x0D) written 0 through the journaled api, then the game's own
`RefreshEntityBmMaps`, which clears the fog bit on every red unit it now sees. An arrival is a
unit no event has loaded yet and no RNG is drawn, so neither is revealed; the sandbox's load
undoes the game's writes, and it refuses inside an open sandbox. Its unit test (`test_sight.lua`,
T071) passes, and it is proven live off the suite: vanilla chapter 7 (Ch6, fog), scout state,
seed 1001, where the original lost on turn 2 when Eirika died in the enemy phase. The full_info
replay at decision 4 matched, chose a different plan, avoided the death with nothing traded, and
saw 24 units with 0 fogged, against the original's 3 seen and 21 fogged. The real `replay`
command cannot reach a fog start yet: no suite start has fog (in `chapter_settings.json` only
chapters 7, 19, 32, 61 and 62 do), so PR-G adds one.

**Built** (T079, 2026-11-07). One instrumented replay per case:
- ours ch02 (chapter 3), seed 1002, the green 0xC9 (Klimt): `deep` witnessed `search_miss`.
- ours ch03 (chapter 4), seed 1002, unit 3, turn 21: `deep` chose the same plan at decisions 45
  and 46. Forcing the second-ranked plan at 45 saved unit 3 and traded it for 0x05. Every plan
  judged at 45 was over the cap (max_die 0.905 to 0.93), so the death stays unclassified: a
  fallback on a board where no judged plan was safe.
- The pinned state reloads to the same board in the same emulator process (`pinned_board`
  true). Loading it in a fresh emulator is PR-G's T084.
- Each replay took 6 to 30 wall seconds.

The audit on both stores, instrument `1edeb96ff443+v1`:
- vanilla: "0 of 17 audited failures (0%) have a witnessed label; 17 unclassified. The bar is 90%:
  not met. 2 orphan DIAG lines (no record matches their run)."
- ours: "1 of 13 audited failures (8%) have a witnessed label; 12 unclassified. The bar is 90%:
  not met. 2 orphan DIAG lines (no record matches their run)."

SC-004 is far below 90% because replays were run for only a handful of deaths. It is PR-F's
measuring stick, not its checkpoint: the checkpoint is that a failure is labelled only with a
witness, and every other one stays visible as unclassified. The orphans are lines written before
the run identity carried the trace, and the chapter 7 full-information line, whose scout run is kept in the probe's own runs file
(`fogprobe.jsonl`), not in the store's `runs.jsonl`. Audited against that file (instrument
`b74ed95f600a+v1`), the line witnesses `information_unavailable`: "1 of 1 audited failures (100%)".
