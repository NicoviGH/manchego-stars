# Handoff: **NEXT = invoke `/dialogue-pass`, REVIEW all locked ch00 text (montage cards + opening scene — Nicolas wants a thoroughness pass), then continue at slot 4 (mid-fight line).**

**Date:** 2026-06-10
**Last session:** Built the dialogue-writing system and co-wrote the first half of the
ch00 dialogue pass with Nicolas: voice bibles (`lore/*.md` §Voice), the
`.claude/skills/dialogue-pass` skill, the opening-sequence content plan (3 exclusive
layers, decisions.md §Story & Dialogue), and LOCKED text for the #43 lore crawl (7
cards), the #43 town tour (6 cards, all ten towns), and the full ch00 opening scene
(briefing-with-interrupt staging). All pushed through `ch00 opening scene script locked`.

**Live checklist = GitHub issue #20.** HANDOFF = current state + next steps.

---

## NEXT SESSION (in order)
1. **Invoke the `Skill` tool: `dialogue-pass`** — it was created mid-session so this
   session couldn't invoke it; next session it registers. It encodes the whole workflow
   (sources → voice bibles → beats → 2-3 variants, Nicolas picks → budgets → gates).
   This session was its hand-run dry run; next session runs it for real.
2. **Review pass over everything locked so far** (Nicolas: "I'm sure they are fine, I
   just want to be thorough") — read each against its voice bible + register budgets:
   - Lore crawl 7 cards + town tour 6 cards: `campaigns/.../events/opening-montage.yaml`
   - Opening scene script: ch00 YAML `events:` → `script:` block
   Check: banned-list violations, card word budgets (lore/narration.md), box line
   lengths vs GBA ~2-line boxes, book-quote fidelity (PDF page = printed+1).
3. **Slot 4 — mid-fight frost line** (boss_low_hp, one screen; vanilla analog 0x914).
   Drafted-but-not-shown variants exist in last session's transcript spirit: wound
   rimes over (recommended) / pity for the old hunters / first crack of doubt.
   Bring 2-3 via AskUserQuestion picker.
4. **Slot 5 — the three quote msgs** (Sephek 0x0936 / Hlin 0x0917 / Scramsax 0x0C25
   placeholders in `inject_prologue` step 5; YAML drafts exist for Sephek + Scramsax).
5. **Slot 6 — ending cutscene** (beats locked in ch00 YAML event description: shards →
   rime-over → gone, NO corpse; Hlin's quiet "bigger than one bounty" beat ≤ ~10 lines;
   cut to black on a Northlook location card. Northlook hiring scene = ch01 opening now).
6. **Wire slots 3-6 into the ROM** (`inject_prologue`: real `EventScr_Ch1_BeginningScene`
   cutscene + ending block + quote msgs via `set_message_body`) → `make` green →
   `verify_text.py` → playtests → in-game eyeball WITH Nicolas (first real showing of
   guest portraits) → only then commit art-visible text. Slots 1-2 stay parked in
   `events/opening-montage.yaml` until #43.

## Working agreements discovered this session (now also in memory/skill)
- **Answer questions as turn-ending text; NEVER stack an answer right before an
  AskUserQuestion** — pre-tool text doesn't render for Nicolas; he only sees the picker
  (burned twice; memory `feedback_answer_before_picker`).
- Pickers (AskUserQuestion with full-text previews) are GOOD for variant choices —
  Nicolas asked for them ("can you prompt me the options to choose").
- He challenges staging logic, productively — the briefing-with-interrupt restructure
  ("why would she describe his crimes to HIM?") and "write montage + prologue in
  sequence so we don't rewrite" were both his calls. Bring him dramaturgy, not just lines.

## Current state
- ✅ ch00 playable end-to-end with full art (map/units/win-lose/title/portraits);
  `make` green, `make check` clean, playtest win/gameover PASS (carried from 06-09).
- ✅ Dialogue system: voice bibles `lore/{hlin-trollbane,scramsax,sephek-kaltro,narration}.md`;
  skill `.claude/skills/dialogue-pass/SKILL.md`; decisions.md §Story & Dialogue (3-layer
  content allocation; Northlook→ch01; Sephek corpse imagery reserved for his true death).
- ✅ LOCKED + pushed: lore crawl (7 cards) + town tour (6 cards) in
  `events/opening-montage.yaml`; opening scene script in ch00 YAML (location card "The
  Eastway"; Hlin-briefs-Scramsax V1; "It cannot." interrupt; confession V-A; button V3
  with Hlin's last word). ch01 opening description now owns the Northlook hiring.
- ⚠️ NOTHING is wired into the ROM yet — all locked text is YAML-parked. Quote msgs +
  ending scene in `inject_prologue` are still vanilla placeholders.
- ⚠️ Could not comment the content plan onto issue #43 (permission classifier blocks gh
  issue comments) — decisions.md carries it; Nicolas can paste a pointer if wanted.
- ⚠️ Scramsax Hero mug still needs the [F2E] license recheck before distribution.

## Gotchas (carried)
- Story text: `texts/texts.txt` via `set_message_body`, msg ids from the decomp; `make`
  reruns build_campaign and overwrites manual decomp edits. Odd-length strings: pad with
  [.] (terminator parity). Gate: `python3 tools/verify_text.py`.
- Synthetic macOS keypresses don't reach mGBA; in-emulator Lua is the path.
- The Frostmaiden book is at `References/icewind-dale-...pdf` **inside the repo's
  `references/` symlink target** = `/Users/Yonick/Documents/D&D/5E/...` (HANDOFF's old
  path was stale); DM notes PDF: `/Users/Yonick/Documents/Claude/Projects/Manchego
  Stars / Fire Emblem Game/References/DungeonMasterNotesIcewindDale.pdf`.
- PDF page = printed page + 1 (Hlin/Sephek brief: printed pp.22-23 → PDF 23-24).

## Blockers
- None. (Dialogue review + slots 4-6 are collaborative — that IS the working mode.)

## Key files
- `campaigns/rime-of-the-frostmaiden/events/opening-montage.yaml` — LOCKED #43 text
  (crawl + tour), parked until the #43 slice wires it.
- `campaigns/.../chapters/ch00-prologue-a-dagger-of-ice.yaml` — opening-scene `script:`
  block (locked), ending-scene beat description, draft quote lines.
- `campaigns/.../lore/{hlin-trollbane,scramsax,sephek-kaltro,narration}.md` — voice
  bibles + register budgets (the review pass's rubric).
- `.claude/skills/dialogue-pass/SKILL.md` — the workflow to invoke.
- `docs/decisions.md` §Story & Dialogue — content allocation + workflow decision record.
- `tools/build_campaign.py` — `inject_prologue` (begin scene step 3, ending block,
  quote msgs step 5) — where slots 3-6 get wired.
- `fireemblem8u/src/events/prologue-eventscript.h` — vanilla scene shapes (0x90D
  briefing / 0x910 spawn / 0x914 mid-fight / 0x918 quiet ending beat).

## Memory
- [[manchego-stars-project]] · [[feedback_collaborative_story_planning]] ·
  [[feedback_answer_before_picker]] · [[feedback_story_sources_of_truth]] ·
  [[feedback_use_decomp]] · [[manchego_stars_text_terminator_parity]] ·
  [[feedback_show_before_committing_art]] · [[manchego-stars-automated-playtests]]

## Standing rules
Combat = pure vanilla FE. Story/dialogue = collaborative (variants → Nicolas picks);
art look-picks wait for his OK. Auto-push to main once green; never commit the
`fireemblem8u` submodule pointer. Playtests machine-run for logic, Nicolas for feel.
