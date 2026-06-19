# Handoff — Content track 🔒 live state

Per-track live state for the **content lane** (Ch2+ slices, dialogue, art). Worktree doctrine,
ownership map, and trunk rules → `CLAUDE.md` §Tracks (read first; the lane guard is
`check.py check_lane_ownership`). Parallel-work + seam model → `docs/decisions.md` §Delivery model /
§Seam enforcement. Backlog → GitHub issues (#49 ① Content). **Shared builds/gotchas/rules → `HANDOFF.md`
+ `CLAUDE.md`; this file holds only my current state + content-lane-specific gotchas.** Don't touch
`HANDOFF-pipeline.md`.

## 🔴 DO FIRST — clear the live Ch1 playtest fixes before deepening Ch2 (flagged 2026-06-19)
Two content-track fixes from friends' **v0.1.0** runs are live on the build every new tester plays.
Land them as the **next unit of work**, before more Ch2 — otherwise they sit unaddressed:
- **#57 — Ch1 Seize unclear:** make the seize tile read as a seize point. Edits **only**
  `chapters/ch01-the-iron-trail.yaml` (`seize_tile [21,7]` terrain + boss placement) — isolated, no
  injector touch. Decomp rationale + the seize-legibility checkpoint are on #57 and `decisions.md`
  §Combat System.
- **#58 — narration/aside text boxless over cutscene art:** fix at `build_campaign.py:654` (the
  "Marty leans in…" narration path). ⚠ **Bundle with the ch02 wiring branch** — it shares
  `build_campaign.py` with ch02 host wiring, so a separate lane would conflict; and land #58's box
  convention **before** wiring more ch02 cutscenes, or you re-do Ch2 narration against changed behavior.

Both gate Ch1 #21's Definition of Done.

## Now (2026-06-19) — ch02 dialogue all LOCKED; host wiring BLOCKED on the missing ch02 map
All three ch02 cutscenes are locked text in `ch02-cold-welcome.yaml` (opening, turn-3 rear-ambush bark,
targos-inn ending — `2e60003`, #22) but **unwired**. The ending lands the **Sephek breadcrumb** (town
blames the druids' Auril rumor; **Rootis** IDs the dagger-of-ice kill from Hlin's briefing — no fight;
**RBG** forks the party north onto the druids' trail). Sephek arc recorded in `decisions.md` §Story
(distinct from Ravisin (ch05); reckoning → an Act-II multi-boss slot; `lore/sephek-kaltro.md` note fixed).

**Host wiring can't start: ch02 has no map layout.** `inject_ch01` injects a real `.mar`+`.json` layout
per chapter (ch00/ch01/test each have one); ch02 has **none** — the YAML's `maps/ch02-cold-welcome.tmx`
was never authored. **Decided with Nicolas: design the ch02 map FIRST, then host the whole slice in one
pass** (avoids throwaway deploy/enemy placement on a placeholder). Off-map cutscene wiring is
map-independent and could go first, but we're sequencing map-first.
⚠ Carry-forward flag: the rear-ambush bark line is 31 chars, past the 29-char on-map bubble wrap → at
insertion it wraps / needs an `[LF]` split; verify the right-side bubble isn't pushed offscreen.

## Next (priority order)
1. **🔴 DO FIRST — Ch1 v0.1.0 playtest fixes #57 + #58** (see the DO FIRST blocker above). Land before
   deepening Ch2 or they sit unaddressed on the build every tester plays. #57 is isolated (`ch01` YAML);
   **#58 shares `build_campaign.py:654`** with ch02 wiring, so it bundles into that branch and lands
   before more ch02 cutscene wiring.
2. **Design the ch02 map** (#22) — 15×15 snow-road reskin of FE8 Ch2 ("same choke points + spawn
   geography", per the YAML `map:` block); shared `snowy-bern` winter tileset is already injected. Per the
   collaborative-map flow: bring Nicolas 2–3 layout concepts, iterate, then author the `.mar`+`.json`
   layout under `campaigns/.../maps/`.
3. **Host ch02 (full slice)** once the map lands — write `inject_ch02` modeled on `inject_ch01`: host on
   chapter **slot 3** (`EventScr_Ch3_*`), inject the three locked cutscenes (off-map opening BACG scene +
   targos-inn ending + the turn-3 rear-ambush TURN event), place deploy/enemies/defend-sled objective on
   the new map, and flip ch01's ending from the dev placeholder to **`MNC2(0x3)`**. Mind the rear-ambush
   bubble-width flag. Then Vellynne cutscene portrait (#19) + in-game motion review.
4. Supporting content as Ch2 needs them: enemy YAML pass #18, NPC/recruit stubs #17, recruit schedule
   (#45 item 5), world-map unlock #29.
5. Art passes layer on already-playable slices: portraits #19, overworld sprites #38.

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
