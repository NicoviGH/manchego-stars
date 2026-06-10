# Handoff: **#43 CLOSED (full opening montage shipped + GIF-approved). NEXT = resume the PC voice INTERVIEW (designed, zero answers collected — Braulo's questions are pending), then the FULL Ch1 slice (#21); dialogue pass comes LAST in the slice.**

**Date:** 2026-06-10
**Session focus:** shipped the #43 world-map tour half (two drawn-map backdrops + the
rewritten prologue WM event + a save-slot palette fix), closed #43; then pivoted to
dialogue foundations: credits for the new purchased assets, NPC-builder folded into the
dialogue skill, sequencing corrected (full Ch1 before any ch01 dialogue), and a
structured PC voice interview DESIGNED and kicked off — Nicolas ended the session right
at the first question, so NO answers exist yet.

**Live checklist = GitHub issues (#20 ch00 done, #43 closed, #21 = Ch1 slice).**

---

## NEXT SESSION (in order)
1. **Resume the PC voice interview** — the turn-ending questions for **Braulo** are
   already asked (see §Interview state below; re-ask them verbatim if needed). One PC
   per round: persona → speech habits → remembered line (calibration) → what would feel
   wrong (banned list). After each PC, write the §Voice section into their
   `lore/<pc>.md` immediately (format = `lore/hlin-trollbane.md` §Voice: one-line
   summary, **Diction rules**, **Calibration lines**, **Banned**). Commit per-PC or in
   batches; these are text-only (no GIF gate).
2. **Full Ch1 slice (#21, The Iron Trail)** — same order as ch00: map → roster/enemies →
   objectives/events → playtests → dialogue pass LAST (Northlook hiring scene opens ch01
   and owns the location card + hiring beat; decisions.md §Story & Dialogue). Don't
   start with dialogue — Nicolas's explicit correction this session.
3. **#29 world map** — the tour's drawn maps bootstrap it; the WM screen itself (nodes,
   travel) is still vanilla Magvel.
4. Scramsax Hero mug still needs the [F2E] license recheck before distribution (carried).

## Interview state (step 1's working notes)
- Order: roster — **Braulo (pending)** → Marty → Meesmickle → Prof RBG → Rootis →
  Sclorbo → Wolfram → Pinky (RBG's homunculus son, he/him) → offer Pepperjack & Brie
  (their voice is done BY DESIGN: each only says its own name, Pokémon-style).
- Braulo's pending questions (asked, unanswered): (1) table persona when his player
  spoke in character; (2) speech habits — sentence length, tics/catchphrases, how he
  addresses the party, crab/ocean vocabulary; (3) a line/moment actually said at the
  table (calibration gold, paraphrase fine); (4) what would feel WRONG from him (banned).
- Seeds already in lore files: Braulo = thrifty hermit-crab Berserker, 40, "The Next
  Shell is always over the horizon", greed flaw. Marty = myconid barista druid,
  **Speech: none** on sheet — interview must settle how a speechless PC gets FE text
  (spores? emotes? translated by others?). Meesmickle = vampire-tabaxi fiend warlock
  (NO personality section at all — most blank slate). RBG = lawful-evil artificer,
  compulsive cheese-phrases ("You have left me quite discheesed") — already a diction
  rule. Rootis = snowperson sorcerer, mystery-lover, overcomplicates. Sclorbo = chwinga
  lore bard, helper/encourager, shameful secret. Wolfram = scaleless drakeborn, avatar
  of METALLO (first being to create metal). Cheese is the campaign's running gag
  (Manchego Stars, Pepperjack, Brie, "discheesed").

## Accomplished (this session)
- **#43 tour half → CLOSED**: book regional map became TWO drawn-map backdrops (Gemini
  Magvel-style repaint of the dale + purchased hand-drawn ten-towns close-up, icy
  duotone, all towns/lakes re-lettered in 3×5 micro-caps); new `tools/gen_drawnmap.py`
  converts any source art to the FE8 drawn-map format; `inject_world_tour` rewrites
  `EventScrWM_Prologue_Beginning` with the 6 locked cards (msg 0x8DB), A→B map swap
  under FADI/FADU, WM_MOVECAM2 pan (y 24↔48) for the Redwaters card. Full
  New-Game-to-map GIF approved ("perfect"). Pushed `6865c9a`.
- **Save-slot select fix** (Nicolas's review nit): all three slot banners now
  theme-blue — `inject_title_theme` extended through `gUnknown_08A07AEA/B0A`
  (`sub_80895B4`'s config&1 table continues past the 9-color label). Verified
  in-emulator; difficulty-mode banners keep their semantic colors.
- **CREDITS.md**: Joel Kleine's *Ten-Towns Hand Drawn Maps and NPC Builder* (purchased,
  [DriveThru 353776](https://www.drivethrucomics.com/en/product/353776/icewind-dale-ten-towns-hand-drawn-maps-and-npc-builder),
  DMs Guild CCA); WotC section for in-ROM book art (mural + regional map); Gemini
  AI-disclosure for tour map A. `2fe7368`.
- **Dialogue skill trained on the NPC pack**: new `lore/npc-bench.md` (name bank, 12
  voice textures, Dale occupations, d20 quirks, 4 pre-gen wanderers with hooks — Pia
  the escaped-lottery girl is prime side-recruit material — and real inter-town travel
  times for pacing claims); SKILL.md routes minor NPCs there, never full bibles.
  `bfc09ba`.
- Sequencing corrected in HANDOFF (`bfe3c3a`): full Ch1 slice before ch01 dialogue.

## Tried but didn't work (debug trail, for posterity — details in decisions.md)
- First in-engine tour showed a checkerboard instead of the map: our tile 0 wasn't
  blank (GmapRm parks a cleared-to-tile-0 BG2 over the map during blocking display).
- Second attempt rendered both maps vertically mirrored: TSA rows are stored BOTTOM-UP
  (`TmApplyTsa` walks the dest upward). Both fixes live in `gen_drawnmap.gba_binaries`.
- Theorizing from C alone stalled twice; mGBA Lua register/VRAM dumps (`/tmp` one-off
  script pattern) found both bugs in minutes. Prefer that loop for display bugs.
- Save-slot green: NOT Pal_SaveMenuBG (it's all blue) — the slot plaques ride the
  chapter-title palette table via `sub_80895B4(config&1)`.

## Current state
- ✅ New Game (MONTAGE=1): 7-card crawl over aurora mural → 6-card Icewind Dale tour
  over the two drawn maps → ch00. Default `make` keeps the straight-to-map dev boot.
  **Distribution (#37) must set MONTAGE=1.** Both modes green; `verify_text` 3404/0
  both; win playtest passes both.
- ✅ ch00 DONE end-to-end (#20); save-slot banners all blue.
- ⚠️ ch01+ chapter YAMLs still carry aspirational `ea_file:` fields (schema cleanup).
- ℹ️ nanobanana MCP broken (retired model id); Nicolas runs Gemini by hand — prompt
  recipe pattern in `map-review/43-tour-map/gemini-prompt.md` (gitignored).

## Blockers
- None. The interview needs Nicolas live (it's his memory of the table).

## Key files
- `campaigns/.../lore/*.md` — voice bibles (§Voice exists only for hlin/scramsax/sephek;
  ALL PCs pending the interview). `lore/npc-bench.md` = minor-NPC toolkit.
- `.claude/skills/dialogue-pass/SKILL.md` — the dialogue workflow (inputs/gates).
- `tools/gen_drawnmap.py` — map-art → drawn-map converter (extend for #29).
- `tools/build_campaign.py` — `inject_world_tour`, `inject_title_theme` (save-slot fix).
- `campaigns/.../events/tour-map-{a-dale,b-towns}.*` — locked tour backdrops.
- `References/NPCs/2410173-Icewind_Dale_NPCs.pdf` — purchased NPC builder (distilled
  into npc-bench.md; full tables there).
- `docs/decisions.md` §Story & Dialogue — crawl + tour wiring entries (format gotchas).

## Gotchas (carried)
- Story text: YAML `script:` → build_campaign generates bodies; `make` overwrites manual
  decomp edits. Gate: `python3 tools/verify_text.py`.
- Odd-length NAME strings: pad with [.] (terminator parity).
- Synthetic macOS keypresses don't reach mGBA; in-emulator Lua is the path.
- Bash cwd drifts between tool calls — always `cd` to repo root for git/make.
- **PNG → `open` (Preview); GIF → `open -a Safari`** (Preview shows GIFs static —
  missed twice now).
- Frostmaiden book: `references/References/icewind-dale-...pdf` (symlink →
  `/Users/Yonick/Documents/D&D/5E/`); DM notes:
  `/Users/Yonick/Documents/Claude/Projects/Manchego Stars / Fire Emblem Game/References/DungeonMasterNotesIcewindDale.pdf`.
- PDF page = printed page + 1 (Cold Open boxed text: printed p.22 → PDF 23).

## Memory
- [[manchego-stars-project]] · [[feedback_collaborative_story_planning]] ·
  [[feedback_answer_before_picker]] · [[feedback_sharing_visual_drafts]] ·
  [[feedback_use_decomp]] · [[feedback_show_before_committing_art]] ·
  [[manchego-stars-automated-playtests]] · [[feedback_check_references_for_art]]

## Standing rules
Combat = pure vanilla FE. Story/dialogue = collaborative (variants → Nicolas picks; full
quotes in picker descriptions); in-engine review = GIFs via `record`, opened in Safari,
wait for his OK before committing art-visible content. Auto-push to main once green;
never commit the `fireemblem8u` submodule pointer. Playtests machine-run for logic,
Nicolas for feel.
