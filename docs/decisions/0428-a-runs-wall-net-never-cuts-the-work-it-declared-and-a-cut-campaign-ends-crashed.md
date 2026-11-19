---
id: 428
title: "A run's wall net never cuts the work it declared, and a cut campaign ends crashed"
date: "2026-11-19"
section: "Operational Gotchas (durable)"
issues: [665, 639, 510]
---
# A run's wall net never cuts the work it declared, and a cut campaign ends crashed

**Decided 2026-11-19 (#665).** It amends ADR 0173 (the deadline is a frame budget; the wall
limit stays as a last-resort net).

**The problem.** #639's overnight laps (`resume --scout`, 20 campaigns) looked finished. 19 of
them had been cut at exactly 2 hours by run.sh's `PT_MAX_WALL_S=7200`, mid-chapter and still
playing. The `campaign` scenario declares 86400s of work ("a whole game is hours"), but the
flat net cut it first. campaign.lua never wrote its end line, so `resume` printed no end and
counted no crash, and the partial chapters were read as where the campaigns stopped.

**The rules.**
1. **The default wall net is never under the scenario's declared deadline** (run.sh
   `wall_net`). Unset, it is 7200s or the deadline, whichever is longer. A net is for a
   pathology OVERRUN and STALL miss, never for a run doing the work it declared. Every scenario
   but `campaign` declares less than 7200s, so only campaigns change. An explicit
   `PT_MAX_WALL_S` is a deliberate cap and is honoured as given, so unset and 7200 are no
   longer one run: `PT_MAX_WALL_S` left `matrix.py` `RUN_SH_DEFAULTS` (it stays in the key).
2. **A campaign the bot played that left no end line ends `crashed`, in run.sh's words**
   (`montecarlo.py` `records_of`). Its `why` quotes run.sh's verdict (`run_verdict`: the last `RESULT:` line before
   any inspector render, from the log's last MB), so `resume`
   prints it and counts it under "N crashed", and its run dir is kept. It carries what
   campaign.lua's own end carries (`route`, `chapters`), and it is made for a campaign cut
   before the bot's first record too. A diagnostic replay writes no CAMPAIGN line by design and
   is left alone. run.sh's verdict line is read by `matrix.py` `verdict_line`, the one reader
   `parse_verdict` also uses.

**Why not size the net on the lap (chapters × the attempt cap).** An attempt's length is not
known ahead, so any multiplier is a guess that cuts the slow lap. The declared deadline is the
one budget the scenario already owns; OVERRUN and STALL still stop a run that is genuinely not
finishing or wedged, and rule 2 makes any cut that does happen visible.

**What bounds a looping campaign now.** Not the wall net. A bot that loops inside a decision
ends the attempt `timeout` (botrun.lua `M.DECISION_FRAMES`, ADR 0411), and one that plays
without progress ends it `stuck` (the two no-progress rules). Each chapter has at most
`MAX_ATTEMPTS` (12) attempts. OVERRUN at the declared 86400s of work is the backstop past those.
