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
   - **⚠️ THE CRUX — the 4-face fix (FINALIZED PLAN below).** `FACE_SLOT_COUNT = 4` (`include/face.h:4`):
     only 4 faces can be loaded at once (the `gFaces` pool; `FindFreeFaceSlot` returns −1 when full).
     Beat 1 has ~10 speakers, and `_script_to_message` (build_campaign ~493) lazy-loads each speaker
     once and **never clears** → overflows. Verified engine facts (don't re-derive):
       * `sTalkState->faces[8]` is **position-indexed** (`scene.h:77`); `[OpenX]` (textdefs 8–15) sets
         the active position via `SetActiveTalkFace(pos−8)`; `[LoadFace][FID]` loads into a free `gFaces`
         slot at the active position (`scene.c:855`).
       * `[ClearFace]` (`scene.c:888`) fades out `faces[activePosition]` and frees its `gFaces` slot —
         so **`[OpenX][ClearFace]` clears the face at position X**. (≈16-frame fade per clear → reads as
         nice pacing between speakers.)
       * Vanilla `.h` files never use the `[ClearFace]` text tag — they cap scenes at ≤4 faces. We're the
         first to need eviction, so this is a genuine `_script_to_message` extension.

     **FIX = make `_script_to_message` POSITION-aware with auto-eviction** (one general change; the
     prologue's 3-speaker call is unaffected). Replace the flat `loaded` set with a `live` map of
     **position → speaker** (≤4 entries) and an LRU order, then per dialogue block:
     ```
     pos, fid = staging[speaker]            # staging stays speaker -> ([OpenX], fid_or_None)
     if live.get(pos) == speaker:           # already on screen here -> just re-activate
         touch LRU
     else:
         if pos in live:                    # someone else holds this podium -> clear them
             emit '[OpenPOS][ClearFace]'; del live[pos]
         while len(live) >= 4:              # all 4 podiums full -> evict LRU podium
             p_old = lru.pop(0); emit '[OpenP_OLD][ClearFace]'; del live[p_old]
         emit '[OpenPOS][LoadFace][FID]'; live[pos] = speaker; lru.append(pos)
     emit page text (existing [OpenPOS][A]...[A] shape)
     ```
     This makes **podiums (positions) the budget, not speakers** — so the 7-PC roll-call can all share
     ONE spotlight position (each new PC auto-clears the previous → one face at a time), while Hlin
     stays anchored at another podium. Suggested staging (≤3 concurrent, well under the cap; final
     count/positions are a **feel** call for the step-4 motion review): Hlin `[OpenMidRight]` (anchor),
     Scramsax `[OpenFarRight]`, the 7 PCs all `[OpenMidLeft]` (rotating spotlight), Hruna `[OpenLeft]`.
   - **`staging` builds for all 10:** 7 PCs via `PORTRAIT_MAP` slots, Scramsax=`Kyle`, Hlin=`Natasha`,
     **Hruna=`Villager_Woman`**. ⚠️ `_fid_tag('Villager_Woman')` → `[FID_Villager_Woman]` (underscore,
     WRONG); real tag is `[FID_VillagerWoman]`. Fix: hardcode Hruna's fid `'[FID_VillagerWoman]'`, **or**
     add `'VILLAGER_WOMAN': 'VillagerWoman'` to the `special` dict in `_fid_tag` (build_campaign ~536,
     which is keyed by UPPERCASE slot like the existing `'ONEILL'`) and call `_fid_tag('VILLAGER_WOMAN')`.
   - **Faceless / stage-business handling:** **Sclorbo** never speaks — render his parenthetical as a
     box with NO `[LoadFace]`; give him a staging entry `(pos, None)` and have the eviction code emit an
     `[OpenX]` to an **unoccupied** podium so no loaded face mouth-moves under his impression text.
     **Marty's spore-cough + Braulo's isopod** are stage directions, NOT message text — drop them (the
     YAML carries them as `#` comments only).
   - **Message split (recommended structure):** stage one persistent `BACG(BG_FIREPLACE)` and show the
     opening as **per-beat messages** A/B/C/D/E (the script's `# ── A/B/C… ──` seams), each its own
     `TEXTSHOW(msg)/TEXTEND/REMA`. Reasons: bounds message byte-length (watch for any buffer cap — a
     single ~22-entry message may be too long; **verify at build**), gives natural `REMA` pauses, and
     keeps each message's face state self-contained. Eviction still needed WITHIN beat B (roll-call =
     9 speakers). Allocate dead slot-2 message ids for the boxes (the `0x94x`/`0x95x` band around the
     lord-select ids has unused slots; cf. prologue's 0x90D/0x90E).
   - **Location card + lord-select handoff:** `BROWNBOXTEXT("The Northlook", x, y)` over the BG.
     The existing lord-select (`LORDSEL_PROMPT_MSG=0x957`) must follow the scene — and Hlin's FINAL
     scripted line ("…Who leads them up the trail?") already asks the question, so **don't ask twice.**
     Recommended: end the scenic E-message one line early and set **0x957 = that final Hlin line**
     (with her face, shown over the map after `FADU`), so the question lands exactly once as the direct
     lead-in to the menu. (Currently 0x957 is faceless narration "The company gathers… / Who will lead…".)
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
- **Reverse-engineered + FINALIZED the step-3 wiring plan** (NEXT UP §3): the scenic `BACG`/`Text_BG`
  idiom (`lordsplit-eventscript.h` template), `BG_FIREPLACE=0x09`, the location-card `BROWNBOXTEXT`,
  and the full **4-face-slot fix** — position-aware auto-eviction in `_script_to_message` (pseudocode
  in §3), with the two engine facts verified (`faces[8]` position-indexed; `[ClearFace]` frees the
  active podium). The next instance can implement directly from §3.

## Tried but didn't work (this session)
- **Hruna as a canon scarf-wrapped frost-dwarf** (Assassin {SSHX} [F2E] mug, frost- and wool-recolored):
  on-canon (book: "bundled… only their eyes visible") and a clean [F2E] license, but Nicolas rejected
  it as **"too suspicious"** — a hooded/masked figure reads sinister, wrong for a sympathetic
  quest-giver. → Switched to the open-faced Generic Villager. **Lesson:** for NPCs, the emotional read
  Nicolas wants can outrank book canon; lead with the *feel* of the scene, not the literal description.
- **A wool-scarf collar painted onto the villager** — prototyped (cream cowl over the throat), looked
  fine, but Nicolas said "nevermind on the scarf." Final = plain olive-wool coat, no scarf. (The
  scratch recolor/preview scripts + ref downloads were cleaned up; only `hruna.png` + the vendor recipe
  shipped.)

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
