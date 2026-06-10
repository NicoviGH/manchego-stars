# Handoff: **ch00 dialogue pass COMPLETE & WIRED (GIF-review approved). NEXT = pick with Nicolas: ch01 dialogue pass (`/dialogue-pass`, Northlook hiring scene) or the #43 opening-montage wiring (crawl + tour text is locked and parked).**

**Date:** 2026-06-10
**Last session:** Ran the dialogue-pass skill for real (first invocation): review pass over
all locked ch00 text (added a §Craft check to the skill — quality, not just compliance),
two craft fixes Nicolas picked (Scramsax "Save your sermon", crawl card 6 "Winter has not
relented"), locked slots 4-6 via pickers (boss line / 3 battle quotes / ending scene), then
WIRED everything into the ROM and got it GIF-reviewed and approved. All pushed through
`c119fcc`.

**Live checklist = GitHub issue #20.** HANDOFF = current state + next steps.

---

## NEXT SESSION (in order)
1. **Pick with Nicolas:** ch01 dialogue pass (the Northlook hiring scene now OWNS the
   location card + the hiring beat — ch00 ends on a fade-out, no tease) **or** wire the
   #43 opening montage (lore crawl + town tour text locked in
   `events/opening-montage.yaml`, awaiting the boot-sequence slice).
2. Whichever runs: invoke the **`dialogue-pass` skill** — it now carries the full recipe
   (sources → voice bibles → variants with FULL QUOTES in AskUserQuestion *descriptions*,
   never previews — they don't render for him → craft check → insertion gates → GIF
   review via `run.sh record` → his OK → commit).
3. Scramsax Hero mug still needs the [F2E] license recheck before distribution (carried).

## Working agreements discovered this session
- **Review in-engine text as GIFs, not stills** ("use this format going forward"):
  `tools/playtest/run.sh record` → dedupe → GIF → `open -a Safari`. Static shots catch
  the typewriter mid-stroke and false-alarm as cut-off text. (decisions.md §Story &
  Dialogue; memory `feedback_sharing_visual_drafts`.)
- **AskUserQuestion previews don't render for Nicolas** — full quote text goes in each
  option's `description`. (memory `feedback_answer_before_picker`.)
- The craft check (cover-the-name test, box buttons, device budget…) is now a standing
  section of the skill — "functional is a finding, not a pass."

## Current state
- ✅ **ch00 is DONE end-to-end**: map, units, win/lose, title, portraits, AND all
  dialogue wired + in-engine approved. `make` green, `verify_text` 0 runaway,
  win/gameover playtests PASS, GIF review OK'd.
- ✅ Dialogue wiring is GENERATED from the chapter YAML's locked `script:` blocks
  (`_script_to_message` in `tools/build_campaign.py`) — YAML stays the SoT; msg ids ride
  never-loaded vanilla slots (0x664 card / 0x90D briefing / 0x90E confrontation /
  0x914 battle quote / 0x918 ending / 0x936-0x917-0xC25 quotes).
- ✅ New Game select + save screen now show "Prologue: A Dagger of Ice" (slot 0's
  chapTitleId/text pointed at the host's).
- ✅ Playtest harness grew `scenes` (per-page contact sheet) and `record` (continuous
  frames → review GIFs) scenarios.
- ⚠️ Slots 1-2 (lore crawl + town tour) stay YAML-parked until the #43 slice.
- ⚠️ ch01+ chapter YAMLs still carry aspirational `ea_file:` fields (schema cleanup
  candidate — wiring actually goes through build_campaign decomp patches).

## Tried but didn't work (text-engine lessons — now encoded in the skill + code comments)
- **Text_BG(BG_PLAIN_2)** for scenes: vanilla's GREEN summer plains in a two-year
  winter. FE8 ships no snow background → on-map text (vanilla 0x910/0x911 convention).
- **40-char lines on-map**: bubbles clip at ~29 chars (Text_BG tolerates ~42).
- **Lazy right-face load mid-message + later multi-page turns**: empty offscreen
  bubbles. Root cause (decomp-traced, scene.c): `GetStrTalkLen` does NOT stop at [A]
  (+12px and keeps measuring to the next speaker's printable), and `PutTalkBubble`'s
  right-side branch has NO x clamp (`x = 29 - width`, left side clamps) → merged
  same-speaker turns overflow → tilemap wrap. Fix: coalesce consecutive same-speaker
  turns into one block, every non-terminal [A] is [LF]-followed; boss "steps out" via a
  message SPLIT with the enemy LOAD1 between (vanilla 0x910 shape).

## Blockers
- None.

## Key files
- `campaigns/.../chapters/ch00-prologue-a-dagger-of-ice.yaml` — all locked scripts +
  quotes (the dialogue SoT; trigger `boss_battle` = first-engagement quote, FE-native).
- `campaigns/.../events/opening-montage.yaml` — LOCKED #43 text, parked.
- `campaigns/.../lore/{hlin-trollbane,scramsax,sephek-kaltro,narration}.md` — voice bibles.
- `.claude/skills/dialogue-pass/SKILL.md` — workflow incl. craft check + encoding gotchas.
- `tools/build_campaign.py` — `_script_to_message` / `_wrap_fe_lines` (encoding rules,
  decomp-traced rationale) + `inject_prologue` steps 3/4c/5b.
- `tools/playtest/run.sh scenes|record` + `harness.lua` — contact-sheet & GIF capture.
- `docs/decisions.md` §Story & Dialogue — content allocation, GIF-review convention.

## Gotchas (carried)
- Story text: YAML `script:` → build_campaign generates bodies; `make` reruns
  build_campaign and overwrites manual decomp edits. Gate: `python3 tools/verify_text.py`.
- Odd-length NAME strings: pad with [.] (terminator parity; `name_message_body` does it).
- Synthetic macOS keypresses don't reach mGBA; in-emulator Lua is the path.
- Frostmaiden book: `references/References/icewind-dale-...pdf` (symlink →
  `/Users/Yonick/Documents/D&D/5E/`); DM notes:
  `/Users/Yonick/Documents/Claude/Projects/Manchego Stars / Fire Emblem Game/References/DungeonMasterNotesIcewindDale.pdf`.
- PDF page = printed page + 1 (Cold Open boxed text: printed p.22 → PDF 23).

## Memory
- [[manchego-stars-project]] · [[feedback_collaborative_story_planning]] ·
  [[feedback_answer_before_picker]] · [[feedback_sharing_visual_drafts]] ·
  [[feedback_use_decomp]] · [[feedback_show_before_committing_art]] ·
  [[manchego-stars-automated-playtests]] · [[manchego_stars_text_terminator_parity]]

## Standing rules
Combat = pure vanilla FE. Story/dialogue = collaborative (variants → Nicolas picks; full
quotes in picker descriptions); in-engine text review = GIFs via `record`, wait for his
OK before committing art-visible text. Auto-push to main once green; never commit the
`fireemblem8u` submodule pointer. Playtests machine-run for logic, Nicolas for feel.
