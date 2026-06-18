# Handoff: rescue #44 root-caused (general MU-standing bug, fix deferred — needs a design call) + Ch1 difficulty QUANTIFIED (balance_report.py). Both items now need Nicolas's calls.

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

## 🔴 Rescue #44 — root cause found, FIX DEFERRED (needs a design call)
Diagnosed with live mGBA instrumentation (palette-RAM/OAM/VRAM reads; instrumentation removed).
**It is NOT a palette-bank bug** (the earlier theory): OBJ bank 0x0B holds the correct cast
palette the whole time, and the MU sheet on disk is correct. The real fault:
- The MU display dispatch (`mu.c:856`) routes `facing == MU_FACING_STANDING → PutMuSMS`, which
  draws the **class** SMS (`GetClassSMSId`) through the cast palette → near-black. `GetMuImg`/the
  `#38` override does **not** cover this path; `StartUiStandingMu` (the would-be custom loader) is
  dead code. **It's a general cast-MU fault, not rescue-specific** — also hits a *selected idle*
  unit. The rescue lift halts to standing, so it's the most visible case (and what got noticed).
  Walking uses the AP path (custom sheet in `gMUGfxBuffer`) and is likely fine.
- **Why deferred:** the fix is in hot vanilla MU rendering (every unit's movement display) and the
  standing-MU gfx-load point is unresolved → too risky to ship unverified overnight for a
  **non-critical** bug. **Pick one (Nicolas):**
  1. Route cast MUs through the AP path when "standing" (synth sheet already has the idle pose in
     every frame). Most faithful to #38. Gate on a campaign-agnostic "has custom MU?" check
     (`charId in gMuImgOverride`, empty in vanilla ⇒ zero stock-unit change). Verifiable via
     `recordrescue` + `ch01win`.
  2. Make the standing-MU path use `GetUnitSMSId(unit)` not `GetClassSMSId(jid)` — needs more RE
     on where the standing-MU gfx loads.
  3. Accept the vanilla look: standard player palette (0x0C) for cast MUs so the class sprite reads
     as a normal blue unit during selection/lift (not custom, but not black). Lowest risk.

## 🟡 Ch1 difficulty — QUANTIFIED (needs Nicolas's lever calls)
`balance_report.py` settles it: **the enemies are not the problem — the party is.** Our line
goblins are **lv1** (class base); vanilla Ch1's were **lv2-3** + the same lv4 boss, so our enemy
field is marginally *easier*. The gap is entirely the lordless cast:
- **Durability:** vanilla's *frailest* fielded unit (Eirika, 2.8 enemy-hits-to-down) ≈ our
  *sturdiest*. Half our cast drops in **<2 hits** open ground (~2.6 with forest). **Seth takes 17.5.**
- **Carry gap:** Eirika **ORKOs the boss** (effective Rapier ×3); our best (Braulo) needs ~2.8
  rounds of boss exposure (and the boss hits him for 11 — a real risk).
- **Output gap:** **Seth alone = 48% of vanilla's 4-unit DPR.** Our best 4 = 44% of vanilla;
  our best 6 = 55% → **more bodies can't replace the missing carry.**

**Recommended levers (quantified; lean-generous, no enemy nerfs):**
1. **An anchor/carry is the #1 lever** — it's what Seth was. Cheapest: **Wolfram +3 Spd** so
   fighters stop doubling him → survivability **1.8 → 3.9** hits-to-down (he's our intended wall).
   And/or field a recurring **guest veteran (a Jagen)** like the prologue's Scramsax for Ch1.
2. **deploy_limit 4 → 5 (or 6)** — output 44% → 50–55%, lets a healer *and* attackers come, fills
   forest tiles. Low risk; do it.
3. **Forest-cover routing** (already in-map, +20 avo → squishies 1.9 → 2.6). Free; ensure the
   approach lanes actually have cover.
4. **Generous EXP** for campaign snowball — but note **starting levels barely move Ch1 durability**
   (defensive growths are 5–15%); don't rely on it for survivability.
   **AVOID:** nerfing the (already-gentle) enemies; blanket party-leveling.

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
