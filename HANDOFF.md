# Handoff: Ch1 slice (#21) — Beat 1 + the TRAIL BEATS DONE & approved (Northlook scene, sign/body, house hints, Izobai taunt + death, 'Ol Bitey). NEXT = ch01 ending scene (Duvessa) + wire ch02 so the ending stops landing on vanilla Ch3.

**Date:** 2026-06-17 (session 4)
**Session focus:** Finished the **ch01 dialogue pass** (interactive, one beat at a time):
- **Beat 1 Northlook scene** (session 3) — scenic `bg_Fireplace` + the 4-face fix; approved.
- **Trail beats** (this session): road sign + dismembered sled-driver folded into one trailhead
  trigger; two house hints reskinned from **vanilla Ch1's own house quotes**; **Izobai** voice bible
  (`lore/izobai.md`) + turn-1 taunt (spare `EventScr_Ch2_Turn2Player`) + death quote; Braulo's beat-E
  line de-collectivised ("Fair price for honest work."). Design in `docs/decisions.md` → "Ch1 trail beats".
- **'Ol Bitey** — the stuffed fish — mounted over the Northlook hearth via `inject_northlook_bitey`
  (custom in-palette BG edit as an idempotent build step). Reviewed in-game, Nicolas: "he's perfect."
- Hit + fixed the **Huffman terminator-parity bug** on the body narration (`_term_pad` `[.]` helper).

`make` green, `verify_text` 3404/0, **playtests PASS** (ch00 win/gameover, ch01 entry, ch01win).
GIFs (gitignored): `ch01-beat1-northlook.gif`, `ch01-izobai-taunt.gif`.

**What landed (working tree, uncommitted):**
- **`_script_to_message` is now position-aware with auto-eviction** (the finalized 4-face fix):
  tracks PODIUMS (screen positions) not speakers; re-using a podium emits `[OpenX][ClearFace]`
  (~16f fade), and a full pool (4) evicts the LRU podium. Faceless speakers (fid `None`) print a
  box with no `[LoadFace]`. Optional `width` arg (29 map / 42 scenic). **Prologue output is
  byte-identical** (≤4 distinct podiums → old lazy-load behaviour); verified by `verify_text`.
- **`_fid_tag`** gained `'VILLAGER_WOMAN': 'VillagerWoman'` (Hruna's real tag `[FID_VillagerWoman]`).
- **YAML** (`ch01-the-iron-trail.yaml`): added 4 `beat_break` sentinels (A|B|C|D|E seams) + a
  comment that the final Hlin line is the lord-prompt. **Dialogue text untouched** (still locked).
- **`inject_ch01`**: step 0 splits the locked `script:` on `beat_break` into 5 beats, builds the
  podium staging, and pops Hlin's final line for the over-map lord prompt; step 4 prepends the
  scenic scene to `EventScr_Ch2_BeginningScene`; step 6 writes the card + beat bodies + a
  face-bearing `0x957`. Message ids: card `0x945`, beats A–E `0x940–0x944` (dead vanilla Ch1
  tutorial slots; the prologue host strips Ch1's tutorial lists so they never display).
- **Scene shape** (head of BeginningScene): `REMOVEPORTRAITS` → `BACG(BG_FIREPLACE)` → `FADU(16)`
  → `BROWNBOXTEXT(0x945)` "The Northlook" (auto-dismisses — it's a blocking 100f+fade proc, no
  lingering) → `Text(0x940..0x944)` (each `Text` ends in REMA → **clears faces → fresh 4-face
  budget per beat**, BG persists across REMA, cf. ch16a) → `FADI(16)` → **`LOMA(0x2)`** → existing
  DISA/LOAD/`FADU(16)`(map) → lord-select. The lord prompt now uses `TEXTSTART` (was
  `TUTORIALTEXTBOXSTART`) so Hlin's face shows on `0x957`.
- **BG-garble fix (session-3, post-first-review):** BACG clobbers the map's BG VRAM, so just
  fading back up showed a corrupted tilemap behind the lord prompt/menu. Fixed with the vanilla
  **ch13a** idiom — `FADI(16)` → `SVAL(EVT_SLOT_B,0)` → `LOMA(CH01_HOST_INDEX)` (`RestartBattleMap`
  reloads the map graphics for the already-current chapter) → `FADU`. Replaces the `RemoveBGIfNeeded`
  call (that helper is for chapter *transitions*, not return-to-this-map). Verified clean in-game.
- **Name confirmed:** DM notes say *"The Northlook, the inn and tavern"* — the name is **"The
  Northlook"** (it IS the inn; "Inn" is not part of the name). Card text is correct.
- **Motion review GIF:** `map-review/ch01-beat1-northlook.gif` (`run.sh recordch01` → Pillow).
- **Staging — TWO-SIDED (revised after review 2):** quest-givers on the RIGHT (Hlin `[OpenMidRight]`,
  Scramsax `[OpenFarRight]`, Hruna `[OpenRight]`), party on the LEFT. The roll-call rotates one PC
  through `[OpenMidLeft]`; **monologue beats PRELOAD silent PC listeners** (`_script_to_message`'s new
  `preload=`) so Hlin/RBG address a populated room; **Hruna stands across from RBG** in the haggle.
  **Sclorbo now has his Ross face** (was faceless). All beats ≤4 concurrent faces (budget-safe).
- **BG-garble fix + scenic lord-select:** `BACG` draws on **BG3**; the menu's `ClearBg0Bg1` only
  touches BG0/1, and `CallLordSelectMenu` now does `SetDispEnable(1,1,0,1,1)` (BG2/map OFF) — so the
  lord-select plays over its own scenic BG (`CH01_LORDSEL_BG = BG_STONE_CHAMBER`, a swappable
  placeholder), NOT the battle map. After the pick: `FADI` → `LOMA(host)` (`RestartBattleMap`) →
  DISA/LOAD/`FADU` → prep. **Hlin's "who leads?" stays in beat E at the Northlook** (no over-map prompt).
- **Playtest harness:** ch01/ch01win A-tap budgets 60→200; added **`scenesch01`** (per-page contact
  sheet) and **`recordch01`** (continuous frames → Pillow GIF). Open GIFs with **`open -a Safari`**.

### Review 3 — applied (this session, still uncommitted)
- **Marty's spore cough** → a parenthetical page (no FE8 particle system); **Sclorbo gets his Ross face**.
- **Meesmickle line:** "a bounty hunter" → "**a scale-less dragonborn**" (Wolfram).
- **Staging reworked to clean TWO-SHOTS** (podium geometry: only MidLeft↔MidRight are ≥96px apart, so
  speakers rotate through one inner podium, Hlin anchors mid-right). Fixes the Hlin/Scramsax and
  Hlin/Hruna overlap. Beat C listeners cut 3→2 (far-left + left). RBG haggles across from Hruna.
- **Pinky has presence:** RBG adds "this is my boy, Pinky" and **Pinky (Neimi) peeks from far-left**.
- **Lord-select confirm:** "lead the **party**" (was "company").

### Review 4 — applied (this session, still uncommitted)
- **Marty pours coffee** (was "cocoa").
- **RBG + Pinky:** kept together in beat B (Pinky `[OpenFarLeft]` beside his father at mid-left,
  Hlin watching mid-right). The B2 two-shot split was tried and **reverted** — Nicolas: the stacked
  pair "was fine actually."
- **Lord-select BG = `BG_DARKLING_WOODS`** — Nicolas: "the most Icewind Dale of the options."

### Beat 1 — SETTLED
Face transitions = **fade** (`[ClearFace]`), Nicolas's call. Full rationale + the whole scene
design are in `docs/decisions.md` ("Multi-speaker cutscene faces"). No open questions on Beat 1.

---

## Prior session (2) — Beat-1 art DONE & pushed (`5c6e4bb`)
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

## NEXT UP — Nicolas motion-review sign-off → commit → trail beats

**START HERE.** Steps 1–3 (BG, Hruna bust, **wiring**) are DONE; the scene builds, plays, and
passes every playtest. The change is **uncommitted, pending Nicolas's sign-off** on the face
choreography (the one thing playtests can't judge).

1. **Motion-review sign-off (Nicolas).** Review `map-review/ch01-beat1-northlook.png` (per-page
   contact sheet; regenerate with `bash tools/playtest/run.sh scenesch01` → Pillow dedupe+grid).
   Confirm the 3 feel calls at the top of this doc (spotlight `[ClearFace]` fades · Hlin's face over
   the map for the lord prompt · the lingering watcher during Sclorbo's pantomime). For true motion
   I can add a `recordch01` GIF scenario if the stills aren't enough.
2. **Commit** once signed off (doc + YAML + tools in one commit; `Closes` nothing — #21 slice
   continues). `make` green, `verify_text` 3404/0, playtests PASS are already in hand. Auto-push.
3. **Resume the dialogue pass on the trail beats** — same variant flow:
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

## Accomplished (session 2 — the art + the wiring plan now implemented)
- **Beat-1 art DONE & pushed (`5c6e4bb`):** tavern BG = `bg_Fireplace` (as-is, Nicolas's pick over
  `bg_House`); **Hruna bust** = vendored Generic Villager {Cynon} [F2E] olive-wool recolor on the
  `Villager_Woman` slot (sympathetic mug, not the canon scarf-dwarf — his call). Recipe in
  `guest_vendor_busts.py`; credited; `docs/decisions.md` updated. `make` green, verify_text 3404/0.
- The step-3 wiring plan reverse-engineered that session (scenic `BACG` idiom, `BG_FIREPLACE=0x09`,
  the 4-face position-aware eviction) is **now implemented** — see the session-3 block up top.

## Tried but didn't work (session 2 — Hruna art)
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
- ✅ **Beat 1 WIRED & playing** (this session, uncommitted): scenic Northlook scene + 4-face
  roll-call + Hlin-led lord prompt. `make` green, `verify_text` 3404/0, playtests PASS
  (ch00 win/gameover, ch01 entry, ch01win). Hruna's bust now renders in the scene.
- ⚠️ **Uncommitted — awaiting Nicolas's motion-review sign-off** on the choreography (the 3 feel
  calls at the top). Contact sheet: `map-review/ch01-beat1-northlook.png`.
- ⚠️ Trail beats still placeholder; gendered chief text (0x93C/0x961) needs the Izobai she/her fix.
- ⚠️ ch01 ending MNC2(0x3) lands on vanilla Ch3 until ch02 is wired.

## Blockers
- **Nicolas motion-review sign-off** gates the commit (logic is done & green).

## Next steps (priority order)
1. **Nicolas signs off** on the Beat-1 choreography (review `map-review/ch01-beat1-northlook.png`).
2. **Commit** the wiring (build_campaign.py + YAML + harness.lua + HANDOFF/decisions) and auto-push.
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
