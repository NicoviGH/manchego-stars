# Handoff — Content track 🔒 live state

Per-track live state for the **content lane** (Ch2+ slices, dialogue, art). Worktree doctrine,
ownership map, and trunk rules → `CLAUDE.md` §Tracks (read first; the lane guard is
`check.py check_lane_ownership`). Parallel-work + seam model → `docs/decisions.md` §Delivery model /
§Seam enforcement. Backlog → GitHub issues (#49 ① Content). **Shared builds/gotchas/rules → `HANDOFF.md`
+ `CLAUDE.md`; this file holds only my current state + content-lane-specific gotchas.** Don't touch
`HANDOFF-pipeline.md`.

## Now (2026-06-21, review session) — #20 closed (was done, never reconciled) · issue-reconciliation backstop SHIPPED

**✅ #20 (Prologue) CLOSED — it was done since 2026-06-10, just never reconciled.** The cutscenes +
co-written dialogue all ship via `inject_prologue` step 4c (`build_campaign.py`, msgs 0x90D/0x90E
opening, 0x914 mid-fight, 0x918 ending + death/defeat quotes) generated from the locked
`ch00-prologue-a-dagger-of-ice.yaml` `script:` blocks; played end-to-end in the alpha run (#47). The
issue sat open only because its checkboxes were never ticked. Closed `completed` with a note; final
pre-distribution playthrough stays tracked in #31. (Stale crumb left in ch00 YAML: an `ea_file:
events/ch00-ending.ea` that doesn't exist and isn't used — build generates bodies directly. Harmless;
clean up if you touch that YAML.)

**✅ SHIPPED — SessionStart issue-reconciliation backstop (`d36c55d`, pushed).** Diagnosed why #20 was
missed: the only issue-closing lever is a manual `Closes #N`, and issue state lives outside the repo, so
`check.py`/`make`/CI can never catch "shipped but open" (the #20 dialogue landed in a Ch2-focused commit
that never named it). Fix (all shared-lane; avoids pipeline-exclusive `tools/hooks/` + `check.py`):
`tools/issue_reconcile.py` (flags open chapter issues whose chapter is SHIPPED = locked dialogue AND a
host/inject fn, yet never closed by a commit; pure cores tested in `tools/test_issue_reconcile.py`,
stdlib-only) + `.claude/hooks/session-start.sh` registered in `.claude/settings.json` (injects the
reconciliation reflex every session, runs the script when `gh` is present; dependency-free so it works on
the web) + `dialogue-pass` skill "Close the loop" step (prompt `Closes #N` when locked dialogue finishes a
chapter issue) + ADR in `decisions.md` (2026-06-21). The hook fires live (confirmed on this session's
resume). The script also flagged **#21 (Ch1)** — RESOLVED as a false positive: Ch1 is shipped but stays
open because the **lord-select UX (#46)** came in as Ch1 playtest feedback (alpha item #4), so it's
**in-scope for the Ch1 vertical slice**. #46 is now a **sub-issue of #21** (recorded on both issues). The
finishing #46 commit must `Closes #46` **and** `Closes #21` (see Next #1). Ch1 art (#38/#39) is layered
polish, not slice-gating.

## Now (2026-06-21) — #46 lord-select pitches 🅿️ APPROVED, awaiting "go" to wire · onboarding guardrail SHIPPED

**🅿️ #46 lord-select UX — 8 pitches approved by Nicolas, PARKED on his "go" to wire.**
Candidate set **confirmed = 8** (not the old "5" guess): every classed cast member in `PORTRAIT_MAP`
order — braulo, marty, wolfram, meesmickle, prof-rbg, rootis, sclorbo, **pinky** (now a proper PC, see
below). Tone fork **resolved: mechanical** (Nicolas: blended was too flavor-heavy) — drafts re-tuned to
mirror FE8's own class-help register (`texts.txt` MSG_30C–33x), strength-then-weakness, ~2–3 lines.
The 8 approved drafts live in this session's transcript; resume by writing them into `pcs/*.yaml`.
- **Uncommitted scaffolding from the prior session (still in the worktree, NOT committed):**
  `tools/build_campaign.py` `lord_pitch_text(unit)` (hard-fails on a missing pitch) +
  `lord_select_menu_code(...)` (the card generator w/ `onSwitchIn LordSelect_DrawCard`); `LordPitch` +
  `LordSelectMenuCode` test classes in `tools/test_build_campaign.py`. Old inline menu still drives
  `inject_ch01` (un-regressed). **Don't lose these — they're the wiring target.**
- **LEFT to finish #46:** ① write the 8 `lord_pitch:` fields. ② allocate a VETTED dead-msg-id block for
  the pitch + explainer bodies (`set_message_body`), add a `vanilla_portrait_id(slot)` helper, compute
  `portrait_ids`, swap `inject_ch01` → `lord_select_menu_code(...)`. ⚠ **`0x965–0x96E` are NOT
  dead** — live FE8 tutorial strings (the "pegasus knights fly over mountains" / `FID_EphraimFlashback`);
  vetted pool is `0x940–0x964` (~full). ③ build + mGBA render (tune card wrap; confirm `onSwitchIn`
  fires on the *initial* highlight, else blank until cursor moves); show Nicolas. ④ ADR + `Closes #46`
  **and `Closes #21`** (#46 is a sub-issue of the Ch1 slice — finishing it signs off Ch1) (+ close tracker #47).

**✅ SHIPPED this session — FE8 onboarding-parity guardrail (`7856528`, merged main).** Combat is
vanilla-strict, but rewriting cutscenes can silently strip the onboarding a vanilla player gets (delivered
via BOTH `PLAY_FLAG_TUTORIAL` boxes *and* mandatory dialogue). System: `onboarding-catalog.yaml` (what
vanilla teaches + channel + decomp citation) → chapter `introduces:` ledger → `gen_onboarding_index.py` →
`docs/ONBOARDING.md` (4/20 covered) → `test_onboarding.py` (integrity + freshness) → **dialogue-pass
"Tutorial-parity check" step** (the reflex: flag each first-appearance concept, owe the vanilla heads-up).
ADR in `decisions.md` §Story & Dialogue. **Open work tracked in #64** (catalog decomp sweep, the 16 Pending
concepts, prologue-box verification, the pipeline-lane `check.py` freshness fold-in).

**✅ SHIPPED this session — Pinky = 8th PC + lord candidate; stale roster defs reconciled** (`8a4912e` /
`d2b48a8`). `git mv npcs/pinky.yaml → pcs/`; decisions.md 7→8 PCs + base-class row; reconciled the two stale
Pepperjack & Brie paragraphs into one current "vanilla map ballistae" decision; fixed the stale
Marty/Meesmickle "differentiate at promotion, not base" note (they split growths from L1). (#45 leftover
item resolved; couldn't tick its checkbox — closed issue, write denied.)

## ✅ DONE 2026-06-20 — Ch1 v0.1.0 playtest fixes #57 + #58 landed
Both live-build fixes from the brother's v0.1.0 run are fixed and verified in-engine:
- **#57 — Ch1 Seize legible:** seize tile [21,7] is now the castle-gate metatile 938
  (`TERRAIN_GATE_CASTLE`) — reads as a Seize point, chief on it. **Restores vanilla Ch1's gate
  +20avo/+3def to the boss** (the bonus-free ruins tile was the deviation). ⚠ **Pipeline track:**
  the boss is now tankier — account for the gate terrain in ch01's parity bar (flagged in
  `decisions.md` §Combat resolution + the seize ADR).
- **#58 — narration boxes opaque:** faceless `narration:`/asides now ride an auto-centered
  `SOLOTEXTBOXSTART` box (was the translucent `Text()` window, illegible over BACG art). New
  `_scenic_beat_calls` helper in `build_campaign.py` applies it per-beat across opening + ending;
  a beat mixing narration + faces must be split with a `beat_break` (ch01 ending E2/E2b, msg 0x93D).
  Convention recorded in `decisions.md` §Story & Dialogue. **Apply to ch02 cutscenes as you wire them.**

Verified: `tools/build.sh test` green, `verify_text.py` 3404 msgs/0 runaway, `recordending` PASS
(narration box opaque on-screen). Ch1 #21 DoD: these two boxes checked.

## Now (2026-06-20) — ch02 map + dialogue DONE; Ch2 dev 🅿️ PARKED on the difficulty engine (#61/#62)
ch02 dialogue is locked (opening, turn-3 rear-ambush bark, targos-inn ending — `2e60003`, #22) and the
**map is authored**: `maps/ch02-cold-welcome.mar`+`.json` — a 15×15 winter reskin of FE8 Ch2 that
**Nicolas painted by hand** in the browser editor (villages rebuilt from winter building tiles, mountains
+ fort + ground retiled). Framing fixed in the YAML: the Rolling Cheddar is the party's **home on runners**.
ch02 `enemy_units` converted to the canonical schema (class/level/`autolevel`/`inventory`) so the
difficulty engine + inject can read them.

**🅿️ PARKED (Nicolas, 2026-06-20): no more Ch2 dev until the difficulty engine is reliable.** Driving ch02
through `tools/difficulty.py` surfaced two engine math defects that make party-side balancing blind:
**#61** (no vanilla player FIELD for Ch2 → party-parity delta skipped) and **#62** (healers crash / a base
Priest's promotion-locked tome is miscounted as throughput — engine ignores the `unlock: promotion` flag).
Both filed `tooling`+`balance`, with acceptance criteria, and listed under #49 ② Pipeline. #22 is labelled
`blocked`. What IS known: **enemy-pressure parity verified ×0.88 (within band)**; our 4-attacker core
(3.69 kills/rd) ≈ vanilla's 4 (3.42); **Sclorbo = our Moulder** (base Priest, staff-only = 0 offense).
**Deploy is NOT an open question** — per decisions.md §"Field parity" (2026-06-10), `deploy_limit` = vanilla
chapter N's count, so **ch02 `deploy_limit: 5`** (set in the YAML; Pick Units fields 5 of our 8, chosen lord
force-deployed) and **enemies mirror vanilla Ch2 1:1 — never scaled**. The park is purely on engine
reliability: once #61/#62 land, re-run `difficulty.py --chapter ch02` to confirm our best-5 sits at vanilla
parity on the party side (today that delta is skipped/untrustworthy), then place units + build inject_ch02.

**Map-tooling upgrades this session (all in `tools/`, content lane):** `gen_map_editor.py` now renders a
side-by-side **vanilla reference** (built via the decomp's own `gbagfx` — never hand-decode the PNG/pal),
a grid/terrain-border toggle (`g`), a decluttered palette (orange filler slots dropped) with **every
terrain id named** (the frozen-building groups read "Building / roof" etc. instead of raw hex). Nicolas's
retile was diffed vs vanilla Ch2 → **`maps/reskin-learned.json`** (50 vanilla→winter tile mappings) which
`gen_map_editor` now applies, so future chapters inherit his conventions as the starting reskin.
`gen_map_editor.py` + `import_map_layout.py` are now worktree-aware (root from `__file__`).
Tree-diversity experiment was rejected — winter pines too alike; his uniform pine (192) reads best.
⚠ Carry-forward flag: the rear-ambush bark line is 31 chars, past the 29-char on-map bubble wrap → at
insertion it wraps / needs an `[LF]` split; verify the right-side bubble isn't pushed offscreen.

## Next (priority order)
1. **🚧 Resume #46 lord-select UX** — see the "Now" block above for the exact resume steps (author the 5
   `lord_pitch:` blurbs via `dialogue-pass` → vetted dead-id block + swap `inject_ch01` to the generator →
   build/render → ADR + `Closes #46` **+ `Closes #21`** — #46 is a sub-issue of the Ch1 slice, so finishing
   it signs off Ch1). The Python scaffolding is done + green; this is wiring + content + build.
2. **Host ch02 (full slice)** (#22) — the map is done; write `inject_ch02` modeled on `inject_ch01`: host
   on chapter **slot 3** (`EventScr_Ch3_*`), register `maps/ch02-cold-welcome.mar` + the winter tileset,
   inject the three locked cutscenes (off-map opening BACG scene + targos-inn ending + the turn-3
   rear-ambush TURN event), place deploy/enemies/defend-sled objective on the new map, and flip ch01's
   ending from the dev placeholder to **`MNC2(0x3)`**. Mind the rear-ambush bubble-width flag. Then
   Vellynne cutscene portrait (#19) + in-game motion review.
3. Supporting content as Ch2 needs them: enemy YAML pass #18, NPC/recruit stubs #17, recruit schedule
   (#45 item 5), world-map unlock #29.
4. Art passes layer on already-playable slices: portraits #19, overworld sprites #38.

## Watch out (content-lane only)
- **Writing any dialogue → invoke the `dialogue-pass` skill first.** Voice grounding lives in the repo:
  per-NPC `lore/*.md` §Voice bibles + `lore/frostmaiden-voices.md` (canon cast) + the FE8 cadence corpus
  `fireemblem8u/texts/texts.txt`. Read sources BEFORE asking Nicolas; bring drafts, not questions.
- Long unit names overflow FE8's name buffer — add a short `fe_name` (≤12) to new units.
- Story bodies are `make`-regenerated; gate text changes with `python3 tools/verify_text.py`.
- **Chapter hosting (model on `inject_ch01`, `tools/build_campaign.py`):** each campaign chapter rides the
  *next* vanilla slot (ch01→slot 2 `EventScr_Ch2_*`; ch02→**slot 3** `EventScr_Ch3_*`) and needs a real
  `.mar`+`.json` map layout — no layout = no playable map. Off-map cutscenes (opening BACG / ending) are
  map-independent; deploy/enemy/objective coords need the map. Chapters chain via `MNC2(<next slot>)`; an
  unhosted next chapter dead-ends on `dev_placeholder_scene`.
