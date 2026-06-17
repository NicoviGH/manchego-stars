# Handoff: Ch1 (#21) — ending dialogue LOCKED + ALL ending art DONE (Duvessa + Baxby). NEXT = wiring: Baxby unit/sprite/face → ending eventscript → Bryn Shander BG → ch02 host.

**Date:** 2026-06-17 (session 5)
**Where we are:** Ch1 "The Iron Trail" is fully playable and written through the battle.
The **ch01 ending scene ("The Rolling Cheddar") is WRITTEN + LOCKED** in the YAML, and **all
its art is done**: Duvessa Shane's portrait (wired), Baxby's map sprite (hand-painted by
Nicolas), and Baxby's portrait (committed, not yet wired). What remains is **engine WIRING**
(no more art/feel decisions except the Bryn Shander BG): consume the locked ending script in
the eventscript, wire Baxby as a recruit + his face/sprite, and host ch02 so the ending stops
landing on vanilla Ch3.

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

## Accomplished (session 5, committed + pushed)
- **ch01 ending scene "The Rolling Cheddar" WRITTEN + LOCKED** (co-written with Nicolas) — recorded as
  `events[chapter_end].script` in `ch01-the-iron-trail.yaml`. Beats A–F: Duvessa thanks them → Council
  commission + grants the **wrecked trail sled** (she gifts it; dwarves wrote it off) + points west to
  **Targos** → **Wolfram** asks Hruna for the recovered **iron** to armor it (Hruna grants) → **RBG**
  over-engineers the repair + names it the **Rolling Cheddar** → **Meesmickle** dry button ("a dry
  corner for me… I'll allow it") → **Marty** wins over **Baxby** the axe-beak with food/shelter (first
  recruit; Baxby = dignified hard-worker, not mean) → Duvessa "Targos is expecting weather. Better
  hurry." Velynne's orb hook stays HELD for the ch02 cold-open. **"iron" not "steel"** throughout.
  New **`lore/duvessa-shane.md`** voice bible (earnest young stateswoman; book p.32–33).
- **Duvessa portrait DONE + wired** — a palette recolor of **vanilla Selena** (Nicolas's base pick:
  her fur-shoulder bust reads as a winter official; matches book p.33). `portraits/duvessa.py`
  reproducible generator (decodes clean Selena from git HEAD → RGB recolor → 96×80 indexed) +
  `duvessa.png`/`_preview.png`; `GUEST_PORTRAIT_MAP['duvessa']='Selena'` (collision-free). Approved
  look: brown hair, navy coat, white fur, blue earring, sleeve kept brown.
- **Baxby map sprite DONE** — `map_sprites/baxby.png` (32×96, 3 frames, cast palette). Reskinned from
  the FE-Repo **Chocobo Rider {SkidMarc25}** (rider + lance stripped, snowy tundra recolor); **hand-
  painted by Nicolas** in `tools/map_sprite_editor.py` (I prepped the canvas + donor reference, he did
  the pixels). 3 frames reused for both idle + walk (Meesmickle pattern). NOTE: the editor's **Finish**
  button is broken (Save works) — minor tool bug to fix.
- **Baxby portrait DONE** (committed, not yet wired) — `portraits/baxby.png`. Ref = the **axe-beak art
  from the Frostmaiden book, modified with Gemini** (Nicolas), then `ref_to_bust.py --crop
  780,18,1920,940 --flip-h --zoom 0.88` (max size with the whole beak clear of the dead corners).
  Credited in CREDITS.md (WotC-derived + AI-assisted + the Chocobo base). Render params still need to
  move into a `baxby.yaml` `art.render` block at wiring.
- **Gemini note:** I can't drive Gemini directly (API key gets 403 on image endpoints; the nanobanana
  MCP is pinned to a retired model → 404). Portraits go the proven route: **Nicolas generates on his
  side**, hands me the PNG, I run the bust pipeline.

## Current state
- ✅ Ch1 engine + all in-battle content (entry, lord-select, deploy cap, houses, sign/body, Izobai
  taunt + death, Seize win). Combat is vanilla-parity. Ending dialogue LOCKED + Duvessa face ready.
- ⚠️ **ending NOT wired in-game yet** — `EventScr_Ch2_EndingScene` is still the placeholder
  (`TEXTSHOW(0x954)` "The iron ingots are recovered." + `MNC2(0x3)`). The locked YAML script is not
  yet consumed.
- ⚠️ **ch01 ending lands on vanilla Ch3** (`MNC2(0x3)`) until ch02 is wired.

## Next steps (priority order) — ALL WIRING now (art is done); no art/feel input needed except the BG
1. **Wire Baxby** (3 sub-parts):
   (a) **cutscene face** — he SPEAKS in the ending; add a `GUEST_PORTRAIT_MAP` entry (`'baxby': <some
   collision-free vanilla slot>`) so `portraits/baxby.png` dresses it, and map the `baxby:` speaker →
   that slot's FID in the ending staging.
   (b) **recruit unit** — purchasable @200 in `post_chapter`; author `baxby.yaml` (class = **cavalier**,
   Seth chassis; record the `art.render` block: ref `References/PCs/Baxby.png`, crop [780,18,1920,940],
   flip_h, zoom 0.88). Decide his deploy/recruit wiring (he also appears in ch02 deployment if bought).
   (c) **map sprite injection** — wire `map_sprites/baxby.png` (3-frame 32×32, idle+walk reuse) for his
   unit; guest-sprite path per [[manchego_stars_guest_map_sprite_wiring]] (cast palette → cast bank).
2. **Wire the ending eventscript** (`inject_ch01` → `EventScr_Ch2_EndingScene`). Mirror the Beat-1
   opening machinery: split the locked `chapter_end` script on `beat_break` (A–F), allocate ~6 dead
   message ids + a location card, build `ending_staging` (speakers→podium/FID: `duvessa`→FID_Selena,
   `hruna`→FID_VillagerWoman, `baxby`→its slot, cast via PORTRAIT_MAP), `_script_to_message` each beat
   with REMA between, then victory sting → `MNC2`. 7 speakers across 6 beats — lean on podium eviction.
3. **Bryn Shander gate/market BG** — the ending is scenic (in-town). Needs a `BACG` background (reskin
   a vanilla town BG or build one; show-before-commit — the one remaining art piece). Placeholder BG OK until then.
4. **Wire ch02** ("cold-welcome", `unlocks_chapter` in ch01 `post_chapter`) so the ending's `MNC2`
   targets a real ch02 host slot, not vanilla Ch3. Mirror the inject_ch01 hosting pattern.
5. **Carried:** #29 world map; pre-distribution license rechecks (Scramsax Hero mug, AlexYTXG
   Bandit-Peg, **Chocobo {SkidMarc25}** — no [F2E] tags; Fire Imp + Cynon villager ARE [F2E]);
   ch02+ YAML `ea_file:` cleanup; fix the map_sprite_editor **Finish** button.

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
