---
name: triage-feedback
description: Classify, label, and route Manchego Stars playtest feedback into the right vertical-slice workstream so it gates that slice's Definition of Done instead of pooling as tech debt. Use when Nicolas pastes friend feedback ("my friend said…", "they thought Ch1 was…"), asks to triage the playtest issues, or processes new [Playtest] issues from the GitHub form.
---

# Triage Feedback — route playtest notes into the slice workstream

Two intake paths, one routine. Friends file the slim form
(`.github/ISSUE_TEMPLATE/playtest_feedback.yml` → `[Playtest]` issue, `playtest` label);
Nicolas also drops feedback ad-hoc in chat. Both flow through the SAME classification so
the issue list reads uniformly. **The form is dumb intake; this skill is the intelligence.**
The taxonomy below is the single source of truth the form's "what kind" dropdown mirrors —
keep them in sync if either changes.

Core rule (why this skill exists): **feedback must land in a vertical slice's checklist so
the slice can't be marked done while it's open.** It is NOT allowed to become a `playtest`
bucket nobody drains. Mirror how #47 already works — lightweight items are checklist lines;
substantial ones get promoted to their own labeled issue and linked back.

## Inputs (read FIRST)

1. **Live state:** `HANDOFF.md` — which slice the work is currently on (e.g. content → Ch2
   #22). This decides whether incoming feedback is *upstream* (gates forward progress) or
   *current/downstream* (handled in stream).
2. **The slice issues** (the workstream this feeds): each chapter issue carries a
   **Vertical-slice checklist** = its Definition of Done. Map area → issue:

   | Area | Issue |
   |---|---|
   | Title / opening montage | #43 (montage slots) / #36 (title+credits) |
   | Prologue — A Dagger of Ice | #20 |
   | Ch1 — The Iron Trail | #21 |
   | Ch2 — Cold Welcome | #22 |
   | Ch3 — The Termalaine Mine | #23 |
   | Ch4 — The White Moose | #24 |
   | Ch5 — The Elven Tomb | #25 |
   | Ch6 — The Maer Monster | #26 |
   | Ch7 — Blood in Bremen | #27 |
   | Ch8 — The Eastway Ambush | #28 |
   | World map / menus / prep | #29 (world map) / #46 (prep+lord-select UX) |

   Verify the mapping is still live with `gh issue list --label content` before writing —
   issue numbers are facts, don't trust this table blind if the repo has moved on.
3. **The alpha tracker:** #47 (Prologue→Ch1 friend run). Cross-link feedback from that run
   so the rollup stays complete; close it per its own exit criteria, not here.

## Classification taxonomy (maps to EXISTING labels — don't invent new ones)

Combat is vanilla FE8 (see CLAUDE.md) — "too hard" is a map/enemy/recruit-design finding,
labeled `balance`, never a stat-conversion question.

| If the feedback is about… | Label(s) |
|---|---|
| A crash, soft-lock, garbled text, wrong sprite/flag, anything broken | `bug` |
| Difficulty, hit rates, enemy pressure, a unit dying too easily | `balance` |
| Story, a line of dialogue, a character read, pacing of a scene | `content` |
| A portrait, map tileset, battle/map sprite, visual polish | `art` |
| Music or a sound effect | `audio` |
| Engine behavior: UI, menus, prep screen, a system that isn't map data | `engine` |
| A feature idea / nice-to-have beyond MVP | `stretch` |

One note can earn several labels (a confusing cutscene that also reads flat → `content`;
a sprite that misleads in combat → `art` + `bug`). Also capture **sentiment** in the body
(loved / fine / frustrating / confusing / boring) — it's signal even when there's no fix.

## Routine

1. **Parse** the raw text semantically — what actually happened, where, how it felt, what
   they expected vs. got. Don't keyword-match; read it. Pull the area even when the friend
   said "not sure" (infer from unit/scene names). **Capture the build version** (the form
   asks; ad-hoc, ask Nicolas which build) and record it in the filed issue — a finding is
   only meaningful against a known ROM, and it may already be fixed on a newer build.
2. **Classify** → label(s) + area + sentiment, per the tables above.
3. **Decide weight** — mirror #47:
   - **Lightweight** (a clear, bounded fix or a one-line impression): becomes a **checklist
     line on the area's slice issue**, e.g. append to the Vertical-slice checklist:
     `- [ ] **Playtest:** Brie one-shot by bridge archers — read as unfair (balance)`.
   - **Substantial** (its own workstream — a difficulty model, a re-write, a system change):
     **open a new labeled issue** (`playtest` + mapped labels, milestone = the slice's
     milestone), then **link it from the slice checklist** as a gating item
     (`- [ ] **Playtest:** … → #NN`). This is exactly the #45/#46 promotion pattern.
4. **Gate-check against current work** (the anti-tech-debt step):
   - Read `HANDOFF.md` for the slice in progress. If the feedback targets an **upstream**
     slice (earlier than current — e.g. Ch1 feedback while work is on Ch2), it **blocks
     forward progress**: a slice already played by friends regressed. Add the `blocked`
     label to that upstream slice issue, and **surface it loudly** in your reply — name it
     as a gate that must clear before (or in parallel with) the current slice, not deferred.
   - If it targets the **current** slice, fold it into that slice's open checklist normally.
   - If it targets a **downstream/unbuilt** slice, file it on that slice's issue so it's
     waiting when the stream arrives — still tracked, just not gating now.
5. **File it** with `gh`: `[Playtest]` title, `playtest` + mapped labels, body with
   **What happened / Where / Sentiment / Suggested fix / Source** (friend name or `#47`),
   and the cross-links from steps 3–4. For form issues, edit the existing issue (add labels,
   append the structured body, link it) rather than opening a duplicate.
6. **Report back** to Nicolas: one line per item — `area · label(s) · weight · where it
   landed (issue/#NN or checklist) · GATING? y/n`. Lead with anything gating.

## Gates / conventions

- **Repo over memory** (Definition of Done in CLAUDE.md): the triage result lives in
  GitHub issues, never in chat or private memory. If a decision comes out of triaging
  (e.g. "Ch1 archer range is intended, won't fix"), record it in `docs/decisions.md`.
- Don't silently reclassify or close a friend's note as "won't fix" — bring it to Nicolas
  with your reasoning; he owns the call.
- Keep the form's "what kind" dropdown and this taxonomy in lockstep — they're one source
  of truth split across two files.
- **Per-release upkeep:** when a chapter ships or a new build goes out, update the form's
  `where` + `version` dropdowns (tie to release #37) so friends only ever see what they can
  reach. Never list unbuilt chapters — that's what prompted trimming the form to v0.1.0.
