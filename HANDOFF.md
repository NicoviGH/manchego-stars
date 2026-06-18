# Handoff: rescue #44 fix DECIDED (route MUs via AP path — implement next). Ch1 difficulty QUANTIFIED but the APPROACH IS STILL OPEN — evaluating options (lord-as-anchor is one idea on the table, NOT chosen; deploy-limit + levers undecided).

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
sprite instead of the class SMS. **The gate (`charId in gMuImgOverride`) is NON-NEGOTIABLE — Nicolas
confirmed (2026-06-18): only the CAST may change. Every stock/vanilla/guest-only-walk character must
keep its full class animations (walk + everything) 100% untouched.** The table is empty for stock
units, so the dispatch change must apply ONLY to entries in it. Note this fix touches only the brief
*standing* moment of cast MUs — walking is the AP path and is already untouched for everyone; the
cast stays idle-only by design (we add no walk art, just stop the standing pose rendering black).
Verify via `recordrescue` (lift = colourful custom sprite, not black) + `ch01win` (stock/vanilla
units still walk + animate normally, no regressions). Implementation detail to mind: when `facing==STANDING`, `SetMuFacing` calls
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

## 🟡 Ch1 difficulty — QUANTIFIED; approach STILL OPEN (evaluating options, nothing chosen)
`balance_report.py` settles it: **the enemies are not the problem — the party is.** Our line
goblins are **lv1** (class base); vanilla Ch1's were **lv2-3** + the same lv4 boss, so our enemy
field is marginally *easier*. The gap is entirely the lordless cast:
- **Durability:** vanilla's *frailest* fielded unit (Eirika, 2.8 enemy-hits-to-down) ≈ our
  *sturdiest*. Half our cast drops in **<2 hits** open ground (~2.6 with forest). **Seth takes 17.5.**
- **Carry gap:** Eirika **ORKOs the boss** (effective Rapier ×3); our best (Braulo) needs ~2.8
  rounds of boss exposure (and the boss hits him for 11 — a real risk).
- **Output gap:** **Seth alone = 48% of vanilla's 4-unit DPR.** Our best 4 = 44% of vanilla;
  our best 6 = 55% → **more bodies can't replace the missing carry.**

**STATUS: still evaluating — NOTHING decided.** Options on the table (lean-generous, no enemy nerfs):
- **"Lord-mode" — the player-chosen lord becomes the party's anchor (Nicolas's idea, UNDECIDED).**
  Restores vanilla's "one anchor carries it" structure + gives lord-select weight + a campaign-long
  anchor (lord persists). Open sub-dial = how strong: Braulo-2.8 (today) → **Jagen-lite ≈ Gilliam
  5.9** (leanable, still a fight) → Seth-17.5 (solos). Constraints if pursued: MVP unpromoted ⇒
  level-boosted *in-class* anchor (flavour follows the picked class), NOT a promoted Paladin;
  campaign-wide; a pure level-boost won't fix class holes (e.g. Wolfram Spd-15% doubling) so it'd
  need a survivability floor. Nicolas also floated an alt framing: instead level the fielded party
  to ≈ vanilla's 4 (caveat: vanilla's output is Seth-concentrated, so a flat ensemble bump can't
  match it — *someone* still has to anchor).
- **Per-unit anchor tweak** — e.g. Wolfram +3 Spd → survivability 1.8→3.9 (stops the fighter double).
- **Guest veteran (a Jagen)** fielded in Ch1, like the prologue's Scramsax.
- **deploy_limit 4 → 5/6** (output 44%→50–55%) — Nicolas wants to discuss; **undecided**.
- **Forest-cover routing** (free, +20 avo → squishies 1.9→2.6) — secondary.
- **Generous campaign EXP** — long-game lever; barely moves Ch1 durability (def growths 5–15%).
- **AVOID:** nerfing the (already-gentle) enemies; blanket party-leveling (doesn't fix durability).

**Offered next step (NOT greenlit):** extend `tools/balance_report.py` to model "lord-mode" at 2–3
tiers across all 7 lord candidates, to pick the dial on numbers. Nicolas may want to keep weighing
the *concept* (lord-anchor vs party-bump vs guest vs deploy) before any modelling.

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
