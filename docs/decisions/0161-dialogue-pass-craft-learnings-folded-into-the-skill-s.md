---
id: 161
title: "Dialogue-pass craft learnings (2026-07-23, ch05 opening) — folded into the skill's Craft check."
date: "2026-07-23"
section: "Story & Dialogue"
issues: []
---

# Dialogue-pass craft learnings (2026-07-23, ch05 opening) — folded into the skill's Craft check.

Two failure modes surfaced hard while writing ch05 and are now first-class checks in
`.claude/skills/dialogue-pass/SKILL.md`: (1) **people talking, not mood-narration** — the #1 cause of
"dry"; a line that *describes atmosphere* ("she wakes the sad things") is dead even when evocative, so
every box must be a person reacting/joking/asking, with dread carried by a concrete in-character line;
(2) **draft BOXED, not prose** — prose-length lines read wordy and hide the A-press pacing, so lines are
hand-boxed (2 lines, ~29–30 ch; on-map ≤29) from the first pass and shown boxed. Also: **canon research
in the ROM-free web env** — the RotFM PDF lives on Nicolas's Mac, so fill canon gaps from online
actual-play recaps + the Forgotten Realms wiki (this caught Sahnar's real identity: female, elven royalty,
awake-and-aware for millennia). Verify against Nicolas's table, which outranks book canon for our version.
_Decided: 2026-07-23 (ch05 opening dialogue pass, ROM-free web session)._

**ch05 opening uses the vanilla two-scene rhythm: a focused PRE-MAP cutscene + an ON-MAP opening scene.**
`chapter_start` (Text_BG) carries the ch04 thread and mood (party descends the gateway into the open-air
hollow; Lupin/Marty/Pinky; Ravisin stays SILENT — saved for the eruption); then the map loads and a
`map_opening` on-map scene brings the enemies into view and Basil (a green ally) joins. More dynamic than
one talking-heads cutscene, and it's what FE8 does. Villain reveal is *earned* at the eruption (she acts,
she doesn't monologue at the door). _Decided: 2026-07-23 (ch05 opening, with Nicolas)._
**In-engine dialogue review is motion, not stills:** `tools/playtest/run.sh record` captures every 5th frame
through both scenes; deduped GIFs (opened in Safari) are what Nicolas signs off before art-visible text commits —
static screenshots catch the typewriter mid-stroke and false-alarm as cut-off text. _Decided: 2026-06-10 with
Nicolas ("use this format going forward")._
