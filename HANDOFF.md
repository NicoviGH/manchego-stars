# Handoff: Ch1 (#21) — dialogue pass DONE & committed. NEXT = the ch01 ENDING scene (Duvessa + Baxby; needs art) → then wire ch02.

**Date:** 2026-06-17 (end of session 4)
**Where we are:** Ch1 "The Iron Trail" is fully playable and written through the battle.
The opening Northlook scene + all trail beats are committed (`b0c03cf`). The one remaining
ch01 gap is the **ending cutscene** (currently a one-line placeholder), which needs new
**art** (Duvessa + Baxby). After that, **ch02** needs wiring so the ending stops landing
on vanilla Ch3.

`make` green · `verify_text` 3404/0 · playtests PASS (ch00 win/gameover, ch01 entry, ch01win).

## Accomplished (this session, committed)
- **Whole ch01 dialogue pass** (`b0c03cf`), co-written interactively with Nicolas:
  - **Beat 1 Northlook scene** (`9b851cf`) — scenic `bg_Fireplace`, the 4-face-slot fix
    (`_script_to_message` podium eviction), two-shot staging, scenic Darkling-Woods lord-select.
  - **Trail beats** — road sign + dismembered sled-driver folded into one trailhead trigger
    (`0x955`+`0x956`); two house hints reskinned from **vanilla Ch1's own house quotes**
    (`0x93B`/`0x93C`); **Izobai** voice bible + turn-1 taunt (spare `EventScr_Ch2_Turn2Player`) +
    death quote (`0x961`); Braulo's commit line de-collectivised ("Fair price for honest work.").
  - **'Ol Bitey** mounted over the hearth via `inject_northlook_bitey` (idempotent in-palette BG edit).
  - **`_term_pad`** helper for the Huffman terminator-parity `[.]` pad (hand-written narration bled
    into the next message without it).
- Design depth recorded in `docs/decisions.md` ("Multi-speaker cutscene faces" + "Ch1 trail beats").

## Current state
- ✅ Ch1 engine + all in-battle content (entry, lord-select, deploy cap, houses, sign/body, Izobai
  taunt + death, Seize win). Combat is vanilla-parity.
- ⚠️ **ch01 ending scene is a placeholder** — `EventScr_Ch2_EndingScene` = victory sting +
  `TEXTSHOW(0x954)` ("The iron ingots are recovered.") + `MNC2(0x3)`. The real scene isn't written.
- ⚠️ **ch01 ending lands on vanilla Ch3** (`MNC2(0x3)`) until ch02 is wired.

## Next steps (priority order)
1. **Write + wire the ch01 ending scene** (`events[chapter_end]` in the YAML → `EventScr_Ch2_EndingScene`).
   Per the DM notes: **Duvessa Shane** (Speaker of Bryn Shander) arrives with two guards, thanks the
   party, pays the reward, and **hires them for ongoing Ten-Towns security — points them to Targos**
   (frost-druid unrest). Braulo asks about sled dogs → **Baxby the axe-beak** is for sale (200 GP;
   `post_chapter.units_available_to_recruit`). Use the **dialogue-pass skill** (variants → Nicolas
   picks; read voice bibles first). Velynne Harpell's stolen-orb hook is HELD for the **Ch2 cold-open**
   (DM notes: "as the party leave town… head west to Targos"), so don't spend it here.
2. **ART NEEDS (custom, show-before-commit)** — gate the ending scene:
   - **Duvessa Shane portrait** — recurring NPC (rides a guest face slot like Hlin/Hruna; add to
     `GUEST_PORTRAIT_MAP`). Mine `References/` first ([[feedback_check_references_for_art]]); she's a
     book NPC (Ten-Towns). Pipeline: `tools/portrait_tool.py` / `ref_to_bust.py`
     ([[project_manchego_stars_portrait_pipeline]]). Likely also a **Duvessa voice bible** (she recurs).
   - **Baxby the axe-beak** — needs a **portrait** (shop/recruit mug) **and a map sprite** (axe-beak
     mount). Map-sprite recipe: [[manchego_stars_guest_map_sprite_wiring]] + `tools/map_sprite_tool.py`;
     base candidates in the FE-Repo ([[reference_fe_repo]] — pegasus/wyvern/bird-type). Baxby is a
     mount, probably non-speaking (no full bible; `npc-bench` at most).
3. **Wire ch02** ("cold-welcome", `unlocks_chapter` in ch01 `post_chapter`) so the ending's `MNC2`
   targets a real ch02 host slot, not vanilla Ch3. Mirror the inject_ch01 hosting pattern.
4. **Carried:** #29 world map; pre-distribution license rechecks (Scramsax Hero mug, AlexYTXG
   Bandit-Peg — no [F2E] tags; Fire Imp + Cynon villager ARE [F2E]); ch02+ YAML `ea_file:` cleanup.

## Key files
- `campaigns/.../chapters/ch01-the-iron-trail.yaml` — `events[chapter_end]` (ending scene to write),
  `post_chapter` (Baxby recruit @200, `unlocks_chapter: ch02-cold-welcome`, `gold_reward: 300`).
- `tools/build_campaign.py` — `inject_ch01` (the ending = `EventScr_Ch2_EndingScene` block, currently
  placeholder `0x954`/`MNC2(0x3)`); `inject_northlook_bitey`; `_script_to_message` (podium eviction +
  `preload=` listeners + `width`); `_term_pad`; `gDefeatTalkList`; `PORTRAIT_MAP`/`GUEST_PORTRAIT_MAP`.
- `campaigns/.../portraits/` — `guest_vendor_busts.py` (+ vendored bases); add Duvessa/Baxby here.
  `tools/portrait_tool.py`, `tools/ref_to_bust.py`, `tools/map_sprite_tool.py`.
- `campaigns/.../lore/*.md` — voice bibles (7 PCs + hlin/scramsax/izobai/narration/npc-bench). Add
  Duvessa. `.claude/skills/dialogue-pass` — the co-writing skill.
- `references/References/` — Frostmaiden book (image-only PDF; `pdftoppm`) + DM notes (`pdftotext`) +
  Ten-Towns maps; mine for Duvessa likeness + the ending's plot facts.
- `tools/verify_text.py` (text gate) · `tools/playtest/run.sh ch01win|recordch01` (logic + GIF).

## Gotchas (carried)
- Story text lives in YAML/build strings → `make` regenerates message bodies; gate with `verify_text`.
- **Hand-written message bodies: run through `_term_pad`** (odd printable count → `[.]` pad, or the
  0x00 terminator doesn't stand alone and the decoder bleeds into the next message).
- Map bubbles wrap ~29 chars (clip); scenic Text_BG ~42. `[A][LF]` = page break; every non-terminal
  `[A]` must be `[LF]`-followed; same-speaker turns coalesce. Faces: 4 slots max (`_script_to_message`
  handles eviction). `BACG` is BG3; returning to the battle map after a scenic scene needs `LOMA`.
- gDefeatTalkList: chapter-keyed entries at the HEAD, never after `{.pid=-1}`. `CONST_DATA` for
  injected tables (rodata is discarded). **Never commit the `fireemblem8u` submodule pointer** — it's
  a build artifact (restore_vanilla_sources + inject steps rebuild it); stage repo files explicitly.
- Built ROM lands at `fireemblem8u/fireemblem8.gba`. Synthetic macOS keypresses don't reach mGBA
  (in-emulator Lua only). Nicolas can't see inline renders — save to `map-review/` and `open`
  (PNG → Preview; **GIF → `open -a Safari`**). Izobai is female; Pinky is male.
- Vanilla facts: `git -C fireemblem8u show HEAD:<file>`. Frostmaiden book PDF page = printed + 1.

## Memory
[[manchego-stars-project]] · [[project_manchego_stars_campaign_structure]] · [[project_manchego_stars_dm_notes]] ·
[[feedback_story_sources_of_truth]] · [[feedback_collaborative_story_planning]] · [[feedback_prep_before_drafting_dialogue]] ·
[[feedback_check_references_for_art]] · [[feedback_custom_art_lever]] · [[feedback_nicolas_not_an_artist]] ·
[[feedback_show_before_committing_art]] · [[feedback_sharing_visual_drafts]] · [[project_manchego_stars_portrait_pipeline]] ·
[[manchego_stars_guest_map_sprite_wiring]] · [[reference_fe_repo]] · [[feedback_vendor_community_assets]] ·
[[manchego_stars_text_terminator_parity]] · [[feedback_fe_name_truncation]] · [[manchego-stars-automated-playtests]] ·
[[feedback_answer_before_picker]] · [[feedback_clean_doc_rewrites]] · [[project_manchego_stars_cast_notes]] ·
[[feedback_use_decomp]] · [[feedback_proactive-push]]

## Standing rules
Combat = pure vanilla FE; field parity with vanilla ch N is doctrine. Custom art on every sprite part
where it matters, follow concept faithfully, one artwork at a time, **show before committing**.
Story/dialogue = collaborative (variants → Nicolas picks; read ALL relevant voice bibles first; use
the dialogue-pass skill). Auto-push to main once green; never commit the `fireemblem8u` submodule
pointer. Playtests machine-run for logic, Nicolas for feel.
