# Handoff — Content track 🔒 live state

Per-track live state for the **content lane** (Ch2+ slices, dialogue, art). Worktree doctrine,
ownership map, and trunk rules → `CLAUDE.md` §Tracks (read first; the lane guard is
`check.py check_lane_ownership`). Parallel-work + seam model → `docs/decisions.md` §Seam enforcement /
§Seam refinement. Backlog → GitHub issues (#49 ① Content). **Shared builds/gotchas/rules → `HANDOFF.md`
+ `CLAUDE.md`; this file holds only my current state + content-lane-specific gotchas.** Don't touch
`HANDOFF-pipeline.md`.

## Base state (clean — start here)
- **`inst/content` = `b0576f1`**, ahead of `main` (`f12643d`) by 3 commits (reward-budget ADR, design-lock
  handoff, **the ch02 reground**); fast-forwardable — merge down to `main` + push.
- **`make` green** as of the reground build (`b0576f1`), `verify_text` 0 runaway (3404 msgs), drift clean,
  `difficulty.py --chapter ch02` PARITY, `check.py` clean. Working tree clean except the `fireemblem8u`
  submodule pointer (build artifact — **never commit it**).
- **This session = ch02 REGROUND, built green.** The locked design (§1) is now implemented: vanilla-Ch2
  enemy parity (chardalyn berserkers), 3 GREEN chwinga protect layer with the per-unit soft-fail
  charm-gift mechanic (`CHECK_ALIVE` → `GIVEITEMTO` at the ending scene), sled + invented chest dropped.
  ADR extended in `decisions.md` §"Ch2 hosting". **Remaining for ch02 = the human checkpoints (§1 below).**

## Decisions locked this session (all recorded in the repo — don't re-derive)
- **Recruit budget** (`decisions.md` §"Recruit budget"): roster tracks vanilla's field-growth curve to a
  **~16–18 pool**, NOT capped at Ch5. `deploy_limit` = vanilla field per chapter; recruits fill role gaps.
  Killed the stale roadmap "stops at Ch5" line.
- **Reward/item budget** (`decisions.md` §"Reward/item budget" + `fe8-pacing-reference.md §3`, now a
  [decomp]-pinned per-chapter curve): a chapter's loot mirrors its `parity_reference` (channel + tier).
  Caps: no boosters/promo before parity ≥ FE8 **Ch5**; no Silver before **Ch8**; no Master Seal / Secret
  Shop / Sacred before **~Ch14a**. Placement follows the parity_reference, not our chapter number.
- **Chapter status** (`check.py check_chapter_status`): every chapter YAML carries `status: active|planned`;
  planned = brainstorm seed (tooling skips them in the curve/gate). ch00–02 active, ch03–08 planned.
- **ch02 map is a FAITHFUL reskin** of FE8 Ch2 (terrain diff vs `Ch2Map` = **2/225** cells). Vanilla Ch2's
  literal unit tiles ARE valid in-game — author against the committed **`.mar`** (the `map-review/*-layout.json`
  is stale, disagrees ~5 cells). (Corrects an earlier wrong "walkability diverged" note.)

## Now / Next (priority order)

### 1. 🎯 ch02 "Cold Welcome" (#22) — TACTICAL REGROUND DONE (`b0576f1`); 3 human checkpoints remain
The enemy/chwinga/gift/mechanic reground is **built green** (`inject_ch02` rewritten: parity enemies,
GREEN chwinga table `088B4718`, per-survivor `CHECK_ALIVE`→`GIVEITEMTO` gifts, reinforcements →`088B4758`,
sled dropped). What's LEFT before ch02 is "done":
- **(a) Dialogue reground — Nicolas co-write via `dialogue-pass`.** The LOCKED 2026-06-19 cutscene text
  still frames the dropped sled (Wolfram's rear-bark "…the sled"; ending narration "…ringing the sled")
  and calls the reinforcements "Snow Wolves", and the opening lacks a chwinga intro beat (a Marty line —
  the befriend-creatures diplomat). Wired as placeholder meanwhile; YAML has a PENDING block marking the
  three edits. Changing the opening beat count touches `CH02_OPENING_MSGS`.
- **(b) Chwinga + Vellynne art (#38/#39, #19).** Map-sprite reskin + portraits + name-text
  (Mote/Rime/Glimmer) over the DARA/KLIMT/MANSEL placeholder slots; Vellynne's cutscene bust. **Show
  Nicolas before commit** (no art committed without sign-off).
- **(c) mGBA load-test** ch01→ch02→win→chains; verify the chwinga LOAD green, the archer threatens the
  pegasi, and surviving chwinga deliver their charms at the ending.

The original locked-design spec is preserved below for reference (now implemented):

**A. Enemies → vanilla FE8 Ch2 "The Protected" parity (exact mix + tiles), reskinned as chardalyn berserkers.**
- Use vanilla Ch2's ACTUAL UnitDef positions + levels (from `git -C fireemblem8u show HEAD:src/events_udefs.c`
  tables `088B4344` enemies + `088B44AC` Bazba): ~6 Brigand (Iron Axe, **L1**, one drops a Vulnerary) + 1
  Archer (Iron Bow, L1) + **Bone** (named Brigand **L4**) + **Bazba** (Steel Axe). NOT my old L3 / defend-east
  placement.
- **Flavor = chardalyn berserkers** — Auril-maddened humans (physical axe/bow, **zero reskin stretch**, ties
  to ch02's frost-druid/Auril plot; book: Wilderness Encounters #7, p107). Boss **Halvar** → Bazba slot;
  miniboss **Grukk** → Bone slot.
- Re-verify `python3 tools/difficulty.py --chapter ch02` lands PARITY *with the chwinga green help counted*
  (see B) — vanilla enemies + 3 peg-chwinga ≈ vanilla Ch2 (5 + Ross/Garcia). If it sags, the chwinga are the
  swing factor, not enemy-level inflation.

**B. Protected → 3 GREEN Pegasus chwinga (DROP the sled entirely).**
- Chwinga = the vulnerable green allies you protect (mirrors vanilla's Ross/Garcia, who are green). Book:
  "Starting Quest: Nature Spirits" (p25–26) — harmless gift-giving snow-spirits; we arm them so they defend
  themselves (like Ross/Garcia, who aren't defenseless).
- **Chassis = `CLASS_PEGASUS_KNIGHT`** (verified balance match): 3 pegs ≈ Ross+Garcia in output (9–11 vs 12)
  & survivability; **Mage over-shoots** (magic hits Res≈0 on brigands) and **Myrmidon wildly over** (sword>axe
  + doubling = 3.5× output). The ch02 **archer hard-counters fliers** (iron-bow ×3) → that's the protect tension.
- **Green table:** repurpose vanilla Ch3's Colm green table (`UnitDef_088B4718`, already FACTION_GREEN) for the
  chwinga; the old build used it for RED reinforcements — reassign (fold any kept reinforcement into the RED
  `088B463C`, or drop the turn-3 wave). Cautious green AI (defend, don't suicide). `fe_name` ≤12.
- **NEW mechanic:** green protected allies + per-unit soft-fail. A chwinga that dies forfeits *its* charm only
  (set a flag on death, checked at chapter end) — not a game over. This is the chapter's signature beat.
- **Art (checkpoint, #38/#39):** tiny-spirit reskin over the Pegasus chassis — show Nicolas before commit.

**C. Charms/gifts → the exact vanilla Ch2 village loot, 1:1 with the chwinga.**
- Each SURVIVING chwinga gifts one of: **Red Gem `0x76` / Elixir `0x6D` / Pure Water `0x6E`** (vanilla Ch2's
  three village gifts). Deliver at chapter end gated on the per-chwinga survival flag. In-budget by the
  Reward ADR (ch02 parity = FE8 Ch2 = gems + premium consumables; **no boosters/promos**).

**D. Keep / drop / dialogue.**
- KEEP: `deploy_limit` 5, party persists, **Baxby's cutscene join unchanged** (do NOT rewrite it), DefeatAll,
  lord auto-deploy, the 3 locked cutscenes. NO Talk-recruit in ch02 (Baxby = the recruit; Talk planned elsewhere).
- DROP: the sled (and its soft-fail/chest-forfeit framing) and my hand-placed positions.
- **Dialogue (invoke `dialogue-pass` skill):** the locked cutscenes don't mention the chwinga — they need a
  small intro beat (why they're on the road / the party shielding them; a Marty line fits — he's the
  befriend-creatures diplomat). Co-write per the skill; ground in `lore/marty.md`.
- **Gates:** `make` green · `verify_text` 0 · `difficulty.py --chapter ch02` PARITY · mGBA load-test (ch01→ch02
  →win→chains) · art sign-off (chwinga + Vellynne #19). ADR the locked design in `decisions.md` (extend
  §"Ch2 hosting") in the SAME commit (no separate spec doc — `feedback_no_spec_docs`).

### 2. 🅿️ #46 lord-select reskin — DESIGN LOCKED, PARKED (needs Nicolas at his computer for the render sign-off)
This is the deferred UI work ("pick up the lord ux when home"). Build = clone/adapt `prep_unitselect.c` →
**`engine/lord_select_screen.c`** (dedicated screen; real prep untouched), driven by build-generated
`gLordSelectCandidates[]` + a parallel pitch-msg table (portrait+name from each pid's `CharacterData`). Pitch
panel replaces the inventory panel (qualitative, no stats); Up/Down live-refresh; A → "Will N lead?" [Yes/No]
→ sets `LORDSEL_FLAG_BASE + i`. (a)-explainer once before (locked text in issue #46). Writable buffers →
`EWRAM_OVERLAY(0)`. Custom flair (distinct frame/title/tint) is in DoD, build-then-flair.
- **Reusable:** pitches committed in `pcs/*.yaml` (`lord_pitch:`, inert until wired); dead msg-ids — pitches
  `0x929–0x92F,0x932`, explainer `0x957` (`0x965–0x96E` are LIVE); `recordlord` exists in `harness.lua`
  (`PT_FPS=240 tools/playtest/run.sh recordlord` → `make_gif.py`). Gate: mGBA render → Nicolas sign-off;
  commit `Closes #46`+`Closes #21`; ADR already in `decisions.md` §Lord-select UI.

### 3. Supporting content / art
Vellynne portrait #19 · ch02 title card (gen_chapter_title atlas lacks C/W/d/m — VISUAL, sign-off) · enemy
YAML pass #18 · NPC/recruit stubs #17 · world-map unlock #29 · overworld sprites #38 · onboarding-parity #64.

## Watch out (content-lane only)
- **msg-id vetting is treacherous:** `data_battlequotes.c` stores ids 4-digit zero-padded (`0x0935`); naïve
  hex-grep gives false negatives. Vet by **content** + check `data_battlequotes.c` in the `0x0XXX` form. (ch02
  used dead Ch3-scene ids `0x98b–0x99a`, excluding the LIVE `0x993`/`0x994`.)
- **Writing any dialogue → invoke the `dialogue-pass` skill first.** Voice grounding: per-NPC `lore/*.md` §Voice
  + `lore/frostmaiden-voices.md` + `fireemblem8u/texts/texts.txt`. Read sources first; bring drafts.
- **DM notes are a baseline, not a cage** — invented content (e.g. ch02's combat; the canonical Targos leg has
  none) is legit; say canon-vs-invented, don't treat "not in the notes" as wrong. Story sources of truth:
  `References/DungeonMasterNotesIcewindDale.pdf` + the Frostmaiden book PDF (image-only; read pages via the
  Read tool's `pages`).
- **Reward placement follows `parity_reference`, not chapter number** (Reward ADR). Our MVP (parity ≤ Ch13) is
  below the Master-Seal/Secret-Shop line → promotions stay deferred to Revel's End.
- Long unit names overflow FE8's name buffer — add a short `fe_name` (≤12) to new units.
- Story bodies are `make`-regenerated; gate text changes with `python3 tools/verify_text.py`.
- **Chapter hosting (model on `inject_ch01`/`inject_ch02`):** each chapter rides the *next* vanilla slot
  (ch01→2; ch02→**3**); chains via `MNC2(<next slot>)`; an unhosted next chapter dead-ends on
  `dev_placeholder_scene`. ch02 is party-persist (no cast re-LOAD), DefeatAll (slot-4 goal donor), lord
  auto-force-deployed (flag hook — nothing per-chapter).
- **The repo moves under you:** parallel pipeline work lands on `main`. Re-check `git log main` and sync before
  a big build.
