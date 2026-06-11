# Handoff: **Ch1 slice (#21) under way — MAP DONE (painted+committed). NEXT = engine: trace the prep-screen gate → deploy caps (`deploy_limit: 4`) → #42 player-chosen lord → goblin wiring → playtests → dialogue LAST.**

**Date:** 2026-06-10
**Session focus:** Ch1 "The Iron Trail" slice — base-map concepts → Nicolas picked B
(Ch13a layout, winter-reskinned) → flow/difficulty/win-condition worked out with him →
**Field parity doctrine** decided & recorded → Nicolas's editor paint pass → map
compiled, YAML matched to the paint, all pushed (`b2ff3cf`…`0b8dbc6`).

**Live checklist = GitHub issues (#21 = Ch1 slice; #42 pulled INTO the slice).**

---

## THE TWO DECISIONS THAT SHAPE EVERYTHING (recorded in decisions.md, dated 2026-06-10)
1. **Field parity** — our chapter N mirrors vanilla FE8 chapter N **on the field, both
   sides**: `deploy_limit` = vanilla's ally-slot count (pacing-ref §1b table, [decomp]),
   enemy counts/levels/AI mirror vanilla ch N (classes reskinned to our fiction). Cast
   being recruited ≠ fielded. Ch1 = **4 deploy vs 7+3 goblins**. Map layouts may be
   borrowed from ANY vanilla chapter; the cadence anchor is always same-numbered ch.
2. **#42 (player-chosen lord) ships in THIS slice** — menu after ch00 ending, persisted;
   chosen PC carries `EVFLAG_GAMEOVER` (lose = lord falls); `CanUnitSeize` patched to
   the chosen pid (win = lord seizes). Others keep flag-less "retreat" quotes.

## NEXT SESSION (in order)
1. **Trace the prep-screen gate.** `hasPrepScreen` in chapter_settings.json is False for
   EVERY chapter incl. ones that show preps in-game → the JSON field is dead; find the
   real gate in C (start: gamecontrol.c chapter-start flow / prep proc entry). Then:
   `deploy_limit: 4` → build_campaign emits 4 ally slots + Pick Units, lord force-deployed.
2. **#42 lord select** (menu UI, save persistence, death→EVFLAG_GAMEOVER hook,
   `CanUnitSeize` patch — vanilla hardcodes Eirika/Ephraim at `bmdifficulty.c:61`).
3. **Wire ch01 into the build** (model on `inject_prologue`): map pieces (.mar committed),
   roster per YAML (3 soldier + 3 fighter goblins lv1 autolevel, chief = Armor Knight lv4
   iron lance Breguet AI `{0x3,0x3,0x9,0x20}` on (21,7), +3 west spawns turn 3), Seize
   objective + lose hook (gDefeatTalkList HEAD rule!), road sign (8,8), 2 hint houses.
4. Playtests (win=seize, gameover=lord falls) via tools/playtest; **dialogue pass LAST**.
5. **Goodberry rename** (Vulnerary→Goodberry party-wide) — lands within this slice.
6. Carried: #29 world map; Scramsax Hero mug [F2E] license recheck.
7. **GitHub housekeeping (permission-blocked this session):** #21 body needs the slice
   checklist; #42 needs a "pulled into slice" comment. Content drafted — re-run with
   Nicolas present to approve the `gh` calls.

## Ch1 design (source of truth = chapters/ch01-the-iron-trail.yaml)
- Map: 25×16 Ch13a layout through snowy-bern. Nicolas painted: Bryn Shander compound
  (west edge, village door **B8=(1,7)**), fort camp structures (glitchy wall-fragment
  tiles globally → forts), **ruins arch (21,7) = camp center = seize tile = chief's
  tile**, north house **N3=(13,2)**, ridge smoothing.
- Hint houses = vanilla Ch1 pattern (msgs 0x93B/0x93C: NO items, pure tactical hints):
  compound = fort-terrain hint; north = boss hint ("scrap-plate turns blades; magic
  (def→res) + Braulo's axe-over-spear beat it") — text written in the dialogue pass.
- Triangle reality: cast has ZERO sword users (axes Braulo / lances Wolfram+Pinky /
  bows RBG / tomes+staves rest). Old "party's swords" YAML note was stale — fixed.
- Goblins are FIGHTERS not brigands (no peak-crossing pathing; no village razing).
  Ridge-crossing lesson deferred to ch02 (vanilla Ch2's gimmick).

## Tried/learned this session
- Vanilla facts MUST come from `git -C fireemblem8u show HEAD:<file>` (working tree is
  our injected build artifacts — ch1-eventudefs.h currently holds our ch00 cast!) or
  from `baserom.gba` (hex-labeled symbols encode vanilla addresses; UnitDefinition is
  20 B, `include/bmunit.h:195`; faction bits: blue=0 green=1 red=2).
- Vanilla Ch13a (our map donor) is a Defend-12-turns map; our reversed Seize use keeps
  its design grammar (held east line, edge-entry lanes). Full decode in chat → key
  numbers pinned in `docs/fe8-pacing-reference.md` §1b.
- Editor tooling generalized: `gen_map_editor.py <Layout> <out.html> <download.json>`,
  `import_map_layout.py <stem> [src]` (compiles .mar/.json + renders preview).
- Paint-pass round trips: verify authored YAML coords against the painted terrain
  (3 coords had landed on peaks/walls); ASCII walkability dump + overlay render
  (`map-review/21-iron-trail/painted-with-units.png`) before sign-off.
- Browser-tab gotcha: TWO editors may be open (old prologue editor downloads
  `prologue-layout.json`!) — check export DIMENSIONS before importing; never import a
  15×10 grid into ch01.

## Current state
- ✅ Ch1 map committed: `maps/ch01-the-iron-trail.{mar,json}` (NOT yet injected into the
  ROM build — build_campaign wiring is step 3 above). `make` untouched this session →
  still green from voice-interview session.
- ✅ decisions.md §Field parity; fe8-pacing-reference §1b (vanilla deploy-slot table +
  full vanilla Ch1 field table); ch01 YAML fully rewritten (parity + paint-matched).
- ✅ ch00 DONE (#20); New Game montage flow unchanged. Voice bibles complete (lore/*.md).
- ⚠️ ch02+ YAMLs still carry aspirational `ea_file:` fields (schema cleanup, carried).
- ℹ️ Stray uncommitted: `map-review/` renders (gitignored); two old `prologue-layout*.json`
  in ~/Downloads (Jun 8, 5 cosmetic ch00 tweaks never imported — confirm or trash).

## Blockers
- None. (#42 menu UI is the biggest unknown; prep-gate trace is the first domino.)

## Key files
- `campaigns/.../chapters/ch01-the-iron-trail.yaml` — the slice's source of truth.
- `campaigns/.../maps/ch01-the-iron-trail.{mar,json}` — painted layout (compiled).
- `map-review/21-iron-trail/` — editor.html, concept renders, REVIEW.md, unit overlay.
- `docs/decisions.md` §Field parity, §Game over, §gDefeatTalkList — the rules ch01 wiring must follow.
- `docs/fe8-pacing-reference.md` §1b — vanilla field counts [decomp].
- `tools/{gen_map_editor,import_map_layout,render_reskin_concepts}.py` — map tooling (now generic).
- `fireemblem8u/src/bmdifficulty.c:61` `CanUnitSeize`; `bmtrick.c` game-over check
  (`EVFLAG_GAMEOVER || CountAvailableBlueUnits()==0`) — #42 patch points.
- `tools/build_campaign.py:inject_prologue` — the model for `inject_ch01`.

## Gotchas (carried)
- Story text: YAML `script:` → build_campaign generates bodies; `make` overwrites manual
  decomp edits. Gate: `python3 tools/verify_text.py`.
- Odd-length NAME strings: pad with [.] (terminator parity).
- gDefeatTalkList: chapter-keyed entries at the HEAD of the table; never after `{.pid=-1}`.
- Synthetic macOS keypresses don't reach mGBA; in-emulator Lua is the path.
- Bash cwd drifts between tool calls — always `cd` to repo root for git/make (bit again).
- **PNG → `open` (Preview); GIF → `open -a Safari`.**
- Frostmaiden book: `references/References/icewind-dale-...pdf` (symlink →
  `/Users/Yonick/Documents/D&D/5E/`); DM notes:
  `/Users/Yonick/Documents/Claude/Projects/Manchego Stars / Fire Emblem Game/References/DungeonMasterNotesIcewindDale.pdf`.
- PDF page = printed page + 1.

## Memory
- [[manchego-stars-project]] · [[feedback_fe-strictness]] (field parity is its sharpest
  form yet — recorded in decisions.md) · [[feedback_collaborative_map_design]] ·
  [[feedback_use_decomp]] · [[feedback_answer_before_picker]] ·
  [[feedback_sharing_visual_drafts]] · [[manchego-stars-automated-playtests]] ·
  [[feedback_show_before_committing_art]]

## Standing rules
Combat = pure vanilla FE; **field parity with vanilla ch N (both sides) is now doctrine**.
Story/dialogue = collaborative (variants → Nicolas picks); in-engine review = GIFs via
`record` in Safari, wait for OK before committing art-visible content. Auto-push to main
once green; never commit the `fireemblem8u` submodule pointer. Playtests machine-run for
logic, Nicolas for feel.
