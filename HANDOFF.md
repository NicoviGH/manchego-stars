# Handoff: Ch1 (#21) — reusable DEV PLACEHOLDER for unbuilt chapters (RBG cheese pun → title); faceless-narration box bug fixed; economy reconciled to vanilla. NEXT = host ch02 (Baxby's recruit unit falls out of it as a one-liner).

**Date:** 2026-06-17 (session 8)
**Where we are:** Ch1 "The Iron Trail" is fully playable and content-complete enough to ship for
playtest: the ending cutscene "The Rolling Cheddar" plays cleanly and now lands on a **reusable dev
placeholder** instead of vanilla Ch3 — RBG delivers a "still under construction, thanks for
playtesting" cheese pun over the campfire BG, then returns to the title screen. This session also
**fixed the faceless-narration box** (Marty's "leans in..." stage line rendered as a cramped sliver +
corrupted his next line) and **reconciled the economy to vanilla FE8** (no flat per-chapter gold
bonus; ch01 is a net wash). The remaining ch01→ch02 work is now **hosting ch02**; Baxby's recruit
unit falls out of that as a one-liner (see the net-new correction below).

`make` green · `verify_text` 3404/0 · playtests: recordending PASS (ending + placeholder → title);
ch01win re-verified for the new title-return path; recordprep unchanged.

## Accomplished (session 8, committed + pushed)
- **Reusable DEV PLACEHOLDER for unbuilt chapters** (`c5f7703`). A chapter whose `unlocks_chapter`
  target isn't hosted yet now lands on `dev_placeholder_scene()` instead of `MNC2`'ing onto a leftover
  vanilla map: `REMOVEPORTRAITS` → `BACG(BG_FIREPLACE)` → RBG's "still under construction, thanks for
  playtesting" cheese-pun `Text()` → `MNTS` back to the **title screen**. Pure event scene (no
  map/units; `MNTS`/`EvtBackToTitle` = `GAME_ACTION_EVENT_RETURN`, eventscr.c). ch01's ending uses it
  (was dropping to vanilla Ch3). Punt it forward at each new boundary. Confirmed in-game (campfire +
  pun render clean). Copy lives in `DEV_PLACEHOLDER_LINE` — trivially editable.
- **Faceless-narration box bug FIXED** (`c5f7703`). Marty's "leans in close and breathes a soft
  puff…" stage line (a faceless `narration` speaker) rendered as a **cramped 2-char sliver** and
  **corrupted Marty's next line** (his bust shoved to the bottom edge). Cause: `_script_to_message`
  prepended an `[OpenMidLeft]` to faceless boxes — but `[Open*]` (textdefs 8–15) are portrait POSITION
  anchors, so opening one with no `[LoadFace]` anchors the window to an absent portrait's mouth.
  Faceless boxes now emit **no `[OpenX]`** → plain full-width box. Verified in captured frames.
- **Economy reconciled to vanilla FE8** (`c5f7703`). Decomp-checked: FE8 grants **no flat per-chapter
  clear bonus** (prologue/Ch1/Ch2 event scripts give zero gold); gold comes only from in-map sources —
  gold-giving villages (`SVAL(EVT_SLOT_3,n)` + `GIVEITEMTOMAIN(leader)`), sellable drops/gems, chests.
  ch01 is a **net wash** like vanilla Ch1 (~0 gold): the ~200g job pay is spent winning over Baxby (a
  **free story-recruit** — FE8 shops sell items, not units). `decisions.md §Economy` + ch01
  `post_chapter` reconciled (`gold_reward` dropped); the "two hundred gold" line is flavor only.
- **Playtest harness** (`c5f7703`, `e4efde8`). Added the `gProcScr_TitleScreen` symbol; `recordending`
  + `ch01win` now assert the ending reaches the **title** via the placeholder (the placeholder
  lengthened the post-seize path, so `ch01win`'s win budget went 3600→9000). Both PASS.
- **Title screen: gold "MANCHEGO STARS" logo** (`e7bff72`) — for the ALPHA bundle. The boot title's
  stylized gold "FIRE EMBLEM" is a ~10-letter one-off (only its own letters exist), so the missing
  letters are **hand-built**: `tools/gen_gold_title.py` draws each glyph as a shape mask and
  auto-applies the logo's per-row gold sheen + red-brown outline + drop shadow + italic shear (all read
  off the vanilla logo). `inject_title_screen()` regenerates `title_fire_emblem_logo.png` each build
  (gbagfx rebuilds the .4bpp.lz; palette + sprite OAM untouched), centered in the on-screen window so
  nothing clips. Confirmed in-game via `recordending` (shoots the title once it draws);
  `map-review/title-ingame-manchego-stars.png`. **Approved by Nicolas** (chose hand-built letterforms).

## Accomplished (session 7, committed + pushed)
- **Ending dialogue "flashing" fixed + Marty's spore-cough added** (`0581a35`). The flashing was real:
  silent **Marty preloads** faded in/out at every beat's `REMA`, and **Duvessa** faded out/in across
  the A→B boundary mid-speech. Fix: merged the two consecutive Duvessa beats (A+B → one continuous
  beat, loads once), **dropped all silent-listener preloads** (`end_preload` all `[]`), and split E
  into **E1/E2** so Duvessa clears at the beat boundary before Marty greets Baxby (no same-podium
  swap). Each beat now shows only its actual speakers; `REMA` fades land only between genuinely
  different casts (= scene transitions, not flicker). Marty's cough is a new **faceless `narration`
  speaker** in `end_stage` (a box with no portrait) before he speaks. `CH01_ENDING_MSGS` now 6 ids.
- **Faithful 60fps recorder** (`0581a35`). At `fpsTarget=240` mGBA frameskips ~4×, so the "frame"
  callback (and `shot()`) fired only every ~4th emulated frame — aliasing the engine's ~16-frame face
  fades into 1-frame "blips" (this is what made smooth fades *look* like flashing). `run.sh` now runs
  `record*` scenarios at **60fps + videoSync** (assert scenarios stay 240fps for speed) → callback
  every emulated frame → smooth fades.
- **Save-state CHECKPOINT system** (`c0e38e0`) — *the big tooling win*. Build a slow scene's lead-up
  ONCE at top speed, then replay just that section at viewable 60fps by loading an mGBA save state,
  instead of grinding ch00→ch01 every spot-check. `run.sh recordending` auto-builds the `seize`
  checkpoint at 240fps if missing/stale (ROM-hash-stamped), then records the ending at 60fps; a 2nd
  run on the same build **skips the grind (~88s vs ~8min)**. `recordprep` does the same for the
  Preparations/Pick Units screen. States live in `tools/playtest/states/` (gitignored).
- **GIF recording made standard** (`8655ccd`) — `tools/playtest/make_gif.py <scenario> <tag> --name X
  --fps N --open` assembles frames → `map-review/X.gif` → opens in Safari. Recipe documented in the
  `run.sh` header + `docs/decisions.md` "Automated playtests" (NOT memory — it's repo-sourced).
- **Pick Units black silhouettes FIXED** (`7bae15d`). `PrepUnit_InitSMS` loads our cast palette into
  OBJ bank 0x0B (`ApplyUnitSpritePalettes`) then zeros bank 0x0B with `CpuFastFill` — vanilla cleanup
  (no purple-faction units in prep) that blanked our cast (we repurpose 0x0B for the cast palette).
  New patch in `_inject_palette_bank_hook` drops that fill (`prep_unitselect.c` added to
  `PATCHED_DECOMP_FILES`). Roster now renders in full colour.
- **'Ol Bitey repainted** (`7ad96c9`). The cool-blue fish drew from a different 4bpp sub-palette than
  the mantle tiles (block 5, warm stone) → the converter garbled it to a black blob. Repainted as a
  dark smoked-fish using only block-5 indices. **Approved by Nicolas.**
- **Ending BG = vanilla `BG_NORMAL_VILLAGE`** (`41a341f`). We tried winterizing it but a palette swap
  just washes the village out, and the FE-Repo had no clean FE8-GBA snow-village BG (Village5Snow is
  real snow but 40px short → any fill looks tiled/stretched). Per Nicolas, use the vanilla village
  as-is and move on. (The `BG_GATE` placeholder is gone.)

## Tried but didn't work (session 7, still relevant)
- **Winterizing `BG_NORMAL_VILLAGE` via palette swap** — a recolor can only desaturate, can't ADD snow
  accumulation; over-whitening washed the walls out, restraining it left it "just desaturated."
  Abandoned → vanilla village.
- **FE-Repo `Village5Snow.bmp`** (real FE8 snow art, Nicolas's first pick) — the source is 240×**120**
  (bottom 40px is blue text-box filler). Filling the missing band three ways (tile the ground = visible
  slats; stretch = stretched; shift-down + sky-fill = streaked tree-tops) all looked bad. Abandoned.
- Lesson: there is **no drop-in full-frame FE8-GBA snowy-village BG** in the FE-Repo; a real custom
  winter town would need the Gemini pipeline (Nicolas generates → I convert), parked for later.

## Current state
- ✅ Ch1 engine + all in-battle content (entry, lord-select, deploy cap, houses, sign/body, Izobai
  taunt + death, Seize win). Combat vanilla-parity.
- ✅ **Ending cutscene plays clean** — flashing fixed, cough added, **faceless narration box fixed**,
  over `BG_NORMAL_VILLAGE`. 6 beats (A+B, C, D, E1, E2, F), all faces incl. Baxby on the Forde slot.
- ✅ **Ending lands on the dev placeholder → title** (no longer vanilla Ch3). `recordending` + `ch01win`
  PASS through to `gProcScr_TitleScreen`.
- ✅ **Economy is vanilla-faithful** — no flat per-chapter bonus; ch01 = net wash (see decisions.md).
- ✅ **Pick Units / deploy roster renders correctly** (palette fix). ✅ 'Ol Bitey reads as a fish.
- ⚠️ **Baxby is a cutscene face only** — recruit UNIT + map-sprite not wired yet. This is now a
  one-liner that rides **hosting ch02** (he's a free story-recruit = a ch02 blue `UnitDefinition`
  entry; see the net-new correction in Next steps). `npcs/baxby.yaml` authored (Cavalier, Franz donor,
  **Forde** slot).
- ⚠️ **Prep roster sprite overlap** (DEFERRED) — Braulo/Wolfram/Meesmickle/Baxby use 32×32 map sprites
  but the roster is pitched 16px, so adjacent sprites overlap. Fixing it is a deep/risky rewrite of
  FE8's prep scroll system (16px hardcoded in ~20 spots: sprite/cursor/error-box Y + `yDiff_cur` math
  + scrollbar; names on a hardware-scrolled BG2 tilemap). Cosmetic → parked pending a decision (defer
  vs dedicate a focused pass). **Awaiting Nicolas's call** (last open question of the session).

## Next steps (priority order)
> **Net-new correction (2026-06-17):** an earlier handoff called Baxby's "recruit/market machinery
> net-new." That conflated two things. **Recruiting a unit and carrying it across chapters is 100%
> vanilla** — a unit joins by being a blue `UnitDefinition` (`LoadUnit`/`LoadUnits`, bmunit.c) and
> persists via the save system, exactly like the existing roster. Even deducting gold is a vanilla
> event cmd (`EvtGiveMoneymAtSlot3NoPopup` → `EVSUBCMD_GIVETOSLOT3`, eventscr.c). The ONLY non-vanilla
> thing is a literal "shop sells a *character*" UI (FE8 shops sell items only) — and **we don't need
> it**: Baxby is a free story-recruit won over in the ending, so he's just a ch02 starting unit.

1. **Host ch02 "Cold Welcome"** — the real remaining work, and Baxby's recruit unit falls out of it as
   a one-liner. ch02 is designed in YAML but has **no build assets** (no map/`.mar`, no events, not
   hosted). Needs: a map (yaml says **reskin vanilla FE8 Ch2** — same layout, arctic palette, per
   [[project_manchego_stars_winter_reskin]]); the enemy roster/boss/reinforcements; chapter-start +
   inn cutscenes; hosting on the next chapter slot (mirror `inject_ch01`); then point ch01's ending at
   `MNC2(<ch02 slot>)` instead of `dev_placeholder_scene()`. **Map design is Nicolas-driven**
   ([[feedback_collaborative_map_design]]) — bring concepts before building.
   - **Baxby (rides ch02):** add "Baxby" name on the **Forde** slot + his Cavalier class/stats/inventory
     to ch02's blue `UnitDefinition` (he's a free recruit, so he just starts deployable in ch02);
     map-sprite injection per [[manchego_stars_guest_map_sprite_wiring]] (cast palette → purple bank,
     the bank the prep fix protects). `map_sprites/baxby.png` + bust are already committed.
2. **ALPHA title screen — DONE** (`e7bff72`, `f8b9621`, `3c212ff`). Gold "MANCHEGO STARS" logo
   (hand-built glyphs, `gen_gold_title.py`) + two-line cream serif subtitle "RIME OF THE /
   FROSTMAIDEN" (`gen_subtitle.py`, both baked into the logo graphic; the second logo sprite was
   repointed to Y=80 to carry the subtitle row, scroll banner dropped) + icy-blue backdrop with the
   two dragons removed (`title_main_background.gbapal` hue-set blue, dragon foreground blanked — both
   idempotent). Wired in `inject_title_screen`. `map-review/title-final-icyblue.png`.
   - **Optional future upgrade:** the actual Frostmaiden cover painting as the BG. Parked — FE8's
     title BG is a custom two-blob + TSA + palette format (~640 tiles), so dropping a full painting in
     is high-effort/high-risk; the icy-blue recolor was the agreed pragmatic call for the alpha.
     Source art saved by Nicolas at `~/Downloads/FrostmaidenCover.jpeg` (move into `References/` if pursued).
3. **Prep roster overlap** (deferred) — only if Nicolas wants it before more chapters; it's a focused
   prep-scroll-system rewrite. Verify with `recordprep` (now fast via checkpoints).
4. **In-game confirms (Nicolas, opportunistic):** 'Ol Bitey in the Northlook scene; overall ending feel;
   the dev placeholder / RBG pun wording (copy lives in `DEV_PLACEHOLDER_LINE`).
5. **Carried:** custom Bryn Shander winter BG via Gemini (parked); #29 world map; pre-distribution
   license rechecks (Scramsax Hero mug, AlexYTXG Bandit-Peg, **Chocobo {SkidMarc25}** — no [F2E] tags;
   Fire Imp + Cynon villager ARE [F2E]); ch02+ YAML `ea_file:` cleanup; map_sprite_editor **Finish**
   button bug.

## Key files
- `tools/build_campaign.py` — `dev_placeholder_scene`/`dev_placeholder_message` + `DEV_PLACEHOLDER_*`
  (the reusable unbuilt-boundary scene; ch01 ending calls it instead of `MNC2`); `inject_ch01` (ending
  = `EventScr_Ch2_EndingScene`: `BACG(BG_NORMAL_VILLAGE)` + per-beat `Text()`;
  `end_stage`/`end_home`/`end_preload`(all [])/`end_overrides`; faceless `narration` speaker);
  `_script_to_message` (**faceless speakers now emit NO `[OpenX]`** → plain full-width box);
  `_inject_palette_bank_hook`; `inject_northlook_bitey` (block-5 fish); `_term_pad`;
  `PORTRAIT_MAP`/`GUEST_PORTRAIT_MAP` (`baxby→Forde`); `CH01_ENDING_MSGS`/`CH01_ENDING_CARD_MSG`.
- `campaigns/.../chapters/ch01-the-iron-trail.yaml` — `events[chapter_end].script` (A+B merged, E1/E2
  split, narration cough); `post_chapter` (vanilla economy: `net_gold: 0`, Baxby = free story-recruit,
  `unlocks_chapter: ch02-cold-welcome`).
- `campaigns/.../npcs/baxby.yaml` — recruit-unit design (Cavalier, Franz donor, Forde slot, art.render).
- `tools/playtest/` — `run.sh` (checkpoint orchestration + 60fps for record*); `harness.lua`
  (`saveState`/`loadState`, `reachPrep`/`leavePrepAndGrindToSeize`, `ckpt_prep`/`ckpt_seize`,
  `recordprep`/`recordending`); `make_gif.py`; `states/` (gitignored).
- `tools/verify_text.py` (text gate, also `verify_text.py 0xNNN` to decode one message).

## Gotchas (carried)
- Story text lives in YAML/build strings → `make` regenerates bodies; gate with `verify_text`.
- **Hand-written narration → `_term_pad`** (odd printable count needs the `[.]` pad or the 0x00
  terminator bleeds into the next message). `_script_to_message` output doesn't need it.
- Scenic Text_BG wraps ~42 chars; map bubbles ~29 (clip). Faces: 4 slots max (eviction handled).
  **A preloaded silent listener fades in/out at every REMA it straddles — don't preload across beats.**
- **FE8 convo BGs are 4bpp: each 8×8 tile binds ONE 16-colour sub-palette.** Edits to a BG (Bitey, or
  any insert) must use only that tile's sub-palette block or the converter garbles them.
- **Recording fidelity:** `record*` must run at 60fps (run.sh does this) or frameskip aliases fades
  into "blips". Checkpoints (`states/`) make scene spot-checks fast; first run per build pays the
  240fps grind, later runs load instantly.
- `CONST_DATA` for injected tables (rodata discarded). **Never commit the `fireemblem8u` submodule
  pointer** — it's a build artifact; stage repo files explicitly.
- Built ROM at `fireemblem8u/fireemblem8.gba`. Synthetic macOS keypresses don't reach mGBA. Nicolas
  can't see inline renders — save to `map-review/` (gitignored) and `open` (PNG → Preview; GIF → Safari).
  Izobai is female; Pinky is male.

## Memory
[[manchego-stars-project]] · [[project_manchego_stars_campaign_structure]] · [[manchego-stars-automated-playtests]] ·
[[manchego_stars_guest_map_sprite_wiring]] · [[reference_fe_repo]] · [[feedback_vendor_community_assets]] ·
[[feedback_custom_art_lever]] · [[feedback_nicolas_not_an_artist]] · [[feedback_show_before_committing_art]] ·
[[feedback_sharing_visual_drafts]] · [[feedback_collaborative_map_design]] · [[feedback_answer_before_picker]] ·
[[manchego_stars_text_terminator_parity]] · [[feedback_use_decomp]] · [[feedback_clean_doc_rewrites]] ·
[[feedback_proactive-push]] · [[feedback_anti_drift_conventions]] · [[feedback_handoff_vs_memory]]

## Standing rules
Combat = pure vanilla FE; field parity with vanilla ch N is doctrine. Custom art where it matters,
**show before committing**; bring 2-3 options and let Nicolas drive. Story/dialogue = collaborative
(dialogue-pass skill). **Fast playtests for logic; slow 60fps recordings only for scene spot-checks**
(checkpoints make this cheap). Repo is the source of truth, NOT memory — don't put recipes in memory.
Auto-push to main once green; never commit the `fireemblem8u` submodule pointer.
