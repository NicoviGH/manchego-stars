# Handoff — Content track 🔒 live state

Per-track live state for the **content lane** (Ch2+ slices, dialogue, art). Worktree doctrine,
ownership map, and trunk rules → `CLAUDE.md` §Tracks (read first; the lane guard is
`check.py check_lane_ownership`). Parallel-work + seam model → `docs/decisions.md` §Seam enforcement /
§Seam refinement. Backlog → GitHub issues (#49 ① Content). **Shared builds/gotchas/rules → `HANDOFF.md`
+ `CLAUDE.md`; this file holds only my current state + content-lane-specific gotchas.** Don't touch
`HANDOFF-pipeline.md`.

## Base state (clean — start here)
- `inst/content` synced to `main` base (`288b1a1`); **ahead by ch02 work** (`6a52682`, `74f9d16`) pushed to
  `origin/inst/content`.
- **`make` green**, `verify_text` 0 runaway (3404 msgs), drift clean, 12 unit tests pass. Working tree clean
  (only the `fireemblem8u` submodule pointer, a build artifact — **never commit it**).
- **Committed last session** (`eaaf340`): 8 `lord_pitch:` YAML fields + #46-reskin & seam-refinement ADRs.
  The hand-built lord-select menu was discarded (superseded by the reskin); `build_campaign.py` clean base.
- **Committed THIS session** (ch02, #22 — see §2): `6a52682` ch02 unit positions (vs the real hand-retiled
  map); `74f9d16` `inject_ch02` host wiring + 3 cutscenes (build-green). #22 boxes checked: Host/Units/Cutscenes.

## Now / Next (priority order)

### 1. 🚧 #46 lord-select — DESIGN LOCKED, build is the next task (reskin "Pick Units")

**Read first:** issue **#46** (the locked design + DoD checklist comment) + `decisions.md` §Lord-select UI.

A hand-built menu (custom frames + `StartFace2` bust + multi-line text drawn to BG) was tried and
**abandoned**: the bust wouldn't render over the scenic BACG (OBJ-vs-BG priority), `DrawUiFrame2` borders
didn't draw, text spilled. Nicolas's call: **clone-and-adapt a vanilla menu** — **`prep_unitselect.c`**
(the deploy "Pick Units" screen: already a scrollable unit list + live `PutFaceChibi` portrait + side panel).

**The build:**
- Clone+adapt `prep_unitselect.c` → **`engine/lord_select_screen.c`** (a *dedicated* screen; the real prep
  screen stays untouched). Campaign-agnostic; driven by build-generated `gLordSelectCandidates[]` + a parallel
  pitch-msg table; **portrait id + name from each pid's `CharacterData`** (no live-Unit dependency).
- **Pitch panel replaces the inventory panel** (qualitative, no stats). Up/Down live-refresh portrait + pitch;
  **A → "Will N lead the party?" [Yes/No]** → sets `LORDSEL_FLAG_BASE + i` (read by `LordSelect_GetPid`).
- **(a) explainer** shown once before the screen. Locked text (variant A): *"Choose who leads the party. Your
  leader must survive every battle -- if they fall, the journey ends."*
- `build_campaign.py`: generate the pitch-msg table, write pitch + explainer bodies (`set_message_body`),
  add a `vanilla_portrait_id`/`lord_pitch_text` helper, replace `CallLordSelectMenu` → `StartLordSelectScreen`.
  Wire `engine/lord_select_screen.c` into the decomp build (objects list + ldscript). **Use `EWRAM_OVERLAY(0)`
  for writable buffers** (the vanilla idiom — `events_script.o` discards `.bss`, which is why the hand-built
  `static struct Text` wouldn't link).
- **Custom flair (in DoD, NOT deferred):** distinct frame/title/tint so players don't confuse it with the prep
  screen minutes later. Build first, then flair.
- Gates: `make` green · `verify_text` 0 runaway · unit tests · **mGBA `recordlord` render → Nicolas sign-off**
  (show-before-committing). Commit `Closes #46` **and** `Closes #21`; ADR already in `decisions.md`.

**Reusable (already done — don't redo):**
- **Pitches** are committed in `pcs/*.yaml` (`lord_pitch:`, plain + qualitative). `build_campaign` doesn't read
  them yet (inert until the reskin wires them).
- **Vetted dead msg-id block** (zero live-script refs; not `data_battlequotes.c` death quotes): **pitches**
  `0x929,0x92A,0x92B,0x92C,0x92D,0x92E,0x92F,0x932`; **explainer** `0x957`. (`0x965–0x96E` are LIVE — flashback.)
- **Clone findings** (`prep_unitselect.c`): writable buffers `EWRAM_OVERLAY(0)`; list drawn to BG2, screen sets
  up its **own** full-screen bg (good — separates from the cutscene, and the flair pass owns the look); list
  source `MakePrepUnitList`/`GetUnitFromPrepList` (swap for the candidate table); `PrepUnit_DrawUnitItems` is the
  panel to replace with the pitch; `PrepUnit_HandlePressA` is the select hook to repoint at pick+confirm.
- **`recordlord`** already exists in `harness.lua` (pipeline-authored, on main) — use it for the render:
  `PT_FPS=240 tools/playtest/run.sh recordlord` → `tools/playtest/make_gif.py recordlord lord --name lord-select`.
  The menu cards are late in the frame sequence (~before the confirm); the GIF capture works as-is.

### 2. ch02 slice (#22) — ✅ HOSTED & build-green (commits `6a52682` positions, `74f9d16` inject_ch02)
**What landed (this session):** `inject_ch02` hosts Ch2 on chapter slot 3 — `make` green, `verify_text`
0 runaway, drift clean, 12 unit tests pass, cutscenes decode clean (spot-checked). ch01 → ch02 →
dev placeholder (ch03 unhosted) chains. ADR in `decisions.md` §"Ch2 hosting".
- **Positions** authored on the built **`.mar`**'s walkable tiles (plains/forest), verified in-bounds.
  The winter map is a **faithful reskin** of FE8 Ch2 (terrain diff vs `Ch2Map` = 2/225 cells), so
  walkability ≈ vanilla. Placement is our own defend-east arrangement (party+sled NW, boss far-east, rear
  wolves west edge) — NOT vanilla's literal tiles; mirroring vanilla exactly is an open option. (Author
  against the `.mar`, not `map-review/*-layout.json` — the review grid disagrees with the build.)
- **DefeatAll**: slot-3 host goal = vanilla slot-4's `defeat_all` template; `Seize(14,1)`+chests/doors dropped
  from `EventListScr_Ch3_Location` (`CountRedUnits()` win). Lord auto-force-deploys (flag hook; nothing per-chapter).
- **Cutscenes** built from the locked YAML: Vellynne opening (BACG, placeholder `FID_Ismaire` face), Wolfram
  turn-3 rear bark (auto-wrapped), Targos-inn ending (#58 opaque narration box). Halvar death quote wired.
- **msg-id pool** = dead vanilla Ch3 scene texts `0x98b–0x99a`; **`0x993`/`0x994` are LIVE battle quotes,
  excluded** (the hex-grep false-negative the gotchas warn about). (The handoff's old `0x933/0x937/0x938`
  spares were unused — the Ch3 scene pool is bigger and cleaner.)

**REMAINING for #22 (deferred, flagged in code + the ADR):**
- **Defend-in-place sled soft-fail** (novel green-unit + flag mechanic: sled death → forfeit chest+250g, not
  game over) **+ sled sprite** — the chapter's defining layer; not yet built.
- **Vellynne cutscene portrait #19** (placeholder vanilla face shows meanwhile).
- snow-wolf / road-bandit **map-sprite reskin** (vanilla brigand sprite for now; #38).
- **chest** + vulnerary drop placement (chest pos authored in YAML at `[5,11]`, not yet wired — needs a
  thief/key decision).
- **Title card** "Chapter 2: Cold Welcome" — `gen_chapter_title` atlas lacks C/W/d/m + the "Ch.2:" prefix;
  extend `LETTERS`/`WORDS` then compose (a visual artifact → Nicolas sign-off; cf. inject_ch01 step 6a). VISUAL.
- **Load-test** (mGBA / Nicolas): ch01 clear → ch02 plays → win → chains; verify cutscene staging + reinforcement.

### 3. Supporting content / art
Enemy YAML pass #18 · NPC/recruit stubs #17 · world-map unlock #29 · portraits #19 · overworld sprites #38 ·
onboarding-parity #64.

## Seam refinement (B) — ratified, NOT built, NOT urgent
`decisions.md` §Seam refinement: content-feature `record*` scenarios are content spot-checks. **Not built**, and
no longer pressing — a `recordlord` already exists on main (pipeline-authored) and *running* it was never blocked.
If the content lane needs to author/tune its own capture scenario before the mechanism lands (carve a content-owned
`tools/playtest/content_scenarios.lua` the harness includes — a **pipeline** `check.py`/`harness.lua` edit), use
`--no-verify` for that one commit.

## Watch out (content-lane only)
- **msg-id vetting is treacherous:** `data_battlequotes.c` stores ids 4-digit zero-padded (`0x0935`), and
  `msg_data.c` packs them as halfword arrays — naïve hex-grep gives false negatives. Vet by **content** (a
  one-chapter scene line our host overwrites?) + check `data_battlequotes.c` in the `0x0XXX` form.
- **Writing any dialogue → invoke the `dialogue-pass` skill first.** Voice grounding: per-NPC `lore/*.md` §Voice +
  `lore/frostmaiden-voices.md` + `fireemblem8u/texts/texts.txt`. Read sources first; bring drafts.
- Long unit names overflow FE8's name buffer — add a short `fe_name` (≤12) to new units.
- Story bodies are `make`-regenerated; gate text changes with `python3 tools/verify_text.py`.
- **Chapter hosting (model on `inject_ch01`):** each chapter rides the *next* vanilla slot (ch01→2; ch02→**3**)
  and needs a real `.mar`+`.json` map. Chapters chain via `MNC2(<next slot>)`; an unhosted next chapter
  dead-ends on `dev_placeholder_scene`.
- **Engine UI in a custom event-menu:** writable globals can't live in `events_script.o` (its `.bss` is
  discarded); use `EWRAM_OVERLAY(0)`. OBJ-based faces (`StartFace2`) don't render over an opaque BACG (priority)
  — the reskin sidesteps both by using its own bg + `PutFaceChibi`.
- **The repo moves under you:** scheduled/parallel pipeline work lands on `main` mid-session. Re-check
  `git log main` and sync before a big build (this handoff was written after one such sync).
