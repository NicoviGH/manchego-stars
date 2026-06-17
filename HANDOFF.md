# Handoff: Ch1 (#21) — ending cutscene WIRED + plays in-game (Duvessa + Baxby faces). NEXT = Baxby recruit UNIT + map-sprite injection → Bryn Shander custom BG → ch02 host.

**Date:** 2026-06-17 (session 6)
**Where we are:** Ch1 "The Iron Trail" is fully playable AND the **ending cutscene "The Rolling
Cheddar" now plays in-game** — the locked `chapter_end` script is consumed by `inject_ch01` into
`EventScr_Ch2_EndingScene` (scenic BACG + "Bryn Shander" card + one `Text()` per beat A–F, all 7
speakers' faces staged with the 4-face budget). **Baxby's cutscene face is wired** (rides the vanilla
Forde slot). What remains: Baxby's recruit **UNIT** + axe-beak **map-sprite** injection (his bust +
cutscene face are done), the custom **Bryn Shander market BG** (a `BG_GATE` placeholder is in now;
the one remaining art piece, show-before-commit), and **hosting ch02** so the ending stops landing on
vanilla Ch3.

`make` green · `verify_text` 3404/0 · playtests PASS (ch00 win/gameover, ch01 entry, ch01win — the
last now runs the ending through all 6 beats and advances).

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

## Accomplished (session 6, committed + pushed — `4863fe8`)
- **Ending cutscene "The Rolling Cheddar" WIRED + plays in-game** (`4863fe8`). `inject_ch01` now
  consumes the locked `chapter_end` script into `EventScr_Ch2_EndingScene`, mirroring Beat 1:
  `REMOVEPORTRAITS` → `BACG` → `FADU` → "Bryn Shander" `BROWNBOXTEXT` card → one `Text()` per beat
  (A–F) → `FADI` → `MNC2`. Each `Text()`'s trailing `REMA` clears faces so the 4-face budget resets
  per beat. New constants `CH01_ENDING_CARD_MSG=0x94C` + `CH01_ENDING_MSGS=(0x946..0x94B)` (same dead
  slot-2 pool as Beat 1). Staging (`end_stage`/`end_home`/`end_preload`/`end_overrides`): **Duvessa
  hosts mid-right**, party speaks mid-left, the other beat speaker(s) opposite her; **beat E: Baxby
  evicts Duvessa's mid-right podium** (`[OpenMidRight][ClearFace]` step-out) as she points to the
  market and the bird steps up. Marty (Seth) preloads as a silent listener in A/B/F so she's not
  addressing an empty room. Decoded faces verified: marty=Seth, duvessa=Selena, wolfram=Franz,
  hruna=VillagerWoman, rbg=Moulder, meesmickle=Gilliam, **baxby=Forde**.
- **Baxby's cutscene face wired** — `GUEST_PORTRAIT_MAP['baxby']='Forde'`. Forde is a vanilla Cavalier
  (matches Baxby's donor class) absent from ch00–08, so dressing `FID_Forde` with `baxby.png` is
  collision-free; `inject_portraits` now generates `portrait_Forde_*`. His recruit unit + map sprite
  will ride this SAME Forde character slot when wired.
- **BG = `BG_GATE` placeholder** ("back inside the Bryn Shander gate") — reads fine as a stand-in; the
  custom winter market BG is the one remaining ending art piece (show-before-commit).
- Decision recorded in `docs/decisions.md` ("Ch1 ending … wired the same way as Beat 1").

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
  taunt + death, Seize win). Combat is vanilla-parity.
- ✅ **Ending cutscene WIRED + plays in-game** — `EventScr_Ch2_EndingScene` consumes the locked
  `chapter_end` script (6 beats A–F, all 7 faces incl. Baxby on the Forde slot). Plays over a
  `BG_GATE` placeholder. Needs Nicolas's in-game **motion/feel** pass.
- ⚠️ **Baxby is a cutscene face only** — his recruit UNIT + map-sprite are NOT wired yet (he can speak
  in the ending but can't be bought/deployed).
- ⚠️ **BG is a placeholder** (`BG_GATE`) — custom Bryn Shander market BG pending (show-before-commit).
- ⚠️ **ch01 ending lands on vanilla Ch3** (`MNC2(0x3)`) until ch02 is hosted.

## Next steps (priority order) — wiring; no art/feel input needed except the BG + the in-game feel pass
1. **Baxby's in-game motion/feel review** (Nicolas, in-game) — boot the ROM, seize ch01, watch the
   ending play. Confirm the staging (Duvessa mid-right, the beat-E step-out) reads right.
2. **Wire Baxby's recruit UNIT** — `npcs/baxby.yaml` is authored (Cavalier, Franz donor). He rides the
   **Forde** character slot (same slot his cutscene face already dresses). Needs: purchasable @200 in
   `post_chapter.units_available_to_recruit` (NB: `post_chapter` is NOT consumed by build_campaign yet
   — recruit/market machinery is net-new), a name entry ("Baxby" on the Forde slot), and his Cavalier
   class/stats/inventory wired to a free unit slot. He also needs to appear in ch02 deployment if bought.
3. **Baxby map-sprite injection** — wire `map_sprites/baxby.png` (3-frame 32×32, idle+walk reuse) for
   his unit; guest-sprite path per [[manchego_stars_guest_map_sprite_wiring]] (cast palette → cast bank).
4. **Custom Bryn Shander market BG** — replace the `BG_GATE` placeholder (`CH01_ENDING` BACG in
   inject_ch01) with a winter town/market scenic BG (reskin a vanilla town BG or build one;
   show-before-commit — the one remaining ending art piece).
5. **Wire ch02** ("cold-welcome", `unlocks_chapter` in ch01 `post_chapter`) so the ending's `MNC2`
   targets a real ch02 host slot, not vanilla Ch3. Mirror the inject_ch01 hosting pattern.
6. **Carried:** #29 world map; pre-distribution license rechecks (Scramsax Hero mug, AlexYTXG
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
