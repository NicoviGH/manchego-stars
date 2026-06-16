# Handoff: Ch1 slice (#21) — Beat 1 (Northlook opening) dialogue LOCKED & committed. NEXT = art-shop tavern BG + Hruna → wire Beat 1 → resume writing the trail beats.

**Date:** 2026-06-16
**Session focus:** Ran the **Ch1 "The Iron Trail" dialogue pass** (`dialogue-pass` skill) on
**Beat 1 — The Northlook opening**. Co-wrote it with Nicolas over many iterations and locked
the whole scene. Committed the locked text to the chapter YAML (`6852c67`, pushed to main).

**The opening is the "meet at the tavern" set piece:** Hlin & Scramsax come in from the cold;
the **seven PCs introduce themselves one by one** (each grounded in their `lore/<pc>.md` voice
bible); Hlin gives a **campaign-altitude story** (the unnatural endless winter that "has a will
of its own" + its agents — the prologue ice-dagger killer recast as one such agent enforcing the
sacrifices; implies the Frostmaiden without spoiling the Targos/Ch2 frost-druid reveal); RBG
haggles the iron job to 200 GP; Braulo calls it fair and commits; Hlin asks for one voice to
lead → hands into lord-select.

---

## NEXT UP — finish Beat 1 (in this order, per Nicolas), then continue the dialogue pass

**START HERE on a fresh instance.** The order Nicolas set:

1. **Art-shop the tavern background** — quickly survey **vanilla FE8 + the FE-Repo** and pick;
   **most likely NO custom work needed.** Vanilla already has fitting catalog BGs (decomp
   `gConvoBackgroundData`, `src/eventscr2.c:83`): **`bg_Fireplace`** (a hearth/tavern interior —
   and our Northlook canon centers on Ol' Bitey mounted over the hearth) is the on-the-nose pick;
   `bg_Town`/`bg_House`/`bg_Interior_Brown` are alternates. Winter-reskin the palette if desired
   ([[project_manchego_stars_winter_reskin]]). Show-before-commit ([[feedback_show_before_committing_art]]).
   FE-Repo access recipe: [[feedback_vendor_community_assets]] / [[reference_fe_repo]].
2. **Hruna portrait** — same approach: **vendor/bench first** (FE-Repo dwarf/female mug), custom
   only if forced. One-chapter NPC. Book ref: frost-scarred dwarf, lost right ear + two fingers to
   frostbite, raspy smoker's voice (book p.34, the Foaming Mugs questgivers). Guest map-sprite
   wiring recipe if she needs a unit: [[manchego_stars_guest_map_sprite_wiring]].
3. **Wire Beat 1** — make `inject_ch01` (`tools/build_campaign.py`) consume the chapter_start
   `script:` and stage it as the slot-2 (`EventScr_Ch2_*`) BeginningScene over the chosen BG.
   **Reuse, don't reinvent:** `_script_to_message` (lazy faces, `[A][LF]` pages, wrap), and the
   prologue's pattern is the template — see `inject_prologue` (`build_campaign.py` ~2620–2650)
   which already consumes ch00's `events['chapter_start']['script']` via `_script_to_message`
   with an `opening_staging` face map and a message SPLIT at the boss reveal. Ch01 currently does
   NOT consume the opening script (that's why this YAML is inert today). Things the wiring must
   handle: portrait/face loads for ~10 speakers (the 7 PCs + Scramsax/Hlin/Hruna; FIDs from
   `PORTRAIT_MAP`), **Sclorbo's impression text** (parenthetical, no face — he never speaks),
   **Marty's spore-cough + Braulo's isopod** are stage business (choreography, not message text),
   the `location_card` ("The Northlook"), and the existing lord-select (`LORDSEL_PROMPT_MSG=0x957`)
   must follow the scene. Pick/allocate dead slot-2 message ids for the new boxes.
4. **In-game MOTION review** (`tools/playtest/run.sh record` → GIFs in `map-review/` → `open -a
   Safari`), then Nicolas sign-off. Stills mislead (typewriter mid-stroke). Decided 2026-06-10.
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
- **Beat 1 (Northlook opening) dialogue fully co-written and LOCKED** — committed to
  `campaigns/.../chapters/ch01-the-iron-trail.yaml` `events[chapter_start].script:`
  (22 entries; location card + A/B/C/D/E movements). `6852c67`, pushed to main.
- Settled the chapter's open questions: keep "goblins"; Velynne orb → Ch2 cold-open; optional
  beats (the body + Izobai taunt) both IN; scene-style = location-driven (BG off-map / over-map
  on-map), grounded in the decomp.
- Grounded everything in source: read all 7 PC bibles + npc-bench, Hlin/Scramsax/narration bibles,
  the DM notes (confirmed the murder/dagger thread is a one-off; the recurring spine is
  frost-druids/Auril/the worsening winter, party = Ten-Towns troubleshooters), and the decomp's
  background system (`gConvoBackgroundData`, `BACG`/`EvtDisplayTextBg`).
- **Verified:** `make` green · `verify_text` 3404/0 (text inert until wired).

## Current state
- ✅ Ch1 engine machine-verified (entry/preps/deploy-cap, lord-select force-deploy + game over,
  win-by-Seize). `make` green, `verify_text` 3404/0; playtests PASS (ch00 win/gameover/retreat,
  ch01 default-lord, ch01lord, ch01win, goodberry).
- ✅ Izobai boss portrait · ✅ Fire Imp grunt sprites · ✅ Goodberry reflavor · ✅ **Beat 1 dialogue
  text locked**.
- ⚠️ **Beat 1 not yet playable** — the locked YAML script is inert until `inject_ch01` consumes it;
  needs tavern BG + Hruna portrait + wiring + motion review (NEXT UP, steps 1–4).
- ⚠️ Trail beats still placeholder; gendered chief text (0x93C/0x961) needs the Izobai she/her fix.
- ⚠️ ch01 ending MNC2(0x3) lands on vanilla Ch3 until ch02 is wired.

## Blockers
- None. (Beat-1 wiring depends on the tavern BG + Hruna art being chosen first — steps 1–2.)

## Next steps (priority order)
1. **Tavern BG art-shop** (vanilla/FE-Repo, likely `bg_Fireplace`; show-before-commit).
2. **Hruna portrait** (vendor/bench first).
3. **Wire Beat 1** into `inject_ch01` (consume chapter_start `script:`, stage on slot 2 over the BG).
4. **In-game motion review** → Nicolas sign-off.
5. **Resume dialogue pass on the trail beats** (start with the body; write Izobai's voice bible
   before her taunt/death quote).
6. Carried: #29 world map; license rechecks before distribution (Scramsax Hero mug, AlexYTXG
   Bandit-Peg portrait — no [F2E] tags; Fire Imp IS [F2E]); ch02+ YAML `ea_file:` schema cleanup;
   wire ch02 so the ch01 ending stops landing on vanilla Ch3.

## Key files
- `campaigns/.../chapters/ch01-the-iron-trail.yaml` — **Beat 1 locked `script:`** under
  `events[chapter_start]`; roster, objective, the trail/house/ending event stubs (still to write).
- `tools/build_campaign.py` — `inject_ch01` (slot-2 wiring; **does not yet consume the opening
  script** — step 3); `inject_prologue` (~2620–2650, the template that DOES consume ch00's
  script via `_script_to_message` + `opening_staging`); `_script_to_message`, `set_message_body`,
  `_wrap_fe_lines`; `LORDSEL_*` ids; `PORTRAIT_MAP`.
- `campaigns/.../lore/*.md` — voice bibles (7 PCs + hlin/scramsax/narration/npc-bench). **No
  Izobai bible yet** — write it before her taunt/death quote.
- `fireemblem8u/src/eventscr2.c:83` — `gConvoBackgroundData` BG catalog (Fireplace/Gate/Town/…).
- `fireemblem8u/include/eventscript.h` / `EAstdlib.h` — `BACG`=`EvtDisplayTextBg`, `LOMA`=`EvtLoadMap`.
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
