# Handoff: **Ch1 slice (#21) — GOBLIN GRUNT MAP SPRITES SHIPPED. NEXT = Goodberry rename, then the dialogue pass (LAST).**

**Date:** 2026-06-16
**Session focus:** Executed the documented goblin-grunt-classes plan (#21). Ch1's soldier/
fighter grunts are now **goblins on the map** via a non-destructive class-clone mechanism;
vanilla soldier/fighter untouched. `make` green, `verify_text` 3404/0, `ch01win` PASS,
map screenshot confirms clean green goblins.

**Live checklist = GitHub issue #21 (Ch1 slice).**

---

## What shipped this session (committed + pushed to main)
**Enemy class reskins (#21) — goblin grunts.** A new campaign-agnostic mechanism that gives
an enemy a themed overworld sprite without touching its shared vanilla class:
- **Clone, don't reskin.** Reskinning `CLASS_SOLDIER`/`CLASS_FIGHTER` is campaign-wide. Instead
  we clone each base class into an unused slot — vanilla's ballista-empty classes
  `CLASS_BLST_REGULAR_EMPTY` (0x6A) and `CLASS_BLST_LONG_EMPTY` (0x6B) — copying the **whole**
  class body (stats + weapon ranks + terrain + `pBattleAnimDef` ⇒ combat identical), changing
  only `.number`, `.SMSId` and the move-table row. Vanilla soldier/fighter stay human.
- **Standard SMS palette, not the cast bank.** Enemies render their class SMS under the
  **enemy faction palette**, so the goblin sheet is remapped onto the base class's standard SMS
  index layout (`map_sprite_tool.remap_sms_palette`) — distinct from the cast's purple-bank path.
- **Both grunt classes share the ONE goblin sprite** (BoW/Norikins "Goblin Spearman", credited
  CREDITS.md row 29). Idle SMS 116 (0x74); walk reuses the soldier/fighter motion script.
- **Predicted maroon came out GREEN** in-game — the goblin's green skin nearest-maps to an SMS
  index the enemy palette leaves green (faction recolour hits cloth/armour, not skin). Happy
  accident; `remap_sms_palette` overrides are the knob if a future reskin reads wrong.
- Verified: `make` green, `verify_text` 3404/0, **ch01win PASS** (combat works via cloned anim;
  chief kill → Seize → ch3); map screenshot `/tmp/playtest-ch01win/05-ch01win-map.png` shows two
  clean green goblin grunts; `CLASS_SOLDIER`/`CLASS_FIGHTER` entries byte-unchanged (SMSId 0x3f/0x31).

## Files touched
- `tools/map_sprite_tool.py` — new `remap_sms_palette()` (sibling to `recolour`; targets a vanilla
  class wait sheet's palette instead of the cast palette).
- `tools/build_campaign.py` — new `inject_enemy_class_reskins(campaign)` + helpers
  (`_parse_class_enum_values`, `_class_field`, `_wait_table_len`, `_wait_symbol_at`,
  `_move_motion_at`, `_set_move_row`, `enemy_class_reskins`); wired into `main()` AFTER
  `inject_map_sprites` (SMS-id ordering) and BEFORE `inject_ch01`; `inject_ch01` grunt-class swap
  (`grunt_class()` via `reskin_by_base`); `src/data_classes.c` added to `PATCHED_DECOMP_FILES`.
- `campaigns/.../campaign.yaml` — `enemy_class_reskins:` block (goblin-soldier/goblin-fighter).
- `campaigns/.../map_sprites/goblin-spearman.png` (+ `_mu.png`) — vendored stand/walk sheets.
- `docs/decisions.md` — Art & Audio: the clone-into-unused-slot decision (dated 2026-06-16).

## NEXT SESSION (in order)
1. **Goodberry rename** (Vulnerary → Goodberry party-wide) — within this slice.
2. **Dialogue pass LAST**: Northlook opening, lord-select prompt/confirm, house hints
   0x93B/0x93C (note: 0x93C + the chief death quote still read **masculine "his/chief"** —
   update for **Izobai/female** in the dialogue pass), road sign 0x955, ending 0x954,
   chief quote 0x961; then `record` GIFs → Nicolas sign-off. Use the `dialogue-pass` skill.
3. Carried: #29 world map; Scramsax Hero mug [F2E] license recheck; **AlexYTXG Bandit-Peg +
   BoW goblin-spearman license recheck before distribution** (no [F2E] tag on the bandit-peg
   filename; BoW goblin IS [F2E]); ch02+ YAML `ea_file:` schema cleanup.

## Current state
- ✅ Ch1 engine fully machine-verified (entry/preps/cap, lord-select force-deploy + game over,
  win-by-Seize). `make` green, `verify_text` 3404/0, playtests PASS (ch00 win/gameover/retreat,
  ch01 default-lord, ch01lord, ch01win).
- ✅ **Izobai boss portrait shipped** (commit 5459864). Nicolas approved the bust.
- ✅ **Goblin grunt map sprites shipped** (this session). Green goblins on the map; reusable
  enemy-class-reskin mechanism for future themed enemies.
- ⚠️ Dialogue still placeholder; gendered chief text needs the Izobai/female pass.
- ⚠️ ch01 ending MNC2(0x3) lands on vanilla Ch3 until ch02 is wired.

## Blockers
- None.

## Key files
- `tools/build_campaign.py` — `inject_enemy_class_reskins` (~after `_inject_mu_sprites`),
  `GUEST_PORTRAIT_MAP` (izobai→Breguet), `inject_ch01` (`CH01_CLASS_IDS`, `grunt_class`,
  `enemy_entry`, chief name/quote staging).
- `campaigns/.../campaign.yaml` `enemy_class_reskins:` — the reskin catalog.
- `campaigns/.../chapters/ch01-the-iron-trail.yaml` — chief = "Izobai", goblin roster.
- `fireemblem8u/src/data_classes.c` (gClassData clones), `src/unit_icon_move_data.c` (move rows
  105/106 repointed), `src/unit_icon_wait_data.c` (goblin wait row 116) — injected build artifacts.
- `tools/playtest/harness.lua` — `ch01win` (`ch01win-map` shot = the goblin verification frame).

## Gotchas (carried)
- **rodata is discarded by the decomp ldscript**: injected `static const` tables / `""`
  literals → link error. Use `CONST_DATA` (.data); `gClassData` is already `CONST_DATA`.
- The move/class tables index by **`classId-1`** (NOT SMSId); the wait table indexes by SMSId.
  Clone the class slot FULLY so combat doesn't crash.
- Story text: YAML `script:` → build generates bodies; `make` overwrites manual decomp edits.
  Gate: `python3 tools/verify_text.py`.
- Odd-length NAME strings: pad with `[.]` (terminator parity).
- gDefeatTalkList: chapter-keyed entries at the HEAD; never after `{.pid=-1}`.
- Vanilla facts: `git -C fireemblem8u show HEAD:<file>`. **Never commit the `fireemblem8u`
  submodule pointer.**
- Bash cwd drifts; the built ROM lands at `fireemblem8u/fireemblem8.gba` (NOT repo root).
- Synthetic macOS keypresses don't reach mGBA; in-emulator Lua is the path. Playtest
  screenshots can land mid-transition — linger/extra A.
- PNG → `open` (Preview); GIF → `open -a Safari`.
- Pinky is male ("he"). Izobai is female ("she").
- Frostmaiden book (`references/References/icewind-dale-...pdf`, 324pp, **image-only, no text
  layer** — use `pdftoppm`) PDF page = printed + 1; DM notes
  `.../References/DungeonMasterNotesIcewindDale.pdf` (has a text layer).

## Memory
[[manchego-stars-project]] · [[feedback_custom_art_lever]] · [[feedback_nicolas_not_an_artist]] ·
[[project_manchego_stars_portrait_pipeline]] · [[feedback_show_before_committing_art]] ·
[[reference_fe_repo]] · [[feedback_vendor_community_assets]] · [[manchego-stars-automated-playtests]] ·
[[manchego_stars_guest_map_sprite_wiring]] · [[project_manchego_stars_winter_reskin]] ·
[[feedback_answer_before_picker]] · [[project_manchego_stars_cast_notes]] (Pinky=he; Izobai=she)

## Standing rules
Combat = pure vanilla FE; field parity with vanilla ch N is doctrine (cap = parity; chosen
lord force-deployed). Custom art on EVERY sprite part, follow concept faithfully, one
artwork at a time, **show before committing**. Story/dialogue = collaborative (variants →
Nicolas picks). Auto-push to main once green; never commit the `fireemblem8u` submodule
pointer. Playtests machine-run for logic, Nicolas for feel.
</content>
</invoke>
