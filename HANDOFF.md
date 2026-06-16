# Handoff: Ch1 slice (#21) — Beat 1 art DONE (tavern BG = bg_Fireplace; Hruna bust shipped, `5c6e4bb`). NEXT = WIRE Beat 1 into inject_ch01 (the 4-face-slot constraint is the crux) → motion review → resume trail beats.

**Date:** 2026-06-16 (session 2)
**Session focus:** Beat-1 **art-shop (steps 1–2 of the prior plan), now DONE & pushed** (`5c6e4bb`):
- **Tavern BG = vanilla `bg_Fireplace`** (`BG_FIREPLACE = 0x09`, `constants/backgrounds.h`), used
  **as-is** (no reskin) — Nicolas picked it over `bg_House`. Hearth common room; matches the
  Ol'-Bitey-over-the-hearth canon. No custom work.
- **Hruna bust shipped** — vendored **Generic Villager {Cynon} [F2E]**, periwinkle→olive-wool coat
  recolor, riding the generic **`Villager_Woman`** face slot (FID tag `[FID_VillagerWoman]` = 0x60),
  added to `GUEST_PORTRAIT_MAP`. Deliberately departs from book canon (the bundled, scarf-wrapped,
  eyes-only frost-dwarf): a scarf-wrapped Assassin-mug recolor was prototyped and rejected by Nicolas
  as "too suspicious" — he wanted **open, sympathetic "please help us" energy** for a one-chapter NPC.
  Recipe folded into `portraits/guest_vendor_busts.py`; credited in CREDITS.md + vendor/README;
  decision recorded in `docs/decisions.md`. `make` green, verify_text 3404/0.

**Beat 1 itself** (locked `6852c67`) is the "meet at the tavern" set piece: Hlin & Scramsax in from
the cold; the **7 PCs introduce themselves one by one**; Hlin's campaign-altitude story (endless
winter "with a will of its own" + its agents — the prologue ice-dagger killer recast as one);
RBG haggles the iron job to 200 GP; Braulo commits; Hlin asks who leads → hands into lord-select.

---

## NEXT UP — WIRE Beat 1 (step 3), then motion review, then the trail beats

**START HERE on a fresh instance.** Steps 1–2 (BG + Hruna art) are DONE. Remaining:

3. **Wire Beat 1** into `inject_ch01` (`tools/build_campaign.py`, ~2814) — consume the chapter_start
   `script:` and stage it as a **scenic off-map scene over `bg_Fireplace`** at the HEAD of
   `EventScr_Ch2_BeginningScene` (currently ~3118–3149), BEFORE the existing guest-DISA / roster
   LOAD / lord-select. **Idioms already reverse-engineered this session:**
   - **Scenic BG:** `BACG(BG_FIREPLACE)` → `FADU(n)` → `TEXTSHOW(msg)/TEXTEND/REMA` → `FADI(n)` →
     `REMOVEPORTRAITS` + `CALL(EventScr_RemoveBGIfNeeded)`. Template = **`lordsplit-eventscript.h`**
     (a scene→menu, exactly our scene→lord-select shape). `Text_BG(bg,msg)` (Convo_Helpers.h) is the
     one-shot bundled form; use the explicit form so the location card + multiple messages share the BG.
   - **Location card** "The Northlook": `BROWNBOXTEXT(card_msg, x, y)` over the BG (prologue uses
     `BROWNBOXTEXT(0x664,8,8)`); card text via `name_message_body`.
   - **⚠️ THE CRUX — `FACE_SLOT_COUNT = 4`** (`include/face.h:4`) but Beat 1 has **~10 speakers**.
     `_script_to_message` lazy-loads each speaker once and **never clears** (fine for the prologue's
     3 speakers; OVERFLOWS here — `FindFreeFaceSlot` returns −1 after 4). `[ClearFace]` (ctrl 17,
     `scene.c:888`) fades out the **active** face slot, so eviction = emit `[OpenX][ClearFace]` for an
     LRU speaker before loading a 5th. **Plan:** extend `_script_to_message` to keep ≤4 concurrent
     faces (evict LRU), OR split the opening into ≤4-distinct-speaker messages with `REMOVEPORTRAITS`
     between them. Positions: 8 exist (`[OpenFarLeft]`..`[OpenFarFarRight]`, textdefs 8–15) but only 4
     slots — reuse them; the 7-PC roll-call likely reads best **one PC at a time** (clear between),
     Hlin/Scramsax held as the anchor pair. The exact face count/positions are a **feel** call for the
     motion review (step 4).
   - **Staging dict** (speaker key → `([OpenX], _fid_tag(slot))`) for all 10: 7 PCs via `PORTRAIT_MAP`
     slots, Scramsax=`Kyle`, Hlin=`Natasha`, **Hruna=`Villager_Woman`** — NOTE `_fid_tag('Villager_Woman')`
     yields `[FID_Villager_Woman]` (underscore) but the real tag is `[FID_VillagerWoman]`; add to the
     `special` dict in `_fid_tag` (build_campaign ~534) or hardcode Hruna's tag.
   - **Sclorbo** = parenthetical impression text, **NO face** (`[OpenX]` with no LoadFace, or plain text);
     **Marty's spore-cough + Braulo's isopod** = stage business, NOT message text (drop or comment).
   - **`location_card` + the existing lord-select (`LORDSEL_PROMPT_MSG=0x957`) must follow the scene.**
     Hlin's final scripted line already asks "who leads?" — reconcile with 0x957 so the question isn't
     asked twice (either trim the scene's last line into 0x957, or reword 0x957 to a brief connective).
   - Allocate dead slot-2 message id(s) for the new opening box(es) (cf. how 0x90D/0x90E were used in
     the prologue; the `0x95x` band around the lord-select ids has dead slots).
4. **In-game MOTION review** (`tools/playtest/run.sh record` → GIFs in `map-review/` → `open -a
   Safari`), then Nicolas sign-off — validates the face choreography. Stills mislead. Decided 2026-06-10.
5. **Resume the dialogue pass on the trail beats** — same variant flow:
   road sign (0x955, placeholder→voice) · **the body** (Beat 3b: yeti-torn dwarf, two sets of
   tracks, one huge — the chapter's most story; foreshadows the Easthaven yeti) · House 1 terrain
   hint (0x93B) · House 2 boss hint (0x93C, also **regender to Izobai she/her**) · **Izobai
   turn-1 taunt** (vanilla-parity boss-taunt slot; needs an **Izobai voice bible** co-written
   first — none exists yet) · **Izobai death quote** (0x961, rewrite "Gah! The ironses were
   ours!" in her voice). Beats settled this session: keep "goblins" (no imp rename); Velynne orb
   hook HELD → it's the **Ch2 cold-open** (DM notes: "as the party leave town… head west to
   Targos"); ending Beat 8 BG location (camp vs Bryn Shander gate) still Nicolas's call.

### LOCKED Beat-1 facts (don't re-litigate)
- **Scene-style rule (decomp-confirmed):** dialogue talks OVER THE MAP when on the battlefield
  (vanilla default — Ch1 opening, taunts, houses, endings); a **scenic `BACG` background** is for
  OFF-battlefield story scenes (taverns, councils, flashbacks). So Beat 1 (the Northlook, off-map)
  = scenic BG; the trail beats (3/3b/4/5/6/7, on-map) = over-the-map portraits; ending Beat 8 =
  Nicolas's call (camp over-map vs `bg_Gate` scenic).
- **Cast = 7 playable PCs:** Braulo (hermit-crab Fighter/axe), Marty (sporemaster Shaman; spores
  read as normal text, coughs them at new folk, never acknowledges it), Meesmickle (vampire-tabaxi
  Shaman; rare dry one-liners), Prof. RBG (underfolk; cheese puns + grandiose + does the money
  talking), Rootis (snowperson Ice-Mage; warm, gentle snow humor, mystery-lover), Sclorbo (chwinga
  Priest; **never speaks — parenthetical impression text only**), Wolfram (drakeborn Knight; tastes/
  eats metal, never backs down). Voice bibles in `campaigns/.../lore/`.
- **Process correction this session** (now [[feedback_prep_before_drafting_dialogue]]): read EVERY
  speaker's voice bible + the roster BEFORE drafting a line. The first Beat-1 draft went out with
  only Braulo loaded → invented a quest-giver, skipped the cast. Don't repeat.

---

## Accomplished this session
- **Beat-1 art DONE & pushed (`5c6e4bb`):** tavern BG = `bg_Fireplace` (as-is, Nicolas's pick over
  `bg_House`); **Hruna bust** = vendored Generic Villager {Cynon} [F2E] olive-wool recolor on the
  `Villager_Woman` slot (sympathetic mug, not the canon scarf-dwarf — his call). Recipe in
  `guest_vendor_busts.py`; credited; `docs/decisions.md` updated. `make` green, verify_text 3404/0.
- **Reverse-engineered the step-3 wiring** (see NEXT UP §3): the scenic `BACG`/`Text_BG` idiom
  (`lordsplit-eventscript.h` template), `BG_FIREPLACE=0x09`, the location-card `BROWNBOXTEXT`, and
  the **4-face-slot constraint** (`FACE_SLOT_COUNT=4` vs ~10 speakers) + the `[ClearFace]` eviction fix.

## Current state
- ✅ Ch1 engine machine-verified (entry/preps/deploy-cap, lord-select force-deploy + game over,
  win-by-Seize). `make` green, `verify_text` 3404/0; playtests PASS (ch00 win/gameover/retreat,
  ch01 default-lord, ch01lord, ch01win, goodberry).
- ✅ Izobai boss portrait · ✅ Fire Imp grunt sprites · ✅ Goodberry reflavor · ✅ Beat 1 dialogue
  text locked · ✅ **tavern BG picked** · ✅ **Hruna bust shipped & injected**.
- ⚠️ **Beat 1 not yet playable** — the locked YAML script is still inert until `inject_ch01` consumes
  it (step 3 wiring + step 4 motion review). The Hruna bust is injected but referenced by nothing yet.
- ⚠️ Trail beats still placeholder; gendered chief text (0x93C/0x961) needs the Izobai she/her fix.
- ⚠️ ch01 ending MNC2(0x3) lands on vanilla Ch3 until ch02 is wired.

## Blockers
- None.

## Next steps (priority order)
1. **Wire Beat 1** into `inject_ch01` — the scenic `bg_Fireplace` scene at the head of
   `EventScr_Ch2_BeginningScene`; mind the **4-face-slot limit** (NEXT UP §3 has the full idiom map).
2. **In-game motion review** → Nicolas sign-off (validates face choreography).
3. **Resume dialogue pass on the trail beats** (start with the body; write Izobai's voice bible
   before her taunt/death quote; regender 0x93C/0x961 to she/her).
4. Carried: #29 world map; license rechecks before distribution (Scramsax Hero mug, AlexYTXG
   Bandit-Peg portrait — no [F2E] tags; Fire Imp + Cynon villager ARE [F2E]); ch02+ YAML `ea_file:`
   schema cleanup; wire ch02 so the ch01 ending stops landing on vanilla Ch3.

## Key files
- `campaigns/.../chapters/ch01-the-iron-trail.yaml` — **Beat 1 locked `script:`** under
  `events[chapter_start]`; roster, objective, the trail/house/ending event stubs (still to write).
- `campaigns/.../portraits/` — `hruna.png` (shipped) + `guest_vendor_busts.py` (regenerates it);
  `vendor/Generic Villager {Cynon} [F2E].png`.
- `tools/build_campaign.py` — `inject_ch01` (~2814; BeginningScene ~3118–3149, **does not yet consume
  the opening script** — step 3); `inject_prologue` (~2620–2650, consumes ch00's script via
  `_script_to_message` + `opening_staging` — the cross-reference template, though it stages OVER-MAP,
  not scenic); `_script_to_message` (~493, **needs the ≤4-face eviction**), `_fid_tag` (~532),
  `set_message_body`, `_wrap_fe_lines`; `LORDSEL_*` ids; `PORTRAIT_MAP` / `GUEST_PORTRAIT_MAP` (Hruna added).
- `campaigns/.../lore/*.md` — voice bibles (7 PCs + hlin/scramsax/narration/npc-bench). **No
  Izobai bible yet** — write it before her taunt/death quote.
- `fireemblem8u/src/eventscr2.c:83` — `gConvoBackgroundData` BG catalog (Fireplace=idx 9/Gate/Town/…);
  `include/constants/backgrounds.h` — `BG_FIREPLACE=0x09` enum.
- `fireemblem8u/include/eventscript.h` / `EAstdlib.h` — `BACG`=`EvtDisplayTextBg`, `LOMA`=`EvtLoadMap`;
  `include/EA_Standard_Library/Convo_Helpers.h` — `Text_BG(bg,msg)`, `Text(msg)`.
- `fireemblem8u/src/events/lordsplit-eventscript.h` — **scene→menu scenic template** (BACG/FADU/
  TEXTSHOW/FADI/REMOVEPORTRAITS). `src/scene.c:855–898` — `[LoadFace]`/`[ClearFace]` semantics;
  `include/face.h:4` — `FACE_SLOT_COUNT=4` (the constraint). textdefs 8–17 = the Open*/LoadFace/ClearFace tags.
- `tools/verify_text.py` — text regression gate. `tools/playtest/run.sh record` — motion GIFs.
- `.claude/skills/dialogue-pass` — the co-writing skill (voice bible, variant flow, craft checks).

## Gotchas (carried)
- Story text: YAML `script:` → build generates bodies; `make` overwrites manual decomp edits. Gate:
  `python3 tools/verify_text.py`.
- Odd-length NAME strings: pad with `[.]` (terminator parity).
- Map speech bubbles ~29 chars/line and clip; full-screen Text_BG tolerates ~42 (`_wrap_fe_lines`).
  `[A][LF]` = page break; same-speaker turns coalesce; every non-terminal `[A]` must be `[LF]`-followed.
- gDefeatTalkList: chapter-keyed entries at the HEAD; never after `{.pid=-1}`.
- rodata is discarded by the ldscript: use `CONST_DATA` (.data) for injected tables/literals.
- Vanilla facts: `git -C fireemblem8u show HEAD:<file>`. **Never commit the `fireemblem8u`
  submodule pointer** (decomp edits are build artifacts; stage repo files explicitly).
- Bash cwd drifts; built ROM lands at `fireemblem8u/fireemblem8.gba` (NOT repo root).
- Synthetic macOS keypresses don't reach mGBA; in-emulator Lua is the path. Screenshots can land
  mid-transition — linger/extra A. PNG → `open` (Preview); GIF → `open -a Safari`. Nicolas can't
  see inline renders — save to `map-review/` and `open`.
- Pinky is male ("he"). **Izobai is female ("she")** — load-bearing for her taunt/death quote.
- Frostmaiden book (`references/References/icewind-dale-...pdf`, image-only — `pdftoppm`); PDF page
  = printed + 1. DM notes `.../DungeonMasterNotesIcewindDale.pdf` (has a text layer; use `pdftotext`).

## Memory
[[manchego-stars-project]] · [[feedback_prep_before_drafting_dialogue]] · [[feedback_collaborative_story_planning]] ·
[[feedback_story_sources_of_truth]] · [[project_manchego_stars_dm_notes]] · [[feedback_show_before_committing_art]] ·
[[feedback_custom_art_lever]] · [[feedback_nicolas_not_an_artist]] · [[feedback_answer_before_picker]] ·
[[feedback_clean_doc_rewrites]] · [[manchego-stars-automated-playtests]] · [[feedback_fe_name_truncation]] ·
[[manchego_stars_text_terminator_parity]] · [[project_manchego_stars_cast_notes]] · [[feedback_sharing_visual_drafts]] ·
[[project_manchego_stars_winter_reskin]] · [[feedback_vendor_community_assets]] · [[reference_fe_repo]] ·
[[manchego_stars_guest_map_sprite_wiring]] · [[project_manchego_stars_portrait_pipeline]]

## Standing rules
Combat = pure vanilla FE; field parity with vanilla ch N is doctrine. Custom art on every sprite
part where it matters, follow concept faithfully, one artwork at a time, **show before committing**.
Story/dialogue = collaborative (variants → Nicolas picks; read ALL voice bibles first). Auto-push to
main once green; never commit the `fireemblem8u` submodule pointer. Playtests machine-run for logic,
Nicolas for feel.
