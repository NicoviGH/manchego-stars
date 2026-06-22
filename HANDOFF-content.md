# Handoff — Content track 🔒 live state

Per-track live state for the **content lane** (Ch2+ slices, dialogue, art). Worktree doctrine,
ownership map, and trunk rules → `CLAUDE.md` §Tracks (read first; the lane guard is
`check.py check_lane_ownership`). Parallel-work + seam model → `docs/decisions.md` §Seam enforcement /
§Seam refinement. Backlog → GitHub issues (#49 ① Content). **Shared builds/gotchas/rules → `HANDOFF.md`
+ `CLAUDE.md`; this file holds only my current state + content-lane-specific gotchas.** Don't touch
`HANDOFF-pipeline.md`.

## Base state (clean — start here)
- `inst/content` is **synced to `main`** (merged `288b1a1`: per-chapter parity gate #48b, LLM-player M1
  #63, BPS/dist #59) — work on a current base, no stale-merge debt.
- **`make` green**, `verify_text` 0 runaway. Working tree clean (only the `fireemblem8u` submodule pointer,
  which is a build artifact — **never commit it**).
- **Committed this session** (`eaaf340`): the 8 `lord_pitch:` YAML fields + the #46-reskin & seam-refinement
  ADRs. The earlier **hand-built lord-select menu was discarded** (superseded by the reskin) — so
  `build_campaign.py` is back at its clean base; the reskin is built fresh on top.

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

### 2. Host ch02 full slice (#22) — gate PASSED, fully scoped, `inject_ch02` build pending
`difficulty.py --chapter ch02` ⇒ **PARITY (within band)** (enemy-pressure ×0.88 OK; throughput +0.59;
durability-min 1.0 = Pinky vs the lone archer — intended flier/bow counterplay, telegraphed in her pitch; leave
the archer placement). Resolved unknowns for `inject_ch02` (model on `inject_ch01`):
- **DefeatAll**: copy vanilla **slot-4's `defeat_all` goal block** into the slot-3 host goal; engine's
  `CountRedUnits()` drives the rout win (no Seize — drop `Seize(14,1)` from `EventListScr_Ch3_Location`).
  `CauseGameOverIfLordDies` is **already** in `EventListScr_Ch3_Misc`.
- **Host slot 3** (`EventScr_Ch3_*`); **party persists** → no cast re-LOAD (just deploy template cap 5 + enemies +
  turn-3 reinforcements).
- **Positions**: ch02 YAML has none — the reskin keeps vanilla geometry, so **source from vanilla Ch2 "The
  Protected" parity** (first pass for Nicolas to adjust); author into the ch02 YAML.
- **Cutscenes** (locked in `ch02-cold-welcome.yaml`): Vellynne opening (BACG), turn-3 Wolfram rear-bark (31 chars →
  needs `[LF]` split, verify right-bubble on-screen), targos-inn ending. **Spare verified-dead msg-ids:
  `0x933,0x937,0x938`.** Apply the #58 opaque-narration-box convention.
- **Defend-sled** (soft-fail green unit → forfeit chest+250g) + sled sprite + Vellynne portrait (#19) = art
  checkpoints for Nicolas.
- Register `inject_ch02` in `main()` after `inject_ch01`; flip ch01's ending `dev_placeholder_scene` → **`MNC2(0x3)`**.

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
