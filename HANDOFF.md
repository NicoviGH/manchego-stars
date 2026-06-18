# Handoff: rescue #44 fix DECIDED (route MUs via AP path — implement next) + Ch1 difficulty going the "chosen-lord = the anchor/Jagen" route (Nicolas's idea); next step = model lord-mode tiers in balance_report.py. Decisions captured below.

**Date:** 2026-06-18 (session 12)
**Where we are:** Overnight session on the two open items from session 11. Both are now
**diagnosed/quantified with reusable tooling**, and both land on a **decision Nicolas needs
to make** (a risky engine fix vs the gentler options; which difficulty levers to pull).

`make` green (untouched ROM — only Lua/Python tooling changed) · `recordrescue` PASS (now
reliable) · `balance_report.py` runs clean · drift clean. **Commits `8acd12c`, `992d3ad`.**

## Shipped this session (committed + pushed)
- **Reliable `recordrescue` repro + #44 root cause** (`8acd12c`). The old scenario fired the
  rescue mid-PLAYER-PHASE-banner and checked the wrong `US_RESCUING` bit (`0x1000`, should be
  `0x10`), so it never lifted anyone. Now it waits out the battle-start cutscene
  (`StdEventEngine`) + banner, iterates deployed units until one can lift a neighbour (FE8 gates
  Rescue on Aid≥Con), and asserts `US_RESCUING`. Reproduces the black sprite every run.
- **`tools/balance_report.py`** (`992d3ad`) — the parked balance-report idea, built. FE8 combat
  math (decomp formulas) for our cast vs vanilla Ch1 vs the shared enemies. `python3 tools/balance_report.py`.

## 🟢 Rescue #44 — root cause found, FIX DECIDED (route MUs via AP path; implement next session)
**Nicolas's call (2026-06-18): option 1 — route cast MUs through the AP path when "standing."**
The synth MU sheet already holds the idle pose in every frame, so the AP path renders the custom
sprite instead of the class SMS. Gate it on a campaign-agnostic "has custom MU?" check
(`charId in gMuImgOverride`, empty in vanilla ⇒ zero stock-unit change). Verify via `recordrescue`
(lift should now be the colourful custom sprite, not black) + `ch01win` (no movement-render
regressions). Implementation detail to mind: when `facing==STANDING`, `SetMuFacing` calls
`SetStandingMuFacing` (not `AP_SwitchAnimation`), so a valid AP animation must be ensured for the
cast-MU standing case before `PutMu` can render it.

Diagnosed with live mGBA instrumentation (palette-RAM/OAM/VRAM reads; instrumentation removed).
**It is NOT a palette-bank bug** (the earlier theory): OBJ bank 0x0B holds the correct cast
palette the whole time, and the MU sheet on disk is correct. The real fault:
- The MU display dispatch (`mu.c:856`) routes `facing == MU_FACING_STANDING → PutMuSMS`, which
  draws the **class** SMS (`GetClassSMSId`) through the cast palette → near-black. `GetMuImg`/the
  `#38` override does **not** cover this path; `StartUiStandingMu` (the would-be custom loader) is
  dead code. **It's a general cast-MU fault, not rescue-specific** — also hits a *selected idle*
  unit. The rescue lift halts to standing, so it's the most visible case (and what got noticed).
  Walking uses the AP path (custom sheet in `gMUGfxBuffer`) and is likely fine. (Caution: the fix
  touches hot vanilla MU rendering — every unit's movement display — so verify broadly, not just
  the rescue case.)

## 🟡 Ch1 difficulty — QUANTIFIED; going the "chosen-lord = the anchor" route (Nicolas's idea)
`balance_report.py` settles it: **the enemies are not the problem — the party is.** Our line
goblins are **lv1** (class base); vanilla Ch1's were **lv2-3** + the same lv4 boss, so our enemy
field is marginally *easier*. The gap is entirely the lordless cast:
- **Durability:** vanilla's *frailest* fielded unit (Eirika, 2.8 enemy-hits-to-down) ≈ our
  *sturdiest*. Half our cast drops in **<2 hits** open ground (~2.6 with forest). **Seth takes 17.5.**
- **Carry gap:** Eirika **ORKOs the boss** (effective Rapier ×3); our best (Braulo) needs ~2.8
  rounds of boss exposure (and the boss hits him for 11 — a real risk).
- **Output gap:** **Seth alone = 48% of vanilla's 4-unit DPR.** Our best 4 = 44% of vanilla;
  our best 6 = 55% → **more bodies can't replace the missing carry.**

**DIRECTION (Nicolas, 2026-06-18):** make the **player-chosen lord the party's anchor** (its
Jagen/Seth). This restores the structure we stripped going lordless — vanilla Ch1 is winnable
largely *because* of one anchor — and gives lord-select real weight + a consistent anchor all
campaign (the lord persists). The decision is **how strong** (a dial), framed by the quantified
hits-to-down: our best today = **Braulo 2.8**; **Jagen-lite ≈ vanilla Gilliam 5.9** (leanable, still
a real fight); **full Seth 17.5** (solos the map). Lean toward the **Gilliam end** for a friend group.
Constraints: (1) **MVP is unpromoted** → a level-boosted *in-class* anchor (flavour follows the
picked class — offensive vs wall), NOT a promoted Paladin; (2) it's **campaign-wide** (boost rides
forward — a feature). A pure level-boost helps offense but won't fix class-specific holes (e.g.
Wolfram's Spd-15% doubling), so it likely needs a small **survivability floor** (AS-to-dodge-doubles
+ an HP/Def minimum) on top.

**NEXT STEP:** extend `tools/balance_report.py` to model "lord-mode" at 2–3 tiers (level-only /
level+floor / Seth-tier) for **all 7 lord candidates**, print durability+output, so Nicolas picks
the dial with data. **deploy_limit (4/5/6) is still open** — settle it *after* the anchor tier
(with a real anchor, 4–5 may be plenty; without, lean 6). Forest-cover routing (free, +20 avo →
squishies 1.9→2.6) and generous campaign EXP stay as secondary levers. **AVOID:** nerfing the
(already-gentle) enemies; blanket party-leveling (doesn't fix durability anyway).

## On-demand builds (unchanged)
`tools/build.sh test` (lean) · `tools/build.sh dist` (with #43 montage; stamps `dist/`). NEVER a
bare `make` for a shippable ROM — it strips the montage.

## Key files (this session)
- `tools/playtest/harness.lua` — `recordrescue` rewritten (cutscene-wait + rescuer iteration +
  correct `US_RESCUING`). `tools/balance_report.py` — Ch1 combat-math comparison + lever sim.

## Gotchas (carried + new)
- **`recordrescue` is the #44 repro** (`tools/playtest/run.sh recordrescue`); the lifted cast unit
  renders black. **`US_RESCUING = 0x10`** (1<<4), not 0x1000.
- **#44 is a STANDING-MU fault**, not a palette bug — don't re-chase the palette bank (it's correct).
- Background `run.sh` calls need an explicit `cd`/absolute path (shell cwd resets between tool
  calls — a relative `tools/playtest/run.sh` silently no-ops from the wrong dir).
- `record*` defaults to 60fps+videoSync; `PT_FPS=240 tools/playtest/run.sh <scen>` for fast
  static/proc-detected captures. Built ROM at `fireemblem8u/fireemblem8.gba`. Nicolas can't see
  inline renders — save to `map-review/` and `open`. Izobai female; Pinky male.
- **Never commit the `fireemblem8u` submodule pointer** (build artifact); stage repo files explicitly.
- Story text → `make` regenerates bodies; gate with `verify_text` after any text change.

## Memory
[[manchego-stars-project]] · [[project_manchego_stars_campaign_structure]] · [[manchego-stars-automated-playtests]] ·
[[manchego_stars_guest_map_sprite_wiring]] · [[feedback_use_decomp]] · [[feedback_fe-level-design]] ·
[[feedback_proactive-push]] · [[feedback_handoff_vs_memory]] · [[feedback_answer_before_picker]] ·
[[manchego_stars_rescue_standing_mu_bug]] · [[manchego_stars_ch1_difficulty]]

## Standing rules
Combat = pure vanilla FE; field parity with vanilla ch N is doctrine. Custom art where it matters,
**show before committing**; bring 2-3 options, let Nicolas drive. **Fast playtests for logic;
60fps recordings only for fade spot-checks.** Repo is the source of truth, NOT memory. Auto-push
to main once green; never commit the `fireemblem8u` submodule pointer.
