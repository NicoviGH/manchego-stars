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
- a **forced** plan that avoids it: with an act `Bot.candidates` did not offer on the board that
  act was played on (the replay's `unoffered`, checked as it plays), `missing_action`. The
  pinned board alone cannot say this: a later act of the plan is played on a board the earlier
  ones changed. Otherwise the plan is placed by what the planner recorded at the pinned decision,
  in the trace's `plan` event (`planner.lua`, T076): in no `considered` entry (the beam or the
  budget cut it before it was judged), `search_miss`; judged and rejected `over_cap`,
  `mis_predicted_safety`; judged and `outranked`, `mis_scored`. A forced line with no
  `unoffered`, a decision with no plan `audit`, or a plan rejected as `stalled` (one the planner
  may not play) claims nothing.

A replay that planned the same plan, could not play its plan to the end (`broken`, the first
act it did not play; `chosen` is then what it did play), did not avoid the death, or traded it for another unit's is no witness, and the audit says which it was. The trade is not hypothetical: on ours-ch03 seed
1002 the forced plan (unit 3 not attacking, decision 45) saved unit 3, and the boss killed unit 5
instead. That moved the failure; it did not avoid it. A replay run again appends a new line, and
the newest line of each replay (one decision, mode and plan) is the one the audit reads. A replay whose fork did not match the original (`matched` false) is shown as
**UNMATCHED** and counted apart in the SC-004 sentence: it is a fault of the replay, not an
answer about the bot, and is never dropped as a plain non-witness.

**A line from before `planned` claims nothing.** Until the replay recorded its whole plan
(`planned`) and where it broke off (`broken`), a replay that stopped at the pinned decision
printed `avoided` true, and a full-information plan could use acts only the fog-off board offered
(fixed: the diagnostic reveals knowledge, not powers). Such a line is stale: the audit names it
and asks for a re-run, and it counts as no witness.

**Every supported label is reported, plus one primary**, picked in this order: `missing_action`,
`mis_predicted_safety`, `mis_scored`, `search_miss`, `information_unavailable`. A defect the bot
owns comes before a limit of its search, and that before what it could not have known: the
first is the one a fix acts on.

**Diagnostics never feed production** (FR-019). A diagnostic or forced replay writes no `BOTRUN`
record, no retry memory, no endpoint and no label. It prints only `DIAG <json>` lines:
`{ run, ref, mode, matched, baseline, planned, chosen, differs, failure, avoided, traded, unoffered,
broken, trace, pinned, pinned_board }` (`pinned_board`: the filed state, loaded back, holds the board the
pinned decision read), where `run` names
the original attempt (its campaign, seed, chapter and attempt, the name `replay --record` takes,
and its game) and identifies it by its filed trace: the suite reruns a start under every
instrument, so only the trace tells those runs apart, and the audit matches a line to its run by
the trace alone. `ref` is the pinned decision. A
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
campaign's chapter is reached through every chapter before it), a held-out run is refused
while the bot is being tuned (FR-025), and so is a run of another instrument than the code now:
a newer planner would play the diagnostic, and its witness would count toward the old
instrument. A death no plan committed to and no decision moved (a greedy phase's) has no
decision to pin, and is refused too. The replay's trace is filed beside the runs file, its
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
seed 1001, where the original, played fresh under instrument `e1a4192ff78f+v1`, lost on turn 2
when Eirika died in the enemy phase (decision 4, the fog flag set). The full_info replay at
decision 4 (17.2 s, through the probe script with the instrument check; the older probe record
was refused) matched. Where the fogged board showed 3 units and fogged 21, it judged with none
fogged, and its acts were still the fogged board's offer: the diagnostic reveals knowledge, not
powers. It played all of a different plan (attacks on units 134 and 148 among its acts), traded
no one, and Eirika lived. An earlier full_info line, made before the knowledge-not-powers fix,
could use acts only the fog-off board offered, and is stale. The real `replay` command cannot
reach a fog start yet: no suite start has fog (in `chapter_settings.json` only chapters 7, 19,
32, 61 and 62 do), so it stays off the suite until PR-G adds one.

**Built** (T079, 2026-11-07, instrument `e1a4192ff78f+v1`). The originals were played fresh
under the code that replays them (the suite's tasks for ours, the scout start for vanilla
chapter 7), and every named death happened again. Every replay matched, and every pinned state
reloaded to the board its decision read (`pinned_board`; a fresh emulator's load is PR-G's
T084).
- **ours ch02 (chapter 3), seed 1002** (16.6 s, won): Klimt (0xC9) fell on turn 1 (decision 1)
  and Dara (0xCA) on turn 3, both `rng_tail`. A `deep` replay of Klimt's death, pinned at its
  `plan_ref` (decision 1: a green unit has no act that moves it), took 5.5 s. It moved unit 3 to
  4,4 instead of 2,6, played the whole plan, traded no one, and Klimt lived: `search_miss`,
  witnessed.
- **ours ch03 (chapter 4), seed 1002** (31.7 s, won): unit 0x4 fell on turn 11 and Meesmickle
  (unit 3) on turn 21, both `over_cap`. The last decision that moved Meesmickle was 45 (an attack);
  the death's `plan_ref` is 46.
  - `deep` at 45 (29.6 s) planned the baseline's plan and broke at `4>wait@14,4>nil`, on a
    surprise replan after Meesmickle's attack, which the original made too (at 46). No witness.
  - `force` at 45 (29.8 s): the best-ranked judged plan in which Meesmickle does not attack (max_die
    0.931, against the played plan's 0.905; every judged plan was over the cap). It played whole,
    every act offered. Meesmickle lived, and unit 5 died instead (`traded` [5]): no witness. Nothing
    says the hold caused the death: every judged plan was over the cap, and the alternative only
    moves the death to another unit. It stays unclassified, a fallback on a board where no judged
    plan was safe.
- **vanilla chapter 7, seed 1001** (8.1 s, lost): `full_info` witnessed `information_unavailable`
  (above).
- Each replay took 5.5 to 30 wall seconds.

**A normal replan breaks a deep or full-information replay.** `broken` is set when a surprise
replan cuts the diagnostic's plan short, even where the original replanned at the same point, as
in Meesmickle's `deep` replay. It cost nothing there (the plan was the baseline's), but it can
block a witness: such a replay plays a plan that differs only in what came after the cut. This
PR leaves it so, the strict reading. Counting a cut the original also made as not broken is a
change to make with the evidence of a case where it matters.

The audit, instrument `e1a4192ff78f+v1`:
- ours (`runs.jsonl`): "1 of 4 audited failures (25%) have a witnessed label; 3 unclassified. The
  bar is 90%: not met. 2 orphan DIAG lines (no record matches their run)."
- vanilla (`fogprobe.jsonl`): "1 of 1 audited failures (100%) have a witnessed label; 0
  unclassified. The bar is 90%: met. 1 orphan DIAG lines (no record matches their run)."
- vanilla's `runs.jsonl` has no run under this instrument, so its audit picks the newest run's,
  `1edeb96ff443+v1`: 0 of 17.

SC-004 is far below 90% because replays were run for only a handful of deaths. It is PR-F's
measuring stick, not its checkpoint: the checkpoint is that a failure is labelled only with a
witness, and every other one stays visible as unclassified. The orphans are stale lines whose run
is not in the runs file: written before the run identity carried the trace, or naming a run no
longer kept there.
