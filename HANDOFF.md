# Handoff: Ch1 slice (#21) — Goodberry SHIPPED. NEXT (active) = the Ch1 dialogue pass + cutscenes (incl. scene images).

**Date:** 2026-06-16
**Session focus:** Shipped the **Goodberry** reflavor (Vulnerary → name + custom blueberry
icon, party-wide) via two new campaign-agnostic, data-driven inject mechanisms; verified it
in-game. Slice work before this: Izobai boss portrait, Fire Imp grunt sprites. **The only
remaining Ch1-slice item is the dialogue pass** — and per Nicolas it includes the chapter's
cutscenes (scene art/images), not just text.

**Live checklist = GitHub issue #21 (Ch1 slice).** Latest commits (all on main):
`2a024e8` (goodberry playtest scenario), `f9c09cd` (Goodberry reflavor), `e2aa9ae` / `fe5a7a9`
(Fire Imp grunts), `5459864` (Izobai portrait).

---

## NEXT UP — Ch1 "The Iron Trail" dialogue pass + cutscenes (the slice's LAST item)

**This is the active task. START HERE on a fresh instance.** Use the **`dialogue-pass`** skill
(voice-bible-grounded, variant-based, vanilla-paced). Collaborative: bring 2–3 variants per beat,
Nicolas owns voice/picks, lock a beat before the next; then `record` GIFs (motion, not stills) →
sign-off. **Don't summarize from memory** — re-open the sources per beat.

### How it's wired (facts)
- **Our Ch1 is hosted on chapter slot 2** (`EventScr_Ch2_*` in `fireemblem8u/src/events/ch2-eventscript.h`);
  ch00 prologue is on slot 1 (the vanilla Ch1 group). All Ch1 wiring is **inline eventscript** via
  `_replace_brace_block` in `inject_ch01` (`tools/build_campaign.py`) — the YAML `ea_file:` fields are
  descriptive only; there are no `.ea` files.
- Text → `set_message_body` into `texts/texts.txt`; gate with `python3 tools/verify_text.py` (0 runaway);
  odd-length strings pad `[.]`. Message slots in use (slot-2 / vanilla-Ch1 dead slots):
  `LORDSEL_PROMPT_MSG=0x957`, `LORDSEL_CONFIRM_MSGS=0x959..0x95F` (per-candidate), road sign `0x955`,
  house1 `0x93B`, house2 `0x93C`, ending `0x954`, chief death-quote `0x961`. Boss rides the **BREGUET**
  slot (`CH01_BOSS_SLOT`).
- Reusable scene-art machinery (do NOT reinvent): `_script_to_message` (lazy faces, `[A][LF]` pages,
  29-char on-map bubble wrap); `inject_opening_montage`/`inject_world_tour` (full-screen card slides +
  drawn map, MONTAGE=1) = the pattern for drawn cutscene backgrounds; chapter title cards are images
  (`graphics/chap_title/chap_title_*.png`, glacial-blue). Save draft scene art to `map-review/` + `open`.

### CANON DIGEST (read from source this session — cite, don't paraphrase from here when drafting)
**DM notes** (`references/References/DungeonMasterNotesIcewindDale.pdf`, full text): party of "adventurers
and misfits" meets in **The Northlook** (inn/tavern, de-facto capital **Bryn Shander**); **three dwarves**
ask help tracking a **missing shipment of iron ingots**; party tracks the **missing sled** to a
**dismembered body**, then finds **goblins** stealing the ingots; dispatch, return iron for a reward.
Then **Duvessa Shane, Speaker of Bryn Shander**, hires them for Ten-Towns' troubles (shorter days /
worsening winter) and points them to **Targos** (unrest after a **frost-druid** visit); as they leave,
**Velynne Harpell** (Arcane Brotherhood) warns to watch for a **missing orb** her colleague stole. Party
buys **Baxby the axe-beak** to pull a town-to-town sled; head west to Targos.
**Book** (`...icewind-dale-rime-of-the-frostmaidenpdf_compress.pdf`, image-only; PDF pg = printed+1):
- *Foaming Mugs* quest, printed p.34 (PDF 35–36): ingots are **Clan Battlehammer**'s from the mine at
  **Kelvin's Cairn**, to be delivered to **Blackiron Blades** (Bryn Shander smithy); reward = a **gemstone
  (50 gp) each + 10% Blackiron discount** + dwarven friendship; need **snowshoes**. The three frostfallen
  dwarves: **Hruna** (speaks for the group; raspy voice from years of smoking; lost her right ear + two
  fingers to frostbite), **Korux** (silent; lost three fingers, two toes, his nose; can cover snowshoe cost),
  **Storn** (terrified of white dragons, keeps glancing at the sky).
- *Oobok's Remains* (PDF 36): the dismembered corpse is **Oobok the dwarf**, torn apart and **eaten by a
  YETI** (it took his head); the goblins' snowshoe tracks (a half-dozen Small humanoids) lead south to the
  thieves hauling the sled. → a two-killer mystery: yeti ate Oobok, goblins took the steel.
- *Goblins / Izobai* (PDF 36): **Izobai**, the **one-eared goblin boss**, commands a **trained (hooded)
  hawk** (the scout that spotted the sled) and rides atop a **20-ft wagon** with a **lit torch**, drawn by
  **two roaring polar bears**; six goblins haul the 900-lb sled.
- Bryn Shander (printed p.32) & locations (p.32–33): walled hill town; Auril's winter is strangling trade
  and the locals' goodwill ("no safer place to spend coin or the night"). **Duvessa Shane** = young
  **lawful-good human noble**, head of the Council/Speaker. **Sheriff Markham Southwell** = LG veteran
  enforcer. **The Northlook** = rowdiest tavern, best spot for leads/rumors; **owned by Scramsax** (retired
  sellsword/veteran — *our ch00 guest*), who bought & stuffed **Ol' Bitey**, the battle-scarred knucklehead
  trout mounted over the hearth (a prank spell makes it snap and sometimes sing). Duvessa portrait p.33;
  Sheriff portrait p.33.

### CHRONOLOGICAL BEAT OUTLINE (our flow ‖ FE8 Ch1 cadence parallel)
FE8 Ch1 parallel = the decomp `EventScr_Ch1_*` skeleton (slot-1 structure, now ch00's): BeginningScene
(loc title + ally scene + enemy/boss intro) → Turn1Enemy boss taunt → AllyReinforceArrive + Talks →
Houses ×2 → EnemyReinforceArrive → DefeatBoss/Seize → EndingScene → MNC2.

| # | Our beat | FE8 Ch1 parallel | Msg slot(s) | Speakers | Status | Image / background |
|---|----------|------------------|-------------|----------|--------|--------------------|
| 0 | Title card "The Iron Trail" | loc brown-box (0x664) | (title art) | — | ✅ shipped (glacial-blue) | **DONE** (image exists) |
| 1 | **Opening — The Northlook**: Scramsax's tavern; Hlin hands the seven off ("Ten-Towns needs younger hands"); Hruna/Korux/Storn explain the stolen ingot sled → hire the party | BeginningScene ally+enemy intro (0x90D/0x90E) | NEW scene text (precede lord-select) | Hlin, Scramsax, Hruna (+Korux/Storn beats), cast | ❌ **NOT WRITTEN** (jumps straight to lord-select) | **Drawn BG candidate: Northlook interior** (Ol' Bitey over the hearth). Portraits needed: Hruna/Korux/Storn (3 dwarves) |
| 2 | **Lord select**: "Who leads them north?" + per-PC confirm | (no vanilla analogue; #42) | 0x957 + 0x959.. | narration | ⚠️ functional placeholder | none (menu) |
| 3 | **Road sign** (tile 8,8): "BRYN SHANDER — 2 MILES. WATCH FOR WOLVES." | AREA flavor | 0x955 | sign | ⚠️ placeholder (ok) | none |
| 3b| **Oobok's body** on the trail (optional new beat): a PC reads the scene — yeti-torn dwarf, goblin tracks south | (no direct analogue) | NEW (or fold into sign/area) | a PC | ❌ optional/new | optional drawn BG: body in the snow |
| 4 | **House 1 (1,7)** terrain hint: goblins dug into the waystation; mounds shrug blows + heal | Visit1 (0x93B) | 0x93B | villager (FID_VillagerMan3) | ⚠️ placeholder → voice | none |
| 5 | **House 2 (13,2)** boss hint: scrap-plate turns blades, magic ignores plate, axe beats spear | Visit2 (0x93C) | 0x93C | villager | ⚠️ placeholder + ⚠️ **regender → Izobai (she/her)** | none |
| 6 | **Izobai turn-1 taunt** (optional new): one-eared boss, hawk on her arm, atop the wagon | Turn1Enemy boss taunt (0x930) | NEW (battle-talk slot) | Izobai | ❌ optional/new | none (portrait exists) |
| 7 | **Izobai death quote** (currently "Gah! The ironses were ours!") | DefeatBoss | 0x961 | Izobai | ⚠️ rewrite in her voice | none (portrait exists) |
| 8 | **Ending — recovery & retainer**: ingots recovered → **Duvessa Shane** + guards thank the party, hire them for Ten-Towns work, point to **Targos**; Braulo asks re: sled dogs → **Baxby** for sale. (Hook: **Velynne Harpell**'s missing orb, per DM notes) | EndingScene (0x918) → MNC2 | 0x954 → MNC2(0x3) | Duvessa, Braulo, (Velynne?) | ⚠️ one-line placeholder → full scene | **Drawn BG candidate: goblin camp aftermath / Duvessa at the gate**. Portrait needed: Duvessa Shane (book p.33 ref); maybe Velynne |

### IMAGE / BACKGROUND PLAN (Nicolas's ask #2 — tied to the beats above)
- **Drawn full-screen backgrounds (decide per beat, show-before-commit):** (a) **Northlook interior** [Beat 1],
  optional (b) **Oobok's body in the snow** [Beat 3b], (c) **goblin-camp aftermath / Duvessa arrives** [Beat 8].
  Mechanism = the montage/tour card-slide pattern.
- **New portraits (guest policy: vendor by default, custom if recurring):** **Duvessa Shane** (recurs as Speaker
  → likely custom from book p.33 ref) and the **three dwarves** Hruna/Korux/Storn (one-chapter → vendor/bench).
  Optional **Velynne Harpell** if the orb hook is used (she recurs later → custom eventually).
- **Already have:** cast portraits, Hlin & Scramsax (ch00 guests), Izobai, the title card, a villager FID.

### OPEN QUESTIONS FOR NICOLAS (resolve as we go, chronologically)
1. Beat 1: where does the **Hlin→party hand-off** live — here at the Northlook, or is it already covered by
   the ch00 ending (0x918 "Ten-Towns will need more hands")? Avoid repeating it.
2. Name **Oobok** / foreshadow the **yeti** (Beat 3b)? (Yetis/ice-trolls return at Easthaven.) Drawn BG or skip?
3. Lean into book canon for Izobai — **hawk + polar-bear wagon + torch** in her taunt, or keep it lean?
4. Ending: include the **Velynne Harpell orb** hook now (sets up later chapters) or hold it?
5. Grenade rename "goblins"→"imps" in roster/dialogue (art is an imp; class ids stay `goblin-*`)?
6. Cutscene-visual style overall: **drawn BGs** for 1/8 (cinematic, bigger lift) vs **portrait-on-map** (vanilla, fast)?

---

## Accomplished this session — Goodberry reflavor (#21)
The Vulnerary now reads **"Goodberry"** with a custom blueberry icon, party-wide. **Verified
in-game** (`tools/playtest/run.sh goodberry`: Hlin's item menu shows the berry icon + "Goodberry ×3"
+ "Restores some HP.").
- **Two data-driven, campaign-agnostic mechanisms** (engine/content boundary kept):
  - `inject_item_names` — `campaign.yaml item_names: {ITEM_ENUM: name}` → rewrites the item's
    `nameTextId` message (terminator-parity padded → `Goodberry[.][X]`).
  - `inject_item_icons` — `campaign.yaml item_icons: {ITEM_ENUM: asset}` → overwrites the item's
    tracked `graphics/item_icon/*.png` source (gbagfx makes the `.4bpp` at build). Both resolve
    id/iconId from `data_items.c` and the icon source from `data_item_icon.s` incbin order — nothing hardcoded.
- **Icon = `tools/item_icon_tool.py` `blueberry_grid` (design L2)**, authored in FE8's shared
  16-colour item-icon palette (blue body, dark calyx button, green branch from the button centre,
  left leaf). Asset: `campaigns/.../item_icons/goodberry.png`. Iteration renders in
  `map-review/goodberry-icon/` (gitignored).
- Cast per-unit inventory `name:` fields are documentation-only now (FE8 = one name+icon per item id),
  all unified to "Goodberry" (Meesmickle's blood-draught flavor kept as a comment).
- **Verified:** `make` green · `verify_text` 3404/0 · `ch01win` PASS · in-game capture PASS.

## Earlier in this slice (shipped, fully documented in `docs/decisions.md`)
- **Izobai boss portrait** (green-goblin reskin of an FE-Repo Bandit Peg mug; Nicolas approved).
- **Fire Imp grunt map sprites** via a reusable, non-destructive **enemy-class-clone** mechanism
  (`inject_enemy_class_reskins`; clones `CLASS_SOLDIER`/`CLASS_FIGHTER` into the unused ballista-empty
  slots, swaps only SMS/move rows, combat rides the cloned anim). Sprite authored in the standard SMS
  palette → reads red under the enemy faction palette. Lessons (pick a standard-palette sprite; remap
  to the *enemy* palette; green = ally colour so rejected; declare `frame:` for off-size sheets) and
  the full mechanism are in `docs/decisions.md` Art & Audio.

## Current state
- ✅ Ch1 engine fully machine-verified (entry/preps/deploy-cap, lord-select force-deploy + game over,
  win-by-Seize). `make` green, `verify_text` 3404/0; playtests PASS (ch00 win/gameover/retreat,
  ch01 default-lord, ch01lord, ch01win, goodberry).
- ✅ Izobai portrait · ✅ Fire Imp grunt sprites · ✅ Goodberry reflavor.
- ⚠️ **Ch1 dialogue still placeholder** (the active next task); gendered chief text needs the
  Izobai/female fix.
- ⚠️ ch01 ending MNC2(0x3) lands on vanilla Ch3 until ch02 is wired.

## Blockers
- None.

## Next steps (priority order)
1. **Ch1 dialogue pass + cutscenes** (see "NEXT UP" above) — the slice's last item. `dialogue-pass`
   skill; variants → Nicolas picks; fix the gendered Izobai text; scope cutscene scene-images;
   `record` GIFs → sign-off.
2. Carried: #29 world map; license rechecks before distribution — Scramsax Hero mug (no [F2E] tag),
   AlexYTXG Bandit-Peg portrait (no [F2E] tag); Fire Imp IS [F2E]; ch02+ YAML `ea_file:` schema cleanup.
3. Carried: wire ch02 so the ch01 ending stops landing on vanilla Ch3.

## Key files
- `tools/build_campaign.py` — text injectors `inject_item_names`, `_script_to_message`,
  `set_message_body`, `_wrap_fe_lines`; `inject_ch01` (cutscene `script:` staging, chief name/quote,
  `LORDSEL_*` message ids, house/sign/ending ids); `inject_opening_montage`/`inject_world_tour`
  (scene-image machinery); `inject_item_names`/`inject_item_icons` (Goodberry).
- `campaigns/.../chapters/ch01-the-iron-trail.yaml` — Ch1 `script:`/scene + roster (chief = "Izobai").
- `tools/verify_text.py` — text regression gate (run after every text change).
- `.claude/skills/dialogue-pass` — the dialogue co-writing skill (voice bible, variant flow).
- `tools/playtest/harness.lua` — scenarios incl. `record` (GIF capture for sign-off) and new
  `goodberry` (in-game item-menu capture); `tools/playtest/run.sh <scenario>`.
- `tools/item_icon_tool.py` — item-icon authoring (`blueberry_grid`, pack/unpack/render).

## Gotchas (carried)
- Story text: YAML `script:` → build generates bodies; `make` overwrites manual decomp edits. Gate:
  `python3 tools/verify_text.py` (sweeps for runaway/corruption).
- Odd-length NAME strings: pad with `[.]` (terminator parity); `name_message_body` handles it.
- Map speech bubbles top out ~29 chars/line and clip; full-screen Text_BG tolerates ~42 (see
  `_wrap_fe_lines`). `[A][LF]` = page break (2 visible lines/A-press); same-speaker turns coalesce.
- gDefeatTalkList: chapter-keyed entries at the HEAD; never after `{.pid=-1}`.
- **Item reflavor:** rename via `item_names:` (text) + `item_icons:` (a 16×16 indexed PNG in the
  shared item palette); the icon **source is the `.png`** (gbagfx compiles `.4bpp`), so inject the
  `.png`, not the `.4bpp`, and restore via git (`.4bpp` is an untracked build artifact).
- rodata is discarded by the decomp ldscript: use `CONST_DATA` (.data) for injected tables/literals.
- Vanilla facts: `git -C fireemblem8u show HEAD:<file>`. **Never commit the `fireemblem8u` submodule
  pointer** (decomp edits are build artifacts; stage repo files explicitly).
- Bash cwd drifts; the built ROM lands at `fireemblem8u/fireemblem8.gba` (NOT repo root).
- Synthetic macOS keypresses don't reach mGBA; in-emulator Lua is the path. Screenshots can land
  mid-transition — linger/extra A.
- PNG → `open` (Preview); GIF → `open -a Safari`. Nicolas can't see inline renders — save to
  `map-review/` and `open`.
- `gh` write commands are allow-listed in `~/.claude/settings.json`; self-modifying settings still
  needs explicit user authorization.
- Pinky is male ("he"). **Izobai is female ("she")** — load-bearing for the dialogue pass.
- Frostmaiden book (`references/References/icewind-dale-...pdf`, 324pp, image-only, no text layer —
  use `pdftoppm`); PDF page = printed + 1. DM notes `.../DungeonMasterNotesIcewindDale.pdf` (has text).

## Memory
[[manchego-stars-project]] · [[feedback_collaborative_story_planning]] · [[feedback_story_sources_of_truth]] ·
[[project_manchego_stars_dm_notes]] · [[feedback_show_before_committing_art]] · [[feedback_custom_art_lever]] ·
[[feedback_nicolas_not_an_artist]] · [[feedback_answer_before_picker]] · [[feedback_clean_doc_rewrites]] ·
[[manchego-stars-automated-playtests]] · [[feedback_fe_name_truncation]] · [[manchego_stars_text_terminator_parity]] ·
[[project_manchego_stars_cast_notes]] · [[feedback_sharing_visual_drafts]]

## Standing rules
Combat = pure vanilla FE; field parity with vanilla ch N is doctrine (cap = parity; chosen lord
force-deployed). Custom art on EVERY sprite part, follow concept faithfully, one artwork at a time,
**show before committing**. Story/dialogue = collaborative (variants → Nicolas picks). Auto-push to
main once green; never commit the `fireemblem8u` submodule pointer. Playtests machine-run for logic,
Nicolas for feel.
