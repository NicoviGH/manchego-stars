# Handoff — Content track 🔒 live state

Per-track live state for the **content lane** (Ch2+ slices, dialogue, art). Worktree doctrine,
ownership map, and trunk rules → `CLAUDE.md` §Tracks (read first; the lane guard is
`check.py check_lane_ownership`). Parallel-work + seam model → `docs/decisions.md` §Delivery model /
§Seam enforcement. Backlog → GitHub issues (#49 ① Content). **Shared builds/gotchas/rules → `HANDOFF.md`
+ `CLAUDE.md`; this file holds only my current state + content-lane-specific gotchas.** Don't touch
`HANDOFF-pipeline.md`.

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
1. **🔴 DO FIRST — Ch1 v0.1.0 playtest fixes #57 + #58** (see the DO FIRST blocker above). Land before
   deepening Ch2 or they sit unaddressed on the build every tester plays. #57 is isolated (`ch01` YAML);
   **#58 shares `build_campaign.py:654`** with ch02 wiring, so it bundles into that branch and lands
   before more ch02 cutscene wiring.
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
