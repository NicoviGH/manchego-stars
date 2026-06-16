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

## NEXT UP — Ch1 dialogue pass + cutscenes (the slice's last item)

**This is the active task.** Use the **`dialogue-pass`** skill (voice-bible-grounded,
variant-based, vanilla-paced). Collaborative: bring 2–3 variants per beat, Nicolas picks; then
`record` GIFs for sign-off. Story sources of truth = the DM-notes PDF + the Frostmaiden book
(read them directly; see Gotchas for paths) — don't invent.

**Text beats still placeholder (message IDs, from `inject_ch01` in `tools/build_campaign.py`):**
- Northlook opening scene · lord-select prompt/confirm (`LORDSEL_PROMPT_MSG`, `LORDSEL_CONFIRM_MSGS`)
- house hints `0x93B` / `0x93C` · road sign `0x955` · chapter-ending `0x954` · chief quote `0x961`
- ⚠️ **Gendered text fix:** `0x93C` **and the chief death quote** still read masculine
  ("his/chief") — the Ch1 chief is **Izobai (female)**. Update to she/her.
- Optional: rename grunts "goblins"→"imps" in roster/dialogue (art is an imp; class ids stay `goblin-*`).

**Cutscenes-with-images (Nicolas's note "incl. cutscenes with images"):** scope the visual side
up front — what scene art each beat needs and the mechanism. Relevant existing machinery to reuse,
NOT reinvent:
- `inject_ch01` already stages cutscene `script:` blocks via `_script_to_message` (faces load
  lazily; `[A][LF]` page breaks; map-bubble width caveats are handled).
- `inject_opening_montage` / `inject_world_tour` (MONTAGE=1 builds) handle the lore-crawl card
  slides + drawn-map tour — the pattern for full-screen scene images already exists.
- Chapter title cards are IMAGES (`graphics/chap_title/chap_title_*.png`, glacial-blue theme).
- Portraits exist for the cast + Izobai; cutscene "faces" come from those slots.
- **First step when starting:** read the ch01 YAML `script:`/scene blocks + the `dialogue-pass`
  skill, then decide per-beat which need a drawn scene image vs. portrait-on-map dialogue, and
  bring options to Nicolas. Save any draft scene art to `map-review/` and `open` it (he can't see
  inline renders).

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
