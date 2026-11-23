---
id: 457
title: "The bot's work order lives on a GitHub Project roadmap, and make tidy keeps every open #640 issue on it"
date: "2026-11-23"
section: "Working Conventions (Definition of Done)"
issues: [747, 640, 699]
---

# The bot's work order lives on a GitHub Project roadmap, and make tidy keeps every open #640 issue on it

**Decided (Nicolas, 2026-11-23, #747):** "can we build a roadmap (via github maybe?) and stick
to it", and, against a roadmap kept as an issue comment: "NO not a comment, that's clearly getting
out of control. github HAS roadmaps".

**Why.** The order of #640's work was kept in three places that drifted apart: #699's status
table, HANDOFF's "next" lists, and the issues' own comments. Every investigation filed issues and
none were re-ranked or closed. On 2026-11-23, 27 issues were open under #640, and 17 of them had
never been sized against the latest measurement (`m740c`, #699 comment 7093112364).

**The call.**
- **The roadmap:** the user Project https://github.com/users/NicoviGH/projects/2, linked to
  the repository. Its fields:
  - **Status:** Now, Next, Later, Parked, Epic or Done. The epics are #640, #699 and #689.
    It is the built-in Status field: a Board view's columns group by it, and grouping cannot
    be set through the API.
  - **Rank:** the order within a Status.
  - **Reach:** what the issue touches in the latest measurement.
- **The one place the order lives.** HANDOFF and #699's status table point at the Project;
  they do not restate the order.
- **The guard:** `make tidy` (`tools/gh_tidy.py`, `check_roadmap`) reports every open issue in
  #640's tree, the root included, that is not on the Project or has no Status. Reading Project
  items needs the token's `read:project` scope. Without it, the run exits 2 (UNCHECKED), never
  clean.
- **Views:** "Roadmap" (a Board, one column per Status) and "Ranked list" (a Table); both
  hide Done.
- **Placing new work:** a new issue under #640 is placed with its reach, sized against the
  latest measurement, before work starts on it (Nicolas, 2026-11-22: size a fix before
  recommending it). Parked issues also carry the `on-hold` label and its one why-comment; `make tidy` checks the
  label.
