# Handoff — Content track 🔒 live state

Per-track live state for the **content lane** (Ch2+ slices, dialogue, art). Worktree doctrine,
ownership map, and trunk rules → `CLAUDE.md` §Tracks (read first; the lane guard is
`check.py check_lane_ownership`). Parallel-work + seam model → `docs/decisions.md` §Delivery model /
§Seam enforcement. Backlog → GitHub issues (#49 ① Content). **Shared builds/gotchas/rules → `HANDOFF.md`
+ `CLAUDE.md`; this file holds only my current state + content-lane-specific gotchas.** Don't touch
`HANDOFF-pipeline.md`.

## Now / Next (priority order)

### 1. 🚧 #46 lord-select UX — pitches DRAFTED (mechanical), awaiting sign-off, then wire

The choose-your-lead screen (#46, last open alpha item #47 #4): a one-time explainer + a per-candidate
card (portrait + a short strengths/weaknesses **pitch**) refreshing live as the cursor moves. Design
locked on #46. **No numeric stats** (no live-`Unit` dependency at menu time); pitch is hand-authored
YAML (`lord_pitch:` per PC).

**Candidate set = 8** (every classed cast member, `PORTRAIT_MAP` order): braulo, marty, wolfram,
meesmickle, prof-rbg, rootis, sclorbo, pinky. Tone = **mechanical** (Nicolas: blended too flavor-heavy);
drafts mirror FE8's own class-help register (`texts.txt` MSG_30C–33x).

**⏳ AWAITING NICOLAS — two small calls before these lock (asked, not yet answered):**
(a) faint flavor tint (e.g. RBG's "Um, actually—") or fully plain? (b) keep qualitative (no numbers,
per the #46 lock) or show base stats? **Latest drafts (verbatim — re-confirm before committing):**
- **braulo** — "Axe fighter, at home in any terrain. High power and HP — but low skill, and weak to magic."
- **marty** — "Dark mage — stronger but slower than a mage. Strikes resistance at range; fragile."
- **meesmickle** — "Dark mage; strong, slow magic at range. Gains Summon on promotion — but frail."
- **wolfram** — "Heavily armored knight. Towering defense and HP — but poor movement, weak to magic."
- **prof-rbg** — "Bowman who attacks from afar — deadly to fliers. No melee: helpless when cornered."
- **rootis** — "Anima mage — solid skill, low physical strength. Reliable damage at range; frail."
- **sclorbo** — "Spiritual guide who heals allies with sacred staves. Deals no damage — keep him guarded."
- **pinky** — "Airborne knight — flies over any terrain, resists magic. Weak to bows; keep clear of archers."

**⚠ Uncommitted scaffolding already in this worktree (`git status` will show it — DON'T lose it):**
`tools/build_campaign.py` `lord_pitch_text(unit)` (hard-fails on a missing pitch) +
`lord_select_menu_code(...)` (card generator w/ `onSwitchIn LordSelect_DrawCard`); `LordPitch` +
`LordSelectMenuCode` classes in `tools/test_build_campaign.py` (suite was 20/20 green). Old inline menu
still drives `inject_ch01`, so the build is un-regressed.

**LEFT to finish #46:** ① get the two calls answered → write the 8 `lord_pitch:` fields into `pcs/*.yaml`
(invoke `dialogue-pass`). ② allocate a VETTED dead-msg-id block for pitch + explainer bodies
(`set_message_body`), add `vanilla_portrait_id(slot)` helper, compute `portrait_ids`, swap `inject_ch01`
→ `lord_select_menu_code(...)`. **⚠ `0x965–0x96E` are NOT dead** (live FE8 tutorial strings — pegasus/
mountains, `FID_EphraimFlashback`); vetted pool `0x940–0x964` (~full) — trace any reuse first. ③ build +
mGBA render: tune card wrap; confirm `onSwitchIn` fires on the *initial* highlight (else blank until the
cursor moves — may need a first-draw after `StartMenu`). Show Nicolas (show-before-committing). ④ ADR +
`Closes #46` (and close tracker #47, the last open alpha item).

### 2. Host ch02 full slice (#22) — UNBLOCKED (was parked on #61/#62, both now CLOSED)

The Ch2 park was purely on the difficulty engine (#61 vanilla player FIELD, #62 healer modeling). **Both
issues are now CLOSED**, so the exit criterion is met: **re-run `tools/difficulty.py --chapter ch02`** to
confirm our best-5 sits at vanilla parity on the party side (was skipped/untrustworthy before), THEN place
units + build `inject_ch02`. Already done: ch02 dialogue locked (`2e60003`), map authored
(`maps/ch02-cold-welcome.mar`+`.json`, hand-painted winter reskin), `enemy_units` on the canonical schema,
`deploy_limit: 5` (vanilla-Ch2 count; enemies mirror vanilla 1:1, never scaled). Model `inject_ch02` on
`inject_ch01`: host on **slot 3** (`EventScr_Ch3_*`), register the map + winter tileset, inject the 3
cutscenes (off-map opening BACG + targos-inn ending + turn-3 rear-ambush TURN), place deploy/enemies/
defend-sled objective, flip ch01's ending placeholder to **`MNC2(0x3)`**. **⚠ rear-ambush bark = 31 chars**,
past the 29-char on-map bubble wrap → needs an `[LF]` split; verify the right-side bubble isn't offscreen.
Apply the #58 opaque-narration-box convention to ch02 cutscenes. Then Vellynne cutscene portrait (#19).

### 3. Supporting content / art (as Ch2+ needs them)
Enemy YAML pass #18 · NPC/recruit stubs #17 · world-map unlock #29 · portraits #19 · overworld sprites #38.
Onboarding-parity coverage as chapters are authored → **#64** (run the dialogue-pass "Tutorial-parity check").

## Recently shipped this session (context — all on `main`)
- **FE8 onboarding-parity guardrail** (`7856528`): `onboarding-catalog.yaml` + chapter `introduces:` ledger
  → `gen_onboarding_index.py` → `docs/ONBOARDING.md` (4/20) → `test_onboarding.py` → dialogue-pass
  "Tutorial-parity check" step. ADR in `decisions.md` §Story & Dialogue. **Open work → #64.**
- **Pinky = 8th PC + lord candidate** (`8a4912e`/`d2b48a8`): `pinky.yaml` moved `npcs/`→`pcs/`; decisions.md
  reconciled to 8 PCs; stale Pepperjack/Brie + Marty/Meesmickle notes fixed. (#45 leftover ticked.)
- **`gh` rejection fix:** Nicolas pasted an `autoMode.allow` block into `~/.claude/settings.json` — issue/PR
  writes no longer hit the classifier soft-deny. (I can't write classifier/autoMode rules myself — hard
  block; hand the user the JSON. `permissions.allow` alone does NOT override the classifier.)

## Watch out (content-lane only)
- **Writing any dialogue → invoke the `dialogue-pass` skill first** (now includes the Tutorial-parity step).
  Voice grounding: per-NPC `lore/*.md` §Voice + `lore/frostmaiden-voices.md` + `fireemblem8u/texts/texts.txt`.
  Read sources BEFORE asking; bring drafts, not questions.
- Long unit names overflow FE8's name buffer — add a short `fe_name` (≤12) to new units.
- Story bodies are `make`-regenerated; gate text changes with `python3 tools/verify_text.py`.
- **Chapter hosting (model on `inject_ch01`):** each campaign chapter rides the *next* vanilla slot
  (ch01→slot 2; ch02→**slot 3**) and needs a real `.mar`+`.json` map. Off-map cutscenes are map-independent;
  deploy/enemy/objective coords need the map. Chapters chain via `MNC2(<next slot>)`; an unhosted next
  chapter dead-ends on `dev_placeholder_scene`.
