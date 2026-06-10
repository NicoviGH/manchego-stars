# Handoff: **PC voice interview COMPLETE — all 10 voices locked into lore/*.md. NEXT = the FULL Ch1 slice (#21, The Iron Trail): map → roster/enemies → objectives/events → playtests → dialogue pass LAST.**

**Date:** 2026-06-10
**Session focus:** ran the full PC voice interview with Nicolas (one round per PC,
batched where he batched) and wrote a §Voice section into every PC's lore file —
Braulo, Marty, Meesmickle, Rootis, Sclorbo, Prof RBG, Wolfram, Pinky, plus writing
rules codified for Pepperjack & Brie. The dialogue-pass skill now has a complete
voice-bible bench for the whole cast.

**Live checklist = GitHub issues (#20 ch00 done, #43 closed, #21 = Ch1 slice).**

---

## NEXT SESSION (in order)
1. **Full Ch1 slice (#21, The Iron Trail)** — same order as ch00: map → roster/enemies →
   objectives/events → playtests → dialogue pass LAST (Northlook hiring scene opens ch01
   and owns the location card + hiring beat; decisions.md §Story & Dialogue). Don't
   start with dialogue — Nicolas's explicit correction, now twice affirmed.
2. **#29 world map** — the tour's drawn maps bootstrap it; the WM screen itself (nodes,
   travel) is still vanilla Magvel.
3. Scramsax Hero mug still needs the [F2E] license recheck before distribution (carried).
4. **Goodberry item rename** (new, from the interview): Nicolas intends to replace
   Vulneraries with **Goodberries** party-wide (Marty keeps the party fed in-fiction).
   Wire during the Ch1 slice or as a standalone text/item tweak; intent recorded in
   `lore/marty.md` §Signature gear.

## Voice interview outcomes (all shipped, committed per-PC)
- **Braulo** — quiet decider; deal-as-justice ("that was the deal"); full plain
  sentences, no caveman-speak, no jokes; isopod-in-shell scene gag (stares at Marty,
  never acknowledged). Calibration: the maer-speaker payment fight he started.
- **Marty** — Nicolas's own PC. Rapport spores read as NORMAL dialogue; spore-cough
  gag before his first line to anyone new; cheerful barista diplomat whose powers are
  horrifying (irony is the voice); goes silent when violence starts. Calibration:
  Lupin the wolf-leader recruitment, maer parley, isopod jailbreak.
- **Meesmickle** (he/him — file pronouns FIXED from she/her) — Salem-from-Sabrina dry
  one-liners, delivered flat; low line-count by design.
- **Rootis** (he/him) — wholesome Olaf-but-not-silly; matter-of-fact snow-body humor;
  overcomplicated-theory flaw from his sheet played straight (Nicolas confirmed once
  he saw it's sheet-sourced); low line-count by design.
- **Sclorbo** (he/him) — NEVER speaks: impression/gesture stage-direction text only,
  rendered as parentheticals in-ROM (no italic font) — deliberately distinct from
  Marty. Secret stays buried (unplayed hook). Low line-count by design.
- *(The Meesmickle/Rootis/Sclorbo players are the table's introverts → low
  line-counts are AUTHENTIC, not a gap. All three abstained from the Bremen fight.)*
- **Prof RBG** — Professor Ratigan register; cheese puns constantly ("Cheesed to meet
  you", "Sounds Gouda to me!") + "Um, actually—" corrections; ex-mobster with an
  underground rat network (added to his Backstory); **the puns NEVER stop** — his
  dark side (kobold execution) shows in deeds, not a changed register (Nicolas's
  correction); warmth reserved for Pinky.
  His banned list is inferred, not interviewed — confirm opportunistically.
- **Wolfram** — materials-science nerd (smells/tastes/EATS metal); METALLO is
  backstory, NOT a speech tic; friendly, never backs down. Calibration: answered the
  Bremen speaker's intimidation by biting his axe.
- **Pinky** — childlike, reverential, "Father said I could!"; volunteers for danger
  (mine scout). Same player as RBG (Pinky was his construct). Save "am I real?" for
  the finale Wish — no early angst.
- **Pepperjack & Brie** — §Speech extended with dialogue-pass writing rules:
  punctuation/repetition carry meaning, others translate, comprehension never the
  joke, banned from any word but their own name.
- Cast-notes memory updated: pronouns, Nicolas-played-Marty, RBG/Pinky same player.

## Current state
- ✅ New Game (MONTAGE=1): 7-card crawl over aurora mural → 6-card Icewind Dale tour
  over the two drawn maps → ch00. Default `make` keeps the straight-to-map dev boot.
  **Distribution (#37) must set MONTAGE=1.** Both modes green; `verify_text` 3404/0
  both; win playtest passes both.
- ✅ ch00 DONE end-to-end (#20); save-slot banners all blue.
- ✅ Voice bibles complete: §Voice in ALL PC lore files + hlin/scramsax/sephek;
  `lore/npc-bench.md` = minor-NPC toolkit. (This session — lore-only commits
  `95abb08`…`95c9ba1`, no ROM changes, build untouched.)
- ⚠️ ch01+ chapter YAMLs still carry aspirational `ea_file:` fields (schema cleanup).
- ℹ️ nanobanana MCP broken (retired model id); Nicolas runs Gemini by hand — prompt
  recipe pattern in `map-review/43-tour-map/gemini-prompt.md` (gitignored).

## Blockers
- None.

## Key files
- `campaigns/.../lore/*.md` — voice bibles (§Voice now exists for EVERY PC + guests).
  `lore/npc-bench.md` = minor-NPC toolkit.
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
- [[manchego-stars-project]] · [[project_manchego_stars_cast_notes]] ·
  [[feedback_collaborative_story_planning]] · [[feedback_answer_before_picker]] ·
  [[feedback_sharing_visual_drafts]] · [[feedback_use_decomp]] ·
  [[feedback_show_before_committing_art]] · [[manchego-stars-automated-playtests]] ·
  [[feedback_check_references_for_art]]

## Standing rules
Combat = pure vanilla FE. Story/dialogue = collaborative (variants → Nicolas picks; full
quotes in picker descriptions); in-engine review = GIFs via `record`, opened in Safari,
wait for his OK before committing art-visible content. Auto-push to main once green;
never commit the `fireemblem8u` submodule pointer. Playtests machine-run for logic,
Nicolas for feel.
